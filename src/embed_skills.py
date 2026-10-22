"""Embed the unique skill keys from prepare_skills.py with a pinned BGE model revision (Sprint 3).

    py src/embed_skills.py --skills UNIQUE.csv --model-config embedding_model.json --out-dir OUT [--batch-size 64]

Example (the 2026-10-21 pilot bundle; OUT must be a new folder, the existing embeddings are never overwritten):
    py src/embed_skills.py \
        --skills data/processed/sprint3_pilot_2026-10-21/unique_skills.csv \
        --model-config data/processed/sprint3_pilot_2026-10-21/embedding_model.json \
        --out-dir data/processed/<new_folder>/embeddings

The model config (model_id, revision, dimensions, device, input_column, input_template, normalize_embeddings)
is used as given: skill_key is embedded as-is (template "{skill_key}", no BGE query prefix) and vectors are
L2-normalised. Row i of vectors.npy is the skill with vector_row == i in skill_index.csv.
Checks dimensions, finite values and unit norms before anything is written. Refuses to overwrite outputs.
Output: <out-dir>/vectors.npy (float32), skill_index.csv, metadata.json (config + shape + sha256)
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

CONFIG_KEYS = ["model_id", "revision", "dimensions", "device", "input_column", "input_template",
               "normalize_embeddings"]
INDEX_COLS = ["vector_row", "skill_key", "display_label", "mention_count", "posting_count"]
OUTPUTS = ["vectors.npy", "skill_index.csv", "metadata.json"]
NORM_TOL = 1e-4


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_config(config):
    missing = [k for k in CONFIG_KEYS if k not in config]
    if missing:
        raise ValueError(f"model config: missing {missing}")
    if not config["revision"] or config["revision"] in ("main", "latest"):
        raise ValueError("model config: revision must be a pinned commit hash")
    if config["input_template"] != "{skill_key}" or config["input_column"] != "skill_key":
        raise ValueError("model config: expected input_column skill_key and template '{skill_key}' (no prefix)")
    if config["normalize_embeddings"] is not True:
        raise ValueError("model config: normalize_embeddings must be true")


def validate_skills(skills):
    """unique_skills.csv must have one row per non-empty, already-normalised key."""
    missing = [c for c in INDEX_COLS[1:] if c not in skills.columns]
    if missing:
        raise ValueError(f"skills: missing columns {missing}")
    keys = skills["skill_key"]
    if (keys == "").any():
        raise ValueError("skills: empty skill_key")
    if keys.duplicated().any():
        raise ValueError(f"skills: duplicate skill_key {keys[keys.duplicated()].tolist()}")
    bad = keys[keys != keys.str.strip().str.lower()].tolist()
    if bad:
        raise ValueError(f"skills: skill_key not normalised {bad}")


def validate_vectors(vectors, n_rows, dims):
    """Shape (n_rows, dims), float32, all finite, every row unit length."""
    if vectors.shape != (n_rows, dims):
        raise ValueError(f"vectors: shape {vectors.shape}, expected {(n_rows, dims)}")
    if vectors.dtype != np.float32:
        raise ValueError(f"vectors: dtype {vectors.dtype}, expected float32")
    if not np.isfinite(vectors).all():
        raise ValueError("vectors: non-finite values")
    norms = np.linalg.norm(vectors, axis=1)
    off = np.flatnonzero(np.abs(norms - 1) > NORM_TOL)
    if off.size:
        raise ValueError(f"vectors: {off.size} rows not unit length (first: row {off[0]}, norm {norms[off[0]]:.6f})")


def build_index(skills):
    index = skills[INDEX_COLS[1:]].reset_index(drop=True)
    index.insert(0, "vector_row", range(len(index)))
    return index


def embed(texts, config, batch_size):
    from sentence_transformers import SentenceTransformer  # heavy import; only when actually embedding

    model = SentenceTransformer(config["model_id"], revision=config["revision"], device=config["device"])
    got = model.get_sentence_embedding_dimension()
    if got != config["dimensions"]:
        raise ValueError(f"model gives {got} dimensions, config says {config['dimensions']}")
    vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=True, convert_to_numpy=True,
                           show_progress_bar=True)
    return np.asarray(vectors, dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills", required=True, help="unique_skills.csv from prepare_skills.py")
    ap.add_argument("--model-config", required=True, help="JSON with model_id, revision, dimensions, ...")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--device", help="override the config's device (e.g. cpu, mps, cuda)")
    args = ap.parse_args()

    out = Path(args.out_dir)
    exists = [f for f in OUTPUTS if (out / f).exists()]
    if exists:
        raise SystemExit(f"Refusing to overwrite {exists} in {out}")

    config = json.loads(Path(args.model_config).read_text(encoding="utf-8"))
    if args.device:
        config["device"] = args.device
    validate_config(config)
    skills = pd.read_csv(args.skills, encoding="utf-8-sig", dtype={"skill_key": str, "display_label": str},
                         keep_default_na=False)
    validate_skills(skills)
    index = build_index(skills)
    texts = [config["input_template"].format(skill_key=k) for k in index["skill_key"]]

    vectors = embed(texts, config, args.batch_size)
    validate_vectors(vectors, len(index), config["dimensions"])

    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "vectors.npy", vectors)
    index.to_csv(out / "skill_index.csv", index=False, encoding="utf-8")
    metadata = {**config, "shape": list(vectors.shape), "dtype": str(vectors.dtype),
                "unique_skills_sha256": sha256(args.skills),
                "files_sha256": {f: sha256(out / f) for f in ["vectors.npy", "skill_index.csv"]}}
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"{vectors.shape[0]} vectors x {vectors.shape[1]} dims ({config['model_id']}@{config['revision'][:7]}) -> {out}")


if __name__ == "__main__":
    main()
