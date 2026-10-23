// Section B pipeline UI. Plain JS, no build step. All data comes from app/server.py (/api/*).
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtTime = (t) => (t ? new Date(t).toLocaleTimeString() : "");
const ago = (t) => { const m = Math.round((Date.now() - t) / 60000); return m < 1 ? "just now" : m < 90 ? `${m} min ago` : `${Math.round(m / 60)} h ago`; };
const pct = (x) => `${Math.round(x * 100)}%`;
const VERDICTS = ["known_skill", "trait", "new_candidate", "not_a_skill"];
const store = {
  get: (k) => { try { return localStorage.getItem(k) || ""; } catch { return ""; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode: ignore */ } },
};

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

// ---------- tabs ----------
let view = "status";
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
  view = b.dataset.view;
  document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
  document.querySelectorAll(".view").forEach((s) => (s.hidden = s.id !== `view-${view}`));
  if (view === "status") loadStatus();
  if (view === "review") loadQueue();
  if (view === "skills") loadSkills();
  if (view === "map") loadMap();
  if (view === "models") loadModels();
}));

// ---------- 1. pipeline status ----------
function card(k, v, extra = "") { return `<div class="card"><div class="k">${esc(k)}</div><div class="v">${v}</div>${extra}</div>`; }

async function loadStatus() {
  let s;
  try { s = await api("/api/status"); } catch (e) {
    $("#updated").textContent = `error: ${e.message}`;
    $("#offline").hidden = false;
    $("#offline").textContent = /fetch/i.test(e.message)
      ? "Cannot reach the UI server. The numbers below are old. Start app/server.py again."
      : `The server answered with an error: ${e.message}`;
    return;
  }
  $("#offline").hidden = true;
  $("#updated").textContent = `updated ${new Date().toLocaleTimeString()}`;
  const lf = s.langfuse;
  $("#langfuse").href = lf.url;
  $("#lf-dot").className = `dot ${lf.state === "connected" ? "on" : "off"}`;
  $("#lf-dot").title = lf.state === "connected" ? `Langfuse connected: ${lf.traces} LLM calls traced`
    : lf.state === "error" ? `Langfuse keys set, but the check failed: ${lf.error}` : "No Langfuse keys in .env";

  const c = s.counts, b = s.batch, t = s.tasks || {};
  // "Now": plain answer to "what is the pipeline doing?" (two scheduled jobs: extract, then hourly load)
  const ex = t.extract, ld = t.load, last = b && b.last_ts ? b.last_ts * 1000 : null;
  const exRunning = ex && ex.state === "Running", fresh = last && Date.now() - last < 15 * 60000;
  const exCls = exRunning ? (fresh ? "running" : "stalled") : "";
  const exTitle = !b ? "Extraction: no batch file found"
    : b.done >= b.total ? `Extraction finished: ${b.total}/${b.total} postings`
    : exRunning ? (fresh ? `● Extracting skills now: ${b.done}/${b.total} postings (${pct(b.done / b.total)})`
                         : `⚠ Extraction job is on, but no new posting for ${ago(last)} (Groq limit? PC asleep?)`)
    : `○ Extraction paused: ${b.done}/${b.total} postings (${pct(b.done / b.total)})`;
  const exMeta = [last ? `last posting extracted ${ago(last)} (${fmtTime(last)})` : "",
    ex && !exRunning && ex.next_run !== "N/A" ? `restarts ${ex.next_run}` : ""].filter(Boolean).join(" · ");
  renderPipe(s, exRunning && fresh, ld && ld.state === "Running");
  renderCharts(s);
  const run0 = s.runs[0];
  const ldTitle = ld && ld.state === "Running" ? "● Loading new skills into Supabase now"
    : `Load to Supabase (hourly): last ${run0 ? `${fmtTime(run0.started_at)} · ${run0.status}` : "never"}`;
  const ldMeta = [ld && ld.next_run !== "N/A" ? `next load ${ld.next_run}` : "",
    "copies the extracted postings into the database, then links skills to ESCO / O*NET"].filter(Boolean).join(" · ");
  $("#now").innerHTML = `<div class="row ${exCls}"><div class="t">${esc(exTitle)}</div><div class="m">${esc(exMeta)} · Groq ${esc(b ? b.model : "")}</div></div>`
    + `<div class="row ${ld && ld.state === "Running" ? "running" : ""}"><div class="t">${esc(ldTitle)}</div><div class="m">${esc(ldMeta)}</div></div>`;

  $("#status-cards").innerHTML = [  // the big counts are in the diagram above; these are the extras
    card("Greenhouse postings (live feed)", c.greenhouse), card("Review decisions", c.decisions),
    card("Langfuse traces (LLM calls)", lf.state === "connected" ? lf.traces : lf.state === "error" ? "error" : "off",
      `<div class="muted">${lf.state === "connected" ? (lf.last_trace ? `last ${esc(new Date(lf.last_trace).toLocaleString())}` : "none yet: first trace at the next pipeline run")
        : lf.state === "error" ? esc(lf.error) : "add keys to .env"}</div>`),
    card("Database size (free: 500 MB)", `${(c.db_bytes / 1e6).toFixed(1)} MB`,
      `<div class="progress"><span style="width:${pct(Math.min(c.db_bytes / 500e6, 1))}"></span></div>`),
  ].join("");

  const run = s.latest;
  $("#run-title").textContent = run ? `· ${run.source} · ${run.run_id} · ${run.status}` : "· no runs yet";
  $("#flow").innerHTML = Object.entries(s.stages).map(([name, st], i) => {
    const cls = st === "done" ? "done" : st === "error" ? "error" : st ? (run && run.status === "running" ? "running" : "done") : "";
    const skip = run && run.source === "kaggle" && (name === "fetch" || name === "clean") ? "skipped (Kaggle file is fixed)" : "skipped";
    const label = st === "error" ? "error" : cls === "running" ? "running…" : cls === "done" ? "done" : skip;
    return `${i ? '<span class="arrow">→</span>' : ""}<div class="stage ${cls}"><div class="name">${esc(name)}</div><div class="st">${esc(label)}</div></div>`;
  }).join("");

  const m = s.active_model;
  $("#active-model").textContent = m || "—";
  $("#active-model").className = `model-chip ${m && !m.includes("qwen") ? "fallback" : ""}`;
  $("#fallback-note").textContent = m && !m.includes("qwen") ? "fallback in use (primary Groq Qwen unavailable)" : m ? "primary model" : "";

  const total = s.verdicts.reduce((a, v) => a + v.n, 0) || 1;
  const byV = Object.fromEntries(s.verdicts.map((v) => [v.verdict, v.n]));
  $("#verdict-bar").innerHTML = VERDICTS.map((v) => `<span class="v-${v}" style="width:${pct((byV[v] || 0) / total)}" title="${v}: ${byV[v] || 0}"></span>`).join("");
  $("#verdict-legend").innerHTML = VERDICTS.map((v) => `<span><span class="sw v-${v}"></span>${v} ${byV[v] || 0} (${pct((byV[v] || 0) / total)})</span>`).join("");

  $("#events").innerHTML = s.events.slice().reverse().map((e) =>
    `<tr><td>${fmtTime(e.ts)}</td><td>${esc(e.stage)}</td><td><span class="badge b-${e.status === "error" ? "warn" : e.status === "done" ? "ok" : "edited"}">${esc(e.status)}</span></td><td><code>${esc(e.model || "")}</code></td><td>${esc(e.message)}</td></tr>`).join("")
    || '<tr><td colspan="5" class="muted">No events yet. Run <code>py src/pipeline.py</code> or <code>py src/load_supabase.py</code>.</td></tr>';
  $("#models").innerHTML = s.models.map((x) => `<tr><td><code>${esc(x.model)}</code></td><td>${x.n}</td></tr>`).join("");
  $("#switches").innerHTML = s.switches.map((x) => `<li><div class="t">${esc(x.message)}</div><div class="m">${fmtTime(x.ts)} · run ${esc(x.run_id)}</div></li>`).join("")
    || '<li class="muted">No fallbacks so far.</li>';
  $("#runs").innerHTML = s.runs.map((r) => `<li><div class="t">${esc(r.source)} · ${esc(r.status)}</div><div class="m">${esc(r.run_id)} · fetched ${r.n_fetched} · new ${r.n_new} · skills ${r.n_statements}</div></li>`).join("");
}
// Pipeline diagram: one box per step with live counts; dots move on the links while a job runs.
function renderPipe(s, extracting, loading) {
  const c = s.counts, b = s.batch, tx = s.taxonomy, n = (x) => (x ?? 0).toLocaleString();
  const known = s.verdicts.find((v) => v.verdict === "known_skill"), total = s.verdicts.reduce((a, v) => a + v.n, 0) || 1;
  const nodes = [
    { ic: "📄", k: "Postings", n: n(c.kaggle), m: `Kaggle sample + ${n(c.greenhouse)} Greenhouse` },
    { ic: "🤖", k: "Extract skills", n: b ? `${n(b.done)}/${n(b.total)}` : "—", m: `Qwen3.8 27B on Groq (free)`, live: extracting, log: "qwen" },
    { ic: "🧩", k: "Skill statements", n: n(c.statements), m: `${n(c.unique_skills)} unique skills`, live: loading },
    { ic: "🔗", k: "Link ESCO / O*NET", n: known ? pct(known.n / total) : "—", m: "statements matched to a known skill", live: loading },
    { ic: "🗂️", k: "Cluster topics", n: tx ? n(tx.topics) : "—", m: "HDBSCAN on skill embeddings", off: true, href: "/learn/cluster-topics.html#big" },
    { ic: "⭐", k: "Skill library", n: tx ? n(tx.library) : "—", m: tx ? `cross-sector skills · ${n(tx.strong_links)} strong links` : "", off: true,
      href: "/learn/library-links.html" },
  ];
  const flows = [extracting, loading, loading, false, false];
  $("#pipe").innerHTML = nodes.map((d, i) =>
    `${i ? `<span class="link ${flows[i - 1] ? "flow" : ""}" aria-hidden="true"></span>` : ""}`
    + `<${d.href ? `a href="${d.href}" target="_blank" rel="noopener"` : d.log ? `button type="button" data-log="${d.log}"` : "div"} class="node ${d.live ? "live" : ""} ${d.off ? "offline" : ""}">`
    + `<div class="ic" aria-hidden="true">${d.ic}</div><div class="k">${esc(d.k)}</div><div class="n">${esc(d.n)}</div>`
    + `<div class="m">${esc(d.m)}</div>${d.href ? '<div class="more">How it works →</div>' : d.log ? '<div class="more">Live log →</div>' : ""}`
    + `</${d.href ? "a" : d.log ? "button" : "div"}>`).join("");
  document.querySelectorAll("#pipe [data-log]").forEach((el) => el.addEventListener("click", () => openLog(el.dataset.log)));
  $("#pipe-note").textContent = "Solid boxes run on a schedule (extract continuously, load hourly). Dashed boxes are offline Sprint 3 steps."
    + ` Everything is stored in Supabase (${(c.db_bytes / 1e6).toFixed(1)} MB of 500 MB).`;
}

