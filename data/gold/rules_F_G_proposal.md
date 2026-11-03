# Proposal: Rules F and G (add-on to LABELING_RULES.md)

Status: **PROPOSED 2026-10-29**. Sector draft by Priyanka. Revised by Dhanush (with Claude and GPT review).
The team confirms these together with rules A–E. Then they go into `LABELING_RULES.md` after rule E.

**Summary:** one rule for all 8 sectors. The sector helps to *read* a phrase. It never adds a skill the
posting does not ask for. Whether a skill is *core* or *additional* for a sector is not decided while
labelling. It comes later from counts across postings (Sprint 4).

---

## F. Context rule (all sectors)

Rules A–E still apply first. Degrees, licences, certifications, years of experience and traits are never
skills, in any sector.

**F1. Who needs the item?** The same words can mean different things.

| Posting wording | Who needs it | Label |
|---|---|---|
| "Maintain patient confidentiality per HIPAA" (nurse) | the worker must apply the law | `HIPAA` |
| "Build features for our HIPAA-compliant messaging app" (developer) | it describes the product | nothing |
| "Knowledge of securities regulations preferred" (finance) | the worker must know it | `securities regulations` |
| "We operate in a highly regulated financial market" | it describes the company | nothing |

- The worker must know or use it → skill (in requirements, preferred items or specialised duties).
- It only describes the product, company, clients, industry or setting → nothing (background).
- **"Preferred" still counts.** "Tableau preferred" → `Tableau`, as in the worked example. This applies
  to skills only: a preferred degree, licence, certification or trait is still excluded (rules A–E).

**F1b. Generic law phrases.** Label a compliance phrase when it names a specific law or standard, or a
domain of rules (safety, food safety, health and safety, employment law). Label nothing when it covers
"all laws" with no domain. This matches the existing gold labels (checked 2026-10-29):

| Posting wording | Label | Source |
|---|---|---|
| "Follow safety regulations, including proper lifting procedures" | `safety regulations; proper lifting procedures` | li_3889122912 (gold) |
| "adhere to health and safety standards" | `health and safety standards` | li_3887717230 (gold) |
| "Thorough knowledge of employment-related laws and regulations" | `employment-related laws and regulations` | li_3886890185 (gold) |
| "Ensures compliance with all applicable state and federal laws" | nothing (no domain) | li_3906221602 (not in gold) |
| "Ensures adherence to legal and regulatory requirements" | nothing (no domain) | li_3906080933 (not in gold) |

**F2. Do not infer.** Never add a skill only because of the sector, employer, job title, what the
occupation usually needs, or a match in ESCO/O\*NET.

**F3. Pick the sector from the worker's role and duties.** Do not use the employer's industry or the
`sector_fixed` column (LinkedIn job functions are noisy). A developer at a hospital follows the Tech
examples. A nurse giving clinical care follows the Medical examples. When a role spans both (for example,
healthcare IT integration), read the actual duties and apply what fits each item.

**F4. Steps for each item**
1. Apply rules A–E first. An item they exclude (degree, licence, certification, years, trait, routine
   task) stays excluded; the table below never brings it back.
2. Sentence check (F1): does the worker have to know or use it?
3. Reference check (optional): ESCO / O\*NET match from `link_reference.py` only. A person or an LLM must
   never guess that an item is "listed in O\*NET".

| Sentence check | Reference match | Label |
|---|---|---|
| Worker must know or use it | found | skill |
| Worker must know or use it | none | skill; note "possible new skill" → `new_candidate` review queue |
| Only describes product, company or setting | any | nothing |
| Unclear | found | do not add automatically; note it → `new_candidate` review queue |
| Unclear | none | note it → `new_candidate` review queue |

"Bring it to the team" means the existing `new_candidate` review queue (from `link_reference.py`), not a new process.

A reference match decides *what kind* of item it is (rule E). It never proves that the posting asks for it.
Note format: `sector: tech | role: <job title> | reason`.

