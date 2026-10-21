# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `claude-haiku-5-5` via anthropic, prompt `skill_extraction_v3`
- **Gold set:** 50 postings, 675 gold skills (`data\gold\gold_labels.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. **The extractor is a Claude model, so it is not independent of the suggestions** (see `src/bias_check.py`).
- **Evidence check:** 99% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 675 | 773 | 0.61 | 0.70 | 0.65 | 0.71 | 0.81 | 0.75 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 54 | 0.63 | 0.79 | 0.70 | 0.69 | 0.86 | 0.76 |
| Engineering | 3 | 38 | 53 | 0.49 | 0.68 | 0.57 | 0.57 | 0.79 | 0.66 |
| Finance + Accounting | 6 | 97 | 108 | 0.53 | 0.59 | 0.56 | 0.71 | 0.79 | 0.75 |
| Health Care | 8 | 72 | 74 | 0.58 | 0.60 | 0.59 | 0.70 | 0.72 | 0.71 |
| IT | 9 | 203 | 217 | 0.74 | 0.79 | 0.77 | 0.82 | 0.88 | 0.85 |
| Legal | 4 | 41 | 41 | 0.51 | 0.51 | 0.51 | 0.68 | 0.68 | 0.68 |
| Management | 5 | 50 | 63 | 0.60 | 0.76 | 0.67 | 0.65 | 0.82 | 0.73 |
| Mixed | 5 | 64 | 89 | 0.46 | 0.64 | 0.54 | 0.52 | 0.72 | 0.60 |
| Sales + Marketing | 6 | 67 | 74 | 0.72 | 0.79 | 0.75 | 0.74 | 0.82 | 0.78 |

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

Total for the 100 scored postings (each paid once, cached after): **238,987 input** and **126,355 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-20T22:01:47+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 1 | 1 | 1953 | 1259 |
| 2026-10-20T22:07:31+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 50 | 49 | 116836 | 64950 |
| 2026-10-20T23:49:20+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 100 | 50 | 120198 | 60146 |
| 2026-10-21T01:34:57+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 2000 | 2000 | 4738461 | 2531623 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales plans
- #2: market dynamics
- #2: client relationships
- #3: Diesel mechanics
- #3: hydraulic equipment maintenance
- #3: electric vehicle maintenance
- #3: heavy-duty truck repair
- #3: maintenance scheduling
- #5: prospecting
- #6: construction documents
- #6: resource management
- #8: prosecuting patent applications
- #8: organizational
- #10: embedded Electronic Control Unit
- #10: Diagnostic Trouble Codes
- #10: Control Parameter Identifiers
- #10: Parameter Identifiers
- #10: Routine Identifiers
- #11: equipment maintenance
- #11: Urology
- #13: distribution
- #13: warehousing
- #13: counting
- #14: RF boards
- #19: query authoring

**Extra predicted skills (false positives), first 25:**

- #2: logical thinking
- #2: teamwork
- #3: following instructions
- #5: prioritization
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
- #8: organization
- #8: client service
- #10: Adaptive AUTOSAR
- #10: Software Defined Vehicle 2.0
- #10: requirements definition
- #10: VECU simulation
- #10: DTCs
- #10: PIDs
- #10: CPIDs
- #10: RIDs
- #10: interface specifications
