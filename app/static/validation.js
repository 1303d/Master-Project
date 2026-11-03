// Gold Validation page. Plain JS, no build step. All data comes from app/validation_api.py (/api/validation/*).
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get: (k) => { try { return localStorage.getItem(k) || ""; } catch { return ""; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode: ignore */ } },
};
const REV = (s) => `<span class="st-${esc(s)}">${esc(s)}</span>`;
const TYPE = { model_only: "model-only (extra)", gold_only: "gold-only (missed)" };
const P1_DECISIONS = ["KEEP_GOLD", "ADD_TO_GOLD", "REMOVE_FROM_GOLD", "REVISE_GOLD", "UNSURE"];
const P2_DECISIONS = ["VALID_SKILL", "INVALID_SKILL", "NEEDS_REVISION", "UNSURE"];

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  let data;
  try { data = await r.json(); } catch { throw new Error(`${r.status} ${r.statusText}`); }
  if (!r.ok) { const e = new Error(data.error || r.statusText); e.missing = data.missing; e.hint = data.hint; throw e; }
  return data;
}
function say(msg, kind = "saved") { const s = $("#gv-save"); s.className = `save-status ${kind}`; s.textContent = msg; }
function reviewer() {
  const r = $("#gv-reviewer").value;
  if (!r) { say("Choose your reviewer name (top right) first.", "error"); $("#gv-reviewer").focus(); }
  return r;
}
function findAt(text, phrase) {  // same rule as the server: exact, else ignore case + runs of whitespace
  if (!phrase) return null;
  const i = text.indexOf(phrase);
  if (i >= 0) return [i, i + phrase.length];
  const re = new RegExp(phrase.trim().split(/\s+/).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+"), "i");
  const m = re.exec(text);
  return m ? [m.index, m.index + m[0].length] : null;
}
function highlight(text, phrases) {
  const spans = phrases.map((p) => findAt(text, p)).filter(Boolean).sort((a, b) => a[0] - b[0]);
  let out = "", at = 0;
  for (const [s, e] of spans) { if (s < at) continue; out += esc(text.slice(at, s)) + `<mark class="focus">${esc(text.slice(s, e))}</mark>`; at = e; }
  return out + esc(text.slice(at));
}
async function postingPane(el, part, item, phrases) {
  el.classList.remove("empty-state");
  el.innerHTML = `<h2>Posting #${esc(item.n)} <span class="muted">${esc(item.posting_id)}</span></h2><p class="muted">Loading…</p>`;
  try {
    const p = await api(`/api/validation/posting?part=${part}&item=${encodeURIComponent(item.item_id)}`);
    if (p.missing) { el.innerHTML += `<div class="warnbox">${esc(p.message)}</div>`; el.querySelector("p.muted")?.remove(); return null; }
    el.innerHTML = `<h2>Posting #${esc(item.n)} <span class="muted">${esc(item.posting_id)}</span></h2>
      <div class="posting-text">${highlight(p.description, phrases)}</div>`;
    el.querySelector("mark.focus")?.scrollIntoView({ block: "center" });
    return p.description;
  } catch (e) { el.innerHTML += `<div class="warnbox">${esc(e.message)}</div>`; return null; }
}
const ruleSelect = (id, value) => `<label>Applicable labelling rule <select id="${id}"><option value="">—</option>${
  (S.status?.rule_choices || []).map((r) => `<option ${r === value ? "selected" : ""}>${esc(r)}</option>`).join("")}</select></label>`;
const versionsHtml = (vs) => vs.length ? `<h3>My submitted versions</h3><ul class="history">${vs.map((v) =>
  `<li>v${v.version} · ${esc(v.action)} · ${esc(v.ts)}${v.amend_reason ? ` · reason: ${esc(v.amend_reason)}` : ""}${
    v.post_reveal ? " · <strong>after reveal: kept for the record, not counted in scores</strong>" : ""}</li>`).join("")}</ul>` : "";

// ---------- state, tabs, status ----------
const S = { status: null, view: "p1", p1: [], p2: [], p3: [], cases: [], sel: {} };
document.querySelectorAll("#gv-tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
function show(v) {
  S.view = v;
  document.querySelectorAll("#gv-tabs button").forEach((x) => x.setAttribute("aria-selected", String(x.dataset.view === v)));
  document.querySelectorAll(".view").forEach((s) => (s.hidden = s.id !== `view-${v}`));
  refresh();
}
$("#gv-reviewer").addEventListener("change", () => { store.set("gv-reviewer", $("#gv-reviewer").value); S.sel = {}; refresh(); });

async function loadStatus() {
  S.status = await api("/api/validation/status");
  const sel = $("#gv-reviewer");
  if (sel.options.length === 1) {
    sel.innerHTML += S.status.reviewers.map((r) => `<option>${esc(r)}</option>`).join("");
    sel.value = S.status.reviewers.includes(store.get("gv-reviewer")) ? store.get("gv-reviewer") : "";
    $("#p1-rule").innerHTML += S.status.rule_choices.map((r) => `<option>${esc(r)}</option>`).join("");
    const runs = new Set(); S.status.manifests.forEach((m) => (m.settings?.runs || []).forEach((r) => runs.add(r)));
    $("#p1-run").innerHTML += [...runs].map((r) => `<option>${esc(r)}</option>`).join("");
  }
  const alerts = [];
  const miss = S.status.artifacts.filter((a) => !a.exists);
  if (miss.length) alerts.push(`Missing on this machine: ${miss.map((a) => `<code>${esc(a.path)}</code> (${esc(a.source)})`).join(", ")}. Affected views show a message instead of data.`);
  S.status.manifests.filter((m) => !m.manifest_id).forEach((m) => alerts.push(`Part ${m.part} sample is not built yet — open <b>Source Versions</b> and press “Build missing samples”.`));
  S.status.manifests.filter((m) => m.stale_sources?.length).forEach((m) => alerts.push(`Part ${m.part} (${esc(m.manifest_id)}): sources changed since the sample was built (${m.stale_sources.map(esc).join(", ")}). Reviews stay tied to the old sample; rebuild with <code>python src/validation/cli.py build --new-version</code> after the team agrees.`));
  if (S.status.broken_log_lines.length) alerts.push(`Unreadable lines in review logs (unresolved Git merge?): ${S.status.broken_log_lines.map(esc).join(", ")}`);
  $("#gv-alerts").innerHTML = alerts.map((a) => `<div class="warnbox">${a}</div>`).join("");
  const sm = S.status.summary;
  if (sm && sm.parts) {
    const ps = Object.values(sm.parts).filter((p) => p.manifest);
    const total = ps.reduce((a, p) => a + p.items, 0), done = ps.reduce((a, p) => a + p.reviewed, 0);
    const card = (k, v) => `<div class="card"><div class="k">${esc(k)}</div><div class="v">${v}</div></div>`;
    $("#gv-summary").innerHTML = card("Total review cases", total) + card("Completed (≥1 submitted review)", done) +
      card("Pending", total - done) + card("Unresolved adjudication cases", sm.team.awaiting_adjudication + sm.team.needs_discussion);
  }
}

async function refresh() {
  try { await loadStatus(); } catch (e) { $("#gv-alerts").innerHTML = `<div class="warnbox">${esc(e.message)}</div>`; return; }
  const r = $("#gv-reviewer").value;
  const needR = ["p1", "p2", "p3", "adj"].includes(S.view);
  if (needR && !r) { say("Choose your reviewer name (top right) to load your queue.", "error"); return; }
  say("");
  try {
    if (S.view === "p1") await loadP1();
    if (S.view === "p2") await loadP2();
    if (S.view === "p3") await loadP3();
    if (S.view === "adj") await loadCases();
    if (S.view === "progress") renderProgress();
    if (S.view === "sources") renderSources();
  } catch (e) { say(e.message, "error"); }
}

function listNav(part, items, open) {
  const i = items.findIndex((x) => x.item_id === S.sel[part]);
  return `<div class="nav-row"><button class="ghost" ${i <= 0 ? "disabled" : ""} data-go="${i - 1}">← Previous</button>
    <button class="ghost" ${i < 0 || i >= items.length - 1 ? "disabled" : ""} data-go="${i + 1}">Next →</button></div>`;
}
function wireNav(el, items, open) { el.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => open(items[+b.dataset.go].item_id))); }

