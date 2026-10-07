"""Pick 100 usable postings for hand labeling, stratified by sector.

Sector = the posting's first listed LinkedIn job function, grouped into 8 sectors + Mixed.
Output: data/gold/gold_labels.csv (one row per posting, labels filled in later)
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "linkedin"
CLEAN = ROOT / "data" / "interim" / "postings_clean.parquet"
OUT = ROOT / "data" / "gold" / "gold_labels.csv"

SEED = 42  # fixed seed -> the same postings every run
MIN_CHARS, MAX_CHARS = 300, 5000  # skip extremes to keep labeling time reasonable

SECTOR_OF_FUNCTION = {
    "Information Technology": "IT",
    "Health Care Provider": "Health Care",
    "Engineering": "Engineering",
    "Sales": "Sales + Marketing",
    "Marketing": "Sales + Marketing",
    "Business Development": "Sales + Marketing",
    "Finance": "Finance + Accounting",
    "Accounting/Auditing": "Finance + Accounting",
    "Management": "Management",
    "Legal": "Legal",
    "Administrative": "Admin / HR / Customer Service",
    "Human Resources": "Admin / HR / Customer Service",
    "Customer Service": "Admin / HR / Customer Service",
}
QUOTA = {
    "IT": 15, "Health Care": 15, "Engineering": 12, "Sales + Marketing": 12,
    "Finance + Accounting": 12, "Management": 10, "Legal": 8,
    "Admin / HR / Customer Service": 8, "Mixed": 8,
}


def main():
    df = pd.read_parquet(CLEAN)
    pool = df[df["is_usable"] & df["n_chars"].between(MIN_CHARS, MAX_CHARS)]

    funcs = pd.read_csv(RAW / "jobs" / "job_skills.csv").merge(
        pd.read_csv(RAW / "mappings" / "skills.csv"), on="skill_abr")
    primary = funcs.drop_duplicates("job_id")[["job_id", "skill_name"]]
    pool = pool.merge(primary, on="job_id", how="left")
    pool["sector"] = pool["skill_name"].map(SECTOR_OF_FUNCTION).fillna("Mixed")

    parts = [pool[pool["sector"] == s].sample(n=n, random_state=SEED) for s, n in QUOTA.items()]
    sample = pd.concat(parts).sample(frac=1, random_state=SEED)  # shuffle sectors
    sample = sample.reset_index(drop=True)
    sample["n"] = range(1, len(sample) + 1)

    out = sample[["n", "posting_id", "sector", "title", "company_name", "location"]].copy()
    for col in ["suggested_skills", "gold_skills", "labeled_by", "notes"]:
        out[col] = ""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        raise SystemExit(f"{OUT.name} already exists. Delete it first to avoid losing labels.")
    out.to_csv(OUT, index=False)
    print(out["sector"].value_counts().to_string())
    print(f"Saved {OUT.relative_to(ROOT)} ({len(out)} postings)")


if __name__ == "__main__":
    main()
