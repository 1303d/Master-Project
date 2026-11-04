# Hierarchy Proposal v2.1 — validation report

> **AI-GENERATED, UNREVIEWED (pending human approval).** Targeted refinement of v2 (no new clustering sweep). Frozen inputs, v1, v2 and preflight outputs unchanged. Nothing is human-approved.

## 1. Confidence count reconciliation

v2 comparison table used *LOO margin ≥ 0.02* = 93; v2 placement states also required *not split-pending*: 93 − 12 split-pending = 81. Reconciled: True.
**Authoritative definition (all versions below): CONFIDENT = LOO margin ≥ 0.02 AND not split-pending.** The margin-only count is reported as `confident_margin_only`.

## 2. Conflict diagnosis (v2 placed topics)

{'CLEAR': 93, 'CONFLICT': 71, 'NEAR_TIE': 52} (split candidates among conflicts: 9).

## 3–4. Decisions

| Decision | Topics |
|---|---:|
| KEEP | 130 |
| MOVE | 36 |
| MOVE_ORPHAN | 23 |
| UNRESOLVE_ORPHAN | 13 |
| KEEP_NEAR_TIE | 9 |
| UNRESOLVE | 5 |

Pair / consolidation analysis: {'KEEP_PAIR': 29, 'KEEP_SEPARATE': 2}.

## 5. Labels

States {'PROVISIONAL_LABEL': 54, 'UNRESOLVED_LABEL': 5}; confidence {'medium': 49, 'low': 9, 'high': 1}.

## 6. Fair comparison (identical corrected definitions)

| Metric | v1 | v2 | v2.1 |
|---|---:|---:|---:|
| parents | 90.000 | 96.000 | 59.000 |
| eligible | 335.000 | 335.000 | 335.000 |
| placed | 303.000 | 216.000 | 198.000 |
| loo_conflicts | 96.000 | 71.000 | 14.000 |
| low_margin_0_to_0.02 | 85.000 | 52.000 | 52.000 |
| unresolved | 71.000 | 158.000 | 176.000 |
| confident_share_of_eligible | 0.364 | 0.278 | 0.394 |
| placed_share_of_eligible | 0.904 | 0.645 | 0.591 |
| median_loo_margin | 0.013 | 0.013 | 0.032 |
| mean_parent_coherence | 0.850 | 0.874 | 0.869 |
| median_parent_separation | 0.900 | 0.891 | 0.888 |
| mixing_parents | 29.000 | 17.000 | 1.000 |
| non_mixing_parent_share | 0.678 | 0.823 | 0.983 |
| median_parent_esco_purity_L1 | 0.381 | 0.450 | 0.375 |
| median_parent_esco_purity_L2 | 0.316 | 0.375 | 0.346 |
| mean_parent_esco_coverage | 0.430 | 0.414 | 0.443 |
| suspicious_parents | 36.000 | 21.000 | 5.000 |
| near_duplicate_parent_pairs | 2.000 | 0.000 | 0.000 |
| max_parent_size | 14.000 | 6.000 | 12.000 |
| median_parent_size | 3.000 | 2.000 | 3.000 |
| parents_with_split_pending | 24.000 | 19.000 | 14.000 |
| confident_authoritative | 106.000 | 81.000 | 117.000 |
| low_confidence_authoritative | 197.000 | 135.000 | 81.000 |
| confident_margin_only | 122.000 | 93.000 | 132.000 |
| loo_conflict_rate | 0.317 | 0.329 | 0.071 |
| low_margin_rate | 0.281 | 0.241 | 0.263 |
| parents_size_2 | 42.000 | 80.000 | 29.000 |
| parents_size_3_5 | 37.000 | 15.000 | 21.000 |
| parents_size_6plus | 11.000 | 1.000 | 9.000 |
| labels_high | nan | 0.000 | 1.000 |
| labels_medium | nan | 28.000 | 49.000 |
| labels_low | nan | 68.000 | 9.000 |

### Common placed-topic population

| Version | Topics | Conflict rate | Low-margin rate | Median margin | Confident rate | Mean parent coherence | In mixing parent |
|---|---:|---:|---:|---:|---:|---:|---:|
| v1 | 196 | 0.199 | 0.281 | 0.022 | 0.459 | 0.851 | 0.306 |
| v2 | 196 | 0.311 | 0.230 | 0.017 | 0.398 | 0.878 | 0.143 |
| v2_1 | 196 | 0.071 | 0.260 | 0.032 | 0.592 | 0.861 | 0.015 |

### Coverage–quality trade-off (v2 sweep re-ranked without the 60% floor; no new sweep)

| Placed share | Config | Placed | Confident (margin) | LOO conflicts | Coherence | Mixing parents | ESCO L2 |
|---|---|---:|---:|---:|---:|---:|---:|
| (0.0, 0.3] | weighted/v1_70_15_15/0.15/unplace_loo_conflicts | 54 | 47 | 0 | 0.895 | 0 | 0.500 |
| (0.3, 0.4] | weighted/v1_70_15_15/0.26/unplace_loo_conflicts | 116 | 93 | 0 | 0.888 | 1 | 0.343 |
| (0.4, 0.5] | weighted/w80_10_10/0.24/unplace_loo_conflicts | 135 | 105 | 0 | 0.885 | 1 | 0.332 |
| (0.5, 0.6] | complete/w80_10_10/0.37/unplace_loo_conflicts | 171 | 131 | 0 | 0.861 | 2 | 0.323 |
| (0.6, 0.7] | average/w80_10_10/0.21/keep_conflicts_low_confidence | 219 | 93 | 73 | 0.878 | 16 | 0.367 |
| (0.7, 0.8] | average/w80_10_10/0.23/keep_conflicts_low_confidence | 245 | 104 | 79 | 0.869 | 20 | 0.368 |
| (0.8, 0.9] | weighted/w80_10_10/0.26/keep_conflicts_low_confidence | 282 | 120 | 94 | 0.861 | 23 | 0.346 |
| (0.9, 1.0] | weighted/w50_30_20/0.44/keep_conflicts_low_confidence | 303 | 116 | 112 | 0.853 | 30 | 0.333 |

Without the floor the top-ranked configuration would be weighted/v1_70_15_15/0.15/unplace_loo_conflicts placing 54 topics — higher quality scores only by placing far fewer topics.

## 7. Validation

Placement states: {'UNRESOLVED_SINGLETON': 119, 'PLACED_CONFIDENT': 117, 'PLACED_LOW_CONFIDENCE': 81, 'UNRESOLVED_EXCLUDED': 39, 'UNRESOLVED_PARENT_DISSOLVED': 13, 'UNRESOLVED_CONFLICT': 5}.

**Structural problems: none**