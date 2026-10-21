"""Rebuild data/gold/gold_postings.csv (posting text of the 100 gold postings) with contacts masked.

    py src/make_gold_postings.py            # write it if missing; if it exists, check it is identical
    py src/make_gold_postings.py --force    # overwrite

Input:  data/gold/gold_labels.csv (n, posting_id, sector), data/interim/postings_clean.parquet (text)
Output: data/gold/gold_postings.csv: n, posting_id, sector, title, company_name, location, description
Emails and phone numbers are replaced by [EMAIL] / [PHONE] with the masker the file was first made with
(2026-10-06): US phone numbers only. It is stricter than gold_tool.hide_contacts, which also masks dates
and section numbers ("2024-03-11"). Labels and LLM caches are keyed on this exact text, so keep this masker.
The file holds posting text, so it is shared via Drive, not Git.
"""
import argparse
import re
from pathlib import Path

import pandas as pd

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
US_PHONE = re.compile(r"\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def hide_contacts(text):
    return US_PHONE.sub("[PHONE]", EMAIL.sub("[EMAIL]", text))

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "data" / "gold" / "gold_labels.csv"
CLEAN = ROOT / "data" / "interim" / "postings_clean.parquet"
OUT = ROOT / "data" / "gold" / "gold_postings.csv"
COLS = ["n", "posting_id", "sector", "title", "company_name", "location", "description"]


def build():
    labels = pd.read_csv(LABELS, encoding="utf-8-sig")[["n", "posting_id", "sector"]]
    text = pd.read_parquet(CLEAN, columns=["posting_id", "title", "company_name", "location", "description"])
    out = labels.merge(text.drop_duplicates("posting_id"), on="posting_id", how="left", validate="one_to_one")
    missing = out[out.description.isna()].posting_id.tolist()
    if missing:
        raise SystemExit(f"{len(missing)} gold postings not found in {CLEAN.name}: {missing[:5]}")
    out["description"] = out.description.map(hide_contacts)
    return out[COLS]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="overwrite an existing file")
    args = ap.parse_args()
    new = build()
    if OUT.exists() and not args.force:
        old = pd.read_csv(OUT, encoding="utf-8-sig")
        diff = [c for c in COLS if not old[c].fillna("").astype(str).equals(new[c].fillna("").astype(str))]
        print(f"{OUT.relative_to(ROOT)} exists: " + ("identical to a fresh build" if not diff
                                                    else f"DIFFERS in columns {diff} (use --force to overwrite)"))
        return
    new.to_csv(OUT, index=False, encoding="utf-8-sig")
    emails, phones = (new.description.str.count(t).sum() for t in (r"\[EMAIL\]", r"\[PHONE\]"))
    print(f"{len(new)} postings -> {OUT.relative_to(ROOT)} ({emails} emails, {phones} phones masked)")


if __name__ == "__main__":
    main()
