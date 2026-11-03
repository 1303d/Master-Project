# Rules review pack — 2026-10-29

For Priyanka and Lochan. Please read this page first (5 minutes), then the proposal.

## Files in this pack

| File | What it is |
|---|---|
| `README.md` | This page: the problem, what we agreed, the plan, the research |
| `rules_F_G_proposal.md` | **The proposal to review**: rule F (one context rule) and rule G (examples for all 8 sectors) |
| `LABELING_RULES.md` | The current rules A–E, for reference. Rule A now has a longer HIPAA table (added 2026-10-29) |
| `pipeline_plan.mmd` | The plan as a Mermaid diagram (paste it into mermaid.live to see it) |

## 1. The problem

The LLM extractor finds skill words in the JD. But a skill word is not always a skill.

- Nurse JD: "Maintain patient confidentiality per HIPAA" → the nurse must apply the law → **skill**.
- Developer JD: "Build features for our HIPAA-compliant messaging app" → it describes the product → **not a skill**.

Both contain "HIPAA". Only the sentence tells them apart. Our noise review hit this case (row #79).
not_a_skill counts (about 815 different skills each): Priyanka 94 (11.5%, final file
`noise_review_Priyanka_FINAL.xlsx`, a note on each row), Lochan 26, Dhanush 47 (pre-filled by Claude,
not yet edited by Dhanush). Each of us reviewed different skills, so these counts are not an agreement score.

ESCO has no HIPAA entry. The closest is the knowledge "health care legislation". In O\*NET it is "Law and Government".

## 2. What we agreed (Dhanush, with Claude and GPT review)

1. **One rule for all 8 sectors, not 8 rulebooks.** The test: does the *worker* have to know or use it,
   or does it only describe the product, company or setting? (rule F)
2. **The sector helps to read a phrase. It never adds a skill.** No skill from the job title, industry,
   or "what this job usually needs".
3. **Pick the sector from the worker's duties**, not the employer or the noisy `sector_fixed` column.
   A developer at a hospital follows the Tech examples.
4. **ESCO / O\*NET decide what *kind* of item it is, not *whether* the posting asks for it** (same as rule E).
   An item missing from both libraries is never rejected for that reason alone.
5. **Sector examples (rule G) for all 8 sectors + mixed.** Tech and Medical come from Priyanka's draft.
   The other six are drafts with real sentences from the **dev** gold postings (never the test postings).
   We add more examples only where we disagree.
6. **Core vs additional is not a labelling question.** Example: "knowledge of securities law" in a finance
   posting is labelled as a skill. Later the counts show how many finance postings ask for it
   (e.g. 15% → additional finance skill, 90% → core). ESCO does the same with essential / optional skills.
7. **"Preferred" skills still count.** A required/preferred tag may be added later as extra information.

## 3. The plan

```
JD
 → 1. LLM extracts skill + evidence        (exists, prompt v3)
 → 2. Context check: worker needs it?      (NEW, prompt v4, rule F)
        no      → drop, save the reason
        unclear → review queue (the existing new_candidate queue)
        yes     → continue
 → 3. ESCO / O*NET match, exact + meaning  (exists, link_reference.py)
 → 4. Skill saved with evidence + reason
 → 5. Test v3 vs v4 on the dev set (strict and lenient F1). Test set untouched.
 → 6. Later: dictionary scan for missed skills, only if recall is low
 → 7. Sprint 4: count per sector → core vs additional
```

## 4. What research says (all papers checked to exist)

- **SkillSpan** (Zhang et al., NAACL 2022): wrote clear labelling rules first, refined them in rounds and
  measured agreement between annotators (kappa ≈ 0.70–0.75). → We will measure our agreement too.
  https://aclanthology.org/2022.naacl-main.366/
- **Nesta Open Jobs Observatory** (2021): ESCO keyword matching gave many wrong matches, so they had to
  filter by context. → A keyword match alone does not prove a skill.
  https://www.nesta.org.uk/project-updates/skills-extraction-ojo/
- **Entity Linking in the Job Market Domain** (Zhang et al., EACL Findings 2024): extracting a skill and
  linking it to ESCO are separate tasks. → Matches our steps 2 and 3.
  https://aclanthology.org/2024.findings-eacl.28/
- **GOJA** (Krüger et al., EMNLP 2025): 500 German job ads; links each requirement to its role and context.
  → We store `context_type` and `reason` with each skill.
  https://aclanthology.org/2025.emnlp-main.1375/
- **SkiLLens** (De Santo et al., EACL 2026 industry): new skills not in ESCO, mapped with a human in the
  loop. → Same as rule E: missing from ESCO is not a reason to reject.
  https://aclanthology.org/2026.eacl-industry.65/
- **SRICL** (arXiv 2604.21525, 2026 preprint): retrieves relevant examples per posting. → Later idea: give
  the LLM only the Tech or Medical examples that fit the posting.
  https://arxiv.org/abs/2604.21525

## 5. What we need from you

1. Read `rules_F_G_proposal.md` and answer the 3 questions at its end.
2. Mark any example you think is wrong or missing.
3. When all three of us agree, Dhanush moves F and G into `LABELING_RULES.md` and removes "PROPOSED".
