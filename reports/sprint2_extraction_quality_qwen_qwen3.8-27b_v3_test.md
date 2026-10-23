# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `qwen/qwen3.8-27b` via groq, prompt `skill_extraction_v3`
- **Gold set:** 50 postings, 649 gold skills (`data\gold\gold_labels.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. The extractor is not one of the suggesting models.
- **Coverage:** 50 of 50 gold postings scored.
- **Evidence check:** 99% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 649 | 657 | 0.65 | 0.66 | 0.66 | 0.74 | 0.75 | 0.74 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 5 | 39 | 45 | 0.60 | 0.69 | 0.64 | 0.78 | 0.90 | 0.83 |
| Engineering | 3 | 74 | 91 | 0.56 | 0.69 | 0.62 | 0.65 | 0.80 | 0.72 |
| Finance + Accounting | 6 | 96 | 89 | 0.71 | 0.66 | 0.68 | 0.80 | 0.74 | 0.77 |
| Health Care | 7 | 56 | 61 | 0.57 | 0.62 | 0.60 | 0.64 | 0.70 | 0.67 |
| IT | 9 | 147 | 156 | 0.68 | 0.72 | 0.70 | 0.78 | 0.82 | 0.80 |
| Legal | 5 | 119 | 97 | 0.63 | 0.51 | 0.56 | 0.71 | 0.58 | 0.64 |
| Management | 5 | 28 | 31 | 0.55 | 0.61 | 0.58 | 0.61 | 0.68 | 0.64 |
| Mixed | 5 | 38 | 35 | 0.89 | 0.82 | 0.85 | 0.97 | 0.89 | 0.93 |
| Sales + Marketing | 5 | 52 | 52 | 0.73 | 0.73 | 0.73 | 0.75 | 0.75 | 0.75 |

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

Total for the 100 scored postings (each paid once, cached after): **137,254 input** and **40,020 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-09T09:31:04+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v1 | 3 | 3 | 2502 | 1477 |
| 2026-10-09T10:08:14+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v1 | 100 | 97 | 89052 | 40425 |
| 2026-10-15T20:52:25+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v1 | 3 | 3 | 2769 | 1195 |
| 2026-10-15T21:17:06+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v2 | 50 | 50 | 59645 | 18337 |
| 2026-10-17T16:16:08+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v2+knn2 | 50 | 50 | 102589 | 19369 |
| 2026-10-18T20:53:08+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v3 | 50 | 50 | 68045 | 20842 |
| 2026-10-20T17:45:06+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v4 | 50 | 50 | 89995 | 21473 |
| 2026-10-20T23:43:49+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v3 | 100 | 50 | 69209 | 19178 |
| 2026-10-22T23:49:40+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v3 | 1 | 1 | 855 | 61 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #1: litigation
- #1: organized
- #1: drafting discovery
- #4: inside sales
- #4: outside sales
- #7: transcribe information
- #7: customer service
- #7: nutrition analysis
- #9: drafting legal documents
- #9: Google Office Suite
- #16: Routing
- #17: technology proficiency
- #17: planning
- #17: client service
- #17: information analysis
- #17: administrative
- #17: multitasking
- #17: Microsoft Office
- #18: administrative
- #18: clerical
- #18: document management
- #18: court filing
- #18: document naming
- #18: document uploading
- #18: correspondence preparation

**Extra predicted skills (false positives), first 25:**

- #1: preparing discovery
- #1: filing documents
- #1: preparing trial exhibits
- #1: interpersonal skills
- #1: organization
- #7: keyboarding
- #7: transcription
- #7: food service
- #7: healthcare
- #9: legal document preparation
- #9: reading and interpreting rules and regulations
- #9: drafting Department Orders
- #9: drafting Director's Instruction
- #9: federal government websites
- #9: state and federal laws
- #9: basic subsistence benefits
- #9: legislative branch
- #9: judicial branch
- #9: executive branch
- #9: litigation process
- #17: contract management system
- #17: Word
- #17: Excel
- #17: PowerPoint
- #17: Outlook
