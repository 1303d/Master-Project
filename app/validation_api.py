"""Gold Validation page API (mounted by app/server.py under /validation and /api/validation/*).

Reads and writes only repository files (data/validation/, reports/validation/); no database, no API calls.
Blindness is enforced here, not only in the browser:
  - Part 2 items carry only the candidate label; the key and other reviewers' decisions are returned only
    after this reviewer has submitted that item (/reveal).
  - Part 3 never returns gold labels or model output until this reviewer has submitted the posting (/compare).
  - Adjudication cases of Parts 2-3 are redacted for a reviewer who has not submitted that item yet.
  - Every un-blinding (/reveal, /compare, an unredacted Part 2-3 case) is logged as a 'reveal' event first, so
    later amendments are marked post-reveal and never change official scores (validation/reviews.py).
Posting text is served only for postings inside an active manifest (never test or protected postings).
"""
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from validation import adjudication, manifests, reporting  # noqa: E402
from validation.cli import artifacts  # noqa: E402
from validation.config import PARTS, Config  # noqa: E402
from validation.reviews import ReviewStore  # noqa: E402
from validation.sources import MissingArtifact, load_gold, load_postings  # noqa: E402
from validation.storage import read_jsonl  # noqa: E402

PAGE = Path(__file__).resolve().parent / "static" / "validation.html"


