// Sprint 3 deck (Section B skill taxonomy). Run: node build.js  -> C:/master/reports/sprint3_deck.pptx
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("C:/Users/dhanu/.claude/skills/synced/02812373-138d-4a58-874b-33e46fa50871_826bc7ac-44c0-47ee-9603-3653755db69f/pptx/scripts/apply_theme.js");

const OUT = "C:/master/reports/sprint3_deck.pptx";
const THEME = {
  name: "Skill Taxonomy",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2430", lt1: "FFFFFF", dk2: "0B3C42", lt2: "EEF3F4",
    accent1: "0F6E78", accent2: "D99A00", accent3: "5B6673", accent4: "1E7A46", accent5: "A3321F", accent6: "7FB8BE",
    hlink: "0F6E78", folHlink: "5B6673",
  },
};
const HEX = THEME.colors; // hex-only options (grid lines, chart colors)

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Sprint 3 - Section B skill taxonomy";
pres.author = "Section B team";
const C = pres.SchemeColor;
const W = 13.333, M = 0.6;

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "DARK_TITLE",
  background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.3, w: 11.5, h: 1.6, fontSize: 42, bold: true, color: C.background1, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 4.05, w: 11.5, h: 1.4, fontSize: 18, color: "CFE3E5", valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "DARK_CLOSE",
  background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.45, w: W - 2 * M, h: 1.0, fontSize: 36, bold: true, color: C.background1, valign: "middle", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: HEX.lt1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.35, w: W - 2 * M, h: 0.9, fontSize: 32, bold: true, color: C.text2, valign: "middle" }, text: "" } },
    { text: { text: "Section B · Skill taxonomy · Sprint 3", options: { x: M, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: C.accent3 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: HEX.accent3, align: "right" },
});

// ---------- helpers ----------
const T = (s, text, o) => s.addText(text, { isTextBox: true, fontSize: 15, color: C.text1, valign: "top", margin: 0.05, ...o });
function card(s, x, y, w, h, head, body, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: o.fill || C.background2 }, line: { type: "none" },
    objectName: `card ${head}` });
  T(s, head, { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: 0.45, fontSize: 17, bold: true, color: o.headColor || C.accent1 });
  T(s, body, { x: x + 0.2, y: y + 0.62, w: w - 0.4, h: h - 0.75, fontSize: o.size || 14 });
}
function stat(s, x, y, w, num, label, o = {}) {
  T(s, num, { x, y, w, h: 0.95, fontSize: o.size || 48, bold: true, color: o.color || C.accent1, fontFace: THEME.headFontFace, valign: "bottom" });
  T(s, label, { x, y: y + 0.98, w, h: 0.6, fontSize: 13, color: C.accent3 });
}
const bullets = (items, o = {}) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6, ...o } }));
const tag = (s, x, y, text, color) => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.35, h: 0.32, rectRadius: 0.16, fill: { color }, line: { type: "none" } });
  T(s, text, { x, y, w: 1.35, h: 0.32, fontSize: 11, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0 });
};
function table(s, rows, o) {
  const head = rows[0].map((h) => ({ text: h, options: { bold: true, color: C.background1, fill: { color: C.accent1 }, fontSize: o.size || 13 } }));
  const body = rows.slice(1).map((r, i) => r.map((c) => (typeof c === "object" ? c : { text: String(c), options: {
    fontSize: o.size || 13, color: C.text1, fill: { color: o.hl === i ? "DCEDEF" : (i % 2 ? HEX.lt2 : HEX.lt1) }, bold: o.hl === i } })));
  s.addTable([head, ...body], { x: o.x, y: o.y, w: o.w, colW: o.colW, rowH: o.rowH, border: { type: "solid", pt: 0.5, color: "D5DDE0" }, margin: 0.06, valign: "middle" });
}
const chartText = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt",
  legendFontFace: "+mn-lt", catAxisLabelColor: HEX.accent3, valAxisLabelColor: HEX.accent3, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
  dataLabelFontSize: 11, dataLabelColor: HEX.dk1, titleColor: HEX.dk1, titleFontSize: 14, valGridLine: { color: "E1E7EA", size: 0.5 },
  catGridLine: { style: "none" } };

