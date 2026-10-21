"""Section B pipeline UI: pipeline status, human review queue, skills explorer (reads/writes Supabase).

    py app/server.py              # http://127.0.0.1:8765/   (Ctrl+C to stop)
    py app/server.py --port 8800

Standard library web server (WSGI), bound to 127.0.0.1. It connects to Supabase with SUPABASE_DB_URL
from .env and never sends a key to the browser. The look is copied from Lochan's Team B dashboard
(taxonomy-skill-project/src/dashboard_static).

Review decisions are appended to review_decisions and applied to skill_links (review_status = reviewed),
so the automatic ESCO / O*NET linker never overwrites them and the same skill is not reviewed twice.
"""
import argparse
import hashlib
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
SAMPLE = ROOT / "data" / "processed" / "extraction_sample_2000.csv"
BATCH_MODEL, BATCH_PROMPT = "qwen/qwen3.8-27b", ROOT / "prompts" / "skill_extraction_v3.txt"
STAGES = ["fetch", "clean", "dedupe", "extract", "link", "load"]
DECISIONS = {"skill": "known_skill", "trait": "trait", "not_a_skill": "not_a_skill", "alias": "known_skill"}


class App:
    def __init__(self):
        self.con, self._batch = None, (0, None)

    def q(self, sql, params=None):
        """Rows as dicts; reconnects once if the pooled connection dropped."""
        for attempt in (1, 2):
            try:
                if self.con is None or self.con.closed:
                    self.con = db.connect()
                cur = self.con.execute(sql, params or {})
                if cur.description is None:
                    return []
                cols = [c.name for c in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
            except Exception:
                self.con = None
                if attempt == 2:
                    raise

    def batch_progress(self):
        """Kaggle batch (Groq Qwen, extract_skills.py) progress, counted from its cache every 30 s."""
        if time.time() - self._batch[0] > 30 and SAMPLE.exists():
            import pandas as pd
            sha = hashlib.sha256(BATCH_PROMPT.read_text(encoding="utf-8").encode()).hexdigest()
            texts = pd.read_csv(SAMPLE, encoding="utf-8-sig").description
            done = sum((ROOT / "cache" / "groq" /
                        f"{hashlib.sha256(f'{BATCH_MODEL}|{sha}|{t}'.encode()).hexdigest()}.json").exists() for t in texts)
            self._batch = (time.time(), {"model": BATCH_MODEL, "done": done, "total": len(texts)})
        return self._batch[1]

    def status(self):
        counts = self.q("""select
            (select count(*) from postings where source = 'kaggle') kaggle,
            (select count(*) from postings where source = 'greenhouse') greenhouse,
            (select count(*) from skill_statements) statements,
            (select count(*) from skill_links) unique_skills,
            (select count(*) from review_decisions) decisions,
            pg_database_size(current_database()) db_bytes""")[0]
        verdicts = self.q("""select l.verdict, count(*) n from skill_statements s join skill_links l using (skill_key)
                             group by 1 order by 2 desc""")
        runs = self.q("select * from pipeline_runs order by started_at desc limit 8")
        latest = runs[0] if runs else None
        events = self.q("select * from pipeline_events where run_id = %(r)s order by id",
                        {"r": latest["run_id"]}) if latest else []
        stages = {s: None for s in STAGES}
        for e in events:
            if e["stage"] in stages:
                stages[e["stage"]] = e["status"]
        last = next((e for e in reversed(events) if e["model"]), None)
        switches = self.q("select * from pipeline_events where stage = 'model_switch' order by id desc limit 10")
        models = self.q("select model, count(*) n from skill_statements group by 1 order by 2 desc")
        return {"counts": counts, "verdicts": verdicts, "runs": runs, "latest": latest, "events": events[-80:],
                "stages": stages, "active_model": last["model"] if last else None, "switches": switches,
                "models": models, "batch": self.batch_progress(),
                "langfuse": bool(os.getenv("LANGFUSE_PUBLIC_KEY")),
                "langfuse_url": os.getenv("LANGFUSE_PROJECT_URL") or os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"}

    def queue(self, q):
        return self.q("""select l.skill_key, l.ref_label, l.source, l.score, count(*) n
            from skill_links l join skill_statements s using (skill_key)
            where l.verdict = 'new_candidate' and l.review_status = 'auto' and l.skill_key like %(like)s
            group by 1, 2, 3, 4 order by n desc, 1 limit 300""", {"like": f"%{q.get('q', '').lower()}%"})

    def skill(self, key):
        link = self.q("select * from skill_links where skill_key = %(k)s", {"k": key})
        examples = self.q("""select s.posting_id, s.skill, s.evidence, s.model, p.title, p.company, p.source, p.url,
                                    p.description
                             from skill_statements s join postings p using (posting_id)
                             where s.skill_key = %(k)s order by p.source desc, s.posting_id limit 6""", {"k": key})
        history = self.q("select * from review_decisions where skill_key = %(k)s order by id desc", {"k": key})
        return {"link": link[0] if link else None, "examples": examples, "history": history}

    def decide(self, body):
        key, decision = str(body.get("skill_key", "")).strip().lower(), body.get("decision")
        reviewer, alias = str(body.get("reviewer", "")).strip(), str(body.get("alias_of") or "").strip()
        if not key or decision not in DECISIONS or not reviewer:
            raise ValueError("skill_key, a valid decision and a reviewer ID are required")
        if decision == "alias" and not alias:
            raise ValueError("an alias needs the canonical skill name")
        self.q("""insert into review_decisions (skill_key, decision, alias_of, reviewer, note)
                  values (%(k)s, %(d)s, %(a)s, %(r)s, %(n)s)""",
               {"k": key, "d": decision, "a": alias or None, "r": reviewer, "n": body.get("note") or None})
        self.q("""update skill_links set verdict = %(v)s, source = 'human review', ref_label = %(l)s, ref_id = null,
                  score = null, match = 'review', review_status = 'reviewed', updated_at = now()
                  where skill_key = %(k)s""",
               {"v": DECISIONS[decision], "l": alias or key, "k": key})
        return {"ok": True}

    def skills(self, q):
        return self.q("""select l.skill_key, l.verdict, l.source, l.ref_label, l.review_status, count(*) n
            from skill_statements s join skill_links l using (skill_key)
            where (%(v)s = '' or l.verdict = %(v)s) and l.skill_key like %(like)s
            group by 1, 2, 3, 4, 5 order by n desc limit 300""",
                      {"v": q.get("verdict", ""), "like": f"%{q.get('q', '').lower()}%"})

    def reviews(self):
        return self.q("select * from review_decisions order by id desc limit 50")

    def __call__(self, environ, start):
        path, method = environ.get("PATH_INFO", "/"), environ["REQUEST_METHOD"]
        q = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()}
        try:
            if path == "/" or path.startswith("/static/"):
                f = STATIC / ("index.html" if path == "/" else path.removeprefix("/static/"))
                if f.resolve().parent != STATIC.resolve() or not f.is_file():  # no path tricks
                    return self.send(start, {"error": "not found"}, "404 Not Found")
                start("200 OK", [("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream"),
                                 ("Cache-Control", "no-store")])
                return [f.read_bytes()]
            if method == "GET":
                routes = {"/api/status": self.status, "/api/review/queue": lambda: self.queue(q),
                          "/api/review/skill": lambda: self.skill(q.get("key", "").lower()),
                          "/api/skills": lambda: self.skills(q), "/api/reviews": self.reviews}
                if path in routes:
                    return self.send(start, routes[path]())
            if method == "POST" and path == "/api/review/decision":
                size = int(environ.get("CONTENT_LENGTH") or 0)
                return self.send(start, self.decide(json.loads(environ["wsgi.input"].read(size) or b"{}")))
            return self.send(start, {"error": "not found"}, "404 Not Found")
        except ValueError as e:
            return self.send(start, {"error": str(e)}, "400 Bad Request")
        except Exception as e:
            return self.send(start, {"error": f"{type(e).__name__}: {str(e)[:200]}"}, "500 Internal Server Error")

    @staticmethod
    def send(start, obj, status="200 OK"):
        body = json.dumps(obj, default=str).encode()
        start(status, [("Content-Type", "application/json"), ("Cache-Control", "no-store")])
        return [body]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    print(f"Pipeline UI on http://127.0.0.1:{args.port}/  (Ctrl+C to stop)")
    make_server("127.0.0.1", args.port, App()).serve_forever()


if __name__ == "__main__":
    main()
