# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `qwen/qwen3.8-27b` via groq, prompt `skill_extraction_v5`
- **Gold set:** 50 postings, 709 gold skills (`data\processed\gold_v3_score_tmp.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. The extractor is not one of the suggesting models.
- **Coverage:** 50 of 50 gold postings scored.
- **Evidence check:** 98% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 709 | 692 | 0.69 | 0.67 | 0.68 | 0.78 | 0.76 | 0.77 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 49 | 0.61 | 0.70 | 0.65 | 0.71 | 0.81 | 0.76 |
| Engineering | 3 | 39 | 36 | 0.83 | 0.77 | 0.80 | 0.89 | 0.82 | 0.85 |
| Finance + Accounting | 6 | 108 | 100 | 0.68 | 0.63 | 0.65 | 0.77 | 0.71 | 0.74 |
| Health Care | 8 | 68 | 77 | 0.62 | 0.71 | 0.66 | 0.68 | 0.76 | 0.72 |
| IT | 9 | 217 | 198 | 0.84 | 0.77 | 0.80 | 0.89 | 0.81 | 0.85 |
| Legal | 4 | 42 | 49 | 0.47 | 0.55 | 0.51 | 0.69 | 0.81 | 0.75 |
| Management | 5 | 51 | 42 | 0.62 | 0.51 | 0.56 | 0.79 | 0.65 | 0.71 |
| Mixed | 5 | 72 | 67 | 0.57 | 0.53 | 0.55 | 0.70 | 0.65 | 0.68 |
| Sales + Marketing | 6 | 69 | 74 | 0.65 | 0.70 | 0.67 | 0.69 | 0.74 | 0.71 |

## Zero-skill postings

0 gold postings have no skills; the extractor predicted 0 skills for them.

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

Total for the 50 scored postings (each paid once, cached after): **81,995 input** and **20,967 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

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
| 2026-10-29T22:55:09+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v5 | 50 | 50 | 81995 | 20967 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales plans
- #2: brand localization
- #2: client relationships
- #3: Diesel mechanics
- #3: repair scheduling
- #5: prospecting
- #6: construction contract administration
- #6: construction plans and specifications
- #6: construction documents
- #6: resource management
- #6: conflict resolution
- #10: verification and validation
- #10: ECU diagnostics
- #11: infection control
- #11: equipment maintenance
- #11: triaging patients
- #11: obtaining vitals
- #12: AWS IAM
- #12: API testing
- #12: collaboration
- #13: distribution
- #13: warehousing
- #13: material handling equipment
- #13: physical inventories
- #13: cycle counts

**Extra predicted skills (false positives), first 25:**

- #2: sales planning
- #2: relationship building
- #2: marketing activities
- #2: competitor analysis
- #2: customer feedback analysis
- #2: reporting
- #2: residential solar market
- #2: logical thinking
- #2: teamwork
- #3: heavy duty diesel trucks
- #3: rolling stock
- #3: diagnosis
- #3: CNG equipment
- #3: gas equipment
- #3: record keeping
- #6: problem solving
- #6: supervision
- #6: communication
- #8: post-grant
- #10: Virtual Electronic Control Units
- #11: vital signs
- #11: triage
- #11: OSHA/MOSHA
- #11: biomedical waste disposal
- #11: attention to detail
