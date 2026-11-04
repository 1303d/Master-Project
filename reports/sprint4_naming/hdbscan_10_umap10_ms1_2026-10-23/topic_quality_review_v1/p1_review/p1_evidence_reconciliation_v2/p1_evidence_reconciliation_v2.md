# Sprint 4 — P1 evidence reconciliation v2

> Read-only. Every extraction record is **AI-generated** (model column) and **not manually reviewed** (review_status = not_manually_reviewed). Flags below are **candidates for human review**, not confirmed errors. Nothing was renamed, merged, split, reassigned or excluded.

## Validation

| Check | Expected | Observed |
|---|---|---|
| p1_topics | 20 | 20 |
| p1_skills | 976 | 976 |
| membership_records | 976 | 976 |
| linked_records | 2013 | 2013 |
| unmapped_aliases | 0 | 0 |
| missing_p1_members | 0 | 0 |
| duplicate_statement_ids | 0 | 0 |

Also checked: alias_key unique; frozen snapshot hashes equal its manifest; one topic per P1 skill and it equals the v1 topic; per-skill mention and posting counts equal `reports/sprint3_noise.xlsx`; inputs and protected files byte-identical after the run.

## Evidence classes

| Class | What it proves | Records / skills |
|---|---|---|
| Extraction | an AI extractor (claude-haiku-5-5 1975, qwen/qwen3.8-27b 38) produced this skill with this quote | 2013 records, 967 postings |
| Posting context, verified | the quote occurs in a local copy of that posting (contact-masked) | 1996 records (4 after whitespace/case normalisation) |
| Posting context, not found | local text exists but the quote is not in it (masking or paraphrase) | 17 records |
| Posting text unavailable | no local copy of that posting | 0 records |
| Human review | Sprint 3 noise-review decision (weak members only) | 409 skills |

Evidence corrections: 0 records differ from original_evidence and 0 from original_skill. Records reached through a normalisation rule: 70. 775 of 976 P1 skills occur in exactly one posting.

## Candidates for human review (rule-based)

| Flag | Skills | Rule |
|---|---|---|
| ambiguous_acronym | 291 | short code, no matching confident link, no expansion in any quote |
| generic_noun | 149 | single dictionary word, no matching confident link |
| reference_mapping | 65 | confident link label shares no word with the skill |
| conflicting_meaning | 88 | ≥2 postings whose quotes share no content word |
| any of the above | 461 | — |

## Topics

