# Gold Set Labeling Rules (Section B — Skills)

Read these before you label. All three of us must follow the same rules.

## What counts as a skill

A skill is something a person can **know** or **do** that the job asks for.

| Label it | Example |
|---|---|
| Tools and software | Python, SQL, Excel, Salesforce, AutoCAD |
| Methods and techniques | statistical analysis, agile, financial modeling |
| Knowledge areas | accounting principles, HIPAA compliance, contract law |
| Soft skills | written communication, leadership, negotiation |
| Languages | Spanish |

## What does NOT count

| Do not label | Why | Example |
|---|---|---|
| Degrees | Qualification, not a skill | "Bachelor's degree" |
| Years of experience | A quantity, not a skill | "5+ years" → label only the skill after it |
| Licenses / certifications | Qualification | "CPA license", "RN license" |
| Task-only duties | Section A's job | "manage the sales team", "drive large work streams" |
| Personality traits | Too vague | "self-starter", "passionate" |
| Benefits, company info | Not a requirement | "401k", "fast-paced environment" |

## How to write each skill

1. Write **one skill per item**. "Python and SQL" → `Python; SQL`
2. Use the **wording from the posting**. Do not rename or "improve" it.
3. Prefer **short** labels of 1–4 words. "strong verbal and written communication skills" → `verbal communication; written communication`.
   Keep the full name of a tool, standard, law or concept when shortening it would change its meaning
   (`Unfunded Mandates Reform Act`, not `Mandates Act`).
4. Remove filler words: "strong", "excellent", "proficiency in", "skills".
5. Label each skill **once** per posting, even if it appears twice ("Excel" three times → `Excel` once).
   Do not merge **different** skills because they are related (`SQL` and `database management` stay two);
   synonyms are merged later by the alias table, not while labelling.
6. Separate skills with `;` in the `gold_skills` column.

## Where to look

Read the **whole** description. Skills often hide in the duties section, not only in "Requirements".

**Duties rule (team decision 2026-10-07):** a duty that **names** a tool, method or knowledge area is
labelled ("Build prototypes" → `prototyping`; "reconcile accounts in QuickBooks" → `QuickBooks`).
A duty that names none is a task: skip it, and do not invent the skill it implies.
If the skill is also in the requirements, label it once, as required.

## Audit decisions (PROPOSED 2026-10-18 — team to confirm before the gold audit)

**A. Named laws, standards and tools are atomic.** Label each one separately when the posting asks for
knowledge of it or ability to use it. A name that only appears in passing is not a skill.
- "Knowledge of the Paperwork Reduction Act and Administrative Procedure Act" → `Paperwork Reduction Act; Administrative Procedure Act`
- "Experience with SAP, Chempax and Concur" → `SAP; Chempax; Concur` (not one grouped item)
- "Experience with legislative frameworks" (no names given) → `legislative frameworks`
- **Required vs incidental:** label it only when the posting asks for knowledge or proficiency. "Our
  clients include hospitals" → nothing. Keep the meaning of the phrase (rule D):

  | Posting wording | Label |
  |---|---|
  | "Knowledge of HIPAA" | `HIPAA` |
  | "HIPAA compliance experience" | `HIPAA compliance` |
  | "Familiarity with HIPAA regulations" | `HIPAA regulations` |
- **Industries / practice areas are not skills by themselves:** "General Liability" alone → nothing;
  "knowledge of General Liability law" → `General Liability law`.
- A specific item and a broad one are **different** skills when scoring ("Paperwork Reduction Act" ≠
  "legislative frameworks").

**B. Specialised duties → the underlying skill.** A duty counts when it names an ability, method, tool or
knowledge area (this extends the duties rule above). A routine duty does not.

| Posting wording | Label |
|---|---|
| Develop data models | `data modeling` |
| Draft affidavits | `affidavit drafting` |
| Draft settlement agreements | `settlement agreement drafting` |
| Troubleshoot data pipelines | `troubleshooting` |
| Attend court hearings | not a skill (unless a distinct skill is also stated) |
| Responsible for customer invoices | not a skill (unless invoicing is asked for as a skill/method) |
| Process routine paperwork | not a skill |
| File and maintain records | not a skill |

Test: does the phrase support a specific ability, method, tool or knowledge area, or does it only
describe something the employee does?

**C. Soft skills only when the posting asks for them**, anywhere in the posting (not only under a
"Requirements" heading). Do not add `teamwork`, `organization` or `communication` because the job
"sounds like" it needs them.

| Wording | Decision |
|---|---|
| "Strong written communication skills" | `written communication` |
| "Ability to prioritize competing deadlines" | `prioritization` |
| "Strong collaboration skills" | `collaboration` |
| "Works effectively with cross-functional teams" | `collaboration` |
| "Works well with others" | `collaboration` |
| "Partners with engineers to define features" | `collaboration` (clearly worded collaborative duty) |
| "The role involves working with engineers" | not a skill (collaboration only inferred from the role) |
| "We value passionate, energetic people" | not a skill (trait) |
| "This is a fast-paced environment" | not a skill (environment) |

Rule: accept `collaboration` when the wording directly states a collaboration ability or a collaborative
duty; never infer `collaboration` or `teamwork` from the role's context alone.

**D. How far a label may be rewritten.** Keep the employer's wording. Allowed: minimal grammar changes
(plural → singular, drop filler words) and turning a stated action into its skill ("build prototypes" →
`prototyping`). Not allowed: replacing a term with a broader, narrower or merely related concept
("draft affidavits" → ~~`legal expertise`~~). Synonyms (IIS = Internet Information Services) are handled
later by the alias table, not while labelling.
Action-to-skill conversion is allowed only when the underlying ability, method, tool or knowledge area is
clear. Keep the original meaning and do not add a capability the text does not support. When evidence is
collected (the LLM's output), the exact source phrase is stored separately from the label.

**E. ESCO and O\*NET are the rule book for doubtful items** (decided by Dhanush 2026-10-20; we have no
Lightcast access, so the two open libraries are the grounding reference).
- Sources: ESCO v1.2 and O\*NET 31.0, downloaded by `src/download_reference.py` into `data/reference/`.
- **Trait (not a skill):** the item matches an O\*NET Work Style or one of ESCO's 18 *transversal* "attitudes
  and values" items (`esco_attitudes.csv` joined to `reuse_level = transversal`). Examples: attention to
  detail, dependability, initiative, adaptability, work independently, cope with pressure. Both libraries
  call **attention to detail** a trait, so it is no longer labelled (this reverses the old soft-skill rule).
- **Skill:** the item matches an ESCO skill/knowledge item or an O\*NET Software Skill / Knowledge /
  Essential / Transferable Skill.
- **Neither library has it:** a human decides, using rules A–D. It is never rejected only because it is
  missing (ESCO misses many US tools and legal procedures).
- The evidence phrase must still come from the posting. The library decides *what kind* of item it is, not
  whether the posting asks for it.
- Applied by script to dev and test in the same way (`gold_labels_v2.csv`); gold v1 is kept for comparison.

## When unsure

- Write the case in the `notes` column.
- Bring it to the team. Agree, then add the decision to this file.
- Do **not** look at any LLM output before you finish a posting.

## Worked example

> "We need a Data Analyst with 3+ years of SQL and Python experience. Experience with Tableau or Power BI preferred. Strong communication skills. Bachelor's degree required. You will build weekly sales reports."

`gold_skills`: `SQL; Python; Tableau; Power BI; communication`

Not labeled: "3+ years" (quantity), "Bachelor's degree" (qualification), "build weekly sales reports"
(task-only duty: it names no tool or method).