async function send(part, item, action, data, amend_reason) {
  const r = reviewer(); if (!r) return false;
  say("Saving…", "saving");
  try {
    await api("/api/validation/review", { reviewer: r, part, item_id: item.item_id, action, data, amend_reason });
    say(`Saved: #${item.n} ${action === "draft" ? "draft" : action === "submit" ? "submitted (locked)" : "amendment saved as a new version"}`);
    return true;
  } catch (e) { say(`Not saved: ${e.message}`, "error"); return false; }
}

// ---------- Part 1 ----------
["#p1-q", "#p1-type", "#p1-status", "#p1-rule", "#p1-run"].forEach((s) => $(s).addEventListener("input", renderP1List));
async function loadP1() {
  const d = await api(`/api/validation/items?part=1&reviewer=${encodeURIComponent(reviewer())}`);
  S.p1 = d.items; renderP1List();
  if (S.sel.p1) openP1(S.sel.p1);
}
function p1Filtered() {
  const q = $("#p1-q").value.trim().toLowerCase(), t = $("#p1-type").value, st = $("#p1-status").value,
    rule = $("#p1-rule").value, run = $("#p1-run").value;
  return S.p1.filter((i) => (!q || i.posting_id.toLowerCase().includes(q) || i.label.toLowerCase().includes(q) || `#${i.n}` === q)
    && (!t || i.type === t) && (!st || i.status === st) && (!run || i.runs.includes(run))
    && (!rule || ((i.latest || i.draft || {}).rule === rule)));
}
function renderP1List() {
  const items = p1Filtered();
  $("#p1-count").textContent = `${items.length} of ${S.p1.length} items`;
  $("#p1-list").innerHTML = items.map((i) => `<li data-id="${i.item_id}" class="${i.item_id === S.sel.p1 ? "sel" : ""}">
    <div class="t">${esc(i.label)}</div><div class="m">#${esc(i.n)} · ${TYPE[i.type]} · ${REV(i.status)}${i.stale ? " · ⚠ stale" : ""}</div></li>`).join("")
    || '<li class="muted">No items match.</li>';
  document.querySelectorAll("#p1-list li[data-id]").forEach((li) => li.addEventListener("click", () => openP1(li.dataset.id)));
}
async function openP1(id) {
  S.sel.p1 = id; renderP1List();
  const it = S.p1.find((x) => x.item_id === id); if (!it) return;
  postingPane($("#p1-text"), 1, it, [it.label]);
  const cur = it.latest || it.draft || {}, locked = !!it.latest;
  const choices = P1_DECISIONS.filter((d) => !(d === "ADD_TO_GOLD" && it.type === "gold_only") && !(d === "REMOVE_FROM_GOLD" && it.type === "model_only"));
  const f = $("#p1-form"); f.classList.remove("empty-state");
  f.innerHTML = `${listNav("p1", p1Filtered())}<h2>${esc(it.label)}</h2>
    <dl class="kv"><dt>Type</dt><dd>${TYPE[it.type]}</dd>
      <dt>Existing gold label</dt><dd>${it.type === "gold_only" ? esc(it.label) : '<span class="muted">not in gold</span>'}</dd>
      <dt>Model prediction</dt><dd>${it.type === "model_only" ? esc(it.label) : '<span class="muted">not predicted</span>'}</dd>
      <dt>Runs</dt><dd>${it.runs.map(esc).join(", ")}</dd><dt>My status</dt><dd>${REV(it.status)}</dd></dl>
    ${it.stale ? '<div class="warnbox">This gold label is no longer in the current gold file (the run used an older gold).</div>' : ""}
    <div class="gv-form">
      <div class="gv-choices">${choices.map((d) => `<label><input type="radio" name="p1d" value="${d}" ${cur.decision === d ? "checked" : ""}> ${d}</label>`).join("")}</div>
      <label>Proposed label (REVISE_GOLD; optional wording for ADD_TO_GOLD) <input id="p1-label" value="${esc(cur.proposed_label)}"></label>
      ${ruleSelect("p1-rulesel", cur.rule)}
      <label>Reason (required for ADD / REMOVE / REVISE) <textarea id="p1-reason">${esc(cur.reason)}</textarea></label>
      ${locked ? '<label>Amendment reason (your submission is locked; changes create a new version) <input id="p1-amend"></label>' : ""}
      <div class="row">${locked ? '<button id="p1-amend-btn">Save amendment</button>'
        : '<button class="ghost" id="p1-draft">Save draft</button><button id="p1-submit">Submit review</button>'}</div>
    </div>${versionsHtml(it.versions)}`;
  wireNav(f, p1Filtered(), openP1);
  const data = () => ({ decision: f.querySelector("input[name=p1d]:checked")?.value, proposed_label: $("#p1-label").value,
    rule: $("#p1-rulesel").value, reason: $("#p1-reason").value });
  const after = async (ok) => { if (ok) { await loadP1(); } };
  $("#p1-draft")?.addEventListener("click", async () => after(await send(1, it, "draft", data())));
  $("#p1-submit")?.addEventListener("click", async () => after(await send(1, it, "submit", data())));
  $("#p1-amend-btn")?.addEventListener("click", async () => after(await send(1, it, "amend", data(), $("#p1-amend").value)));
}

