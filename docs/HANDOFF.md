# HANDOFF — Section B Skill Taxonomy (Sprint 2)

## ▶ CURRENT STATUS (2026-10-20) — extractor optimisation before Sprint 3 (read this first)
Sprint 2 is done (see README). Now improving the extractor before the 2,000-posting run.
- Gold split 50/50: `data/gold/gold_split.csv`, `gold_postings_dev.csv` / `_test.csv` (`src/make_gold_split.py`).
  **Test half is untouched** — score it once, after everything is frozen.
- New CLI: `extract_skills.py --postings --tag --prompt --examples K`; `evaluate.py --tag --split dev|test`
  (also writes `reports/errors_<tag>_<split>.csv`); `src/list_recall.py` (recall on list items).
- Dev results (lenient P/R/F1 · list-item recall): v1 .68/.77/.72 · v2 .75/.72/.74 · v2+kNN-examples .75/.72/.74
  (+72% tokens → dropped) · **v3 .72/.75/.74, list recall .83** (working prompt). Strict F1 .63/.65/.65/.65.
- Human-vs-human agreement (3 postings only): strict .63, lenient .73.
- Labeling rules A–D added to `data/gold/LABELING_RULES.md` (still marked PROPOSED → team confirms → AGREED).
- Audit: `data/gold/AUDIT_CHECKLIST.md`, blind sheet `reports/audit_dev_blind.csv` (437 items), hidden key
  `reports/audit_dev_key.csv`.
- Agreed sequence: rules AGREED → blind gold audit (dev + test, same rules) → gold_labels_v2.csv →
  alias table (from dev errors only) + alias-adjusted F1 → prompt v4 mirrors agreed rules → re-score on dev
  (gold v1 and v2) → freeze prompt/aliases/scorer → score test once → run 2,000 postings
  (`data/processed/extraction_sample_2000.csv`, `src/make_extraction_sample.py`) → Supabase.
- Report: strict F1, alias-adjusted F1, list-item recall; pre- and post-audit scores.
- Waiting on user: team confirms rules, fills blind sheet, creates Supabase project (`SUPABASE_DB_URL` in `.env`).
- Nightly pipeline idea (extract → ESCO/O*NET linking → Supabase) agreed in principle; no Google search
  (cost, ToS, not reproducible).

### Update 2026-10-20 (later) — model comparison, extractor chosen
- Papers in `data/gold/reference/` read (SkillSpan, Rethinking SE, SKORE, GoLLIE). Prompt v4 (rules A–D +
  paper ideas) = no gain (dev strict .63 / lenient .73) → **v3 stays frozen**.
- Dev, prompt v3 (strict F1 / lenient F1 / list recall): Qwen 27B (Groq) .65/.74/.83 · gpt-oss-120b .59/.71/.84 ·
  Nemotron 3 Ultra 550B (OpenRouter free) .51/.60 · **Claude Haiku 5.5 .65/.75/.86**. Gemini 3.8 Flash free tier
  stopped at 20/50 (daily cap). Gemma 4 31B free: upstream 429s.
- Bias check (`src/bias_check.py`): dev gold = 55% kept from the Claude draft, 45% human-added. Haiku recall
  kept .83 vs Qwen .73, human-added .79 vs .78 → Haiku's gain is drafter bias. Report human-added recall as the fair number.
- **Chosen for the 2,000 run: Claude Haiku 5.5 + v3** (class Anthropic key, ~$2; no rate limits).
  Output `statements_claude-haiku-5-5_sample2000.csv`, log `reports/extract_sample2000_haiku.log`.
  **Done 2026-10-20:** 2,000/2,000 postings, 0 failures, 28,834 statements, 11,410 unique skills (lowercase),
  71 postings with zero skills, evidence verbatim 99.2%, tokens 4.74M in / 2.53M out (≈ $1.74).
  **Test (gold v1, scored once):** Haiku strict .66 / lenient .75 (P .72 R .78); Qwen strict .66 / lenient .75.
  Test bias check: recall kept/human-added — Haiku .79/.80, Qwen .77/.75 (no drafter bias visible on test).
