# Sprint 3 — Skill preparation and embeddings (pilot, 2026-10-21)

*Taxonomy of Work capstone, Section B. This report covers the first Sprint 3 step: preparing extracted skill
labels and embedding them. It is an **exploratory pilot** on a partial extraction batch, not the final corpus.*

## 1. Scope: what the pilot covers

| Item | Count |
|---|---|
| Postings in the extraction sample (`extraction_sample_2000.csv`) | 2,000 |
| Completed by the extractor (Qwen3.8 27B on Groq, prompt v3) | 87 (#1–87) |
| … with at least one skill | 79 |
| … successful with zero skills (explicit `{"skills": []}`) | 8 |
| Failed | 0 |
| Not yet processed (#88–2000) | 1,913 |
| Skill mentions (statements) | 1,005 |
| Unique skill labels after normalisation | 712 |
| Approved evidence corrections | 21 (in 9 postings) |

The batch was interrupted; the counts come from the read-only reconciliation in the input bundle
(`RECONCILIATION.md`, `reconcile_result.csv`). No extraction API was called for this step.

**Review status.** Only the 21 flagged statements were reviewed, in an AI-assisted review in chat that the
user approved (reviewer Lochan, 2026-10-21). The other **984 of 1,005 labels (98%) are still manually
unreviewed** extractor output (`review_status = not_manually_reviewed`). They have not been checked against
the labelling rules, and traits and synonyms are still present.

**Not done yet:** clustering, labelling of clusters, the hierarchy, and storing the prepared skills or
vectors in the database (Supabase). Nothing in this step reads or writes Supabase.

## 2. Preparation (`src/prepare_skills.py`)

Inputs: the statements CSV (one row per extracted skill, `statement_id = <posting_id>:skill:<i>`), the
approved review CSV and the postings CSV (for the description text).

1. **Validation.** The run stops with a list of errors, and writes nothing, if any of these fail:
   - statement, approval and posting IDs are unique;
   - every statement's posting exists, and no skill label is empty;
   - for each approval, the statement exists and the approval's `posting_id`, `original_skill` and
     `original_evidence` equal the statement's;
   - `reviewer_confirmation = approved` and `decision = keep` (the only decision used so far);
   - the corrected evidence is the **exact** substring `description[evidence_start:evidence_end]` of that
     posting.
2. **Corrections** are applied by `statement_id`. All 21 replace the evidence: the extractor had shortened
   quotes with "…" (for example `Knowledge of... CMS`), so the original evidence was not in the text. One
   correction also changes the label: `Microsoft solutions` became `Microsoft solution areas`. The original
   label and evidence are kept in `original_skill` / `original_evidence`, and `review_status` marks the row
   `approved_flagged_entry`. `evidence_in_text` is the extractor-time flag and is kept unchanged, so it
   stays `False` for these 21 rows even though the corrected evidence is now exact.
3. **Normalisation**: `skill_key = label.strip().lower()`. That is all. No synonym merging, no plural or
   punctuation changes and no trait filtering, because those decisions belong to clustering and review.
   Example: `Python` / `python` share a key; `communication` and `verbal communication` do not.
4. **Counting** per `skill_key`: `mention_count` (statements) and `posting_count` (distinct postings).
   `display_label` is the most common original spelling, and a tie goes to the first one seen. All 1,005
   statement rows are kept with their `statement_id` and `posting_id` links, so every skill can be traced
   back to its supporting postings. 630 of the 712 keys occur once. The most common are teamwork (22),
   communication (20) and written communication (18).

Outputs: `prepared_mentions.csv` (1,005 rows), `unique_skills.csv` (712 rows, sorted by key) and
`manifest.json` (counts, normalisation flags, sha256 of every input and output).

## 3. Embeddings (`src/embed_skills.py`)

| Setting | Value |
|---|---|
| Model | `BAAI/bge-small-en-v1.5` |
| Revision (pinned commit) | `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` |
| Dimensions | 384, float32 |
| Input | `skill_key`, as-is (template `{skill_key}`; **no** BGE query prefix, since labels are not search queries) |
| Normalised | yes (L2, unit length), so dot product = cosine similarity |
| Device | cpu |
| Result | 712 × 384 vectors |

The model settings are read from `embedding_model.json`. The script refuses a config that has no pinned
revision, adds a prefix or does not normalise. After encoding, it checks the shape, dtype, that all values
are finite and that every row has unit norm (tolerance 1e-4). It writes nothing if a check fails, and it
never overwrites existing outputs. Row *i* of `vectors.npy` is the skill with `vector_row = i` in
`skill_index.csv`. `metadata.json` stores the config, the shape, the sha256 of `unique_skills.csv` and of
both output files.

Environment used for the pilot vectors (`environment.txt`): Python 3.14.8, sentence-transformers 6.2.0,
transformers 5.20.2, torch 2.14.1, numpy 2.5.4, pandas 3.0.6. Other versions or hardware can change the
last float digits, so re-made vectors are checked by the validations, not by a byte hash.

## 4. How to reproduce

```
py -m pip install -r requirements.txt

py src/prepare_skills.py ^
  --statements data/interim/sprint3_pilot_2026-10-21/statements_qwen_qwen3.8-27b_sample2000_v3.csv ^
  --approved   data/interim/sprint3_pilot_2026-10-21/evidence_review_approved.csv ^
  --postings   data/interim/sprint3_pilot_2026-10-21/extraction_sample_2000.csv ^
  --out-dir    <new folder> ^
  --scope "Partial Kaggle Qwen v3 pilot: 87 completed postings"

py src/embed_skills.py ^
  --skills       <new folder>/unique_skills.csv ^
  --model-config data/processed/sprint3_pilot_2026-10-21/embedding_model.json ^
  --out-dir      <new folder>/embeddings

py -m pytest tests/test_skill_prep.py -q      # synthetic fixtures; no model download
```

(On macOS/Linux use `python3` or `.venv/bin/python` and `\` for line breaks.) Both scripts refuse to write
into a folder that already holds their outputs, so use a new folder to keep the shared results safe.

**Check (2026-10-21):** preparation was re-run into a temporary folder. `prepared_mentions.csv` and
`unique_skills.csv` are byte-identical to the shared outputs (sha256 `89b1ce2e…` and `75c60be2…`). The
manifest has the same fields and the same file hashes; only the path keys differ. The shared vectors were not
re-made. They pass the embedding validations (712 × 384, float32, finite, max |norm − 1| = 1.8e-7), their
hashes match `metadata.json`, and an index rebuilt from `unique_skills.csv` is byte-identical to
`skill_index.csv`.

## 5. Where the data lives

`data/interim/` and `data/processed/` are ignored by Git: the files are large, and the posting texts are
not for a public repo. The input bundle (`data/interim/sprint3_pilot_2026-10-21/`) and the generated outputs
(`data/processed/sprint3_pilot_2026-10-21/`) are shared separately through the team Drive. Git holds only the
scripts, tests and this report. The sha256 values in `manifest.json` and `embeddings/metadata.json` let a
teammate check that their copy is the same one.