// ---------- Part 2 (blind) ----------
["#p2-q", "#p2-status"].forEach((s) => $(s).addEventListener("input", renderP2List));
async function loadP2() {
  const d = await api(`/api/validation/items?part=2&reviewer=${encodeURIComponent(reviewer())}`);
  S.p2 = d.items; renderP2List();
  if (S.sel.p2) openP2(S.sel.p2);
}
function p2Filtered() {
  const q = $("#p2-q").value.trim().toLowerCase(), st = $("#p2-status").value;
  return S.p2.filter((i) => (!q || i.posting_id.toLowerCase().includes(q) || i.label.toLowerCase().includes(q)) && (!st || i.status === st));
}
function renderP2List() {
  const items = p2Filtered();
  $("#p2-count").textContent = `${items.length} of ${S.p2.length} candidates`;
  $("#p2-list").innerHTML = items.map((i) => `<li data-id="${i.item_id}" class="${i.item_id === S.sel.p2 ? "sel" : ""}">
    <div class="t">${esc(i.label)}</div><div class="m">#${esc(i.n)} · ${REV(i.status)}</div></li>`).join("") || '<li class="muted">No items match.</li>';
  document.querySelectorAll("#p2-list li[data-id]").forEach((li) => li.addEventListener("click", () => openP2(li.dataset.id)));
}
async function openP2(id) {
  S.sel.p2 = id; renderP2List();
  const it = S.p2.find((x) => x.item_id === id); if (!it) return;
  postingPane($("#p2-text"), 2, it, [it.label]);
  const cur = it.latest || it.draft || {}, locked = !!it.latest;
  const f = $("#p2-form"); f.classList.remove("empty-state");
  f.innerHTML = `${listNav("p2", p2Filtered())}<h2>Candidate: ${esc(it.label)}</h2>
    <p class="muted">Is this a valid skill label for this posting under the written rules?</p>
    <div class="gv-form">
      <div class="gv-choices">${P2_DECISIONS.map((d) => `<label><input type="radio" name="p2d" value="${d}" ${cur.decision === d ? "checked" : ""} ${locked ? "disabled" : ""}> ${d}</label>`).join("")}</div>
      <label>Proposed label (NEEDS_REVISION) <input id="p2-label" value="${esc(cur.proposed_label)}" ${locked ? "disabled" : ""}></label>
      ${ruleSelect("p2-rulesel", cur.rule)}
      <label>Explanation (required for INVALID / NEEDS_REVISION) <textarea id="p2-expl" ${locked ? "disabled" : ""}>${esc(cur.explanation)}</textarea></label>
      <div class="row">${locked ? '<button class="ghost" id="p2-reveal">Show reference (after submission)</button>'
        : '<button class="ghost" id="p2-draft">Save draft</button><button id="p2-submit">Submit (locks the blind review)</button>'}</div>
      <div id="p2-ref"></div>
    </div>${versionsHtml(it.versions)}`;
  wireNav(f, p2Filtered(), openP2);
  const data = () => ({ decision: f.querySelector("input[name=p2d]:checked")?.value, proposed_label: $("#p2-label").value,
    rule: $("#p2-rulesel").value, explanation: $("#p2-expl").value });
  $("#p2-draft")?.addEventListener("click", async () => { if (await send(2, it, "draft", data())) loadP2(); });
  $("#p2-submit")?.addEventListener("click", async () => { if (await send(2, it, "submit", data())) loadP2(); });
  $("#p2-reveal")?.addEventListener("click", async () => {
    if (!confirm("After you see the answer, later amendments are kept for the record but do not change your scored result. Continue?")) return;
    try {
      const d = await api(`/api/validation/reveal?item=${encodeURIComponent(it.item_id)}&reviewer=${encodeURIComponent(reviewer())}`);
      const ref = d.reference || {};
      $("#p2-ref").innerHTML = `<h3>Reference</h3><dl class="kv"><dt>Source</dt><dd>${esc(ref.source)}: in gold = ${esc(ref.in_gold)}, matched by ${esc((ref.matched_by_runs || []).join(", "))}</dd>
        <dt>Other reviewers</dt><dd>${Object.entries(d.others).map(([r, x]) => `${esc(r)}: ${esc(x.decision)}`).join(" · ") || "none yet"}</dd></dl>
        <p class="muted">Your submission stays as submitted. Disagreements go to Team Adjudication.</p>`;
    } catch (e) { say(e.message, "error"); }
  });
}

