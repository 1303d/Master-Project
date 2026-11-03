# Two-pass (v8 + duties) vs v8, dev, v3-proposed gold

## Scores

```
model     setup  predicted  P_strict  R_strict  F1_strict  P_lenient  R_lenient  F1_lenient  F1_strict_alias
 qwen        v8        630     0.719     0.639      0.677      0.819      0.728       0.771            0.683
 qwen v8+duties        744     0.642     0.674      0.658      0.739      0.776       0.757            0.663
haiku        v8        671     0.759     0.718      0.738      0.841      0.795       0.817            0.743
haiku v8+duties        867     0.608     0.743      0.669      0.678      0.829       0.746            0.674
```

## Paired bootstrap (2,000 draws, same 50 postings)

```
model       metric  F1_v8  F1_two_pass   diff  ci95_low  ci95_high contains_0
 qwen       strict  0.677        0.658 -0.019    -0.030     -0.006         no
 qwen      lenient  0.771        0.757 -0.014    -0.027      0.000        yes
 qwen strict+alias  0.683        0.663 -0.019    -0.031     -0.006         no
haiku       strict  0.738        0.669 -0.069    -0.088     -0.051         no
haiku      lenient  0.817        0.746 -0.071    -0.090     -0.053         no
haiku strict+alias  0.743        0.674 -0.070    -0.088     -0.051         no
```

## Counts

```
model  items_added_after_merge  added_matched_gold_strict  added_matched_gold_lenient  original_misses_v8  original_misses_recovered  added_not_matching_gold  near_duplicate_pairs_after_merge  P_strict_collapsed (diagnostic)  F1_strict_collapsed (diagnostic)
 qwen                      114                         25                          34                 144                         27                       80                                 5                            0.644                             0.657
haiku                      196                         18                          24                  97                         18                      172                                 4                            0.610                             0.669
```

## Top 10 added items that did not match gold

```
model                                added_item_not_in_gold  count
 qwen                                 equipment maintenance      1
 qwen                                           diagnostics      1
 qwen                                  cng equipment repair      1
 qwen                             electric equipment repair      1
 qwen                       hydraulic equipment maintenance      1
 qwen              virtual electronic control units (vecus)      1
 qwen software defined vehicle (sdv) 2.0-based architecture      1
 qwen                             urine specimen collection      1
 qwen                                    forklift operation      1
 qwen                                        osha standards      1
haiku                                       troubleshooting      2
haiku                               vital signs measurement      2
haiku                                 regulatory compliance      2
haiku                         marketing campaign management      1
haiku                                        sales planning      1
haiku                             cng equipment maintenance      1
haiku                          safety regulation compliance      1
haiku                                   contract compliance      1
haiku                                  business development      1
haiku                                       project scoping      1
```

## Decision (pre-registered rule)

```
model  F1_strict_v8  F1_strict_two_pass  P_strict_v8  P_strict_two_pass decision
 qwen         0.677               0.658        0.719              0.642  keep v8
haiku         0.738               0.669        0.759              0.608  keep v8
```
