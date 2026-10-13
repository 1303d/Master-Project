# Sprint 2 deck — slide content (reuses the Sprint 1 template)

Numbers are from `reports/sprint2_extraction_quality_qwen_qwen3.8-27b.md` and `data/gold/gold_labels.csv` (2026-10-09).

---

## Slide 1 — Title (reuse slide 1)
- Top label: **SPRINT 2 : TEXT EXTRACTION**
- Title: **TAXONOMY OF WORK**
- Subtitle: **SKILL EXTRACTION & GOLD-SET EVALUATION**
- Footer: GROUP 3 · OCTOBER 9, 2026 · TAXONOMY OF WORK CAPSTONE · NORTHEASTERN × WORKHUMAN

---

## Slide 2 — What we're building (reuse slide 2)
Keep the 3 steps. Mark step 2 as this sprint:
- 1: COLLECT — done in Sprint 1 ✔
- **2: EXTRACT — this sprint:** pull one atomic skill statement per skill from each posting, and measure how good it is
- 3: ORGANIZE — next sprints: cluster, label, build the hierarchy, benchmark vs ESCO / O\*NET

---

## Slide 3 — Sprint 2 goals (reuse slide 3)
1. Choose and justify an extraction approach
2. Hand-label 100 postings as a gold set
3. Measure precision / recall, and log LLM token usage

---

## Slide 4 — Corpus: Kaggle LinkedIn postings
*Title: "One corpus, cleaned — nothing deleted"*

| | Count |
|---|---|
| Postings (Mar–Apr 2024, CC0) | 123,849 |
| Exact duplicate descriptions (tagged) | 16,320 |
| Too short (<200 chars) / missing | 636 / 7 |
| **Usable unique postings** | **106,909** |

- **Tag, don't drop:** every row stays, with flags (`is_duplicate`, `is_short`, `is_usable`).
- **Line breaks kept:** bullets stay readable for labellers and the LLM. Duplicate flags unchanged.
- **Contacts masked:** emails and phone numbers removed before sharing.

---

## Slide 5 — Gold set design
*Title: "100 postings, every sector"*

| Sector | Postings |
|---|---|
| IT | 15 |
| Health Care | 15 |
| Engineering | 12 |
| Finance + Accounting | 12 |
| Sales + Marketing | 12 |
| Management | 10 |
| Legal | 8 |
| Admin / HR / Customer Service | 8 |
| Mixed | 8 |

- Random, stratified by LinkedIn's first-listed job function (seed 42), 300–5,000 characters, usable rows only.
- LinkedIn's sector tags are noisy (an "Attorney" tagged IT), so we added a corrected `sector_fixed`.
- Result: **1,317 gold skills**; 1 posting correctly has **zero** skills.

---

## Slide 6 — What counts as a skill
*Title: "Clear rules before labelling"*

| ✅ Label it | ❌ Don't label it |
|---|---|
| Tools: Excel, Salesforce, Epic, Westlaw | Degrees, licences, certifications |
| Methods: phlebotomy, financial modeling | Years of experience |
| Knowledge: GAAP, HIPAA compliance | Personality traits ("self-starter") |
| Soft skills: written communication | Benefits, company info, EEO text |
| Languages: Spanish | Duties that name no skill ("manage the team") |

- **Duty rule (team decision):** a duty that *names* a skill counts — "build prototypes" → *prototyping*.
- One skill per item, posting wording, no filler words ("strong", "proficiency in").

---

## Slide 7 — How we labelled
*Title: "LLM-suggested, human-decided"*

- An LLM (Claude / ChatGPT) **suggested** skills; a human **accepted, edited or rejected** each one. Both lists are saved, so human edits are measurable.
- 3 annotators: Priyanka 55 postings · Lochan 35 · Dhanush 10.
- Doubtful skills were checked against **ESCO v1.2.1** (13,939 skills) and **O\*NET 31.0** (31,821 software/tool rows) with our `check_skill.py` lookup, plus the web for new tools.
- Finding: ESCO misses many **US legal procedures** (depositions, written discovery) and niche tools — so "not in ESCO" ≠ "not a skill".
- **Quality flags we report honestly:** 3 postings double-labelled (exact-name agreement 30–52%, mostly wording); 12 rows kept the AI suggestion unchanged.