// ---------- Part 3 (independent) ----------
$("#p3-status").addEventListener("input", renderP3List);
$("#p3-rules-btn").addEventListener("click", async () => {
  try { const d = await api("/api/validation/rules"); $("#rules-text").textContent = d.text; $("#rules-dialog").showModal(); }
  catch (e) { say(e.message, "error"); }
});
async function loadP3() {
  const d = await api(`/api/validation/items?part=3&reviewer=${encodeURIComponent(reviewer())}`);
  S.p3 = d.items; renderP3List();
  if (S.sel.p3) openP3(S.sel.p3);
}
const p3Filtered = () => S.p3.filter((i) => !$("#p3-status").value || i.status === $("#p3-status").value);
function renderP3List() {
  const items = p3Filtered();
  $("#p3-count").textContent = `${items.length} of ${S.p3.length} postings`;
  $("#p3-list").innerHTML = items.map((i) => `<li data-id="${i.item_id}" class="${i.item_id === S.sel.p3 ? "sel" : ""}">
    <div class="t">Posting #${esc(i.n)}</div><div class="m">${esc(i.posting_id)} · ${REV(i.status)}${i.versions.length > 1 ? ` · v${i.versions.length}` : ""}</div></li>`).join("");
  document.querySelectorAll("#p3-list li[data-id]").forEach((li) => li.addEventListener("click", () => openP3(li.dataset.id)));
}
let p3Text = null;
async function openP3(id, amending = false) {
  S.sel.p3 = id; renderP3List();
  const it = S.p3.find((x) => x.item_id === id); if (!it) return;
  const cur = (amending ? it.latest : it.draft || it.latest) || { skills: [] };
  p3Text = await postingPane($("#p3-text"), 3, it, (cur.skills || []).map((s) => s.evidence));
  const locked = !!it.latest && !amending;
  const f = $("#p3-form"); f.classList.remove("empty-state");
  const row = (s = {}) => `<div class="skill-row">
      <label>Skill <input class="sk" value="${esc(s.skill)}" ${locked ? "disabled" : ""}></label>
      <label>Exact evidence from the posting <input class="ev" value="${esc(s.evidence)}" ${locked ? "disabled" : ""}></label>
      <label>Confidence <select class="cf" ${locked ? "disabled" : ""}>${["", "high", "medium", "low"].map((c) => `<option ${s.confidence === c ? "selected" : ""}>${c}</option>`).join("")}</select></label>
      ${locked ? "<span></span>" : '<button class="danger rm" type="button">Remove</button>'}
      <label class="notes">Notes (optional) <input class="nt" value="${esc(s.notes)}" ${locked ? "disabled" : ""}></label>
      <div class="ev-state"></div></div>`;
  f.innerHTML = `${listNav("p3", p3Filtered())}<h2>Posting #${esc(it.n)} — ${locked ? "submitted (locked)" : amending ? "amendment (new version)" : "your annotation"}</h2>
    <p class="muted">${locked ? "This is your submitted annotation. Compare it with gold, or start an amendment (a new version; the original is kept)." :
      "List every skill the posting asks for, one per row, with the exact phrase that supports it. Nothing is pre-filled."}</p>
    <div class="skill-rows" id="p3-rows">${(cur.skills || []).map(row).join("") || (locked ? "<p class='muted'>No skills submitted.</p>" : row())}</div>
    ${locked ? "" : '<div class="row"><button class="ghost" id="p3-add" type="button">+ Add skill</button></div>'}
    <div class="gv-form">
      <label>Overall confidence <select id="p3-conf" ${locked ? "disabled" : ""}>${["", "high", "medium", "low"].map((c) => `<option ${cur.overall_confidence === c ? "selected" : ""}>${c}</option>`).join("")}</select></label>
      <label>Notes <textarea id="p3-notes" ${locked ? "disabled" : ""}>${esc(cur.notes)}</textarea></label>
      ${amending ? '<label>Amendment reason (required) <input id="p3-amend"></label>' : ""}
      <div class="row">${locked ? '<button id="p3-compare">Compare with gold</button><button class="ghost" id="p3-start-amend">Start amendment</button>'
        : amending ? '<button id="p3-amend-btn">Submit amendment</button><button class="ghost" id="p3-cancel">Cancel</button>'
        : '<button class="ghost" id="p3-draft">Save draft</button><button id="p3-submit">Submit annotation (locks it)</button>'}</div>
      <div id="p3-cmp"></div>
    </div>${versionsHtml(it.versions)}`;
  wireNav(f, p3Filtered(), (x) => openP3(x));
  const check = () => f.querySelectorAll(".skill-row").forEach((r) => {
    const ev = r.querySelector(".ev").value.trim(), st = r.querySelector(".ev-state");
    if (!ev) { st.className = "ev-state"; st.textContent = ""; r.classList.remove("bad"); return; }
    if (p3Text == null) { st.className = "ev-state no"; st.textContent = "posting text missing on this machine: evidence cannot be checked"; return; }
    const ok = !!findAt(p3Text, ev);
    st.className = `ev-state ${ok ? "ok" : "no"}`; st.textContent = ok ? "✓ evidence found in the posting" : "✗ evidence not found in the posting";
    r.classList.toggle("bad", !ok);
  });
  const wire = () => {
    f.querySelectorAll(".rm").forEach((b) => (b.onclick = () => { b.closest(".skill-row").remove(); }));
    f.querySelectorAll(".ev").forEach((i) => (i.oninput = check));
  };
  wire(); check();
  $("#p3-add")?.addEventListener("click", () => { $("#p3-rows").insertAdjacentHTML("beforeend", row()); wire(); });
  const data = () => ({ skills: [...f.querySelectorAll(".skill-row")].map((r) => ({ skill: r.querySelector(".sk").value,
    evidence: r.querySelector(".ev").value, confidence: r.querySelector(".cf").value, notes: r.querySelector(".nt").value })),
    overall_confidence: $("#p3-conf").value, notes: $("#p3-notes").value });
  $("#p3-draft")?.addEventListener("click", async () => { if (await send(3, it, "draft", data())) loadP3(); });
  $("#p3-submit")?.addEventListener("click", async () => {
    if (!confirm("Submit and lock this annotation? Later changes become a new version.")) return;
    if (await send(3, it, "submit", data())) loadP3();
  });
  $("#p3-start-amend")?.addEventListener("click", () => openP3(id, true));
  $("#p3-cancel")?.addEventListener("click", () => openP3(id));
  $("#p3-amend-btn")?.addEventListener("click", async () => { if (await send(3, it, "amend", data(), $("#p3-amend").value)) loadP3(); });
  $("#p3-compare")?.addEventListener("click", async () => {
    if (!confirm("After you see the answer, later amendments are kept for the record but do not change your scored result. Continue?")) return;
    try {
      const d = await api(`/api/validation/compare?item=${encodeURIComponent(it.item_id)}&reviewer=${encodeURIComponent(reviewer())}`);
      const label = { match: "match", naming_difference: "naming difference", gold_only: "gold-only (candidate unsupported gold label)",
        reviewer_only: "reviewer-only (candidate omission; the model found it)", shared_omission: "possible shared omission (gold and model both missed it)" };
      $("#p3-cmp").innerHTML = `<h3>Comparison with existing gold (latest version)</h3>
        <p class="muted">Candidates only — nothing is a confirmed gold error until adjudication approves it.</p>
        <div class="table-wrap small"><table><thead><tr><th>Result</th><th>Yours</th><th>Gold</th></tr></thead><tbody>${
        d.rows.map((r) => `<tr><td class="k-${r.kind}">${esc(label[r.kind])}${r.ambiguous ? " · ambiguous" : ""}</td><td>${esc(r.reviewer_label || "—")}</td><td>${esc(r.gold_label || "—")}</td></tr>`).join("")}</tbody></table></div>`;
    } catch (e) { say(e.message, "error"); }
  });
}

