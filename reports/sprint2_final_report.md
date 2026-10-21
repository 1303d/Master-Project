# Sprint 2 — Final report: skill extraction (Section B)

*Taxonomy of Work capstone, Section B (skill taxonomy). Final version 2026-10-21. It replaces the earlier
per-run reports in `reports/sprint2_extraction_quality_*.md`, which stay as the detailed evidence.*

## 1. Summary

- **Deliverable 1, statements table:** Supabase table `skill_statements` and the shared-contract view
  `statements` (`kind = 'skill'`). It holds 28,834 statements from 2,000 Kaggle postings (the Claude Haiku
  research benchmark). It also holds a growing set from the pipeline extractor: Qwen, 957 statements from
  84 postings on 2026-10-21. Every check in `src/verify_db.py` passes.
- **Deliverable 2, quality:** on the held-out **test half** of the gold set (50 postings, 649 gold skills), the
  pipeline extractor scores **strict F1 0.66 and lenient F1 0.74** (Qwen3.8 27B, prompt v3). Two humans agreed
  at lenient F1 0.73 on the 3 double-labelled postings, so the extractor is at about the level of the labels.
- **Deliverable 3, tokens:** 2,630 API calls, 5.70 M input and 3.18 M output tokens across all experiments
  (§7). The pipeline extractor runs on free tiers: $0.

## 2. Data

- Corpus: Kaggle `arshkon/linkedin-job-postings`, with 123,849 US postings from 2024-03-24 to 2024-04-20.
  Of these, 106,909 are usable after tagging duplicates, short and missing texts (`src/clean_postings.py`).
  Nothing is deleted; the rows are only flagged.
- Extraction sample: 2,000 usable postings outside the gold set (`src/make_extraction_sample.py`).
- Live feed: Greenhouse Job Board API, 5 boards (`config/boards.yaml`). 453 postings were stored on
  2026-10-21, and their extraction runs as a nightly queue.
- Contacts are masked before text is shared. Two maskers exist, and both are kept so the existing texts
  stay the same:
  - The gold set (`src/make_gold_postings.py`) masks US phone numbers only. It reproduces
    `gold_postings.csv` exactly.
  - The sample and Greenhouse use `gold_tool.hide_contacts`, which is broader and also masks some dates as
    phone numbers. This is a known limitation, and it is not changed, because LLM caches are keyed on the text.

## 3. Gold set

| Item | Value |
|---|---|
| Postings / gold skills | 100 / 1,333 (gold v1, `data/gold/gold_labels.csv`; was 1,317 before the 2026-10-21 review of 5 postings, §4) |
| Sampling | Stratified by first-listed LinkedIn job function, seed 42, 300–5,000 characters |
| Method | LLM-suggested (Claude / ChatGPT), human-corrected; both lists stored (`suggested_skills`, `gold_skills`) |
| Labellers | Priyanka 55, Lochan 30, Dhanush 15 (incl. postings 37, 76, 80, 84, 96, whose labeller was unrecorded and which Dhanush re-reviewed on 2026-10-21) |
| Sector | `sector_fixed` corrects noisy LinkedIn tags (posting 11 filled 2026-10-21: Health Care, same as its LinkedIn sector) |
| Agreement | 3 double-labelled postings: strict F1 0.63, lenient 0.73 (too few for a reliable ceiling) |
| Rules | `data/gold/LABELING_RULES.md`: base rules + A–D (proposed) + **E: ESCO v1.2 and O\*NET 31.0 decide skill vs trait** |
| Gold v2 | v1 minus 19 items that rule E calls traits (`--write-gold-v2`). **Provisional** until the team confirms rules A–E |

Human edits were large: 44% of dev gold skills (301 of 684) were added by humans, and 78 of 461 LLM
suggestions were dropped. So the gold set is not a copy of the LLM draft.

## 4. Dev / test split, and how the test half was used

`src/make_gold_split.py` splits the 100 postings 50/50, stratified by sector (seed 42).

- **Dev (50)** was used for every design choice: prompts v1 → v4, the semantic-search (kNN) example
  experiment, the scorer normaliser, and the model comparison.
