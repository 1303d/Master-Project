# Hierarchy Proposal v2 — validation report

> **AI-GENERATED, UNREVIEWED (pending human approval).** Proposed parent level above the 374 frozen leaf topics. No topic, name, membership, alias, link, embedding, clustering output, v1 file or preflight file was changed. Nothing is human-approved.

## Corrected evaluation framework (applied identically to v1 and v2)

| Metric | Definition |
|---|---|
| coherence | mean pairwise cosine of child-topic centroids within a parent (child-child) |
| LOO margin | cos(child, own parent without the child) − max cos(child, any other parent) |
| parent separation | cosine of a parent centroid to its nearest other parent centroid (parent-parent) |
| sibling affinity | share of a parent's assigned members whose nearest other topic is a sibling (member level) |
| ESCO purity L1 / L2 | largest-group share of usable ESCO links at skills-hierarchy Level 1 / Level 2, multi-parent (1/|groups|) |
| ESCO coverage | share of assigned members with a usable Level 2 ESCO link |

ESCO exclusions: 91 assigned-member links whose URI is not in v1.2.1 and 29 links of the 37 suspect skills (Phase 3 verdicts CONFIRMED/LIKELY_INCORRECT, CONTEXT_DEPENDENT; includes unity, scales, design experience). Source files untouched.

Suspicious parent = member-level mixing (sibling affinity < 0.15 or weakest child pair < 0.75) or coherence < 0.82 or nearest parent ≥ 0.95 or ≥ 2 split-pending children. Thresholds fixed before the sweep.

## Configuration sweep and selection

Space: linkage ['average', 'complete', 'weighted'] × weights ['v1_70_15_15', 'w60_20_20', 'w50_30_20', 'w80_10_10'] × thresholds 0.15–0.5 (step 0.01) × ['keep_conflicts_low_confidence', 'unplace_loo_conflicts'] = 864 configurations (`configuration_sweep.csv`).

Criteria fixed before running: hard {'max_parent_size': 15, 'min_placed_share_of_eligible': 0.6, 'min_threshold_neighbour_ari': 0.8}; objective = mean percentile rank of: confident_share_of_eligible, mean_parent_coherence, non_mixing_parent_share, median_parent_esco_purity_L2 (higher is better for all four); tie-break = v1 weights, then average linkage, then smaller threshold, then keep_conflicts.

Feasible configurations: 192. **Selected: {'linkage': 'average', 'weights': 'v1_70_15_15', 'weights_values': (0.7, 0.15, 0.15), 'threshold': 0.24, 'mode': 'keep_conflicts_low_confidence'}.**

## v1 vs v2 (same corrected definitions)

| Metric | v1 | v2 | v2 without split candidates | v2 vs v1 |
|---|---:|---:|---:|---|
| parents | 90.000 | 96.000 | 84.000 | same/context |
| eligible | 335.000 | 335.000 | 298.000 | same/context |
| placed | 303.000 | 216.000 | 183.000 | worse |
| confident | 122.000 | 93.000 | 86.000 | worse |
| low_confidence | 181.000 | 123.000 | 97.000 | improved |
| loo_conflicts | 96.000 | 71.000 | 54.000 | improved |
| low_margin_0_to_0.02 | 85.000 | 52.000 | 43.000 | improved |
| unresolved | 71.000 | 158.000 | 191.000 | worse |
| confident_share_of_eligible | 0.364 | 0.278 | 0.289 | worse |
| placed_share_of_eligible | 0.904 | 0.645 | 0.614 | worse |
| median_loo_margin | 0.013 | 0.013 | 0.018 | improved |
| mean_parent_coherence | 0.850 | 0.874 | 0.874 | improved |
| median_parent_separation | 0.900 | 0.891 | 0.886 | improved |
| mixing_parents | 29.000 | 17.000 | 15.000 | improved |
| non_mixing_parent_share | 0.678 | 0.823 | 0.821 | improved |
| median_parent_esco_purity_L1 | 0.381 | 0.450 | 0.455 | improved |
| median_parent_esco_purity_L2 | 0.316 | 0.375 | 0.375 | improved |
| mean_parent_esco_coverage | 0.430 | 0.414 | 0.411 | worse |
| suspicious_parents | 36.000 | 21.000 | 17.000 | improved |
| near_duplicate_parent_pairs | 2.000 | 0.000 | 0.000 | improved |
| max_parent_size | 14.000 | 6.000 | 6.000 | same/context |
| median_parent_size | 3.000 | 2.000 | 2.000 | same/context |
| parents_with_split_pending | 24.000 | 19.000 | 0.000 | same/context |

Improved: low_confidence, loo_conflicts, low_margin_0_to_0.02, median_loo_margin, mean_parent_coherence, median_parent_separation, mixing_parents, non_mixing_parent_share, median_parent_esco_purity_L1, median_parent_esco_purity_L2, suspicious_parents, near_duplicate_parent_pairs.
Worse (trade-offs): placed, confident, unresolved, confident_share_of_eligible, placed_share_of_eligible, mean_parent_esco_coverage.

## Placement states

| State | Topics |
|---|---:|
| PLACED_LOW_CONFIDENCE | 135 |
| UNRESOLVED_SINGLETON | 119 |
| PLACED_CONFIDENT | 81 |
| UNRESOLVED_EXCLUDED | 39 |

## Parent labels

Label confidence: {'low': 68, 'medium': 28}; basis: {'child topic names only (no shared terms, no agreeing ESCO group)': 65, 'shared child-name terms': 27, 'verified ESCO Level 2 group agreeing with child names / member skills': 4}; flagged for label review: 68.

## Structural validation

