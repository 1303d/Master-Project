# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `claude-haiku-5-5` via anthropic, prompt `skill_extraction_v8`
- **Gold set:** 50 postings, 709 gold skills (`data\gold\gold_labels_v3_dev_proposed.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. **The extractor is a Claude model, so it is not independent of the suggestions** (see `src/bias_check.py`).
- **Coverage:** 50 of 50 gold postings scored.
- **Postings with gold skills but no predictions:** 1 (#45): check these are real empty answers, not parsing problems.
- **Sectors from:** gold_split.csv sector_eval.
- **Evidence check:** 99% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 709 | 671 | 0.76 | 0.72 | 0.74 | 0.84 | 0.80 | 0.82 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 43 | 0.77 | 0.77 | 0.77 | 0.81 | 0.81 | 0.81 |
| Engineering | 3 | 39 | 42 | 0.76 | 0.82 | 0.79 | 0.81 | 0.87 | 0.84 |
| Finance + Accounting | 6 | 108 | 93 | 0.80 | 0.69 | 0.74 | 0.87 | 0.75 | 0.81 |
| Health Care | 8 | 68 | 58 | 0.66 | 0.56 | 0.60 | 0.83 | 0.71 | 0.76 |
| IT | 9 | 217 | 219 | 0.79 | 0.80 | 0.80 | 0.87 | 0.88 | 0.87 |
| Legal | 4 | 42 | 40 | 0.62 | 0.60 | 0.61 | 0.80 | 0.76 | 0.78 |
| Management | 5 | 51 | 49 | 0.69 | 0.67 | 0.68 | 0.82 | 0.78 | 0.80 |
| Mixed | 5 | 72 | 57 | 0.79 | 0.62 | 0.70 | 0.82 | 0.65 | 0.73 |
| Sales + Marketing | 6 | 69 | 70 | 0.77 | 0.78 | 0.78 | 0.81 | 0.83 | 0.82 |

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

Optional (added 2026-10-30; the strict and lenient numbers above are unchanged by them):
- --aliases skill_aliases_manual.csv: an extra "strict+alias" score. Both gold and predicted names are first
  mapped skill_key -> canonical_key (lowercased, exact key), then matched strictly.
- --same-postings-as RUN [RUN ...]: score only postings that every listed run also finished, so two
  versions are compared on the same postings (a failed posting would otherwise drop out of one run only).
- --baseline RUN --bootstrap N: paired bootstrap over postings; 95% interval of (this run - baseline) F1.
- --sector-source split: sectors from gold_split.csv sector_eval instead of the gold file.

## LLM token usage

Total for the 50 scored postings (each paid once, cached after): **169,489 input** and **80,741 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

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
| 2026-10-30T05:22:29+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 50 | 0 | 0 | 0 |
| 2026-10-30T05:29:23+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v8 | 50 | 50 | 169489 | 80741 |
| 2026-10-30T05:29:32+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v8a | 50 | 50 | 155989 | 85653 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales plans
- #2: sales strategies
- #2: client relationships
- #3: Diesel mechanics
- #3: hydraulic equipment maintenance
- #3: CNG vehicle maintenance
- #3: heavy-duty truck repair
- #3: electrically operated equipment maintenance
- #3: repair scheduling
- #6: construction contract administration
- #6: construction documents
- #6: resource management
- #8: prosecuting patent applications
- #8: litigation
- #10: embedded Electronic Control Unit
- #10: Software Defined Vehicle 2.0
- #11: equipment maintenance
- #11: administering injections
- #11: obtaining vitals
- #11: computer software
- #13: distribution
- #13: warehousing
- #13: cycle counts
- #13: reading
- #19: data warehouse

**Extra predicted skills (false positives), first 25:**

- #2: teamwork
- #3: diagnosis
- #6: procurement rules
- #6: quality standards
- #6: safety processes
- #6: coaching
- #6: supervision
- #6: continuous improvement
- #8: patent prosecution
- #8: client service
- #10: requirements gathering
- #10: simulation
- #11: vital signs
- #11: OSHA
- #11: MOSHA
- #11: biohazardous waste policy
- #11: injection administration
- #12: requirements gathering
- #12: error handling
- #12: documentation
- #12: AWS developer tools
- #13: order picking
- #19: data warehousing
- #19: code review
- #19: data lineage