---

## Slide 8 — Extraction approach
*Title: "LLM prompting with structured output"*

```
posting text ─► prompt v1 (our labelling rules) ─► LLM (JSON: skill + evidence) ─► statements
                                          cache on disk · retries · token log
```

- **Why an LLM:** skills appear in free text, duties and lists, with many wordings — rules/NER miss most of them.
- **Model:** Qwen 3.8-27B on **Groq free tier** (brief p.7). Temperature 0, JSON output.
- **Independence:** we avoided OpenAI and Anthropic models, because ChatGPT/Claude suggested the gold labels.
- **Gemini 3.8 Flash** (Google AI Studio) was also run, but Google returned "high demand" (503) errors — only 7/100 finished.
- **Engineering:** provider-agnostic backend (swap with one flag), every response cached (re-runs are free), rate-limit retries, keys only in `.env`.

---

## Slide 9 — Results
*Title: "F1 = 0.72 on 100 hand-labelled postings"*

| Matching | Precision | Recall | F1 |
|---|---|---|---|
| Strict (same name) | 0.60 | 0.66 | 0.63 |
| **Lenient** (word overlap) | **0.69** | **0.76** | **0.72** |

- Lenient = one name's words appear in the other ("prototyping" ≈ "high-fidelity prototyping").
- **100%** of evidence phrases are copied exactly from the posting — no invented text.
- Zero-skill posting: the model correctly returned **0** skills.

---

## Slide 10 — Results by sector (lenient F1)
*Suggested: horizontal bar chart*

| Sector | F1 |
|---|---|
| IT | **0.81** |
| Engineering | 0.75 |
| Admin / HR / Customer Service | 0.75 |
| Mixed | 0.72 |
| Finance + Accounting | 0.71 |
| Legal | 0.68 |
| Sales + Marketing | 0.67 |
| Management | 0.63 |
| Health Care | 0.61 |

- **Best: IT** — tools have clear names (SQL, Snowflake, Jira).
- **Weakest: Health Care, Management** — duties and skills blur ("patient care", "safety checks").
- Sector counts use `sector_fixed`, so they differ slightly from slide 5.

---

## Slide 11 — Error analysis
*Title: "Where the model and humans disagree"*

320 missed gold skills · 451 extra predicted skills (lenient)

| Error type | Example |
|---|---|
| Granularity (split vs merged) | gold "SAP/Chempax/Concur" merged → model lists SAP, Concur separately |
| Wording | "preparing discovery" vs gold "drafting discovery" |
| Duty vs skill boundary | model adds "patient care", "safety checks", "requirements gathering" |
| Soft skills / traits | model skips "organized", "multitasking"; humans kept them |
| Gold inconsistency | some gold rows rename or merge skills against our own rules |

- Many "errors" are **gold-set wording**, not model mistakes → next step: normalise gold names.

---

## Slide 12 — LLM usage
*Title: "Free tier, fully logged"*

| | Value |
|---|---|
| Provider / model | Groq · qwen/qwen3.8-27b |
| API calls | 100 (each posting paid once, then cached) |
| Input tokens | 91,554 |
| Output tokens | 41,902 |
| Cost | $0 (free tier) |

- Gemini attempt: 7 postings before 503 capacity errors.
- Claude Code was used to build and test the pipeline; usage is documented in the sprint report.

---

## Slide 13 — Limitations & next steps
**Limitations**
- Gold labels were LLM-suggested; 12 rows unchanged → possible anchoring.
- Only 3 postings double-labelled → agreement estimate is weak.
- Kaggle data is 2024; one LinkedIn-derived source.
- Name-based matching (gold has no evidence offsets).

**Next (Sprint 3)**
- Run the extractor on a stratified sample of the corpus → `statements` table.
- Normalise gold names; adjudicate double-labelled postings.
- Prompt tuning only on a dev split (to avoid overfitting the 100).
- Embed and cluster statements; map to ESCO / O\*NET.

---

## Slide 14 — Thank You (reuse slide 13)

**Drop from the Sprint 1 deck:** slides 4, 6–10 (source profiles) and 12 (source links). Keep the Kaggle profile (slide 5) only if you want a recap.
