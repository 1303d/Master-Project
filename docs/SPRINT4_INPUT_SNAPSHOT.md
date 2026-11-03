# Sprint 4 input snapshot (frozen Sprint 3 taxonomy)

Made by `src/freeze_sprint4_input.py` from the active Supabase run `hdbscan_10_umap10_ms1_2026-10-23`, read inside a
transaction the server confirmed as READ ONLY. Sprint 4 reads only this snapshot, so later changes in the database
(new statements, a new run) cannot silently change the hierarchy work.

- Snapshot: `data/processed/sprint4_input_hdbscan_10_umap10_ms1_2026-10-23/` (gitignored, 20 MB; share via Drive)
- Tracked manifest: `reports/sprint4_input/hdbscan_10_umap10_ms1_2026-10-23/manifest.json` (hash of every file)
- Check a copy you received: `python src/freeze_sprint4_input.py verify` (add `--db --env <path to .env>` to also
  compare with Supabase). The export command refuses to overwrite an existing snapshot.

## Files (schema `sprint4_input/1`)

| File | Rows | Key / order | Columns |
|---|---|---|---|
| `run.json` | 1 | — | cluster_runs row: run_id, method, params, metrics, vectors_sha256, is_active, created_at |
| `topics.csv` | 374 | topic_id | topic_id, cluster_id, event, jaccard, level, label (= centroid skill, provisional), parent_topic_id, status, is_transversal, split_from, merged_into, first_run, last_run, label_reviewed_by |
| `skills.csv` | 11,093 | vector_row (= sorted skill_key) | vector_row, skill_key (canonical ID and name) |
| `vectors.npy` | 11,093 × 384 float32 | row i = skills.csv vector_row i | BAAI/bge-small-en-v1.5 @ 5c38ec7c…, unit length |
| `memberships.csv` | 11,093 | skill_key, topic_id | skill_key, topic_id, role, state (assigned 8,646 / weak 2,447), score (cosine to centroid), margin |
| `aliases.csv` | 11,449 | alias_key | raw name → canonical skill_key, rule (R1–R4), reviewed_by, created_at |
| `reference_links.csv` | 10,659 | skill_key | ESCO / O*NET link per canonical skill: verdict, source, ref_label, ref_id, score, match, review_status, updated_at (434 skills have no link row) |
| `library.csv` | 196 | skill_key | cross-sector library (status, postings, templates, sectors, entropy, skill_type, reuse_level) |
| `library_links.csv` | 980 | skill_key, topic_id | library skill → topic links (lift, p, q, strength) |

## Notes

- Deterministic: rows sorted by their key, floats via `repr`, `\n` line ends, sorted JSON keys; the time is only in
  the manifest, so the same data always gives the same file hashes (`data_fingerprint`).
- `vectors.npy` is the database copy. `load_embeddings.py` stored vectors with 7 significant digits, so it is not
  byte-identical to the original Sprint 3 file; that file's hash is kept as `source_vectors_sha256` (8dc4dbdf…).
- Not included: posting text, statements, gold labels, review data, credentials.
