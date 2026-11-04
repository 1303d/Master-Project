# Sprint 4 — Phase 2 closure and Phase 3 taxonomy evaluation (audit v1)

> **All review judgments in this folder are AI-GENERATED (Claude Code, claude-opus-5-5, 2026-11-04) and NOT
> human-validated. Every proposed action is pending approval.** Metrics are recomputed by
> `src/build_phase3_audit_outputs.py` from frozen inputs (hashes in `manifest.json`). Nothing in the taxonomy,
> snapshot, aliases, links, embeddings or clustering was changed. T0104 = `INVESTIGATE_CLUSTER` was approved by the
> user in conversation and is recorded here only; it is not yet written into the review workbook.

**Verdict: Phase 2 technically COMPLETE (with noted partial items); Phase 3 PARTIAL — no hierarchy exists.**

## Files

| File | Rows | Content |
|---|---:|---|
| `topic_metrics_374.csv` | 374 | computed: sizes, weak share, within-topic cosine, nearest topic, silhouette, kNN agreement, ESCO purity, coverage, name checks; AI action where reviewed |
| `p1_skill_audit_976.csv` | 976 | AI membership class (Phase 2), link verdict, conflicting key, acronym status, v2 rule flags, Sprint 3 human decision |
| `reference_link_verification_38.csv` | 38 | accepted links checked against ESCO v1.2.1 / O*NET 31.0 definitions |
| `conflicting_meaning_keys_9.csv` | 9 | every extraction record, senses, treatment |
| `acronym_resolution_61.csv` | 61 | status, evidence, supported meaning (no invented expansions) |
| `non_p1_topic_review_54.csv` | 54 | member-level screening (all names; quotes for short codes) |
| `topic_pair_review_75.csv` | 75 | all centroid pairs ≥ 0.90 |
| `manifest.json` | — | input/output hashes, global metrics, definitions, limitations |

## Sources

