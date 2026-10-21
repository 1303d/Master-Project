# Sprint 2 — Extraction quality report (Section B, skills)

- **Extractor:** `nvidia/nemotron-3-ultra-550b-a55b:free` via openrouter, prompt `skill_extraction_v3`
- **Gold set:** 49 postings, 672 gold skills (`data\gold\gold_labels.csv`).
  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected. The extractor is not one of the suggesting models.
- **Coverage:** 49 of 50 gold postings scored; NOT scored (failed or not run): li_3902780709.
- **Evidence check:** 97% of predicted evidence phrases occur verbatim in the posting.

## Overall (micro-averaged)

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| **All** | 49 | 672 | 1169 | 0.41 | 0.71 | 0.52 | 0.48 | 0.83 | 0.61 |

## By sector

| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |
|---|---|---|---|---|---|---|---|---|---|
| Admin / HR / Customer Service | 4 | 43 | 92 | 0.39 | 0.84 | 0.53 | 0.42 | 0.91 | 0.58 |
| Engineering | 3 | 38 | 98 | 0.28 | 0.71 | 0.40 | 0.38 | 0.97 | 0.54 |
| Finance + Accounting | 6 | 106 | 192 | 0.33 | 0.60 | 0.43 | 0.44 | 0.79 | 0.56 |
| Health Care | 8 | 72 | 126 | 0.36 | 0.62 | 0.45 | 0.42 | 0.74 | 0.54 |
| IT | 9 | 203 | 277 | 0.59 | 0.81 | 0.68 | 0.66 | 0.90 | 0.76 |
| Legal | 4 | 41 | 43 | 0.56 | 0.59 | 0.57 | 0.70 | 0.73 | 0.71 |
| Management | 5 | 50 | 98 | 0.33 | 0.64 | 0.43 | 0.37 | 0.72 | 0.49 |
| Mixed | 4 | 52 | 117 | 0.26 | 0.60 | 0.37 | 0.36 | 0.81 | 0.50 |
| Sales + Marketing | 6 | 67 | 126 | 0.42 | 0.79 | 0.55 | 0.45 | 0.85 | 0.59 |

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

Total for the 49 scored postings (each paid once, cached after): **67,001 input** and **205,847 output** tokens (output includes thinking tokens). Per-run log (`reports/token_usage.csv`):

| run_at | provider | model | prompt_version | postings | api_calls | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|
| 2026-10-20T20:59:48+00:00 | openrouter | nvidia/nemotron-3-ultra-550b-a55b:free | skill_extraction_v3 | 1 | 1 | 1127 | 3125 |
| 2026-10-20T21:44:23+00:00 | openrouter | nvidia/nemotron-3-ultra-550b-a55b:free | skill_extraction_v3 | 50 | 48 | 65874 | 202722 |

## Error samples (lenient)

**Missed gold skills (false negatives), first 25:**

- #2: sales plans
- #2: client relationships
- #8: organizational
- #10: verification and validation
- #11: infection control
- #11: equipment maintenance
- #11: Urology
- #13: distribution
- #13: warehousing
- #13: OSHA standards
- #13: cycle counts
- #13: reading
- #13: legible writing
- #19: relational databases
- #19: query authoring
- #19: data warehouse
- #19: data models
- #21: IT Governance and Controls
- #21: Data Flow Analysis
- #21: Audit Reporting
- #21: Stakeholder Presentation
- #29: statistical models
- #29: statistical software
- #29: attention to detail
- #30: cycle counts

**Extra predicted skills (false positives), first 25:**

- #2: sales planning
- #2: business development
- #2: relationship building
- #2: marketing activities
- #2: competitor analysis
- #2: customer feedback analysis
- #2: cross-functional collaboration
- #2: sales reporting
- #2: residential solar
- #2: inverters
- #2: consumer electronics
- #2: mobile energy storage
- #2: services
- #2: energy industry
- #2: business expansion
- #2: independent thinking
- #2: logical thinking
- #2: teamwork
- #5: Outbound sales
- #5: B2B sales
- #5: Sales outreach
- #5: Sales narrative articulation
- #5: Meeting setting
- #5: Pipeline management
- #5: CRM tracking
