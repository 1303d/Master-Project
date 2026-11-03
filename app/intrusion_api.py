"""Intrusion v2 reviewer page API (mounted by app/server.py: page /validation, endpoints /api/intrusion-v2/*).

Files only: no database, no LLM, no network. Reads the frozen questions.json and reads/writes one reviewer's
responses/<reviewer>.csv, in the exact schema src/intrusion_v2.py writes and scores
(reviewer, question_id, A, B, C, D, E, answer, note). Final submission calls intrusion_v2.submit(), the same lock
the CLI uses, so `python src/intrusion_v2.py score` works unchanged.

Blindness, enforced here and not only in the browser:
  - The answer key (data/interim/intrusion_v2/...) is never opened by this module.
  - Only question_id + the five option texts leave the server; never topic ids, labels, strata or the intruder.
  - A reviewer's request returns only that reviewer's own answers. Team status is submitted yes/no only.
  - No score is computed or returned here (scoring stays a separate CLI step after all three submitted).
File paths come only from the fixed reviewer list (no user-supplied path). Writes are atomic (temp file in the same
folder + os.replace) under a lock, and are read back before the client is told "saved".
The reviewer dropdown is not authentication: keep the server local (127.0.0.1) or behind UI_PASSWORD.
"""
import csv
import io
import json
import os
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import intrusion_v2 as iv  # noqa: E402

try:  # cross-process lock where available (macOS / Linux); the in-process lock always applies
    import fcntl
except ImportError:  # Windows: one server process, so the thread lock is enough
    fcntl = None

PAGE = Path(__file__).resolve().parent / "static" / "intrusion_v2.html"
HEADER = ["reviewer", "question_id", *iv.LETTERS, "answer", "note"]
NOTE_MAX = 500
_LOCK = threading.Lock()


class Locked(Exception):
    """The reviewer has submitted; answers can no longer change."""


