# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `gemini-3.8-flash` via google-ai-studio, prompt `skill_extraction_v3`
- **Gold set:** 20 postings, 264 gold skills (`data/gold/gold_labels.csv`).
  Labels are LLM-suggested and human-corrected (Claude/ChatGPT suggestions; Gemini was not used), so the extractor is independent of the label suggestions.
- **Evidence check:** 100% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 20 | 264 | 256 | 0.75 | 0.72 | 0.73 | 0.80 | 0.78 | 0.79 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 2 | 14 | 15 | 0.80 | 0.86 | 0.83 | 0.87 | 0.93 | 0.90 |
| Engineering | 3 | 38 | 43 | 0.74 | 0.84 | 0.79 | 0.77 | 0.87 | 0.81 |
| Finance + Accounting | 1 | 15 | 12 | 0.33 | 0.27 | 0.30 | 0.58 | 0.47 | 0.52 |
| Health Care | 3 | 32 | 31 | 0.65 | 0.62 | 0.63 | 0.74 | 0.72 | 0.73 |
| IT | 4 | 86 | 93 | 0.80 | 0.86 | 0.83 | 0.81 | 0.87 | 0.84 |
| Legal | 1 | 9 | 11 | 0.73 | 0.89 | 0.80 | 0.73 | 0.89 | 0.80 |
| Management | 2 | 22 | 15 | 0.80 | 0.55 | 0.65 | 0.93 | 0.64 | 0.76 |
| Mixed | 1 | 12 | 6 | 0.83 | 0.42 | 0.56 | 1.00 | 0.50 | 0.67 |
| Sales + Marketing | 3 | 36 | 30 | 0.80 | 0.67 | 0.73 | 0.87 | 0.72 | 0.79 |

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

Total for the 20 scored postings (each paid once, cached after): **27,514 input** and **17,149 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-09T09:09:56+00:00 | google-ai-studio | gemini-3.8-flash | skill_extraction_v1 | 3 | 3 | 2353 | 1477 |
| 2026-10-09T19:35:59+00:00 | google-ai-studio | gemini-3.8-flash | skill_extraction_v1 | 100 | 1 | 470 | 504 |
| 2026-10-20T20:37:04+00:00 | google-ai-studio | gemini-3.8-flash | skill_extraction_v3 | 2 | 2 | 2511 | 1376 |
| 2026-10-21T00:14:46+00:00 | google-ai-studio | gemini-3.8-flash | skill_extraction_v3 | 50 | 18 | 25003 | 15773 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales plans
- #2: sales strategies
- #2: market dynamics
- #2: brand localization
- #2: client relationships
- #3: Diesel mechanics
- #3: safety regulations
- #3: CNG vehicle maintenance
- #3: electric vehicle maintenance
- #3: heavy-duty truck repair
- #3: maintenance scheduling
- #5: prospecting
- #6: construction plans and specifications
- #6: construction documents
- #8: organizational
- #10: embedded Electronic Control Unit
- #10: verification and validation
- #11: equipment maintenance
- #11: microscopic preparation
- #11: triaging patients
- #11: obtaining vitals
- #11: computer software
- #11: database skills
- #11: Urology
- #13: distribution

**Extra predicted skills (false positives), first 25:**

- #2: sales planning
- #2: teamwork
- #6: procurement
- #6: coaching
- #6: continuous improvement
- #6: performance reviews
- #8: post-grant
- #8: organization
- #8: client service
- #10: Virtual Electronic Control Units
- #10: Software Defined Vehicle
- #10: simulation
- #10: Vehicle Intelligent Platform
- #10: Adaptive AUTOSAR
- #11: patient care
- #11: taking vital signs
- #11: triage
- #11: OSHA
- #11: MOSHA
- #11: verbal communication
- #13: teamwork
- #14: X-Band
- #19: data warehousing
- #19: slowly changing dimensions
- #19: data modeling
