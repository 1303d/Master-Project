# v8 dev evaluation (Haiku and Qwen), 2026-10-30

Dev split only (50 postings). Scoring = `src/evaluate.py` functions, unchanged. Sectors = `gold_split.csv` sector_eval (`--sector-source split`). Aliases = `config/skill_aliases_manual.csv`.

## 1. Run manifest

- **Code commit:** `768d388` (runs used commit `768d388`; later commits add only this report).
- **Qwen v8 stops / resumes:** first run 2026-10-30T05:29:56Z; 36/50 done when the Claude Code session ended during a 429 wait (retry-after up to 1,121 s). stop: session ended during 429 wait, 36/50 cached; resume 2026-10-30T18:08:53Z resume1 ended 2026-10-30T18:17:57Z. Same settings; 14 new calls; 0 failed.
- Qwen v3 / v5 and Haiku v3 were rebuilt from the cache (`--legacy-cache-key`, 0 calls).

| run | model_id | provider | prompt | prompt_sha256 | typed | types | temperature | reasoning_format | delay_s | started_utc | ended_utc | postings_scored | failed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5_v3 | claude-haiku-5-5 | anthropic | skill_extraction_v3.txt | 773380cfe087e9dc31538e1442158d2e04fc45166216f8e0b775abba44b9b868 | False | - |  | - | 4 (default, earlier run) | earlier run (cache reused) |  | 50 | 0 |
| claude-haiku-5-5_v8a | claude-haiku-5-5 | anthropic | skill_extraction_v8a.txt | 26ac628dd785f7363fd3a1f65b639cc1c92531e6054181cc32e63d212e0dbb87 | True | skill,knowledge,tool |  | - | 1 | 2026-10-30T05:22:36Z | 2026-10-30T05:29:33Z | 50 | 0 |
| claude-haiku-5-5_v8 | claude-haiku-5-5 | anthropic | skill_extraction_v8.txt | 5f0302cd8a9de5158d49670f052cc69eaeac1ff68fe248d500cb028ed83ee03a | True | skill,knowledge,tool |  | - | 1 | 2026-10-30T05:22:36Z | 2026-10-30T05:29:23Z | 50 | 0 |
| qwen_qwen3.8-27b_v3 | qwen/qwen3.8-27b | groq | skill_extraction_v3.txt | 773380cfe087e9dc31538e1442158d2e04fc45166216f8e0b775abba44b9b868 | False | - | 0.000 | hidden | 4 (default, earlier run) | earlier run (cache reused) |  | 50 | 0 |
| qwen_qwen3.8-27b_v5 | qwen/qwen3.8-27b | groq | skill_extraction_v5.txt | b6166d6ecf5f7f5047e3a2da368b211c451b5b5ee0cd910ca9dd0aed29cd691e | False | - | 0.000 | - | 4 (default, earlier run) | earlier run (cache reused) |  | 50 | 0 |
| qwen_qwen3.8-27b_v8 | qwen/qwen3.8-27b | groq | skill_extraction_v8.txt | 5f0302cd8a9de5158d49670f052cc69eaeac1ff68fe248d500cb028ed83ee03a | True | skill,knowledge,tool | 0.000 | hidden | 40 | 2026-10-30T05:29:56Z | 2026-10-30T18:17:57Z | 50 | 0 |

| gold | file | sha256 |
|---|---|---|
| v2 | data\gold\gold_labels_v2.csv | b212c10ef7d23f88f742191984bc67984b929858382c108306bcfb9bc74a964c |
| v3_dev_proposed | data\gold\gold_labels_v3_dev_proposed.csv | 47496d962e2c5359bb51e9f2280774a514cd520b6d1f7df7534d08e75efb3e7c |
| audit | data\gold\audit\gold_audit_dev_v3_proposed.xlsx | 8dc12de6250f0779e10ac9fc6db179d46ad87e3adf02b79948b4e8de157b4154 |
| aliases | config\skill_aliases_manual.csv | afc6c60d01560b2ee03bfbb97ec3049eb5274d47dbe9dec38f206b36aafae660 |

## 2. Main results

F1 traits dropped = predicted items linked as `trait` in `skill_links.csv` removed (extra column only).

