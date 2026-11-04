# Hierarchy Proposal v2.2 — validation report

> **AI-GENERATED, UNREVIEWED (pending human approval).** Coverage recovery and label refinement on top of v2.1. No new clustering, no new parents; prior versions and frozen data unchanged.

## 1. v2.1 verification

{'topics': 374, 'eligible': 335, 'excluded': 39, 'placed': 198, 'parents': 59, 'confident': 117, 'eligible_unresolved': 137} — all as expected.

## 2–3. Sequential placement

Candidates: 137 {'v2_singleton_never_reconsidered': 119, 'v2_1_unresolved_parent_dissolved': 13, 'v2_1_unresolved_conflict': 5}. Preliminary single-test passes (v2 singletons): 77.
Gates: margin ≥ 0.005 (split candidates ≥ 0.02); coherence ≥ 0.82 and drop ≤ 0.01; no member-level mixing; member support > 0; no new conflicts and ≤ 1 new low-margin child.

**Accepted: 16** (of the preliminary 77: 14). Rejected: 121; most common failed gate: {'G2_coherence': 79, 'G1_margin': 43, 'G5_no_new_conflicts': 39, 'G3_no_mixing': 39, 'G4_member_support': 8}.

## 4. Labels

States {'PROVISIONAL_LABEL': 48, 'UNRESOLVED_LABEL': 11}; confidence {'low': 31, 'medium': 27, 'high': 1}; vague single words 11; not covering all children 21.

## 6. v2.1 vs v2.2 (identical definitions)

| Metric | v2.1 | v2.2 |
|---|---:|---:|
| parents | 59.000 | 59.000 |
| eligible | 335.000 | 335.000 |
| placed | 198.000 | 214.000 |
| loo_conflicts | 14.000 | 10.000 |
| low_margin_0_to_0.02 | 52.000 | 57.000 |
| unresolved | 176.000 | 160.000 |
| confident_share_of_eligible | 0.394 | 0.439 |
| placed_share_of_eligible | 0.591 | 0.639 |
| median_loo_margin | 0.032 | 0.031 |
| mean_parent_coherence | 0.869 | 0.869 |
| median_parent_separation | 0.888 | 0.891 |
| mixing_parents | 1.000 | 1.000 |
| non_mixing_parent_share | 0.983 | 0.983 |
| median_parent_esco_purity_L1 | 0.375 | 0.373 |
| median_parent_esco_purity_L2 | 0.346 | 0.317 |
| mean_parent_esco_coverage | 0.443 | 0.445 |
| suspicious_parents | 5.000 | 6.000 |
| near_duplicate_parent_pairs | 0.000 | 0.000 |
| max_parent_size | 12.000 | 14.000 |
| median_parent_size | 3.000 | 3.000 |
| parents_with_split_pending | 14.000 | 14.000 |
| confident_authoritative | 117.000 | 130.000 |
| low_confidence_authoritative | 81.000 | 84.000 |
| confident_margin_only | 132.000 | 147.000 |
| loo_conflict_rate | 0.071 | 0.047 |
| low_margin_rate | 0.263 | 0.266 |
| parents_size_2 | 29.000 | 27.000 |
| parents_size_3_5 | 21.000 | 21.000 |
| parents_size_6plus | 9.000 | 11.000 |
| labels_high | 1.000 | 1.000 |
| labels_medium | 49.000 | 27.000 |
| labels_low | 9.000 | 31.000 |
| eligible_coverage | 0.591 | 0.639 |
| label_same_root_duplicates | 1.000 | 0.000 |
| label_unresolved | 5.000 | 8.000 |
| label_concatenated_or_generic | 0.000 | 0.000 |
| label_vague_single_word | — | 11.000 |
| label_not_covering_all_children | — | 21.000 |

### Common placed topics

| Scope | Version | Topics | Conflict rate | Median margin | Confident rate | Parent coherence | In mixing parent |
|---|---|---:|---:|---:|---:|---:|---:|
| v2.1 ∩ v2.2 | v2_1 | 198 | 0.071 | 0.032 | 0.591 | 0.861 | 0.015 |
| v2.1 ∩ v2.2 | v2_2 | 198 | 0.051 | 0.031 | 0.606 | 0.861 | 0.015 |
| all four | v1 | 196 | 0.199 | 0.022 | 0.459 | 0.851 | 0.306 |
| all four | v2 | 196 | 0.311 | 0.017 | 0.398 | 0.878 | 0.143 |
| all four | v2_1 | 196 | 0.071 | 0.032 | 0.592 | 0.861 | 0.015 |
| all four | v2_2 | 196 | 0.051 | 0.031 | 0.602 | 0.861 | 0.015 |

ESCO purity attribution: see `esco_purity_attribution.md`.

## 7. Validation

Placement states: {'PLACED_CONFIDENT': 130, 'UNRESOLVED_SINGLETON': 105, 'PLACED_LOW_CONFIDENCE': 84, 'UNRESOLVED_EXCLUDED': 39, 'UNRESOLVED_PARENT_DISSOLVED': 13, 'UNRESOLVED_CONFLICT': 3}.

**Structural problems: none**