// Charts (Plotly, already loaded for the Skill map). One series each, so no legend; the caption names it.
function renderCharts(s) {
  if (!window.Plotly) return;
  const css = getComputedStyle(document.documentElement), v = (k) => css.getPropertyValue(k).trim();
  const ink = v("--text"), muted = v("--muted"), line = v("--line"), accent = v("--accent");
  const base = () => ({ margin: { l: 44, r: 10, t: 6, b: 36 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: v("--font"), size: 11, color: muted }, hoverlabel: { font: { color: ink } }, showlegend: false,
    xaxis: { gridcolor: "rgba(0,0,0,0)", linecolor: line, zeroline: false, fixedrange: true },
    yaxis: { gridcolor: line, zeroline: false, fixedrange: true, rangemode: "tozero" } });  // fresh each call: Plotly mutates layouts
  const cfg = { displayModeBar: false, responsive: true };
  const b = s.batch;
  if (b && b.times) {
    const times = b.times.map((t) => new Date(t * 1000));
    Plotly.react("ch-progress", [{ x: times, y: times.map((_, i) => i + 1), type: "scatter", mode: "lines",
      line: { color: accent, width: 2, shape: "hv" }, hovertemplate: "%{x|%b %d %H:%M}<br>%{y} postings<extra></extra>" }],
      { ...base(), yaxis: { ...base().yaxis, range: [0, b.total * 1.02], title: { text: `of ${b.total}`, font: { size: 11 } } } }, cfg);
  }
  let run = 0;
  const h = (s.history || []).map((r) => ({ x: new Date(r.ts), y: (run += r.n) }));
  Plotly.react("ch-loads", [{ x: h.map((r) => r.x), y: h.map((r) => r.y), type: "scatter", mode: "lines+markers",
    line: { color: accent, width: 2, shape: "hv" }, marker: { size: 8, color: accent },
    hovertemplate: "%{x|%b %d %H:%M}<br>%{y} statements<extra></extra>" }], base(), cfg);
  const t = (s.top_skills || []).slice().reverse();
  Plotly.react("ch-top", [{ x: t.map((r) => r.n), y: t.map((r) => r.skill_key), type: "bar", orientation: "h",
    marker: { color: accent }, text: t.map((r) => r.n), textposition: "outside", textfont: { color: muted },
    cliponaxis: false, hovertemplate: "%{y}: %{x} postings<extra></extra>" }],
    { ...base(), margin: { l: 130, r: 30, t: 6, b: 24 }, bargap: 0.25,
      xaxis: { ...base().xaxis, showticklabels: false }, yaxis: { ...base().yaxis, gridcolor: "rgba(0,0,0,0)", automargin: true,
        tickfont: { color: ink } } }, cfg);
}

