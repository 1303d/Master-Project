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
| `evaluation.json` | anyone: the declared protocol (single-reviewer decision record, tracked) |
| `summary_<mode>.md` | anyone: **shareable**, aggregate numbers only (tracked) |
| `private/`, `scores/` | **private**: full scores, per-question reports, diagnostics — answer-key content (gitignored) |

`responses/` and `submitted/` are **gitignored** (2026-11-02), so a filled answer file cannot reach Git by
accident before everyone has answered. The blank `responses/<you>.csv` templates (no answers in them) are
handed out once via the team Drive.

## Evaluation actually run: single reviewer (protocol deviation, 2026-11-02)

**Planned protocol:** three independent reviewers (Lochan, Priyanka, Dhanush), scored only when all three have
submitted, with inter-reviewer agreement (pairwise agreement, Fleiss' kappa) reported next to accuracy.

**What happened:** only **one genuine reviewer (Lochan)** took the test. Dhanush and Priyanka did not, and no
responses were created or copied for them. The team decided to evaluate this run as a **single-reviewer,
exploratory** study. The decision is recorded once, create-only, in `evaluation.json` (`declare-single`), tied to
Lochan's locked submission by its SHA-256; it does not change any answer, question or key.

| | Planned | Run |
|---|---|---|
| Mode | `three_reviewer` | `single_reviewer` |
| Reviewers / expected | 3 / 3 | 1 (Lochan) / 1 |
| Status | — | **completed** (1 of 1 submitted, 24 questions) |
| Agreement | pairwise + Fleiss' kappa | **not available** — agreement needs at least two raters |

**Result** (`summary_single_reviewer.md`): 15 / 24 correct = **0.625**, 95 % Wilson interval 0.427–0.788, chance
0.20, exact one-sided binomial p ≈ 7e-6. By stratum (4 questions each): transversal 3/4, low confidence **1/4**,
long tail 3/4, large 2/4, medium 3/4, small 3/4. Across all 24 questions, topics in the bottom quartile of
cohesion (mean member cosine to centroid) scored 1/7, the others 14/17.

**Why it is exploratory, not validated:** with one rater we cannot tell an incoherent topic from one person's
judgement, cannot estimate rater noise, and 24 answers give a wide interval. The reviewer's machine also held the
(unopened) answer key file. **This result must not be described as validated by three reviewers.**

**Where files belong:** shareable = `summary_single_reviewer.md`, `evaluation.json`, `manifest.json`,
`questions.json` (tracked). Private (gitignored) = `private/` (full score JSON, per-question report, diagnostics),
`scores/` (legacy score output), `responses/`, `submitted/`, and the key in `data/interim/`.
Reproduce: `python src/intrusion_v2.py status` (mode + completion) and `python src/intrusion_v2.py score`
(writes a new private score + refuses to overwrite the summary).

### Running a future independent three-reviewer evaluation

1. Generate a **new** question set (new run folder or new seed) so nobody has seen the questions or this result;
   the key must be generated and held by someone who is **not** a reviewer.
2. Do **not** create `evaluation.json` (absent = `three_reviewer`). Each reviewer answers alone in the page and
   submits; nobody discusses questions or opens `private/` / `scores/` until all three submitted.
3. The scorer runs `python src/intrusion_v2.py score`; it refuses until all three submitted, then reports accuracy
   and agreement. `--allow-partial` exists only for a progress check and is marked PARTIAL, never final.

## For each reviewer: web page (recommended, since 2026-11-02)

1. Start the dashboard: `.venv/bin/python app/server.py` → open `http://127.0.0.1:8765/validation`
   (*Skill Pipeline — Intrusion v2*). It needs no Supabase; sign in first if `UI_PASSWORD` is set.
2. Choose **your own** name. One question at a time; pick the skill that does not belong (A–E, or keys A–E).
   Every choice is saved to your `responses/<you>.csv` at once ("Saved" appears only after the server wrote
   the file and read it back). Close the page any time; it resumes at your first unanswered question.
3. The summary shows answered / unanswered. **Submit final answers** (after a confirmation) runs the same lock
   as `python src/intrusion_v2.py submit` and writes `submitted/<you>.json`; your answers can no longer change.
4. Then hand in as in step 6 below. No score is shown anywhere on the page.

Code: `app/intrusion_api.py` (endpoints `/api/intrusion-v2/questions|responses|progress|team|answer|submit`),
`app/static/intrusion_v2.*`, tests `tests/intrusion_v2/test_intrusion_frontend.py`. The API never opens the answer
key and sends only question ids + option texts. **The name dropdown is not a login**: anyone who can open the page
can pick any name. Keep the server on 127.0.0.1 (the default) or set `UI_PASSWORD` before sharing it.

## For each reviewer: CSV by hand (alternative)

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

## Scoring under the original three-reviewer protocol (one person, after all three pushed)

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
