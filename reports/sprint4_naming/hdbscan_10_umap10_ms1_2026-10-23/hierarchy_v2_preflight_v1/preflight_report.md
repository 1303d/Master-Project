# Hierarchy v2 preflight (v1)

> Read-only checks. v1 artifacts, frozen inputs and accepted reference mappings were not changed. Findings and proposed handling are AI-generated and pending human approval.

**Verdict: READY FOR HIERARCHY PROPOSAL V2**

## 1. v1 integrity

| Check | Result |
|---|---|
| output_hashes_ok | True |
| script_hash_ok | True |
| input_hashes_ok | True |
| rerun_identical | True |
| topics | 374 |
| ids_match | True |
| parents | 90 |
| states | {'PLACED': 251, 'PLACED_LOW_CONFIDENCE': 52, 'UNRESOLVED_EXCLUDED': 39, 'UNRESOLVED_SINGLETON': 32} |
| excluded_with_parent | 0 |
| unresolved_with_parent | 0 |

## 2. ESCO levels (corrected)

Source: ~/Desktop/testing/references/esco_v1.2.1 (ESCO v1.2.1 (classification, en, csv)). Levels from `skillsHierarchy_en.csv`; parents from `broaderRelationsSkillPillar_en.csv`.

- Groups per level: {0: 4, 1: 28, 2: 156, 3: 452} (Level 0 = knowledge, language skills and knowledge, skills, transversal skills and competences).
- The audit column `esco_purity_level2` used the first-parent chain's `path[-2]`; for every resolvable link it is a **Level ['1']** group ({'1': 3454}). It is renamed here as `audit_v1_column_esco_purity_level2_is_really_L1`; the audit file is unchanged.
- Corrected metric `esco_purity/2` (`src/esco_levels.py`): explicit level, multi-parent aware (weight 1/|groups|), links whose URI is not in v1.2.1 or that have no ancestor at the level are counted and excluded; ≥ 3 usable links required.
- 4759 ESCO concepts have several broader parents; 778 of our links have > 1 Level 2 ancestor (v1 hierarchy used the first parent only).
- Medians over topics: Level 1 purity 0.456, Level 2 purity 0.400 (311 topics).

## 3. ESCO URI discrepancies (212 links)

Rows: 212; distinct URIs: 103; accepted (`known_skill`) rows: 106 (no lexical overlap with the label: 17); rows on assigned members: 174.

| Class | Links | Distinct URIs |
|---|---:|---:|
| VERSION_MISMATCH | 35 | 15 |
| INVALID_IDENTIFIER | 0 | 0 |
| MISSING_REFERENCE_EXPORT | 168 | 82 |
| INCORRECT_ACCEPTED_MAPPING | 0 | 0 |
| UNRESOLVED | 9 | 6 |

Rule order: invalid URI → Phase 3 confirmed-incorrect accepted link → URI referenced by v1.2.1 (concept scheme / scope note) without a record → label present in v1.2.1 under another URI → unresolved. No accepted mapping was replaced.

## 4. The three 'exact' matches

| Skill | Normalised key | Accepted label | v1.2.1 labels with the same key | Explained by v1.2.1 | Explanation |
|---|---|---|---|---|---|
| unity | unity | design principles | Unity (digital game creation systems) [alt: 'Unity'] | False | no v1.2.1 label of the accepted concept normalises to this key; the match came from the v1.2 API export (data/reference/esco_skills.csv), which is not available locally |
| scales | scale | design principles | none | False | no v1.2.1 label of the accepted concept normalises to this key; the match came from the v1.2 API export (data/reference/esco_skills.csv), which is not available locally |
| design experience | design | think creatively | think creatively [alt: 'design'] | True | normaliser drops filler 'experience' -> ('design',); v1.2.1 'think creatively' has alt label 'design' |

`link_reference.py` marks a match exact when `evaluate.norm` keys are equal; `norm` lower-cases, drops filler words (including 'experience', 'knowledge', 'skill') and strips a plural 's'. All three accepted mappings are wrong in context.

## 5. Hierarchy similarity metrics

- **coherence**: mean pairwise cosine between child-topic centroids (child-child)
- **cos_to_own_parent (v1)**: child centroid vs member-weighted parent centroid that INCLUDES the child (self-inclusive, biased upward)
- **nearest_parent_cos (v1)**: parent centroid vs parent centroid (parent-parent; means of many members, so higher than child-child)
- **verdict**: the three are not on one scale; v1 compared them only implicitly. v2 must use leave-one-out child-to-parent scores.
- Coherence recomputed for all 90 parents: match = True.
- Children closer to another parent: v1 (self-inclusive) 6; leave-one-out **96 of 303**; LOO margin < 0.02: 181.
- v1 never forced an excluded topic into a parent (see section 1).

## 6. Suspicious-parent detection

- v1 flagged 45 parents; its rules are implemented as documented (coherence p10, ESCO share < 0.30 with ≥ 8 links, ≥ 2 split-pending children, nearest parent ≥ 0.95), but none of them measures member-level mixing.
- New member-level rule (sibling member affinity < 0.15 or weakest child pair < 0.75): 29 candidates; not flagged by v1: P015, P019, P026, P029, P037, P038, P045, P048, P050, P054, P056, P080, P084, P086.
- P080 (Keyboarding and Typing | Switching Equipment): {'sibling_member_affinity': 0.125, 'min_child_pair_cos': 0.8509, 'v1_suspicious': False, 'mixing_candidate_v2_rule': True}.
- The new rule is a heuristic: some candidates are sensible pairs of distinct topics (e.g. Recruitment | Onboarding).