setInterval(() => { if (view === "status" && !document.hidden) loadStatus(); }, 4000);

// ---------- 2. review queue ----------
let current = null;
$("#reviewer").value = store.get("reviewer");
$("#reviewer").addEventListener("change", () => store.set("reviewer", $("#reviewer").value.trim()));
let qTimer;
$("#queue-q").addEventListener("input", () => { clearTimeout(qTimer); qTimer = setTimeout(loadQueue, 250); });

async function loadQueue() {
  const rows = await api(`/api/review/queue?q=${encodeURIComponent($("#queue-q").value.trim())}`);
  $("#queue-count").textContent = `${rows.length} skills to review (most frequent first)`;
  $("#queue").innerHTML = rows.map((r) => `<li data-key="${esc(r.skill_key)}" class="${r.skill_key === current ? "sel" : ""}">
      <div class="t">${esc(r.skill_key)} <span class="muted">×${r.n}</span></div>
      <div class="m">closest: ${esc(r.ref_label)} (${esc(r.source)}, ${Number(r.score).toFixed(2)})</div></li>`).join("")
    || '<li class="muted">Nothing to review.</li>';
  document.querySelectorAll("#queue li[data-key]").forEach((li) => li.addEventListener("click", () => openSkill(li.dataset.key)));
}

