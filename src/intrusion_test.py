"""Human word-intrusion test for clustering runs (Sprint 3: pick the clustering method).

    py src/intrusion_test.py make  --runs DIR_A DIR_B --emb-dir EMB [--topics 20] [--seed 42]
    py src/intrusion_test.py score

make:  for each run, picks N random topics with >= 6 clustered members. Each item shows the topic's 5 most-mentioned
       skills plus 1 intruder: a top-3 skill of another topic of the same run, far from this topic's centroid
       (cosine below the median of all candidates). Items of both runs are shuffled together, so the rater does not
       know which method made a topic (blind). Writes reports/intrusion/items.json (what the UI shows, no answers)
       and key.json (method, topic, intruder). Refuses to overwrite: answers would stop matching their items.
score: reads answers.csv (written by the UI, app/static/intrusion.html) and prints the share of intruders found per
       run, with a 95% Wilson interval. Chance = 1/6. Higher = more coherent topics (Chang et al. 2009).
"""
import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "intrusion"
TOP, MIN_SIZE = 5, 6


def make(args):
    if (OUT / "items.json").exists():
        sys.exit(f"{OUT / 'items.json'} exists; move it away first (answers are tied to these items)")
    vectors = np.load(Path(args.emb_dir) / "vectors.npy")
    rng = random.Random(args.seed)
    items, key = [], {}
    for run_dir in map(Path, args.runs):
        a = pd.read_csv(run_dir / "assignments.csv")
        a = a[a.cluster >= 0]  # HDBSCAN noise is not part of any topic
        groups = {c: g.sort_values(["mention_count", "skill_key"], ascending=[False, True])
                  for c, g in a.groupby("cluster") if len(g) >= MIN_SIZE}
        tops = {c: g.head(3) for c, g in groups.items()}
        for c in rng.sample(sorted(groups), args.topics):
            g = groups[c]
            centroid = vectors[g.vector_row.to_numpy()].mean(axis=0)
            centroid /= np.linalg.norm(centroid)
            cand = pd.concat([t for o, t in tops.items() if o != c])
            cand = cand[~cand.skill_key.isin(g.skill_key)]
            cos = vectors[cand.vector_row.to_numpy()] @ centroid
            far = cand[cos < np.median(cos)]
            intruder = far.iloc[rng.randrange(len(far))].skill_key
            shown = list(g.head(TOP).skill_key) + [intruder]
            rng.shuffle(shown)
            items.append({"skills": shown})
            key_entry = {"run": run_dir.name, "topic": int(c), "intruder": intruder}
            items[-1]["_key"] = key_entry
    rng.shuffle(items)
    for i, it in enumerate(items, 1):
        it["item"] = i
        key[i] = it.pop("_key")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "items.json").write_text(json.dumps(items, indent=1), encoding="utf-8")
    (OUT / "key.json").write_text(json.dumps({"seed": args.seed, "runs": args.runs, "items": key}, indent=1), encoding="utf-8")
    print(f"{len(items)} items -> {OUT / 'items.json'} (key in key.json; do not open it before answering)")


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    mid, half = (p + z * z / (2 * n)) / (1 + z * z / n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return mid - half, mid + half


def score(_args):
    key = json.loads((OUT / "key.json").read_text(encoding="utf-8"))["items"]
    path = OUT / "answers.csv"
    if not path.exists():
        sys.exit("no answers yet: take the test in the UI first (/static/intrusion.html)")
    answers = {}
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            answers[r["item"]] = r  # the last answer per item counts (the rater may change their mind)
    per_run = {}
    for item, k in key.items():
        if item in answers:
            hit = answers[item]["choice"] == k["intruder"]
            per_run.setdefault(k["run"], []).append((hit, item, k, answers[item]["choice"]))
    print(f"answered {len(answers)} of {len(key)} items; chance = {1 / (TOP + 1):.2f}\n")
    for run, rows in sorted(per_run.items()):
        hits = sum(h for h, *_ in rows)
        lo, hi = wilson(hits, len(rows))
        print(f"{run:28} {hits}/{len(rows)} = {hits / len(rows):.2f}   95% CI {lo:.2f}-{hi:.2f}")
    print("\nmissed intruders (topic may be incoherent):")
    for run, rows in sorted(per_run.items()):
        for hit, item, k, choice in rows:
            if not hit:
                print(f"  item {item:>2} {run} topic {k['topic']}: intruder '{k['intruder']}', picked '{choice}'")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--runs", nargs=2, required=True, help="two cluster run folders (assignments.csv)")
    m.add_argument("--emb-dir", required=True, help="the embeddings both runs were clustered on")
    m.add_argument("--topics", type=int, default=20, help="topics per run")
    m.add_argument("--seed", type=int, default=42)
    sub.add_parser("score")
    args = ap.parse_args()
    make(args) if args.cmd == "make" else score(args)


if __name__ == "__main__":
    main()