// ---------- adjudication ----------
["#adj-status", "#adj-part", "#adj-conflict"].forEach((s) => $(s).addEventListener("input", renderCases));
async function loadCases() { S.cases = await api(`/api/validation/cases?reviewer=${encodeURIComponent(reviewer())}`); renderCases(); }
const fmtChange = (c) => !c ? "no change" : c.action === "add" ? `add “${c.to_label}”` : c.action === "remove" ? `remove “${c.from_label}”` : `“${c.from_label}” → “${c.to_label}”`;
function renderCases() {
  const st = $("#adj-status").value, part = $("#adj-part").value, conf = $("#adj-conflict").checked;
  const rows = S.cases.filter((c) => (!st || c.status === st) && (!part || String(c.part) === part) && (!conf || c.conflict));
  $("#adj-count").textContent = `${rows.length} of ${S.cases.length} cases`;
  $("#adj-rows").innerHTML = rows.map((c) => c.redacted
    ? `<tr><td>${c.part}</td><td colspan="4" class="redacted">hidden until you submit your own review of this item (keeps your review blind)</td><td>${REV(c.status)}</td></tr>`
    : `<tr data-id="${c.case_id}" class="${c.case_id === S.sel.adj ? "sel" : ""}"><td>${c.part}</td><td>${esc(c.n)}</td><td>${esc(c.label)}</td>
      <td>${c.reviews.length}${c.conflict ? " · conflict" : ""}</td><td>${c.proposed_changes.map((x) => esc(fmtChange(x))).join("<br>") || "—"}</td><td>${REV(c.status)}</td></tr>`).join("")
    || '<tr><td colspan="6" class="muted">No cases yet: cases appear when reviews propose a change, are unsure, or disagree.</td></tr>';
  document.querySelectorAll("#adj-rows tr[data-id]").forEach((tr) => tr.addEventListener("click", () => openCase(tr.dataset.id)));
}
function openCase(id) {
  S.sel.adj = id; renderCases();
  const c = S.cases.find((x) => x.case_id === id); if (!c) return;
  const d = $("#adj-detail"); d.classList.remove("empty-state");
  const opts = c.proposed_changes;
  d.innerHTML = `<h2>${esc(c.label)} <span class="muted">part ${c.part} · #${esc(c.n)} · ${esc(c.posting_id)}</span></h2>
    <p>Status: ${REV(c.status)}${c.conflict ? ' · <span class="st-NEEDS_DISCUSSION">reviewers disagree</span>' : ""}</p>
    <h3>Submitted reviews</h3><ul class="history">${c.reviews.map((r) => `<li><b>${esc(r.reviewer)}</b> v${r.version}: ${esc(r.decision || r.kind)}
      → ${esc(fmtChange(r.change))}${r.rule ? ` · rule: ${esc(r.rule)}` : ""}${r.reason ? ` · “${esc(r.reason)}”` : ""}${r.evidence ? ` · evidence: “${esc(r.evidence)}”` : ""}</li>`).join("")}</ul>
    <h3>Decision</h3><div class="gv-form">
      ${opts.length ? `<div class="gv-choices">${opts.map((o, i) => `<label><input type="radio" name="adjc" value="${i}" ${i === 0 ? "checked" : ""}> ${esc(fmtChange(o))}</label>`).join("")}</div>` : '<p class="muted">No change was proposed (unsure or conflicting reviews).</p>'}
      <label>Final label (for add / revise; edit if needed) <input id="adj-label" value="${esc(opts[0]?.to_label || "")}"></label>
      <label>Rationale (required) <textarea id="adj-rat"></textarea></label>
      <div class="row"><button id="adj-ok">Approve</button><button class="danger" id="adj-no">Reject</button>
        <button class="ghost" id="adj-talk">Needs discussion</button></div></div>
    <h3>History</h3><ul class="history">${c.history.map((h) => `<li>${esc(h.ts)} · ${esc(h.adjudicator)}: ${esc(h.decision)} — ${esc(h.rationale)}${h.change ? ` (${esc(fmtChange(h.change))})` : ""}</li>`).join("") || "<li>none</li>"}</ul>`;
  d.querySelectorAll("input[name=adjc]").forEach((r) => r.addEventListener("change", () => { $("#adj-label").value = opts[+r.value].to_label || ""; }));
  const go = async (decision) => {
    const r = reviewer(); if (!r) return;
    const pick = opts[+(d.querySelector("input[name=adjc]:checked")?.value ?? -1)];
    const change = decision === "APPROVED" && pick ? { ...pick, to_label: pick.action === "remove" ? null : $("#adj-label").value } : null;
    try {
      await api("/api/validation/adjudicate", { adjudicator: r, case_id: c.case_id, decision, rationale: $("#adj-rat").value, change });
      say(`Recorded: ${decision} (gold files are not changed by this)`); await loadCases(); openCase(id);
    } catch (e) { say(`Not saved: ${e.message}`, "error"); }
  };
  $("#adj-ok").addEventListener("click", () => go("APPROVED"));
  $("#adj-no").addEventListener("click", () => go("REJECTED"));
  $("#adj-talk").addEventListener("click", () => go("NEEDS_DISCUSSION"));
}