- **Rule E (LABELING_RULES.md): ESCO + O\*NET are the rule book** for skill vs trait. Traits = O\*NET Work
  Styles + ESCO's 18 transversal attitudes (incl. attention to detail). Reference data: `src/download_reference.py`
  → `data/reference/` (ESCO 13,479 skills, 443 attitude-group items, 6 O\*NET 31.0 files).
- New providers in `extract_skills.py`: `openrouter`, `anthropic`. `py` currently lacks pandas → use
  `C:\Users\dhanu\AppData\Local\Programs\Python\Python311\python.exe`.

- **Reference linking built (`src/link_reference.py`)** → `data/processed/skill_links.csv` (12,875 unique skills).
  Exact match, then bge-small cosine ≥ 0.85 (skills) / ≥ 0.88 (traits; lower gave wrong traits such as
  "change control" → "adapt to change"). Sample2000: known_skill 69% · trait 2% · new_candidate 29%.
  New candidates are often real US skills missing from both libraries (month-end close, journal entries, GAAP,
  CI/CD, OSHA, KPIs) → keep them, human review. `--write-gold-v2` → `data/gold/gold_labels_v2.csv`
  (20 trait items removed, column `removed_traits`). `evaluate.py --gold … --links …` scores on v2 with
  predicted traits dropped: F1 unchanged (Haiku dev .65/.75, test .66/.75), since traits are only ~2%.

### ROADMAP (keep this current; the user relies on it)
Target pipeline: postings (Kaggle static + Greenhouse live API) → clean/dedupe → LLM extractor →
ESCO/O\*NET check → unknown skills to human review → processing → Supabase.
**Rule (2026-10-20): the professor's Anthropic key is NOT used in the pipeline** (research / Claude Code only).
Pipeline extractor = free provider; Groq Qwen 27B + v3 matches Haiku on test (.66 / .75).
**Demo: Friday 2026-10-23, 3 pm** (prototype showcase). Target ≥ 1,000 Kaggle postings extracted by then.
1. ✅ Haiku sample2000 = research data only (CSV, not in Supabase). Qwen batch re-run started 2026-10-20 ~22:30
   on the free Groq tier (`reports/extract_sample2000_qwen.log`, ~30 postings/h; laptop stays on overnight).
2. 🟡 Supabase: code ready — `sql/supabase_schema.sql`, `src/db.py --init/--check`, `src/load_supabase.py`
   (loads postings + skills straight from the Groq cache, so it can run any time). Needs `SUPABASE_DB_URL` in `.env`.
