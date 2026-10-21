"""Diagnostic: recall on gold skills that sit inside a list in the posting (the v3 target).

    py src/list_recall.py --model qwen/qwen3.8-27b --tags v2 v3 --split dev

A gold skill counts as a "list item" when its exact text occurs in the posting with a list
separator right before or after it: , / ( ) ; or "and"/"or".
Recall uses the same lenient matching as evaluate.py, restricted to those gold skills.
"""
import argparse
import re
from pathlib import Path

import pandas as pd

from evaluate import match, split
from extract_skills import slug

ROOT = Path(__file__).resolve().parents[1]
SEP = r"(?:[,/();]|\band\b|\bor\b)"


def is_list_item(skill, text):
    s = re.escape(skill.lower())
    return re.search(rf"{SEP}\s*{s}\b|\b{s}\s*{SEP}", text.lower()) is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tags", nargs="+", required=True)
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    args = ap.parse_args()

    gold = pd.read_csv(ROOT / "data" / "gold" / "gold_labels.csv")
    posts = pd.read_csv(ROOT / "data" / "gold" / f"gold_postings_{args.split}.csv", encoding="utf-8-sig")
    gold = gold.merge(posts[["posting_id", "description"]], on="posting_id")
    items = {r.posting_id: [g for g in split(r.gold_skills) if is_list_item(g, r.description)]
             for r in gold.itertuples()}
    total = sum(map(len, items.values()))
    print(f"{args.split}: {total} gold skills sit inside a list")

    for tag in args.tags:
        pred = pd.read_csv(ROOT / "data" / "processed" / f"statements_{slug(args.model)}_{tag}.csv")
        by_post = pred.groupby("posting_id").skill.apply(list).to_dict()
        found = sum(match(g, by_post.get(pid, []), lenient=True)[0] for pid, g in items.items())
        print(f"  {tag}: list-item recall {found}/{total} = {found / total:.2f}")


if __name__ == "__main__":
    main()
