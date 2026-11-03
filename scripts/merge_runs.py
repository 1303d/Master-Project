"""Merge two extraction runs into one (e.g. lists pass + duties pass), dropping repeats.

    py scripts/merge_runs.py qwen_qwen3.8-27b_v8 qwen_qwen3.8-27b_v8_duties qwen_qwen3.8-27b_v8+duties

An item of the second run is dropped when the first run already has the same skill for that posting
(strict name match, as in src/evaluate.py) or the second run repeats itself. A posting counts as done only when
both runs finished it. Writes data/processed/statements_<out>.csv and extraction_postings_<out>.csv, so
evaluate.py can score <out> (and use it as --baseline).
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluate import norm, pairs_ok  # noqa: E402

P = ROOT / "data" / "processed"


def main(first, second, out):
    a, b = pd.read_csv(P / f"statements_{first}.csv"), pd.read_csv(P / f"statements_{second}.csv")
    da, db = (pd.read_csv(P / f"extraction_postings_{r}.csv") for r in (first, second))
    rows = []
    for pid, items in b.groupby("posting_id", sort=False):
        have = [norm(s) for s in a.loc[a.posting_id == pid, "skill"]]
        for r in items.itertuples(index=False):
            n = norm(r.skill)
            if not any(pairs_ok(n, h, lenient=False) for h in have):
                rows.append(r._asdict())
                have.append(n)
    merged = pd.concat([a, pd.DataFrame(rows, columns=b.columns)], ignore_index=True)
    merged["statement_id"] = merged.posting_id + ":skill:" + (merged.groupby("posting_id").cumcount() + 1).astype(str)
    merged.to_csv(P / f"statements_{out}.csv", index=False)
    ok = set(da.loc[da.status == "done", "posting_id"]) & set(db.loc[db.status == "done", "posting_id"])
    d = da.set_index("posting_id")[["status", "n_skills", "tokens_in", "tokens_out"]].join(
        db.set_index("posting_id")[["tokens_in", "tokens_out"]], rsuffix="_2")
    d["status"] = ["done" if p in ok else "failed" for p in d.index]
    d["n_skills"] = merged.groupby("posting_id").size().reindex(d.index).fillna(0).astype(int)
    d["tokens_in"], d["tokens_out"] = d.tokens_in + d.tokens_in_2, d.tokens_out + d.tokens_out_2
    d[["status", "n_skills", "tokens_in", "tokens_out"]].reset_index().to_csv(P / f"extraction_postings_{out}.csv", index=False)
    print(f"{out}: {len(a)} + {len(rows)} new from {second} ({len(b) - len(rows)} repeats dropped) = {len(merged)} items, "
          f"{len(ok)} postings done in both")


if __name__ == "__main__":
    main(*sys.argv[1:4])