function highlight(text, evidence) {
  if (!evidence) return esc(text);
  const i = text.toLowerCase().indexOf(evidence.toLowerCase());
  if (i < 0) return esc(text);
  return `${esc(text.slice(0, i))}<mark class="focus">${esc(text.slice(i, i + evidence.length))}</mark>${esc(text.slice(i + evidence.length))}`;
}

async function openSkill(key) {
  current = key;
  document.querySelectorAll("#queue li").forEach((li) => li.classList.toggle("sel", li.dataset.key === key));
  const d = await api(`/api/review/skill?key=${encodeURIComponent(key)}`);
  const ex = $("#examples");
  ex.classList.remove("empty-state");
  ex.innerHTML = `<h2>${esc(key)}</h2><p class="muted">Found in ${d.examples.length} example posting(s). Evidence is highlighted.</p>` +
    d.examples.map((e) => `<div class="example"><div class="t"><strong>${esc(e.title)}</strong> · ${esc(e.company)} ·
      <span class="badge b-direct">${esc(e.source)}</span> <code>${esc(e.model)}</code></div>
      <div class="ev">evidence: “${esc(e.evidence)}”</div>
      <div class="posting-text">${highlight(e.description, e.evidence)}</div></div>`).join("");
  ex.querySelectorAll("mark.focus").forEach((m) => m.scrollIntoView({ block: "center" }));

  const l = d.link || {};
  const dec = $("#decide");
  dec.classList.remove("empty-state");
  dec.innerHTML = `<h2>Decision</h2>
    <dl class="kv"><dt>Closest library entry</dt><dd>${esc(l.ref_label)}</dd><dt>Library</dt><dd>${esc(l.source)}</dd>
      <dt>Similarity</dt><dd>${l.score == null ? "—" : Number(l.score).toFixed(3)} (needs ≥ 0.85 to count)</dd></dl>
    <div class="decide">
      <div class="row"><button data-d="skill">✓ It is a skill</button><button class="trait" data-d="trait">Trait</button>
        <button class="danger" data-d="not_a_skill">✗ Not a skill</button></div>
      <label class="muted">Alias of (canonical name) <input id="alias" placeholder="e.g. Amazon Web Services"></label>
      <div class="row"><button class="ghost" data-d="alias">Save as alias</button></div>
      <label class="muted">Note (optional) <input id="note" placeholder="why"></label>
    </div>
    <h3>History</h3><ul class="history">${d.history.map((h) => `<li>${esc(h.decision)}${h.alias_of ? ` → ${esc(h.alias_of)}` : ""} · ${esc(h.reviewer)} · ${fmtTime(h.decided_at)}</li>`).join("") || "<li>none</li>"}</ul>`;
  dec.querySelectorAll("button[data-d]").forEach((b) => b.addEventListener("click", () => decide(b.dataset.d)));
}

async function decide(decision) {
  const reviewer = $("#reviewer").value.trim();
  const st = $("#save-status");
  if (!reviewer) { st.className = "save-status error"; st.textContent = "Enter your reviewer ID first."; $("#reviewer").focus(); return; }
  store.set("reviewer", reviewer);
  st.className = "save-status saving"; st.textContent = "Saving…";
  try {
    await api("/api/review/decision", { skill_key: current, decision, reviewer, alias_of: $("#alias")?.value, note: $("#note")?.value });
    st.className = "save-status saved"; st.textContent = `Saved: “${current}” → ${decision}`;
    const next = document.querySelector(`#queue li[data-key="${CSS.escape(current)}"]`)?.nextElementSibling?.dataset.key;
    await loadQueue();
    if (next) openSkill(next); else { $("#examples").innerHTML = "Done."; $("#decide").innerHTML = ""; }
  } catch (e) { st.className = "save-status error"; st.textContent = `Not saved: ${e.message}`; }
}

