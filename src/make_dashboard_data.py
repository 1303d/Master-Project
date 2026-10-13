"""Build data files so the teammate's review dashboard can annotate the Kaggle gold set (no dashboard code changes).

Input:  data/gold/gold_labels.csv (100 posting_ids) + data/interim/postings_clean.parquet
Output: dashboard_kaggle/ (git-ignored data)
    data/kaggle_gold.sqlite                            postings table (only the columns the dashboard reads)
    data/annotation/sprint2_v1/selection_manifest.csv  all 100 as split=evaluation (blank start, no AI drafts)
    docs/skill_annotation_guidelines.md                copy of data/gold/LABELING_RULES.md

Run the dashboard:
    py taxonomy-skill-project/src/dashboard.py --root dashboard_kaggle --db dashboard_kaggle/data/kaggle_gold.sqlite
"""
import csv
import hashlib
import shutil
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold" / "gold_labels.csv"
CLEAN = ROOT / "data" / "interim" / "postings_clean.parquet"
OUT = ROOT / "dashboard_kaggle"
SNAPSHOT = "kaggle-arshkon-2024"

# exact header the dashboard checks (taxonomy-skill-project/src/select_annotation_set.py MANIFEST_FIELDS)
MANIFEST_FIELDS = ["snapshot_id", "posting_id", "split", "board_token", "company_name", "title", "location",
                   "first_department", "seniority_label", "group_id", "group_size", "group_basis",
                   "group_members", "clean_text_sha256", "seed", "selection_version"]


def main():
    gold = pd.read_csv(GOLD)
    posts = pd.read_parquet(CLEAN, columns=["posting_id", "description"]).set_index("posting_id")
    gold["clean_text"] = gold["posting_id"].map(posts["description"])
    assert gold["clean_text"].notna().all(), "some gold posting_ids are missing from the cleaned data"

    db = OUT / "data" / "kaggle_gold.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE postings (snapshot_id TEXT, posting_id TEXT, company_name TEXT, title TEXT,
                   location TEXT, word_count INTEGER, exclusion_reason TEXT, is_duplicate_of TEXT,
                   is_placeholder INTEGER, sector TEXT, clean_text TEXT NOT NULL,
                   PRIMARY KEY (snapshot_id, posting_id))""")
    rows, manifest = [], []
    for g in gold.itertuples():
        company = g.company_name if isinstance(g.company_name, str) else "(unknown)"
        sector = g.sector_fixed if isinstance(g.sector_fixed, str) else g.sector  # sector_fixed only set once labelled
        rows.append((SNAPSHOT, g.posting_id, company, g.title, g.location, len(g.clean_text.split()),
                     "", None, 0, sector, g.clean_text))
        manifest.append(dict.fromkeys(MANIFEST_FIELDS, "") | {
            "snapshot_id": SNAPSHOT, "posting_id": g.posting_id, "split": "evaluation",
            "company_name": company, "title": g.title, "location": g.location,
            "first_department": sector, "group_id": g.posting_id, "group_size": 1,
            "clean_text_sha256": hashlib.sha256(g.clean_text.encode("utf-8")).hexdigest(),
            "seed": 42, "selection_version": "kaggle-gold-v1"})
    con.executemany("INSERT INTO postings VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()

    man = OUT / "data" / "annotation" / "sprint2_v1" / "selection_manifest.csv"
    man.parent.mkdir(parents=True, exist_ok=True)
    with man.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(manifest)

    (OUT / "docs").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "data" / "gold" / "LABELING_RULES.md", OUT / "docs" / "skill_annotation_guidelines.md")
    print(f"Wrote {len(rows)} postings to {db.relative_to(ROOT)} and {man.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