// ================= 1. Title =================
pres.addSection({ title: "Opening" });
let s = pres.addSlide({ masterName: "DARK_TITLE", sectionTitle: "Opening" });
s.addText("From skill statements to leaf topics", { placeholder: "title" });
s.addText("Sprint 3 — Representation & Clustering · Section B (skills) · Taxonomy of Work capstone, Northeastern", { placeholder: "body" });
T(s, "SPRINT 3 REPORT", { x: M, y: 1.6, w: 6, h: 0.4, fontSize: 14, bold: true, color: C.accent2, charSpacing: 4 });
s.addNotes("Section A builds the task taxonomy; we build the skill side. This deck covers how we moved on from Sprint 2, what Sprint 3 is, the clustering methods we tried, our skill library, the parameter sweep, and the final result.");

// ================= 2. At a glance =================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Opening" });
s.addText("Sprint 3 at a glance", { placeholder: "title" });
T(s, "Goal (brief): turn skill statements into leaf topics, with topic and membership tables and a stability report.", { x: M, y: 1.35, w: 12, h: 0.5, fontSize: 17, color: C.text2 });
[["11,093", "clean skills\n(from 11,449 names)"], ["374", "leaf topics\nHDBSCAN"], ["0.84", "stability AMI\non 80% subsets"], ["196", "library skills\n249 strong links"]]
  .forEach(([n, l], i) => { const x = M + i * 3.05; s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.3, w: 2.8, h: 2.4, rectRadius: 0.1, fill: { color: C.background2 }, line: { type: "none" } }); stat(s, x + 0.25, 2.5, 2.4, n, l); });
T(s, bullets(["Chosen: HDBSCAN, min cluster size 10, min samples 1, on UMAP-10 of bge-small embeddings",
  "Every skill keeps a topic: 78% clustered, the rest are weak members of the nearest topic",
  "All tables, including the embeddings (pgvector), are in Supabase"]), { x: M, y: 5.0, w: 12, h: 1.7, fontSize: 16 });
s.addNotes("Four numbers to remember. 11,093 clean skills after merging duplicate names, 374 topics, stability 0.84, and a library of 196 cross-sector skills with 249 strong links to domain topics.");

// ================= 3. From Sprint 2 =================
pres.addSection({ title: "1. From Sprint 2" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "1. From Sprint 2" });
s.addText("Where Sprint 2 left us", { placeholder: "title" });
const s2 = [["Corpus", "Kaggle LinkedIn dataset: 123,849 US postings (Mar–Apr 2024). Duplicates tagged, not dropped. Plus a live Greenhouse feed (453)."],
  ["Gold set", "100 hand-labelled postings, 8 sectors, 1,333 gold skills. Rule E: ESCO + O*NET decide skill vs trait."],
  ["Extractor", "Qwen3.8 27B on Groq (free), prompt v3. Test F1 strict .66 / lenient .74 — ties Claude Haiku (.66 / .75)."],
  ["Pipeline", "Clean → dedupe → LLM extract (cached, Langfuse) → ESCO / O*NET link → Supabase. 69% known · 2% trait · 29% new."]];
s2.forEach(([h, b], i) => card(s, M + (i % 2) * 4.1, 1.45 + Math.floor(i / 2) * 2.55, 3.9, 2.35, h, b));
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.95, y: 1.45, w: 3.8, h: 4.9, rectRadius: 0.1, fill: { color: C.text2 }, line: { type: "none" } });
T(s, "What was still missing", { x: 9.15, y: 1.65, w: 3.4, h: 0.5, fontSize: 18, bold: true, color: C.accent2 });
T(s, bullets(["A list of skill statements, but no structure",
  "\"excel\", \"microsoft excel\" and \"advanced excel\" were three unrelated strings",
  "Nothing said which skills belong together, or which domains need a generic skill"]), { x: 9.15, y: 2.25, w: 3.4, h: 3.9, fontSize: 15, color: C.background1 });
s.addNotes("Sprint 2 gave us clean postings, a gold set, a chosen free extractor and a live pipeline. What it did not give us is structure — that is Sprint 3.");

