# Section B — Skill Taxonomy · Prototype demo (Fri 2026-10-23, 15:00)

Slide content for the PowerPoint. One block per slide: **title**, on-slide text (short), *visual*, and
speaker notes (what to say). About 12 slides ≈ 12–15 minutes incl. the live part.
All numbers are from the repo (reports/, HANDOFF.md, canonical_v2/) as of 2026-10-22.

---

## 1. Title
**From job postings to a skill taxonomy — Section B prototype**
- Taxonomy of Work capstone · Section B (skills)
- Team: Dhanush, Lochan, Priyanka · Northeastern
- *Visual:* the pipeline-at-a-glance strip from the dashboard (6 boxes)

Notes: Section A builds the task taxonomy, we build the skill side. Today: how we get skills out of postings,
how we group them, and what is still open.

---

## 2. The problem and our goal
- Job postings describe skills in free text, with many names for one skill
- Goal (brief): given a business initiative → ranked **tasks** and **skills** with supporting postings
- Section B delivers the **skill** half: extract → clean → embed → cluster → link
- Reference standards: **ESCO v1.2** and **O\*NET 31.0** (Lightcast access not granted)

Notes: End goal is not a resume matcher. Sprint 5 joins our skills to Section A's tasks.

---

## 3. Data
- Kaggle `arshkon/linkedin-job-postings`: **123,849** US postings (Mar–Apr 2024), a published dataset (no scraping)
- Cleaning **tags, never drops**: 16,320 duplicate texts, 636 short, 7 missing → 106,909 usable
- Extraction sample: **2,000** postings (emails / phones masked) + **453** live Greenhouse postings
- Gold set: **100** postings across 8 sectors, hand-labelled (LLM suggests, human decides): **1,333** gold skills
- *Visual:* sector bar of the gold set (IT 15, Health 15, Engineering 12 …)

Notes: The LinkedIn dataset is allowed (brief names Kaggle dumps). Gold split 50 dev / 50 test; test scored once.

---

## 4. Labelling rules (what counts as a skill)
- One skill per item, posting wording, filler removed ("strong", "skills", "knowledge of")
- Not skills: degrees, years, licences, certificates, tasks from the duties section
- **Rule E:** ESCO + O\*NET are the rule book for skill vs **trait**
  (traits = O\*NET Work Styles + ESCO attitudes, e.g. *attention to detail*, *leadership*)
- *Visual:* one posting with skills highlighted (from data/gold/gold_example.xlsx)

Notes: Rules came from disagreements while labelling; without them F1 is meaningless.

---

## 5. Choosing the extractor (Sprint 2 result)
| Model (prompt v3) | Dev F1 strict / lenient |
|---|---|
| Claude Haiku 5.5 (benchmark only) | .67 / .76 |
| **Qwen3.8 27B on Groq (free) — chosen** | **.66 / .74** |
| gemini-3.5-flash-lite | .64 / .71 |
| gpt-oss-120b | .61 / .71 |
| Nemotron 3 Ultra (49 postings) | .52 / .61 |
- Test set (scored once): **Qwen strict .66 / lenient .74**, Haiku .66 / .75 → a tie, so the **free** model wins
- Human-vs-human agreement (3 postings): strict .63 / lenient .73 → we are near the human ceiling
- *Visual:* the F1 bar chart from the UI "Models & code" tab

Notes: Prompt v4 (rules + paper ideas) gave no gain, v3 stays frozen. Bias check: Haiku's dev edge came from the
gold drafts being Claude-suggested.

---

## 6. The live pipeline
- Postings → clean / dedupe → **LLM extract** (LiteLLM router: Groq Qwen, fallback Gemini) → **ESCO / O\*NET link**
  → unknown skills to **human review** → **Supabase**
- Every LLM call is cached (re-runs are free) and traced in **Langfuse**
- Scheduled: Qwen batch (resumable), hourly load, nightly Greenhouse
- Verdicts: **69%** known skill · **2%** trait · **29%** new candidate (→ review queue, 5,924 skills)
- *Visual:* screenshot of the Pipeline status tab (diagram + "Now" + charts)

Notes: Honest status: Groq free tier rate-limits us (~10 min waits), Qwen batch is at ~240 / 2,000. The clustering
snapshot uses one model per posting: Qwen where done, the Haiku research run elsewhere.

---

## 7. Cleaning the skill names (before clustering)
- 11,449 skill names from 28,777 mentions → many duplicates ("excel" = "microsoft excel", "power point")
- Cross-check with **3 independent signals**: spelling rules · embedding similarity · same ESCO / O\*NET entry
- 289 candidate pairs checked against the posting evidence: **269 merged, 16 kept apart**
  (canvas ≠ canva, SAPs ≠ SAP, routings ≠ routing, CMM ≠ CMMS)
