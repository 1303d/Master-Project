"""Supabase (Postgres) access for the skill pipeline. Reads SUPABASE_DB_URL from .env.

    py src/db.py --init      # create the tables (sql/supabase_schema.sql); safe to re-run
    py src/db.py --check     # print row counts per table
"""
import argparse
import hashlib
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
TABLES = ["postings", "skill_statements", "skill_links", "review_decisions", "pipeline_runs", "pipeline_events"]


def connect():
    url = os.getenv("SUPABASE_DB_URL")
    if not url:  # an error, not sys.exit: the UI server must survive it and show the message
        raise RuntimeError("SUPABASE_DB_URL is missing in .env")
    return psycopg.connect(url, autocommit=True, prepare_threshold=None)  # no prepared statements: pooler-safe


def text_hash(text):
    """Same text after lowercasing and collapsing whitespace -> same hash (dedupe across sources)."""
    return hashlib.sha256(re.sub(r"\s+", " ", str(text).lower()).strip().encode()).hexdigest()


def skill_key(skill):
    return str(skill).strip().lower()


def upsert_postings(con, rows):
    """rows: dicts with posting_id, source, company, title, location, sector, url, description.
    A posting whose text already exists (same text_hash, any source) is skipped. Returns rows inserted."""
    sql = """insert into postings (posting_id, source, company, title, location, sector, url, description, text_hash)
             values (%(posting_id)s, %(source)s, %(company)s, %(title)s, %(location)s, %(sector)s, %(url)s,
                     %(description)s, %(text_hash)s)
             on conflict do nothing"""
    rows = [{**r, "text_hash": text_hash(r["description"])} for r in rows]
    with con.cursor() as cur:
        before = cur.execute("select count(*) from postings").fetchone()[0]
        cur.executemany(sql, rows)
        return cur.execute("select count(*) from postings").fetchone()[0] - before


def upsert_statements(con, rows):
    """rows: dicts with statement_id, posting_id, skill, evidence, evidence_in_text, provider, model,
    prompt_version, run_id. Re-loading the same statement_id updates it."""
    sql = """insert into skill_statements (statement_id, posting_id, skill, skill_key, evidence, evidence_in_text,
                                           provider, model, prompt_version, run_id)
             values (%(statement_id)s, %(posting_id)s, %(skill)s, %(skill_key)s, %(evidence)s, %(evidence_in_text)s,
                     %(provider)s, %(model)s, %(prompt_version)s, %(run_id)s)
             on conflict (statement_id) do update set skill = excluded.skill, skill_key = excluded.skill_key,
               evidence = excluded.evidence, evidence_in_text = excluded.evidence_in_text, model = excluded.model"""
    with con.cursor() as cur:
        cur.executemany(sql, [{**r, "skill_key": skill_key(r["skill"])} for r in rows])


def upsert_links(con, rows):
    """rows: dicts with skill_key, verdict, source, ref_label, ref_id, score, match.
    A human-reviewed link is never overwritten by the automatic ESCO/O*NET linker."""
    sql = """insert into skill_links (skill_key, verdict, source, ref_label, ref_id, score, match)
             values (%(skill_key)s, %(verdict)s, %(source)s, %(ref_label)s, %(ref_id)s, %(score)s, %(match)s)
             on conflict (skill_key) do update set verdict = excluded.verdict, source = excluded.source,
               ref_label = excluded.ref_label, ref_id = excluded.ref_id, score = excluded.score,
               match = excluded.match, updated_at = now()
             where skill_links.review_status = 'auto'"""
    with con.cursor() as cur:
        cur.executemany(sql, rows)


def unlinked_keys(con):
    with con.cursor() as cur:
        return [r[0] for r in cur.execute(
            "select distinct s.skill_key from skill_statements s left join skill_links l using (skill_key) "
            "where l.skill_key is null").fetchall()]


def start_run(con, source, note=None):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    con.execute("insert into pipeline_runs (run_id, source, note) values (%s, %s, %s)", (run_id, source, note))
    return run_id


def event(con, run_id, stage, status, message=None, model=None):
    con.execute("insert into pipeline_events (run_id, stage, status, model, message) values (%s, %s, %s, %s, %s)",
                (run_id, stage, status, model, message))
    print(f"[{stage}:{status}] {message or ''}{f' ({model})' if model else ''}", flush=True)


def finish_run(con, run_id, status="done", **counts):
    sets = ", ".join(f"{k} = %({k})s" for k in counts)
    con.execute(f"update pipeline_runs set status = %(status)s, finished_at = now(){', ' + sets if sets else ''} "
                f"where run_id = %(run_id)s", {"status": status, "run_id": run_id, **counts})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    with connect() as con:
        if args.init:
            con.execute((ROOT / "sql" / "supabase_schema.sql").read_text(encoding="utf-8"))
            print("schema applied")
        for t in TABLES:
            print(f"{t:18} {con.execute(f'select count(*) from {t}').fetchone()[0]:>8}")


if __name__ == "__main__":
    main()
