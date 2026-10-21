"""Split the gold postings 50/50 into dev (tune the extractor on) and test (score once, at the end).

    py src/make_gold_split.py

Stratified by sector (sector_fixed, else sector), seed 42, so both halves keep the sector mix.
Output: data/gold/gold_split.csv (posting_id, split), gold_postings_dev.csv, gold_postings_test.csv
Refuses to overwrite an existing split (the test half must stay unseen).
"""
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "data" / "gold"
SEED = 42


def main():
    out = GOLD_DIR / "gold_split.csv"
    if out.exists():
        raise SystemExit(f"{out.name} already exists. Delete it only if you really want a new split.")

    labels = pd.read_csv(GOLD_DIR / "gold_labels.csv")
    labels["sector_eval"] = labels.sector_fixed.fillna(labels.sector)
    dev_ids, _ = train_test_split(labels.posting_id, train_size=len(labels) // 2,
                                  stratify=labels.sector_eval, random_state=SEED)
    split = labels[["posting_id", "sector_eval"]].assign(
        split=lambda d: d.posting_id.isin(dev_ids).map({True: "dev", False: "test"}))
    split.to_csv(out, index=False)

    postings = pd.read_csv(GOLD_DIR / "gold_postings.csv", encoding="utf-8-sig")
    for name in ["dev", "test"]:
        ids = split.loc[split.split == name, "posting_id"]
        postings[postings.posting_id.isin(ids)].to_csv(GOLD_DIR / f"gold_postings_{name}.csv", index=False)

    print(pd.crosstab(split.sector_eval, split.split, margins=True).to_string())
    print(f"Saved {out.relative_to(ROOT)} and gold_postings_dev/test.csv")


if __name__ == "__main__":
    main()