| run | gold | postings | gold_items | predicted | P_strict | R_strict | F1_strict | P_lenient | R_lenient | F1_lenient | F1_strict_alias | F1_strict_traits_dropped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5_v3 | v2 | 50 | 675 | 773 | 0.622 | 0.713 | 0.664 | 0.702 | 0.804 | 0.750 | 0.664 | 0.672 |
| claude-haiku-5-5_v8 | v2 | 50 | 675 | 671 | 0.700 | 0.696 | 0.698 | 0.784 | 0.779 | 0.782 | 0.704 | 0.699 |
| claude-haiku-5-5_v8a | v2 | 50 | 675 | 670 | 0.682 | 0.677 | 0.680 | 0.773 | 0.767 | 0.770 | 0.686 | 0.680 |
| qwen_qwen3.8-27b_v3 | v2 | 50 | 675 | 702 | 0.640 | 0.665 | 0.652 | 0.717 | 0.745 | 0.731 | 0.658 | 0.658 |
| qwen_qwen3.8-27b_v5 | v2 | 50 | 675 | 692 | 0.647 | 0.664 | 0.655 | 0.731 | 0.750 | 0.740 | 0.661 | 0.661 |
| qwen_qwen3.8-27b_v8 | v2 | 50 | 675 | 630 | 0.667 | 0.622 | 0.644 | 0.763 | 0.713 | 0.737 | 0.650 | 0.644 |
| claude-haiku-5-5_v3 | v3_dev_proposed | 50 | 709 | 773 | 0.668 | 0.728 | 0.696 | 0.748 | 0.815 | 0.780 | 0.696 | 0.704 |
| claude-haiku-5-5_v8 | v3_dev_proposed | 50 | 709 | 671 | 0.759 | 0.718 | 0.738 | 0.841 | 0.795 | 0.817 | 0.743 | 0.738 |
| claude-haiku-5-5_v8a | v3_dev_proposed | 50 | 709 | 670 | 0.731 | 0.691 | 0.711 | 0.822 | 0.777 | 0.799 | 0.716 | 0.711 |
| qwen_qwen3.8-27b_v3 | v3_dev_proposed | 50 | 709 | 702 | 0.679 | 0.673 | 0.676 | 0.759 | 0.752 | 0.755 | 0.682 | 0.682 |
| qwen_qwen3.8-27b_v5 | v3_dev_proposed | 50 | 709 | 692 | 0.694 | 0.677 | 0.685 | 0.779 | 0.760 | 0.769 | 0.691 | 0.691 |
| qwen_qwen3.8-27b_v8 | v3_dev_proposed | 50 | 709 | 630 | 0.719 | 0.639 | 0.677 | 0.819 | 0.728 | 0.771 | 0.683 | 0.677 |

## 3. Paired comparisons (v3-proposed gold, same 50 postings, 2,000 bootstrap draws, seed 0)

| this | baseline | metric | baseline_F1 | this_F1 | diff | ci95_low | ci95_high | interval_contains_0 |
|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5_v8a | claude-haiku-5-5_v3 | strict | 0.696 | 0.711 | 0.014 | -0.019 | 0.050 | yes |
| claude-haiku-5-5_v8a | claude-haiku-5-5_v3 | lenient | 0.780 | 0.799 | 0.019 | -0.009 | 0.047 | yes |
| claude-haiku-5-5_v8a | claude-haiku-5-5_v3 | strict+alias | 0.696 | 0.716 | 0.020 | -0.015 | 0.056 | yes |
| claude-haiku-5-5_v8 | claude-haiku-5-5_v8a | strict | 0.711 | 0.738 | 0.027 | -0.007 | 0.061 | yes |
| claude-haiku-5-5_v8 | claude-haiku-5-5_v8a | lenient | 0.799 | 0.817 | 0.018 | -0.009 | 0.044 | yes |
| claude-haiku-5-5_v8 | claude-haiku-5-5_v8a | strict+alias | 0.716 | 0.743 | 0.027 | -0.007 | 0.061 | yes |
| claude-haiku-5-5_v8 | claude-haiku-5-5_v3 | strict | 0.696 | 0.738 | 0.041 | 0.007 | 0.077 | no |
| claude-haiku-5-5_v8 | claude-haiku-5-5_v3 | lenient | 0.780 | 0.817 | 0.037 | 0.010 | 0.066 | no |
| claude-haiku-5-5_v8 | claude-haiku-5-5_v3 | strict+alias | 0.696 | 0.743 | 0.047 | 0.010 | 0.085 | no |
| qwen_qwen3.8-27b_v8 | qwen_qwen3.8-27b_v3 | strict | 0.676 | 0.677 | 0.001 | -0.043 | 0.037 | yes |
| qwen_qwen3.8-27b_v8 | qwen_qwen3.8-27b_v3 | lenient | 0.755 | 0.771 | 0.015 | -0.010 | 0.042 | yes |
| qwen_qwen3.8-27b_v8 | qwen_qwen3.8-27b_v3 | strict+alias | 0.682 | 0.683 | 0.001 | -0.043 | 0.038 | yes |
| qwen_qwen3.8-27b_v8 | claude-haiku-5-5_v8 | strict | 0.738 | 0.677 | -0.061 | -0.112 | -0.018 | no |
| qwen_qwen3.8-27b_v8 | claude-haiku-5-5_v8 | lenient | 0.817 | 0.771 | -0.047 | -0.079 | -0.015 | no |
| qwen_qwen3.8-27b_v8 | claude-haiku-5-5_v8 | strict+alias | 0.743 | 0.683 | -0.061 | -0.112 | -0.017 | no |

- claude-haiku-5-5_v8a vs claude-haiku-5-5_v3: strict +0.014 [-0.019, +0.050] -> interval contains 0 (difference not shown).
- claude-haiku-5-5_v8 vs claude-haiku-5-5_v8a: strict +0.027 [-0.007, +0.061] -> interval contains 0 (difference not shown).
- claude-haiku-5-5_v8 vs claude-haiku-5-5_v3: strict +0.041 [+0.007, +0.077] -> interval excludes 0.
- qwen_qwen3.8-27b_v8 vs qwen_qwen3.8-27b_v3: strict +0.001 [-0.043, +0.037] -> interval contains 0 (difference not shown).
- qwen_qwen3.8-27b_v8 vs claude-haiku-5-5_v8: strict -0.061 [-0.112, -0.018] -> interval excludes 0.

## 4. Prompt decision

Rule (fixed before results): choose v8 if strict F1(v8) >= F1(v8a) and strict P(v8) >= P(v8a) - 0.02 (Haiku, v3-proposed gold, same postings); else v8a.