// ================= 4. What Sprint 3 is =================
pres.addSection({ title: "2. Sprint 3 and how we did it" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "2. Sprint 3 and how we did it" });
s.addText("What Sprint 3 asks, and our answer", { placeholder: "title" });
table(s, [["Brief task", "Our answer"],
  ["Choose a representation and store it in the shared database", "bge-small-en-v1.5 (384 dims) · Supabase pgvector table, 11,093 rows"],
  ["Fit and compare at least two clustering methods", "Four: HDBSCAN, Leiden, agglomerative, k-means"],
  ["Run a parameter sweep and report stability", "20 settings + 6 stability runs on the final data"],
  ["Can a statement belong to more than one topic?", "One main topic + weak members + skill-library links"],
  ["Deliverable: topic and membership tables", "topics (374), skill_topics (11,093) in Supabase"]], { x: M, y: 1.6, w: 12.1, colW: [5.3, 6.8], size: 17, rowH: 0.8 });
s.addNotes("This maps the brief line by line to what we built. Every task has a concrete artefact in the repo or the database.");

// ================= 5. How we did it =================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "2. Sprint 3 and how we did it" });
s.addText("How we did it: eight steps", { placeholder: "title" });
const steps = [["Snapshot", "28,777 mentions · 1,931 postings"], ["Clean names", "11,449 → 11,093 skills"], ["Embed", "bge-small, 384 dims"], ["Cluster", "4 methods"],
  ["Sweep", "20 settings"], ["Stability", "80% subsets + seeds"], ["Membership", "main + weak + related"], ["Library", "196 skills, links"]];
steps.forEach(([h, b], i) => {
  const x = M + (i % 4) * 3.05, y = 1.6 + Math.floor(i / 4) * 2.45;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.8, h: 2.05, rectRadius: 0.1, fill: { color: i === 3 ? "DCEDEF" : C.background2 }, line: { type: "none" } });
  s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.2, w: 0.55, h: 0.55, fill: { color: C.accent1 }, line: { type: "none" } });
  T(s, String(i + 1), { x: x + 0.2, y: y + 0.2, w: 0.55, h: 0.55, fontSize: 16, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0 });
  T(s, h, { x: x + 0.2, y: y + 0.9, w: 2.4, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
  T(s, b, { x: x + 0.2, y: y + 1.35, w: 2.4, h: 0.6, fontSize: 14, color: C.accent3 });
});
T(s, "Snapshot = one model per posting (Qwen where its batch is done, the Haiku research run elsewhere; both score the same on test).", { x: M, y: 6.55, w: 12, h: 0.4, fontSize: 12, color: C.accent3 });
s.addNotes("Each step has its own script: prepare_skills, normalize_aliases, embed_skills, cluster_skills, cluster_stability, load_taxonomy, build_library. The Qwen batch is slowed by Groq's free tier, so the snapshot mixes Qwen and the Haiku research run; both tie on the test set.");

// ================= 6. Clean names =================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "2. Sprint 3 and how we did it" });
s.addText("Cleaning skill names before clustering", { placeholder: "title" });
T(s, "Each name is one point in the embedding space, so duplicates split counts. We cross-checked every pair with independent signals:", { x: M, y: 1.35, w: 12, h: 0.6, fontSize: 16 });
[["Spelling", "plural, spaces, \"(ap)\"\npower point = powerpoint"], ["Vendor / level word", "adobe photoshop = photoshop\nadvanced excel = excel"], ["Meaning + reference", "near-identical embedding or same ESCO / O*NET entry"]]
  .forEach(([h, b], i) => card(s, M + i * 2.75, 2.15, 2.55, 2.1, h, b, { size: 13 }));
stat(s, 9.2, 2.15, 3.5, "269", "pairs merged after reading the posting evidence (of 289 checked)", { size: 54 });
T(s, "Kept apart (different things)", { x: M, y: 4.55, w: 8, h: 0.4, fontSize: 17, bold: true, color: C.accent5 });
T(s, bullets(["canvas (Canvas LMS) ≠ canva (design tool)", "\"SAPs\" (lab analysis plans) ≠ SAP software",
  "routings (manufacturing) ≠ routing (networks) · CMM ≠ CMMS"]), { x: M, y: 5.0, w: 8, h: 1.6, fontSize: 15 });
stat(s, 9.2, 4.6, 3.5, "11,093", "clean skills (from 11,449)", { size: 44 });
s.addNotes("Pairs found only by meaning are usually broad versus narrow, like trend analysis vs market trend analysis — we did not merge those; they are parent/child candidates for Sprint 4.");