---

## G. Sector examples

These are examples of rule F, not separate rules. All 8 sectors are covered (G1–G8), plus mixed postings
(G9). G1–G2 are from Priyanka's draft. G3–G9 are drafts by Dhanush: most examples are real sentences from
the **dev** gold postings (posting id shown), and the label is the one already in `gold_labels.csv`.
Never take examples from the test postings. Add more examples when the team disagrees on real postings.

### G1. Tech

Default for laws and standards: background, unless the role must build, secure, audit or comply with them.

| Rule | Posting wording | Label |
|---|---|---|
| T1 tools the worker uses | "Experience with React, Node.js and AWS" | `React; Node.js; AWS` |
| | "Python 3 required" | `Python 3` (keep the posting's wording, rule 2; the alias table links it to `Python`) |
| | "Our platform runs on AWS" | nothing (describes the company) |
| T2 laws/standards only with a compliance duty | "Implement HIPAA privacy and security controls" | `HIPAA` |
| | "Audit systems for compliance with HIPAA" | `HIPAA` |
| | "Ensure systems meet HIPAA and SOC 2 controls" | `HIPAA; SOC 2` |
| | "Handle PII in line with GDPR requirements" | `GDPR` |
| | "Build features for our HIPAA-compliant messaging app" | nothing |
| | "We are SOC 2 certified" | nothing |
| T3 named practices | "Practice pair programming and code reviews" | `pair programming; code review` |
| | "Set up CI/CD pipelines" | `CI/CD` |
| | "Write unit tests" | `unit testing` |
| | "Attend daily standups" / "Work on assigned tickets" | nothing (routine) |
| T4 duties that name a method (rule B) | "Design REST APIs" | `API design` |
| | "Troubleshoot production incidents" | `troubleshooting` |
| | "Conduct user research with customers" | `user research` |
| | "Join the on-call rotation" / "Support the engineering team" | nothing |
| T5 domain alone is not a skill | "Fintech startup" / "e-commerce company" | nothing |
| | "Knowledge of payments processing" | `payments processing` |
| T6 certifications | "AWS Certified Solutions Architect preferred" | nothing |
| | "AWS certification preferred; experience deploying on AWS" | `AWS` |

### G2. Nursing / Medical

Default for laws and standards: skill, when they control the worker's own practice.

| Rule | Posting wording | Label |
|---|---|---|
| M1 clinical procedures, even as duties | "Perform venipuncture" | `venipuncture` |
| | "Start and maintain IVs" | `IV insertion; IV maintenance` |
| | "Provide wound care and dressing changes" | `wound care; dressing changes` |
| | "Administer medications" | `medication administration` |
| | "Conduct patient assessments" | `patient assessment` |
| | "Perform CPR" | `CPR` |
| M2 laws in the worker's own practice | "Maintain patient confidentiality per HIPAA" | `HIPAA` |
| | "Follow OSHA bloodborne pathogen standards" | `OSHA bloodborne pathogen standards` |
| | "Handle controlled substances per DEA regulations" | `DEA regulations` |
| | "Knowledge of Joint Commission standards" | `Joint Commission standards` |
| | "Follow mandatory reporting requirements" | `mandatory reporting` |
| | "Our HIPAA-compliant patient portal" | nothing |
| M3 licences and certifications | "Active RN license" / "LPN" / "CNA" | nothing |
| | "BLS / ACLS / PALS certification required" | nothing |
| | "BLS certification required; able to perform CPR" | `CPR` |
| M4 clinical systems and equipment | "Experience with Epic or Cerner" | `Epic; Cerner` |
| | "Document care in the EHR" | `EHR documentation` |
| | "Operate infusion pumps" | `infusion pumps` |
| M5 clinical knowledge | "Knowledge of medical terminology" | `medical terminology` |
| | "Understanding of pharmacology" | `pharmacology` |
| | "ICD-10 and CPT coding" | `ICD-10 coding; CPT coding` |
| | "Infection control practices" | `infection control` |
| M6 units and settings alone | "2 years ICU experience" / "Med-Surg unit" | nothing (setting + years) |
| | "Knowledge of critical care nursing" | `critical care nursing` |
| M7 routine care duties | "Answer call lights" / "Assist patients as needed" | nothing |
| | "Keep rooms clean and stocked" | nothing |
| | "Provide patient education on discharge" | `patient education` |
| M8 patient-facing qualities (rules C, E) | "Compassionate, empathetic caregiver" | trait (O\*NET Work Style: Empathy) |
| | "Calm under pressure" | trait (O\*NET Work Style: Stress Tolerance) |
| | "Strong patient communication skills" | `patient communication` |

### G3. Engineering

Default: named tools, standards and methods the engineer uses are skills. Licences, insurance and
benefits text are not.

| Posting wording | Label | Source |
|---|---|---|
| "migrate design from … AUTOSAR to Software Defined Vehicle 2.0" | `AUTOSAR` | li_3904952109 |
| "experience with: verifying and validating … ECU signal data … using Diagnostic Trouble Codes" | `verification and validation; Diagnostic Trouble Codes` | li_3904952109 |
| "must possess and retain a current, valid class-appropriate driver's license" | nothing (licence) | li_3890891917 |
| "shall maintain the statutorily required liability insurance (Arizona Administrative Code …)" | nothing (condition of the job, not a skill) | li_3890891917 |
| "paid leave required by Federal, State or local law" | nothing (benefits) | li_3891039132 |
| "Knowledge of ASME / building codes" (example, not from gold) | `ASME codes` / `building codes` | — |

### G4. Sales + Marketing

Default: the industry the company sells into is background. Named product knowledge and sales tools are skills.

| Posting wording | Label | Source |
|---|---|---|
| "Deep understanding of the energy industry, including knowledge of home energy storage … and market dynamics" | `home energy storage; market dynamics` (not "energy industry") | li_3891854133 |
| "establish relationships with potential clients in the residential energy industry" | `client relationships` only | li_3891854133 |
| "Experience with SalesLoft, Similarweb, Chili Piper, 6Sense" | `SalesLoft; Similarweb; Chili Piper; 6Sense` | li_3905336446 |
| "Our primary goal is to deliver the best technology in the industry" | nothing (company) | li_3905336446 |
| "Follow safety regulations, including proper lifting procedures" | `safety regulations; proper lifting procedures` | li_3889122912 |
| "eager to learn, adaptable, and have the passion to be successful" | nothing (traits) | li_3905336446 |

### G5. Finance + Accounting

Default: a named law, standard or accounting system the worker must apply is a skill. The employer's
industry and general "we comply with the law" text are background.

| Posting wording | Label | Source |
|---|---|---|
| "ensure compliance of all business transactions with … the Bank Secrecy Act" | `Bank Secrecy Act` | li_3906221602 |
| "Implement and monitor internal controls to ensure compliance with financial policies" | `internal controls` | li_3902352352 |
| "Knowledge of SAP, Chempax, Concur, or other accounting systems is preferred" | `SAP; Chempax; Concur` | li_3902352352 |
| "Knowledge of cost accounting principles, financial statement preparation, and analysis" | `cost accounting; financial statement preparation; financial statement analysis` | li_3902352352 |
| "ALTIVIA is a leading chemical manufacturing company" | nothing (company) | li_3902352352 |
| "Newpark is transitioning … to a leading provider of sustainable technologies" | nothing (company) | li_3891263924 |
| "Knowledge of GAAP" (example, not from gold) | `GAAP` | — |
| "Ensures compliance with all applicable state and federal laws, company procedures and policies" | nothing (generic, names no law or area) | li_3906221602 |

### G6. Management (incl. operations and warehouse)

Default: named safety standards and systems the worker follows are skills. Leadership is labelled only
when the posting asks for it (rule C).

| Posting wording | Label | Source |
|---|---|---|
| "Comply with all local, OSHA or Expeditors' standards" | `OSHA standards` | li_3887719486 |
| "Our Zone utilizes a Warehouse Management System so technology is required to perform this job" | `Warehouse Management System` | li_3905331187 |
| "They establish robust internal controls, compliance processes, and contingency plans" | `internal controls; contingency plans` | li_3886210955 |
| "Performs general cleaning tasks to adhere to health and safety standards" | `health and safety standards` | li_3887717230 |
| "if you have a good understanding of the industrial, petrochemical … industry" | nothing (industry alone) | li_3904949322 |
| "Hilton has been a leader in the hospitality industry" / "Leadership – We're leaders in our industry" | nothing (company values, not a request) | li_3887717230 |

### G7. Legal

Default: named laws, rules and legal procedures the worker must know or do are skills. Practice areas the
firm works in, bar licences and the firm's own compliance are not.

| Posting wording | Label | Source |
|---|---|---|
| "Knowledge of federal and state rules of civil procedures is essential" | `federal rules of civil procedure; state rules of civil procedure` | li_3889760266 |
| "strong legal writing, legal research, and client management skills" | `legal writing; legal research; client management` | li_3884437728 |
| "Draft affidavits" / "Draft settlement agreements" | `affidavit drafting` / `settlement agreement drafting` | rule B |
| "Our team represents clients in matters involving professional liability, labor and employment …" | nothing (practice areas of the firm) | li_3889760266 |
| "IL bar license required" / "should be licensed in Texas" | nothing (licence) | li_3900943350, li_3884437728 |
| "our firm complies with applicable state and local laws governing nondiscrimination" | nothing (employer text) | li_3889760266 |
| "Attend court hearings" | nothing (routine duty, rule B) | rule B |

### G8. Admin / HR / Customer Service

Default: office tools and named HR systems are skills. Laws are skills when the worker must apply them
(often in HR). Equal-opportunity text is not.

| Posting wording | Label | Source |
|---|---|---|
| "Must be proficient with Microsoft Office applications" | `Microsoft Office applications` | li_3894890877 |
| "Thorough knowledge of employment-related laws and regulations" | `employment-related laws and regulations` | li_3886890185 |
| "Experience using … HR Systems (Ceridian Dayforce Preferred)" | `Ceridian Dayforce` | li_3886890185 |
| "Candidates with references are always preferred by our clients" | nothing | li_3903456306 |
| "We are an equal-opportunity employer and welcome applicants from all backgrounds" | nothing (employer text) | li_3894890877 |

### G9. Mixed postings

Use F3: read the worker's duties and pick the example set that fits each item.

| Posting wording | Label | Source |
|---|---|---|
| "Understanding and experience with VEEVA Vault" (pharma project manager) | `VEEVA Vault` | li_3906080933 |
| "Prior experience planning and managing product launches, preferably in pharmaceutical industry" | `product launches` (not "pharmaceutical industry") | li_3906080933 |
| "Ensures adherence to legal and regulatory requirements" | nothing (generic, names no law or area) | li_3906080933 |
| "Must be computer literate … and the willingness to learn" | `computer literacy` (willingness to learn = trait) | li_3902780709 |

---

## Before we adopt F and G

1. The team confirms rules A–G together. Then "PROPOSED" is removed.
2. Re-check the IT and Health Care gold postings (about 30) with F and G. Save the result as a new gold
   version. Keep the current gold labels and the frozen v3 baseline unchanged until then.
3. Test a v4 extraction prompt (with the context check) against v3 on the dev set only. Do not use the
   test set for tuning.
4. Check the G3–G9 drafts against more real dev postings. Add or fix examples where we disagree.

## For Priyanka: questions to answer

- Do you agree that one rule (F) applies to all sectors, with G as examples only?
- Is any example in G1 or G2 wrong or missing?
- Your final noise review has 94 not_a_skill rows, each with a note. Do F and F1b match those notes?