| F1_strict_v8a | F1_strict_v8 | P_strict_v8a | P_strict_v8 | F1_rule_met | precision_rule_met | chosen |
|---|---|---|---|---|---|---|
| 0.7107 | 0.7377 | 0.7313 | 0.7586 | True | True | v8 |

**Chosen: v8.** Qwen was run on v8 only.

## 5. Per sector (v3-proposed gold, prompt v8)

| model | sector | postings | gold_items | P_strict | R_strict | F1_strict | P_lenient | R_lenient | F1_lenient | note |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | Admin / HR / Customer Service | 4 | 43 | 0.767 | 0.767 | 0.767 | 0.814 | 0.814 | 0.814 | too small to interpret |
| claude-haiku-5-5 | Engineering | 3 | 39 | 0.762 | 0.821 | 0.790 | 0.810 | 0.872 | 0.840 | too small to interpret |
| claude-haiku-5-5 | Finance + Accounting | 6 | 108 | 0.796 | 0.685 | 0.736 | 0.871 | 0.750 | 0.806 |  |
| claude-haiku-5-5 | Health Care | 8 | 68 | 0.655 | 0.559 | 0.603 | 0.828 | 0.706 | 0.762 |  |
| claude-haiku-5-5 | IT | 9 | 217 | 0.795 | 0.802 | 0.798 | 0.868 | 0.876 | 0.872 |  |
| claude-haiku-5-5 | Legal | 4 | 42 | 0.625 | 0.595 | 0.610 | 0.800 | 0.762 | 0.780 | too small to interpret |
| claude-haiku-5-5 | Management | 5 | 51 | 0.694 | 0.667 | 0.680 | 0.816 | 0.784 | 0.800 |  |
| claude-haiku-5-5 | Mixed | 5 | 72 | 0.789 | 0.625 | 0.698 | 0.825 | 0.653 | 0.729 |  |
| claude-haiku-5-5 | Sales + Marketing | 6 | 69 | 0.771 | 0.783 | 0.777 | 0.814 | 0.826 | 0.820 |  |
| qwen/qwen3.8-27b | Admin / HR / Customer Service | 4 | 43 | 0.846 | 0.767 | 0.805 | 0.923 | 0.837 | 0.878 | too small to interpret |
| qwen/qwen3.8-27b | Engineering | 3 | 39 | 0.500 | 0.590 | 0.541 | 0.652 | 0.769 | 0.706 | too small to interpret |
| qwen/qwen3.8-27b | Finance + Accounting | 6 | 108 | 0.728 | 0.620 | 0.670 | 0.793 | 0.676 | 0.730 |  |
| qwen/qwen3.8-27b | Health Care | 8 | 68 | 0.662 | 0.632 | 0.647 | 0.738 | 0.706 | 0.722 |  |
| qwen/qwen3.8-27b | IT | 9 | 217 | 0.845 | 0.751 | 0.795 | 0.907 | 0.806 | 0.854 |  |
| qwen/qwen3.8-27b | Legal | 4 | 42 | 0.523 | 0.548 | 0.535 | 0.750 | 0.786 | 0.767 | too small to interpret |
| qwen/qwen3.8-27b | Management | 5 | 51 | 0.632 | 0.471 | 0.539 | 0.842 | 0.627 | 0.719 |  |
| qwen/qwen3.8-27b | Mixed | 5 | 72 | 0.638 | 0.514 | 0.569 | 0.759 | 0.611 | 0.677 |  |
| qwen/qwen3.8-27b | Sales + Marketing | 6 | 69 | 0.727 | 0.580 | 0.645 | 0.818 | 0.652 | 0.726 |  |

## 6. Error breakdown (lenient, v3-proposed gold)

Classes are checked in this order; each error is counted once. 'Original' = gold label with no audit finding.

| run | error | class | count |
|---|---|---|---|
| claude-haiku-5-5_v8 | miss | audit_added_or_revised | 22 |
| claude-haiku-5-5_v8 | miss | original | 97 |
| claude-haiku-5-5_v8 | miss | review | 26 |
| claude-haiku-5-5_v8 | extra | REVIEW candidate | 24 |
| claude-haiku-5-5_v8 | extra | near-miss wording | 15 |
| claude-haiku-5-5_v8 | extra | other | 43 |
| claude-haiku-5-5_v8 | extra | single word | 24 |
| claude-haiku-5-5_v8 | extra | trait | 1 |
| qwen_qwen3.8-27b_v8 | miss | audit_added_or_revised | 26 |
| qwen_qwen3.8-27b_v8 | miss | original | 144 |
| qwen_qwen3.8-27b_v8 | miss | review | 23 |
| qwen_qwen3.8-27b_v8 | extra | REVIEW candidate | 13 |
| qwen_qwen3.8-27b_v8 | extra | near-miss wording | 19 |
| qwen_qwen3.8-27b_v8 | extra | other | 51 |
| qwen_qwen3.8-27b_v8 | extra | rule-list violation | 3 |
| qwen_qwen3.8-27b_v8 | extra | single word | 28 |
| qwen_qwen3.8-27b_v5 | miss | audit_added_or_revised | 22 |
| qwen_qwen3.8-27b_v5 | miss | original | 123 |
| qwen_qwen3.8-27b_v5 | miss | review | 25 |
| qwen_qwen3.8-27b_v5 | extra | REVIEW candidate | 18 |
| qwen_qwen3.8-27b_v5 | extra | near-miss wording | 16 |
| qwen_qwen3.8-27b_v5 | extra | other | 59 |
| qwen_qwen3.8-27b_v5 | extra | rule-list violation | 5 |
| qwen_qwen3.8-27b_v5 | extra | single word | 44 |
| qwen_qwen3.8-27b_v5 | extra | trait | 11 |

