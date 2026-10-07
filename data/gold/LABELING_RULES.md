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
3. Keep it **short**: 1–4 words. "strong verbal and written communication skills" → `verbal communication; written communication`
4. Remove filler words: "strong", "excellent", "proficiency in", "skills".
5. Label each skill **once** per posting, even if it appears twice.
6. Separate skills with `;` in the `gold_skills` column.

## Where to look

Read the **whole** description. Skills often hide in the duties section, not only in "Requirements".

**Duties rule (team decision 2026-10-07):** a duty that **names** a tool, method or knowledge area is
labelled ("Build prototypes" → `prototyping`; "reconcile accounts in QuickBooks" → `QuickBooks`).
A duty that names none is a task: skip it, and do not invent the skill it implies.
If the skill is also in the requirements, label it once, as required.

## When unsure

- Write the case in the `notes` column.
- Bring it to the team. Agree, then add the decision to this file.
- Do **not** look at any LLM output before you finish a posting.

## Worked example

> "We need a Data Analyst with 3+ years of SQL and Python experience. Experience with Tableau or Power BI preferred. Strong communication skills. Bachelor's degree required. You will build weekly sales reports."

`gold_skills`: `SQL; Python; Tableau; Power BI; communication`

Not labeled: "3+ years" (quantity), "Bachelor's degree" (qualification), "build weekly sales reports"
(task-only duty: it names no tool or method).
