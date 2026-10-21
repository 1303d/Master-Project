"""Live pipeline: Greenhouse -> clean -> dedupe -> LLM extract (LiteLLM fallback) -> ESCO/O*NET -> Supabase.

    py src/pipeline.py --max-new 10                 # all boards in config/boards.yaml, at most 10 new postings
    py src/pipeline.py --boards figma oura --max-new 5

Every stage writes rows to pipeline_events, which the UI shows live (app/server.py).
- fetch:   public Greenhouse Job Board API (no key), raw JSON kept in data/raw/greenhouse/<run_id>/
- clean:   HTML -> text with line breaks, emails/phones masked, postings under 200 characters skipped
- dedupe:  a posting whose text is already stored (any source, same text_hash) is skipped
- load:    every new posting is stored, so Supabase holds the whole live corpus
- extract: the oldest --max-new Greenhouse postings that have no skills yet (a queue: each run catches up),
           via llm_router.Extractor (Groq Qwen, fallback Gemini Flash); answers cached in cache/litellm/
- link:    new skills get an ESCO / O*NET verdict (rule E); human-reviewed skills keep their decision
"""
import argparse
import hashlib
import html
import json
import re
import time
from pathlib import Path

import requests
import yaml

import db
from gold_tool import hide_contacts
from llm_router import PROMPT, Extractor
from load_supabase import link_keys

ROOT = Path(__file__).resolve().parent.parent
BOARDS = ROOT / "config" / "boards.yaml"
API = "https://boards-api.greenhouse.io/v1/boards/{}/jobs?content=true"
CACHE = ROOT / "cache" / "litellm"


