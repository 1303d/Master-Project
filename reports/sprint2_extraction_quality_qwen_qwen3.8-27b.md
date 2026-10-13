# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `qwen/qwen3.8-27b` via groq, prompt `skill_extraction_v1`
- **Gold set:** 100 postings, 1317 gold skills (`data/gold/gold_labels.csv`).
  Labels are LLM-suggested and human-corrected (Claude/ChatGPT suggestions; Gemini was not used), so the extractor is independent of the label suggestions.
- **Evidence check:** 100% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 100 | 1317 | 1448 | 0.60 | 0.66 | 0.63 | 0.69 | 0.76 | 0.72 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 9 | 82 | 102 | 0.56 | 0.70 | 0.62 | 0.68 | 0.84 | 0.75 |
| Engineering | 6 | 112 | 135 | 0.64 | 0.78 | 0.70 | 0.69 | 0.83 | 0.75 |
| Finance + Accounting | 12 | 193 | 217 | 0.54 | 0.61 | 0.57 | 0.67 | 0.76 | 0.71 |
| Health Care | 15 | 123 | 150 | 0.47 | 0.58 | 0.52 | 0.55 | 0.67 | 0.61 |
| IT | 18 | 350 | 345 | 0.74 | 0.73 | 0.73 | 0.82 | 0.81 | 0.81 |
| Legal | 9 | 160 | 143 | 0.58 | 0.52 | 0.55 | 0.72 | 0.64 | 0.68 |
| Management | 10 | 76 | 83 | 0.55 | 0.61 | 0.58 | 0.60 | 0.66 | 0.63 |
| Mixed | 10 | 102 | 129 | 0.53 | 0.68 | 0.60 | 0.64 | 0.81 | 0.72 |
| Sales + Marketing | 11 | 119 | 144 | 0.59 | 0.71 | 0.65 | 0.61 | 0.74 | 0.67 |

## Zero-skill postings

1 gold postings have no skills; the extractor predicted 0 skills for them.

## Matching rules

(one-to-one, per posting), after normalising both names (lowercase, filler words removed,
simple plural -> singular):
- strict:  normalised names are equal
- lenient: equal, OR all words of one name appear in the other
           ("prototyping" ~ "high-fidelity prototyping", "Visio" ~ "Microsoft Visio")
The gold set has no evidence offsets, so matching is by name only.

## LLM token usage

Total for the 100 scored postings (each paid once, cached after): **91,554 input** and **41,902 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-09T09:31:04+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v1 | 3 | 3 | 2502 | 1477 |
| 2026-10-09T10:08:14+00:00 | groq | qwen/qwen3.8-27b | skill_extraction_v1 | 100 | 97 | 89052 | 40425 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #1: litigation
- #1: organized
- #1: drafting discovery
- #2: sales plans
- #2: brand localization
- #2: client relationships
- #3: Diesel mechanics
- #3: electric vehicle maintenance
- #3: maintenance scheduling
- #4: inside sales
- #4: outside sales
- #5: prospecting
- #5: organization
- #6: construction contract administration
- #6: construction plans and specifications
- #6: resource management
- #7: transcribe information
- #8: FTO analysis
- #9: Google Office Suite
- #10: embedded Electronic Control Unit
- #10: verification and validation
- #10: ECU diagnostics
- #11: infection control
- #11: equipment maintenance
- #11: triaging patients

**Extra predicted skills (false positives), first 25:**

- #1: preparing discovery
- #1: filing documents
- #1: preparing trial exhibits
- #1: interpersonal skills
- #1: organization
- #2: sales planning
- #2: relationship building
- #2: marketing activities
- #2: competitor analysis
- #2: customer feedback analysis
- #2: reporting
- #2: residential solar market
- #2: teamwork
- #3: heavy duty diesel trucks
- #3: rolling stock
- #3: diagnose
- #3: gas
- #3: electrically operated equipment
- #3: work orders
- #3: hydraulic equipment
- #3: record keeping
- #5: organizational skills
- #5: prioritization
- #6: performance reviews
- #6: training
