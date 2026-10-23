"""Section B pipeline UI: pipeline status, review queue, skills explorer, 3D skill map (reads/writes Supabase).

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
import ast
import csv
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
LEARN = ROOT / "learn"  # study pages, linked from the pipeline diagram
LOGS = {  # the only files /api/logs may read (scheduled jobs; see scripts/*.cmd)
    "qwen": ("Qwen batch (extract)", ROOT / "reports" / "extract_sample2000_qwen.log"),
    "load": ("Hourly load to Supabase", ROOT / "reports" / "task_load_qwen.log"),
    "greenhouse": ("Nightly Greenhouse", ROOT / "reports" / "task_greenhouse.log"),
}
INTRUSION = ROOT / "reports" / "intrusion"  # src/intrusion_test.py make -> items.json; the UI appends answers.csv
SAMPLE = ROOT / "data" / "processed" / "extraction_sample_2000.csv"
BATCH_MODEL, BATCH_PROMPT = "qwen/qwen3.8-27b", ROOT / "prompts" / "skill_extraction_v3.txt"
SKILL_MAP = ROOT / "data" / "processed" / "sprint3_full_2026-10-22" / "canonical_v2" / "skill_map_3d.csv"
STAGES = ["fetch", "clean", "dedupe", "extract", "link", "load"]
TASKS = {"extract": r"\SkillPipeline\QwenBatch", "load": r"\SkillPipeline\LoadQwen"}  # Windows Task Scheduler
DECISIONS = {"skill": "known_skill", "trait": "trait", "not_a_skill": "not_a_skill", "alias": "known_skill"}


LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Sign in - Section B</title>
<style>:root{color-scheme:light dark}body{margin:0;min-height:100vh;display:grid;place-items:center;
font:15px/1.5 system-ui,Segoe UI,sans-serif;background:#15171a;color:#e7e9ec}
form{background:#1d2024;border:1px solid #30343a;border-radius:10px;padding:22px 24px;width:min(340px,90vw);display:grid;gap:10px}
h1{font-size:18px;margin:0}p{margin:0;color:#9aa1ab;font-size:13px}input,button{font:inherit;padding:8px 10px;border-radius:6px}
input{border:1px solid #30343a;background:#15171a;color:inherit}button{border:0;background:#8aa8ff;color:#10131a;font-weight:600;cursor:pointer}
.err{color:#ff9a85}</style></head><body><form method="post" action="/login">
<h1>Skill Pipeline - Section B</h1><p>Enter the team password to open the dashboard.</p>
<input type="password" name="password" autocomplete="current-password" aria-label="Password" autofocus required>
{error}<button type="submit">Sign in</button></form></body></html>"""


def session_token(password):
    """Stateless session: HMAC of the password, so changing UI_PASSWORD logs everyone out."""
    import hashlib
    import hmac
    return hmac.new(password.encode(), b"section-b-ui-session", hashlib.sha256).hexdigest()


def authorized(environ):
    """True when UI_PASSWORD is unset (local use), or the request has the session cookie / Basic auth (curl)."""
    import base64
    import hmac
    from http.cookies import SimpleCookie
    password = os.getenv("UI_PASSWORD")
    if not password:
        return True
    cookie = SimpleCookie(environ.get("HTTP_COOKIE", ""))
    if "sb_session" in cookie and hmac.compare_digest(cookie["sb_session"].value, session_token(password)):
        return True
    header = environ.get("HTTP_AUTHORIZATION", "")
    if header.startswith("Basic "):
        try:
            given = base64.b64decode(header[6:]).decode("utf-8").split(":", 1)[1]
            return hmac.compare_digest(given.encode(), password.encode())
        except (ValueError, IndexError):
            return False
    return False