// ---------- progress ----------
function table(title, obj) {
  return `<div class="detail"><h3>${esc(title)}</h3><table><tbody>${Object.entries(obj).filter(([, v]) => typeof v !== "object" || v === null)
    .map(([k, v]) => `<tr><td>${esc(k.replace(/_/g, " "))}</td><td>${esc(v)}</td></tr>`).join("")}</tbody></table></div>`;
}
function renderProgress() {
  const s = S.status.summary;
  if (!s || !s.parts) { $("#progress-body").innerHTML = `<div class="warnbox">${esc(s?.error || "No data")}</div>`; return; }
  const names = { 1: "Part 1 — Disagreements", 2: "Part 2 — Agreements (blind)", 3: "Part 3 — Full postings" };
  const team = s.team;
  $("#progress-body").innerHTML = `<div class="metrics">${Object.entries(s.parts).map(([p, v]) => table(names[p], v)).join("")}
    ${table("Team", team)}</div><h3>Reviewer completion (submitted / total)</h3>
    <div class="table-wrap small"><table><thead><tr><th>Reviewer</th><th>Part 1</th><th>Part 2</th><th>Part 3</th></tr></thead><tbody>${
    Object.entries(team.per_reviewer).map(([r, ps]) => `<tr><td>${esc(r)}</td>${[1, 2, 3].map((p) => ps[p] ? `<td>${ps[p].submitted}/${ps[p].total}${ps[p].drafts ? ` · ${ps[p].drafts} draft` : ""}</td>` : "<td>—</td>").join("")}</tr>`).join("")}</tbody></table></div>`;
}
$("#export-btn").addEventListener("click", async () => {
  try { const d = await api("/api/validation/export", {}); say(`Report written: ${d.files.join(", ")}`); } catch (e) { say(e.message, "error"); }
});