class IntrusionAPI:
    def __init__(self, root=ROOT, run_id=iv.RUN_ID):
        self.root, self.run_id = Path(root), run_id
        self.out = iv.out_dir(self.root, run_id)

    # ---------- inputs ----------
    def reviewer(self, value):
        r = str(value or "").strip().lower()
        if r not in iv.REVIEWERS:  # whitelist: the only way a name reaches a file path
            raise ValueError(f"unknown reviewer; choose one of {', '.join(iv.REVIEWERS)}")
        return r

    def questions(self):
        """Blind view of the frozen questions: question_id and the five options, nothing else."""
        data = json.loads((self.out / "questions.json").read_text(encoding="utf-8"))
        qs = []
        for q in data["questions"]:
            opts = q["options"]
            if sorted(opts) != list(iv.LETTERS):
                raise ValueError(f"{q['question_id']}: expected options A-E")
            qs.append({"question_id": q["question_id"], "options": {x: opts[x] for x in iv.LETTERS}})
        return {"run_id": data["run_id"], "instructions": data["instructions"], "questions": qs}

    def path(self, reviewer):
        return self.out / "responses" / f"{reviewer}.csv"

    def submitted(self, reviewer):
        return iv.status(self.root, self.run_id)[reviewer]

    # ---------- response file ----------
    @contextmanager
    def locked(self, reviewer):
        self.path(reviewer).parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, open(self.out / "responses" / f".{reviewer}.lock", "a") as lf:
            if fcntl:
                fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl:
                    fcntl.flock(lf, fcntl.LOCK_UN)

    def ensure_file(self, reviewer):
        """Create the blank template (same bytes as intrusion_v2.make) if this clone has none (it is gitignored)."""
        p = self.path(reviewer)
        if not p.exists():
            iv.write_new(p, iv.template_csv(iv.load_questions(self.root, self.run_id), reviewer))

    def read(self, reviewer):
        """{qid: {"answer", "note"}} after the same checks the scorer uses (options untouched, no duplicates)."""
        _, problems, _ = iv.validate(self.root, self.run_id, reviewer)
        if problems:
            raise ValueError("response file has problems (fix or restore it before continuing): " + "; ".join(problems[:5]))
        with self.path(reviewer).open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        return {r["question_id"].strip(): {"answer": (r.get("answer") or "").strip().upper(), "note": r.get("note") or ""}
                for r in rows}

    def write_atomic(self, reviewer, saved):
        """Rewrite the whole file from the frozen questions + saved answers: temp file, fsync, os.replace."""
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(HEADER)
        for q in iv.load_questions(self.root, self.run_id):
            s = saved.get(q["question_id"], {})
            w.writerow([reviewer, q["question_id"], *(q["options"][x] for x in iv.LETTERS), s.get("answer", ""),
                        s.get("note", "")])
        target = self.path(reviewer)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{reviewer}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(buf.getvalue())
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target)  # atomic: readers see the old file or the new one, never half of one
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # ---------- endpoints ----------
    def responses(self, q):
        r = self.reviewer(q.get("reviewer"))
        with self.locked(r):
            self.ensure_file(r)
            saved = self.read(r)
        return {"reviewer": r, "answers": {k: v["answer"] for k, v in saved.items() if v["answer"]},
                "notes": {k: v["note"] for k, v in saved.items() if v["note"]}, **self.progress_of(r, saved)}

    def progress_of(self, reviewer, saved):
        answered = sum(1 for v in saved.values() if v["answer"])
        return {"answered": answered, "total": len(saved), "unanswered": len(saved) - answered,
                "submitted": self.submitted(reviewer)}

    def progress(self, q):
        out = self.responses(q)
        return {k: out[k] for k in ("reviewer", "answered", "total", "unanswered", "submitted")}

    def team(self):
        return {"submitted": iv.status(self.root, self.run_id), "all_submitted": all(iv.status(self.root, self.run_id).values())}

    def save(self, body):
        r = self.reviewer(body.get("reviewer"))
        qid = str(body.get("question_id") or "").strip()
        answer = str(body.get("answer") or "").strip().upper()
        note = " ".join(str(body.get("note") or "").split())[:NOTE_MAX]  # one line, bounded
        if qid not in {x["question_id"] for x in iv.load_questions(self.root, self.run_id)}:
            raise ValueError("unknown question")
        if answer not in set(iv.LETTERS):  # a set: "" or "AB" must not pass as a substring of "ABCDE"
            raise ValueError("answer must be one of A-E")
        with self.locked(r):
            if self.submitted(r):
                raise Locked(f"{r} has submitted; answers are locked")
            self.ensure_file(r)
            saved = self.read(r)
            saved[qid] = {"answer": answer, "note": note if "note" in body else saved.get(qid, {}).get("note", "")}
            self.write_atomic(r, saved)
            back = self.read(r)  # confirm what is on disk before reporting success
        if back[qid]["answer"] != answer:
            raise OSError("saved answer could not be read back")
        return {"ok": True, "question_id": qid, "answer": back[qid]["answer"], "note": back[qid]["note"],
                **self.progress_of(r, back)}

    def submit(self, body):
        r = self.reviewer(body.get("reviewer"))
        if body.get("confirm") is not True:
            raise ValueError("submission needs confirm: true")
        with self.locked(r):
            if self.submitted(r):
                raise Locked(f"{r} has already submitted")
            rec = iv.submit(self.root, self.run_id, r)  # validates all 24, writes submitted/<r>.json (create-only)
        return {"ok": True, "reviewer": r, "submitted_utc": rec["submitted_utc"], "answered": len(rec["answers"])}

    # ---------- WSGI ----------
    def __call__(self, environ, start):
        path, method = environ.get("PATH_INFO", "/"), environ["REQUEST_METHOD"]
        from urllib.parse import parse_qs
        q = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()}
        try:
            if path.rstrip("/") == "/validation" and method == "GET":
                start("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")])
                return [PAGE.read_bytes()]
            sub = path.removeprefix("/api/intrusion-v2/")
            if method == "GET":
                routes = {"questions": self.questions, "responses": lambda: self.responses(q),
                          "progress": lambda: self.progress(q), "team": self.team}
                if sub in routes:
                    return self.send(start, routes[sub]())
            if method == "POST":
                size = min(int(environ.get("CONTENT_LENGTH") or 0), 10_000)
                body = json.loads(environ["wsgi.input"].read(size) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("expected a JSON object")
                routes = {"answer": lambda: self.save(body), "submit": lambda: self.submit(body)}
                if sub in routes:
                    return self.send(start, routes[sub]())
            return self.send(start, {"error": "not found"}, "404 Not Found")
        except Locked as e:
            return self.send(start, {"error": str(e), "locked": True}, "409 Conflict")
        except (ValueError, json.JSONDecodeError) as e:
            return self.send(start, {"error": str(e)}, "400 Bad Request")
        except FileNotFoundError:
            return self.send(start, {"error": "intrusion v2 questions not found on this machine"}, "404 Not Found")
        except Exception as e:  # never echo file contents; type + short message only
            return self.send(start, {"error": f"save failed ({type(e).__name__})"}, "500 Internal Server Error")

    @staticmethod
    def send(start, obj, status="200 OK"):
        body = json.dumps(obj).encode()
        start(status, [("Content-Type", "application/json"), ("Cache-Control", "no-store")])
        return [body]