class ValidationAPI:
    def __init__(self, cfg=None):
        self.cfg = cfg or Config()
        self.store = ReviewStore(self.cfg)

    # ---------- helpers ----------
    def manifest(self, part):
        m = manifests.active(self.cfg, int(part))
        if m is None:
            raise MissingArtifact(f"data/validation/manifests/part{part}_v1.json",
                                  "not built yet: press 'Build samples' or run python src/validation/cli.py build")
        return m

    def item(self, part, item_id):
        m = self.manifest(part)
        it = next((i for i in m["items"] if i["item_id"] == item_id), None)
        if it is None:
            raise ValueError(f"{item_id} is not in {m['manifest_id']}")
        return m, it

    def description(self, posting_id):
        gold, _ = load_gold(self.cfg)
        if posting_id not in gold:  # test, unknown-split and protected postings are never served
            raise ValueError("posting is not eligible for validation")
        texts, path = load_postings(self.cfg, [posting_id])
        return texts.get(posting_id), path

    def submitted(self, reviewer, m, item_id):
        return self.store.state(reviewer, m["manifest_id"]).get(item_id, {}).get("latest")

    # ---------- GET ----------
    def status(self):
        mans, bad = [], []
        for p in PARTS:
            m = manifests.active(self.cfg, p)
            mans.append({"part": p, "manifest_id": m["manifest_id"], "items": len(m["items"]),
                         "created_utc": m["created_utc"], "sources": m["sources"], "rules": m["rules"],
                         "settings": m["settings"], "population": m["population"],
                         "stale_sources": manifests.stale_sources(self.cfg, m)} if m else {"part": p, "manifest_id": None})
        for r in self.cfg.reviewers:
            bad += read_jsonl(self.cfg.reviews_file(r))[1] + read_jsonl(self.cfg.adjudication_file(r))[1]
        try:
            summary = reporting.summary(self.cfg)
        except MissingArtifact as e:
            summary = {"error": str(e)}
        return {"reviewers": self.cfg.reviewers, "rule_choices": self.cfg.rule_choices, "artifacts": artifacts(self.cfg),
                "manifests": mans, "summary": summary, "broken_log_lines": bad}

    def items(self, q):
        part, reviewer = int(q.get("part", 0)), self.cfg.check_reviewer(q.get("reviewer"))
        m = self.manifest(part)
        mine = self.store.state(reviewer, m["manifest_id"])
        out = []
        for it in m["items"]:
            s = mine.get(it["item_id"], {"status": "PENDING", "draft": None, "versions": [], "latest": None})
            row = {"item_id": it["item_id"], "posting_id": it["posting_id"], "n": it["n"], "status": s["status"],
                   "draft": s["draft"], "latest": s["latest"], "versions": s["versions"]}
            if part == 1:
                row.update(type=it["type"], label=it["label"], runs=it["runs"], stale=it.get("stale", False))
            elif part == 2:
                row["label"] = it["label"]  # blind: no source, no run, no gold status
            out.append(row)
        return {"manifest_id": m["manifest_id"], "stale_sources": manifests.stale_sources(self.cfg, m), "items": out}

    def posting(self, q):
        _, it = self.item(q.get("part", 0), q.get("item"))
        text, path = self.description(it["posting_id"])
        if text is None:
            return {"missing": True, "posting_id": it["posting_id"],
                    "message": "Posting text is not on this machine. Copy gold_postings_dev.csv from the team "
                               "Drive into data/gold/ (it is gitignored), then reload."}
        return {"missing": False, "posting_id": it["posting_id"], "description": text, "file": self.cfg.rel(path)}

    def reveal(self, q):
        reviewer = self.cfg.check_reviewer(q.get("reviewer"))
        m, it = self.item(2, q.get("item"))
        if not self.submitted(reviewer, m, it["item_id"]):
            raise PermissionError("submit your own decision first; the reference stays hidden until then")
        others = {r: st[it["item_id"]]["latest"] for r, st in self.store.all_states(m["manifest_id"]).items()
                  if r != reviewer and st.get(it["item_id"], {}).get("latest")}
        self.store.record_reveal(reviewer, m, [it["item_id"]], "reveal")
        return {"reference": manifests.part2_key(self.cfg, m["manifest_id"]).get(it["item_id"]), "others": others}

    def compare(self, q):
        reviewer = self.cfg.check_reviewer(q.get("reviewer"))
        m, it = self.item(3, q.get("item"))
        latest = self.submitted(reviewer, m, it["item_id"])
        if not latest:
            raise PermissionError("submit your annotation first; gold labels stay hidden until then")
        from validation.full_posting import compare
        rows = compare(self.cfg, it["posting_id"], latest)
        self.store.record_reveal(reviewer, m, [it["item_id"]], "compare")
        return {"rows": rows}

    def cases(self, q):
        reviewer = self.cfg.check_reviewer(q.get("reviewer"))
        out, shown = [], {}
        for c in adjudication.build_cases(self.cfg, self.store):
            if c["part"] in (2, 3):
                m = self.manifest(c["part"])
                if not self.submitted(reviewer, m, c["item_id"]):
                    out.append({"case_id": c["case_id"], "part": c["part"], "status": c["status"], "redacted": True})
                    continue
                shown.setdefault(c["part"], (m, set()))[1].add(c["item_id"])
            out.append(c)
        for m, ids in shown.values():  # this reviewer now sees others' reviews for these items
            self.store.record_reveal(reviewer, m, sorted(ids), "cases")
        return out

    def rules(self):
        return {"file": self.cfg.rel(self.cfg.p("rules")), "text": self.cfg.p("rules").read_text(encoding="utf-8")}

    # ---------- POST ----------
    def review(self, body):
        part = int(body.get("part", 0))
        m, it = self.item(part, body.get("item_id"))
        text = self.description(it["posting_id"])[0] if part == 3 else None
        e = self.store.record(body.get("reviewer"), m, it["item_id"], body.get("action"), body.get("data") or {},
                              description=text, amend_reason=body.get("amend_reason", ""))
        return {"ok": True, "event": e}

    def adjudicate(self, body):
        e = adjudication.adjudicate(self.cfg, body.get("adjudicator"), body.get("case_id"), body.get("decision"),
                                    body.get("rationale"), body.get("change"))
        return {"ok": True, "event": e}

    def build(self):
        """Create missing manifests only. A changed source needs the CLI (--new-version), on purpose."""
        out = {}
        for p in PARTS:
            if manifests.active(self.cfg, p) is None:
                m, st = manifests.ensure(self.cfg, p)
                out[p] = {"manifest_id": m["manifest_id"], "status": st}
        return out

    # ---------- WSGI ----------
    def __call__(self, environ, start):
        path, method = environ.get("PATH_INFO", "/"), environ["REQUEST_METHOD"]
        q = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()}
        try:
            if path in ("/validation", "/validation/"):
                start("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")])
                return [PAGE.read_bytes()]
            sub = path.removeprefix("/api/validation/")
            if method == "GET":
                routes = {"status": self.status, "items": lambda: self.items(q), "posting": lambda: self.posting(q),
                          "reveal": lambda: self.reveal(q), "compare": lambda: self.compare(q),
                          "cases": lambda: self.cases(q), "rules": self.rules}
                if sub in routes:
                    return self.send(start, routes[sub]())
            if method == "POST":
                size = int(environ.get("CONTENT_LENGTH") or 0)
                body = json.loads(environ["wsgi.input"].read(size) or b"{}")
                routes = {"review": lambda: self.review(body), "adjudicate": lambda: self.adjudicate(body),
                          "export": lambda: {"files": reporting.export(self.cfg)}, "build": self.build}
                if sub in routes:
                    return self.send(start, routes[sub]())
            return self.send(start, {"error": "not found"}, "404 Not Found")
        except PermissionError as e:
            return self.send(start, {"error": str(e)}, "403 Forbidden")
        except MissingArtifact as e:
            return self.send(start, {"error": str(e), "missing": e.path, "hint": e.hint}, "409 Conflict")
        except (manifests.StaleSources, FileExistsError) as e:
            return self.send(start, {"error": str(e)}, "409 Conflict")
        except ValueError as e:
            return self.send(start, {"error": str(e)}, "400 Bad Request")
        except Exception as e:
            return self.send(start, {"error": f"{type(e).__name__}: {str(e)[:200]}"}, "500 Internal Server Error")

    @staticmethod
    def send(start, obj, status="200 OK"):
        body = json.dumps(obj, default=str).encode()
        start(status, [("Content-Type", "application/json"), ("Cache-Control", "no-store")])
        return [body]
