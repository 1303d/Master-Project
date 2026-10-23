"""Check that Supabase holds what the source files say it should. Prints PASS / FAIL / INFO per check.

    py src/verify_db.py

Sources: data/processed/extraction_sample_2000.csv (Kaggle sample), statements_claude-haiku-5-5_sample2000.csv
(research benchmark), the Groq cache (Qwen batch, still growing), data/raw/greenhouse/<run>/ (latest fetch).
"""
import json
import sys
from pathlib import Path

import pandas as pd

import db
from load_supabase import SAMPLE, cached_statements

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
QWEN, PROMPT = "qwen/qwen3.8-27b", ROOT / "prompts" / "skill_extraction_v3.txt"
results = []


def check(name, ok, detail, info=False):
    status = "INFO" if info else ("PASS" if ok else "FAIL")
    results.append(status)
    print(f"{status:4}  {name}: {detail}")


def main():
    sample = pd.read_csv(SAMPLE, encoding="utf-8-sig")
    with db.connect() as con:
        one = lambda sql, *a: con.execute(sql, a).fetchone()[0]

        n = one("select count(*) from postings where source = 'kaggle'")
        check("Kaggle postings", n == len(sample), f"{n} in DB vs {len(sample)} in the sample file")
        ids = {r[0] for r in con.execute("select posting_id from postings where source = 'kaggle'").fetchall()}
        check("Kaggle posting ids", ids == set(sample.posting_id), "same set of posting_id as the sample file")

        haiku_csv = PROCESSED / "statements_claude-haiku-5-5_sample2000.csv"
        if haiku_csv.exists():
            h = pd.read_csv(haiku_csv)
            n = one("select count(*) from skill_statements where model = 'claude-haiku-5-5'")
            check("Haiku benchmark statements", n == len(h), f"{n} in DB vs {len(h)} in {haiku_csv.name}")
            db_per = dict(con.execute("select posting_id, count(*) from skill_statements where model = "
                                      "'claude-haiku-5-5' group by 1").fetchall())
            bad = [p for p, k in h.posting_id.value_counts().items() if db_per.get(p) != k]
            check("Haiku per-posting counts", not bad, f"{len(bad)} postings differ")

        rows, done = cached_statements(sample, "groq", QWEN, PROMPT, None)
        n = one("select count(*) from skill_statements s join postings p using (posting_id) "
                "where p.source = 'kaggle' and s.model = %s", QWEN)
        check("Qwen statements vs cache", n <= len(rows),
              f"{n} in DB, {len(rows)} in the cache ({done} postings); the hourly task loads the gap", info=n < len(rows))
        if n > len(rows):
            check("Qwen statements vs cache", False, "DB has more Qwen rows than the cache")

        n = one("select count(*) from (select distinct skill_key from skill_statements) s "
                "left join skill_links l using (skill_key) where l.skill_key is null")
        check("Every skill has an ESCO/O*NET verdict", n == 0, f"{n} skills without a link")

        n = one("select count(*) from (select posting_id from current_statements group by 1 "
                "having count(distinct model) > 1) x")
        check("current_statements: one model per posting", n == 0, f"{n} postings with two models")

        total, uniq, kinds = con.execute("select count(*), count(distinct statement_id), "
                                         "string_agg(distinct kind, ',') from statements").fetchone()
        check("Contract view 'statements'", total == uniq and kinds == "skill",
              f"{total} rows, {uniq} unique ids, kind = {kinds}")

        ev = one("select avg(evidence_in_text::int) from skill_statements")
        check("Evidence found verbatim", ev >= 0.95, f"{ev:.1%} of statements (expected >= 95%)")

        raw = sorted((ROOT / "data" / "raw" / "greenhouse").glob("*/"))
        if raw:
            jobs = {f"gh_{f.stem}_{j['id']}" for f in raw[-1].glob("*.json")
                    for j in json.loads(f.read_text(encoding="utf-8")).get("jobs", [])}
            stored = {r[0] for r in con.execute("select posting_id from postings where source = 'greenhouse'").fetchall()}
            missing = jobs - stored
            check("Greenhouse: latest fetch stored", not missing,
                  f"{len(jobs)} jobs in {raw[-1].name}, {len(missing)} not in DB (duplicates by text are skipped)",
                  info=bool(missing))
            n = one("select count(*) from postings p where source = 'greenhouse' and exists "
                    "(select 1 from skill_statements s where s.posting_id = p.posting_id)")
            check("Greenhouse postings with skills", True, f"{n} of {len(stored)} (extraction runs as a nightly queue)",
                  info=True)

        with db.connect() as con:  # Sprint 3: the active clustering run must find every vector it was built on
            run = con.execute("""select r.run_id, (select count(*) from skill_topics t where t.run_id = r.run_id),
                                        (select count(*) from skill_embeddings e where e.vectors_sha256 = r.vectors_sha256)
                                 from cluster_runs r where r.is_active""").fetchone()
        if run:
            check("Embeddings of the active run", run[1] == run[2],
                  f"{run[2]} vectors in skill_embeddings for {run[1]} skill memberships ({run[0]})")

    fails = results.count("FAIL")
    print(f"\n{results.count('PASS')} passed, {fails} failed, {results.count('INFO')} info")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
