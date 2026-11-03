# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `claude-haiku-5-5` via anthropic, prompt `skill_extraction_v7`
- **Gold set:** 50 postings, 684 gold skills (`data\gold\gold_labels.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. **The extractor is a Claude model, so it is not independent of the suggestions** (see `src/bias_check.py`).
- **Coverage:** 50 of 50 gold postings scored.
- **Evidence check:** 100% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 684 | 728 | 0.65 | 0.69 | 0.67 | 0.73 | 0.78 | 0.75 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 46 | 0.74 | 0.79 | 0.76 | 0.80 | 0.86 | 0.83 |
| Engineering | 3 | 38 | 51 | 0.57 | 0.76 | 0.65 | 0.65 | 0.87 | 0.74 |
| Finance + Accounting | 6 | 106 | 105 | 0.64 | 0.63 | 0.64 | 0.73 | 0.73 | 0.73 |
| Health Care | 8 | 72 | 69 | 0.58 | 0.56 | 0.57 | 0.71 | 0.68 | 0.70 |
| IT | 9 | 203 | 224 | 0.74 | 0.82 | 0.78 | 0.81 | 0.89 | 0.85 |
| Legal | 4 | 41 | 33 | 0.48 | 0.39 | 0.43 | 0.70 | 0.56 | 0.62 |
| Management | 5 | 50 | 48 | 0.69 | 0.66 | 0.67 | 0.73 | 0.70 | 0.71 |
| Mixed | 5 | 64 | 78 | 0.44 | 0.53 | 0.48 | 0.54 | 0.66 | 0.59 |
| Sales + Marketing | 6 | 67 | 74 | 0.70 | 0.78 | 0.74 | 0.74 | 0.82 | 0.78 |

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

Total for the 50 scored postings (each paid once, cached after): **155,639 input** and **87,360 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

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
- #2: sales strategies
- #2: brand localization
- #2: client relationships
- #3: Diesel mechanics
- #3: electric vehicle maintenance
- #3: heavy-duty truck repair
- #3: maintenance scheduling
- #6: highway construction
- #6: construction contract administration
- #6: construction documents
- #6: resource management
- #8: prosecuting patent applications
- #8: litigation
- #8: organizational
- #10: embedded Electronic Control Unit
- #11: equipment maintenance
- #11: obtaining vitals
- #11: Urology
- #12: API testing
- #13: distribution
- #13: warehousing
- #13: physical inventories
- #13: reading
- #13: counting

**Extra predicted skills (false positives), first 25:**

- #2: energy industry
- #2: teamwork
- #3: equipment repair
- #3: repair planning
- #3: hydraulic equipment
- #3: diagnostic software
- #3: following instructions
- #3: equipment operation
- #5: prioritization
- #5: relationship building
- #6: engineering practices
- #6: procurement rules
- #6: quality standards
- #6: safety processes
- #6: supervision
- #6: coaching
- #6: problem solving
- #6: communication
- #6: contract compliance
- #8: patent prosecution
- #8: organization
- #8: client service
- #10: requirements gathering
- #10: simulation
- #10: Software Defined Vehicle 2.0 architecture