Near-miss pairs (extra shares a word with a missed gold item in the same posting): 71 pairs, all in `06_near_miss_pairs.csv`. First 15:

| run | n | extra | missed_gold |
|---|---|---|---|
| claude-haiku-5-5_v8 | 8 | patent prosecution | prosecuting patent applications |
| claude-haiku-5-5_v8 | 11 | vital signs | obtaining vitals |
| claude-haiku-5-5_v8 | 11 | injection administration | administering injections |
| claude-haiku-5-5_v8 | 19 | data warehousing | data warehouse |
| claude-haiku-5-5_v8 | 19 | data lineage | data warehouse |
| claude-haiku-5-5_v8 | 21 | audit scoping | Audit Reporting |
| claude-haiku-5-5_v8 | 21 | audit scoping | audit scope development |
| claude-haiku-5-5_v8 | 21 | audit scoping | audit testing |
| claude-haiku-5-5_v8 | 31 | testing methodologies | automated testing |
| claude-haiku-5-5_v8 | 31 | testing methodologies | API testing |
| claude-haiku-5-5_v8 | 42 | API development | API design |
| claude-haiku-5-5_v8 | 42 | 3rd Party Anypoint Connectors | MuleSoft Anypoint Connectors |
| claude-haiku-5-5_v8 | 42 | integration design | API design |
| claude-haiku-5-5_v8 | 47 | legal memoranda drafting | legal memorandum drafting |
| claude-haiku-5-5_v8 | 64 | process improvement | process optimization |

Top 10 postings by misses on original gold labels:

| run | n | misses_on_original_gold | missed |
|---|---|---|---|
| claude-haiku-5-5_v8 | 44 | 11 | key performance indicators; cross portfolio reporting; product launches; Commercial sales; Marketing planning; creative development; tactical communications; Microsoft Suite of Office; PPT; verbal communication; written communication |
| claude-haiku-5-5_v8 | 47 | 6 | discovery investigations; legal memorandum drafting; case evaluation; client counseling; client communication; state rules of civil procedure |
| claude-haiku-5-5_v8 | 64 | 6 | operational leadership; process optimization; performance monitoring; data driven decision making; resource allocation; contingency plans |
| claude-haiku-5-5_v8 | 80 | 6 | financial reporting; cost accounting; procedure documentation; collaboration; meet deadlines; analytical skills |
| claude-haiku-5-5_v8 | 11 | 4 | equipment maintenance; administering injections; obtaining vitals; computer software |
| claude-haiku-5-5_v8 | 29 | 4 | regulatory analysis; statistical software; legislative frameworks; analytical |
| claude-haiku-5-5_v8 | 31 | 4 | automated testing; test plans; API testing; software quality assurance |
| claude-haiku-5-5_v8 | 76 | 4 | retail sales; financial sales; complaint resolution; confidentiality |
| claude-haiku-5-5_v8 | 2 | 3 | sales plans; sales strategies; client relationships |
| claude-haiku-5-5_v8 | 33 | 3 | administrative support; supervisory skills; software implementation |
| qwen_qwen3.8-27b_v8 | 80 | 11 | financial management; financial reporting; cost accounting; process optimization; continuous improvement; internal controls; procedure documentation; collaboration; meet deadlines; Excel modeling; analytical skills |
| qwen_qwen3.8-27b_v8 | 44 | 10 | project controls; change controls; key performance indicators; cross portfolio reporting; product launches; Commercial sales; Marketing planning; creative development; tactical communications; Microsoft Suite of Office |
| qwen_qwen3.8-27b_v8 | 13 | 6 | material handling equipment; physical inventories; cycle counts; stock rotation; shrink-wrap machine; counting |
| qwen_qwen3.8-27b_v8 | 47 | 6 | discovery drafting; legal analysis; client counseling; client communication; writing; state rules of civil procedure |
| qwen_qwen3.8-27b_v8 | 64 | 6 | operational leadership; key performance indicators; data driven decision making; resource allocation; internal controls; contingency plans |
| qwen_qwen3.8-27b_v8 | 72 | 6 | back-end development; DevOps; containerization; container orchestration; observability; telemetry collection |
| qwen_qwen3.8-27b_v8 | 76 | 6 | retail sales; financial sales; problem resolution; complaint resolution; personal computer; security procedures |
| qwen_qwen3.8-27b_v8 | 2 | 5 | sales plans; sales strategies; market dynamics; brand localization; client relationships |
| qwen_qwen3.8-27b_v8 | 19 | 5 | data warehouse; macros; testing; UAT; data pipelines |
| qwen_qwen3.8-27b_v8 | 24 | 5 | selling techniques; suggestive selling; multiple selling; closing; proper lifting procedures |
| qwen_qwen3.8-27b_v5 | 44 | 10 | project controls; change controls; key performance indicators; cross portfolio reporting; product launches; Commercial sales; Marketing planning; creative development; tactical communications; Microsoft Suite of Office |
| qwen_qwen3.8-27b_v5 | 80 | 8 | financial management; cost accounting; process optimization; continuous improvement; procedure documentation; collaboration; meet deadlines; Excel modeling |
| qwen_qwen3.8-27b_v5 | 13 | 6 | material handling equipment; physical inventories; cycle counts; stock rotation; shrink-wrap machine; counting |
| qwen_qwen3.8-27b_v5 | 31 | 6 | automated testing; software testing principles; test strategies; test plans; test cases; software quality assurance |
| qwen_qwen3.8-27b_v5 | 64 | 6 | operational leadership; key performance indicators; data driven decision making; resource allocation; internal controls; contingency plans |
| qwen_qwen3.8-27b_v5 | 72 | 6 | back-end development; DevOps; containerization; container orchestration; observability; telemetry collection |
| qwen_qwen3.8-27b_v5 | 76 | 6 | retail sales; financial sales; problem resolution; complaint resolution; personal computer; security procedures |
| qwen_qwen3.8-27b_v5 | 47 | 5 | legal memorandum drafting; legal analysis; client counseling; client communication; writing |
| qwen_qwen3.8-27b_v5 | 6 | 4 | construction contract administration; construction plans and specifications; resource management; conflict resolution |
| qwen_qwen3.8-27b_v5 | 11 | 4 | infection control; equipment maintenance; triaging patients; obtaining vitals |