- **Test (50)** was not used to choose prompts, models or rules. It was **not** scored only once, though:
  - a test report for the v1 prompt was produced when the split was made (lenient F1 0.73);
  - after prompt v3 was frozen, test was scored for Qwen (the pipeline model) and for Haiku (the benchmark);
  - test was then scored again on the provisional gold v2.

  None of these scores led to a change in the prompt or the extractor. The ESCO / O\*NET trait threshold
  (0.88) was set by reading library matches, not test scores. But gold v2 was created after test scores had
  been seen, so v2 test numbers are reported as secondary.
- On 2026-10-21, 5 postings whose labeller was unrecorded were re-reviewed by Dhanush against ESCO / O\*NET
  (rule E). 2 of them (#37, #84) are test postings. They were reviewed from the posting text and the libraries
  only, with no model output shown, but after test scores had been seen. Their gold changed (+2 and +5 skills),
  and the Qwen test lenient F1 moved from 0.75 to 0.74. The scores below use the reviewed gold. Earlier documents said the test half was
  "untouched" or "scored once"; that wording was inaccurate and has been corrected.

## 5. Extraction

- Prompt `prompts/skill_extraction_v3.txt` gives:
  - a positive definition of a skill;
  - exclusions (degrees, certifications, licences, years, traits, routine duties, industries, outcomes);
  - an exhaustive scan of lists;
  - an exact evidence quote for every skill.
- Code `src/extract_skills.py` works with any provider (Groq, Gemini, OpenRouter, Anthropic):
  - It caches every answer on disk and retries on rate limits.
  - **Since 2026-10-21:** answers are validated before they are cached. A malformed answer counts as failed
    and is never cached.
  - Every paid call is logged at once (`reports/token_calls.csv`), and the run summary is written even if a
    run stops early. Failed postings are listed (`status = failed`).
- Pipeline router `src/llm_router.py` (LiteLLM) tries Groq Qwen first and falls back to Gemini Flash on rate
  limits. Langfuse tracing is optional.

### Model comparison (prompt v3)

| Model | Dev strict F1 | Dev lenient F1 (P / R) | Test strict / lenient F1 | Role |
|---|---|---|---|---|
| **Qwen3.8 27B** (Groq) | 0.66 | 0.74 (0.73 / 0.75) | **0.66 / 0.74** | pipeline extractor (free) |
| Claude Haiku 5.5 | 0.67 | 0.76 (0.71 / 0.81) | 0.66 / 0.75 | research benchmark, 2,000 postings |
| gpt-oss-120b (Groq) | 0.61 | 0.71 (0.66 / 0.77) | — | over-extracts |
| Gemini 3.5 Flash-Lite | 0.64 | 0.71 (0.83 / 0.62) | — | precise, misses list items |
| Nemotron 3 Ultra 550B (OpenRouter) | 0.52 | 0.61 (0.48 / 0.83), 49/50 postings | — | over-extracts |

Prompt history on dev (Qwen, lenient / strict F1, list-item recall):

- v1: 0.73 / 0.64.
- v2: 0.74 / 0.66, list recall 0.78.
- v2 + kNN examples: 0.74 / 0.67. It used 72% more tokens, so it was dropped.
- **v3: 0.74 / 0.66, list recall 0.82.**
- v4: 0.74 / 0.64, list recall 0.82. It added more rules from the SkillSpan / SKORE / GoLLIE papers, with no gain.

v3 was chosen on the original gold for its list-item recall (then 0.83 vs 0.78 for v2), and that still holds.

## 6. Evaluation method and robustness

- `src/evaluate.py` matches skills one-to-one per posting, after normalising both names (lowercase, filler
  words removed, plural to singular).
  - **Strict:** the normalised names are equal.
  - **Lenient:** the names are equal, or all the words of one appear in the other.
- **Fixed 2026-10-21:** matching was greedy, so the result depended on list order. It now uses a
  **maximum bipartite matching**, which does not depend on order. Every run was re-scored, and **no reported
  number changed** at two decimals. A unit test shows a case where the old greedy method missed a pair
  (`tests/test_core.py`).
- **Coverage is now reported:** each report states how many gold postings were scored and lists any failed
  ones. All runs scored 50/50, except Nemotron at 49/50.
- **Evidence check:** 99.1% of evidence phrases occur verbatim in the posting.
- **Bias check** (`src/bias_check.py`): recall is split into gold skills *kept from the LLM draft* and gold
  skills *added by humans*.
  - On dev, Haiku (a Claude model, the same family as the drafts) gains only on kept skills: 0.83 vs Qwen
    0.72, while added skills are 0.79 vs 0.78. That is drafter bias.
  - On test: Haiku 0.79 / 0.79, Qwen 0.77 / 0.74. Human-added recall is the fair number to compare.
- **Rule E effect:** on gold v2 with predicted traits dropped, the scores are unchanged (test: Qwen
  0.65 / 0.74, Haiku 0.66 / 0.75), because traits are about 2% of items.

## 7. LLM token usage (`reports/token_usage.csv`)

| Model | API calls | Input tokens | Output tokens |
|---|---|---|---|
| Claude Haiku 5.5 (benchmark, 2,000 + dev / test) | 2,100 | 4,977,448 | 2,657,978 |
| Qwen3.8 27B | 353 | 483,806 | 142,296 |
| Nemotron 3 Ultra | 49 | 67,001 | 205,847 |
| gpt-oss-120b | 50 | 69,728 | 79,615 |
| Gemini models (all) | 78 | 99,850 | 96,998 |
| **Total** | **2,630** | **5,697,833** | **3,182,734** |

Two notes on these numbers:

- The running Qwen batch logs its total only when it finishes. It started before per-call logging existed.
- Qwen, Gemini, Nemotron and gpt-oss ran on free tiers. Haiku (about $2) used the course's shared Anthropic
  key for research only; it is not used in the pipeline.

## 8. ESCO / O\*NET linking (rule E)

`src/link_reference.py` gives every unique skill one of three verdicts:

- **known_skill:** it matches an ESCO skill or knowledge item, or an O\*NET Software / Knowledge /
  Essential / Transferable Skill.
- **trait:** it matches an O\*NET Work Style or one of ESCO's 18 transversal attitudes.
- **new_candidate:** no match. These are kept and go to human review.

Matching uses exact names first, then `bge-small-en-v1.5` cosine similarity: at least 0.85 for skills, and at
least 0.88 for traits. On the 2,000-posting benchmark: known 69% · trait 2% · new 29%. Many new candidates
are real US skills that are missing from both libraries, such as GAAP, CI/CD and month-end close.

## 9. Open items (need the team)

1. ✅ Done 2026-10-21: the 5 postings with no recorded labeller were re-reviewed (§4), and posting 11's
   sector was filled. `gold_labels.csv` is the official version; the older `gold_labels priyanka + lochan.xlsx`
   predates Dhanush's re-labelling of postings 45, 71, 92 and 94.
2. Confirm labelling rules A–E, and choose the official gold version (v1 or v2).
3. Resolve flagged annotation disagreements (`reports/audit_dev_blind.csv`, `data/gold/AUDIT_CHECKLIST.md`).
4. Agree the data contract with Section A. Our `posting_id` format differs from the contract's
   `greenhouse:{board}:{id}` (D4). `kind = 'skill'` is provided by the `statements` view.
5. Share posting texts, statements and caches on Drive, and add the link to the README.

## 10. Reproduce

```
py src/make_gold_postings.py                       # gold posting text (identical to the shared file)
py src/make_gold_split.py                          # 50 dev / 50 test
py src/evaluate.py --model qwen/qwen3.8-27b --tag v3 --split test     # strict 0.66 / lenient 0.74
py src/bias_check.py --split test --runs qwen/qwen3.8-27b:v3 claude-haiku-5-5:v3
py -m pytest tests -q                              # 16 tests, incl. reproducing the test score
py src/verify_db.py                                # database contents vs source files
```
