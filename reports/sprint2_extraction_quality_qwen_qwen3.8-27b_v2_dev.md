# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `qwen/qwen3.8-27b` via groq, prompt `skill_extraction_v2`
- **Gold set:** 50 postings, 684 gold skills (`data\gold\gold_labels.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. The extractor is not one of the suggesting models.
- **Coverage:** 50 of 50 gold postings scored.
- **Evidence check:** 99% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 684 | 647 | 0.68 | 0.65 | 0.66 | 0.76 | 0.72 | 0.74 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 42 | 0.74 | 0.72 | 0.73 | 0.83 | 0.81 | 0.82 |
| Engineering | 3 | 38 | 37 | 0.84 | 0.82 | 0.83 | 0.84 | 0.82 | 0.83 |
| Finance + Accounting | 6 | 106 | 107 | 0.61 | 0.61 | 0.61 | 0.72 | 0.73 | 0.72 |
| Health Care | 8 | 72 | 71 | 0.54 | 0.53 | 0.53 | 0.62 | 0.61 | 0.62 |
| IT | 9 | 203 | 176 | 0.85 | 0.73 | 0.79 | 0.90 | 0.78 | 0.84 |
| Legal | 4 | 41 | 40 | 0.60 | 0.59 | 0.59 | 0.78 | 0.76 | 0.77 |
| Management | 5 | 50 | 37 | 0.70 | 0.52 | 0.60 | 0.73 | 0.54 | 0.62 |
| Mixed | 5 | 64 | 60 | 0.52 | 0.48 | 0.50 | 0.62 | 0.58 | 0.60 |
| Sales + Marketing | 6 | 67 | 77 | 0.61 | 0.70 | 0.65 | 0.64 | 0.73 | 0.68 |

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

Total for the 50 scored postings (each paid once, cached after): **59,645 input** and **18,337 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

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

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales plans
- #2: brand localization
- #2: client relationships
- #3: power tools
- #3: hand tools
- #3: hydraulic equipment maintenance
- #3: CNG vehicle maintenance
- #3: electric vehicle maintenance
- #3: heavy-duty truck repair
- #3: maintenance scheduling
- #5: prospecting
- #6: construction contract administration
- #6: construction plans and specifications
- #6: construction documents
- #6: resource management
- #6: conflict resolution
- #8: organizational
- #10: verification and validation
- #10: ECU diagnostics
- #11: equipment maintenance
- #11: microscopic preparation
- #11: triaging patients
- #11: Urology
- #12: AWS IAM
- #12: API testing

**Extra predicted skills (false positives), first 25:**

- #2: sales planning
- #2: relationship building
- #2: marketing activities
- #2: competitor analysis
- #2: customer feedback analysis
- #2: reporting
- #2: residential solar market
- #2: teamwork
- #3: work independently
- #3: accurate records
- #5: prioritization
- #6: problem solving
- #6: supervision
- #6: communication
- #8: post-grant
- #8: organization
- #10: Virtual Electronic Control Units
- #10: Software Defined Vehicle
- #10: simulation
- #11: verbal communication
- #11: phone communication
- #11: triage
- #11: OSHA compliance
- #13: inventory management
- #13: OSHA compliance