- Result: **11,093** clean skills
- *Visual:* the three-signal diagram + 3 example pairs (one merged, two rejected)

Notes: Pairs found only by meaning are often broad vs narrow ("trend analysis" vs "market trend analysis") —
those are not merged; they are parent/child candidates for Sprint 4.

---

## 8. Representation
- Model **BAAI/bge-small-en-v1.5** (pinned revision), 384 numbers per skill, normalised (cosine = dot)
- Stored in the **shared database**: Supabase pgvector table `skill_embeddings` (11,093 rows, HNSW index)
- UMAP → 10 dimensions for HDBSCAN; → 3D only for the Skill map
- *Visual:* "similar skills sit close" toy picture (learn/cluster-topics.html, tab 2)

Notes: Limitation we found: the model sees only the name. numpy lands next to "basic math", tensorflow next to
airflow ("-flow"). Fix planned: embed name + short description.

---

## 9. Clustering: sweep and stability
- Compared 4 methods: **HDBSCAN, Leiden, agglomerative, k-means**; sweep of 20 settings on the final data
- Stability: cluster 5 random 80% subsets + 3 seeds, compare (AMI, per-topic Jaccard)

| Setting | Topics | Noise | AMI | Coverage |
|---|---|---|---|---|
| HDBSCAN 10, default | 275 | 37% | .91 | 63% |
| **HDBSCAN 10, min_samples 1 (chosen)** | **374** | **22%** | **.84** | **78%** |
| HDBSCAN 10, min_samples 3 | 363 | 24% | .85 | 76% |
| Leiden RB res 20 | 323 | 0% | .75 | 100% |
| Agglomerative 0.4 | 357 | 0% | .61 | 100% |
- *Visual:* this table + the AMI bar chart (learn/cluster-topics.html, tab 3)

Notes: "Default" only looks stable because it drops a third of the skills. min_samples 3 is a near-tie; we keep 1
for coverage. Agglomerative is least stable on raw skills → only for the hierarchy over topic centres (Sprint 4).

---

## 10. We tested the AI advice instead of trusting it
| GPT review suggested | Our test said |
|---|---|
| Leiden with CPM is steadier | **Rejected**: CPM Jaccard .53 vs RB .59 |
| Never force a skill into a topic | **Done**: assigned / weak + score + margin |
| Merge aliases first | **Done**: 269 merges, evidence-checked |
| Hierarchy over centroids | **Agreed** (Sprint 4) |
- *Visual:* the table (learn/cluster-topics.html, tab 4)

Notes: This is the "verify, don't trust" message: every claim got a number from our own data.

---

## 11. One topic or many? Our answer: topics + a skill library
- Brief: "decide whether a statement may belong to more than one topic"
- Each skill: **one main topic**; HDBSCAN noise → **weak member** of the nearest topic (2,447 skills, margin kept)
- Generic skills (communication, excel, attention to detail) appear in every sector → **skill library**
  (≥ 5 postings, ≥ 4 of 8 sectors, no sector > 50%): **196 skills**, typed tool / knowledge / skill / trait
- **Links** library skill → domain topic by co-occurrence: lift + hypergeometric p + BH q, counted per **job template**
  → **980 links, 249 strong** (e.g. excel → payment reconciliation, lift 3.2)
- *Visual:* Venn of excel ∩ accounting topic (learn/library-links.html, tab 3)

Notes: Clustering says what a skill MEANS; links say which domains NEED it. Counting per template (company + title)
removed copied-job inflation (empathy, writing lost their strong links).

---

## 12. Live demo (5 min)
1. Pipeline status: diagram, "Now" box, charts, Langfuse traces
2. Review queue: decide one unknown skill (e.g. "leadership" → trait)
3. Skill map: search a skill, click **microsoft excel** → its strong / weak links
4. Models & code: F1 chart + code map
- Backup if the network fails: screenshots in this deck

---

## 13. Honest limits and next steps
- Limits: half of the topics are fragile (Jaccard ≈ .5) for every method · names fool the embedding ·
  topic names are still the centroid skill · small sample (1,931 postings in the snapshot) · Qwen batch slowed by free tier
- **Sprint 4:** name every topic, build the hierarchy (topics → families), evaluate against ESCO
- **Sprint 5 (with Section A):** task ↔ skill mapping; needs the shared posting IDs (data contract)
- Thank you — questions?

Notes: Say the limits before someone asks; each has a planned fix.