// ================= 7. Representation =================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "2. Sprint 3 and how we did it" });
s.addText("Representation: one vector per skill", { placeholder: "title" });
card(s, M, 1.5, 5.9, 2.4, "Model", "BAAI/bge-small-en-v1.5, pinned revision\n384 numbers per skill, normalised (cosine = dot)\nUMAP → 10 dims for HDBSCAN; 3D only for the map");
card(s, M, 4.1, 5.9, 2.4, "Stored in the shared database", "Supabase table skill_embeddings (pgvector)\n11,093 rows, HNSW cosine index\nPostgres similarity = Python similarity (checked)");
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.9, y: 1.5, w: 5.85, h: 5.0, rectRadius: 0.1, fill: { color: "FBF1DA" }, line: { type: "none" } });
T(s, "Weakness we found: names fool the model", { x: 7.1, y: 1.7, w: 5.4, h: 0.5, fontSize: 18, bold: true, color: "8A5A00" });
table(s, [["Skill", "Lands next to"], ["numpy", "basic math, matlab"], ["tensorflow", "airflow, kubeflow (\"-flow\")"], ["r", "rhel, redcap"], ["microsoft excel", "microsoft office, word (not spreadsheets)"]],
  { x: 7.1, y: 2.35, w: 5.45, colW: [1.9, 3.55] });
T(s, "Fix planned for Sprint 4: embed the name plus a short description, e.g. the O*NET software category.", { x: 7.1, y: 5.3, w: 5.4, h: 0.9, fontSize: 14, color: C.text1 });
s.addNotes("The model only sees the skill name, so it groups by how names look. That is why microsoft excel became HDBSCAN noise after the merge. It still has a weak topic and is a library skill.");

// ================= 8. Methods =================
pres.addSection({ title: "3. Clustering methods" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "3. Clustering methods" });
s.addText("Clustering methods we tried", { placeholder: "title" });
const meth = [["HDBSCAN", "dense areas in UMAP space; sparse skills = noise", "374 topics · 78% · AMI 0.84", "chosen", HEX.accent4],
  ["Leiden (RB)", "communities in a 15-nearest-skill graph", "323 topics · 100% · AMI 0.75", "runner-up", HEX.accent2],
  ["Leiden (CPM)", "same graph, other quality function", "8 settings · Jaccard ≤ 0.53", "rejected", HEX.accent5],
  ["Agglomerative", "merge closest pairs, cut at a distance", "357 topics · AMI 0.61", "hierarchy only", HEX.accent3],
  ["k-means", "k round groups, fixed in advance", "cannot leave a skill out", "not kept", HEX.accent5]];
meth.forEach(([n, how, res, v, col], i) => {
  const y = 1.45 + i * 1.07;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y, w: 12.1, h: 0.92, rectRadius: 0.08, fill: { color: i === 0 ? "DCEDEF" : C.background2 }, line: { type: "none" } });
  T(s, n, { x: M + 0.2, y, w: 2.3, h: 0.92, fontSize: 17, bold: true, color: C.text2, valign: "middle" });
  T(s, how, { x: M + 2.6, y, w: 4.7, h: 0.92, fontSize: 14, valign: "middle" });
  T(s, res, { x: M + 7.4, y, w: 3.0, h: 0.92, fontSize: 14, bold: true, color: C.accent1, valign: "middle" });
  tag(s, M + 10.55, y + 0.3, v, col);
});
s.addNotes("HDBSCAN gives the steadiest topics on the skills it clusters and honestly says 22% do not fit; we keep those as weak members. Leiden covers everything but its labels move more between subsets. On the 78% HDBSCAN clusters, the two agree with AMI 0.78.");

// ================= 9. AI advice =================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "3. Clustering methods" });
s.addText("We tested the AI advice instead of trusting it", { placeholder: "title" });
const adv = [["Leiden with CPM is steadier", "Rejected", "CPM Jaccard 0.53 vs RB 0.59", HEX.accent5],
  ["Merge verified aliases first", "Done", "269 evidence-checked merges", HEX.accent4],
  ["Never force a skill into a topic", "Done", "assigned / weak + score + margin", HEX.accent4],
  ["Build the hierarchy over centroids", "Agreed", "agglomerative least stable on raw skills", HEX.accent4],
  ["Give soft skills their own family", "Done differently", "the skill library + 39 transversal topics", HEX.accent2]];