// ---------- 3. skills ----------
let sTimer;
$("#s-q").addEventListener("input", () => { clearTimeout(sTimer); sTimer = setTimeout(loadSkills, 250); });
$("#s-verdict").addEventListener("change", loadSkills);
async function loadSkills() {
  const rows = await api(`/api/skills?verdict=${$("#s-verdict").value}&q=${encodeURIComponent($("#s-q").value.trim())}`);
  $("#skills-count").textContent = `${rows.length} skills (top 300 by frequency)`;
  $("#skills").innerHTML = rows.map((r) => `<tr><td>${esc(r.skill_key)}</td><td>${r.n}</td>
    <td><span class="badge b-${r.verdict}">${esc(r.verdict)}</span></td><td>${esc(r.ref_label)}</td><td>${esc(r.source)}</td>
    <td>${r.review_status === "reviewed" ? '<span class="badge b-reviewed">reviewed</span>' : '<span class="muted">auto</span>'}</td></tr>`).join("");
}

// ---------- 4. skill map ----------
const PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#17becf", "#bcbd22",
  "#393b79", "#ad494a", "#637939", "#8c6d31", "#7b4173", "#3182bd", "#e6550d", "#31a354", "#756bb1", "#636363", "#e7969c"];
const TOP_TOPICS = 20; // coloured: biggest domain (non-transversal) topics by mentions of assigned skills
const libColor = (i) => `hsl(${(i * 137.5) % 360}, 70%, 45%)`;
let M = null, LIB = [], libSel = null;

async function loadMap() {
  if (!M) {
    try {
      const [m, lib] = await Promise.all([api("/api/map"), api("/api/library")]);
      const p = m.points, n = p.skill_key.length;
      const label = Object.fromEntries(m.topics.map((t) => [t.topic_id, t.label]));
      const transversal = new Set(m.topics.filter((t) => t.is_transversal).map((t) => t.topic_id));
      const cent = {}, mentions = {};
      for (let i = 0; i < n; i++) {
        const t = p.topic_id[i];
        if (p.state[i] !== "assigned") continue;
        if (!p.lib[i]) mentions[t] = (mentions[t] || 0) + p.mention_count[i];
        const c = (cent[t] ||= [0, 0, 0, 0]);
        c[0] += p.x[i]; c[1] += p.y[i]; c[2] += p.z[i]; c[3]++;
      }
      Object.values(cent).forEach((c) => { c[0] /= c[3]; c[1] /= c[3]; c[2] /= c[3]; });
      const top = Object.keys(mentions).filter((t) => cent[t] && !transversal.has(t)).sort((a, b) => mentions[b] - mentions[a]).slice(0, TOP_TOPICS);
      M = { ...m, n, label, cent, top };
      LIB = lib.map((l, i) => ({ ...l, color: libColor(i) }));
    } catch (e) { $("#map-info").textContent = `error: ${e.message}`; return; }
  }
  $("#map-info").textContent = `${M.n} skills · ${M.topics.length} topics · run ${M.run.run_id}`;
  const pre = decodeURIComponent(location.hash.split("/")[1] || "");  // #map/<library skill> preselects it
  if (pre && !libSel) { libSel = LIB.find((l) => l.skill_key === pre) || null; renderLibDetail(); }
  renderLibList();
  drawMap();
}

function drawMap() {
  const p = M.points, idx = { top: {}, other: [], weak: [], lib: [] };
  M.top.forEach((t) => (idx.top[t] = []));
  for (let i = 0; i < M.n; i++) {
    if (p.lib[i]) idx.lib.push(i);
    else if (p.state[i] !== "assigned") idx.weak.push(i);
    else if (idx.top[p.topic_id[i]]) idx.top[p.topic_id[i]].push(i);
    else idx.other.push(i);
  }
  const hover = (i) => `${p.skill_key[i]}<br>topic ${p.topic_id[i]}: ${M.label[p.topic_id[i]] || ""}<br>${p.state[i]} · ×${p.mention_count[i]}`;
  const pts = (ids, name, marker, visible = true) => ({
    type: "scatter3d", mode: "markers", name, visible, hoverinfo: "text",
    x: ids.map((i) => p.x[i]), y: ids.map((i) => p.y[i]), z: ids.map((i) => p.z[i]), text: ids.map(hover), marker,
  });
  const traces = [
    pts(idx.other, "other topics", { size: 2, color: "#9aa1ab", opacity: 0.35 }),
    pts(idx.weak, "weak (unclustered)", { size: 2, color: "#c9cdd3", opacity: 0.25 }, $("#m-weak").checked),
    ...M.top.map((t, k) => pts(idx.top[t], `${t} ${M.label[t]}`, { size: 3, color: PALETTE[k], opacity: 0.85 })),
    pts(idx.lib, "skill library", { size: 5, symbol: "diamond", color: idx.lib.map((i) => libColorOf(p.skill_key[i])), opacity: 1 }),
  ];
  const q = $("#m-q").value.trim().toLowerCase();
  if (q) {
    const hit = [];
    for (let i = 0; i < M.n && hit.length < 300; i++) if (p.skill_key[i].includes(q)) hit.push(i);
    traces.push(pts(hit, `match “${q}” (${hit.length})`, { size: 7, color: "#e11d48", line: { color: "#fff", width: 1 } }));
  }
  if (libSel) traces.push(...libLines(libSel));
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  Plotly.react("map", traces, {
    margin: { l: 0, r: 0, t: 0, b: 0 }, paper_bgcolor: "rgba(0,0,0,0)", font: { color: dark ? "#e7e9ec" : "#1d1f23", size: 11 },
    legend: { itemsizing: "constant", x: 0.01, y: 0.99, font: { size: 10 }, bgcolor: dark ? "rgba(29,32,36,.7)" : "rgba(255,255,255,.7)" },
    uirevision: "keep", scene: { domain: { x: [0, 1], y: [0, 1] }, camera: { eye: { x: 0.85, y: 0.85, z: 0.6 } }, xaxis: { visible: false }, yaxis: { visible: false }, zaxis: { visible: false } },
  }, { displaylogo: false, responsive: true });
}

