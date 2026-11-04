# Sprint 4 — P1 evidence investigation (20 topics)

> Read-only investigation. Source evidence comes from files on disk (`p1_evidence_traceability.csv`). **Diagnoses and remediation proposals are AI-generated (Claude Code) and NOT human-validated** — they live in `p1_remediation_proposals.json`. Nothing was deleted, split, merged, renamed or reassigned.

Generated 2026-11-04T17:23:16+00:00 by `src/build_p1_traceability.py`.

## 1. Data lineage found

| Step | Where it lives | Available here? |
|---|---|---|
| 1. Original LinkedIn posting | Kaggle arshkon/linkedin-job-postings -> Supabase `postings` (Sprint 3 corpus). Local copies: 2,000-posting sample (Downloads/sample2000_qwen_v3_2026-10-21_1545/extraction_sample_2000.csv), 50 gold dev postings (data/gold/gold_postings_dev.csv), full JDs embedded in the Sprint 3 noise-review workbooks (reports/noise_review/noise_review_*.xlsx, one example posting per weak skill). data/raw/ is empty on this machine. | partial |
| 2. Extracted skill statement (skill + evidence quote) | Sprint 3 `prepared_mentions.csv` in data/processed/sprint3_full_2026-10-22/ (teammate's machine) and Supabase `statements`. Local: sample2000 Qwen v3 statements (1,005 statements from 87 postings) and the bold-red evidence span in each noise-review JD. | partial: weak members yes (via noise review), assigned members almost never |
| 3. Normalised skill (alias -> skill_key) | sprint4_input snapshot aliases.csv (rules R1-R4 from src/normalize_aliases.py). | yes |
| 4. Sprint 3 membership (assigned / weak, score, margin) | sprint4_input snapshot memberships.csv; posting / mention counts per skill in reports/sprint3_noise.xlsx (Skills sheet). | yes |
| 5. Sprint 4 topic | sprint4_input topics.csv; features; assembled naming results; review workbook. | yes |
| 6. ESCO / O*NET reference link | sprint4_input reference_links.csv (one best candidate per skill, verdict known_skill / new_candidate / trait, score, match type, review_status = auto). | yes |

## 2. Headline counts

| Measure | Count | Basis |
|---|---|---|
| Member skills traced (P1 memberships) | 976 (567 assigned, 409 weak) | memberships.csv |
| Traced to posting count + reference link + alias rows | 940 | sprint3_noise.xlsx, reference_links.csv, aliases.csv |
| With original posting evidence (extractor quote) | 419 | noise-review JDs / sample2000 statements |
| String occurrence in a local posting only (no extraction record) | 480 | text search; NOT extraction evidence |
| Missing source evidence | 77 | — |
| Ambiguous acronyms / codes (rule) | 318 | short code and no lexically matching confident link |
| Suspected extraction errors — confirmed by a Sprint 3 noise reviewer (`not_a_skill`) | 25 | noise-review decision |
| Suspected extraction errors — AI-flagged (assigned + weak) | 23 | AI reading, see JSON |
| Suspected clustering errors — AI-flagged members | 201 | AI reading, see JSON |
| Questionable ESCO/O*NET matches (rule: confident link shares no word with label) | 65 of 283 confident links | rule |
| Questionable ESCO/O*NET matches — AI-confirmed wrong after reading | 27 | AI reading, see JSON |
| Normalisation issues — AI-flagged (variants not merged) | 21 | AI reading, see JSON |

Remediation proposals (AI-generated, not human-validated):

| Proposal | Topics |
|---|---|
| RETAIN_PENDING_REVIEW | 0 |
| RENAME_PENDING_REVIEW | 0 |
| INVESTIGATE_MEMBER_REASSIGNMENT | 5 |
| INVESTIGATE_TOPIC_SPLIT | 4 |
| INVESTIGATE_TOPIC_EXCLUSION | 10 |
| NEEDS_SOURCE_EVIDENCE | 1 |

| Topic | Name | Members (a/w) | Extraction evidence | Text only | None | Ambig. codes (rule) | Reviewer not_a_skill | Diagnosis (AI) | Remediation (AI) |
|---|---|---|---|---|---|---|---|---|---|
| T0018 | Software Development Tools | 30/39 | 43 | 25 | 1 | 12 | 0 | D, C, F | INVESTIGATE_MEMBER_REASSIGNMENT |
| T0040 | Flexible Adaptability | 28/38 | 39 | 26 | 1 | 4 | 5 | A, D, E, C | INVESTIGATE_TOPIC_EXCLUSION |
| T0057 | C++ and .NET Development | 33/28 | 29 | 26 | 6 | 5 | 1 | D, B | INVESTIGATE_MEMBER_REASSIGNMENT |
| T0103 | Enterprise System Acronyms | 40/43 | 43 | 36 | 4 | 55 | 1 | C, D, E, F | INVESTIGATE_TOPIC_EXCLUSION |
| T0104 | Mixed Technical Codes | 38/18 | 18 | 33 | 5 | 34 | 0 | D, C, E, F | INVESTIGATE_TOPIC_EXCLUSION |
| T0121 | Acronym-Based Technical Standards | 40/16 | 17 | 39 | 0 | 43 | 1 | C, D, B, E, F | INVESTIGATE_TOPIC_EXCLUSION |
| T0135 | Acronym-Based Technical Standards | 34/24 | 24 | 31 | 3 | 43 | 2 | C, D, A, B, F | INVESTIGATE_TOPIC_EXCLUSION |
| T0140 | Garment and Lens Fitting | 33/5 | 6 | 23 | 9 | 1 | 1 | D, E, C | INVESTIGATE_TOPIC_SPLIT |
| T0162 | R Programming Tools | 25/17 | 18 | 23 | 1 | 13 | 0 | D, C, A, F | INVESTIGATE_TOPIC_EXCLUSION |
| T0171 | Site and User Journey Design | 29/5 | 6 | 20 | 8 | 0 | 2 | C, F, E | NEEDS_SOURCE_EVIDENCE |
| T0172 | Quantity Take-Offs and Restructuring | 30/28 | 29 | 25 | 4 | 3 | 2 | D, A, C, F | INVESTIGATE_TOPIC_SPLIT |
| T0177 | Bill of Materials Management | 31/24 | 24 | 29 | 2 | 43 | 1 | C, D, E, B, F | INVESTIGATE_TOPIC_EXCLUSION |
| T0190 | Materials Preparation and Planning | 27/9 | 10 | 19 | 7 | 0 | 0 | D, C, E | INVESTIGATE_MEMBER_REASSIGNMENT |
| T0192 | Rigging and Surface Finishing | 26/22 | 24 | 19 | 5 | 0 | 3 | D, C, E | INVESTIGATE_TOPIC_SPLIT |
| T0193 | Painting and Art Techniques | 23/2 | 2 | 14 | 9 | 0 | 0 | D | INVESTIGATE_MEMBER_REASSIGNMENT |
| T0211 | Miscellaneous Acronyms and Tools | 23/54 | 52 | 24 | 1 | 34 | 6 | A, D, C, F | INVESTIGATE_TOPIC_EXCLUSION |
| T0229 | Scaling and Growth Terms | 14/16 | 15 | 15 | 0 | 9 | 0 | A, D, E, C | INVESTIGATE_TOPIC_EXCLUSION |
| T0234 | Branded Software Platforms | 22/19 | 18 | 23 | 0 | 18 | 0 | D, B, C | INVESTIGATE_TOPIC_EXCLUSION |
| T0239 | Decorative Styling and Decorating | 22/0 | 0 | 16 | 6 | 0 | 0 | D, E | INVESTIGATE_TOPIC_SPLIT |
| T0293 | Sewing and Stitching | 19/2 | 2 | 14 | 5 | 1 | 0 | D, C, E | INVESTIGATE_MEMBER_REASSIGNMENT |

Diagnosis codes: A extraction error · B normalisation error · C ambiguous, needs context · D clustering error · E incorrect reference link · F insufficient evidence.

## 3. Evidence gaps

- Sprint 3 mention-level data (prepared_mentions.csv: posting_id + skill + evidence for every statement) is not on this machine and Supabase was not queried (read-only, no external calls). This is why 553 of 567 assigned members have no extraction record here.
- For assigned members, the CSV shows up to 3 string occurrences in locally available postings. These are context hints only: several land on the wrong sense (e.g. 'unity' in 'creativity, innovation, and unity'; 'prisma' in 'Prisma Health'; 'far' in 'how far you can go'; 'r' in a requisition number), which shows why they must not be treated as extraction evidence.
- Weak members have one extraction example each (the noise-review JD) plus a Sprint 3 noise-review decision. Two of the three reviewer files were re-saved (Numbers) and lost the bold evidence spans, so spans were read from the original generated copies; decisions were read from the reviewed copies. Dhanush's decisions are marked 'Claude (please check)' / 'Claude + GPT (please check)' in the file, so they may be AI-suggested.
- 775 of the 976 P1 members occur in exactly one posting (sprint3_noise.xlsx), so most have at most one context to judge from.
- Reference links are automatic (review_status = auto). Several 'exact' matches with score 1.0 are abbreviation collisions with an ESCO alternative label (e.g. sem -> search engine optimisation, rt -> radiotherapy, dmp -> dance therapy).
- ESCO / O*NET broader-group purity is unavailable in the snapshot.

## 4. Per-topic findings

### T0018 — Software Development Tools

Members 30 assigned / 39 weak · extraction evidence 43 · string-only 25 · none 1 · rule-ambiguous codes 12 · reviewer not_a_skill 0 · confident links with no shared word 3

**Confirmed observations (from source files):**

- 30 assigned / 39 weak. Extraction quotes exist for python ('Strong programming skills in Python', 86 postings), java (36), golang (5), scala (4).
- String occurrences place several members in non-programming lists: discord and bluesky in social-media channel lists, reddit with Kajabi/Facebook, bluebeam with construction tools, blue yonder as a 3rd-party supply-chain tool, argus with Word/Excel/PowerPoint.
- 'unity' occurs only as 'creativity, innovation, and unity'; its known_skill link is 'design principles' (match exact, score 1.0).
- 'r programming' is here while 'r', 'r shiny', 'r administration' are in T0162.

**AI interpretation (not human-validated):**

- A coherent core of programming languages and frameworks (python, java, scala, ruby, golang, django, flask, maven, gulp) is mixed with brand / platform names that share letters (blue*, *portal, meta, lucid).
- The 'r programming' / 'r' split across two topics is a clustering artefact of very short strings.
- *Suspected extraction errors (AI):* unity
- *Suspected clustering errors (member does not fit topic) (AI):* discord, reddit, bluesky, blue yonder, bluebeam, bluebeam pdf, hrally portal, argus, meta, lucid, portal
- *Questionable reference links (AI):* unity
- *Normalisation issues (AI):* bluebeam pdf ~ bluebeam

**Diagnosis (AI):** D, C, F · **Remediation (AI):** `INVESTIGATE_MEMBER_REASSIGNMENT`

*Why:* The programming core is real and well evidenced; the brand/social-platform members look attached by string similarity. Reassigning them is a smaller change than splitting the topic.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| python | assigned | 86 | extraction_snippet | known_skill → Python | — |
| java | assigned | 36 | extraction_snippet | known_skill → Java (computer programming) | — |
| docker | weak | 15 | extraction_snippet | known_skill → Docker | skill |
| confluence | assigned | 7 | text_match_only | known_skill → Atlassian Confluence | — |
| slack | weak | 6 | extraction_snippet | known_skill → Slack | skill |
| bluebeam | assigned | 5 | text_match_only | new_candidate → BeamChek | — |
| django | assigned | 5 | text_match_only | known_skill → Django | — |
| golang | assigned | 5 | extraction_snippet | new_candidate → Erlang | — |

### T0040 — Flexible Adaptability

Members 28 assigned / 38 weak · extraction evidence 39 · string-only 26 · none 1 · rule-ambiguous codes 4 · reviewer not_a_skill 5 · confident links with no shared word 4

**Confirmed observations (from source files):**

- 28 assigned / 38 weak. Only 'flexibility' (16 postings) and 'adaptability' (57) match the name.
- String occurrences: 'packages' in 'comprehensive benefits packages', 'box' in 'think outside the box', 'assortment' in 'work an assortment of days', 'containers' in 'Docker containers', 'umbrella' in a Cisco product list (AMP, Umbrella, NAM).
- Links: dock carts -> 'moor vessels' (known_skill), box -> 'types of boxes', boating -> 'teach boating principles'.
- Validity screening = mixed; the earlier Claude validity proposal (not human-confirmed) lists extraction_noise.

**AI interpretation (not human-validated):**

- Most assigned members are physical objects, product names or boilerplate words, and there is no shared meaning; the two real soft skills are transversal and would fit better elsewhere.
- 'packages', 'box', 'assortment' look like extraction errors, but this is based on string occurrences only - the extractor's own quote is not on disk.
- *Suspected extraction errors (AI):* packages, box, assortment, free float
- *Suspected clustering errors (member does not fit topic) (AI):* flexibility, adaptability, containers, flexray, hootsuite, windchill, umbrella, conformal, alignrt, turbocourt, pole foreman, pontoon
- *Questionable reference links (AI):* dock carts, box
- *Normalisation issues (AI):* packing lists ~ packing

**Diagnosis (AI):** A, D, E, C · **Remediation (AI):** `INVESTIGATE_TOPIC_EXCLUSION`

*Why:* No common skill; the name describes 2 of 28 members. Investigate excluding the topic from the hierarchy and reassigning flexibility / adaptability.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| adaptability | assigned | 57 | text_match_only | trait → Adaptability | — |
| flexibility | assigned | 16 | text_match_only | known_skill → perform services in a flexible manner | — |
| collections | weak | 10 | extraction_snippet | known_skill → art collections | skill |
| containers | assigned | 6 | text_match_only | known_skill → types of containers | — |
| splunk | weak | 4 | extraction_snippet | known_skill → Splunk Enterprise | skill |
| hootsuite | assigned | 3 | text_match_only | known_skill → Hootsuite | — |
| solarwinds | weak | 3 | extraction_snippet | known_skill → SolarWinds | skill |
| aspen | weak | 2 | extraction_snippet | known_skill → ASPEN | skill |

### T0057 — C++ and .NET Development

Members 33 assigned / 28 weak · extraction evidence 29 · string-only 26 · none 6 · rule-ambiguous codes 5 · reviewer not_a_skill 1 · confident links with no shared word 1

**Confirmed observations (from source files):**

- 33 assigned / 28 weak. c++ has an extraction quote ('and or C++', 29 postings); c# appears in 16 postings.
- String occurrences: arc flash / arc flash analysis / arc flash mitigation in power-system study lists; 'plasma arc melt' with 'Electron Beam, and VAR furnaces'; 'arc core' in a reading-programme list ('ARC Core, 100 Book Challenge'); 'oasis' in 'All OASIS documentation'; 'delphi' with 'Opera ... PMS/CRM'; 'procore' in a construction posting.
- '.net core' and 'dotnet core' are separate skill keys; dotnet core is linked to 'Visual Studio .NET'.

**AI interpretation (not human-validated):**

- The C++ / .NET / build-tool core is coherent. Members joined by the strings 'arc', 'core' and 'open source' belong to other fields (electrical safety, metallurgy, education, home health, hospitality).
- *Suspected clustering errors (member does not fit topic) (AI):* arc flash, arc flash analysis, arc flash mitigation, plasma arc melt, arc core, oasis, delphi, procore, core text, cxone
- *Normalisation issues (AI):* dotnet core ~ .net core, .net development ~ .net

**Diagnosis (AI):** D, B · **Remediation (AI):** `INVESTIGATE_MEMBER_REASSIGNMENT`

*Why:* The name fits the core; about 10 string-matched members should be checked for reassignment. The current name could likely be retained after that.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| c++ | assigned | 29 | extraction_snippet | known_skill → C++ | — |
| c# | assigned | 16 | text_match_only | known_skill → C# | — |
| terraform | weak | 10 | extraction_snippet | known_skill → IBM Terraform | skill |
| netsuite | weak | 9 | extraction_snippet | known_skill → Oracle NetSuite | alias |
| spring boot | weak | 7 | extraction_snippet | known_skill → Spring Boot | skill |
| .net | assigned | 6 | text_match_only | known_skill → Visual Studio .NET | — |
| github | assigned | 5 | text_match_only | known_skill → GitHub | — |
| procore | assigned | 4 | text_match_only | known_skill → Procore software | — |

### T0103 — Enterprise System Acronyms

Members 40 assigned / 43 weak · extraction evidence 43 · string-only 36 · none 4 · rule-ambiguous codes 55 · reviewer not_a_skill 1 · confident links with no shared word 3

**Confirmed observations (from source files):**

- 40 assigned / 43 weak; validity screening = surface_form_cluster (acronym share 0.85).
- Expansions present in posting text: 'Manufacturing Execution System (MES)'. Most other acronyms appear only in lists without an expansion.
- 'ats' (assigned) and 'ats units' (weak, 'UPS systems, ATS units') co-exist; the extraction context for 'ats' is not on disk.
- Links: ifrs -> 'visual flight rules', ifsp -> 'visual flight rules', ams -> 'use aeronautical mobile service communications', nam -> 'NAMD' (all known_skill).
- Noise-review decisions for weak members include not_a_skill (asee), alias (pos, accepted abbreviations), unsure (submittals).

**AI interpretation (not human-validated):**

- Grouped by letter shape (three-letter codes ending in -s), not meaning. Several acronyms are ambiguous and cannot be disambiguated without the extraction record.
- *Suspected clustering errors (member does not fit topic) (AI):* ansys, ishikawa, ecosys, mesos, unisys 2200, sla management, ledes ids
- *Questionable reference links (AI):* ifrs, ifsp, ams, nam
- *Normalisation issues (AI):* slas ~ sla management, mes/mom ~ mes

**Diagnosis (AI):** C, D, E, F · **Remediation (AI):** `INVESTIGATE_TOPIC_EXCLUSION`

*Why:* Surface-form cluster; hierarchy treatment is already exclude_until_reclustered. Ambiguous acronyms need their extraction record before any reassignment.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| pos systems | weak | 12 | extraction_snippet | new_candidate → System3 POS software | skill |
| slas | assigned | 6 | text_match_only | new_candidate → Lua | — |
| paas | assigned | 4 | text_match_only | new_candidate → Platform as a service PaaS | — |
| iis | assigned | 4 | text_match_only | known_skill → Microsoft Internet Information Services (IIS) | — |
| ams360 | assigned | 3 | text_match_only | known_skill → AMS Services AMS 360 | — |
| iaas | assigned | 3 | text_match_only | new_candidate → integrated circuits | — |
| ids | assigned | 3 | text_match_only | new_candidate → Intrusion detection system IDS | — |
| ndas | weak | 3 | extraction_snippet | new_candidate → National Geophysical Data Center GEODAS | skill |

### T0104 — Mixed Technical Codes

Members 38 assigned / 18 weak · extraction evidence 18 · string-only 33 · none 5 · rule-ambiguous codes 34 · reviewer not_a_skill 0 · confident links with no shared word 1

**Confirmed observations (from source files):**

- 38 assigned / 18 weak; validity = surface_form_cluster (digit share 0.66).
- String occurrences: cat5 / cat6 / cat5e in cabling lists; ho3-ho6 in a list 'insurance contracts to include HO3, HO4, HO5 HO6'; 5s with 'Housekeeping'; a3 with '8Ds, Kaizen, A3, Ishikawa'; s3 in 'AWS services such as S3'; rt in an NDT method list 'PT, MT, UT, RT, ET'.
- rt is linked to 'radiotherapy' (known_skill, match exact, score 1.0).
- catia, catia v5, catia v6 are three keys; primavera, primavera 6, primavera p6, p6, oracle p6 are five keys.

**AI interpretation (not human-validated):**

- Members are tied together by digits and short letter codes from unrelated domains (networking, CAD, lean, insurance, cloud, scheduling). Variants of the same tool are not merged.
- *Suspected clustering errors (member does not fit topic) (AI):* cat5, cat6, cat5e, catia, catia v5, catia v6, 5s, 5 why, a3, ho3, ho4, ho5, ho6, s3, 3pl, primavera, primavera p6, p6
- *Questionable reference links (AI):* rt
- *Normalisation issues (AI):* catia v5 ~ catia, primavera p6 ~ primavera 6, oracle p6 ~ p6

**Diagnosis (AI):** D, C, E, F · **Remediation (AI):** `INVESTIGATE_TOPIC_EXCLUSION`

*Why:* No shared skill; members belong to many other topics. Already exclude_until_reclustered in validity screening.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| 5s | assigned | 9 | text_match_only | new_candidate → geometry | — |
| itil | weak | 7 | extraction_snippet | new_candidate → apply operations for an ITIL-based environment | skill |
| s3 | assigned | 5 | text_match_only | new_candidate → Amazon Simple Storage Service S3 | — |
| clia | assigned | 3 | text_match_only | new_candidate → Clinical Software Solutions CLIN1 Suite | — |
| 3pl | assigned | 3 | text_match_only | known_skill → 3PL Central | — |
| cat6 | assigned | 3 | text_match_only | new_candidate → PHP | — |
| blackline | weak | 2 | extraction_snippet | new_candidate → memorise script | skill |
| primavera | assigned | 2 | text_match_only | new_candidate → Primavera Cost Management | — |

### T0121 — Acronym-Based Technical Standards

Members 40 assigned / 16 weak · extraction evidence 17 · string-only 39 · none 0 · rule-ambiguous codes 43 · reviewer not_a_skill 1 · confident links with no shared word 2

**Confirmed observations (from source files):**

- 40 assigned / 16 weak; validity = surface_form_cluster (acronym share 0.85). Same provisional name as T0135.
- Expansions present in text: 'Microsoft Team Foundation Server (TFS)', 'Transit Feed Specification (GTFS)', 'Lean Sigma DMAIC framework'.
- dmp and dmps are both linked to 'dance therapy' (known_skill, exact, 1.0); string occurrences are in a marketing data-platform list ('DMP, CDP, Data Onboarders'; 'DSPs, SSPs, DMPs').
- 'dsm' ('diagnosing according to the DSM') and 'dsm v' ('DSM-V/ICD 10') are separate keys; 'pfema' occurs as 'pFEMA, control plan' while 'pfmea' is a weak member of T0135.

**AI interpretation (not human-validated):**

- Grouped by the letters d/f/m/s. Several variants of one term are split across keys or topics.
- *Suspected clustering errors (member does not fit topic) (AI):* figma, jamf, nuovafima, ccc1, demarc extensions
- *Questionable reference links (AI):* dmp, dmps
- *Normalisation issues (AI):* dmps ~ dmp, dsm v ~ dsm, pfema ~ pfmea

**Diagnosis (AI):** C, D, B, E, F · **Remediation (AI):** `INVESTIGATE_TOPIC_EXCLUSION`

*Why:* Surface-form cluster (exclude_until_reclustered). Do not merge with T0135 despite the shared name: both are acronym noise.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| figma | assigned | 4 | text_match_only | known_skill → Figma | — |
| wcf | assigned | 3 | text_match_only | new_candidate → Cisco Systems Cisco Web Cache Communication Protocol WCCP | — |
| smp/e | assigned | 3 | text_match_only | new_candidate → surface-mount technology | — |
| dfar | assigned | 3 | text_match_only | new_candidate → dance therapy | — |
| dmp | assigned | 2 | text_match_only | known_skill → dance therapy | — |
| racf | assigned | 2 | text_match_only | known_skill → IBM Resource Access Control Facility RACF | — |
| fiori | weak | 2 | extraction_snippet | new_candidate → in-circuit test | skill |
| dmm | assigned | 2 | text_match_only | new_candidate → dance therapy | — |

### T0135 — Acronym-Based Technical Standards

Members 34 assigned / 24 weak · extraction evidence 24 · string-only 31 · none 3 · rule-ambiguous codes 43 · reviewer not_a_skill 2 · confident links with no shared word 1

**Confirmed observations (from source files):**

- 34 assigned / 24 weak; validity = surface_form_cluster (acronym share 0.79). Same provisional name as T0121.
- String occurrences: 'MSA Safety is the perfect...' (employer name), 'here at Prisma Health' (employer name), 'Multiple Sleep Latency Test (MSLT)'; fmla / flsa with 'Title VII, ADA ... FEHA, PAGA'.
- 'msds' and 'msds sheets' are separate keys. Weak 'hsa' and 'hse' have reviewer decision not_a_skill.

**AI interpretation (not human-validated):**

- Letter-shape cluster mixing employment law, safety, software and clinical tests. 'msa' and 'prisma' may be employer names picked up by extraction, but the extractor's quote is not on disk, so this is unconfirmed.
- *Suspected extraction errors (AI):* msa, prisma
- *Suspected clustering errors (member does not fit topic) (AI):* asana, akamai, jpa, coda, mslt, scd boots
- *Normalisation issues (AI):* msds sheets ~ msds

**Diagnosis (AI):** C, D, A, B, F · **Remediation (AI):** `INVESTIGATE_TOPIC_EXCLUSION`

*Why:* Surface-form cluster (exclude_until_reclustered); possible employer-name extraction errors need their extraction records.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| fmla | assigned | 5 | text_match_only | new_candidate → Relex FMEA | — |
| msds | assigned | 4 | text_match_only | new_candidate → Material safety data sheet MSDS software | — |
| sas | weak | 4 | extraction_snippet | known_skill → SAS | skill |
| asana | assigned | 3 | text_match_only | known_skill → Asana | — |
| fmea | assigned | 3 | text_match_only | known_skill → SKILL FMEA software | — |
| prisma | assigned | 3 | text_match_only | new_candidate → operate surveying instruments | — |
| san | weak | 2 | extraction_snippet | new_candidate → hardware testing methods | skill |
| jde | weak | 2 | extraction_snippet | new_candidate → Java (computer programming) | skill |

### T0140 — Garment and Lens Fitting

Members 33 assigned / 5 weak · extraction evidence 6 · string-only 23 · none 9 · rule-ambiguous codes 1 · reviewer not_a_skill 1 · confident links with no shared word 14

**Confirmed observations (from source files):**

- 33 assigned / 5 weak; 25/33 have confident links, but the links themselves point to different fields (alter wearing apparel, dispense corrective lenses, tend punch press, operate drill press).
- Extraction quote: dressing changes = 'Perform dressing changes'; it is linked to 'alter wearing apparel'.
- String occurrences: 'Google Sheets' for sheets; 'a pressing business problem' for pressing; 'Brocade SAN Fabric'; 'punch down patch panels' with CAT5e wiring.
- Weak 'attention to detail' (359 postings) has reviewer decision trait.

**AI interpretation (not human-validated):**

- Three themes joined by the words fit / press / punch: garment fitting and tailoring, optical lens fitting, and industrial presses. 'dressing changes' is a wound-care task wrongly linked to clothing.
- *Suspected extraction errors (AI):* pressing
- *Suspected clustering errors (member does not fit topic) (AI):* presses, drill presses, punch press, extrusion press, punch list, punch down, san fabric, sheets, dressing changes, form/fit/function, fitment, club fitting, pap mask fitting
- *Questionable reference links (AI):* dressing changes, pressing, lens options, extrusion press

**Diagnosis (AI):** D, E, C · **Remediation (AI):** `INVESTIGATE_TOPIC_SPLIT`

*Why:* Each theme is coherent on its own (garment vs optical vs presses), so a split is the natural candidate; the garment part may relate to T0293.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| attention to detail | weak | 359 | extraction_snippet | trait → Attention to Detail | trait |
| alterations | assigned | 5 | text_match_only | known_skill → adjust clothes | — |
| pressing | assigned | 2 | text_match_only | known_skill → milling machines | — |
| steam fitting | weak | 2 | extraction_snippet | new_candidate → regulate steam pressure | skill |
| contact lens dispensing | assigned | 2 | unavailable | known_skill → dispense corrective lenses | — |
| lens design | assigned | 2 | text_match_only | known_skill → optical components | — |
| drill presses | assigned | 2 | text_match_only | known_skill → operate drill press | — |
| garment marking | assigned | 2 | unavailable | new_candidate → evaluate garment quality | — |

### T0162 — R Programming Tools

Members 25 assigned / 17 weak · extraction evidence 18 · string-only 23 · none 1 · rule-ambiguous codes 13 · reviewer not_a_skill 0 · confident links with no shared word 0

**Confirmed observations (from source files):**

- 25 assigned / 17 weak; coverage 8%.
- String occurrences: 'R programming, R shiny / R Markdown', 'R administration'; for 'r' the only local occurrence is a requisition code 'R-0421175'; 'arm' in 'repetitive hand and arm motions'; 'sabre' in travel booking; 'archer' as 'Archer/CIT eGRC tool'.
- Extraction quote: redtail = 'Redtail and Charles Schwab platforms are a plus'.

**AI interpretation (not human-validated):**

- A small R-language core (r, r shiny, r administration) plus many tools whose names start with r / contain 'red'. 'arm' looks like a physical-demand phrase, not a skill, but the extraction record is missing.
- *Suspected extraction errors (AI):* arm
- *Suspected clustering errors (member does not fit topic) (AI):* redcap, rhel, redhat, redtail, sabre, archer, crestron, rubrik, erwin, dagger, dovetail, nadcap, red rides, pls pole, ike
- *Normalisation issues (AI):* redhat ~ rhel

**Diagnosis (AI):** D, C, A, F · **Remediation (AI):** `INVESTIGATE_TOPIC_EXCLUSION`

*Why:* The R core is 3-4 members and is split from 'r programming' (T0018); the rest is string-similar noise. Investigate exclusion and moving the R core.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| r | assigned | 11 | text_match_only | known_skill → R | — |
| redis | weak | 4 | extraction_snippet | known_skill → Redis | skill |
| rhel | assigned | 3 | text_match_only | new_candidate → R | — |
| crestron | assigned | 2 | text_match_only | new_candidate → Oberon | — |
| redcap | assigned | 2 | text_match_only | new_candidate → REDCap Research Electronic Data Capture | — |
| dovetail | assigned | 2 | text_match_only | new_candidate → handle feathers | — |
| sentinel | weak | 2 | extraction_snippet | known_skill → Microsoft Azure Sentinel | skill |
| rs232 | weak | 2 | extraction_snippet | new_candidate → geographic information systems | skill |

### T0171 — Site and User Journey Design

Members 29 assigned / 5 weak · extraction evidence 6 · string-only 20 · none 8 · rule-ambiguous codes 0 · reviewer not_a_skill 2 · confident links with no shared word 2

**Confirmed observations (from source files):**

- 29 assigned / 5 weak; validity = mixed.
- String occurrences show different senses of 'site': 'SharePoint site development', 'landscape design, grading, site planning', 'clinical site start-up', 'construction-specific areas of Site Handler'.
- site development and site planning are both linked to 'prepare building site'; design experience -> 'think creatively' (exact, 1.0).
- Weak 'mr experience' and 'go live' have reviewer decision not_a_skill.

**AI interpretation (not human-validated):**

- The UX / journey core (user journeys, journey mapping, user experience, user stories, sitemapping, journey builder) is coherent; 'site' members mix web, construction and clinical-trial meanings. All assigned-member contexts are string occurrences, not extraction records.
- *Suspected extraction errors (AI):* computer experience, design experience
- *Suspected clustering errors (member does not fit topic) (AI):* site planning, site start up, site handler, route navigation apps, virtual worlds, arm templates
- *Questionable reference links (AI):* site development, design experience
- *Normalisation issues (AI):* journey building ~ journey builder, user journey maps ~ journey mapping

**Diagnosis (AI):** C, F, E · **Remediation (AI):** `NEEDS_SOURCE_EVIDENCE`

*Why:* Whether 'site' members are web or construction / clinical can only be settled with the extraction records (prepared_mentions / Supabase statements). Possible POTENTIAL_MERGE with T0123 depends on that.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| user stories | assigned | 7 | text_match_only | new_candidate → summarise stories | — |
| dynamics 365 | weak | 5 | extraction_snippet | known_skill → Microsoft Dynamics | skill |
| templates | assigned | 3 | text_match_only | known_skill → Template design software | — |
| user experience | assigned | 3 | text_match_only | known_skill → combine business technology with user experience | — |
| multi site management | assigned | 2 | text_match_only | unavailable →  | — |
| site experience | assigned | 1 | extraction_snippet | new_candidate → design customer experiences | — |
| arm templates | assigned | 1 | unavailable | new_candidate → Template design software | — |
| website updating | assigned | 1 | unavailable | new_candidate → manage website | — |

### T0172 — Quantity Take-Offs and Restructuring

Members 30 assigned / 28 weak · extraction evidence 29 · string-only 25 · none 4 · rule-ambiguous codes 3 · reviewer not_a_skill 2 · confident links with no shared word 3

**Confirmed observations (from source files):**

- 30 assigned / 28 weak; cos_min 0.652.
- String occurrences: 'quantity take-offs', 'electronic take-offs', 'door take-offs' (estimating); 'consolidating adjustments and eliminations' (accounting); 'terminations' in an HR list; 'less' in 'won't strive for anything less'; 'far' in 'see how far you can go'; 'circulate' in 'Scrub and/or circulate general surgery'; 'phasing' with Dynamo (BIM).
- Extraction quote: rooming = 'standard rooming responsibilities'.
- Weak 'retractor handling' and 'shrink' have reviewer decision not_a_skill.

**AI interpretation (not human-validated):**

- Two real subgroups (construction take-offs; financial consolidation) plus single words from unrelated contexts. 'less' and 'far' look like extraction errors, but only string occurrences are available ('far' may also be an acronym in its real extraction context).
- *Suspected extraction errors (AI):* less, far, rooming, working backwards, adjustment
- *Suspected clustering errors (member does not fit topic) (AI):* circulate, phasing, terminations, redundancy, feeders, door strikes, farcaster, lookback, flighting, obsolescence, rework
- *Normalisation issues (AI):* consolidations ~ consolidating adjustments

**Diagnosis (AI):** D, A, C, F · **Remediation (AI):** `INVESTIGATE_TOPIC_SPLIT`

*Why:* The take-off members form a coherent subgroup worth keeping; the rest should be split off or reassigned after their extraction records are checked.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| after effects | weak | 4 | extraction_snippet | known_skill → Adobe After Effects | skill |
| take offs | assigned | 4 | text_match_only | unavailable →  | — |
| far | assigned | 3 | text_match_only | new_candidate → Persian | — |
| consolidations | assigned | 3 | text_match_only | new_candidate → combination of textures | — |
| rework | assigned | 2 | text_match_only | known_skill → repair patterns | — |
| receivers | weak | 2 | extraction_snippet | new_candidate → broadcast equipment | skill |
| intune | weak | 2 | extraction_snippet | new_candidate → Intusoft ICAP | skill |
| electronic take offs | assigned | 2 | text_match_only | unavailable →  | — |

### T0177 — Bill of Materials Management

Members 31 assigned / 24 weak · extraction evidence 24 · string-only 29 · none 2 · rule-ambiguous codes 43 · reviewer not_a_skill 1 · confident links with no shared word 4

**Confirmed observations (from source files):**

- 31 assigned / 24 weak; validity = surface_form_cluster (acronym share 0.84).
- Expansions present in text: 'Product Lifecycle Management (PLM)', 'Building Information Modeling (BIM)', 'Transportation Management System (TMS)'.
- sem occurs in an analytical-technique list ('GPC, FTIR, NMR, SEM, XPS') and is linked to 'search engine optimisation' (exact, 1.0). wpm occurs as 'Typing speed of 50 wpm'.
- tpm and tpms are separate keys.

**AI interpretation (not human-validated):**

- Only the BOM / PLM members match the name; the rest are three-letter codes ending in -m from many domains.
- *Suspected extraction errors (AI):* wpm
- *Suspected clustering errors (member does not fit topic) (AI):* bim, tms, sem, veeam, ohm's law, cyme, t1, ipam, uvm
- *Questionable reference links (AI):* sem, tdm
- *Normalisation issues (AI):* tpms ~ tpm

**Diagnosis (AI):** C, D, E, B, F · **Remediation (AI):** `INVESTIGATE_TOPIC_EXCLUSION`

*Why:* Surface-form cluster (exclude_until_reclustered); the BOM / PLM core (bom, bom analysis, bom creation, plm) could be reassigned.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| itsm | weak | 4 | extraction_snippet | new_candidate → search engine optimisation | skill |
| postman | weak | 3 | extraction_snippet | known_skill → Postman | skill |
| bom | assigned | 3 | text_match_only | known_skill → draft bill of materials | — |
| sem | assigned | 3 | text_match_only | known_skill → search engine optimisation | — |
| bim | assigned | 2 | text_match_only | new_candidate → MOEM | — |
| gpm | weak | 2 | extraction_snippet | new_candidate → gel permeation chromatography | skill |
| iam | weak | 2 | extraction_snippet | new_candidate → CA IDMS | skill |
| t1 | assigned | 2 | text_match_only | new_candidate → sK1 | — |

### T0190 — Materials Preparation and Planning

Members 27 assigned / 9 weak · extraction evidence 10 · string-only 19 · none 7 · rule-ambiguous codes 0 · reviewer not_a_skill 0 · confident links with no shared word 4

**Confirmed observations (from source files):**

- 27 assigned / 9 weak; validity = coherent (rules).
- String occurrences: 'Material design guidelines and Human Interface guidelines' (UI design); 'administering contrast materials, and positioning patients' (radiology); 'explant preparation'; 'soybean transformation or genome editing'; 'make-ready program for the property'; 'the formulation of action plans'.
- Extraction quote: reagent preparation = 'Prepare the stains and reagents'.
- formulation -> 'food product ingredients' (known_skill).

**AI interpretation (not human-validated):**

- Most members share the word 'material(s)' and are broadly about materials; 'preparation' / 'transformation' / 'make ready' members come from lab, medical, UI and property contexts.
- *Suspected clustering errors (member does not fit topic) (AI):* material design guidelines, contrast materials, contrast preparation, drug preparation, explant preparation, soybean transformation, make ready process, make ready program, time and material
- *Questionable reference links (AI):* formulation

**Diagnosis (AI):** D, C, E · **Remediation (AI):** `INVESTIGATE_MEMBER_REASSIGNMENT`

*Why:* A broad materials topic is defensible; about 9 word-matched members from other fields should be checked for reassignment.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| material handling | weak | 6 | extraction_snippet | known_skill → operate material handling equipment | skill |
| construction materials | assigned | 4 | text_match_only | known_skill → advise on construction materials | — |
| make ready process | assigned | 4 | unavailable | unavailable →  | — |
| materials planning | assigned | 2 | text_match_only | known_skill → ERP INDUSTRIOS Material Planning | — |
| materials characterization | weak | 2 | extraction_snippet | new_candidate → test materials | skill |
| material fabrication | weak | 1 | extraction_snippet | known_skill → mechanics | skill |
| time and material | assigned | 1 | unavailable | new_candidate → printing materials | — |
| contrast preparation | assigned | 1 | unavailable | known_skill → administer contrast media | — |

### T0192 — Rigging and Surface Finishing

Members 26 assigned / 22 weak · extraction evidence 24 · string-only 19 · none 5 · rule-ambiguous codes 0 · reviewer not_a_skill 3 · confident links with no shared word 5

**Confirmed observations (from source files):**

- 26 assigned / 22 weak.
- String occurrences: 'animation rigging/set-up, and character' (3D animation); 'ground rigging support', 'High rigging with harness'; 'Install Grounding, as required by NECA'; 'tunneling methods like ipsec'; 'material usage and cavitation' (moulding); 'suturing' and 'suture cutting' in clinical lists; 'centrifuging' and 'aliquotting' in specimen handling.
- Extraction quotes: splinting = 'Apply splints, casts, dressings'; suture removal = 'remove sutures with competency'.
- waxing -> 'wax body parts' (known_skill) while the string occurs in car-detailing text ('cleaning and waxing'). Weak 'working at height' and 'floor buffing' have reviewer decision not_a_skill.

**AI interpretation (not human-validated):**

- Three themes: rigging / grounding, surface finishing, and clinical / lab procedures, plus string matches on 'ground' and 'tunnel'. 'rigging' itself may be animation rigging in some postings.
- *Suspected clustering errors (member does not fit topic) (AI):* suturing, suture cutting, suture removal, splinting, sheath removal, centrifuging, aliquotting, tunneling, cavitation, garnishing, ground up construction, ground support equipment
- *Questionable reference links (AI):* waxing

**Diagnosis (AI):** D, C, E · **Remediation (AI):** `INVESTIGATE_TOPIC_SPLIT`

*Why:* Two trade subgroups (rigging, surface finishing) and a clinical subgroup are each coherent; a split is the candidate. T0050 Hand and Power Tool Operation is the near-duplicate for the trade part.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| patience | weak | 9 | extraction_snippet | known_skill → exercise patience | trait |
| working under pressure | weak | 8 | extraction_snippet | trait → cope with pressure | trait |
| lubrication | weak | 4 | extraction_snippet | new_candidate → perform routine lube oil tests | skill |
| hoists | weak | 3 | extraction_snippet | known_skill → operate hoists | skill |
| waxing | assigned | 2 | text_match_only | known_skill → wax body parts | — |
| masking | weak | 2 | extraction_snippet | new_candidate → apply opaque | skill |
| splinting | assigned | 2 | extraction_snippet | new_candidate → maintain ropes | — |
| crimping | assigned | 2 | text_match_only | known_skill → crimping | — |

### T0193 — Painting and Art Techniques

Members 23 assigned / 2 weak · extraction evidence 2 · string-only 14 · none 9 · rule-ambiguous codes 0 · reviewer not_a_skill 0 · confident links with no shared word 1

**Confirmed observations (from source files):**

- 23 assigned / 2 weak; validity = coherent; 11 confident links all to art / painting ESCO skills.
- String occurrences: 'iTero Digital Impressions' and 'CEREC One Day Crowns' (dental); 'artworking of slides Pitch deck'; 'mock-ups, wireframes, and prototypes' (UI design).
- 6 'impression' members (impression materials, impression pouring, custom impression trays, digital impressions, itero digital impressions, impression casts).

**AI interpretation (not human-validated):**

- The painting / art core is coherent. The dental impression members joined through the word 'impression'; mockups belong with UI / design prototyping.
- *Suspected clustering errors (member does not fit topic) (AI):* impression materials, impression pouring, custom impression trays, digital impressions, itero digital impressions, impression casts, mockups, mock ups
- *Normalisation issues (AI):* mock ups ~ mockups

**Diagnosis (AI):** D · **Remediation (AI):** `INVESTIGATE_MEMBER_REASSIGNMENT`

*Why:* Reassigning the 6 dental and 2 mock-up members would probably leave a coherent topic whose current name can be retained.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| painting | assigned | 10 | text_match_only | known_skill → paint surfaces | — |
| mockups | assigned | 2 | text_match_only | known_skill → create mock-ups | — |
| artworking | assigned | 1 | text_match_only | known_skill → create artwork | — |
| paint qualities | assigned | 1 | text_match_only | known_skill → inspect paint quality | — |
| makeup application | weak | 1 | extraction_snippet | known_skill → perform quick make-up changeovers | skill |
| itero digital impressions | assigned | 1 | text_match_only | new_candidate → ITSpatial InterSCOPE | — |
| butterfly method | assigned | 1 | unavailable | new_candidate → floral composition techniques | — |
| art history | assigned | 1 | text_match_only | known_skill → art history | — |

### T0211 — Miscellaneous Acronyms and Tools

Members 23 assigned / 54 weak · extraction evidence 52 · string-only 24 · none 1 · rule-ambiguous codes 34 · reviewer not_a_skill 6 · confident links with no shared word 2

**Confirmed observations (from source files):**

- 23 assigned / 54 weak; validity = mixed.
- String occurrences: 'can' in 'so they can get the most'; 'bob' as a contact person's first name in an application instruction; 'accessibility' in an accessibility-of-our-website notice; 'ot' in a therapy-discipline list 'SN, PT, OT, ST'; 'ilocano' in 'Bilingual in Ilocano and English'.
- Weak 'nyc dep' has reviewer decision not_a_skill; 'tact' and 'judgement' are trait.

**AI interpretation (not human-validated):**

- A noise sink: very short tokens and unrelated product names. 'can', 'bob' and 'accessibility' look like extraction errors, but the extractor's quote is not on disk.
- *Suspected extraction errors (AI):* can, bob, accessibility
- *Suspected clustering errors (member does not fit topic) (AI):* pardot, tenable, snowflake, incopy, siprnet, bobcat, ilocano, black duck, katapult, von duprin, stucky
- *Normalisation issues (AI):* pls ~ pls cadd

**Diagnosis (AI):** A, D, C, F · **Remediation (AI):** `INVESTIGATE_TOPIC_EXCLUSION`

*Why:* No shared skill; the largest noise attractor among P1 (54 weak members, 5 near-duplicate topics).

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| snowflake | assigned | 8 | text_match_only | known_skill → Snowflake | — |
| tact | weak | 5 | extraction_snippet | new_candidate → in-circuit test | trait |
| concur | weak | 4 | extraction_snippet | new_candidate → SAP Concur | skill |
| spring | weak | 4 | extraction_snippet | new_candidate → types of spring | skill |
| judgement | weak | 4 | text_match_only | new_candidate → forensic intelligence | trait |
| comscore | weak | 3 | extraction_snippet | new_candidate → Hyperscore | skill |
| it | weak | 3 | extraction_snippet | known_skill → computer technology | skill |
| rally | weak | 2 | extraction_snippet | new_candidate → motivate supporters | skill |

### T0229 — Scaling and Growth Terms

Members 14 assigned / 16 weak · extraction evidence 15 · string-only 15 · none 0 · rule-ambiguous codes 9 · reviewer not_a_skill 0 · confident links with no shared word 3

**Confirmed observations (from source files):**

- 14 assigned / 16 weak.
- String occurrences: 'Panorama City' (a place name); 'the cornerstone of the enterprise'; 'may give rise to a potential conflict'; 'installing or repairing scales and calibrates' (weighing equipment); 'Salesforce Apex'; 'Video: Axis, Exacq, Milestone' (security cameras); 'COBRA administration' (benefits).
- scales -> 'design principles' (exact, 1.0) and scaling -> 'design principles' (known_skill).

**AI interpretation (not human-validated):**

- Common words and brand names that happen to share letters with 'scale' / 'zoom'. 'rise', 'panorama' and 'cornerstone' look like extraction errors (string-occurrence evidence only).
- *Suspected extraction errors (AI):* rise, panorama, cornerstone
- *Suspected clustering errors (member does not fit topic) (AI):* zoom, zoominfo, apex, axis, lawson, cobra, hardscape, scales
- *Questionable reference links (AI):* scales, scaling

**Diagnosis (AI):** A, D, E, C · **Remediation (AI):** `INVESTIGATE_TOPIC_EXCLUSION`

*Why:* Small topic with no shared skill; the few real tools (zoom, zoominfo, apex, lawson) belong to other topics.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| zoom | assigned | 9 | text_match_only | known_skill → Zoom | — |
| apex | assigned | 6 | text_match_only | new_candidate → Apex Business Software iBenefits | — |
| lean | weak | 5 | extraction_snippet | new_candidate → PQ Systems CHARTrunner Lean | skill |
| axis | assigned | 2 | text_match_only | new_candidate → GGY AXIS | — |
| milestone | weak | 2 | extraction_snippet | known_skill → manage time | skill |
| zscaler | weak | 2 | extraction_snippet | new_candidate → operate scaler | skill |
| scale up | assigned | 1 | text_match_only | unavailable →  | — |
| rotation | weak | 1 | extraction_snippet | new_candidate → centrifugal force | alias |

### T0234 — Branded Software Platforms

Members 22 assigned / 19 weak · extraction evidence 18 · string-only 23 · none 0 · rule-ambiguous codes 18 · reviewer not_a_skill 0 · confident links with no shared word 1

**Confirmed observations (from source files):**

- 22 assigned / 19 weak; validity = surface_form_cluster.
- String occurrences: 'Ciso, Avya, contact center' (misspelt next to 'Ciso'); 'Avaya, Fusion, IPC'; 'Environmental, Health, and Safety (EHS)'; 'Kapton, and Rivnuts onto structures'; 'TCP/IP, EIGRP, BGP'.
- 'avya' and 'avaya' are separate keys.

**AI interpretation (not human-validated):**

- Product names grouped by sound (av-, ak-, ek-, as-). 'avya' is a misspelling of avaya that normalisation did not merge.
- *Suspected clustering errors (member does not fit topic) (AI):* avimark, canva, okta, avalara, eigrp, rivnuts, ehs, eks, akka, ekahau, magaya, aspera
- *Normalisation issues (AI):* avya ~ avaya

**Diagnosis (AI):** D, B, C · **Remediation (AI):** `INVESTIGATE_TOPIC_EXCLUSION`

*Why:* Surface-form cluster (exclude_until_reclustered). Members are real tools but share no skill.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| canva | assigned | 5 | text_match_only | known_skill → Canva | — |
| ariba | weak | 4 | extraction_snippet | known_skill → SAP Ariba | alias |
| kanban | weak | 3 | extraction_snippet | new_candidate → PMC KanbanSIM | skill |
| okta | assigned | 2 | text_match_only | new_candidate → online analytical processing | — |
| kajabi | weak | 2 | extraction_snippet | new_candidate → Punjabi | skill |
| veeva | weak | 2 | extraction_snippet | new_candidate → Vertafore ImageRight | skill |
| avigilon | assigned | 2 | text_match_only | new_candidate → MediGraph | — |
| av systems | weak | 2 | extraction_snippet | known_skill → audiovisual products | skill |

### T0239 — Decorative Styling and Decorating

Members 22 assigned / 0 weak · extraction evidence 0 · string-only 16 · none 6 · rule-ambiguous codes 0 · reviewer not_a_skill 0 · confident links with no shared word 5

**Confirmed observations (from source files):**

- 22 assigned / 0 weak; validity = coherent (rules).
- String occurrences: 'bakery decorative designs', 'cookie decorating', 'decorating bags, tips, nozzles' (bakery); 'Ensure style guides and design principles', 'understand AP Style' (writing / brand); 'mood boards, storyboards and style frames' (motion design); 'Paste print, stencil design, solder inspection' (electronics); 'specified fuel gas and acetylene'.
- Links: styling -> 'hairdressing', food styling -> 'hairdressing', style frames -> 'optical components', spray booth -> 'pump paint' (all known_skill).

**AI interpretation (not human-validated):**

- A bakery / decorating subgroup and a style-guide / design subgroup joined by the words 'style' and 'decor', plus unrelated members (stencil design for solder paste, acetylene, upholstery). The rule-based 'coherent' result does not hold up against the posting contexts.
- *Suspected clustering errors (member does not fit topic) (AI):* style guides, ap style, stylesheets, style frames, stencil design, acetylene, upholstery, spray booth, diverse music styles, booth design
- *Questionable reference links (AI):* styling, food styling, style frames

**Diagnosis (AI):** D, E · **Remediation (AI):** `INVESTIGATE_TOPIC_SPLIT`

*Why:* The bakery-decorating members form one coherent group and the style-guide members another; the rest should be reassigned.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| fashion knowledge | assigned | 3 | text_match_only | new_candidate → advise on clothing style | — |
| styling | assigned | 2 | text_match_only | known_skill → hairdressing | — |
| ap style | assigned | 2 | text_match_only | new_candidate → select illustration styles | — |
| cake decorating | assigned | 2 | text_match_only | new_candidate → decorate pastry for special events | — |
| decorative designs | assigned | 1 | text_match_only | known_skill → paint decorative designs | — |
| diverse music styles | assigned | 1 | text_match_only | known_skill → musical genres | — |
| spray booth | assigned | 1 | text_match_only | known_skill → pump paint | — |
| booth design | assigned | 1 | unavailable | new_candidate → packaging processes | — |

### T0293 — Sewing and Stitching

Members 19 assigned / 2 weak · extraction evidence 2 · string-only 14 · none 5 · rule-ambiguous codes 1 · reviewer not_a_skill 0 · confident links with no shared word 6

**Confirmed observations (from source files):**

- 19 assigned / 2 weak; validity = coherent (rules).
- String occurrences: 'braze' occurs as 'Adobe Campaign, Braze, Salesforce' (a marketing platform list), while 'brazing' / 'brazing alloy' occur as 'Selects torch tip, flux and brazing alloy'; 'classical hand analysis' occurs next to 'NASTRAN/PATRAN, CSW, IAS' (engineering analysis); 'hand scratches from job walks' (construction).
- classical hand analysis -> 'read palms' (known_skill); hand sewing -> 'use manual knitting techniques'.

**AI interpretation (not human-validated):**

- The sewing core is coherent. Brazing is metal joining. 'braze' (marketing platform) shows that merging braze with brazing would be WRONG: an ambiguous string needing context. 'classical hand analysis' is an engineering term wrongly linked to palm reading.
- *Suspected clustering errors (member does not fit topic) (AI):* hand brazing, induction brazing, brazing, brazing alloy, braze, classical hand analysis, hand scratches, hand to surface method
- *Questionable reference links (AI):* classical hand analysis, hand sewing

**Diagnosis (AI):** D, C, E · **Remediation (AI):** `INVESTIGATE_MEMBER_REASSIGNMENT`

*Why:* Reassigning about 8 members would leave a coherent sewing topic whose name could be retained.

Highest-posting members:

| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |
|---|---|---|---|---|---|
| sewing equipment | assigned | 2 | text_match_only | known_skill → dressmaking | — |
| brazing | assigned | 2 | text_match_only | known_skill → apply brazing techniques | — |
| hand sewing | assigned | 1 | text_match_only | known_skill → use manual knitting techniques | — |
| double needle machines | assigned | 1 | unavailable | new_candidate → manufacture weft knitted fabrics | — |
| splint fabrication | weak | 1 | extraction_snippet | new_candidate → mechanics | skill |
| braze | assigned | 1 | text_match_only | new_candidate → operate brazing equipment | — |
| hand scratches | assigned | 1 | text_match_only | new_candidate → operate grinding hand tools | — |
| brazing alloy | assigned | 1 | text_match_only | new_candidate → operate brazing equipment | — |

## 5. Verification

- All 976 P1 members (567 assigned + 409 weak) from memberships.csv are in p1_evidence_traceability.csv, one row each; every member has a posting count (sprint3_noise.xlsx) and alias rows; 36 have no reference_links row.
- Every skill named in this JSON is a P1 member (asserted by src/build_p1_traceability.py).
- Source files and the review workbook have identical sha256 before and after the run (asserted in the script and re-checked with shasum over data/processed and config/topic_validity).
- No LLM / external API calls; Supabase not queried or modified; nothing staged or committed.

Source sha256 (unchanged before/after this run):

- `p1_topic_review` fb6b2d7cfc2fc0803a540881f21b6b9de53366b2386fe56c95e5b42f6075c8b0
- `memberships` 0d6854f6a4e7610fe0a36d4d2653b3ed79861c641fb6cf29a60bdab455de7a37
- `aliases` 3a2bbf7490f394bbdd07297d53255a62e7219929851e524a5afa67810046ee99
- `reference_links` 1543cb2ce7ee3b786dd591cf3a2d5f72918a2294b738304ee517821fcf68a845
- `sprint3_noise_workbook` d102ffada17afbe3716766fa84de8288af23155d152aa11246cf1640aa672c40
- `noise_review_Dhanush` bbf5d860c43fbde640462b60407299d97a24de58086e069e4bec8b19249d88b2
- `noise_review_Lochan` 4be9544ee6a72d856bdaac6c86ce5ad4b5dbd7b64fa0bc749131e75bdeded69a
- `noise_review_Priyanka` e6e7072f1580233fa216a2453d3f14250399b966b7510948058156a423608262
- `noise_review_jd_Dhanush` bbf5d860c43fbde640462b60407299d97a24de58086e069e4bec8b19249d88b2
- `noise_review_jd_Lochan` 67fd2b3f06c9391b215f8d5388d48e422cbae3a45104ae46516206dbaed35967
- `noise_review_jd_Priyanka` 2b26deb52c9c0f058623c12315eeab582af84c93358c95958f24a8dbc2f4ccb6
- `sample2000_statements` 8b7de6962f14727bc89494104c5aa922e38e643910ff193a32f7233613dee984
- `sample2000_postings` be0ede93a5894d9f7ef0f36340dc971c4e39ad4d760e5fffc7a20927292f49b8
- `gold_postings_dev` c5f5ea3ffad2e60efc0e00c667344184237d7d1e3fad2ee354fb8da95798182a