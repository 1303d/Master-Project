// Intrusion v2 blind review. Answers live on the server (responses/<reviewer>.csv); nothing is kept in
// browser storage. "Saved" is shown only after the server has written the file and read the answer back.
const $ = (s) => document.querySelector(s);
const LETTERS = ["A", "B", "C", "D", "E"];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const S = { reviewer: "", questions: [], answers: {}, notes: {}, idx: 0, submitted: false,
            pending: {}, failed: {}, chain: Promise.resolve() };

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
                                   : { cache: "no-store" });
  let d = {};
  try { d = await r.json(); } catch { /* non-JSON error */ }
  if (r.status === 401) { location.href = "/login"; throw new Error("not signed in"); }
  if (!r.ok) throw Object.assign(new Error(d.error || `HTTP ${r.status}`), { locked: !!d.locked });
  return d;
}

function setSave(kind, text) {
  const el = $("#save");
  el.className = `save ${kind}`;
  el.textContent = text;
}

const q = () => S.questions[S.idx];
const answeredCount = () => S.questions.filter((x) => S.answers[x.question_id]).length;
const unsaved = () => Object.keys(S.pending).length + Object.keys(S.failed).length;

function render() {
  const cur = q();
  if (!cur) return;
  const qid = cur.question_id, chosen = S.pending[qid]?.answer ?? S.failed[qid]?.answer ?? S.answers[qid] ?? "";
  $("#qtitle").textContent = `Question ${S.idx + 1} of ${S.questions.length} (${qid})`;
  $("#options").innerHTML = '<legend class="sr">Which skill does not belong?</legend>' + LETTERS.map((L) => `
    <label class="opt ${chosen === L ? "chosen" : ""} ${S.submitted ? "disabled" : ""}">
      <input type="radio" name="opt" value="${L}" ${chosen === L ? "checked" : ""} ${S.submitted ? "disabled" : ""}>
      <span class="letter">${L}</span><span>${esc(cur.options[L])}</span>
    </label>`).join("");
  $("#note").value = S.pending[qid]?.note ?? S.failed[qid]?.note ?? S.notes[qid] ?? "";
  $("#note").disabled = S.submitted;
  $("#saveBtn").disabled = S.submitted || !chosen;
  $("#prev").disabled = S.idx === 0;
  $("#next").disabled = S.idx === S.questions.length - 1;
  $("#locked").hidden = !S.submitted;
  renderSummary();
}

function renderSummary() {
  const n = answeredCount(), total = S.questions.length;
  $("#answered").textContent = n; $("#total").textContent = total;
  $("#meter-fill").style.width = `${total ? (100 * n) / total : 0}%`;
  $("#sum-answered").textContent = n; $("#sum-unanswered").textContent = total - n;
  $("#grid").innerHTML = S.questions.map((x, i) =>
    `<button data-i="${i}" class="${S.answers[x.question_id] ? "done" : ""} ${i === S.idx ? "current" : ""}"
      title="${S.answers[x.question_id] ? "answered" : "not answered"}">${esc(x.question_id)}</button>`).join("");
  const ready = !S.submitted && n === total && !unsaved();
  $("#submitBtn").disabled = !ready;
  $("#submit-hint").textContent = S.submitted ? "Submitted — locked." :
    unsaved() ? "Wait until every answer shows Saved." : n < total ? `Answer all ${total} questions to submit (${total - n} left).` : "Ready to submit.";
}

// Saves run one after another (never two writes racing); each shows Saved only after the server confirms.
function save(qid, answer, note) {
  if (S.submitted || !answer) return;
  S.pending[qid] = { answer, note };
  delete S.failed[qid];
  setSave("saving", "Saving…");
  renderSummary();
  const reviewer = S.reviewer;
  S.chain = S.chain.then(async () => {
    if (reviewer !== S.reviewer) return;  // reviewer switched: drop stale work for the old one
    try {
      const d = await api("/api/intrusion-v2/answer", { reviewer, question_id: qid, answer, note });
      if (d.answer !== answer) throw new Error("server stored a different answer");
      S.answers[qid] = d.answer;
      if (d.note) S.notes[qid] = d.note; else delete S.notes[qid];
      if (S.pending[qid]?.answer === answer && S.pending[qid]?.note === note) delete S.pending[qid];
      setSave(unsaved() ? "saving" : "saved", unsaved() ? "Saving…" : `Saved ${qid}`);
    } catch (e) {
      if (S.pending[qid]?.answer === answer) delete S.pending[qid];
      if (e.locked) { S.submitted = true; setSave("failed", "Locked: already submitted"); }
      else { S.failed[qid] = { answer, note }; setSave("failed", `Save failed (${qid}): ${e.message}. Press Save answer to retry.`); }
    }
    render();
  });
  return S.chain;
}

