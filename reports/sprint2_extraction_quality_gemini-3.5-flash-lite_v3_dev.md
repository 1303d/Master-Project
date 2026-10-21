# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `gemini-3.5-flash-lite` via google-ai-studio, prompt `skill_extraction_v3`
- **Gold set:** 50 postings, 675 gold skills (`data\gold\gold_labels.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. The extractor is not one of the suggesting models.
- **Evidence check:** 99% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 50 | 675 | 511 | 0.74 | 0.56 | 0.64 | 0.82 | 0.62 | 0.71 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 38 | 0.66 | 0.58 | 0.62 | 0.79 | 0.70 | 0.74 |
| Engineering | 3 | 38 | 25 | 0.88 | 0.58 | 0.70 | 0.96 | 0.63 | 0.76 |
| Finance + Accounting | 6 | 97 | 57 | 0.63 | 0.37 | 0.47 | 0.74 | 0.43 | 0.55 |
| Health Care | 8 | 72 | 46 | 0.59 | 0.38 | 0.46 | 0.65 | 0.42 | 0.51 |
| IT | 9 | 203 | 181 | 0.87 | 0.77 | 0.82 | 0.92 | 0.82 | 0.86 |
| Legal | 4 | 41 | 36 | 0.47 | 0.41 | 0.44 | 0.72 | 0.63 | 0.68 |
| Management | 5 | 50 | 28 | 0.82 | 0.46 | 0.59 | 0.89 | 0.50 | 0.64 |
| Mixed | 5 | 64 | 54 | 0.59 | 0.50 | 0.54 | 0.70 | 0.59 | 0.64 |
| Sales + Marketing | 6 | 67 | 46 | 0.85 | 0.58 | 0.69 | 0.87 | 0.60 | 0.71 |

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

Total for the 50 scored postings (each paid once, cached after): **65,213 input** and **11,398 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-21T04:35:00+00:00 | google-ai-studio | gemini-3.5-flash-lite | skill_extraction_v3 | 1 | 1 | 1075 | 160 |
| 2026-10-21T04:44:06+00:00 | google-ai-studio | gemini-3.5-flash-lite | skill_extraction_v3 | 50 | 49 | 64138 | 11238 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales plans
- #2: sales strategies
- #2: market dynamics
- #2: home energy storage
- #2: brand localization
- #2: client relationships
- #3: Diesel mechanics
- #3: safety regulations
- #3: electric vehicle maintenance
- #3: heavy-duty truck repair
- #3: maintenance scheduling
- #5: prospecting
- #5: time management
- #6: construction contract administration
- #6: construction plans and specifications
- #6: construction documents
- #6: personnel management
- #6: resource management
- #6: conflict resolution
- #6: leadership
- #8: organizational
- #10: embedded Electronic Control Unit
- #10: verification and validation
- #10: Diagnostic Trouble Codes
- #10: Control Parameter Identifiers

**Extra predicted skills (false positives), first 25:**

- #2: teamwork
- #3: diesel engines
- #6: civil engineering
- #8: post-grant
- #8: organization
- #11: OSHA/MOSHA
- #11: verbal communication
- #19: data warehousing
- #19: slowly changing dimensions
- #19: cloud ETL/ELT tools
- #19: analytics
- #19: code reviews
- #19: adaptability
- #24: product knowledge
- #24: teamwork
- #31: automated test frameworks
- #31: web and mobile applications testing
- #31: code reviews
- #31: testing methodologies
- #33: analytical skills
- #33: supervision
- #34: patient care
- #35: toe trimming
- #35: water hose
- #35: Hazard Communication