def login(environ, start):
    """GET: the sign-in page. POST: check the password, set a 7-day cookie, go to the dashboard."""
    import hmac
    error = ""
    if environ["REQUEST_METHOD"] == "POST":
        size = int(environ.get("CONTENT_LENGTH") or 0)
        given = parse_qs(environ["wsgi.input"].read(size).decode("utf-8", errors="replace")).get("password", [""])[0]
        password = os.getenv("UI_PASSWORD", "")
        if password and hmac.compare_digest(given.encode(), password.encode()):
            secure = "; Secure" if environ.get("HTTP_X_FORWARDED_PROTO") == "https" else ""
            start("303 See Other", [("Location", "/"), ("Set-Cookie", f"sb_session={session_token(password)}; Path=/; "
                                                                    f"Max-Age=604800; HttpOnly; SameSite=Lax{secure}")])
            return [b""]
        error = '<p class="err">Wrong password. Try again.</p>'
    start("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")])
    return [LOGIN_PAGE.replace("{error}", error).encode("utf-8")]


class App:
    def __init__(self):
        self.con, self._batch, self._tasks, self._lf = None, (0, None), (0, {}), (0, None)

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
            files = [ROOT / "cache" / "groq" / f"{hashlib.sha256(f'{BATCH_MODEL}|{sha}|{t}'.encode()).hexdigest()}.json"
                     for t in texts]
            times = [f.stat().st_mtime for f in files if f.exists()]
            self._batch = (time.time(), {"model": BATCH_MODEL, "done": len(times), "total": len(texts),
                                         "last_ts": max(times) if times else None, "times": sorted(times)})
        return self._batch[1]

    def models(self):
        """Extractor scores, read from the evaluate.py reports, plus a map of the code files (docstring line 1)."""
        runs = []
        for f in sorted((ROOT / "reports").glob("sprint2_extraction_quality_*.md")):
            text = f.read_text(encoding="utf-8")
            ex = re.search(r"\*\*Extractor:\*\* `([^`]+)` via (\S+), prompt `([^`]+)`", text)
            gold = re.search(r"\*\*Gold set:\*\* (\d+) postings, (\d+) gold skills \(`([^`]+)`\)", text)
            row = re.search(r"\| \*\*All\*\* \|(.+)", text)
            if not (ex and gold and row):
                continue
            n = [float(x) for x in row.group(1).split("|") if x.strip()]
            tag = f.stem.removeprefix("sprint2_extraction_quality_")
            runs.append({"model": ex.group(1), "provider": ex.group(2), "prompt": ex.group(3).removeprefix("skill_extraction_"),
                         "split": "test" if "_test" in tag else "dev" if "_dev" in tag else "all 100 (Sprint 2)",
                         "gold": "v2 (traits dropped)" if "gold_labels_v2" in gold.group(3) else "v1",
                         "variant": "kNN examples" if "knn" in tag else "", "postings": int(gold.group(1)),
                         "p_strict": n[3], "r_strict": n[4], "f1_strict": n[5], "p_lenient": n[6], "r_lenient": n[7],
                         "f1_lenient": n[8], "report": f"reports/{f.name}"})
        files = []
        for pattern in ("src/*.py", "app/server.py", "prompts/*.txt", "scripts/*.cmd", "sql/*.sql"):
            for f in sorted(ROOT.glob(pattern)):
                text = f.read_text(encoding="utf-8", errors="replace")
                if f.suffix == ".py":
                    doc = (ast.get_docstring(ast.parse(text)) or "").splitlines()[:1]
                    doc = doc[0] if doc else ""
                else:  # first comment line of a .cmd / .sql file; prompts have none
                    doc = next((re.sub(r"^(rem|--)\s*", "", l.strip()) for l in text.splitlines()
                                if l.strip().startswith(("rem ", "--"))), "")
                files.append({"path": f.relative_to(ROOT).as_posix(), "doc": doc})
        return {"runs": runs, "files": files, "root": ROOT.as_posix()}

    def langfuse(self):
        """Langfuse connection check (keys from .env, never sent to the browser), refreshed every 60 s."""
        pk, sk = os.getenv("LANGFUSE_PUBLIC_KEY"), os.getenv("LANGFUSE_SECRET_KEY")
        host = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").rstrip("/")
        if not (pk and sk):
            return {"state": "no_keys", "url": host}
        if time.time() - self._lf[0] > 60:
            import base64
            import urllib.request
            auth = {"Authorization": "Basic " + base64.b64encode(f"{pk}:{sk}".encode()).decode()}
            get = lambda p: json.load(urllib.request.urlopen(urllib.request.Request(host + p, headers=auth), timeout=8))
            try:
                from urllib.parse import quote
                project = get("/api/public/projects")["data"][0]["id"]
                # v2 API (the v1 /traces endpoint answers 410 Gone): count LLM calls (GENERATION observations; each
                # call also has a wrapper SPAN), then fetch the newest observation
                q = {"view": "observations", "metrics": [{"measure": "count", "aggregation": "count"}], "dimensions": [],
                     "filters": [{"column": "type", "operator": "=", "value": "GENERATION", "type": "string"}],
                     "fromTimestamp": "2026-01-01T00:00:00Z", "toTimestamp": "2100-01-01T00:00:00Z"}
                count = get("/api/public/v2/metrics?query=" + quote(json.dumps(q)))["data"][0]["count_count"]
                newest = get("/api/public/v2/observations?limit=1&fromStartTime=2026-01-01T00:00:00Z")["data"]
                out = {"state": "connected", "url": f"{host}/project/{project}/traces", "traces": int(count),
                       "last_trace": newest[0].get("startTime") if newest else None}
            except Exception as e:  # wrong keys, wrong region or offline: show it, do not break the page
                out = {"state": "error", "url": host, "error": f"{type(e).__name__}: {str(e)[:120]}"}
            self._lf = (time.time(), out)
        return self._lf[1]

    def intrusion_items(self):
        """Blind test items (no key) plus the items this rater already answered."""
        if not (INTRUSION / "items.json").exists():
            raise ValueError("no test yet: run  py src/intrusion_test.py make ...")
        items = json.loads((INTRUSION / "items.json").read_text(encoding="utf-8"))
        done = {}
        if (INTRUSION / "answers.csv").exists():
            with (INTRUSION / "answers.csv").open(encoding="utf-8") as f:
                done = {r["item"]: r["choice"] for r in csv.DictReader(f)}
        return {"items": items, "answers": done}

    def intrusion_answer(self, body):
        items = {str(i["item"]): i for i in json.loads((INTRUSION / "items.json").read_text(encoding="utf-8"))}
        item, choice, rater = str(body.get("item")), body.get("choice"), (body.get("rater") or "").strip()
        if item not in items or choice not in items[item]["skills"]:
            raise ValueError("unknown item or choice")
        if not rater:
            raise ValueError("enter your name first")
        path = INTRUSION / "answers.csv"
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["item", "choice", "rater", "answered_at"])
            w.writerow([item, choice, rater, time.strftime("%Y-%m-%dT%H:%M:%S")])
        return {"ok": True}

    def logs(self, q):
        """Last lines of one whitelisted job log, plus when it was last written."""
        name = q.get("name", "qwen")
        if name not in LOGS:
            raise ValueError(f"unknown log: {name}")
        title, path = LOGS[name]
        lines = max(20, min(int(q.get("lines", 200)), 1000))
        if not path.exists():
            return {"name": name, "title": title, "path": path.relative_to(ROOT).as_posix(), "lines": [], "modified": None}
        with path.open("rb") as f:  # read only the tail: the logs grow all day
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 200_000))
            text = f.read().decode("utf-8", errors="replace")
        return {"name": name, "title": title, "path": path.relative_to(ROOT).as_posix(),
                "lines": text.splitlines()[-lines:], "modified": path.stat().st_mtime,
                "logs": {k: v[0] for k, v in LOGS.items()}}

    def statement_sample(self, q):
        """One posting's journey: its statements as stored, plus alias -> canonical, verdict and topic per skill."""
        pid = q.get("posting")
        if not pid:  # a random Qwen-extracted posting with a handful of skills
            row = self.q("""select posting_id from skill_statements where model = %(m)s
                            group by 1 having count(*) between 5 and 14 order by random() limit 1""", {"m": BATCH_MODEL})
            if not row:
                raise ValueError("no extracted postings yet")
            pid = row[0]["posting_id"]
        post = self.q("""select posting_id, source, company, title, location, sector, left(description, 700) excerpt
                         from postings where posting_id = %(p)s""", {"p": pid})
        rows = self.q("""select s.statement_id, s.skill, s.skill_key, s.evidence, s.evidence_in_text, s.model, s.prompt_version,
                                s.run_id, s.created_at, coalesce(a.skill_key, s.skill_key) canonical, a.rule alias_rule,
                                l.verdict, l.source ref_source, l.ref_label, t.topic_id, t.state topic_state, tp.label topic_label
                         from skill_statements s
                         left join skill_aliases a on a.alias_key = s.skill_key
                         left join skill_links l on l.skill_key = s.skill_key
                         left join active_skill_topics t on t.skill_key = coalesce(a.skill_key, s.skill_key)
                         left join topics tp on tp.topic_id = t.topic_id
                         where s.posting_id = %(p)s and s.model = %(m)s order by s.statement_id""",
                      {"p": pid, "m": q.get("model", BATCH_MODEL)})  # one model: the pipeline extractor
        lib = {r["skill_key"] for r in self.q("select skill_key from skill_library")}
        for r in rows:
            r["in_library"] = r["canonical"] in lib
            r["created_at"] = r["created_at"].isoformat() if r["created_at"] else None
        return {"posting": post[0] if post else {"posting_id": pid}, "statements": rows}

    def tasks(self):
        """Status and next run of the scheduled jobs (schtasks), refreshed every 30 s. Empty off Windows."""
        if time.time() - self._tasks[0] > 30:
            out = {}
            for name, tn in TASKS.items():
                try:
                    r = subprocess.run(["schtasks", "/query", "/tn", tn, "/fo", "CSV", "/nh"],
                                       capture_output=True, text=True, timeout=10)
                    row = next(csv.reader(r.stdout.splitlines()), None)
                    if row and len(row) >= 3:
                        out[name] = {"task": tn, "next_run": row[1], "state": row[2]}
                except (OSError, subprocess.SubprocessError):
                    pass
            self._tasks = (time.time(), out)
        return self._tasks[1]

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
        history = self.q("""select date_trunc('hour', created_at) ts, count(*) n from skill_statements
                            where model = %(m)s group by 1 order by 1""", {"m": BATCH_MODEL})
        try:  # Sprint 3 taxonomy tables (sql/taxonomy_schema.sql); absent on an older database
            taxonomy = self.q("""select (select count(*) from topics where status = 'active') topics,
                (select count(*) from skill_library) library,
                (select count(*) from library_links where strength = 'strong') strong_links""")[0]
            # counted on the cleaned names, like the taxonomy (excel + microsoft excel = one skill)
            top = self.q("""select coalesce(a.skill_key, s.skill_key) skill_key, count(distinct s.posting_id) n
                            from skill_statements s left join skill_aliases a on a.alias_key = s.skill_key
                            group by 1 order by 2 desc limit 15""")
        except Exception:
            taxonomy = None
            top = self.q("""select skill_key, count(distinct posting_id) n from skill_statements
                            group by 1 order by 2 desc limit 15""")
        return {"counts": counts, "verdicts": verdicts, "runs": runs, "latest": latest, "events": events[-80:],
                "stages": stages, "active_model": last["model"] if last else None, "switches": switches,
                "models": models, "batch": self.batch_progress(), "tasks": self.tasks(),
                "history": history, "top_skills": top, "taxonomy": taxonomy,
                "langfuse": self.langfuse()}

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

    def skill_map(self):
        """Active clustering run: 3D points (from SKILL_MAP, display only) + topic and library info per skill."""
        if not SKILL_MAP.exists():
            raise ValueError(f"no skill map file: run src/make_skill_map.py ({SKILL_MAP.name})")
        import pandas as pd
        pts = pd.read_csv(SKILL_MAP, keep_default_na=False)
        mem = pd.DataFrame(self.q("""select a.skill_key, a.topic_id, a.state, (l.skill_key is not null) as lib
            from active_skill_topics a left join skill_library l using (skill_key) where a.role = 'primary'"""))
        if mem.empty:
            raise ValueError("no active clustering run in Supabase: run src/load_taxonomy.py --activate")
        pts = pts.merge(mem, on="skill_key")
        run = self.q("select run_id, method from cluster_runs where is_active")[0]
        topics = self.q("select topic_id, label, is_transversal from topics where status = 'active'")
        return {"run": run, "topics": topics,
                "points": {c: pts[c].tolist() for c in ["skill_key", "mention_count", "x", "y", "z", "topic_id",
                                                         "state", "lib"]}}

    def library(self):
        rows = self.q("""select s.skill_key, s.status, s.n_postings, s.n_sectors, s.entropy, s.skill_type, s.reuse_level,
                s.rule_version, l.topic_id, t.label, l.n_postings as link_postings, l.n_templates as link_templates,
                l.lift, l.q_value, l.strength
            from skill_library s left join library_links l using (skill_key) left join topics t using (topic_id)
            order by s.n_postings desc, l.p_value""")
        out = {}
        for r in rows:
            e = out.setdefault(r["skill_key"], {k: r[k] for k in ("skill_key", "status", "n_postings", "n_sectors",
                                                                  "entropy", "skill_type", "reuse_level",
                                                                  "rule_version")} | {"links": []})
            if r["topic_id"]:
                e["links"].append({k: r[k] for k in ("topic_id", "label", "link_postings", "link_templates", "lift",
                                                     "q_value", "strength")})
        return list(out.values())

    def __call__(self, environ, start):
        path, method = environ.get("PATH_INFO", "/"), environ["REQUEST_METHOD"]
        q = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()}
        if path == "/login":
            return login(environ, start)
        if not authorized(environ):  # only when UI_PASSWORD is set (sharing through a tunnel)
            if path.startswith("/api/"):
                return self.send(start, {"error": "not signed in"}, "401 Unauthorized")
            start("303 See Other", [("Location", "/login")])
            return [b""]
        try:
            if path == "/" or path.startswith(("/static/", "/learn/")):
                base = LEARN if path.startswith("/learn/") else STATIC
                f = base / ("index.html" if path == "/" else path.split("/", 2)[2])
                if f.resolve().parent != base.resolve() or not f.is_file():  # no path tricks
                    return self.send(start, {"error": "not found"}, "404 Not Found")
                start("200 OK", [("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream"),
                                 ("Cache-Control", "no-store")])
                return [f.read_bytes()]
            if method == "GET":
                routes = {"/api/status": self.status, "/api/review/queue": lambda: self.queue(q),
                          "/api/review/skill": lambda: self.skill(q.get("key", "").lower()),
                          "/api/skills": lambda: self.skills(q), "/api/reviews": self.reviews,
                          "/api/map": self.skill_map, "/api/library": self.library, "/api/models": self.models,
                          "/api/intrusion/items": self.intrusion_items, "/api/logs": lambda: self.logs(q),
                          "/api/statements/sample": lambda: self.statement_sample(q)}
                if path in routes:
                    return self.send(start, routes[path]())
            if method == "POST" and path == "/api/intrusion/answer":
                size = int(environ.get("CONTENT_LENGTH") or 0)
                return self.send(start, self.intrusion_answer(json.loads(environ["wsgi.input"].read(size) or b"{}")))
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