Frozen snapshot `data/processed/sprint4_input_hdbscan_10_umap10_ms1_2026-10-23/` (all 9 manifest hashes verified),
Sprint 4 features, assembled names `assembled_topic_naming_v1_20261104T003642Z`, P1 reconciliation v2, recovered
`data/interim/prepared_mentions.csv` (sha 753f905f… = original preparation manifest), **ESCO v1.2.1** (19 CSVs,
hashes equal the project reference manifest) and **O*NET 31.0** (August 2026) at `~/Desktop/testing/references/`
(the project's own `data/reference/` is absent on this machine).

## Key results

**Reference links (38 accepted links):** 25 CONFIRMED_INCORRECT, 9 LIKELY_INCORRECT, 3 CONTEXT_DEPENDENT
(sem, boating, site development), 1 UNVERIFIABLE (asa). 34 are valid skills with a wrong link — do not delete them.
Mechanical: 212 of 8,161 ESCO link URIs are absent from v1.2.1; three "exact" matches (unity, scales,
design experience) are not explained by v1.2.1 labels. The 276 acronym `new_candidate` links (score 0.656–0.848) are
unaccepted nearest neighbours — treat as "no reliable link".

**Conflicting keys (9):** sem, dmp, prisma, lis, google, assembly, waxing, templates have ≥ 2 evidence-supported
senses (split candidates); painting is 9/10 trade painting inside an "art" topic.

**Acronyms (61):** 10 resolved with evidence, 30 domain only, 13 possible non-skills, 7 still ambiguous,
1 without local source text.

**P1 memberships (976, Phase 2):** COHERENT 173, QUESTIONABLE 103, LIKELY_MISASSIGNED 615, INSUFFICIENT_CONTEXT 85.
Correction: 17 of 23 v1 `suspected_extraction_errors` were wrong (string matches, not extraction records); do not
use the `ai_v1_*` columns.

**Non-P1 topics (54, 1,822 members):** KEEP_CANDIDATE 13, POTENTIAL_SPLIT 22, INVESTIGATE_CLUSTER 18,
POTENTIAL_MERGE 1. Typical failure: surface-form grouping by shared letters or words (e.g. T0253 message queues +
genomics "seq"; T0088 GxP + Google Cloud "gcp"; T0287 retention + Joint Commission).

**Cluster metrics (independently computed, frozen vectors):**

| Metric | Value |
|---|---|
| Silhouette (cosine, 384-d, assigned) | 0.113 (run.json 0.0929, method not stated) |
| Topics with negative mean silhouette | 43 |
| kNN@10 same-topic agreement (assigned / weak / random) | 0.616 / 0.260 / 0.004 |
| kNN agreement median, P1 vs non-P1 | 0.434 vs 0.611 |
| Same-reference-concept pairs placed in the same topic | 19.2% of 18,597 |
| ESCO purity (level 2), median over 311 topics | 0.50 (P1 0.36) |
| Coverage (existing metric), median | 0.522 |
| Centroid pairs ≥ 0.90 | 75 |
| Weak members within 0.01 of a second topic | 871 / 2,447 |

**Merge screening (75 pairs):** 5 strong candidates, 17 possible, 20 similar-but-distinct, 26 do-not-merge
(12 cross-domain word overlaps, 14 noise-to-noise), 7 insufficient until P1 cleanup.

**Naming (374 provisional names):** 3 duplicate-name pairs, 20 surface-form names ("Acronyms", "Prefixed", "Mixed"),
43 names supported by < 10% of assigned members, 62 low-confidence names. No replacement names proposed for
topics without a coherent core.

## Hierarchy status — NOT IMPLEMENTED

`topics.csv`: all 374 rows `level = topic`, `parent_topic_id` empty. No hierarchy builder in `src/`;
`topic_validity.py` only provides `hierarchy_treatment` (eligible 312 / hold_split_candidate 38 /
exclude_until_reclustered 24) as input for a future builder. Hierarchy validation is blocked until it exists.

## Capstone requirements (brief, Sprint 4)

| Requirement | Status |
|---|---|
| Name every leaf topic | implemented, not validated (0 human-validated names) |
| Reject vague / mixed topics | screening implemented; no decisions taken |
| Build parent levels | **not implemented** |
| Evaluate vs ESCO: coverage | implemented |
| Evaluate vs ESCO: purity | not implemented in the pipeline (computed in this audit only) |
| Evaluate vs ESCO: nearest-neighbour agreement | not implemented in the pipeline (two variants computed here; definition is ours) |
| Hand review of hierarchy, over/under-merge notes | not started |
| Deliverable: labelled hierarchical taxonomy + evaluation report | not met |

Sprint 3 items (method comparison, sweep, stability) are claimed in HANDOFF / the Sprint 3 report, but their
artifacts are not available locally, so they are not verifiable here.

## Technical checklist

| Item | Status |
|---|---|
| Source and hash validation | COMPLETE |
| ESCO / O*NET library location | COMPLETE (Desktop copy; project copy missing) |
| 38-link verification | COMPLETE |
| 9 conflicting keys | COMPLETE |
| 61 acronyms | COMPLETE (8 need full posting text) |
| 54-topic member review | PARTIAL (quotes for long-name members not read) |
| Cluster integrity and coherence metrics | COMPLETE |
| Nearest-neighbour agreement | COMPLETE as audit metric; NOT_STARTED in pipeline |
| ESCO purity | COMPLETE as audit metric; NOT_STARTED in pipeline |
| Split / merge screening | COMPLETE (proposals only) |
| Naming evaluation | COMPLETE (screen) |
| Hierarchy construction | NOT_STARTED |
| Hierarchy validation | BLOCKED (no hierarchy) |
| Phase 2 Audit 4 categories | PARTIAL (560 of 976 by rule) |

## Pending human decisions

1. Write T0104 `INVESTIGATE_CLUSTER` (user-approved) into the workbook.
2. Unlink or remap the 34 wrong accepted links; rule on 3 context-dependent and 1 unverifiable.
3. Split decisions for the 9 multi-sense keys.
4. Skill vs non-skill for 13 acronyms; source lookup for 8.
5. Actions for the 54 non-P1 topics and the 20 P1 topics (`p1_skill_audit_976.csv`, `topic_metrics_374.csv`).
6. Exclusion / re-cluster policy for surface-form topics.
7. Merge rulings (5 strong, 17 possible) and confirmation of 26 do-not-merge pairs.
8. Rename policy, including 3 duplicate-name pairs.
9. Hierarchy method choice, then hand review.
10. Whether evaluation continues on the Haiku-dominant baseline until the Qwen migration.

## Remaining technical work (not done in this task)

Build parent levels from eligible topics; implement purity and nearest-neighbour agreement in the pipeline;
explain the 212 missing ESCO URIs and 3 unexplained exact matches; fetch source text for the 8 unresolved acronyms;
read quotes for the long-name members of the 54 topics; recover the Sprint 3 sweep/stability artifacts.
