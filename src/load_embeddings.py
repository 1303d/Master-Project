"""Store the skill embeddings in Supabase (pgvector), so the representation lives in the shared database.

    py src/load_embeddings.py --emb-dir data/processed/sprint3_full_2026-10-22/canonical_v2/embeddings

Reads vectors.npy + skill_index.csv + metadata.json (embed_skills.py output). Rows are keyed by the vectors file
hash, the same hash cluster_runs.vectors_sha256 records. Re-running for the same hash replaces those rows.
Check after loading: cosine of a few pairs computed in Postgres equals the numpy value.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb-dir", required=True)
    args = ap.parse_args()
    d = Path(args.emb_dir)
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    sha = meta["files_sha256"]["vectors.npy"]
    vectors = np.load(d / "vectors.npy")
    keys = pd.read_csv(d / "skill_index.csv", keep_default_na=False)["skill_key"].tolist()
    if len(keys) != len(vectors):
        raise SystemExit("skill_index.csv and vectors.npy differ in length")

    with db.connect() as con, con.transaction(), con.cursor() as cur:
        cur.execute("delete from skill_embeddings where vectors_sha256 = %s", (sha,))
        with cur.copy("copy skill_embeddings (vectors_sha256, skill_key, model_id, revision, embedding) from stdin") as cp:
            for k, v in zip(keys, vectors):
                cp.write_row((sha, k, meta["model_id"], meta["revision"], "[" + ",".join(f"{x:.7g}" for x in v) + "]"))
        n = cur.execute("select count(*) from skill_embeddings where vectors_sha256 = %s", (sha,)).fetchone()[0]
        for i, j in ((0, 1), (len(keys) // 2, len(keys) - 1)):  # Postgres cosine must match numpy
            pg = cur.execute("""select 1 - (a.embedding <=> b.embedding) from skill_embeddings a, skill_embeddings b
                                where a.vectors_sha256 = %(s)s and b.vectors_sha256 = %(s)s
                                  and a.skill_key = %(a)s and b.skill_key = %(b)s""",
                             {"s": sha, "a": keys[i], "b": keys[j]}).fetchone()[0]
            if abs(pg - float(vectors[i] @ vectors[j])) > 1e-4:
                raise SystemExit(f"cosine mismatch for {keys[i]} / {keys[j]}: {pg} vs {vectors[i] @ vectors[j]}")
    print(f"{n} embeddings ({vectors.shape[1]} dims, {meta['model_id']}) stored for vectors {sha[:12]}; cosine check ok")


if __name__ == "__main__":
    main()
