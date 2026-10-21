# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `openai/gpt-oss-120b` via groq, prompt `skill_extraction_v3`
- **Gold set:** 50 postings, 675 gold skills (`data/gold/gold_labels.csv`).
  Labels are LLM-suggested and human-corrected (Claude/ChatGPT suggestions; Gemini was not used), so the extractor is independent of the label suggestions.
- **Evidence check:** 98% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 675 | 793 | 0.54 | 0.64 | 0.59 | 0.65 | 0.77 | 0.71 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 55 | 0.62 | 0.79 | 0.69 | 0.67 | 0.86 | 0.76 |
| Engineering | 3 | 38 | 57 | 0.39 | 0.58 | 0.46 | 0.58 | 0.87 | 0.69 |
| Finance + Accounting | 6 | 97 | 109 | 0.49 | 0.55 | 0.51 | 0.67 | 0.75 | 0.71 |
| Health Care | 8 | 72 | 99 | 0.41 | 0.57 | 0.48 | 0.52 | 0.71 | 0.60 |
| IT | 9 | 203 | 203 | 0.73 | 0.73 | 0.73 | 0.80 | 0.80 | 0.80 |
| Legal | 4 | 41 | 49 | 0.41 | 0.49 | 0.44 | 0.65 | 0.78 | 0.71 |
| Management | 5 | 50 | 59 | 0.58 | 0.68 | 0.62 | 0.64 | 0.76 | 0.70 |
| Mixed | 5 | 64 | 74 | 0.43 | 0.50 | 0.46 | 0.53 | 0.61 | 0.57 |
| Sales + Marketing | 6 | 67 | 88 | 0.53 | 0.70 | 0.61 | 0.61 | 0.81 | 0.70 |

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

Total for the 50 scored postings (each paid once, cached after): **69,728 input** and **79,615 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-20T18:34:32+00:00 | groq | openai/gpt-oss-120b | skill_extraction_v3 | 1 | 1 | 1173 | 1210 |
| 2026-10-20T18:49:40+00:00 | groq | openai/gpt-oss-120b | skill_extraction_v3 | 50 | 49 | 68555 | 78405 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales strategies
- #2: client relationships
- #3: Diesel mechanics
- #3: computer literacy
- #3: electric vehicle maintenance
- #3: heavy-duty truck repair
- #3: maintenance scheduling
- #5: prospecting
- #5: organization
- #5: time management
- #6: construction documents
- #8: organizational
- #10: embedded Electronic Control Unit
- #10: verification and validation
- #10: ECU diagnostics
- #11: infection control
- #11: equipment maintenance
- #11: triaging patients
- #11: obtaining vitals
- #11: Urology
- #12: AWS
- #12: API testing
- #13: distribution
- #13: warehousing
- #13: forklift operation

**Extra predicted skills (false positives), first 25:**

- #2: teamwork
- #2: energy industry
- #2: inverters
- #2: consumer electronics
- #2: mobile energy storage
- #2: residential solar market
- #2: marketing
- #2: reporting
- #3: heavy duty diesel trucks
- #3: rolling stock
- #3: gas
- #3: electrically operated equipment
- #3: computer literate
- #3: operate any vehicle
- #3: follow detailed instructions
- #3: work independently
- #3: record keeping
- #5: organizational
- #5: manage your time
- #5: prioritize tasks
- #5: work within deadlines
- #6: specifications
- #6: safety work processes
- #6: training
- #6: procurement rules