adv.forEach(([a, v, e, col], i) => {
  const y = 1.5 + i * 1.02;
  T(s, a, { x: M, y, w: 5.2, h: 0.8, fontSize: 17, color: C.text1, valign: "middle" });
  tag(s, M + 5.4, y + 0.24, v, col);
  T(s, e, { x: M + 7.0, y, w: 5.1, h: 0.8, fontSize: 15, color: C.accent3, valign: "middle" });
});
s.addNotes("A long GPT review of our plan was pasted in. We tested each claim on our own data. The headline: its main recommendation, CPM, was wrong for our data.");

// ================= 10. Library why + who =================
pres.addSection({ title: "4. Skill library" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "4. Skill library" });
s.addText("Why we built a skill library", { placeholder: "title" });
T(s, "Clustering groups skills by meaning, from the name only. It never looks at which jobs use a skill.", { x: M, y: 1.3, w: 12, h: 0.5, fontSize: 17, color: C.text2 });
[["Generic skills get stranded", "HDBSCAN puts many in noise (attention to detail has no topic) or in 39 soft-skill topics, cut off from the domains that use them."],
 ["Our end goal needs them", "\"Build a finance team\" needs accounting topics plus excel and attention to detail. Only the postings show that link."],
 ["The brief asks for it", "\"Decide whether a statement may belong to more than one topic.\" Library links are our multi-topic answer."],
 ["It prepares Sprint 5", "Task ↔ skill mapping with Section A uses the same co-occurrence maths: lift, p, q per job template."]]
  .forEach(([h, b], i) => {
    const x = M + (i % 2) * 6.15, y = 2.05 + Math.floor(i / 2) * 2.4;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 5.95, h: 2.2, rectRadius: 0.1, fill: { color: C.background2 }, line: { type: "none" }, objectName: `reason ${i + 1}` });
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.25, w: 0.6, h: 0.6, fill: { color: C.accent2 }, line: { type: "none" } });
    T(s, String(i + 1), { x: x + 0.25, y: y + 0.25, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0 });
    T(s, h, { x: x + 1.05, y: y + 0.25, w: 4.7, h: 0.6, fontSize: 19, bold: true, color: C.text2, valign: "middle" });
    T(s, b, { x: x + 1.05, y: y + 0.95, w: 4.7, h: 1.15, fontSize: 15 });
  });
s.addNotes("Why the library exists. One: generic skills like attention to detail end up as noise or in soft-skill topics, disconnected from domains. Two: our end goal is initiative to tasks to skills, so for a finance team we must also return excel and attention to detail, and only co-occurrence in postings shows that. Three: the brief asks whether a statement can belong to more than one topic; the links are our answer. Four: Sprint 5 will map Section A's tasks to our skills with the same maths.");

s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "4. Skill library" });
s.addText("The skill library: skills every sector needs", { placeholder: "title" });
T(s, [{ text: "Clustering says what a skill means. ", options: { bold: true } }, { text: "It cannot say which domains need a generic skill. Communication is in 603 postings across all 8 sectors; attention to detail has no topic at all." }],
  { x: M, y: 1.35, w: 6.2, h: 1.3, fontSize: 16 });
card(s, M, 2.85, 6.2, 2.1, "Who is in the library (rule v2)", "≥ 5 postings · ≥ 4 of 8 sectors · no sector > 50%\nConfirmed at ≥ 10 postings · fixed before looking at results");
stat(s, M, 5.15, 3, "196", "library skills (146 confirmed)", { size: 44 });
stat(s, M + 3.2, 5.15, 3, "43", "of them are HDBSCAN noise", { size: 44 });
s.addChart(pres.charts.BAR, [{ name: "Library skills", labels: ["skill", "knowledge", "unknown", "tool", "trait"], values: [80, 55, 28, 27, 6] }], {
  x: 7.1, y: 1.4, w: 5.6, h: 5.3, barDir: "bar", chartColors: [HEX.accent1], showValue: true, dataLabelPosition: "outEnd", showLegend: false,
  showTitle: true, title: "Library skills by type (from ESCO / O*NET)", catAxisOrientation: "maxMin", valAxisHidden: true, ...chartText });
s.addNotes("The library is a label on a skill, not a second copy. Types come from each skill's ESCO or O*NET link: tools like excel, traits like attention to detail and leadership.");

