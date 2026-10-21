"""Does an extractor score well only because it agrees with the LLM-suggested drafts?

Gold skills were drafted by an LLM (suggested_skills) and corrected by a human (gold_skills).
This splits each posting's gold into
  kept  = gold skills that were already in the suggestion
  added = gold skills the human added
and reports each model's recall on both parts (lenient matching, same as evaluate.py).
A model biased towards the drafter would show high recall on `kept` but low on `added`.

    py src/bias_check.py --split dev --runs qwen/qwen3.8-27b:v3 openai/gpt-oss-120b:v3
"""
import argparse
from pathlib import Path

import pandas as pd

from evaluate import match, slug, split

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=["all", "dev", "test"], default="dev")
    ap.add_argument("--runs", nargs="+", required=True, help="model:tag pairs")
    args = ap.parse_args()

    gold = pd.read_csv(ROOT / "data" / "gold" / "gold_labels.csv", encoding="utf-8-sig")
    if args.split != "all":
        halves = pd.read_csv(ROOT / "data" / "gold" / "gold_split.csv")
        gold = gold[gold.posting_id.isin(halves.loc[halves.split == args.split, "posting_id"])]

    parts, n_sug, n_dropped = {}, 0, 0
    for r in gold.itertuples():
        g, s = split(r.gold_skills), split(r.suggested_skills)
        _, added, _ = match(g, s, lenient=False)  # gold skills not found in the suggestion
        _, _, dropped = match(g, s, lenient=False)
        kept = [x for x in g if x not in added]
        parts[r.posting_id] = (kept, added)
        n_sug, n_dropped = n_sug + len(s), n_dropped + len(dropped)
    n_kept = sum(len(k) for k, _ in parts.values())
    n_added = sum(len(a) for _, a in parts.values())
    print(f"{args.split}: {len(parts)} postings | gold {n_kept + n_added} = kept {n_kept} + human-added {n_added} "
          f"({n_added / (n_kept + n_added):.0%} added) | suggestions dropped by human {n_dropped}/{n_sug}")

    for run in args.runs:
        model, tag = run.rsplit(":", 1)
        pred = pd.read_csv(ROOT / "data" / "processed" / f"statements_{slug(model)}_{tag}.csv")
        by_post = pred.groupby("posting_id").skill.apply(list).to_dict()
        hit_k = hit_a = 0
        for pid, (kept, added) in parts.items():
            p = by_post.get(pid, [])
            hit_k += match(kept, p, lenient=True)[0]
            hit_a += match(added, p, lenient=True)[0]
        print(f"  {run:32} recall kept {hit_k}/{n_kept} = {hit_k / n_kept:.2f} | "
              f"recall human-added {hit_a}/{n_added} = {hit_a / n_added:.2f}")


if __name__ == "__main__":
    main()
