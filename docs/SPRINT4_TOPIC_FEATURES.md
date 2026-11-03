# Sprint 4 topic features (task 2)

`python src/topic_features.py build` reads only the frozen snapshot (`docs/SPRINT4_INPUT_SNAPSHOT.md`), checks every
file hash first, and writes `data/processed/sprint4_features_hdbscan_10_umap10_ms1_2026-10-23/` (gitignored) plus a
tracked manifest copy in `reports/sprint4_features/<run>/manifest.json`. No database, no API, no re-clustering.
`python src/topic_features.py verify` re-hashes the outputs. An existing output folder is never overwritten.

## Method

- **Centroid** = unweighted mean of the topic's *assigned* members' unit vectors, L2-normalised. Each skill counts
  once: the snapshot has no mention counts, and frequency weighting would let a few generic skills pull the centre.
  Weak members (HDBSCAN noise attached to their nearest topic) are excluded from the centroid and from coherence
  statistics; they are only counted. Check: our member cosines equal the Sprint 3 membership scores (max difference
  5e-5), so the centroid definition matches Sprint 3.
- **Representatives** = the 10 assigned members closest to the centroid (ties by skill_key). No LLM labels.
- **Cohesion**: `cos_mean` / `cos_min` / `cos_max` of assigned members to the centroid; `dispersion = 1 - cos_mean`.
  `resultant` (length of the mean vector) equals `cos_mean` mathematically; it is kept as a check.
- **Confidence**: Sprint 3 `score` (cosine to centroid) and `margin` as stored. A missing value is an empty cell,
  never 0 (`n_missing_score`; currently 0 missing).
- **Reference** (`reference_summary.csv`): distinct *assigned* skills with a confident link (`verdict = known_skill`),
  split ESCO / O\*NET by the `source` prefix; coverage = those / assigned members. `top_concept_share` = share of
  linked skills that share the most common `ref_id` (concentration, not purity). **Purity is unavailable**: the
  snapshot has no ESCO / O\*NET broader-group field, and no category is inferred from titles.
- **Similarity**: 374 × 374 cosine of centroids (`topic_similarity.npy`, row/column order = `topic_ids.csv`), top-5
  neighbours per topic (`topic_neighbors.csv`), and pairs ≥ 0.90 (`similar_topic_pairs.csv`) **for human
  inspection only** — nothing is merged.

## Files

| File | Content |
|---|---|
| `topic_ids.csv` | row → topic_id (sorted); the order of both arrays |
| `topic_centroids.npy` | 374 × 384 float32 |
| `topic_similarity.npy` | 374 × 374 float32, symmetric, diagonal 1 |
| `topic_features.csv` | one row per topic: label, review status, transversal flag, counts, confidence and cohesion stats |
| `representative_skills.csv` | topic_id, rank, skill_key, vector_row, cosine |
| `reference_summary.csv` | per-topic ESCO / O\*NET coverage, link types, concept concentration, purity status |
| `topic_neighbors.csv` | topic_id, rank, neighbour_id, cosine, mutual_nearest, flag_for_review |
| `similar_topic_pairs.csv` | topic pairs with centroid cosine ≥ 0.90 |

Reviewers of the intrusion test (`docs/INTRUSION_TEST_V2.md`) should finish it before browsing these files: they list
topic members.