// ================= 11. Library links =================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "4. Skill library" });
s.addText("Linking library skills to domain topics", { placeholder: "title" });
T(s, "Example: excel and the accounts-payable topic, 1,931 postings", { x: M, y: 1.35, w: 7, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
[["191", "postings with excel"], ["41", "postings with the topic"], ["≈ 4", "shared by chance"], ["18", "shared in reality"]]
  .forEach(([n, l], i) => stat(s, M + i * 1.75, 1.85, 1.65, n, l, { size: 40, color: i === 3 ? C.accent2 : C.accent1 }));
T(s, bullets(["Lift = observed ÷ expected: 18 ÷ 4.1 ≈ 4.4", "p = hypergeometric test (could it be luck?)", "q = Benjamini–Hochberg over all 65,584 pairs",
  "Strong = ≥ 5 job templates, lift ≥ 1.5, q < 0.05"]), { x: M, y: 3.75, w: 6.6, h: 2.6, fontSize: 16 });
card(s, 7.6, 1.45, 5.15, 2.3, "Result", "980 links kept, 249 strong\ne.g. microsoft excel → payment reconciliation, lift 3.2", { size: 15 });
card(s, 7.6, 3.95, 5.15, 2.6, "v1 → v2 improvements", "Names merged first (excel = microsoft excel)\nCount per job template (company + title): 255 → 249 strong\nWhole-company counting tried and rejected (staffing firms)", { size: 14 });
s.addNotes("Raw counts would link communication to every big topic just because both are common. Lift asks: more often than chance? Counting per job template stops one job copied to 20 cities from counting 20 times; empathy and writing lost strong links that way.");

// ================= 12. Sweep =================
pres.addSection({ title: "5. Parameter sweep" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "5. Parameter sweep" });
s.addText("Parameter sweep: 20 settings on the final data", { placeholder: "title" });
s.addChart(pres.charts.LINE, [
  { name: "min_samples default", labels: ["5", "10", "15", "20"], values: [27.0, 37.4, 42.7, 47.5] },
  { name: "min_samples 1", labels: ["5", "10", "15", "20"], values: [19.3, 22.1, 24.3, 27.0] },
  { name: "min_samples 3", labels: ["5", "10", "15", "20"], values: [21.2, 24.0, 26.5, 28.2] }], {
  x: M, y: 1.4, w: 6.4, h: 5.3, chartColors: [HEX.accent3, HEX.accent1, HEX.accent2], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 8,
  showTitle: true, title: "HDBSCAN noise share (%) by min cluster size", showLegend: true, legendPos: "b", legendFontSize: 12, legendColor: HEX.dk1,
  valAxisMinVal: 0, valAxisMaxVal: 50, showValue: false, catAxisTitle: "min cluster size", showCatAxisTitle: true, catAxisTitleFontSize: 12, catAxisTitleColor: HEX.accent3, ...chartText });
s.addChart(pres.charts.BAR, [{ name: "Topics", labels: ["HDB 5, ms1", "HDB 10, ms1 (chosen)", "HDB 10, ms3", "HDB 10, default", "HDB 20, default", "Leiden res 20", "Agglo 0.4"],
  values: [752, 374, 363, 275, 113, 323, 357] }], {
  x: 7.2, y: 1.4, w: 5.55, h: 5.3, barDir: "bar", chartColors: [HEX.accent6, HEX.accent1, HEX.accent6, HEX.accent6, HEX.accent6, HEX.accent6, HEX.accent6],
  showValue: true, dataLabelPosition: "outEnd", showLegend: false, showTitle: true, title: "Topics per setting", catAxisOrientation: "maxMin", valAxisHidden: true, ...chartText });
s.addNotes("Grid: HDBSCAN min cluster size 5/10/15/20 times min_samples default/1/3, Leiden resolution 5-30, agglomerative cut 0.30-0.45. Bigger sizes push more skills into noise; size 5 gives hundreds of tiny topics; min_samples 1 keeps noise near 20%.");

// ================= 13. Stability =================
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "5. Parameter sweep" });
s.addText("Stability: same answer on 80% subsets?", { placeholder: "title" });
const stab = [["HDB 10, default", 0.908, "63%"], ["HDB 10, ms3", 0.853, "76%"], ["HDB 10, ms1 (chosen)", 0.842, "78%"], ["HDB 15, ms1", 0.838, "76%"], ["Leiden res 20", 0.746, "100%"], ["Agglo 0.4", 0.606, "100%"]];
s.addChart(pres.charts.BAR, [{ name: "AMI", labels: stab.map((r) => r[0]), values: stab.map((r) => r[1]) }], {
  x: M, y: 1.4, w: 6.6, h: 5.3, barDir: "bar", chartColors: stab.map((r) => (r[0].includes("chosen") ? HEX.accent1 : HEX.accent6)), showValue: true, dataLabelPosition: "outEnd",
  dataLabelFormatCode: "0.00", showLegend: false, showTitle: true, title: "AMI across 5 random 80% subsets (1 = identical)", catAxisOrientation: "maxMin", valAxisMinVal: 0, valAxisMaxVal: 1, valAxisHidden: true, ...chartText });
