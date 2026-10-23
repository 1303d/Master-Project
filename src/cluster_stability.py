"""Stability and coherence check for one clustering config (Sprint 3, clustering review step 3).

    py src/cluster_stability.py --emb-dir EMB --out OUT.csv --method leiden --param 0.02 --partition cpm --knn 15
    py src/cluster_stability.py --emb-dir EMB --out OUT.csv --method hdbscan --param 10 --min-samples 1

Runs the config on the full data, then on --runs random subsamples (--frac of skills, algorithm seed fixed, so
only the data changes) and on --seeds other seeds with the full data (only the seed changes). Reports:
  sub_ami      mean/sd AMI between subsample runs, on skills present in both (and clustered in both, for hdbscan)
  seed_ami     mean AMI of other-seed runs vs the seed-42 run
  topic_jacc   per full-run topic, best Jaccard with any subsample cluster (on that subsample's skills),
               averaged over subsamples (Hennig 2007); median, share >= 0.75 (stable), share < 0.5 (dissolved)
  coverage     share of skills / mentions in a cluster; intra_cos = mean cosine of a skill to its own centroid
One row per config is appended to --out; per-topic stability goes to OUT_topics_<config>.csv.
"""
import argparse
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_mutual_info_score as ami

from cluster_skills import KNN, SEED, cluster, load


def run(method, param, X, opts, seed=SEED):
    reduced = None
    if method == "hdbscan":
        import umap
        reduced = umap.UMAP(n_components=10, n_neighbors=15, min_dist=0.0, metric="cosine",
                            random_state=seed).fit_transform(X)
    labels, _ = cluster(method, param, X, reduced, seed=seed, **opts)
    return np.asarray(labels)


def pair_ami(a, b):
    keep = (a >= 0) & (b >= 0)
    return ami(a[keep], b[keep])


def intra_cos(X, labels):
    sims = []
    for c in set(labels) - {-1}:
        m = labels == c
        centre = X[m].mean(axis=0)
        sims.append(X[m] @ (centre / np.linalg.norm(centre)))
    return float(np.concatenate(sims).mean())


def topic_jaccard(full, subs):
    """For each full-run topic: mean over subsamples of the best Jaccard with a subsample cluster."""
    out = {}
    for c in set(full) - {-1}:
        members = np.flatnonzero(full == c)
        scores = []
        for idx, lab in subs:
            ref = set(np.intersect1d(members, idx))
            if not ref:
                continue
            groups = pd.Series(idx[lab >= 0]).groupby(lab[lab >= 0]).apply(set)
            scores.append(max((len(ref & g) / len(ref | g) for g in groups), default=0.0))
        out[int(c)] = float(np.mean(scores)) if scores else np.nan
    return pd.Series(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-dir", required=True)
    ap.add_argument("--out", required=True, help="CSV to append one summary row to")
    ap.add_argument("--method", required=True, choices=["hdbscan", "leiden", "agglomerative", "kmeans"])
    ap.add_argument("--param", required=True, type=float)
    ap.add_argument("--min-samples", type=int)
    ap.add_argument("--knn", type=int, default=KNN)
    ap.add_argument("--mutual", action="store_true")
    ap.add_argument("--partition", choices=["rb", "cpm"], default="rb")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--frac", type=float, default=0.8)
    ap.add_argument("--seeds", type=int, default=3, help="extra full-data runs with seeds 1..N")
    args = ap.parse_args()

    X, index, _ = load(args.emb_dir)
    mentions = index["mention_count"].to_numpy()
    opts = {"min_samples": args.min_samples, "knn": args.knn, "mutual": args.mutual, "partition": args.partition}
    param = int(args.param) if args.method in ("hdbscan", "kmeans") else args.param
    name = f"{args.method}_{param}" + (f"_ms{args.min_samples}" if args.min_samples else "") \
        + (f"_{args.partition}_k{args.knn}" + ("_mutual" if args.mutual else "") if args.method == "leiden" else "")

    full = run(args.method, param, X, opts)
    rng = np.random.default_rng(0)
    subs = []
    for _ in range(args.runs):
        idx = np.sort(rng.choice(len(X), int(args.frac * len(X)), replace=False))
        subs.append((idx, run(args.method, param, X[idx], opts)))
    sub_scores = []
    for (ia, la), (ib, lb) in combinations(subs, 2):
        _, pa, pb = np.intersect1d(ia, ib, return_indices=True)
        sub_scores.append(pair_ami(la[pa], lb[pb]))
    seed_scores = [pair_ami(full, run(args.method, param, X, opts, seed=s)) for s in range(1, args.seeds + 1)]
    tj = topic_jaccard(full, subs)

    clustered = full >= 0
    row = {
        "config": name, "n_topics": int(len(set(full) - {-1})),
        "sub_ami_mean": round(float(np.mean(sub_scores)), 4), "sub_ami_sd": round(float(np.std(sub_scores)), 4),
        "seed_ami_mean": round(float(np.mean(seed_scores)), 4) if seed_scores else None,
        "topic_jacc_median": round(float(tj.median()), 4),
        "topics_stable_share": round(float((tj >= 0.75).mean()), 4),
        "topics_dissolved_share": round(float((tj < 0.5).mean()), 4),
        "skill_coverage": round(float(clustered.mean()), 4),
        "mention_coverage": round(float(mentions[clustered].sum() / mentions.sum()), 4),
        "intra_cos": round(intra_cos(X, full), 4),
    }
    out = Path(args.out)
    pd.DataFrame([row]).to_csv(out, mode="a", header=not out.exists(), index=False)
    tj.rename("jaccard").rename_axis("cluster").to_csv(out.with_name(f"{out.stem}_topics_{name}.csv"))
    print(row)


if __name__ == "__main__":
    main()
