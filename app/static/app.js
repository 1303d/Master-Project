// Section B pipeline UI. Plain JS, no build step. All data comes from app/server.py (/api/*).
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtTime = (t) => (t ? new Date(t).toLocaleTimeString() : "");
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
}));

// ---------- 1. pipeline status ----------
function card(k, v, extra = "") { return `<div class="card"><div class="k">${esc(k)}</div><div class="v">${v}</div>${extra}</div>`; }

async function loadStatus() {
  let s;
  try { s = await api("/api/status"); } catch (e) { $("#updated").textContent = `error: ${e.message}`; return; }
  $("#updated").textContent = `updated ${new Date().toLocaleTimeString()}`;
  $("#langfuse").href = s.langfuse_url;
  $("#lf-dot").className = `dot ${s.langfuse ? "on" : "off"}`;
  $("#lf-dot").title = s.langfuse ? "Langfuse keys set: LLM calls are traced" : "No Langfuse keys in .env";

  const c = s.counts, b = s.batch;
  $("#status-cards").innerHTML = [
    card("Kaggle postings", c.kaggle), card("Greenhouse postings", c.greenhouse),
    card("Skill statements", c.statements), card("Unique skills", c.unique_skills),
    card("Review decisions", c.decisions),
    card("Database size (free: 500 MB)", `${(c.db_bytes / 1e6).toFixed(1)} MB`,
      `<div class="progress"><span style="width:${pct(Math.min(c.db_bytes / 500e6, 1))}"></span></div>`),
    b ? card(`Kaggle batch (${b.model})`, `${b.done}/${b.total}`,
      `<div class="progress"><span style="width:${pct(b.done / b.total)}"></span></div>`) : "",
  ].join("");

  const run = s.latest;
  $("#run-title").textContent = run ? `· ${run.source} · ${run.run_id} · ${run.status}` : "· no runs yet";
  $("#flow").innerHTML = Object.entries(s.stages).map(([name, st], i) => {
    const cls = st === "done" ? "done" : st === "error" ? "error" : st ? (run && run.status === "running" ? "running" : "done") : "";
    const label = st === "done" ? "done" : st === "error" ? "error" : st ? (cls === "running" ? "running…" : st) : "not run";
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

loadStatus();