function libColorOf(key) { return (LIB.find((l) => l.skill_key === key) || {}).color || "#000"; }

function libLines(l) {
  const p = M.points, i = p.skill_key.indexOf(l.skill_key);
  if (i < 0) return [];
  const seg = (strength) => {
    const x = [], y = [], z = [];
    l.links.filter((k) => k.strength === strength && M.cent[k.topic_id]).forEach((k) => {
      const c = M.cent[k.topic_id];
      x.push(p.x[i], c[0], null); y.push(p.y[i], c[1], null); z.push(p.z[i], c[2], null);
    });
    return { type: "scatter3d", mode: "lines", name: `${l.skill_key}: ${strength} links`, hoverinfo: "skip",
      x, y, z, line: { color: l.color, width: strength === "strong" ? 8 : 2 } };
  };
  return [seg("strong"), seg("weak")];
}

function renderLibList() {
  const f = $("#lib-q").value.trim().toLowerCase();
  const rows = LIB.filter((l) => l.skill_key.includes(f));
  $("#lib-count").textContent = `(${LIB.length})`;
  $("#lib-list").innerHTML = rows.map((l) => `<button class="chip ${libSel === l ? "sel" : ""}" data-k="${esc(l.skill_key)}"
      style="--c:${l.color}"><span class="sw"></span>${esc(l.skill_key)}</button>`).join("");
  document.querySelectorAll("#lib-list .chip").forEach((b) => b.addEventListener("click", () => {
    const l = LIB.find((x) => x.skill_key === b.dataset.k);
    libSel = libSel === l ? null : l;
    renderLibList(); renderLibDetail(); drawMap();
  }));
}

function renderLibDetail() {
  const l = libSel;
  if (!l) { $("#lib-detail").innerHTML = ""; return; }
  $("#lib-detail").innerHTML = `<h3 style="color:${l.color}">${esc(l.skill_key)}</h3>
    <p class="muted">${l.status} · ${l.n_postings} postings · ${l.n_sectors} sectors · spread ${Number(l.entropy).toFixed(2)}</p>
    <p><span class="badge b-edited" title="from its ESCO / O*NET link (skill_types.py)">type: ${esc(l.skill_type || "unknown")}</span>
      ${l.reuse_level ? `<span class="badge b-edited" title="ESCO reuse level">${esc(l.reuse_level)}</span>` : ""}
      <span class="muted">${esc(l.rule_version || "")}</span></p>
    <table><thead><tr><th>Linked topic</th><th title="postings with both / distinct job templates (company + title)">Postings / templates</th><th>Lift</th><th>q</th><th></th></tr></thead><tbody>
    ${l.links.map((k) => `<tr><td>${esc(k.topic_id)} ${esc(k.label)}</td><td>${k.link_postings}${k.link_templates != null ? ` / ${k.link_templates}` : ""}</td><td>${Number(k.lift).toFixed(2)}</td>
      <td>${Number(k.q_value).toExponential(1)}</td><td><span class="badge b-${k.strength === "strong" ? "ok" : "edited"}">${k.strength}</span></td></tr>`).join("")}
    </tbody></table>`;
}

let mTimer;
$("#m-q").addEventListener("input", () => { clearTimeout(mTimer); mTimer = setTimeout(() => M && drawMap(), 300); });
$("#m-weak").addEventListener("change", () => M && drawMap());
$("#lib-q").addEventListener("input", () => M && renderLibList());