// ---------- sources ----------
function renderSources() {
  $("#art-rows").innerHTML = S.status.artifacts.map((a) => `<tr><td>${esc(a.name)}</td><td><code>${esc(a.path)}</code></td>
    <td>${a.exists ? '<span class="badge b-ok">present</span>' : '<span class="badge b-warn">missing</span>'}</td><td>${esc(a.source)}</td></tr>`).join("");
  $("#man-body").innerHTML = S.status.manifests.map((m) => !m.manifest_id ? `<div class="warnbox">Part ${m.part}: not built yet.</div>` :
    `<details class="detail"><summary><b>Part ${m.part}</b> · ${esc(m.manifest_id)} · ${m.items} items · built ${esc(m.created_utc)}
      ${m.stale_sources.length ? '<span class="badge b-warn">sources changed</span>' : '<span class="badge b-ok">sources unchanged</span>'}</summary>
      <dl class="kv"><dt>Rules</dt><dd><code>${esc(m.rules.file)}</code> ${esc((m.rules.sha256 || "").slice(0, 12))}</dd>
      <dt>Settings</dt><dd><code>${esc(JSON.stringify(m.settings))}</code></dd>
      ${Object.entries(m.sources).map(([k, v]) => `<dt>${esc(k)}</dt><dd><code>${esc((v || "missing").slice(0, 16))}</code>${m.stale_sources.includes(k) ? " ⚠ changed" : ""}</dd>`).join("")}</dl>
      <pre class="posting-text">${esc(JSON.stringify(m.population, null, 1))}</pre></details>`).join("");
}
$("#build-btn").addEventListener("click", async () => {
  try {
    const d = await api("/api/validation/build", {});
    await refresh();
    say(Object.keys(d).length ? `Built: ${Object.values(d).map((x) => x.manifest_id).join(", ")}` : "All samples already exist (never replaced).");
  } catch (e) { say(e.message, "error"); }
});

refresh();
