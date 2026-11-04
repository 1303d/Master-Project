"""Sprint 4 step 3b: offline topic-VALIDITY review (is a topic a real competency concept?), separate from naming.

    python src/topic_validity.py review --pilot-run <naming_run_id>             # write a new validity folder
    python src/topic_validity.py review --pilot-run <naming_run_id> --no-write  # print only

Reads only: the frozen Sprint 4 snapshot + topic features (hash-checked), the prepared naming evidence, and one
finished naming run (its manifest hashes are checked; nothing in it is changed). No API call, no database, no change
to memberships or clustering. Output: data/processed/sprint4_naming_<run>/validity_v1_<naming_run_id>/ (private:
it lists member skills) + a tracked summary in reports/sprint4_naming/<run>/validity_v1_<naming_run_id>/.

Three SEPARATE fields per topic (never merged into one score):
  llm_confidence   the naming model's own rating (from the naming run; pilot topics only)
  cohesion_band    embedding cohesion of the topic (low <= q25 < medium < q75 <= high of cos_mean)
  validity_auto    rule-based classification from the members' strings, reference links and cluster shape:
     (head_word_share = share of members containing the most common word stem, stem = first 5 letters)
     surface_form_cluster  members share string FORM, not meaning: no shared word (head_word_share < 0.30) and
                           mostly acronym-like (>= 0.50), mostly containing digits (>= 0.50) or mostly the same first
                           character (>= 0.60). Small embedding models place short strings by their characters.
     mixed                 real phrases but more than one competency: no shared word and low cohesion, or more weak
                           (noise) members attached than assigned members while cohesion is not high.
     insufficient_evidence no sign of a problem, but nothing confirms the topic either: no shared word and reference
                           coverage < 0.10, or fewer than 10 assigned members.
     coherent              none of the above. This is the default only after the checks above, never because the LLM
                           returned a valid name.
  The LLM output is NOT used to decide validity_auto. Thresholds are heuristics set on 2026-11-03 after reading the
  pilot (see the review report); they flag topics for review, they do not change any membership.
validity_review    a human / reviewer classification where one exists (config/topic_validity/<review>.json); it
                   overrides validity_auto for hierarchy treatment and records the root causes.
hierarchy_treatment coherent -> eligible; mixed -> hold_split_candidate; surface_form_cluster -> exclude_until_reclustered;
                   insufficient_evidence -> hold_unverified. check_rows() refuses any non-coherent topic marked eligible.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import freeze_sprint4_input as fz  # noqa: E402
import topic_naming as tn  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = fz.RUN_ID
SCHEMA_VERSION = "sprint4_validity/1"
VALIDITY = ("coherent", "mixed", "surface_form_cluster", "insufficient_evidence")
ROOT_CAUSES = ("extraction_noise", "embedding_similarity", "clustering_behavior", "naming_prompt_limitation",
               "insufficient_reference_evidence")
TREATMENT = {"coherent": "eligible", "mixed": "hold_split_candidate",
             "surface_form_cluster": "exclude_until_reclustered", "insufficient_evidence": "hold_unverified"}
HEAD_WORD_MIN, ACRONYM_MIN, DIGIT_MIN, INITIAL_MIN = 0.30, 0.50, 0.50, 0.60
LOW_REF, MIN_ASSIGNED, ACRONYM_MAX_LEN, VOCAB_MIN_COUNT = 0.10, 10, 5, 2
STOPWORDS = {"and", "the", "for", "with", "of", "to", "in", "on", "management", "skills", "systems", "system"}
COLS = ["topic_id", "in_pilot", "provisional_name", "llm_confidence", "cohesion_band", "cos_mean", "cos_mean_pct",
        "n_assigned", "n_weak", "coverage_any", "head_word", "head_word_share", "acronym_share", "digit_share",
        "initial_char", "initial_share", "validity_auto", "validity_auto_reason", "validity_review", "root_causes",
        "validity_final", "validity_source", "hierarchy_treatment", "review_required", "review_reason"]
REVIEW_PATH = ROOT / "config" / "topic_validity" / "pilot_review_v1.json"


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()


def out_dirs(root, run_id, naming_run_id):
    name = f"validity_v1_{naming_run_id}"
    return tn.naming_dir(root, run_id) / name, tn.tracked_dir(root, run_id) / name


# ---------- string-form signals ----------
def words(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def build_vocab(skill_keys):
    """Words that occur inside multi-word skill phrases (a cheap stand-in for 'is a normal word')."""
    c = Counter(w for k in skill_keys if len(k.split()) > 1 for w in words(k))
    return {w for w, n in c.items() if n >= VOCAB_MIN_COUNT}


def acronym_like(skill, vocab):
    """One token, and either containing a digit or at most ACRONYM_MAX_LEN letters and not a known word."""
    if len(skill.split()) != 1:
        return False
    core = re.sub(r"[^a-z0-9]", "", skill.lower())
    return bool(core) and (any(ch.isdigit() for ch in core) or (len(core) <= ACRONYM_MAX_LEN and core not in vocab))


def stem(w):
    """Crude stem: the first 5 letters, so purchasing / purchase / purchases or machine / machinery count as one word."""
    return w[:5] if len(w) > 5 else w


def form_signals(members, vocab):
    n = len(members)
    heads = Counter(stem(w) for m in members for w in {stem(x) for x in words(m) if len(x) >= 3 and x not in STOPWORDS})
    head, head_n = heads.most_common(1)[0] if heads else ("", 0)
    inits = Counter(next((ch for ch in m.lower() if ch.isalnum()), "") for m in members)
    init, init_n = inits.most_common(1)[0]
    return {"head_word": head, "head_word_share": head_n / n, "acronym_share": sum(acronym_like(m, vocab) for m in members) / n,
            "digit_share": sum(any(ch.isdigit() for ch in m) for m in members) / n,
            "initial_char": init, "initial_share": init_n / n}


def classify(s):
    """(validity_auto, reason) from data signals only (never from the LLM)."""
    no_head = s["head_word_share"] < HEAD_WORD_MIN
    if no_head:
        hits = [f"{k} {s[k]:.2f} >= {t}" for k, t in (("acronym_share", ACRONYM_MIN), ("digit_share", DIGIT_MIN),
                                                      ("initial_share", INITIAL_MIN)) if s[k] >= t]
        if hits:
            return "surface_form_cluster", f"no shared word (head_word_share {s['head_word_share']:.2f}); " + "; ".join(hits)
    if no_head and s["cohesion_band"] == "low":
        return "mixed", f"no shared word (head_word_share {s['head_word_share']:.2f}) and low cohesion"
    if s["n_weak"] > s["n_assigned"] and s["cohesion_band"] != "high":
        return "mixed", f"more weak members ({s['n_weak']}) than assigned ({s['n_assigned']}) and cohesion {s['cohesion_band']}"
    if s["n_assigned"] < MIN_ASSIGNED:
        return "insufficient_evidence", f"only {s['n_assigned']} assigned members"
    if no_head and s["coverage_any"] < LOW_REF:
        return "insufficient_evidence", (f"no shared word (head_word_share {s['head_word_share']:.2f}) and reference "
                                         f"coverage {s['coverage_any']:.2f} < {LOW_REF}")
    return "coherent", "no surface-form, mixing or evidence problem detected"


# ---------- reviewer classifications ----------
def load_review(path):
    """Reviewer classifications: {topic_id: {...}}; validated, or ValueError."""
    path = Path(path)
    if not path.is_file():
        return {}, None
    raw = path.read_bytes()
    d = json.loads(raw)
    probs, out = [], {}
    for t, r in d.get("topics", {}).items():
        if r.get("validity") not in VALIDITY:
            probs.append(f"{t}: validity {r.get('validity')!r} not in {VALIDITY}")
        bad = [c for c in r.get("root_causes", []) if c not in ROOT_CAUSES]
        if bad or not r.get("root_causes"):
            probs.append(f"{t}: root_causes must be a non-empty subset of {ROOT_CAUSES} (bad: {bad})")
        if not r.get("evidence"):
            probs.append(f"{t}: evidence missing")
        out[t] = r
    if not d.get("reviewer") or not d.get("status"):
        probs.append("reviewer and status are required")
    if probs:
        raise ValueError("review file invalid: " + "; ".join(probs))
    return out, {"path": path, "sha256": sha(raw), "reviewer": d["reviewer"], "status": d["status"],
                 "reviewed_utc": d.get("reviewed_utc")}


# ---------- build ----------
def load_pilot(root, run_id, naming_run_id):
    d = tn.naming_dir(root, run_id) / naming_run_id
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    bad = [f for f, h in m["files_sha256"].items() if not (d / f).is_file() or sha((d / f).read_bytes()) != h]
    if bad:
        raise SystemExit(f"naming run {naming_run_id} changed since it was written: {bad}")
    rows = [json.loads(x) for x in (d / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    return m, {r["topic_id"]: r for r in rows}, {f: m["files_sha256"][f] for f in sorted(m["files_sha256"])}


def build(root=ROOT, run_id=RUN_ID, naming_run_id=None, expected=fz.EXPECTED, review_path=None):
    inp = tn.load_inputs(root, run_id, expected)                        # hash-checks snapshot + features
    if tn.verify(root, run_id):
        raise SystemExit("prepare folder failed verification")
    pm, pilot, pilot_hashes = load_pilot(root, run_id, naming_run_id)
    ev = tn.build_evidence(inp)
    band = {r["topic_id"]: r["payload"]["cohesion_band"] for r in ev["records"]}
    members = {}
    for m in inp["snap"]["memberships"]:
        if m["state"] == "assigned":
            members.setdefault(m["topic_id"], []).append(m["skill_key"])
    vocab = build_vocab([s["skill_key"] for s in inp["snap"]["skills"]])
    review, review_meta = load_review(review_path or Path(root) / "config" / "topic_validity" / "pilot_review_v1.json")
    cos_all = np.array([float(inp["features"][t]["cos_mean"]) for t in inp["topic_ids"]])
    rows = []
    for t in inp["topic_ids"]:
        f, rf = inp["features"][t], inp["references"][t]
        s = {**form_signals(sorted(members[t]), vocab), "cohesion_band": band[t], "n_assigned": int(f["n_assigned"]),
             "n_weak": int(f["n_weak"]), "coverage_any": float(rf["coverage_any"])}
        auto, why = classify(s)
        p, rv = pilot.get(t), review.get(t)
        final, src = (rv["validity"], "review") if rv else (auto, "auto")
        reasons = []
        if final != "coherent":
            reasons.append(f"validity {final}")
        if p and p.get("llm_confidence") == "low":
            reasons.append("llm_confidence_low")
        if band[t] == "low":
            reasons.append("cohesion_low")
        if rv and rv["validity"] != auto:
            reasons.append(f"review differs from auto ({auto})")
        rows.append({"topic_id": t, "in_pilot": t in pilot, "provisional_name": p["provisional_name"] if p else "",
                     "llm_confidence": p["llm_confidence"] if p else "", "cohesion_band": band[t],
                     "cos_mean": float(f["cos_mean"]), "cos_mean_pct": float((cos_all < float(f["cos_mean"])).mean() * 100),
                     **{k: s[k] for k in ("n_assigned", "n_weak", "coverage_any", "head_word", "head_word_share",
                                          "acronym_share", "digit_share", "initial_char", "initial_share")},
                     "validity_auto": auto, "validity_auto_reason": why,
                     "validity_review": rv["validity"] if rv else "", "root_causes": rv["root_causes"] if rv else [],
                     "validity_final": final, "validity_source": src, "hierarchy_treatment": TREATMENT[final],
                     "review_required": bool(reasons), "review_reason": ";".join(reasons)})
    unknown = sorted(set(review) - set(inp["topic_ids"]))
    if unknown:
        raise ValueError(f"review file names unknown topics: {unknown}")
    return {"rows": rows, "review": review, "review_meta": review_meta, "pilot_manifest": pm, "pilot_hashes": pilot_hashes,
            "inputs": {"snapshot": inp["snap"]["manifest"]["data_fingerprint"],
                       "features": inp["features_manifest"]["data_fingerprint"]},
            "members": {t: sorted(v) for t, v in members.items()}, "inp": inp}


def check_rows(rows, expected_ids):
    """Validation: every topic classified once; non-coherent topics are flagged and never hierarchy-eligible."""
    p, ids = [], [r["topic_id"] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(expected_ids):
        p.append("every topic must be classified exactly once")
    for r in rows:
        for k in ("validity_auto", "validity_final"):
            if r[k] not in VALIDITY:
                p.append(f"{r['topic_id']}: {k} {r[k]!r} invalid")
        if r["validity_final"] != "coherent" and (r["hierarchy_treatment"] == "eligible" or not r["review_required"]):
            p.append(f"{r['topic_id']}: {r['validity_final']} topic must be flagged and not hierarchy-eligible")
        if r["hierarchy_treatment"] != TREATMENT.get(r["validity_final"]):
            p.append(f"{r['topic_id']}: treatment does not match validity")
        if r["validity_source"] == "review" and not r["root_causes"]:
            p.append(f"{r['topic_id']}: reviewed topic without root causes")
        if r["validity_auto"] == "coherent" and r["head_word_share"] < HEAD_WORD_MIN and \
                max(r["acronym_share"], r["digit_share"]) >= ACRONYM_MIN:
            p.append(f"{r['topic_id']}: coherent despite surface-form signals")
    return p


# ---------- report ----------
def csv_bytes(rows, cols):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow([";".join(r[c]) if isinstance(r[c], list) else (f"{r[c]:.4f}" if isinstance(r[c], float) else
                    ("true" if r[c] is True else "false" if r[c] is False else r[c])) for c in cols])
    return buf.getvalue().encode("utf-8")


def report_md(res, with_members=True):
    rows, review = res["rows"], res["review"]
    by = {r["topic_id"]: r for r in rows}
    pilot = [r for r in rows if r["in_pilot"]]
    dist = lambda rs, k: dict(sorted(Counter(r[k] for r in rs).items()))
    links = {l["skill_key"]: l for l in res["inp"]["snap"]["links"]}
    L = ["# Topic validity review — Sprint 4 pilot", "",
         f"Naming run `{res['pilot_manifest']['run_id']}` (unchanged; hashes checked). Clustering run `{RUN_ID}`. "
         "No API call; memberships and clustering unchanged.", "",
         "Three separate fields: **llm_confidence** (naming model), **cohesion_band** (embedding), **validity** (is the "
         "topic one competency concept?). Validity is decided from member strings, reference links and cluster shape, "
         "never from the LLM's answer.", "",
         f"Reviewer classifications: {res['review_meta']['reviewer']} — status **{res['review_meta']['status']}**."
         if res["review_meta"] else "No reviewer classifications.", "",
         "## Distribution", "",
         f"- Pilot (24): auto {dist(pilot, 'validity_auto')}; final {dist(pilot, 'validity_final')}",
         f"- All {len(rows)} topics (auto rules only, no LLM): {dist(rows, 'validity_auto')}",
         f"- Hierarchy treatment, all topics: {dist(rows, 'hierarchy_treatment')}", "",
         "## Pilot topics", "",
         "| Topic | Name | LLM conf. | Cohesion | Validity (auto) | Validity (final) | Treatment |",
         "|---|---|---|---|---|---|---|"]
    for r in pilot:
        L.append(f"| {r['topic_id']} | {r['provisional_name']} | {r['llm_confidence']} | {r['cohesion_band']} "
                 f"(p{r['cos_mean_pct']:.0f}) | {r['validity_auto']} | **{r['validity_final']}** | {r['hierarchy_treatment']} |")
    L += ["", "## Six-topic evidence", "",
          "| Topic | Assigned / weak | Cohesion (pct) | Ref. coverage | Head word (share) | Acronym | Digits | Initial (share) | Auto | Proposed | Root causes |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in sorted(review):
        r = by[t]
        L.append(f"| {t} | {r['n_assigned']} / {r['n_weak']} | {r['cos_mean']:.3f} (p{r['cos_mean_pct']:.0f}) | "
                 f"{r['coverage_any']:.2f} | {r['head_word'] or '—'} ({r['head_word_share']:.2f}) | {r['acronym_share']:.2f} | "
                 f"{r['digit_share']:.2f} | {r['initial_char']} ({r['initial_share']:.2f}) | {r['validity_auto']} | "
                 f"**{r['validity_review']}** | {', '.join(r['root_causes'])} |")
    for t in sorted(review):
        r, rv = by[t], review[t]
        L += ["", f"### {t} — \"{r['provisional_name']}\" → **{rv['validity']}**", "",
              f"- Auto rule: `{r['validity_auto']}` ({r['validity_auto_reason']})",
              f"- LLM confidence `{r['llm_confidence']}` · cohesion `{r['cohesion_band']}` (cos_mean {r['cos_mean']:.3f}, "
              f"percentile {r['cos_mean_pct']:.0f}) · reference coverage {r['coverage_any']:.2f}",
              f"- Root causes: {', '.join(rv['root_causes'])}"]
        L += [f"- {e}" for e in rv["evidence"]]
        if rv.get("subthemes"):
            L.append("- Sub-themes seen: " + "; ".join(f"**{k}**: {', '.join(v)}" for k, v in rv["subthemes"].items()))
        L.append(f"- Hierarchy treatment: `{TREATMENT[rv['validity']]}` — {rv.get('treatment_note', '')}")
        if with_members:
            ms = []
            for m in res["members"][t]:
                l = links.get(m)
                ms.append(f"{m}" + (f" [→ {l['ref_label']}]" if l and l["verdict"] == "known_skill" else ""))
            L.append(f"- All assigned members ({len(ms)}): " + "; ".join(ms))
    L += ["", "## Recommended treatment in Sprint 4 hierarchy construction", "",
          "1. Only `validity_final = coherent` topics become concept nodes (`eligible`). The hierarchy builder must read "
          "this field and refuse others unless a human overrides it (recorded).",
          "2. `surface_form_cluster` → `exclude_until_reclustered`: keep the topic ID and members, attach nothing to it, "
          "mark its members `unresolved`. Fix upstream in the next clustering run (expand acronyms through the alias "
          "sheet before embedding; embed with context, e.g. the posting sentence; require a minimum word overlap or "
          "character-similarity guard).",
          "3. `mixed` → `hold_split_candidate`: not a node as-is; a reviewer lists sub-themes (see above) for a later "
          "constrained re-clustering. Do not hand-edit memberships in this run.",
          "4. `insufficient_evidence` → `hold_unverified`: may become a leaf only after a human confirms the meaning.",
          "5. Names of non-coherent topics stay provisional and must not be shown as taxonomy concepts in the demo.",
          "", "## Method limits", "",
          "- Thresholds are heuristics chosen after reading the pilot; they flag topics, they do not prove validity.",
          "- Polysemy (one word, several meanings, e.g. T0274 'coding') is not detectable from string form; it is caught "
          "only indirectly (weak members) or by review.",
          "- Auto `mixed` is a review candidate, not a verdict: topics whose members are instances without a shared word "
          "(e.g. languages: arabic, bengali, cantonese) also trigger 'no shared word + low cohesion', and the weak-member "
          "rule can hold a coherent topic (pilot T0277 'Industrial Machinery Operation' looks coherent). Holding a "
          "coherent topic is the safe error; a reviewer can override it in the review file.",
          "- Auto `surface_form_cluster` looked right on all 24 topics it flagged (all are acronym / code clusters), but "
          "it was only spot-checked by reading labels and first members.",
          "- Reviewer classifications are proposals until a human confirms them (`status` in the review file).", ""]
    return "\n".join(L) + "\n"


def write(res, root, run_id, naming_run_id):
    d, td = out_dirs(root, run_id, naming_run_id)
    if d.exists() or td.exists():
        raise FileExistsError(f"{d.name} exists; never overwritten")
    pilot = [r for r in res["rows"] if r["in_pilot"]]
    files = {"topic_validity_all.csv": csv_bytes(res["rows"], COLS), "pilot_validity.csv": csv_bytes(pilot, COLS),
             "topic_validity_review.md": report_md(res).encode("utf-8")}
    summary = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "naming_run_id": naming_run_id,
               "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "inputs": res["inputs"], "naming_run_files_sha256": res["pilot_hashes"],
               "review": None if not res["review_meta"] else {k: (str(v) if k == "path" else v) for k, v in res["review_meta"].items()},
               "thresholds": {"head_word_min": HEAD_WORD_MIN, "acronym_min": ACRONYM_MIN, "digit_min": DIGIT_MIN,
                              "initial_min": INITIAL_MIN, "low_reference": LOW_REF, "min_assigned": MIN_ASSIGNED},
               "counts": {"pilot_auto": dict(Counter(r["validity_auto"] for r in pilot)),
                          "pilot_final": dict(Counter(r["validity_final"] for r in pilot)),
                          "all_auto": dict(Counter(r["validity_auto"] for r in res["rows"])),
                          "all_treatment": dict(Counter(r["hierarchy_treatment"] for r in res["rows"]))},
               "pilot": [{k: r[k] for k in ("topic_id", "llm_confidence", "cohesion_band", "validity_auto", "validity_final",
                                            "validity_source", "hierarchy_treatment")} for r in pilot],
               "checks": check_rows(res["rows"], [r["topic_id"] for r in res["rows"]]),
               "files_sha256": {n: sha(b) for n, b in sorted(files.items())}}
    d.mkdir(parents=True)
    for n, b in files.items():
        (d / n).write_bytes(b)
    text = json.dumps(summary, indent=1, sort_keys=True) + "\n"
    (d / "validity_summary.json").write_text(text, encoding="utf-8")
    td.mkdir(parents=True)
    (td / "validity_summary.json").write_text(text, encoding="utf-8")   # tracked copy: no member lists
    return d, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["review"])
    ap.add_argument("--pilot-run", required=True, help="naming_run_id of the finished pilot")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    try:
        res = build(naming_run_id=args.pilot_run)
        probs = check_rows(res["rows"], [r["topic_id"] for r in res["rows"]])
        pilot = [r for r in res["rows"] if r["in_pilot"]]
        print(f"topics {len(res['rows'])} | checks {probs or 'OK'}")
        print("pilot auto:", dict(Counter(r["validity_auto"] for r in pilot)), "| final:", dict(Counter(r["validity_final"] for r in pilot)))
        print("all topics auto:", dict(Counter(r["validity_auto"] for r in res["rows"])))
        for r in pilot:
            print(f"  {r['topic_id']} {r['validity_auto']:<22} final={r['validity_final']:<22} llm={r['llm_confidence']:<6} "
                  f"coh={r['cohesion_band']:<6} head={r['head_word']}({r['head_word_share']:.2f}) acr={r['acronym_share']:.2f} "
                  f"dig={r['digit_share']:.2f} init={r['initial_char']}({r['initial_share']:.2f}) | {r['provisional_name']}")
        if probs:
            sys.exit(1)
        if not args.no_write:
            d, _ = write(res, ROOT, RUN_ID, args.pilot_run)
            print(f"written -> {d.relative_to(ROOT)}")
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
