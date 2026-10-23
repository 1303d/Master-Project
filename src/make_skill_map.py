"""3D coordinates for the UI's Skill map tab (UMAP of the skill embeddings, for display only).

    py src/make_skill_map.py --emb-dir EMB --out MAP.csv

UMAP: cosine, 3 dimensions, n_neighbors 15, min_dist 0.1, seed 42. Clustering does NOT use these coordinates.
Output: skill_key, mention_count, x, y, z. Refuses to overwrite.
"""
import argparse
from pathlib import Path

import pandas as pd

from cluster_skills import SEED, load


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out}")

    import umap
    vectors, index, _ = load(args.emb_dir)
    xyz = umap.UMAP(n_components=3, n_neighbors=15, min_dist=0.1, metric="cosine",
                    random_state=SEED).fit_transform(vectors)
    df = index[["skill_key", "mention_count"]].copy()
    df["x"], df["y"], df["z"] = xyz[:, 0].round(3), xyz[:, 1].round(3), xyz[:, 2].round(3)
    df.to_csv(out, index=False)
    print(f"{len(df)} skills -> {out}")


if __name__ == "__main__":
    main()