3. ✅ Greenhouse: `src/pipeline.py` (boards from `config/boards.yaml`, copied from Lochan's repo) — fetch → clean →
   dedupe (text_hash, any source) → extract → load → link; every stage writes `pipeline_events`.
4. ✅ `src/llm_router.py`: LiteLLM Router, Groq Qwen → Gemini Flash fallback (tested: fallback worked while Groq
   was rate-limited), Langfuse via `langfuse_otel` when `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST` are set.
   UI: `app/server.py` (stdlib WSGI, http://127.0.0.1:8765) + `app/static/` (Lochan's CSS) — tabs Pipeline status
   (stage flow, active model, fallbacks, verdict bar, Kaggle batch progress, events), Review queue (unknown skills,
   evidence highlighted, decisions → `review_decisions` + `skill_links.review_status = reviewed`), Skills; Langfuse button.
   **2026-10-21:** Supabase loaded (2,453 postings; 29k statements incl. the Haiku 2,000 *research benchmark*,
   statement_id `<posting>:claude-haiku-5-5:skill:<i>`, loaded with `load_supabase.py --benchmark`).
   View **`current_statements`** = one model per posting (Qwen where done, else Haiku; Greenhouse all) —
   embeddings / RAG read ONLY this view; vectors keep the model name so Haiku can be filtered out.
   Windows tasks: `SkillPipeline\LoadQwen` hourly (`scripts/load_qwen.cmd`, `--if-new`, log
   `reports/task_load_qwen.log`), `SkillPipeline\NightlyGreenhouse` 02:00 (`scripts/nightly_greenhouse.cmd`,
   `--max-new 30`, log `reports/task_greenhouse.log`), `SkillPipeline\QwenBatch` daily 02:20 + started
   2026-10-21 02:16 (`scripts/qwen_batch.cmd`, the 2,000 Kaggle batch, resumable, log
   `reports/extract_sample2000_qwen.log`). Remove with `schtasks /delete /tn "SkillPipeline\<name>"`.
   UI is not a task: start it with `python app/server.py` (Python 3.11 path) → http://127.0.0.1:8765.
   Paused 2026-10-21 02:20. **Next: Sprint 3** (embed `current_statements` → 2 clustering methods → sweep →
   stability → topic tables); Langfuse keys still missing; demo rehearsal Thursday evening; demo Fri 3 pm.
   Project end goal (brief): initiative → tasks → skills with supporting postings (not an ATS matcher).
   Explainer: `learn/taxonomy-of-work-project.html`.
5. ⬜ Sprint 3: embed `current_statements` skills (bge-small) → cluster (≥ 2 methods, sweep, stability) → topics tables.
6. ⬜ Report: test scores, bias check, rule E, model comparison, ceiling (human agreement on more postings).

### Plan — reference linking (skill vs trait verdict), Sprint 3
Problem: the LLM decides "skill or trait?" from its own judgement; no shared rule to land on.
1. Download ESCO v1.2 CSV (skills + "attitudes and values") and O\*NET database text files (Skills, Knowledge,
   Technology Skills, Tools Used, **Work Styles** = traits). Store in `data/reference/` (not edited).
2. `src/link_reference.py`: match every extracted skill to these lists — exact/alias first, then embedding
   similarity with `BAAI/bge-small-en-v1.5` (installed).
3. Verdict per skill: `known_skill` (ESCO/O\*NET skill/knowledge/tool, keep ID) · `trait` (O\*NET Work Style /
   ESCO attitude → excluded) · `new_candidate` (no match → **kept**, flagged; humans review frequent ones).
   Never delete unmatched items: ESCO missed ~half of US legal terms, and new skills are what the taxonomy must find.
4. Tune the similarity threshold on dev gold only; freeze; then report bucket shares + precision per bucket on test.
5. The evidence check (skill phrase quoted from the posting, 99% verbatim) stays as the anti-hallucination guard.

Last updated: 2026-10-06 (end of a ~3-day Claude Code session, 2026-10-05 → 2026-10-06).
Summary/conventions: [../CLAUDE.md](../CLAUDE.md). Secrets: only variable names are mentioned here.

**Source session:** `19222a92-5266-4f39-be95-1985d7169a24`
- Transcript: `C:\Users\dhanu\.claude\projects\C--Users-dhanu\19222a92-5266-4f39-be95-1985d7169a24.jsonl` (~3.8 MB)
- Resume (run from `C:\Users\dhanu`): `claude --resume 19222a92-5266-4f39-be95-1985d7169a24`
- If this file lacks a detail, **search** the transcript instead of reading it whole, e.g.
  `grep -o '.\{150\}mineral deposits.\{150\}' <transcript> | head -3` (tested: works; plain keyword + context)

---

## 1. Current status at a glance

| Item | Status |
|---|---|
| Raw data downloaded (Kaggle LinkedIn) | ✅ `data/raw/linkedin/` |
| Cleaning + tagging | ✅ `data/interim/postings_clean.parquet` (123,849 rows, 106,909 usable) |
| Gold sample (100 postings, 8 sectors) | ✅ `data/gold/gold_labels.csv` |
| Gold labelling | 🟡 **6 / 100** done (all Legal: #1, #8, #17, #18, #47, #56) |
| Legal sector | 🟡 6/8 — #71 shown (awaiting user labels), #94 not shown yet |
| Label cross-check script | ✅ `src/check_gold.py` |
| Final gold set decision (ours vs teammate v2) | 🔴 **Unresolved** |
| Instructor approval for LinkedIn-derived Kaggle data | 🔴 **Not asked yet** (waiting on user/team) |
| Lightcast API | 🔴 **Blocked — waiting on user to register** and put `LIGHTCAST_CLIENT_ID` / `LIGHTCAST_CLIENT_SECRET` in `.env`. `src/lightcast.py` was drafted but **never saved** (session interrupted) |
| ESCO download | ⬜ Not started (only ad-hoc API searches done) |
| Gemini extractor (+ caching, rate limits) | ⬜ Not started (`GEMINI_API_KEY` not set up — UNVERIFIED whether user has one) |
| Scoring script (precision / recall / F1) | ⬜ Not started |
| `statements` table | ⬜ Not started |
| Quality report | ⬜ Not started |
| Git repo | ⬜ Folder is not a git repository |

---

## 2. Chronological summary

### 2026-10-05
1. **User profile** created at `~/.claude/CLAUDE.md` (beginner, short STE-style replies, HTML lessons in `learn/`).
2. Created `C:\Master's-project`. User shared the capstone brief PDF; user is in **Section B (skills)**,
   team of 3, starting at **Sprint 2** with ~4 days.
3. Wrote `learn/skill-taxonomy-project.html` (big picture, pipeline, Sprint 2, P/R widget, quiz).
4. Clarified Sprint 2 with the user: extraction runs on **all** postings; gold set = **100 postings
   labelled by humans**; no screenshots (text already available); ESCO cannot be a gold set.
5. **Dataset #1 considered:** HF `abigailhaddad/usajobs-scraping` — 3,244,472 rows, 10.7 GB parquet,
   no skills column; useful fields `qualificationSummary`, `requirements`, `howYouWillBeEvaluated`;
   `majorDuties` = tasks. Sample rows contained HR templates ("[Insert Duties]").
6. Reviewed 3 papers the user found:
   - Zhang et al. 2022, *Skill Extraction from Job Postings using Weak Supervision* (arXiv 2209.08071) → ESCO-embedding matcher idea.
   - Myronenko & Pylieva 2024 (UCU) → GPT-4 ≈ 46% F1 on SkillSpan skills, fine-tuned BERT ≈ 52%; exact-match scoring is strict.
   - Springer 2024, *Comparative Analysis of LLMs in Structured Information Extraction from Job Postings* (Greek tourism postings).
7. Published a Sprint 2 plan artifact (https://claude.ai/artifact/EsqJbZ1ojnuYZ4NMA2dnSo) — teammates got
   "page not found" (private link), so exported `docs/sprint2-plan.pdf` + `docs/sprint2-plan-full.html`.
   ⚠️ This plan describes the **USAJOBS** dataset and is now outdated.

### 2026-10-06
8. **Dataset #2 considered:** HF `will4381/job-posting-classification` (33,233 rows, 164 MB). Rejected as
   gold: `relevant_skills` generated by GPT-4o-mini (card admits hallucinations); LinkedIn-derived.
9. Discussed human-labelled gold sets (SkillSpan `jjzha/skillspan`, `jjzha/green`, TechWolf
   `skill-extraction-tech/house`) — **user wants US-only**, and these are EU/UK, so not used.
10. Tested **Greenhouse job board API** (no key): Airbnb 151, Stripe 718, GitLab 210 jobs, full text.
    Kept as fallback source.
11. **Dataset #3 chosen:** Kaggle `arshkon/linkedin-job-postings`. Created project structure,
    `download_data.py` (kagglehub, no login needed), downloaded 159 MB zip.
12. Profiled `postings.csv`: 123,849 rows, 7 missing descriptions, 16,021 duplicate descriptions (raw
    count; 16,320 after normalisation), median 3,435 chars, dates 2024-03-24 → 2024-04-20, 35 skill
    categories only, 387 industries, 53 states (CA 10,318, TX 8,617, NY 5,440…), 7,520 location = "United States".
13. User asked for alternatives to dropping → decided **tag, don't drop**; embed unique texts only.
    Wrote/ran `clean_postings.py`.
14. Wrote `LABELING_RULES.md` and `gold_example.xlsx` (3 worked examples: QA Tester, Senior Accountant,
    Associate Attorney).
15. Explained gold set is per posting (≈100 postings × 10–20 skills ≈ 1–2k labels, repeats allowed).
    User proposed per-sector unique lists; explained why that cannot measure recall; suggested per-sector scores instead.
16. Agreed **8 sectors + Mixed** split; rewrote `make_gold_sample.py` (stratified) and built `gold_tool.py`.
17. Teammate's `gold_draft.xlsx` (v1) reviewed: 100 unique, same quotas, but 9 duplicate ids, 17 emails /
    8 phones in text, 8/15 "IT" rows not IT, `final_skills` = draft in all rows. Copied to
    `data/gold/reference/teammate_gold_draft.xlsx`.
18. Investigated sector noise: teammate's script picked *any* IT tag; ours uses first tag, but some postings
    have a **single wrong tag** (Attorney, Statistician, Writer, Sales Technician as IT). Added `sector_fixed`.
19. Teammate's **v2** (`C:\Users\dhanu\Downloads\gold_draft_v2.csv` — ⚠️ **not copied into the repo**):
    PII masked ✅, labeled_by/notes ✅, levels rebalanced (23 blank), but 9 duplicate ids and ~10 wrong
    sectors remain (Packaging Associate/Kitting Team Lead/Audit Manager in IT; Parking Attendant/SRE in
    Finance; Ob/Gyn chair, Exec Compensation, BCBA in Sales).
20. Labelled Legal postings with the user one by one (full text shown, Claude suggests, user decides).
21. Priyanka's 50 labels (`data/gold/reference/golden-set-priyanka.txt`, on v2 postings): **~44/50 identical
    to the Claude draft**, grouped items (e.g. `databases (Oracle, Sybase)`), a duplicate item
    (`lead generation` twice), a garbled item (`Cybersecurity Frameworks Data`). She did fix several sectors.
22. User (not from law) worried about mistakes → wrote `check_gold.py`. Findings: missing *personal injury
    / general litigation* (#18), *depositions, court appearances* (#47), *immigration law, visa types, EOIR*
    (#56); `written communication` not in text for #18/#56.
23. Discussed a "top-500 skills" glossary → recommended an **open alias vocabulary linked to ESCO +
    Lightcast**, labels never restricted. Wrote `learn/skill-vocabulary-plan.html` (8 steps).
24. ESCO API test on 16 legal terms → ~half fail (see CLAUDE.md). Explained Lightcast (categories,
    extraction API, "two machines vote" pre-fill idea: Claude draft + Lightcast agree → quick accept;
    disagree → human checks). User decided to **set up Lightcast**; `.env.example` and requirements were
    updated; `src/lightcast.py` write was interrupted.

---

## 3. Gold labels done (in `data/gold/gold_labels.csv`, labeled_by = Dhanush)

| n | Title | Notes / pending fixes |
|---|---|---|
| 1 | Family Law Paralegal (Houston) | Done. Dropped my suggestions: interpersonal skills, customer service |
| 8 | IP Staff Scientist / Patent Agent (Boston) | "IP analysis" → `IP due diligence` (posting wording) |
| 17 | Legal Coordinator (Ryan Specialty) | Uses `Microsoft Office` umbrella — **app-listing rule undecided** |
| 18 | Legal Assistant (Randstad/Hanover) | Pending: add *personal injury litigation*, *general litigation*; `workflow adaptation` overlaps `adaptability` |
| 47 | Litigation Attorney (Marks O'Neill, Pittsburgh) | Pending: add *depositions*, *court appearances* (+ maybe practice areas) |
| 56 | Associate Immigration Attorney (Hirewell) | Pending: add *immigration law* (+ maybe visa types / EOIR); trait-like items |
| 71 | Health Care Litigation Attorney (LHH) | Shown; my suggestion `litigation; health care law; trial advocacy`. **Awaiting user** |
| 94 | Mid-Level Attorney (Doyle Dennis) | Not shown yet |
| 2 | Business Development Manager (EcoFlow) | Shown, skipped (Sales) — not saved |

---

## 4. Next steps (priority order)
1. **Decide the single final gold set**: ours (`gold_labels.csv`, 6 done) or teammate v2 (50 labelled but
   mostly copied drafts). Recommendation given: v2 if her 50 get a real review; otherwise ours.
2. **Ask the instructor**: is LinkedIn-derived Kaggle data OK? Is LLM-assisted (human-corrected) labelling OK?
3. Apply pending fixes to #18, #47, #56; decide the app-listing rule; label #71, #94.
4. Split remaining postings ~33 each; run `check_gold.py` after each batch.
5. Register for Lightcast → keys in `.env` → recreate `src/lightcast.py` (token via
   `https://auth.emsicloud.com/connect/token`, scope `emsi_open`; skills/extract under
   `https://emsiservices.com/skills/versions/latest` — UNVERIFIED endpoints, from memory) with disk cache.
6. Build Gemini extractor (provider-agnostic wrapper, disk cache, retry on 429, token logging) on the 100
   gold postings + a sample (~2–5k unique postings).
7. Scoring script: normalised names (lowercase, filler removal, alias table), exact + fuzzy match, P/R/F1,
   per `sector_fixed`.
8. Write `statements` table (posting_id, kind='skill', text, method) and the quality report (method,
   scores, prompts, token usage, labelling process, sector-noise finding).
9. Optional: ESCO CSV download + alias vocabulary (`learn/skill-vocabulary-plan.html`).
10. Housekeeping: `git init`, start `docs/prompt_log.md` (counts toward Claude Code usage points).

## 5. Open questions / unresolved decisions
- Final gold set: ours vs v2? Whose labels count?
- **Corpus date conflict:** older folder `C:\Master's Project\CLAUDE.md` (Sprint 1 work, 2026-09-24) says the
  corpus must be **Jan–Sep 2026** postings with an ETL in `pipeline/` (SQLite `data/postings.db`, USAJobs
  Historic, ATS boards, HN). This session uses **2024** Kaggle data. Which is the team's Sprint 2 corpus? (UNVERIFIED)
- **Lightcast access:** the older CLAUDE.md says that, since an April 2026 policy change, free self-serve
  access is nonprofit-only and capped (~50 extractions/month). If true, bulk extraction / "two machines vote"
  is not feasible; downloading the skill list may still be. (UNVERIFIED)
- App rule: list each app (Word, Excel…) vs `Microsoft Office` umbrella (recommended: list each app).
- Visa types / practice areas: separate skills or one umbrella item?
- Data contract with Section A (statements schema) not agreed yet.
- `GEMINI_API_KEY`: does the user/team have one? (UNVERIFIED)

## 6. Important numbers & paths
- Postings 123,849 · duplicates 16,320 · missing 7 · short 636 · usable 106,909.
- Gold: 100 postings, seed 42, 300–5000 chars; quotas in CLAUDE.md.
- Functions (primary tag share): Management 13.6%, Health Care 13.5%, Other 10.2%, Engineering 9.1%,
  Sales 8.8%, IT 8.6%. Experience levels (usable): Mid-Senior 35,772, Entry 29,903, not listed 26,844,
  Associate 8,694, Director 3,309, Internship 1,288, Executive 1,099. 69,061 unique titles.
- Files outside the repo: `C:\Users\dhanu\Downloads\gold_draft_v2.csv` (teammate v2), old project
  `C:\Master's Project\`, user profile `~/.claude/CLAUDE.md`, old memory
  `~/.claude/projects/C--Users-dhanu/memory/masters-capstone-project.md` (partly outdated).

## 7. Memory vs repo discrepancies found while writing this
- `src/lightcast.py` does not exist (planned in chat, write interrupted).
- No `.env` file exists yet (only `.env.example` with variable names).
- `docs/sprint2-plan.*` still describe USAJOBS, not the Kaggle dataset now in use.
- `README.md` setup is correct but does not mention the gold tools.
- Teammate v2 file was analysed in chat but never copied into `data/gold/reference/`.
