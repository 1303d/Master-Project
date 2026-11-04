# ESCO purity attribution (v1, v2, v2.1, v2.2)

> Corrected definitions (esco_levels): skills-hierarchy Level 1 / Level 2, multi-parent weights 1/|groups|, links not in v1.2.1 and the 37 suspect accepted links excluded, parents with ≥ 3 usable links. Purity is a reference-agreement signal, **not proof** of better clustering.

Common placed population (topics placed in all four versions): 196 topics.

| Version | Population | Level | Parents evaluated / total | Median parent purity | Link-weighted purity | Usable links | Median purity, 2-child | Median purity, 3+ | Share 2-child |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v1 | full | 1 | 89/90 | 0.381 | 0.393 | 3104 | 0.407 | 0.375 | 0.461 |
| v1 | full | 2 | 89/90 | 0.316 | 0.343 | 3104 | 0.308 | 0.320 | 0.461 |
| v1 | common_placed | 1 | 60/60 | 0.442 | 0.423 | 1859 | 0.429 | 0.449 | 0.583 |
| v1 | common_placed | 2 | 60/60 | 0.375 | 0.383 | 1859 | 0.357 | 0.449 | 0.583 |
| v2 | full | 1 | 93/96 | 0.450 | 0.433 | 2191 | 0.409 | 0.500 | 0.828 |
| v2 | full | 2 | 93/96 | 0.375 | 0.379 | 2191 | 0.357 | 0.487 | 0.828 |
| v2 | common_placed | 1 | 77/78 | 0.450 | 0.437 | 1869 | 0.409 | 0.500 | 0.792 |
| v2 | common_placed | 2 | 77/78 | 0.375 | 0.389 | 1869 | 0.357 | 0.487 | 0.792 |
| v2_1 | full | 1 | 59/59 | 0.375 | 0.394 | 2072 | 0.409 | 0.341 | 0.492 |
| v2_1 | full | 2 | 59/59 | 0.346 | 0.340 | 2072 | 0.357 | 0.302 | 0.492 |
| v2_1 | common_placed | 1 | 59/59 | 0.375 | 0.396 | 2057 | 0.408 | 0.350 | 0.508 |
| v2_1 | common_placed | 2 | 59/59 | 0.346 | 0.342 | 2057 | 0.355 | 0.303 | 0.508 |
| v2_2 | full | 1 | 59/59 | 0.373 | 0.375 | 2257 | 0.408 | 0.334 | 0.458 |
| v2_2 | full | 2 | 59/59 | 0.317 | 0.317 | 2257 | 0.353 | 0.295 | 0.458 |
| v2_2 | common_placed | 1 | 59/59 | 0.375 | 0.396 | 2057 | 0.408 | 0.350 | 0.508 |
| v2_2 | common_placed | 2 | 59/59 | 0.346 | 0.342 | 2057 | 0.355 | 0.303 | 0.508 |

## Multi-parent ancestry

| Version | Level | Median purity (multi-parent) | Median purity (first parent only) |
|---|---:|---:|---:|
| v1 | 1 | 0.381 | 0.407 |
| v1 | 2 | 0.316 | 0.333 |
| v2 | 1 | 0.450 | 0.450 |
| v2 | 2 | 0.375 | 0.375 |
| v2_1 | 1 | 0.375 | 0.385 |
| v2_1 | 2 | 0.346 | 0.324 |
| v2_2 | 1 | 0.373 | 0.375 |
| v2_2 | 2 | 0.317 | 0.320 |

## Reading (computed from the tables above)

- Parent size vs L1 purity: v1: 2-child 0.407 vs 3+ children 0.375 (share of 2-child parents 0.461); v2: 2-child 0.409 vs 3+ children 0.500 (share of 2-child parents 0.828); v2_1: 2-child 0.409 vs 3+ children 0.341 (share of 2-child parents 0.492); v2_2: 2-child 0.408 vs 3+ children 0.334 (share of 2-child parents 0.458).
- v2 -> v2.1 on the SAME topics (common placed, L1 median): 0.450 -> 0.375; the decline is therefore not a coverage effect. It follows the change in parent composition: v2.1's larger parents (3+ children) have L1 purity 0.341 vs 0.500 in v2, i.e. the moves/orphan placements that built larger parents mixed ESCO groups.
- v2.1 -> v2.2: identical on the common placed population (0.346 vs 0.346 at L2), lower on the full population (0.346 -> 0.317 at L2): the change comes only from the recovered topics added to parents.
- Multi-parent ancestry: first-parent-only medians differ from multi-parent medians by at most a few hundredths (table above), so ESCO's multiple ancestry is a minor factor.
- Reference coverage: usable links v1 3104, v2 2191, v2_1 2072, v2_2 2257; parents with < 3 usable links are not evaluated.
- Higher purity is not proof of better clustering: ESCO links are automatic, and small parents score higher or lower by chance.