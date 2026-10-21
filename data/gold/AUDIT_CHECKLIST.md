# Gold-set audit checklist (Sprint 3 prep)

Goal: fix gold labels that break `LABELING_RULES.md`, **without** letting the model's output decide.

## Before you start
- [ ] The team confirms decisions **A, B, C, D** in `LABELING_RULES.md` ("Audit decisions"). Change the
      heading from PROPOSED to AGREED with the date.
- [ ] Keep the original gold file unchanged: `gold_labels.csv` = **gold v1**. Audited labels go to
      `gold_labels_v2.csv`.
- [ ] Prompt and evaluation changes are frozen while the audit runs.

## Fairness rules
1. Judge every item only by **the posting text + the written rules**. Never by "the model found it".
2. Use the **blind sheet** (`reports/audit_dev_blind.csv`): it does not say where an item came from.
   Do not open `reports/audit_dev_key.csv` until all decisions are filled in.
3. Audit **dev and test the same way**. Test: re-check every gold item against rules A–D only
   (no model output is shown for test).
4. My earlier notes on the 67 v3 extras are **preliminary**: re-decide them blind.
5. Two people decide disputed items; disagreements go to the third (record who decided).

## For each item in the blind sheet
Read the posting (`py src/gold_tool.py show <n>`), then fill `decision`:

| decision | Meaning | Effect on gold v2 |
|---|---|---|
| `skill` | It is a skill under the rules | Add if missing |
| `not skill` | Task, trait, industry, outcome, qualification | Remove if present |
| `rename:<label>` | Skill, but the label breaks a rule (wording, grouping) | Replace with `<label>` |
| `split:<a>; <b>` | Grouped item | Replace with the parts |
| `unsure` | Needs team discussion | Unchanged until decided |

Also fill `reviewer` and, when useful, `note`.

## After the audit
- [ ] Build `gold_labels_v2.csv` from the decisions (script, not by hand).
- [ ] Re-score v2 and v3 on dev against **gold v1 and gold v2**; report both.
- [ ] Then the alias table, then the one-time **test** score, then the 2,000 postings.
