# Intrusion v2 — single-reviewer (exploratory) evaluation summary

Run `hdbscan_10_umap10_ms1_2026-10-23` · status **completed** · 1 of 1 expected reviewer(s) submitted · 24 questions.

This file is safe to share: it contains aggregate numbers only (no question-level results, answer letters,
options, topic labels or intruders). Question-level results are kept in the gitignored `private/` folder.

## Method

Word-intrusion test (Chang et al. 2009): each question shows 4 assigned members of one clustering topic plus 1
intruder from a nearby, different topic; the reviewer picks the one that does not belong (5 options, chance
= 20 %). 24 topics were drawn, 4 from each of 6 strata, seed fixed; questions and the answer key are frozen and
hash-checked (`manifest.json`).

## Result

| Measure | Value |
|---|---|
| Reviewers | 1 (single-reviewer mode) |
| Correct | **15 / 24** (9 incorrect) |
| Accuracy | **0.625** |
| 95 % Wilson interval | 0.427 – 0.788 |
| Chance | 0.20 |
| Exact one-sided binomial p vs chance | 6.7e-06 |

## By stratum

| Stratum | Correct | Accuracy | 95 % Wilson interval |
|---|---|---|---|
| transversal | 3 / 4 | 0.75 | 0.30 – 0.95 |
| low_confidence | 1 / 4 | 0.25 | 0.05 – 0.70 |
| long_tail | 3 / 4 | 0.75 | 0.30 – 0.95 |
| large | 2 / 4 | 0.50 | 0.15 – 0.85 |
| medium | 3 / 4 | 0.75 | 0.30 – 0.95 |
| small | 3 / 4 | 0.75 | 0.30 – 0.95 |

## Limitations

- **Protocol deviation:** the planned protocol was three independent reviewers; one genuine reviewer took
  the test. **Inter-reviewer agreement is not available** (it needs at least two raters), so we cannot
  separate topic incoherence from one person's judgement. Treat the result as **exploratory**.
- The reviewer's machine held the (unopened) answer key file; blindness relied on not opening it.
- 24 questions give wide intervals; each stratum has only 4 questions, so stratum differences are not
  statistically meaningful (all stratum intervals overlap).
- Topic labels used in the study were provisional (centroid skill); topics come from one clustering run.

## Recommended follow-up

1. Run the full three-reviewer protocol on a fresh, independently generated question set (new seed, new key
   held by a non-reviewer) to measure agreement and confirm the accuracy.
2. Inspect the low-confidence stratum and the missed topics by hand in Sprint 4 Step 6 (topic review).
3. Use the diagnostics (private) to decide which topics to split, merge or flag before building the hierarchy.
