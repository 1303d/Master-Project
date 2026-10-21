# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `qwen/qwen3.8-27b` via groq, prompt `skill_extraction_v2+knn2`
- **Gold set:** 50 postings, 675 gold skills (`data/gold/gold_labels.csv`).
  Labels are LLM-suggested and human-corrected (Claude/ChatGPT suggestions; Gemini was not used), so the extractor is independent of the label suggestions.
- **Evidence check:** 98% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 675 | 650 | 0.66 | 0.64 | 0.65 | 0.75 | 0.72 | 0.74 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 40 | 0.80 | 0.74 | 0.77 | 0.85 | 0.79 | 0.82 |
| Engineering | 3 | 38 | 38 | 0.79 | 0.79 | 0.79 | 0.79 | 0.79 | 0.79 |
| Finance + Accounting | 6 | 97 | 108 | 0.51 | 0.57 | 0.54 | 0.69 | 0.76 | 0.72 |
| Health Care | 8 | 72 | 79 | 0.51 | 0.56 | 0.53 | 0.56 | 0.61 | 0.58 |
| IT | 9 | 203 | 192 | 0.83 | 0.79 | 0.81 | 0.88 | 0.83 | 0.85 |
| Legal | 4 | 41 | 37 | 0.51 | 0.46 | 0.49 | 0.68 | 0.61 | 0.64 |
| Management | 5 | 50 | 37 | 0.68 | 0.50 | 0.57 | 0.73 | 0.54 | 0.62 |
| Mixed | 5 | 64 | 57 | 0.44 | 0.39 | 0.41 | 0.67 | 0.59 | 0.63 |
| Sales + Marketing | 6 | 67 | 62 | 0.74 | 0.69 | 0.71 | 0.76 | 0.70 | 0.73 |

## Zero-skill postings

0 gold postings have no skills; the extractor predicted 0 skills for them.

## Matching rules

(one-to-one, per posting), after normalising both names (lowercase, filler words removed,
simple plural -> singular):
- strict:  normalised names are equal, also with spaces removed ("multi-tasking" = "multitasking");
           "analyses" is read as "analysis"
- lenient: equal, OR all words of one name appear in the other
           ("prototyping" ~ "high-fidelity prototyping", "Visio" ~ "Microsoft Visio")
The gold set has no evidence offsets, so matching is by name only.

## LLM token usage

Total for the 50 scored postings (each paid once, cached after): **102,589 input** and **19,369 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-09T09:31:04+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v1 | 3 | 3 | 2502 | 1477 |
| 2026-10-09T10:08:14+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v1 | 100 | 97 | 89052 | 40425 |
| 2026-10-15T20:52:25+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v1 | 3 | 3 | 2769 | 1195 |
| 2026-10-15T21:17:06+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v2 | 50 | 50 | 59645 | 18337 |
| 2026-10-17T16:16:08+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v2+knn2 | 50 | 50 | 102589 | 19369 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales plans
- #2: sales strategies
- #2: market dynamics
- #2: home energy storage
- #2: brand localization
- #2: client relationships
- #3: CNG vehicle maintenance
- #3: electric vehicle maintenance
- #3: heavy-duty truck repair
- #3: maintenance scheduling
- #5: prospecting
- #5: strategic sales approach
- #6: construction contract administration
- #6: construction plans and specifications
- #6: construction documents
- #6: resource management
- #6: conflict resolution
- #8: organizational
- #10: embedded Electronic Control Unit
- #10: verification and validation
- #10: ECU diagnostics
- #11: infection control
- #11: equipment maintenance
- #11: triaging patients
- #11: Urology

**Extra predicted skills (false positives), first 25:**

- #2: sales planning
- #2: teamwork
- #3: work independently
- #3: record keeping
- #5: outbound sales
- #5: prioritization
- #5: sales strategy
- #6: procurement
- #6: problem solving
- #6: communication
- #6: supervision
- #8: post-grant
- #8: organization
- #10: Virtual Electronic Control Units
- #10: Software Defined Vehicle
- #10: simulation
- #10: signal data transmission
- #11: vital signs
- #11: triage
- #11: OSHA/MOSHA
- #11: biomedical waste disposal
- #11: verbal communication
- #11: phone communication
- #13: inventory management
- #13: OSHA compliance