table(s, [["Setting", "Coverage"], ...stab.map((r) => [r[0], r[2]])], { x: 7.5, y: 1.5, w: 5.25, colW: [3.5, 1.75], hl: 2 });
T(s, bullets(["\"Default\" looks most stable only because it drops 37% of skills", "ms3 is a near-tie; we keep ms1 for coverage", "About half of the topics dissolve in some subset, for every method"]),
  { x: 7.5, y: 4.55, w: 5.25, h: 2.1, fontSize: 14 });
s.addNotes("We re-ran each strong setting on 5 random 80% subsets and with 3 other seeds. AMI compares labels between runs. Coverage is the share of skills that get a topic. The chosen setting balances the two.");

// ================= 14. Final result =================
pres.addSection({ title: "6. Final result" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "6. Final result" });
s.addText("Final result of Sprint 3", { placeholder: "title" });
[["374", "leaf topics"], ["8,646", "skills in a topic"], ["2,447", "weak members"], ["980", "library links (249 strong)"]]
  .forEach(([n, l], i) => stat(s, M + i * 3.05, 1.4, 2.8, n, l, { size: 44 }));
T(s, "HDBSCAN · min cluster size 10 · min samples 1 · UMAP 10 dims (15 neighbours, cosine, seed 42) · bge-small-en-v1.5 · 11,093 skills",
  { x: M, y: 3.15, w: 12.1, h: 0.5, fontSize: 15, bold: true, color: C.accent1 });
table(s, [["Brief deliverable", "Status"], ["Representation stored in the shared database", "Done — skill_embeddings (pgvector)"],
  ["At least two clustering methods compared", "Done — four methods"], ["Parameter sweep + stability report", "Done — 20 settings, 6 stability runs"],
  ["Multi-topic membership decided and implemented", "Done — main topic + weak + library links"], ["Topic and membership tables", "Done — topics, skill_topics in Supabase"]],
  { x: M, y: 3.85, w: 12.1, colW: [6.3, 5.8] });
s.addNotes("Every brief deliverable for Sprint 3 is done and in the shared database. The report has the full tables.");

// ================= 15. Limits + next =================
s = pres.addSlide({ masterName: "DARK_CLOSE", sectionTitle: "6. Final result" });
s.addText("Limits and what comes next", { placeholder: "title" });
T(s, "Limits", { x: M, y: 1.9, w: 5.8, h: 0.5, fontSize: 20, bold: true, color: C.accent2 });
T(s, bullets(["About half the topics are fragile, for every method", "The embedding sees only the name", "Topic labels are still the centroid skill",
  "Small sample (1,931 postings); thresholds set by us"]), { x: M, y: 2.45, w: 5.8, h: 3.8, fontSize: 16, color: C.background1 });
T(s, "Next", { x: 7.0, y: 1.9, w: 5.7, h: 0.5, fontSize: 20, bold: true, color: C.accent2 });
T(s, bullets(["Sprint 4: name every topic, build parent levels, evaluate against ESCO", "Keep the library as a cross-sector branch (as ESCO does)",
  "Sprint 5: task ↔ skill mapping with Section A (shared posting ids)", "Questions?"]), { x: 7.0, y: 2.45, w: 5.7, h: 3.8, fontSize: 16, color: C.background1 });
s.addNotes("Say the limits before someone asks; each has a planned fix in Sprint 4 or 5.");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote " + OUT);
})();
