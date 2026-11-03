# Blind cluster intrusion test v2 (Sprint 3 coherence check)

Run: `hdbscan_10_umap10_ms1_2026-10-23` (the active Supabase run). Code: `src/intrusion_v2.py`.
Folder: `reports/intrusion_v2/hdbscan_10_umap10_ms1_2026-10-23/`. The v1 test (`reports/intrusion/`, origin/main)
is left unchanged.

## What was generated (2026-11-02)

- 24 questions, 24 different topics, 5 options each (4 skills from one topic + 1 intruder). Chance = 20 %.
- Topics drawn by stratum, 4 each: transversal, low confidence (mean member score in the lowest quarter),
  long tail (lowest member score in the lowest quarter = possible contamination), large / medium / small
  (size terciles 15 / 24 assigned members). Seed 20261103.
- Intruders come from nearby, non-transversal topics and are not near-synonyms (cosine to every genuine skill
  < 0.70), so they are not obvious. The correct letter is balanced across A–E.
- 11 topics were excluded because their members or labels were printed in the audit chat on 2026-11-02.
- Options are skill names only. A topic's label is its centroid skill, so it can appear as one of the genuine
  options (4 questions) — it is never marked as a label.

| File | Who may open it |
|---|---|
| `questions.json`, `responses/<you>.csv` | reviewers |
| `manifest.json` | anyone (seed, strata, hashes; no answers, no topic IDs) |
| `data/interim/intrusion_v2/<run>/answer_key.json` | **only the scorer, after all three submitted** (gitignored, hash in the manifest) |
| `submitted/<name>.json` | written by `submit`; others should not open it before scoring |

`responses/` and `submitted/` are **gitignored** (2026-11-02), so a filled answer file cannot reach Git by
accident before everyone has answered. The blank `responses/<you>.csv` templates (no answers in them) are
handed out once via the team Drive.

## For each reviewer (Lochan, Priyanka, Dhanush)

1. Open **only your own file**: `reports/intrusion_v2/hdbscan_10_umap10_ms1_2026-10-23/responses/<you>.csv`
   (Excel, Numbers or a text editor). Do not open other reviewers' files, `submitted/`, or `data/interim/`.
2. For each row, read the five skills in columns A–E. Four belong together; write the letter of the one that
   does not belong in **answer** (A, B, C, D or E). Use **note** for comments ("two could be intruders").
   Do not edit the other columns. Answer on your own — no discussion until scoring.
3. Save as CSV (same name).
4. Check: `python src/intrusion_v2.py validate --reviewer <you>` → must say `24 answered, 0 missing, 0 problems`.
5. Lock: `python src/intrusion_v2.py submit --reviewer <you>`. After this the answers cannot be changed
   (a second submit is refused; editing the CSV afterwards makes scoring fail).
6. Tell the team you have submitted. **Hand in only after all three have submitted**, so nobody sees answers
   early. The files are gitignored, so adding them needs `-f` (a deliberate step):
   `git add -f reports/intrusion_v2/hdbscan_10_umap10_ms1_2026-10-23/responses/<you>.csv reports/intrusion_v2/hdbscan_10_umap10_ms1_2026-10-23/submitted/<you>.json`
   then commit and push.

## Scoring (one person, after all three pushed)

1. `git pull`, then `python src/intrusion_v2.py status` → all three `submitted`.
2. Get the answer key file from the machine that generated it (Lochan's, `data/interim/intrusion_v2/...`).
   It was lost once and **rebuilt offline on 2026-11-02** from the frozen Sprint 4 snapshot with the recorded seed;
   the rebuilt file's SHA-256 equals the one in `manifest.json` (as do the questions and the sampling report), so it
   is byte-identical to the original. `score` re-checks this hash every time.
3. `python src/intrusion_v2.py score` (or `--key <path>`). It checks the key hash and that no response changed
   after submission, then writes `scores/score_<time>.json` (never overwritten) and prints:
   - **correctness**: per reviewer (with 95 % Wilson interval), overall, by stratum;
   - **agreement**: pairwise same choice, Fleiss' kappa, unanimous vs disputed questions;
   - **needs adjudication**: disputed questions and questions most reviewers got wrong.
   Agreement means reviewers chose alike, not that they were right; low accuracy on a topic means the topic
   may be incoherent (or the intruder fits it), which the team then discusses.

## Limits

- Blinding is procedural, not enforced: the key file is on the generating machine (Lochan's), and anyone can
  read files in the repository. Lochan should not open `data/interim/intrusion_v2/`.
- `make` refuses to run again for this run (the questions exist), so the test cannot be silently regenerated.
- 24 questions give wide intervals (±~0.2 per reviewer); the result is evidence about coherence, not proof.

Tests: `python -m pytest tests/intrusion_v2 -q` (synthetic taxonomy and synthetic reviewers only).
