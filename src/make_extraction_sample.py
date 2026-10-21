"""Pick a random sample of usable postings for bulk skill extraction (Sprint 3 corpus).

    py src/make_extraction_sample.py            # 2,000 postings
    py src/make_extraction_sample.py --n 500

Random (not stratified), so the sample mirrors the corpus mix. Same length filter and seed as the
gold sample; the 100 gold postings are left out. Emails and phone numbers are masked.
Output: data/processed/extraction_sample_<n>.csv  (columns extract_skills.py reads: n, posting_id, description)
"""
import argparse
from pathlib import Path

import pandas as pd

from gold_tool import hide_contacts
from make_gold_sample import MAX_CHARS, MIN_CHARS, RAW, SECTOR_OF_FUNCTION, SEED

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "interim" / "postings_clean.parquet"
GOLD = ROOT / "data" / "gold" / "gold_postings.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()

    df = pd.read_parquet(CLEAN)
    gold_ids = set(pd.read_csv(GOLD, encoding="utf-8-sig")["posting_id"])
    pool = df[df["is_usable"] & df["n_chars"].between(MIN_CHARS, MAX_CHARS) & ~df["posting_id"].isin(gold_ids)]

    sample = pool.sample(n=args.n, random_state=SEED).reset_index(drop=True)
    funcs = pd.read_csv(RAW / "jobs" / "job_skills.csv").merge(
        pd.read_csv(RAW / "mappings" / "skills.csv"), on="skill_abr")
    primary = funcs.drop_duplicates("job_id")[["job_id", "skill_name"]]
    sample = sample.merge(primary, on="job_id", how="left")
    sample["sector"] = sample["skill_name"].map(SECTOR_OF_FUNCTION).fillna("Mixed")
    sample["description"] = sample["description"].map(hide_contacts)
    sample["n"] = range(1, len(sample) + 1)

    out = ROOT / "data" / "processed" / f"extraction_sample_{args.n}.csv"
    cols = ["n", "posting_id", "sector", "title", "company_name", "location", "description"]
    sample[cols].to_csv(out, index=False, encoding="utf-8")
    print(sample["sector"].value_counts().to_string())
    print(f"Saved {out.relative_to(ROOT)} ({len(sample)} postings, {sample['n_chars'].sum():,} chars)")


if __name__ == "__main__":
    main()
