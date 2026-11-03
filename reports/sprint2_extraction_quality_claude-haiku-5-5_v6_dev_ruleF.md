# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `claude-haiku-5-5` via anthropic, prompt `skill_extraction_v6`
- **Gold set:** 50 postings, 683 gold skills (`data\gold\gold_labels_ruleF.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. **The extractor is a Claude model, so it is not independent of the suggestions** (see `src/bias_check.py`).
- **Coverage:** 50 of 50 gold postings scored.
- **Evidence check:** 100% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 683 | 906 | 0.50 | 0.67 | 0.57 | 0.59 | 0.78 | 0.67 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 52 | 0.65 | 0.79 | 0.72 | 0.71 | 0.86 | 0.78 |
| Engineering | 3 | 38 | 55 | 0.58 | 0.84 | 0.69 | 0.62 | 0.89 | 0.73 |
| Finance + Accounting | 6 | 106 | 128 | 0.50 | 0.60 | 0.55 | 0.59 | 0.71 | 0.64 |
| Health Care | 8 | 72 | 92 | 0.35 | 0.44 | 0.39 | 0.48 | 0.61 | 0.54 |
| IT | 9 | 202 | 263 | 0.60 | 0.78 | 0.68 | 0.69 | 0.90 | 0.78 |
| Legal | 4 | 41 | 42 | 0.52 | 0.54 | 0.53 | 0.62 | 0.63 | 0.63 |
| Management | 5 | 50 | 74 | 0.39 | 0.58 | 0.47 | 0.46 | 0.68 | 0.55 |
| Mixed | 5 | 64 | 107 | 0.36 | 0.59 | 0.44 | 0.42 | 0.70 | 0.53 |
| Sales + Marketing | 6 | 67 | 93 | 0.52 | 0.72 | 0.60 | 0.60 | 0.84 | 0.70 |

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

Total for the 50 scored postings (each paid once, cached after): **143,939 input** and **138,727 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-20T22:01:47+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 1 | 1 | 1953 | 1259 |
| 2026-10-20T22:07:31+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 50 | 49 | 116836 | 64950 |
| 2026-10-20T23:49:20+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 100 | 50 | 120198 | 60146 |
| 2026-10-21T01:34:57+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v3 | 2000 | 2000 | 4738461 | 2531623 |
| 2026-10-30T00:44:52+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v6 | 2 | 2 | 5558 | 5642 |
| 2026-10-30T00:54:01+00:00 | anthropic | claude-haiku-5-5 | skill_extraction_v6 | 50 | 48 | 138381 | 133085 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales plans
- #2: client relationships
- #3: Diesel mechanics
- #3: CNG vehicle maintenance
- #3: electric vehicle maintenance
- #3: heavy-duty truck repair
- #3: maintenance scheduling
- #5: organization
- #6: highway construction
- #6: construction contract administration
- #6: construction documents
- #8: litigation
- #8: organizational
- #10: embedded Electronic Control Unit
- #11: equipment maintenance
- #11: triaging patients
- #11: attention to detail
- #12: attention to detail
- #13: distribution
- #13: warehousing
- #13: physical inventories
- #13: cycle counts
- #13: stock rotation
- #13: attention to detail
- #19: data warehouse

**Extra predicted skills (false positives), first 25:**

- #2: sales planning
- #2: business opportunity identification
- #2: relationship building
- #2: energy industry
- #2: marketing campaigns
- #2: customer feedback analysis
- #2: collaboration
- #2: residential solar
- #2: inverters
- #2: consumer electronics
- #2: mobile energy storage
- #2: business expansion
- #2: logical thinking
- #2: teamwork
- #3: diagnose operational difficulties
- #3: heavy duty diesel trucks
- #3: rolling stock
- #3: CNG equipment
- #3: repair scheduling
- #3: review mechanical write-ups
- #3: coordinate repair schedule
- #3: applicable laws
- #3: applicable regulations
- #3: company policies
- #3: follow instructions
