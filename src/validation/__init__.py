"""Three-part gold-set validation (Section B). See docs/GOLD_VALIDATION_WORKFLOW.md.

Part 1 disagreements, Part 2 blind agreement check, Part 3 independent full-posting annotation,
plus team adjudication. Reviews are append-only event logs, one file per reviewer, so they sync through Git.
Gold files are never written: approved changes become a separate, versioned change set.
"""