## 7. Instruction-following checks

| run | attention_to_detail_or_detail_oriented | scope_duplicate_items | rule_9_10_11_literal_matches | teamwork | team_player | evidence_verbatim_rate | json_failures |
|---|---|---|---|---|---|---|---|
| claude-haiku-5-5_v3 | 12 | 0 | 0 | 13 | 0 | 0.995 | 0 (earlier run, all done) |
| claude-haiku-5-5_v8a | 0 | 0 | 0 | 5 | 0 | 0.999 | 0 |
| claude-haiku-5-5_v8 | 0 | 0 | 0 | 5 | 0 | 0.991 | 0 |
| qwen_qwen3.8-27b_v3 | 11 | 0 | 4 | 10 | 0 | 0.987 | 0 (earlier run, all done) |
| qwen_qwen3.8-27b_v5 | 11 | 3 | 5 | 12 | 0 | 0.981 | 0 (earlier run, all done) |
| qwen_qwen3.8-27b_v8 | 0 | 0 | 3 | 8 | 0 | 0.973 | 0 |

Examples (max 5 per check and run):

| run | check | item |
|---|---|---|
| claude-haiku-5-5_v3 | trait | li_3891266921: attention to detail |
| claude-haiku-5-5_v3 | trait | li_3901945232: attention to detail |
| claude-haiku-5-5_v3 | trait | li_3887719486: attention to detail |
| claude-haiku-5-5_v3 | trait | li_3899527449: attention to detail |
| claude-haiku-5-5_v3 | trait | li_3886826327: attention to detail |
| qwen_qwen3.8-27b_v3 | trait | li_3891266921: attention to detail |
| qwen_qwen3.8-27b_v3 | trait | li_3901945232: attention to detail |
| qwen_qwen3.8-27b_v3 | trait | li_3887719486: attention to detail |
| qwen_qwen3.8-27b_v3 | trait | li_3886826327: attention to detail |
| qwen_qwen3.8-27b_v3 | trait | li_3894890877: attention to detail |
| qwen_qwen3.8-27b_v3 | rule list | li_3891854133: residential solar market |
| qwen_qwen3.8-27b_v3 | rule list | li_3889760266: General Liability |
| qwen_qwen3.8-27b_v3 | rule list | li_3889760266: Healthcare |
| qwen_qwen3.8-27b_v3 | rule list | li_3901680075: filing |
| qwen_qwen3.8-27b_v5 | trait | li_3891266921: attention to detail |
| qwen_qwen3.8-27b_v5 | trait | li_3901945232: attention to detail |
| qwen_qwen3.8-27b_v5 | trait | li_3887719486: attention to detail |
| qwen_qwen3.8-27b_v5 | trait | li_3886826327: attention to detail |
| qwen_qwen3.8-27b_v5 | trait | li_3894890877: attention to detail |
| qwen_qwen3.8-27b_v5 | rule list | li_3891854133: residential solar market |
| qwen_qwen3.8-27b_v5 | rule list | li_3889760266: General Liability |
| qwen_qwen3.8-27b_v5 | rule list | li_3889760266: Healthcare |
| qwen_qwen3.8-27b_v5 | rule list | li_3904949322: profitability |
| qwen_qwen3.8-27b_v5 | rule list | li_3904949322: accuracy |
| qwen_qwen3.8-27b_v5 | scope duplicate | li_3903813809: quarter-end close |
| qwen_qwen3.8-27b_v5 | scope duplicate | li_3903813809: month-end close |
| qwen_qwen3.8-27b_v5 | scope duplicate | li_3903813809: year-end close |
| qwen_qwen3.8-27b_v8 | rule list | li_3889760266: General Liability |
| qwen_qwen3.8-27b_v8 | rule list | li_3889760266: Healthcare |
| qwen_qwen3.8-27b_v8 | rule list | li_3904949322: profitability |

Postings with gold skills but zero predictions:

| run | n | posting_id | gold_items | raw_answer |
|---|---|---|---|---|
| claude-haiku-5-5_v3 | 45 | li_3904944359 | 4 | {"skills": []} |
| claude-haiku-5-5_v8a | 45 | li_3904944359 | 4 | {"skills": []} |
| claude-haiku-5-5_v8 | 45 | li_3904944359 | 4 | {"skills": []} |
| qwen_qwen3.8-27b_v3 | 45 | li_3904944359 | 4 | {"skills": []} |
| qwen_qwen3.8-27b_v3 | 97 | li_3887717230 | 3 | {"skills": []} |
| qwen_qwen3.8-27b_v5 | 45 | li_3904944359 | 4 | {"skills": []} |
| qwen_qwen3.8-27b_v5 | 97 | li_3887717230 | 3 | {"skills": []} |
| qwen_qwen3.8-27b_v8 | 45 | li_3904944359 | 4 | {"skills": []} |
| qwen_qwen3.8-27b_v8 | 97 | li_3887717230 | 3 | {"skills": []} |

