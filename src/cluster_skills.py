"""Cluster the skill embeddings from embed_skills.py (Sprint 3). Clustering is a separate batch step from extraction.

    py src/cluster_skills.py --emb-dir EMB --out-dir OUT --method hdbscan --param 5 10 15 20 30
    py src/cluster_skills.py --emb-dir EMB --out-dir OUT --method agglomerative --param 0.2 0.3 0.4 0.5
    py src/cluster_skills.py --emb-dir EMB --out-dir OUT --method kmeans --param 200 400
    py src/cluster_skills.py --emb-dir EMB --out-dir OUT --method leiden --param 0.5 1 2 4

--param is the swept setting: min_cluster_size (hdbscan), cosine distance threshold (agglomerative), k (kmeans), resolution (leiden).
hdbscan runs on a UMAP reduction (cosine, --umap-dim, seed 42) that is cached in OUT; the others use the raw normalised
vectors (leiden: a 15-nearest-neighbour cosine graph, edge weight = similarity, modularity with resolution). Every value gets its own run folder OUT/<run_id>/ (run_id = method + param), never overwritten:
    assignments.csv  vector_row, skill_key, display_label, mention_count, cluster (-1 = noise), probability
    topics.csv       cluster, size, mentions, top_skills (by mention_count), centroid_skill (closest to centre)
    run.json         method, param, settings, metrics, input sha256
OUT/sweep.csv collects the metrics of every run, so methods and settings can be compared side by side.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_score

METHODS = ["hdbscan", "agglomerative", "kmeans", "leiden"]
SEED = 42
SIL_SAMPLE = 3000
TOP_N = 8
KNN = 15


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(emb_dir):
    emb_dir = Path(emb_dir)
    vectors = np.load(emb_dir / "vectors.npy")
    index = pd.read_csv(emb_dir / "skill_index.csv", keep_default_na=False)
    if len(index) != len(vectors) or (index["vector_row"].to_numpy() != np.arange(len(vectors))).any():
        raise ValueError("skill_index.csv rows do not line up with vectors.npy")
    return vectors, index, sha256(emb_dir / "vectors.npy")


def reduce(vectors, vec_sha, out_dir, dim, seed=SEED):
    """UMAP to `dim` dimensions, cached on disk by input hash + settings (UMAP is the slow part)."""
    cache = out_dir / (f"umap_{dim}d_{vec_sha[:12]}.npy" if seed == SEED else f"umap_{dim}d_{vec_sha[:12]}_s{seed}.npy")
    if cache.exists():
        return np.load(cache)
    import umap
    reduced = umap.UMAP(n_components=dim, n_neighbors=15, min_dist=0.0, metric="cosine",
                        random_state=seed).fit_transform(vectors).astype(np.float32)
    np.save(cache, reduced)
    return reduced


def knn_graph(vectors, k=KNN, mutual=False):
    """kNN cosine graph, edge weight = similarity. Union keeps an edge found from either end, mutual from both."""
    import igraph as ig
    from sklearn.neighbors import NearestNeighbors
    dist, nbr = NearestNeighbors(n_neighbors=k + 1, metric="cosine").fit(vectors).kneighbors(vectors)
    edges = {}
    for i in range(len(vectors)):
        for d, j in zip(dist[i, 1:], nbr[i, 1:]):
            edges.setdefault((min(i, j), max(i, j)), []).append(max(0.0, 1 - float(d)))
    if mutual:
        edges = {e: s for e, s in edges.items() if len(s) > 1}
    graph = ig.Graph(n=len(vectors), edges=list(edges))
    graph.es["weight"] = [s[0] for s in edges.values()]
    return graph


def cluster(method, param, vectors, reduced, min_samples=None, knn=KNN, mutual=False, partition="rb", seed=SEED):
    """Return (labels, probabilities). Noise is -1 (hdbscan only)."""
    if method == "hdbscan":
        from sklearn.cluster import HDBSCAN
        model = HDBSCAN(min_cluster_size=int(param), min_samples=min_samples, copy=True).fit(reduced)
        return model.labels_, model.probabilities_
    if method == "agglomerative":
        from sklearn.cluster import AgglomerativeClustering
        model = AgglomerativeClustering(n_clusters=None, distance_threshold=float(param), metric="cosine",
                                        linkage="average").fit(vectors)
        return model.labels_, np.ones(len(vectors))
    if method == "leiden":
        import leidenalg
        graph = knn_graph(vectors, knn, mutual)
        kind = leidenalg.CPMVertexPartition if partition == "cpm" else leidenalg.RBConfigurationVertexPartition
        part = leidenalg.find_partition(graph, kind, weights="weight", resolution_parameter=float(param), seed=seed)
        return np.array(part.membership), np.ones(len(vectors))
    from sklearn.cluster import KMeans
    model = KMeans(n_clusters=int(param), n_init=3, random_state=seed).fit(vectors)
    return model.labels_, np.ones(len(vectors))


def metrics(labels, vectors, index):
    """Cluster count, noise, size spread, and cosine silhouette on a fixed sample of clustered skills."""
    clustered = labels >= 0
    sizes = pd.Series(labels[clustered]).value_counts()
    mentions = index["mention_count"].to_numpy()
    m = {
        "n_clusters": int(len(sizes)),
        "noise_share": round(float(1 - clustered.mean()), 4),
        "noise_mention_share": round(float(mentions[~clustered].sum() / mentions.sum()), 4),
        "largest_cluster": int(sizes.max()) if len(sizes) else 0,
        "median_cluster": float(sizes.median()) if len(sizes) else 0,
        "singleton_clusters": int((sizes == 1).sum()),
        "silhouette_cosine": None,
    }
    rows = np.flatnonzero(clustered)
    if 2 <= m["n_clusters"] < len(rows):
        rows = np.random.default_rng(SEED).choice(rows, min(SIL_SAMPLE, len(rows)), replace=False)
        if len(set(labels[rows])) > 1:
            m["silhouette_cosine"] = round(float(silhouette_score(vectors[rows], labels[rows], metric="cosine")), 4)
    return m


def topics(labels, vectors, index):
    rows = []
    for c in sorted(set(labels) - {-1}):
        members = np.flatnonzero(labels == c)
        sub = index.iloc[members]
        centre = vectors[members].mean(axis=0)
        rows.append({
            "cluster": int(c),
            "size": len(members),
            "mentions": int(sub["mention_count"].sum()),
            "top_skills": "; ".join(sub.nlargest(TOP_N, "mention_count")["skill_key"]),
            "centroid_skill": sub["skill_key"].iloc[int(np.argmax(vectors[members] @ centre))],
        })
    return pd.DataFrame(rows).sort_values("mentions", ascending=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-dir", required=True, help="folder with vectors.npy + skill_index.csv")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--method", required=True, choices=METHODS)
    ap.add_argument("--param", required=True, nargs="+", type=float, help="value(s) to sweep, see docstring")
    ap.add_argument("--umap-dim", type=int, default=10)
    ap.add_argument("--min-samples", type=int, help="hdbscan only; default = min_cluster_size (more noise)")
    ap.add_argument("--knn", type=int, default=KNN, help="leiden only: neighbours per skill")
    ap.add_argument("--mutual", action="store_true", help="leiden only: keep only mutual kNN edges")
    ap.add_argument("--partition", choices=["rb", "cpm"], default="rb", help="leiden only: modularity (rb) or CPM")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vectors, index, vec_sha = load(args.emb_dir)
    reduced = reduce(vectors, vec_sha, out_dir, args.umap_dim) if args.method == "hdbscan" else None

    sweep_path = out_dir / "sweep.csv"
    for param in args.param:
        param = int(param) if param.is_integer() and args.method in ("hdbscan", "kmeans") else param
        run_id = f"{args.method}_{param}" + (f"_umap{args.umap_dim}" if args.method == "hdbscan" else "") \
            + (f"_ms{args.min_samples}" if args.method == "hdbscan" and args.min_samples else "")
        if args.method == "leiden" and (args.partition, args.knn, args.mutual) != ("rb", KNN, False):
            run_id = f"leiden_{args.partition}_{param}_k{args.knn}" + ("_mutual" if args.mutual else "")
        run_dir = out_dir / run_id
        if run_dir.exists():
            print(f"skip {run_id}: {run_dir} exists (never overwritten)")
            continue
        labels, probs = cluster(args.method, param, vectors, reduced, args.min_samples, args.knn, args.mutual,
                                args.partition)
        m = metrics(labels, vectors, index)

        run_dir.mkdir()
        assign = index[["vector_row", "skill_key", "display_label", "mention_count"]].copy()
        assign["cluster"], assign["probability"] = labels, np.round(probs, 4)
        assign.to_csv(run_dir / "assignments.csv", index=False)
        topics(labels, vectors, index).to_csv(run_dir / "topics.csv", index=False)
        run = {"run_id": run_id, "method": args.method, "param": param, "seed": SEED,
               "umap_dim": args.umap_dim if args.method == "hdbscan" else None, "min_samples": args.min_samples,
               **({"knn": args.knn, "mutual": args.mutual, "partition": args.partition}
                  if args.method == "leiden" else {}),
               "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "vectors_sha256": vec_sha, "metrics": m}
        (run_dir / "run.json").write_text(json.dumps(run, indent=2))

        row = pd.DataFrame([{"run_id": run_id, "method": args.method, "param": param, **m}])
        row.to_csv(sweep_path, mode="a", header=not sweep_path.exists(), index=False)
        print(f"{run_id}: {m}")


if __name__ == "__main__":
    main()
