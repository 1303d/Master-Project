"""Clean and tag LinkedIn postings. Keeps every row; adds flags instead of dropping.

Output: data/interim/postings_clean.parquet
"""
import hashlib
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "linkedin" / "postings.csv"
OUT = ROOT / "data" / "interim" / "postings_clean.parquet"

MIN_CHARS = 200  # shorter descriptions are flagged as too short


def normalize(text):
    """Fix odd unicode; collapse spaces within lines but keep line breaks (bullets stay readable)."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", text)
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def flat(text):
    """Text with all whitespace collapsed to one space (used for hashing and length)."""
    return re.sub(r"\s+", " ", text).strip()


def text_hash(text):
    """Same text (ignoring case and whitespace) -> same id."""
    return hashlib.sha1(flat(text).lower().encode("utf-8")).hexdigest()[:12]


def main():
    cols = ["job_id", "title", "company_name", "location", "description",
            "skills_desc", "formatted_experience_level", "listed_time"]
    df = pd.read_csv(RAW, usecols=cols)
    print(f"Loaded {len(df):,} rows")

    df["description"] = df["description"].map(normalize)
    df["title"] = df["title"].map(normalize).map(flat)
    df["n_chars"] = df["description"].map(flat).str.len()

    # duplicates: same text_id; the earliest posting is the original
    df["text_id"] = df["description"].map(text_hash)
    df = df.sort_values(["listed_time", "job_id"]).reset_index(drop=True)
    df["dup_count"] = df.groupby("text_id")["job_id"].transform("size")
    df["is_duplicate"] = df.duplicated("text_id", keep="first")

    df["is_missing"] = df["n_chars"] == 0
    df["is_short"] = (df["n_chars"] > 0) & (df["n_chars"] < MIN_CHARS)
    df["is_usable"] = ~(df["is_duplicate"] | df["is_missing"] | df["is_short"])

    df["posting_id"] = "li_" + df["job_id"].astype(str)
    df["source"] = "kaggle:arshkon/linkedin-job-postings"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)

    print(f"Duplicates tagged: {df['is_duplicate'].sum():,}")
    print(f"Missing text:      {df['is_missing'].sum():,}")
    print(f"Too short:         {df['is_short'].sum():,}")
    print(f"Usable (unique):   {df['is_usable'].sum():,}")
    print(f"Saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
