You are checking skill aliases for a skill taxonomy built from US job postings.
Use web search (Google) to check what each term means. Use ESCO (esco.ec.europa.eu)
and O*NET (onetonline.org) as the main references.

I attached an Excel file, `alias_check_Dhanush.xlsx`, with 109 rows. Each row has:
- "skill (from posting)": a skill phrase taken from a job posting.
- "proposed alias of": an existing skill that we think means the SAME thing.
- "evidence quote" and "job title": how the posting used the phrase.
- "Claude unsure?": "yes" means the first reviewer had doubts. Check these rows with extra care.

For each row, decide:
- **same**: a recruiter would treat both names as the same skill, at the same level of detail.
  Examples: "vlookup" = "excel formulas", "m&a" = "mergers and acquisitions", "meraki" = "cisco meraki".
- **different**: they are related but not the same. Common cases:
  - the target is broader (e.g. "construction pricing" vs "pricing"),
  - the target is narrower or a brand (e.g. "wireless access points" vs "aruba wireless access points"),
  - the meaning is different (e.g. "change impact analysis" vs "business impact analysis").
  If a better existing name is obvious, write it in "better target", otherwise leave it empty.
- **not_a_skill**: the phrase is not a skill at all (a work arrangement, a task, a degree,
  a licence or certification, an organisation name, or junk). Example: "remote work".

Rules:
1. Use the evidence quote and the job title to decide the meaning. Do not guess from the word alone.
2. Write a short reason (max 20 words). Mention the ESCO or O*NET entry if you found one.
3. Put one source URL that supports your verdict.
4. Do not change the columns n, skill, proposed alias of, evidence quote, job title.
5. If you are not sure, choose "different". It is safer than a wrong merge.

Return the same table with the columns "GPT verdict", "better target (optional)",
"GPT reason" and "source URL" filled in, as an Excel file or a table I can paste into Excel.