// ---------- 5. models & code ----------
const PROMPTS = {  // prompts have no docstring; one line each from docs/HANDOFF.md
  "prompts/skill_extraction_v1.txt": "Prompt v1: first version (Sprint 2 baseline).",
  "prompts/skill_extraction_v2.txt": "Prompt v2: tighter rules, better precision.",
  "prompts/skill_extraction_v3.txt": "Prompt v3: FROZEN working prompt, targets skills inside lists (list recall .83).",
  "prompts/skill_extraction_v4.txt": "Prompt v4: rules A-D + paper ideas; no gain, so v3 stays.",
};
const GROUPS = [
  ["1. Data", ["download_data", "clean_postings", "make_extraction_sample", "download_reference"]],
  ["2. Gold set & scoring", ["make_gold_sample", "make_gold_postings", "make_gold_split", "gold_tool", "check_gold", "evaluate",
    "list_recall", "bias_check", "make_dashboard_data"]],
  ["3. Extraction (LLM)", ["extract_skills", "llm_router", "skill_extraction_v1", "skill_extraction_v2", "skill_extraction_v3",
    "skill_extraction_v4", "qwen_batch"]],
  ["4. ESCO / O*NET linking + Supabase", ["link_reference", "load_supabase", "pipeline", "db", "verify_db", "supabase_schema",
    "load_qwen", "nightly_greenhouse"]],
  ["5. Clustering + library (Sprint 3)", ["prepare_skills", "normalize_aliases", "embed_skills", "cluster_skills", "cluster_stability",
    "build_library", "load_taxonomy", "make_skill_map", "taxonomy_schema"]],
  ["6. This UI", ["server"]],
];
let modelsData = null;
const stem = (path) => path.split("/").pop().replace(/\.[^.]+$/, "");
const vscode = (path) => `vscode://file/${modelsData.root}/${path}`;

async function loadModels() {
  if (!modelsData) {
    try { modelsData = await api("/api/models"); } catch (e) { $("#m-rows").innerHTML = `<tr><td colspan="12">error: ${esc(e.message)}</td></tr>`; return; }
    const known = new Set(GROUPS.flatMap(([, s]) => s));
    const groups = GROUPS.map(([g, stems]) => [g, modelsData.files.filter((f) => stems.includes(stem(f.path)))]);
    groups.push(["Other", modelsData.files.filter((f) => !known.has(stem(f.path)))]);
    $("#code-map").innerHTML = groups.filter(([, fs]) => fs.length).map(([g, fs]) => `<div class="grp"><h4>${esc(g)}</h4><ul>${fs.map((f) =>
      `<li><a href="${esc(vscode(f.path))}">${esc(f.path)}</a><div class="d">${esc(f.doc || PROMPTS[f.path] || "")}</div></li>`).join("")}</ul></div>`).join("");
    $("#m-split").addEventListener("change", renderModelRows);
    $("#m-gold").addEventListener("change", renderModelRows);
  }
  renderModelRows();
  renderF1Chart();
}

function renderModelRows() {
  const sp = $("#m-split").value, gd = $("#m-gold").value;
  const rows = modelsData.runs.filter((r) => (!sp || r.split === sp) && (!gd || r.gold === gd));
  const f = (x) => `<td class="num">${x.toFixed(2)}</td>`;
  $("#m-rows").innerHTML = rows.map((r) => `<tr class="${r.model.includes("qwen") && r.prompt === "v3" ? "chosen" : ""}">`
    + `<td><code>${esc(r.model)}</code>${r.postings < 50 ? ` <span class="badge b-warn" title="only ${r.postings} postings scored (rate limit)">partial</span>` : ""}</td>`
    + `<td>${esc(r.prompt)}${r.variant ? ` · ${esc(r.variant)}` : ""}</td><td>${esc(r.split)}</td><td>${esc(r.gold)}</td><td class="num">${r.postings}</td>`
    + f(r.p_strict) + f(r.r_strict) + f(r.f1_strict) + f(r.p_lenient) + f(r.r_lenient) + f(r.f1_lenient)
    + `<td><a href="${esc(vscode(r.report))}">open</a></td></tr>`).join("")
    || '<tr><td colspan="12" class="muted">No runs match these filters (gold v2 was scored only on dev and test).</td></tr>';
}

