# Pre-registered decision rule: two-pass (v8 + duties) vs v8

Written 2026-10-30T19:39:06Z, before any v8+duties run was scored.

Per model (Qwen, Haiku), on the v3-proposed dev gold, same 50 postings:
- Adopt the two-pass setup if strict F1(v8+duties) >= strict F1(v8)
  AND strict P(v8+duties) >= strict P(v8) - 0.02.
- Otherwise keep v8 (one pass).
Same rule as the v8 vs v8a decision. Not to be changed after seeing results.

Merge dedupe (decided 2026-10-30T19:40:10Z, before scoring, by Dhanush): drop a duty item only when evaluate.py's
norm() + strict match says it equals an item already kept for that posting. -ing / plural variants such as
"cycle counts" / "cycle counting" are kept; their number is counted and reported.
