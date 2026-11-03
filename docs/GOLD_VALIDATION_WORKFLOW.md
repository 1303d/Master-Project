# Gold validation — three-part review (Section B)

**Page not served at the moment (2026-11-02):** `/validation` now shows the Intrusion v2 review
(`docs/INTRUSION_TEST_V2.md`). The Gold Validation API (`/api/validation/*`), its page files
(`app/static/validation.*`), CLI, tests and data are unchanged; re-mount the page in `app/server.py` to use it.
Code: `src/validation/` (backend), `app/validation_api.py` + `app/static/validation.*` (page),
`tests/validation/` (synthetic tests). Config: `data/validation/config/validation_config.yaml`.

## What each part does

| Part | Question | Source | Reviewer sees |
|---|---|---|---|
| 1 Disagreements | Model and gold differ — who is right? | `reports/errors_qwen_qwen3.8-27b_v2_dev.csv` + `_v3_dev.csv` vs gold v1 | posting, label, type (model-only / gold-only), runs |
| 2 Agreements (blind) | Model and gold agree — are both right? | gold labels matched by Qwen v3 (dev), random 25 % (seed 20261102) | posting + candidate label only |
| 3 Full postings | What did both miss? | 12 random dev postings (seed 31102026) | posting text + empty form |
| Team adjudication | Which proposals become gold changes? | submitted reviews | all reviews (Parts 2–3 only after you submitted that item) |

Current samples (`data/validation/manifests/`): **part1_v2 = 393 items** (206 model-only, 187 gold-only),
**part2_v2 = 121 of 483 agreements**, **part3_v2 = 12 postings**, all from 48 eligible dev postings. v2 (2026-11-02)
was built because `LABELING_RULES.md` gained the HIPAA rule; it has exactly the same items as v1 (same sources and
seeds), and Part 3 now also records each posting's text hash. v1 is kept unchanged; no reviews exist on it.

**Why 393 and not 437:** the earlier audit sheet (`reports/audit_dev_key.csv`) also counted the two protected
agreement postings (44 rows together). On the 48 eligible postings, 375 items are identical; the 18 that differ
each way sit in postings 76, 80, 96 (re-reviewed in gold on 2026-10-21, after the old sheet was made), 69 and 12.

## Protection rules (enforced in code)

- Only `split = dev` postings are eligible. Test, unknown-split and duplicate postings are dropped row by row.
- Agreement postings **#44 and #47** (`protected_postings_n`) are never sampled, shown, compared or reported.
- Posting text is served only for postings inside an active manifest.
- Part 2: the page never receives where a label came from; `/reveal` returns it only after you submitted.
  `data/validation/manifests/part2_v<K>_key.json` holds the key — **do not open it before you finish Part 2.**
  Key files are **gitignored**: they stay on the machine that built the manifests.
- **Official result = blind result.** Seeing an answer (`/reveal`, `/compare`, or an unredacted Part 2–3
  adjudication case) is logged as a `reveal` event in your file. An amendment made after that is kept and shown
  ("after reveal") but never changes the reported counts or the adjudication cases: those use the last version
  you submitted before your first reveal of that item. The page asks for confirmation before revealing.
- Part 3: gold labels and model output are returned only after you submitted that posting. No AI suggestions.
- Gold files are never written. APPROVED only records a decision.

## Daily workflow (each teammate)

1. **Pull:** `git pull` (on the team branch).
2. **Check artifacts:** `python src/validation/cli.py status`. Posting text is *not* in Git: copy
   `gold_postings_dev.csv` from the team Drive into `data/gold/` (gitignored). Without it the page shows
   "Posting text is not on this machine" and Part 3 cannot be submitted.
3. **Start the dashboard:** `source .venv/bin/activate` then `python app/server.py` →
   open `http://127.0.0.1:8765/validation`.
4. **Choose your name** (top right). The dropdown is not a login: the server only listens on 127.0.0.1.
5. **Review.** *Save draft* keeps work in progress (resume later). *Submit* locks the review; a later change is
   an *amendment* (new version, reason required, the original stays).
   - Part 1: KEEP_GOLD / ADD_TO_GOLD / REMOVE_FROM_GOLD / REVISE_GOLD / UNSURE — changes need a rule + reason.
   - Part 2: VALID_SKILL / INVALID_SKILL / NEEDS_REVISION / UNSURE — invalid / revision need an explanation.
   - Part 3: one row per skill: name, exact evidence (must occur in the posting), confidence, notes.
6. **Your file:** decisions go to `data/validation/reviews/<you>/events.jsonl` (append-only, one line per event).
   It is **gitignored** (2026-11-02): a pushed review file would let a teammate read your Part 2–3 answers before
   giving their own.
7. **Hand in once, when you have submitted every Part 2 and Part 3 item** (Part 1 is not blind, but it shares the
   file): `git add -f data/validation/reviews/<you>/events.jsonl` (`-f` because the file is ignored, on purpose),
   `git commit -m "Gold validation: <you> reviews"`, push to the team branch, merge through the normal PR workflow.
8. **Adjudication** starts after all three have handed in: **pull**, and the page shows everyone's reviews.

Because each person writes only their own file, hand-ins do not conflict. If a log line is broken (e.g. an
unresolved merge), the page lists it instead of hiding it.

## Adjudication and the approved version

Cases appear when a submitted review proposes a change, is UNSURE / ambiguous, or reviewers disagree.
Statuses: PENDING → IN_REVIEW (draft) → SUBMITTED → APPROVED / REJECTED / NEEDS_DISCUSSION. If two
adjudicators' latest decisions differ, the case is NEEDS_DISCUSSION. Every adjudication needs a rationale
and goes to `data/validation/adjudication/<adjudicator>.jsonl`.

Gold changes are a separate, explicit step (run once the team agrees):

    python src/validation/cli.py approve-version --name gold_v1_validation_1

This writes `data/validation/approved_versions/<name>/changes.csv` + `manifest.json` (never overwritten).
It does **not** edit `gold_labels.csv`. Building a new gold file from the change set is a later, reviewed step;
the protected postings 44/47 must be handled after the agreement exercise.

## Sources and versions

Each manifest stores the SHA-256 of its sources (gold, split, error files, reports), of the labelling rules
(`rules.sha256`; a rules change also makes a manifest stale since 2026-11-02) and a hash of its settings.
If a source changes, the page warns and reviews stay tied to the old manifest. After the team agrees:

    python src/validation/cli.py build --new-version   # writes part<N>_v<K+1>; old manifests and reviews are kept

Reviews from different manifests are never combined.

## Reports

*Progress & Reports* → *Export report*, or `python src/validation/cli.py report` →
`reports/validation/validation_progress_<UTC time>.md` + `.json` (new files each time). Proposals are reported
as proposals, not as confirmed gold errors.

## Tests

    python -m pytest tests/validation -q

Python 3.11 `.venv` with `requirements.txt` + pytest (set up 2026-11-02).

## Known limits

- The tab is named "Agreements", so a reviewer knows Part 2 items are agreements; the page hides *which run*
  and the gold status, not the category.
- Reviewers can still open the gold CSV or the Part 2 key file directly on the machine that has them; blindness
  relies on not doing that. The reviewer dropdown is not a login, so a reviewer could act under another name.
- Reveal logging only covers what this page shows; reading files directly is not logged.
- Part 1/2 are built from the evaluate.py error files (lenient matching), not from raw predictions
  (`data/processed/` is not in Git). Postings a run did not score are excluded from Part 2.
- Part 3 "conflict" detection is per candidate: a reviewer who did not list a skill does not count as disagreeing.