| Parent | Children | Sibling affinity | Weakest pair | v1 flag | v2 rule | Child names |
|---|---:|---:|---:|---|---|---|
| P025 | 2 | 0.0 | 0.7685 | True | True | Risk Management | Data Validation and Verification |
| P046 | 2 | 0.0227 | 0.7947 | True | True | SAP ERP Modules | SD-Prefixed Acronyms |
| P003 | 2 | 0.0469 | 0.8081 | True | True | Creative and Strategic Thinking | Storytelling and Storyboarding |
| P026 | 2 | 0.0476 | 0.8607 | False | True | Account Management | Retention and Incentive Programs |
| P019 | 2 | 0.0548 | 0.8372 | False | True | Mathematical Calculations | CAD Software Proficiency |
| P015 | 2 | 0.0794 | 0.8326 | False | True | Regulatory Compliance | Health Information Privacy |
| P056 | 3 | 0.0889 | 0.7892 | False | True | Professional Writing | Legal Document Drafting | Proposal Development |
| P053 | 2 | 0.0943 | 0.8275 | True | True | Reading Comprehension | Technical Drawing Interpretation |
| P070 | 2 | 0.1034 | 0.7995 | True | True | Recruitment and Hiring | Onboarding Processes |
| P033 | 2 | 0.1064 | 0.8268 | True | True | Social Media Management | Digital Advertising Platforms |
| P086 | 2 | 0.1071 | 0.8216 | False | True | System Configuration | Product and Fixture Installation |
| P051 | 3 | 0.1111 | 0.7302 | True | True | Structural Engineering Design | IT Infrastructure Architecture | Welding Processes and Equipment |
| P084 | 2 | 0.1154 | 0.8392 | False | True | Data and Barcode Coding | Technical Codes Knowledge |
| P048 | 2 | 0.1224 | 0.8222 | False | True | Research Methodologies | Chemistry and Physical Sciences |
| P054 | 2 | 0.1228 | 0.8514 | False | True | Culinary Preparation Techniques | Menu Planning and Development |
| P069 | 2 | 0.125 | 0.8401 | True | True | Freight Forwarding Operations | Warehouse Operations Management |
| P080 | 2 | 0.125 | 0.8509 | False | True | Keyboarding and Typing | Switching Equipment |
| P023 | 2 | 0.127 | 0.8592 | True | True | Performance Analysis and Monitoring | Business Metrics Analysis |
| P063 | 3 | 0.1296 | 0.8037 | True | True | KPI Dashboarding | Issue and Project Tracking | Clinical Charting |
| P029 | 3 | 0.1316 | 0.8466 | False | True | Business Analytics | Optimization Techniques | Machine Learning and AI |
| P062 | 6 | 0.1383 | 0.7591 | True | True | Mechanical Engineering Knowledge | HVAC and Refrigeration Systems | Engineering Practices and Reliability | Parts Catalo |
| P013 | 6 | 0.2222 | 0.7176 | True | True | Project Management Methodologies | Agile Development Methodologies | CRM and CAD Systems | Project Implementation Planni |
| P004 | 14 | 0.2882 | 0.7395 | True | True | Microsoft Software Proficiency | Desktop Computer Operations | Shell Scripting | Mobile Device Technologies | Software A |
| P037 | 4 | 0.3053 | 0.7491 | False | True | Quality Management Systems | Policy Administration and Advocacy | Workforce Planning and Staffing | Human Resources Oper |
| P045 | 6 | 0.3071 | 0.7346 | False | True | Cloud Infrastructure Engineering | Microsoft Azure Cloud Services | AWS Cloud Services | IT Virtualization Technologies  |
| P039 | 8 | 0.3582 | 0.7497 | True | True | Product Lifecycle Management | System Integration Architecture | ERP System Administration | System Architecture Design  |
| P058 | 5 | 0.4571 | 0.7377 | True | True | Cash Handling Operations | Billing Processes | Payment Processing | Invoice Processing | Transaction Processing |
| P038 | 9 | 0.4837 | 0.703 | False | True | Accounting Principles | Financial Planning | Audit Procedures | Financial Software Systems | Loan Origination and Lendin |
| P050 | 9 | 0.5476 | 0.6913 | False | True | Process Automation | Industrial Control Systems | Analog and Power Circuit Design | Electrical Wiring and Cabling | Elec |

## 7. Remaining blockers / conditions for v2

- Use leave-one-out child-to-parent scores for placement confidence and consistency checks.
- Use `esco_purity/2` (explicit level, multi-parent) and exclude the 212 unresolvable links from ESCO features.
- Add the member-level mixing check to the suspicious-parent rules.
- The three wrong 'exact' links and the 34 wrong accepted links stay as they are until a human approves unlinking/remapping; v2 should down-weight or exclude them.
- The v1.2 API export (`data/reference/esco_skills.csv`) is not available, so UNRESOLVED links cannot be traced further.