"""Small helper for hand labeling the gold set.

  py src/gold_tool.py show 1                      # print posting #1 (contact details hidden)
  py src/gold_tool.py save 1 --by Dhanush --suggested "a; b" --gold "a; c" [--notes "..."] [--sector "Legal"]
  py src/gold_tool.py status                      # progress per sector
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "data" / "gold" / "gold_labels.csv"
CLEAN = ROOT / "data" / "interim" / "postings_clean.parquet"

EMAIL = re.compile(r"\S+@\S+\.\S+")
PHONE = re.compile(r"\+?\d[\d\-\s().]{8,}\d")


def hide_contacts(text):
    """Remove emails and phone numbers (personal data)."""
    return PHONE.sub("[PHONE]", EMAIL.sub("[EMAIL]", text))


def load():
    return pd.read_csv(LABELS, dtype=str, keep_default_na=False)


def show(n):
    labels = load()
    row = labels[labels["n"] == str(n)].iloc[0]
    posts = pd.read_parquet(CLEAN, columns=["posting_id", "description"])
    text = posts.loc[posts["posting_id"] == row["posting_id"], "description"].iloc[0]
    print(f"#{n}/{len(labels)} | {row['posting_id']} | {row['sector']}")
    print(f"{row['title']} | {row['company_name']} | {row['location']}\n")
    print(hide_contacts(text))
    if row["gold_skills"]:
        print(f"\n[already labeled] {row['gold_skills']}")


def save(n, by, suggested, gold, notes, sector):
    labels = load()
    i = labels.index[labels["n"] == str(n)][0]
    labels.loc[i, ["suggested_skills", "gold_skills", "labeled_by", "notes"]] = [suggested, gold, by, notes]
    labels.loc[i, "sector_fixed"] = sector or labels.loc[i, "sector"]  # same as sector unless corrected
    labels.to_csv(LABELS, index=False)
    print(f"Saved #{n}: {gold}")


def status():
    labels = load()
    done = labels["gold_skills"] != ""
    print(labels.assign(done=done).groupby("sector")["done"].agg(["sum", "count"]).to_string())
    print(f"Total: {done.sum()}/{len(labels)}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show"); s.add_argument("n", type=int)
    v = sub.add_parser("save"); v.add_argument("n", type=int)
    v.add_argument("--by", required=True); v.add_argument("--suggested", default="")
    v.add_argument("--gold", required=True); v.add_argument("--notes", default="")
    v.add_argument("--sector", default="", help="correct sector if the LinkedIn tag is wrong")
    sub.add_parser("status")
    a = p.parse_args()
    if a.cmd == "show":
        show(a.n)
    elif a.cmd == "save":
        save(a.n, a.by, a.suggested, a.gold, a.notes, a.sector)
    else:
        status()


if __name__ == "__main__":
    main()