function renderF1Chart() {
  if (!window.Plotly) return;
  const rows = modelsData.runs.filter((r) => r.split === "dev" && r.prompt === "v3" && r.gold === "v1")
    .sort((a, b) => a.f1_lenient - b.f1_lenient);
  const css = getComputedStyle(document.documentElement), v = (k) => css.getPropertyValue(k).trim();
  const dark = matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light";
  const [c1, c2] = dark ? ["#3987e5", "#d95926"] : ["#2a78d6", "#eb6834"];  // validated categorical slots 1-2 (dataviz palette)
  const names = rows.map((r) => r.model.replace(/^.*\//, "").replace(":free", "") + (r.postings < 50 ? ` (${r.postings} postings)` : ""));
  const bar = (key, name, color) => ({ type: "bar", orientation: "h", name, y: names, x: rows.map((r) => r[key]), marker: { color },
    text: rows.map((r) => r[key].toFixed(2)), textposition: "outside", textfont: { color: v("--muted") }, cliponaxis: false,
    hovertemplate: `%{y}<br>${name}: %{x:.2f}<extra></extra>` });
  Plotly.react("ch-f1", [bar("f1_strict", "F1 strict", c1), bar("f1_lenient", "F1 lenient", c2)], {
    barmode: "group", bargap: 0.3, bargroupgap: 0.1, margin: { l: 10, r: 40, t: 4, b: 30 },
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { family: v("--font"), size: 11, color: v("--muted") },
    legend: { orientation: "h", y: 1.08, x: 0, font: { color: v("--text") } },
    xaxis: { range: [0, 1], gridcolor: v("--line"), zeroline: false, fixedrange: true },
    yaxis: { automargin: true, tickfont: { color: v("--text") }, fixedrange: true } }, { displayModeBar: false, responsive: true });
  $("#f1-note").textContent = "Partial runs stopped early on free-tier limits, so their scores are less reliable. "
    + "On the test half, Qwen v3 and Claude Haiku are almost tied (see the table, split = test).";
}

// ---------- live job log (Extract skills box) ----------
let logTimer = null;
function logClass(line) {
  if (/FAILED|Error|Traceback|429/.test(line)) return "warn";
  if (/: \d+ skills|done|finished|loaded/i.test(line)) return "ok";
  return /^\s/.test(line) ? "dim" : "";
}
async function refreshLog() {
  const name = $("#log-name").value || "qwen";
  let d;
  try { d = await api(`/api/logs?name=${encodeURIComponent(name)}&lines=300`); } catch (e) { $("#log-meta").textContent = `error: ${e.message}`; return; }
  if (d.logs && $("#log-name").options.length < Object.keys(d.logs).length) {  // first answer brings the real list
    $("#log-name").innerHTML = Object.entries(d.logs).map(([k, t]) => `<option value="${esc(k)}">${esc(t)}</option>`).join("");
    $("#log-name").value = name;
  }
  const when = d.modified ? new Date(d.modified * 1000) : null;
  const fresh = when && Date.now() - when < 15 * 60000;
  $("#log-title").textContent = d.title;
  $("#log-meta").textContent = `${d.path} · ${d.lines.length} last lines · `
    + (when ? `last written ${ago(when)} (${when.toLocaleString()})${fresh ? " · job is writing" : " · no new lines recently: the job is idle, waiting on a rate limit, or stopped"}` : "no log file yet");
  const box = $("#log-text"), atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
  box.innerHTML = d.lines.map((l) => `<span class="${logClass(l)}">${esc(l)}</span>`).join("\n") || '<span class="dim">(empty)</span>';
  if ($("#log-follow").checked && atEnd) box.scrollTop = box.scrollHeight;
}
function openLog(name) {
  if ($("#log-name").options.length) $("#log-name").value = name;
  else $("#log-name").innerHTML = `<option value="${esc(name)}">${esc(name)}</option>`;
  $("#log-dialog").showModal();
  $("#log-text").scrollTop = 1e9;
  refreshLog().then(() => { $("#log-text").scrollTop = 1e9; });
  clearInterval(logTimer);
  logTimer = setInterval(() => { if (!document.hidden) refreshLog(); }, 3000);
}
$("#log-close").addEventListener("click", () => $("#log-dialog").close());
$("#log-dialog").addEventListener("close", () => clearInterval(logTimer));
$("#log-name").addEventListener("change", () => refreshLog().then(() => { $("#log-text").scrollTop = 1e9; }));

// ---------- resizable library panel (Skill map) ----------
(() => {
  const grid = document.querySelector(".map-grid"), bar = $("#map-split");
  const clamp = (w) => Math.round(Math.max(280, Math.min(w, grid.clientWidth * 0.7)));
  const set = (w, save) => {
    grid.style.setProperty("--lib-w", `${clamp(w)}px`);
    if (save) store.set("libWidth", String(clamp(w)));
    if (window.Plotly && $("#map").data) Plotly.Plots.resize("map");
  };
  const saved = +store.get("libWidth");
  if (saved) grid.style.setProperty("--lib-w", `${saved}px`);
  bar.addEventListener("pointerdown", (e) => {
    bar.setPointerCapture(e.pointerId); bar.classList.add("drag");
    const move = (ev) => set(grid.getBoundingClientRect().right - ev.clientX, false);
    const up = (ev) => { bar.classList.remove("drag"); bar.removeEventListener("pointermove", move); bar.removeEventListener("pointerup", up);
      set(grid.getBoundingClientRect().right - ev.clientX, true); };
    bar.addEventListener("pointermove", move); bar.addEventListener("pointerup", up);
  });
  bar.addEventListener("keydown", (e) => {
    const now = document.querySelector(".lib").getBoundingClientRect().width;
    if (e.key === "ArrowLeft") { set(now + 40, true); e.preventDefault(); }
    if (e.key === "ArrowRight") { set(now - 40, true); e.preventDefault(); }
  });
})();

loadStatus();
if (location.hash) document.querySelector(`.tabs button[data-view="${CSS.escape(location.hash.slice(1).split("/")[0])}"]`)?.click();