| Topic | Name | Skills (a/w) | Records | Postings | Context verified | Human decisions | Acronym | Generic | Ref map | Conflict | Any |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T0018 | Software Development Tools | 69 (30/39) | 252 | 162 | 252 | 39 | 12 | 18 | 3 | 6 | 29 |
| T0040 | Flexible Adaptability | 66 (28/38) | 161 | 152 | 160 | 38 | 3 | 16 | 4 | 4 | 21 |
| T0057 | C++ and .NET Development | 61 (33/28) | 150 | 115 | 149 | 28 | 5 | 2 | 1 | 2 | 9 |
| T0103 | Enterprise System Acronyms | 83 (40/43) | 125 | 114 | 123 | 43 | 52 | 7 | 3 | 8 | 58 |
| T0104 | Mixed Technical Codes | 56 (38/18) | 85 | 72 | 85 | 18 | 31 | 4 | 1 | 4 | 37 |
| T0121 | Acronym-Based Technical Standards | 56 (40/16) | 71 | 60 | 69 | 16 | 37 | 2 | 2 | 7 | 40 |
| T0135 | Acronym-Based Technical Standards | 58 (34/24) | 80 | 69 | 78 | 24 | 36 | 4 | 1 | 5 | 40 |
| T0140 | Garment and Lens Fitting | 38 (33/5) | 411 | 388 | 409 | 5 | 1 | 5 | 14 | 11 | 21 |
| T0162 | R Programming Tools | 42 (25/17) | 63 | 57 | 63 | 17 | 13 | 12 | 0 | 6 | 23 |
| T0171 | Site and User Journey Design | 34 (29/5) | 49 | 44 | 49 | 5 | 0 | 0 | 2 | 3 | 5 |
| T0172 | Quantity Take-Offs and Restructuring | 58 (30/28) | 74 | 67 | 74 | 28 | 2 | 16 | 3 | 5 | 22 |
| T0177 | Bill of Materials Management | 55 (31/24) | 68 | 57 | 67 | 24 | 39 | 4 | 4 | 5 | 40 |
| T0190 | Materials Preparation and Planning | 36 (27/9) | 49 | 41 | 48 | 9 | 0 | 1 | 4 | 2 | 6 |
| T0192 | Rigging and Surface Finishing | 48 (26/22) | 76 | 61 | 76 | 22 | 0 | 4 | 5 | 5 | 10 |
| T0193 | Painting and Art Techniques | 25 (23/2) | 35 | 24 | 35 | 2 | 0 | 0 | 1 | 0 | 1 |
| T0211 | Miscellaneous Acronyms and Tools | 77 (23/54) | 108 | 101 | 105 | 54 | 33 | 31 | 2 | 6 | 45 |
| T0229 | Scaling and Growth Terms | 30 (14/16) | 50 | 47 | 49 | 16 | 9 | 15 | 3 | 1 | 18 |
| T0234 | Branded Software Platforms | 41 (22/19) | 56 | 50 | 56 | 19 | 17 | 4 | 1 | 4 | 21 |
| T0239 | Decorative Styling and Decorating | 22 (22/0) | 27 | 18 | 27 | 0 | 0 | 2 | 5 | 2 | 7 |
| T0293 | Sewing and Stitching | 21 (19/2) | 23 | 15 | 22 | 2 | 1 | 2 | 6 | 2 | 8 |

## Examples per flag (first 12 by postings)

- **ambiguous_acronym:** itil (T0104, 7p); apex (T0229, 6p); lean (T0229, 5p); tact (T0211, 5p); s3 (T0104, 5p); paas (T0103, 4p); clia (T0104, 3p); ips (T0103, 3p); iaas (T0103, 3p); cat6 (T0104, 3p); sem (T0177, 3p); ndas (T0103, 3p)
- **generic_noun:** adaptability (T0040, 57p); apex (T0229, 6p); tact (T0211, 5p); lean (T0229, 5p); spring (T0211, 4p); concur (T0211, 4p); lubrication (T0192, 4p); far (T0172, 3p); lambda (T0018, 3p); meta (T0018, 3p); bom (T0177, 3p); it (T0211, 3p)
- **reference_mapping:** alterations (T0140, 5p); sem (T0177, 3p); bom (T0177, 3p); it (T0211, 3p); google (T0018, 3p); garment fitting (T0140, 2p); lens design (T0140, 2p); pressing (T0140, 2p); tailoring (T0140, 2p); rework (T0172, 2p); eyewear fitting (T0140, 2p); finishing (T0192, 2p)
- **conflicting_meaning:** alterations (T0140, 5p); tact (T0211, 5p); iis (T0103, 4p); judgement (T0211, 4p); splunk (T0040, 4p); user experience (T0171, 3p); asana (T0135, 3p); sem (T0177, 3p); bom (T0177, 3p); smp/e (T0121, 3p); wcf (T0121, 3p); templates (T0171, 3p)

## Files

- `p1_extraction_evidence_v2.csv` — one row per linked extraction record (statement_id unique).
- `p1_skill_evidence_summary_v2.csv` — one row per P1 skill: evidence, reference link, human review, candidate flags, AI v1 flags (separate columns).
- `p1_topic_evidence_summary_v2.csv` — one row per P1 topic.
- `manifest.json` — input / output / protected-file hashes, counts, rules.