async function loadReviewer(name) {
  if (unsaved() && !confirm("Some answers are not saved yet. Switch anyway?")) { $("#reviewer").value = S.reviewer; return; }
  Object.assign(S, { reviewer: name, answers: {}, notes: {}, pending: {}, failed: {}, submitted: false });
  $("#start").hidden = !!name; $("#review").hidden = !name; $("#summary").hidden = !name;
  if (!name) return;
  setSave("", "Loading…");
  try {
    const d = await api(`/api/intrusion-v2/responses?reviewer=${encodeURIComponent(name)}`);
    if (S.reviewer !== name) return;
    Object.assign(S, { answers: d.answers, notes: d.notes, submitted: d.submitted });
    const first = S.questions.findIndex((x) => !S.answers[x.question_id]);
    S.idx = first === -1 ? 0 : first;  // resume at the first unanswered question
    setSave(d.submitted ? "saved" : "", d.submitted ? "Submitted" : d.answered ? `Resumed: ${d.answered} saved` : "");
    render();
    loadTeam();
  } catch (e) { setSave("failed", `Could not load your answers: ${e.message}`); }
}

async function loadTeam() {
  try {
    const t = await api("/api/intrusion-v2/team");
    $("#team").textContent = "Submitted so far: " + Object.entries(t.submitted)
      .map(([r, ok]) => `${r[0].toUpperCase() + r.slice(1)} ${ok ? "✓" : "—"}`).join(" · ");
  } catch { $("#team").textContent = ""; }
}

function go(i) { if (i >= 0 && i < S.questions.length) { S.idx = i; render(); } }

$("#options").addEventListener("change", (e) => {
  if (e.target.name === "opt") save(q().question_id, e.target.value, $("#note").value);
});
$("#saveBtn").addEventListener("click", () => {
  const qid = q().question_id, a = $("#options input:checked")?.value;
  if (a) save(qid, a, $("#note").value);
});
$("#note").addEventListener("change", () => {
  const qid = q().question_id, a = $("#options input:checked")?.value;
  if (a && $("#note").value !== (S.notes[qid] ?? "")) save(qid, a, $("#note").value);
});
$("#prev").addEventListener("click", () => go(S.idx - 1));
$("#next").addEventListener("click", () => go(S.idx + 1));
$("#grid").addEventListener("click", (e) => { const b = e.target.closest("button[data-i]"); if (b) go(+b.dataset.i); });
$("#reviewer").addEventListener("change", (e) => loadReviewer(e.target.value));
document.addEventListener("keydown", (e) => {
  if (!S.reviewer || e.target.matches("input[type=text], input:not([type]), select") || e.metaKey || e.ctrlKey) return;
  const k = e.key.toUpperCase();
  if (LETTERS.includes(k) && !S.submitted) { save(q().question_id, k, $("#note").value); render(); }
  else if (e.key === "ArrowLeft") go(S.idx - 1);
  else if (e.key === "ArrowRight") go(S.idx + 1);
});
$("#submitBtn").addEventListener("click", async () => {
  await S.chain;
  if (unsaved()) return alert("Some answers are not saved yet.");
  const n = answeredCount();
  if (!confirm(`Submit your final ${n} answers as ${S.reviewer}?\n\nAfter submitting you cannot change any answer.`)) return;
  try {
    await api("/api/intrusion-v2/submit", { reviewer: S.reviewer, confirm: true });
    S.submitted = true;
    setSave("saved", "Submitted");
    render(); loadTeam();
  } catch (e) { setSave("failed", `Submit failed: ${e.message}`); }
});
window.addEventListener("beforeunload", (e) => { if (unsaved()) { e.preventDefault(); e.returnValue = ""; } });

(async () => {
  try {
    const d = await api("/api/intrusion-v2/questions");
    S.questions = d.questions;
    $("#total").textContent = d.questions.length;
  } catch (e) {
    $("#start").insertAdjacentHTML("beforeend", `<p class="save failed">Could not load questions: ${esc(e.message)}</p>`);
    $("#reviewer").disabled = true;
  }
})();
