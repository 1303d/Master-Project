# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `claude-haiku-5-5` via anthropic, prompt `skill_extraction_v3`
- **Gold set:** 50 postings, 709 gold skills (`data\processed\gold_v3_score_tmp.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. **The extractor is a Claude model, so it is not independent of the suggestions** (see `src/bias_check.py`).
- **Coverage:** 50 of 50 gold postings scored.
- **Evidence check:** 99% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 709 | 773 | 0.67 | 0.73 | 0.70 | 0.75 | 0.82 | 0.78 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 54 | 0.61 | 0.77 | 0.68 | 0.67 | 0.84 | 0.74 |
| Engineering | 3 | 39 | 53 | 0.51 | 0.69 | 0.59 | 0.58 | 0.79 | 0.67 |
| Finance + Accounting | 6 | 108 | 108 | 0.72 | 0.72 | 0.72 | 0.80 | 0.80 | 0.80 |
| Health Care | 8 | 68 | 74 | 0.62 | 0.68 | 0.65 | 0.73 | 0.79 | 0.76 |
| IT | 9 | 217 | 217 | 0.78 | 0.78 | 0.78 | 0.87 | 0.87 | 0.87 |
| Legal | 4 | 42 | 41 | 0.56 | 0.55 | 0.55 | 0.73 | 0.71 | 0.72 |
| Management | 5 | 51 | 63 | 0.57 | 0.71 | 0.63 | 0.67 | 0.82 | 0.74 |
| Mixed | 5 | 72 | 89 | 0.54 | 0.67 | 0.60 | 0.60 | 0.74 | 0.66 |
| Sales + Marketing | 6 | 69 | 74 | 0.74 | 0.80 | 0.77 | 0.77 | 0.83 | 0.80 |

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

Total for the 100 scored postings (each paid once, cached after): **238,987 input** and **126,355 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-20T22:01:47+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 1 | 1 | 1953 | 1259 |
| 2026-10-20T22:07:31+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 50 | 49 | 116836 | 64950 |
| 2026-10-20T23:49:20+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 100 | 50 | 120198 | 60146 |
| 2026-10-21T01:34:57+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 2000 | 2000 | 4738461 | 2531623 |
| 2026-10-30T00:44:52+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v6 | 2 | 2 | 5558 | 5642 |
| 2026-10-30T00:54:01+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v6 | 50 | 48 | 138381 | 133085 |
| 2026-10-30T01:00:35+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v5 | 50 | 50 | 139589 | 70668 |
| 2026-10-30T01:07:20+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v7 | 50 | 50 | 155639 | 87360 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales plans
- #2: market dynamics
- #2: client relationships
- #3: Diesel mechanics
- #3: hydraulic equipment maintenance
- #3: heavy-duty truck repair
- #3: electrically operated equipment maintenance
- #3: repair scheduling
- #5: prospecting
- #6: construction documents
- #6: resource management
- #8: prosecuting patent applications
- #10: embedded Electronic Control Unit
- #10: Diagnostic Trouble Codes
- #10: Control Parameter Identifiers
- #10: Parameter Identifiers
- #10: Routine Identifiers
- #11: equipment maintenance
- #13: distribution
- #13: warehousing
- #13: counting
- #14: RF boards
- #19: query authoring
- #19: data warehouse
- #19: data transformations

**Extra predicted skills (false positives), first 25:**

- #2: logical thinking
- #2: teamwork
- #3: following instructions
- #6: coaching
- #6: supervision
- #6: communication
- #6: problem solving
- #6: continuous improvement
- #6: procurement
- #6: safety processes
- #6: contract compliance
- #8: patent prosecution
- #8: post-grant proceedings
- #8: client service
- #10: Adaptive AUTOSAR
- #10: requirements definition
- #10: VECU simulation
- #10: DTCs
- #10: PIDs
- #10: CPIDs
- #10: RIDs
- #10: interface specifications
- #10: wiring harnesses
- #10: connectors
- #10: serviceability