## 8. Types

| run | items | skill | knowledge | tool | other_types |
|---|---|---|---|---|---|
| claude-haiku-5-5_v8a | 670 | 365 | 113 | 192 | 0 |
| claude-haiku-5-5_v8 | 671 | 365 | 115 | 191 | 0 |
| qwen_qwen3.8-27b_v8 | 630 | 342 | 115 | 173 | 0 |

30 random typed items per model (seed 0) for a human check: `08_type_sample_for_human_check.csv` (`human_check` left empty).

## 9. Tokens, limits and cost

| model | run | in_mean | in_median | in_max | out_mean | out_median | out_max | total_mean | calls |
|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | claude-haiku-5-5_v8 | 3390 | 3408 | 4182 | 1615 | 1677 | 3212 | 5005 | 50 |
| qwen/qwen3.8-27b | qwen_qwen3.8-27b_v8 | 2038 | 2040 | 2537 | 481 | 427 | 1229 | 2519 | 50 |

- Qwen hidden reasoning share: **not recorded** (the extractor stores only `completion_tokens`; `reasoning_format=hidden` output tokens include the reasoning).
- Qwen v8 calls: 50 paid (36 + 14 on resume), 0 failed, 14 retries after 429.
- Groq limits (headers 2026-10-30T05:22:19+00:00): requests/day 1000, tokens/min 8000. Tokens/day is not in the headers; read it on the console Limits page.
- Groq tokens logged in the 24 h before the long 429s: 258,123.