Coverage (374 unique), parent references, no single-child parents, disjoint ID namespaces (depth 2, no cycles), unresolved/excluded topics without parents, consistent child lists, no generic labels, no human approval set.

**Problems: none**

## Known v1 problem parents

| v1 parent | Children | v1 flagged (v1 rules) | v1 mixing (corrected) | v2 placement | Together in v2 | v2 parent suspicious |
|---|---|---|---|---|---|---|
| P035 | Hand and Power Tool Operation | Garment and Lens Fitting | Quantity Take-Offs and Restructuring | Rigging and Surface Finishing | Pallet Jack Operation | True | False | T0050->Q025; T0140->UNRESOLVED_SINGLETON; T0172->UNRESOLVED_SINGLETON; T0192->Q025; T0280->UNRESOLVED_SINGLETON | False | Q025:True |
| P046 | SAP ERP Modules | SD-Prefixed Acronyms | True | True | T0069->UNRESOLVED_SINGLETON; T0301->UNRESOLVED_SINGLETON | False |  |
| P052 | IT Service Desk Support | Food and Beverage Service | True | False | T0089->UNRESOLVED_SINGLETON; T0246->UNRESOLVED_SINGLETON | False |  |
| P080 | Keyboarding and Typing | Switching Equipment | False | True | T0249->Q082; T0266->Q082 | True | Q082:True |
| P085 | HMI and EDI Systems | RFP Response Preparation | True | False | T0299->Q090; T0311->Q090 | True | Q090:True |

## Suspicious v2 parents

| Parent | Label | Coherence | Sibling aff. | Weakest pair | Flags |
|---|---|---:|---:|---:|---|
| Q019 | Shell Scripting / Data Storage Management | 0.8475 | 0.1029 | 0.8475 | mixing |
| Q020 | Cardiac Monitoring / Medical and Surgical Procedures / Renal and Medical Specialty Knowled | 0.8572 | 0.3351 | 0.8282 | split pending |
| Q021 | Clinical and Educational Assessment / Screening Procedures | 0.8377 | 0.0727 | 0.8377 | mixing |
| Q025 | Hand and Power Tool Operation / Rigging and Surface Finishing | 0.9118 | 0.28 | 0.9118 | split pending |
| Q038 | System Integration Architecture / Enterprise Platform Management | 0.9061 | 0.1455 | 0.9061 | mixing |
| Q039 | Structural Engineering Design / IT Infrastructure Architecture | 0.8579 | 0.0896 | 0.8579 | mixing |
| Q041 | Cloud Services: Microsoft Azure Cloud Services; AWS Cloud Services | 0.8408 | 0.1143 | 0.8408 | mixing |
| Q047 | Cash Handling Operations / Transaction Processing | 0.8467 | 0.1333 | 0.8467 | mixing |
| Q054 | Engineering: Mechanical Engineering Knowledge; Engineering Practices and Reliability | 0.8605 | 0.1212 | 0.8605 | mixing |
| Q055 | Cisco Network Security / Proxy and VPN Administration | 0.8429 | 0.1 | 0.8429 | mixing |
| Q056 | KPI Dashboarding / Issue and Project Tracking | 0.8626 | 0.0789 | 0.8626 | mixing |
| Q059 | ERP: ERP System Administration; Epicor ERP Modules | 0.7978 | 0.1714 | 0.7978 | low coherence |
| Q065 | Recruitment and Hiring / Onboarding Processes | 0.7995 | 0.1034 | 0.7995 | mixing, low coherence |
| Q077 | Ticketing Systems / Retail Operations Management | 0.8347 | 0.1429 | 0.8347 | mixing |
| Q078 | Feedback and Needs Analysis / Survey Design and Site Surveying | 0.8802 | 0.12 | 0.8802 | mixing |
| Q082 | Keyboarding and Typing / Switching Equipment | 0.8509 | 0.125 | 0.8509 | mixing |
| Q083 | Document Management Systems / Product Labeling Compliance | 0.8511 | 0.1034 | 0.8511 | mixing |
| Q088 | Data and Barcode Coding / Technical Codes Knowledge | 0.8392 | 0.1154 | 0.8392 | mixing |
| Q089 | Hydraulic and Brake Systems / Pneumatic Systems | 0.856 | 0.1333 | 0.856 | mixing |
| Q090 | HMI and EDI Systems / RFP Response Preparation | 0.7837 | 0.1538 | 0.7837 | low coherence |
| Q091 | System Configuration / Product and Fixture Installation | 0.8216 | 0.1071 | 0.8216 | mixing |

## Grandparent feasibility (not constructed)

The brief (Sprint 4) asks to "build a multi-level hierarchy" and "build parent levels above the leaves"; it fixes no depth. Grouping the v2 parents by centroid (average linkage) at several cuts:

| Cut | Grandparents | Parents grouped | Parents alone | Median ESCO L1 purity | Largest |
|---:|---:|---:|---:|---:|---:|
| 0.06 | 0 | 0 | 96 | nan | 1 |
| 0.08 | 2 | 4 | 92 | 0.478 | 2 |
| 0.1 | 14 | 29 | 67 | 0.349 | 3 |
| 0.12 | 29 | 62 | 34 | 0.375 | 5 |
| 0.15 | 26 | 83 | 13 | 0.312 | 8 |

## Remaining work

- Human review of every parent, label and placement (none approved); document over/under-merging (brief).
- Excluded topics need re-clustering or member reassignment before placement.
- Split decisions for split-pending topics; LOO-conflict topics need a human placement decision.
- Suspect and unresolvable ESCO links remain in the source files until a human approves unlinking/remapping.
- Grandparent level: decision for the team (see feasibility table).