def clean(content):
    """Greenhouse 'content' is escaped HTML: unescape, keep paragraph/list breaks, drop tags, mask contacts."""
    t = html.unescape(content)
    t = re.sub(r"(?i)<\s*li[^>]*>", "\n- ", t)
    t = re.sub(r"(?i)<\s*(br|/p|/div|/li|/h\d|/ul|/ol)[^>]*>", "\n", t)
    t = re.sub(r"(?i)</?\s*(strong|b|em|i|u|span|a)\b[^>]*>", "", t)  # inline tags: no extra space
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", "\n".join(line.strip() for line in t.splitlines()))
    return hide_contacts(t.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boards", nargs="*", help="board tokens (default: all in config/boards.yaml)")
    ap.add_argument("--max-new", type=int, default=10, help="extract at most N new postings this run")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between LLM calls")
    args = ap.parse_args()

    boards = yaml.safe_load(BOARDS.read_text(encoding="utf-8"))["boards"]
    if args.boards:
        boards = [b for b in boards if b["board_token"] in args.boards]
    system = PROMPT.read_text(encoding="utf-8")
    prompt_sha = hashlib.sha256(system.encode()).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)

    with db.connect() as con:
        run_id = db.start_run(con, "greenhouse", note=f"boards: {', '.join(b['board_token'] for b in boards)}")
        try:
            # fetch
            db.event(con, run_id, "fetch", "start", f"{len(boards)} Greenhouse boards")
            raw_dir = ROOT / "data" / "raw" / "greenhouse" / run_id
            raw_dir.mkdir(parents=True, exist_ok=True)
            jobs = []
            for b in boards:
                r = requests.get(API.format(b["board_token"]), timeout=60)
                r.raise_for_status()
                (raw_dir / f"{b['board_token']}.json").write_text(r.text, encoding="utf-8")
                got = r.json().get("jobs", [])
                jobs += [(b, j) for j in got]
                db.event(con, run_id, "fetch", "progress", f"{b['company_name']}: {len(got)} jobs")
            db.event(con, run_id, "fetch", "done", f"{len(jobs)} jobs fetched")

            # clean
            db.event(con, run_id, "clean", "start", "HTML -> text, mask contacts")
            posts = []
            for b, j in jobs:
                text = clean(j.get("content", ""))
                if len(text) < 200:
                    continue
                posts.append({"posting_id": f"gh_{b['board_token']}_{j['id']}", "source": "greenhouse",
                              "company": b["company_name"], "title": j.get("title"),
                              "location": (j.get("location") or {}).get("name"),
                              "sector": ((j.get("departments") or [{}])[0] or {}).get("name"),
                              "url": j.get("absolute_url"), "description": text})
            db.event(con, run_id, "clean", "done", f"{len(posts)} usable ({len(jobs) - len(posts)} too short)")

            # dedupe
            db.event(con, run_id, "dedupe", "start", "skip postings already stored (same id or same text)")
            seen_ids = {r[0] for r in con.execute("select posting_id from postings").fetchall()}
            seen_hash = {r[0] for r in con.execute("select text_hash from postings").fetchall()}
            fresh, hashes = [], set()
            for p in posts:
                h = db.text_hash(p["description"])
                if p["posting_id"] in seen_ids or h in seen_hash or h in hashes:
                    continue
                hashes.add(h)
                fresh.append(p)
            db.event(con, run_id, "dedupe", "done", f"{len(fresh)} new, {len(posts) - len(fresh)} already stored")

            # store every new posting now; extraction then works through a queue (catches up night by night)
            db.event(con, run_id, "load", "start", "store new postings")
            new = db.upsert_postings(con, fresh)
            db.event(con, run_id, "load", "progress", f"{new} new postings stored")
            todo = con.execute("""select posting_id, title, description from postings p where source = 'greenhouse'
                                  and not exists (select 1 from skill_statements s where s.posting_id = p.posting_id)
                                  order by fetched_at, posting_id limit %s""", (args.max_new,)).fetchall()
            todo = [{"posting_id": a, "title": b, "description": c} for a, b, c in todo]
            waiting = con.execute("""select count(*) from postings p where source = 'greenhouse' and not exists
                                     (select 1 from skill_statements s where s.posting_id = p.posting_id)""").fetchone()[0]

            # extract
            db.event(con, run_id, "extract", "start",
                     f"{len(todo)} of {waiting} postings without skills (--max-new {args.max_new}), prompt {PROMPT.stem}")
            ex, rows, last_model, called, fails = Extractor(), [], None, False, 0
            for i, p in enumerate(todo, 1):
                key = hashlib.sha256((prompt_sha + "|" + p["description"]).encode()).hexdigest()
                path = CACHE / f"{key}.json"
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                else:
                    if called:
                        time.sleep(args.delay)
                    try:
                        out, t_in, t_out, served = ex.extract(system, p["description"],
                                                              trace={"session_id": run_id, "trace_name": p["posting_id"]})
                    except Exception as e:  # every model in the chain failed: record and move on
                        db.event(con, run_id, "extract", "error", f"{p['posting_id']}: {str(e)[:150]}")
                        fails += 1
                        if fails >= 2:  # all models rate-limited: the rest stay in the queue for the next run
                            db.event(con, run_id, "extract", "info",
                                     f"stopped: all models unavailable; {len(todo) - i} postings wait for the next run")
                            break
                        continue
                    called, fails = True, 0
                    data = {"posting_id": p["posting_id"], "model": served, "tokens_in": t_in, "tokens_out": t_out,
                            "output": out}
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                if last_model and data["model"] != last_model:
                    db.event(con, run_id, "model_switch", "info", f"{last_model} -> {data['model']}", model=data["model"])
                last_model = data["model"]
                low = p["description"].lower()
                skills = [s for s in data["output"].get("skills", []) if s.get("skill")]
                for k, s in enumerate(skills, 1):
                    ev = str(s.get("evidence", "")).strip()
                    rows.append({"statement_id": f"{p['posting_id']}:skill:{k}", "posting_id": p["posting_id"],
                                 "skill": s["skill"].strip(), "evidence": ev,
                                 "evidence_in_text": bool(ev) and ev.lower() in low, "provider": "litellm",
                                 "model": data["model"], "prompt_version": PROMPT.stem, "run_id": run_id})
                db.event(con, run_id, "extract", "progress", f"{i}/{len(todo)} {p['title']}: {len(skills)} skills",
                         model=data["model"])
            db.event(con, run_id, "extract", "done", f"{len(rows)} skill statements")

            # load statements, then link the new skills
            db.upsert_statements(con, rows)
            db.event(con, run_id, "load", "done", f"{len(rows)} skill statements stored")
            keys = db.unlinked_keys(con)
            db.event(con, run_id, "link", "start", f"{len(keys)} new skills -> ESCO / O*NET")
            db.upsert_links(con, link_keys(keys))
            db.event(con, run_id, "link", "done", f"{len(keys)} skills linked")
            db.finish_run(con, run_id, n_fetched=len(jobs), n_new=new, n_statements=len(rows))
        except Exception as e:
            db.event(con, run_id, "load", "error", str(e)[:200])
            db.finish_run(con, run_id, status="failed")
            raise


if __name__ == "__main__":
    main()
