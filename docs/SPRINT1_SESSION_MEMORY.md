# Sprint 1 session memory (data collection, Sep 24–25, 2026)

Carry-over notes from the Sprint 1 Claude Code session that worked in the **old folder
`C:\Master's Project`** (with a space). Read with `docs/HANDOFF.md`, which is the main state file.

> ⚠️ **Superseded decision.** That session collected a **2026-only** corpus. On 2026-10-07 the team chose
> **Kaggle `arshkon/linkedin-job-postings` (2024)** as the final corpus, and the "2026 only" rule was dropped.
> Use the old ETL only as an optional extra (e.g. checking emerging/AI skills), not as the main corpus.

---

## 1. Brief requirements that matter for Sprint 3 (from `Taxonomy_of_Work_Capstone_Project_Description_1.pdf`)

**Sprint 3 = Representation & Clustering (weeks 5–6).** Sample tasks:
- Choose a representation (e.g. sentence embeddings) and **store it in the shared database**.
- Fit a clustering method (BERTopic, HDBSCAN, k-means, agglomerative) and **compare at least two**.
- Run a **parameter sweep** and report **cluster stability**.
- Decide if a statement can belong to **more than one topic**, and implement that.
- **Deliverable:** `topics` + `topic_membership` tables, and a stability report with the chosen parameters.

**Sprint 4 (next):** name every leaf topic, build parent levels (more than 2 levels), and evaluate leaf topics
against ESCO/Lightcast (coverage, purity, nearest-neighbour agreement).

**Data contract (minimum):**
| Entity | Must capture |
|---|---|
| Postings | stable ID, source, raw text |
| Statements | one row per skill/task statement, linked to its posting, `kind` = task \| skill |
| **Topics** | leaf topics: name, description, size, **a representation comparable across groups** |
| **Topic membership** | statement ↔ topic, optional strength score |
| Hierarchy | parent–child relations, more than 2 levels |
| Task–skill map | task topic ↔ skill topic, score + evidence |

**Grading (100):** sprint deliverables 35 (~5 each) · final demo 25 · taxonomy quality 15 · code quality 10 ·
**Claude Code usage 15 (keep a log of prompts that worked)**.

**LLM rules:** free tiers only (Gemini default, GitHub Models, Groq/OpenRouter, Ollama). Use a small
provider-agnostic wrapper, cache every response to disk, log token counts per sprint, keys only in env vars.

**Sources rule:** no scraping LinkedIn/Glassdoor or any site whose terms prohibit it. Published datasets and
official APIs only. If unsure, ask the instructor.

---

## 2. ESCO findings (useful for Sprint 3–4 evaluation)

Pulled all ESCO skills from the official API (`api_tests/test_esco_api.py` in the old folder →
`C:\Master's Project\data\reference\esco\esco_skills_api.json`). Copy that JSON if you need it.

| Check | Result |
|---|---|
| Skills (API, current release; latest listed v1.2.1) | **13,485 unique URIs**, 0 duplicates, 0 missing English labels |
| Skill types | skill/competence 10,583 · knowledge 2,903 (1 skill has both) |
| Reuse levels | sector-specific 6,412 · cross-sector 3,643 · occupation-specific 2,977 · transversal 453 |
| Hierarchy | 402 parent groups; 5,136 skills sit under a broader skill |
| Label matches | data 179 · engineering 70 · **AI/ML only 3** |

- Team B's slide used the **v1.2.0 CSV: 14,579** "unique skill URIs". Don't mix the two counts without explaining
  the version difference.
- **"Only 3 AI/ML skills"** means ESCO under-covers AI. Expect many AI/data skill clusters with no good ESCO
  match. Report them as "emerging / not in ESCO", and use Lightcast as the coverage check.
- **ESCO API quirks:**
  1. `offset` is a **page number**, not a record position.
  2. `full=true` gives **HTTP 500** on pages with a skill that has two skill types. Use `full=false`
     (still has skill type, reuse level, broader concept; no description or alt labels).
  3. The CSV download is only sent by **email link** (esco.ec.europa.eu/en/use-esco/download).

---

## 3. Old 2026 ETL (folder `C:\Master's Project`)

Built and tested; it still works if you ever need fresh 2026 postings.

```
cd "C:\Master's Project"
venv\Scripts\Activate.ps1                          # project venv (Python 3.11)
python -m pipeline.run                              # daily: last 2 days, all sources
python -m pipeline.run --since 2026-04-01 --sources usajobs --usajobs-focus
```
- Files: `pipeline/run.py` (CLI), `pipeline/sources.py` (one fetcher per source), `pipeline/store.py` (SQLite).
- Output: `data/postings.db`, table `postings`, key (source, native_id). Columns include `description`
  (plain text) and `raw_text` (original markup). Re-runs never duplicate rows.
- Sources (all **US-only**, no keys): `usajobs` (Historic JOA API), `ats` (Greenhouse/Lever/Ashby),
  `hn` (HN "Who is hiring?"), `smartrecruiters`, `nyc` (NYC Jobs open data), `himalayas`.
- Docs in that folder: `data/findings.md` (all numbers), `data/sources_research.md` (source checks, legal notes),
  `data/schema.md`, `docs/sprint1_slides_content.md` (Sprint 1 slides).

**Database state when the session ended:** ats 1,941 · hn 1,576 · smartrecruiters 2,191 · nyc 1,446 ·
himalayas 4,357 · usajobs 469 (data/AI/ML roles, Apr–Sep 2026; 23 of these are unpaid "Semester of Service"
volunteer projects, which the slide excluded → 446 paid).

**USAJobs lessons (important if anyone uses USAJobs data):**
- The Historic API counts **job announcements (JOAs), not unique jobs**. 2026 had ~191k announcements:
  ~7% repeat the same job (public + internal versions), ~64% are not open to the public, ~12% get canceled.
- **Fake postings exist:** "This is a test announcement…" and OPM's **"Testing USA Hire batteries"**
  (titles like "REQ200-Codility…", even "1560 Data Science"). Filter on both phrases.
- Teammate's USAJobs pilot (`Lochan9/taxonomy-skill`, 25 rows): ~15 are general analyst roles, 2 are in
  Germany. Its **split text columns** (duties / qualifications / requirements / education) are a good design.

---

## 4. Environment gotchas

- `python` on PATH points to the **hermes-agent venv**. Use `py` (or the old project's `venv`).
- `markitdown` (reads .pptx/.pdf/.docx) is installed in system Python 3.11: run `markitdown <file>`.
- Old folder has `.vscode/settings.json` pointing VS Code at its `venv`.

---

## 5. Open items carried over

- Ask the instructor: **reference implementation** of the framework (brief p.8 mentions one), and whether the
  university licenses **Lightcast** (free Lightcast is capped/nonprofit-only since April 2026).
- Start / keep the **prompt log** (15 points for Claude Code usage).
- Team B already has a shared **Supabase (Postgres)** schema with all contract tables
  (`sql/001_create_shared_schema.sql`). Sprint 3 `topics` and `topic_membership` should go there, so the
  Sprint 5 join with Section A works.