| model | assumption | total_tokens_2000 | days_by_tokens | days_by_requests | cost_usd |
|---|---|---|---|---|---|
| qwen/qwen3.8-27b | TPD 200,000 (Dhanush's figure, unmeasured) | 5037240 | 25.2 | 2.0 | 0.00 |
| qwen/qwen3.8-27b | TPD 258,123 (Groq tokens logged in the 24 h before the long 429s began: an estimate of the real TPD) | 5037240 | 19.5 | 2.0 | 0.00 |
| claude-haiku-5-5 | standard price, https://platform.claude.com/docs/en/about-claude/pricing (read 2026-10-30) | 10009200 |  |  | 2.29 |
| claude-haiku-5-5 | Message Batches API (50% off; not yet checked for this key) | 10009200 |  |  | 1.15 |

## 10. Independence check

`src/bias_check.py --split dev` (gold_labels.csv v1, lenient):

```
dev: 50 postings | gold 684 = kept 383 + human-added 301 (44% added) | suggestions dropped by human 78/461
  claude-haiku-5-5:v8              recall kept 299/383 = 0.78 | recall human-added 229/301 = 0.76
  qwen/qwen3.8-27b:v8              recall kept 264/383 = 0.69 | recall human-added 219/301 = 0.73
  claude-haiku-5-5:v3              recall kept 316/383 = 0.83 | recall human-added 237/301 = 0.79
  qwen/qwen3.8-27b:v3              recall kept 277/383 = 0.72 | recall human-added 236/301 = 0.78
```

v3-proposed gold split by v2 `suggested_skills` (strict match = accepted suggestion):

| model | gold_part | items | recall_strict | recall_lenient |
|---|---|---|---|---|
| claude-haiku-5-5 | accepted LLM suggestion | 384 | 0.742 | 0.815 |
| claude-haiku-5-5 | human-added / rewritten | 325 | 0.689 | 0.775 |
| qwen/qwen3.8-27b | accepted LLM suggestion | 384 | 0.635 | 0.719 |
| qwen/qwen3.8-27b | human-added / rewritten | 325 | 0.643 | 0.748 |

## 11. Ten example postings (one per sector in `n` order, then by `n`)

✓ = matched a gold item (lenient). Unmarked = extra.

| n | sector | gold | haiku_v8 | qwen_v8 |
|---|---|---|---|---|
| 2 | Sales + Marketing | sales plans; sales strategies; market analysis; market dynamics; home energy storage; brand localization; client relationships; negotiation; communication; problem-solving; English | ✓brand localization; ✓market analysis; ✓home energy storage; ✓market dynamics; ✓negotiation; ✓communication; ✓problem solving; teamwork; ✓English | sales planning; ✓market analysis; ✓negotiation; ✓problem-solving; ✓communication; teamwork; ✓English; ✓home energy storage |
| 3 | Mixed | Diesel mechanics; M5 planner; power tools; hand tools; hydraulic equipment maintenance; computer literacy; diagnostic software; safety regulations; CNG vehicle maintenance; heavy-duty truck repair; electrically operated equipment maintenance; repair scheduling | diagnosis; ✓M5 planner; ✓safety regulations; ✓power tools; ✓hand tools; ✓diagnostic software; ✓computer literacy | heavy duty diesel trucks; rolling stock; CNG equipment; gas equipment; ✓electrically operated equipment; ✓M5 planner; ✓safety regulations; ✓power tools; ✓hand tools; ✓hydraulic equipment; ✓diesel mechanic; ✓computer literacy; ✓diagnostic software |
| 5 | Sales + Marketing | prospecting; strategic sales approach; Salesforce; LinkedIn Sales Navigator; G-Suite; SalesLoft; Similarweb; Chili Piper; 6Sense; communication; interpersonal skills; phone skills; organization; time management; active listening; prioritization | ✓Salesforce; ✓LinkedIn Sales Navigator; ✓G-Suite; ✓SalesLoft; ✓Similarweb; ✓Chili Piper; ✓6Sense; ✓communication; ✓interpersonal; ✓phone; ✓organization; ✓time management; ✓prioritization; ✓active listening; ✓strategic sales approach; ✓prospecting | ✓Salesforce; ✓LinkedIn Sales Navigator; ✓G-Suite; ✓SalesLoft; ✓Similarweb; ✓Chili Piper; ✓6Sense; ✓communication; ✓interpersonal skills; ✓organization; ✓phone skills; ✓time management; ✓prioritization; ✓active listening; ✓strategic sales |
| 6 | Engineering | engineering analysis; highway construction; construction contract administration; construction plans and specifications; construction documents; personnel management; resource management; conflict resolution; leadership | ✓construction specifications; procurement rules; ✓highway construction; quality standards; safety processes; ✓engineering analysis; ✓conflict resolution; ✓leadership; coaching; supervision; ✓personnel management; continuous improvement | ✓engineering analysis; ✓highway construction; ✓personnel management; ✓leadership; supervision; problem solving |
| 8 | Legal | biological sciences; drafting patent applications; prosecuting patent applications; IP due diligence; FTO analysis; litigation; written communication; oral communication; organization | ✓biological sciences; ✓patent application drafting; patent prosecution; ✓IP due diligence; ✓FTO analyses; ✓organization; ✓written communication; ✓oral communication; client service | ✓patent application drafting; patent prosecution; ✓IP due diligence; ✓FTO analyses; ✓litigation; post-grant; ✓organization; ✓written communication; ✓oral communication |
| 11 | Health Care | infection control; equipment maintenance; urinalysis; microscopic preparation; EHR; sterilization; disinfection; triaging patients; phlebotomy; administering injections; obtaining vitals; processing specimens; customer service; medical terminology; ICD-9; CPT-4 Codes; written communication; computer software; database skills; HIPAA compliance; multitasking; problem-solving; typing; verbal communication | vital signs; ✓dip urinalysis; ✓microscopic preparation; ✓specimen processing; ✓triaging patients; ✓EHR; OSHA; MOSHA; ✓infection control; ✓sterilization; ✓disinfection; biohazardous waste policy; ✓phlebotomy; injection administration; ✓medical terminology; ✓ICD-9; ✓CPT-4; ✓customer service; ✓verbal communication; ✓written communication; ✓database; ✓multitasking; ✓problem-solving; ✓HIPAA; ✓typing | vital signs; ✓urinalysis; ✓microscopic preparation; ✓EHR; OSHA/MOSHA; ✓sterilization and disinfection practices; biomedical waste disposal; ✓customer service; ✓medical terminology; ✓ICD-9; ✓CPT-4 Codes; ✓verbal communication; ✓written communication; ✓computer software; ✓database skills; ✓HIPAA; ✓multitasking; ✓problem-solving; ✓typing; ✓triaging patients; ✓phlebotomy; ✓administering injections; ✓processing specimens |
| 12 | IT | AWS; AWS APIs; Python; Node.js; S3; DynamoDB; Lambda; API Gateway; AWS SDKs; AWS IAM; OAuth; RESTful API design; serverless architecture; microservices; API testing; Postman; Swagger; CI/CD pipelines; DevOps; problem-solving; collaboration | ✓Python; ✓Node.js; ✓AWS APIs; ✓AWS services; ✓S3; ✓DynamoDB; ✓Lambda; requirements gathering; ✓collaboration; error handling; documentation; ✓RESTful API design; ✓AWS IAM; ✓OAuth; ✓serverless architecture; ✓microservices development; ✓problem solving; ✓API Gateway; ✓AWS SDKs; AWS developer tools; ✓Postman; ✓Swagger; ✓API testing; ✓CI/CD pipelines; ✓DevOps | ✓Python; ✓Node.js; ✓AWS APIs; ✓S3; ✓DynamoDB; ✓Lambda; ✓RESTful API design; ✓AWS IAM; ✓OAuth; ✓serverless architecture; ✓microservices development; ✓problem-solving; ✓API Gateway; ✓AWS SDKs; ✓Postman; ✓Swagger; ✓CI/CD pipelines; ✓DevOps practices |
| 13 | Management | distribution; warehousing; RF technologies; forklift operation; material handling equipment; OSHA standards; physical inventories; cycle counts; stock rotation; shrink-wrap machine; reading; counting; legible writing; simple math | ✓forklift; ✓material handling equipment; ✓shrink-wrap machine; ✓RF technologies; ✓OSHA; order picking; ✓cycle counting; ✓physical inventory; ✓stock rotation; ✓simple math; ✓legible writing | ✓forklift; ✓RF technologies; ✓OSHA; ✓reading; ✓writing; ✓math; teamwork |
| 15 | Admin / HR / Customer Service | Microsoft Office Suite; communication; interpersonal skills; organization | ✓communication; ✓interpersonal; ✓Microsoft Office Suite; ✓organization | ✓communication; ✓interpersonal skills; ✓Microsoft Office Suite; ✓organization |
| 21 | Finance + Accounting | IT Audit; Risk-Based Audit Planning; Information Security; Regulatory Compliance; Third-Party IT Risk Assessment; Audit Reporting; Bank Secrecy Act; Privacy Act Compliance; leadership; mentoring; audit scope development; audit testing; evidence analysis; IT general controls; data flows; oral presentations; IT consulting | ✓IT audit; ✓risk assessment; ✓risk-based audit planning; audit scoping; ✓consulting; ✓mentoring; ✓oral presentations; third-party vendor risk; ✓IT general controls; ✓information security; ✓regulatory compliance; IT governance; ✓Bank Secrecy Act; ✓Privacy Act | ✓IT audit; ✓IT consulting; ✓information security; risk-based annual internal audit plan; ✓regulatory compliance; audit reports; work papers; interviews; written reports; ✓oral presentations; ✓Bank Secrecy Act; ✓Privacy Act |

## 12. Facts for the batch decision (no recommendation)

| model | F1_strict | F1_lenient | Qwen_minus_Haiku_strict_ci95 | 2000_postings | independence |
|---|---|---|---|---|---|
| claude-haiku-5-5 (v8) | 0.738 | 0.817 |  | $2.29 standard / $1.15 batch, paid key | strict recall accepted-suggestion minus human-added: +0.053; Claude model, same family as the suggesting LLM |
| qwen/qwen3.8-27b (v8) | 0.677 | 0.771 | -0.061 [-0.112, -0.018] | 25.2 days at 200k TPD; 19.5 days at ~258,123 (observed); free | strict recall accepted-suggestion minus human-added: -0.008; not a suggesting model |

## 13. Problems found

1. `tests/test_core.py:97-101` `test_reproduce_official_test_score` runs `evaluate.py --split test`; running the full test suite scores the test split. It also fails now: `evaluate.py` prints only the first 12 report lines and the `**All**` row moved below them (Desktop's 2 new header lines). It was run once by accident on 2026-10-30 (old v3 predictions, numbers unchanged, report file reverted); skipped since.
2. `tests/test_core.py:72` expected `validate_output` items without the `type` key (stale since `--typed`); fixed in `768d388`.
3. Instructions name `data/skill_aliases_manual.csv`; the file is `config/skill_aliases_manual.csv`.
4. `src/evaluate.py:166-172` report name has no baseline in it: `--baseline X` and `--baseline Y` for the same run write the same `..._paired.md` (second overwrites first). Numbers here come from this script instead.
5. `prompts/skill_extraction_v8.txt`: the duty scan is rule 17 but sits between rules 12 and 13 (numbering out of order). Not edited (hard rule 3).
6. `src/extract_skills.py` GroqBackend stores only `completion_tokens`, so Qwen's hidden reasoning share cannot be reported.
7. The Qwen run is a child of the Claude Code session: it stopped when the session ended during a 429 wait. For the 2,000 batch, run it outside Claude Code (or as a scheduled task).
8. Groq tokens/day is not in the response headers; 1,121 s retry-after waits started after 258,123 Groq tokens in 24 h.
9. `CLAUDE.md` (cache row) still says the key is model + prompt + text and 'never change the formula'; since 2026-10-30 call settings are in the key (old caches via `--legacy-cache-key`).
10. `gold_labels_v3_dev_proposed.csv` has no `sector_fixed`; all scores here use `gold_split.csv` sector_eval.

## 14. Files produced

- `reports/v8_dev_evaluation_2026-10-30.md` (this file)
- `scripts/v8_dev_report.py` (builds this report)
- `data/processed/statements_*`, `typed_*`, `extraction_postings_*`, `cache_keys_*` for claude-haiku-5-5_v8a, claude-haiku-5-5_v8, qwen_qwen3.8-27b_v8
- run logs and limits: `reports/v8_dev_evaluation_2026-10-30/run_*.log`, `run_*_start.txt`, `run_Q8_stops.txt`, `groq_limits_headers.json`
- `reports/v8_dev_evaluation_2026-10-30/01_run_manifest.csv`
- `reports/v8_dev_evaluation_2026-10-30/01_input_files.csv`
- `reports/v8_dev_evaluation_2026-10-30/02_main_results.csv`
- `reports/v8_dev_evaluation_2026-10-30/03_paired_comparisons.csv`
- `reports/v8_dev_evaluation_2026-10-30/04_prompt_decision.csv`
- `reports/v8_dev_evaluation_2026-10-30/05_per_sector.csv`
- `reports/v8_dev_evaluation_2026-10-30/06_error_classes.csv`
- `reports/v8_dev_evaluation_2026-10-30/06_near_miss_pairs.csv`
- `reports/v8_dev_evaluation_2026-10-30/06_top_miss_postings.csv`
- `reports/v8_dev_evaluation_2026-10-30/07_instruction_checks.csv`
- `reports/v8_dev_evaluation_2026-10-30/07_examples.csv`
- `reports/v8_dev_evaluation_2026-10-30/07_zero_predictions.csv`
- `reports/v8_dev_evaluation_2026-10-30/08_type_sample_for_human_check.csv`
- `reports/v8_dev_evaluation_2026-10-30/08_type_distribution.csv`
- `reports/v8_dev_evaluation_2026-10-30/09_tokens_per_posting.csv`
- `reports/v8_dev_evaluation_2026-10-30/09_projection_2000.csv`
- `reports/v8_dev_evaluation_2026-10-30/10_independence.csv`
- `reports/v8_dev_evaluation_2026-10-30/11_examples.csv`
- `reports/v8_dev_evaluation_2026-10-30/12_batch_facts.csv`
