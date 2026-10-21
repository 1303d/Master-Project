# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `claude-haiku-5-5` via anthropic, prompt `skill_extraction_v3`
- **Gold set:** 50 postings, 649 gold skills (`data\gold\gold_labels.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. **The extractor is a Claude model, so it is not independent of the suggestions** (see `src/bias_check.py`).
- **Coverage:** 50 of 50 gold postings scored.
- **Evidence check:** 99% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 649 | 702 | 0.64 | 0.69 | 0.66 | 0.72 | 0.78 | 0.75 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 5 | 39 | 48 | 0.54 | 0.67 | 0.60 | 0.67 | 0.82 | 0.74 |
| Engineering | 3 | 74 | 79 | 0.71 | 0.76 | 0.73 | 0.75 | 0.80 | 0.77 |
| Finance + Accounting | 6 | 96 | 90 | 0.66 | 0.61 | 0.63 | 0.78 | 0.73 | 0.75 |
| Health Care | 7 | 56 | 68 | 0.54 | 0.66 | 0.60 | 0.65 | 0.79 | 0.71 |
| IT | 9 | 147 | 179 | 0.68 | 0.83 | 0.75 | 0.75 | 0.91 | 0.82 |
| Legal | 5 | 119 | 114 | 0.54 | 0.52 | 0.53 | 0.65 | 0.62 | 0.64 |
| Management | 5 | 28 | 31 | 0.55 | 0.61 | 0.58 | 0.61 | 0.68 | 0.64 |
| Mixed | 5 | 38 | 36 | 0.81 | 0.76 | 0.78 | 0.92 | 0.87 | 0.89 |
| Sales + Marketing | 5 | 52 | 57 | 0.67 | 0.73 | 0.70 | 0.72 | 0.79 | 0.75 |

## Zero-skill postings

1 gold postings have no skills; the extractor predicted 0 skills for them.

## Matching rules

(one-to-one, per posting; maximum matching, so the score does not depend on list order),
after normalising both names (lowercase, filler words removed,
simple plural -> singular):
- strict:  normalised names are equal, also with spaces removed ("multi-tasking" = "multitasking");
           "analyses" is read as "analysis"
- lenient: equal, OR all words of one name appear in the other
           ("prototyping" ~ "high-fidelity prototyping", "Visio" ~ "Microsoft Visio")
The gold set has no evidence offsets, so matching is by name only.

## LLM token usage

Total for the 100 scored postings (each paid once, cached after): **238,987 input** and **126,355 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-20T22:01:47+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 1 | 1 | 1953 | 1259 |
| 2026-10-20T22:07:31+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 50 | 49 | 116836 | 64950 |
| 2026-10-20T23:49:20+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 100 | 50 | 120198 | 60146 |
| 2026-10-21T01:34:57+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 2000 | 2000 | 4738461 | 2531623 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #1: family law
- #1: litigation
- #1: organized
- #4: inside sales
- #4: outside sales
- #7: transcribe information
- #9: legal analysis
- #9: health and human services
- #9: managed care
- #9: Google Office Suite
- #9: Google documents
- #17: organizational
- #17: information analysis
- #17: administrative
- #17: Microsoft Office
- #17: contract management software
- #18: mail processing
- #18: administrative
- #18: clerical
- #18: document management
- #18: court filing
- #18: document naming
- #18: document uploading
- #18: correspondence preparation
- #18: legal document preparation

**Extra predicted skills (false positives), first 25:**

- #1: interpersonal skills
- #1: organization
- #1: customer service
- #1: professionalism
- #7: meal ordering platform
- #7: calorie count
- #7: Intermountain Modified Diet Guideline
- #7: Bedside Connect
- #7: keyboarding
- #7: transcription
- #7: food service equipment
- #7: teamwork
- #9: regulations
- #9: state and federal laws
- #9: state and federal regulations
- #9: government branches
- #9: administrative proceedings
- #9: Google Docs
- #17: organization
- #17: contract management system
- #17: MS Office Suite
- #17: Word
- #17: Excel
- #17: PowerPoint
- #17: Outlook
