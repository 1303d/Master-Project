"""Load the Kaggle sample into Supabase: postings, the extracted skills found in the cache so far, and
their ESCO / O*NET links. Safe to re-run at any time (upserts); run it again as the Qwen batch progresses.

    py src/load_supabase.py
    py src/load_supabase.py --model qwen/qwen3.8-27b --prompt prompts/skill_extraction_v3.txt
    py src/load_supabase.py --provider anthropic --model claude-haiku-5-5 --benchmark   # research run, side by side

Skills are read straight from cache/<provider>/ (same key as extract_skills.py), so postings the batch
has finished are loaded even while it is still running. Links come from data/processed/skill_links.csv;
skills not in it are linked now with link_reference.py.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

import db
from extract_skills import slug
from link_reference import LINKS, link, reference

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "processed" / "extraction_sample_2000.csv"


def cached_statements(posts, provider, model, prompt, run_id, benchmark=False):
    """Rebuild statement rows exactly as extract_skills.py does, from the cached LLM answers.
    A benchmark run gets the model in its statement_id, so it sits beside the pipeline model's rows."""
    tag = f"{slug(model)}:" if benchmark else ""
    system = prompt.read_text(encoding="utf-8")
    sha = hashlib.sha256(system.encode()).hexdigest()
    rows, done = [], 0
    for p in posts.itertuples():
        path = ROOT / "cache" / provider / f"{hashlib.sha256(f'{model}|{sha}|{p.description}'.encode()).hexdigest()}.json"
        if not path.exists():
            continue
        done += 1
        data = json.loads(path.read_text(encoding="utf-8"))
        low = p.description.lower()
        skills = [s for s in data["output"].get("skills", []) if s.get("skill")]
        for i, s in enumerate(skills, 1):
            ev = str(s.get("evidence", "")).strip()
            rows.append({"statement_id": f"{p.posting_id}:{tag}skill:{i}", "posting_id": p.posting_id,
                         "skill": s["skill"].strip(), "evidence": ev, "evidence_in_text": bool(ev) and ev.lower() in low,
                         "provider": data.get("provider", provider), "model": model,
                         "prompt_version": prompt.stem, "run_id": run_id})
    return rows, done


def link_keys(keys):
    """ESCO / O*NET verdicts for these skill keys: reuse skill_links.csv, link the rest now."""
    known = pd.read_csv(LINKS) if LINKS.exists() else pd.DataFrame(columns=["skill"])
    known = known[known.skill.isin(keys)]
    rest = sorted(set(keys) - set(known.skill))
    if rest:
        known = pd.concat([known, link(rest, reference(), 0.85, 0.88)])
    known = known.astype(object).where(known.notna(), None)  # NaN -> NULL
    return [{"skill_key": r.skill, "verdict": r.verdict, "source": r.source, "ref_label": r.ref_label,
             "ref_id": r.ref_id, "score": None if r.score is None else float(r.score), "match": r.match}
            for r in known.itertuples()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--postings", type=Path, default=SAMPLE)
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--model", default="qwen/qwen3.8-27b")
    ap.add_argument("--prompt", type=Path, default=ROOT / "prompts" / "skill_extraction_v3.txt")
    ap.add_argument("--benchmark", action="store_true",
                    help="research run of another model: its rows get the model in statement_id (kept side by side)")
    ap.add_argument("--if-new", action="store_true", help="do nothing unless the cache has new skills (for the hourly task)")
    args = ap.parse_args()

    posts = pd.read_csv(args.postings, encoding="utf-8-sig")
    with db.connect() as con:
        if args.if_new:
            rows, _ = cached_statements(posts, args.provider, args.model, args.prompt, None, args.benchmark)
            stored = con.execute("select count(*) from skill_statements s join postings p using (posting_id) "
                                 "where p.source = 'kaggle' and s.model = %s", (args.model,)).fetchone()[0]
            if len(rows) <= stored:
                print(f"nothing new ({stored} {args.model} skills already stored)")
                return
        note = f"{'research benchmark' if args.benchmark else 'batch load'} {args.model} from {args.postings.name}"
        run_id = db.start_run(con, "kaggle", note=note)
        db.event(con, run_id, "load", "start", f"{len(posts)} Kaggle postings")
        new = db.upsert_postings(con, [{"posting_id": p.posting_id, "source": "kaggle", "company": p.company_name,
                                        "title": p.title, "location": p.location, "sector": p.sector, "url": None,
                                        "description": p.description} for p in posts.itertuples()])
        db.event(con, run_id, "dedupe", "done", f"{new} new postings ({len(posts) - new} already stored)")
        rows, done = cached_statements(posts, args.provider, args.model, args.prompt, run_id, args.benchmark)
        stored = {r[0] for r in con.execute("select posting_id from postings").fetchall()}
        rows = [r for r in rows if r["posting_id"] in stored]  # a posting skipped as a duplicate has no row
        db.upsert_statements(con, rows)
        db.event(con, run_id, "extract", "info", f"{done}/{len(posts)} postings extracted so far, {len(rows)} skills",
                 model=args.model)
        keys = db.unlinked_keys(con)
        db.event(con, run_id, "link", "start", f"{len(keys)} unlinked skills -> ESCO / O*NET")
        db.upsert_links(con, link_keys(keys))
        db.event(con, run_id, "link", "done", f"{len(keys)} skills linked")
        db.finish_run(con, run_id, n_fetched=len(posts), n_new=new, n_statements=len(rows))
        db.event(con, run_id, "load", "done", "batch load finished")


if __name__ == "__main__":
    main()
