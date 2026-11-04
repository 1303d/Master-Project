"""Sprint 4 step 3c: independent, blinded audit of the topic-validity classifier (src/topic_validity.py).

    python src/validity_audit.py make --validity-run validity_v1_<naming_run_id>      # build the audit package
    python src/validity_audit.py evaluate                                            # after a human filled the sheet
    python src/validity_audit.py evaluate --allow-partial                            # progress only, marked PARTIAL

Offline and read-only towards everything that exists: frozen snapshot + features (hash-checked), the validity
outputs (hash-checked against their summary), no API, no database, no membership change, no classifier change.

Sample   population = all topics minus the development topics examined in step 3b (DEV_TOPICS). Strata = the
         classifier's validity_auto. 12 coherent / 12 mixed / 6 surface_form_cluster (insufficient_evidence: none in
         this run). Within a stratum the pool is sorted by (cohesion band, reference coverage, size, weak share,
         topic_id) and drawn by systematic sampling with one seeded random start u in [0, N/n): every topic of the
         stratum has inclusion probability exactly n/N, and the sample spreads over those properties.
Blinding the reviewer files show evidence only (members, representatives, cohesion, size, reference matches with their
         uncertainty, weak members, neighbours). Hidden: automatic validity, its signals, hierarchy treatment,
         generated names, LLM confidence. The automatic predictions sit in sealed/auto_predictions.json (hash in the
         manifest); the evaluator reads them, the reviewer must not. Review order is a seeded shuffle, not by stratum.
Exposure topics whose automatic class was already printed in the 2026-11-03 working session (EXPOSED) are not blind
         for that reader; this is recorded per topic in the sealed file and the evaluation reports them separately.
Evaluate refuses to compute final metrics until every row has a genuine human decision. Sample metrics (confusion
         matrix, agreement, Cohen's kappa) are NOT population estimates because strata were sampled at different
         rates; population estimates weight each stratum by N_h / n_h, with seeded stratified-bootstrap intervals.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import random
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
SCHEMA_VERSION = "validity_audit/1"
AUDIT_NAME = "validity_audit_v1"
SEED = 20261105
DEV_TOPICS = ("T0040", "T0088", "T0103", "T0262", "T0274", "T0374")
PLAN = {"coherent": 12, "mixed": 12, "surface_form_cluster": 6}
VALIDITY = ("coherent", "mixed", "surface_form_cluster", "insufficient_evidence")
PROBLEMS = ("extraction_noise", "embedding_similarity", "clustering_behavior", "insufficient_reference_evidence", "none")
CONFIDENCE = ("high", "medium", "low")
YES_NO = ("yes", "no")
BAND_RANK = {"low": 0, "medium": 1, "high": 2}
N_WEAK_EXAMPLES, N_NEIGHBOURS, BOOTSTRAP = 10, 3, 2000
SHEET_COLS = ["review_order", "topic_id", "human_validity", "supporting_evidence", "suspected_problems",
              "reviewer_confidence", "enter_hierarchy", "notes", "reviewer", "reviewed_utc"]
# Topics whose AUTOMATIC class was printed in the working session of 2026-11-03 (pilot table, the sanity listing of
# all surface_form_cluster topics and the first 12 mixed topics). Not blind for anyone who read that session.
PILOT_TOPICS = ("T0001", "T0019", "T0026", "T0040", "T0053", "T0088", "T0090", "T0103", "T0124", "T0153", "T0168",
                "T0175", "T0252", "T0262", "T0274", "T0275", "T0277", "T0283", "T0303", "T0309", "T0324", "T0336",
                "T0363", "T0374")
LISTED_SURFACE = ("T0088", "T0103", "T0104", "T0121", "T0135", "T0155", "T0177", "T0209", "T0231", "T0234", "T0237",
                  "T0251", "T0253", "T0262", "T0272", "T0273", "T0276", "T0295", "T0305", "T0338", "T0340", "T0371",
                  "T0372", "T0374")
LISTED_MIXED = ("T0003", "T0012", "T0015", "T0018", "T0027", "T0039", "T0040", "T0043", "T0050", "T0057", "T0058", "T0059")
EXPOSED = frozenset(PILOT_TOPICS + LISTED_SURFACE + LISTED_MIXED)
HIDDEN_FIELDS = ("validity", "treatment", "provisional_name", "llm_confidence", "head_word", "acronym_share",
                 "digit_share", "initial_share", "review_required", "stratum")


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()


def audit_dir(root, run_id, validity_run):
    return tn.naming_dir(root, run_id) / f"{AUDIT_NAME}_{validity_run}"


def tracked_audit_dir(root, run_id, validity_run):
    return tn.tracked_dir(root, run_id) / f"{AUDIT_NAME}_{validity_run}"


# ---------- inputs ----------
def load_validity(root, run_id, validity_run):
    """topic_validity_all.csv rows (hash-checked against validity_summary.json)."""
    d = tn.naming_dir(root, run_id) / validity_run
    s = json.loads((d / "validity_summary.json").read_text(encoding="utf-8"))
    bad = [f for f, h in s["files_sha256"].items() if not (d / f).is_file() or sha((d / f).read_bytes()) != h]
    if bad:
        raise SystemExit(f"validity outputs changed since they were written: {bad}")
    rows = list(csv.DictReader((d / "topic_validity_all.csv").open(encoding="utf-8", newline="")))
    for r in rows:
        for k in ("cos_mean", "cos_mean_pct", "coverage_any", "head_word_share", "acronym_share", "digit_share", "initial_share"):
            r[k] = float(r[k])
        for k in ("n_assigned", "n_weak"):
            r[k] = int(r[k])
    return rows, s


# ---------- sampling ----------
def sort_key(r):
    return (BAND_RANK[r["cohesion_band"]], round(r["coverage_any"], 6), r["n_assigned"],
            round(r["n_weak"] / (r["n_weak"] + r["n_assigned"]), 6), r["topic_id"])


def systematic(pool, n, rng):
    """n of the sorted pool by systematic sampling; each element has inclusion probability n / len(pool)."""
    N = len(pool)
    if n > N:
        raise ValueError(f"cannot draw {n} from {N}")
    k = N / n
    u = rng.uniform(0, k)
    idx = [min(N - 1, math.floor(u + i * k)) for i in range(n)]
    if len(set(idx)) != n:
        raise ValueError("systematic sample produced duplicates")
    return [pool[i] for i in idx], u, k


def select_sample(rows, plan=PLAN, dev=DEV_TOPICS, seed=SEED):
    pool = [r for r in rows if r["topic_id"] not in set(dev)]
    rng, chosen, strata = random.Random(seed), [], {}
    for cls, n in plan.items():
        P = sorted((r for r in pool if r["validity_auto"] == cls), key=sort_key)
        picks, u, k = systematic(P, n, rng)
        strata[cls] = {"N": len(P), "n": n, "inclusion_probability": n / len(P), "weight": len(P) / n,
                       "random_start": u, "interval": k, "topics": [r["topic_id"] for r in picks]}
        chosen += [(cls, r) for r in picks]
    other = Counter(r["validity_auto"] for r in pool if r["validity_auto"] not in plan)
    order = [r["topic_id"] for _, r in chosen]
    random.Random(seed + 1).shuffle(order)
    return {"pool_size": len(pool), "unsampled_classes": dict(other), "strata": strata, "review_order": order,
            "chosen": {r["topic_id"]: (cls, r) for cls, r in chosen}}


def diversity(sample):
    rs = [r for _, r in sample["chosen"].values()]
    rng = lambda k: [min(r[k] for r in rs), max(r[k] for r in rs)]
    return {"cohesion_band": dict(Counter(r["cohesion_band"] for r in rs)), "cos_mean": rng("cos_mean"),
            "coverage_any": rng("coverage_any"), "n_assigned": rng("n_assigned"),
            "weak_share": [min(r["n_weak"] / (r["n_weak"] + r["n_assigned"]) for r in rs),
                           max(r["n_weak"] / (r["n_weak"] + r["n_assigned"]) for r in rs)]}


# ---------- blinded evidence ----------
def score_text(link):
    try:
        return f"score {float(link['score']):.2f}"
    except (TypeError, ValueError, KeyError):
        return "no score"


def ref_text(link):
    if not link:
        return "no reference row"
    if link["verdict"] == "known_skill":
        return (f"{link['source']}: \"{link['ref_label']}\" ({link['match']} match, {score_text(link)}; "
                f"{'human-reviewed link' if link['match'] == 'review' else 'automatic match - can be wrong'})")
    if link["verdict"] == "trait":
        return f"trait ({link['source']}: \"{link['ref_label']}\")"
    return (f"no confident match (closest guess \"{link['ref_label']}\", {score_text(link)} - unreliable)"
            if link.get("ref_label") else "no confident match")


def topic_evidence(t, inp, records, stats):
    snap = inp["snap"]
    links = {l["skill_key"]: l for l in snap["links"]}
    mem = [m for m in snap["memberships"] if m["topic_id"] == t]
    assigned = sorted((m for m in mem if m["state"] == "assigned"), key=lambda m: (-float(m["score"]), m["skill_key"]))
    weak = sorted((m for m in mem if m["state"] == "weak"), key=lambda m: (-float(m["score"]), m["skill_key"]))
    f = inp["features"][t]
    p = records[t]["payload"]
    return {"topic_id": t, "n_assigned": len(assigned), "n_weak": len(weak),
            "weak_share": round(len(weak) / max(1, len(weak) + len(assigned)), 3),
            "cohesion": {"cos_mean": round(float(f["cos_mean"]), 3), "cos_min": round(float(f["cos_min"]), 3),
                         "band": p["cohesion_band"], "percentile": round(stats[t], 0)},
            "reference_coverage": round(float(inp["references"][t]["coverage_any"]), 2),
            "representative_skills": p["representative_skills"],
            "assigned_members": [{"skill": m["skill_key"], "cosine_to_centre": round(float(m["score"]), 3),
                                  "reference": ref_text(links.get(m["skill_key"]))} for m in assigned],
            "weak_examples": [m["skill_key"] for m in weak[:N_WEAK_EXAMPLES]],
            "neighbour_topics": [{"topic_id": n["topic_id"], "similarity": n["similarity"], "top_skills": n["top_skills"]}
                                 for n in p["neighbour_topics"][:N_NEIGHBOURS]]}


def blinded_md(evidence, order):
    L = ["# Blinded topic evidence — audit v1", "",
         "Read REVIEW_INSTRUCTIONS.md first. Topics appear in a random order. No names, classifications or model ratings "
         "are shown on purpose.", ""]
    by = {e["topic_id"]: e for e in evidence}
    for i, t in enumerate(order, 1):
        e = by[t]
        c = e["cohesion"]
        L += [f"## {i}. {t}", "",
              f"- Size: {e['n_assigned']} assigned members, {e['n_weak']} weak (loosely attached) members "
              f"(weak share {e['weak_share']:.2f})",
              f"- Cohesion: mean cosine to centre {c['cos_mean']} (min {c['cos_min']}), band {c['band']}, "
              f"percentile {c['percentile']:.0f} of 374 topics",
              f"- Confident ESCO / O*NET coverage: {e['reference_coverage']:.2f} of assigned members",
              f"- Representative skills (closest to centre): {', '.join(e['representative_skills'])}",
              f"- Weak-member examples: {', '.join(e['weak_examples']) or '—'}",
              "- Nearest other topics: " + "; ".join(f"{n['topic_id']} ({n['similarity']}): {', '.join(n['top_skills'])}"
                                                    for n in e["neighbour_topics"]), "",
              "| # | Assigned member | cosine | Reference match (automatic) |", "|---|---|---|---|"]
        L += [f"| {j} | {m['skill']} | {m['cosine_to_centre']} | {m['reference']} |" for j, m in enumerate(e["assigned_members"], 1)]
        L.append("")
    return "\n".join(L) + "\n"


INSTRUCTIONS = """# Validity audit v1 — reviewer instructions

You are checking whether each topic is ONE real competency concept. Work alone; do not discuss topics with other
reviewers until everyone has finished.

## Do not open before you finish
- `sealed/` (automatic predictions) and any `evaluation_*` file.
- Earlier naming or validity outputs (`topic_naming_*`, `validity_v1_*`) and their reports.
If you remember a topic's automatic label from the 2026-11-03 working session, still judge only from the evidence, and
write `seen label before` in notes.

## What to read
`blinded_evidence.md` (or `.jsonl`): per topic, all assigned member skills (sorted by closeness to the centre), the 10
representatives, cohesion, size, weak members, nearest topics, and ESCO / O*NET matches. Reference matches are made
by an automatic linker and can be wrong even when marked "exact" (that is the linker's match type, not identical text;
e.g. "innovative thinking" -> "think creatively"). Only "human-reviewed link" was checked by a person. "No confident
match" says nothing about meaning.

## Classes (`human_validity`)
- `coherent` — most members express one competency (skill, knowledge or tool area); a few outliers are fine.
- `mixed` — members are real skill phrases but cover two or more different competencies (including one word used in
  different senses).
- `surface_form_cluster` — members are grouped by how the strings look (shared letters, acronym shape, digits), not
  by meaning.
- `insufficient_evidence` — you cannot tell what most members mean from the evidence (do not guess).

## Other columns in `reviewer_sheet.csv`
- `supporting_evidence`: 1-2 sentences, cite members.
- `suspected_problems`: any of `extraction_noise; embedding_similarity; clustering_behavior;
  insufficient_reference_evidence` or `none` (separate with `;`).
- `reviewer_confidence`: `high`, `medium`, `low`.
- `enter_hierarchy`: `yes` only if this topic should become a concept node as it is; otherwise `no`.
- `notes`: anything else (e.g. sub-themes, `seen label before`).
- `reviewer`: your name; `reviewed_utc`: date.

Fill every row, save as CSV (same name), then run `python src/validity_audit.py evaluate`.
"""


def csv_bytes(rows, cols):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow([r.get(c, "") for c in cols])
    return buf.getvalue().encode("utf-8")


EVIDENCE_KEYS = {"topic_id", "n_assigned", "n_weak", "weak_share", "cohesion", "reference_coverage", "representative_skills",
                 "assigned_members", "weak_examples", "neighbour_topics", "cos_mean", "cos_min", "band", "percentile",
                 "skill", "cosine_to_centre", "reference", "similarity", "top_skills"}
LEAK_STRINGS = ("surface_form", "insufficient_evidence", "hold_split", "hold_unverified", "exclude_until", "eligible",
                "llm_confidence", "provisional_name", "validity_auto", "head_word", "acronym_share", "initial_share")


def evidence_keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from evidence_keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from evidence_keys(v)


def check_blind(files, evidence, names):
    """Problems if reviewer-facing files reveal classifier outputs, their signals or generated names."""
    p = sorted(set(evidence_keys(evidence)) - EVIDENCE_KEYS)
    skills = {str(v).lower() for e in evidence for v in (e["representative_skills"] + e["weak_examples"]
              + [m["skill"] for m in e["assigned_members"]] + [s for nb in e["neighbour_topics"] for s in nb["top_skills"]])}
    probs = [f"evidence has non-whitelisted keys {p}"] if p else []
    for n, b in files.items():
        low = b.decode("utf-8").lower()
        probs += [f"{n}: contains {w!r}" for w in LEAK_STRINGS if w in low and n != "REVIEW_INSTRUCTIONS.md"]
        rest = low
        for sk in sorted(skills, key=len, reverse=True):                 # names that are only parts of member
            rest = rest.replace(sk, " ")                                 # skill strings are not leaks
        probs += [f"{n}: contains generated name {nm!r}" for nm in names if nm and nm.lower() in rest]
    return probs


def make(root=ROOT, run_id=RUN_ID, validity_run=None, expected=fz.EXPECTED, seed=SEED, plan=PLAN):
    d, td = audit_dir(root, run_id, validity_run), tracked_audit_dir(root, run_id, validity_run)
    if d.exists() or td.exists():
        raise FileExistsError(f"{d.name} exists; never overwritten")
    inp = tn.load_inputs(root, run_id, expected)
    if tn.verify(root, run_id):
        raise SystemExit("prepare folder failed verification")
    rows, vsum = load_validity(root, run_id, validity_run)
    sample = select_sample(rows, plan, DEV_TOPICS, seed)
    records = {r["topic_id"]: r for r in tn.build_evidence(inp)["records"]}
    cos = np.array([float(inp["features"][t]["cos_mean"]) for t in inp["topic_ids"]])
    pct = {t: float((cos < float(inp["features"][t]["cos_mean"])).mean() * 100) for t in inp["topic_ids"]}
    evidence = [topic_evidence(t, inp, records, pct) for t in sample["review_order"]]
    sheet = [{"review_order": i, "topic_id": t} for i, t in enumerate(sample["review_order"], 1)]
    sealed = {"warning": "AUTOMATIC PREDICTIONS - reviewers must not open this file before finishing the review",
              "validity_run": validity_run, "predictions": {
                  t: {"stratum": cls, "validity_auto": r["validity_auto"], "validity_auto_reason": r["validity_auto_reason"],
                      "hierarchy_treatment_auto": tn_treatment(r["validity_auto"]), "in_pilot": r["in_pilot"] == "true",
                      "exposed_in_session_2026_11_03": t in EXPOSED,
                      "signals": {k: r[k] for k in ("head_word_share", "acronym_share", "digit_share", "initial_share",
                                                    "cohesion_band", "coverage_any", "n_assigned", "n_weak")}}
                  for t, (cls, r) in sample["chosen"].items()}}
    files = {"blinded_evidence.md": blinded_md(evidence, sample["review_order"]).encode("utf-8"),
             "blinded_evidence.jsonl": "".join(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n" for e in evidence).encode("utf-8"),
             "reviewer_sheet.csv": csv_bytes(sheet, SHEET_COLS),
             "REVIEW_INSTRUCTIONS.md": INSTRUCTIONS.encode("utf-8")}
    leaks = check_blind(files, evidence, [r["provisional_name"] for r in rows if r["provisional_name"]])
    if leaks:
        raise ValueError(f"reviewer files reveal hidden information: {leaks}")
    sealed_b = (json.dumps(sealed, indent=1, sort_keys=True) + "\n").encode("utf-8")
    manifest = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "validity_run": validity_run,
                "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "inputs": {"snapshot": inp["snap"]["manifest"]["data_fingerprint"],
                           "features": inp["features_manifest"]["data_fingerprint"],
                           "validity_summary_files_sha256": vsum["files_sha256"]},
                "procedure": {"population": f"all topics minus development topics {list(DEV_TOPICS)}",
                              "pool_size": sample["pool_size"], "strata": "validity_auto", "plan": plan,
                              "within_stratum": "sort by (cohesion band, reference coverage, n_assigned, weak share, "
                                                "topic_id); systematic sampling with one random start u ~ U[0, N/n)",
                              "seed": seed, "review_order": "random.Random(seed + 1).shuffle",
                              "unsampled_classes": sample["unsampled_classes"]},
                "strata": {c: {k: v for k, v in s.items() if k != "topics"} for c, s in sample["strata"].items()},
                "topics_sorted": sorted(sample["review_order"]),
                "diversity": diversity(sample),
                "exposure": {"exposed_topics_in_sample": sum(t in EXPOSED for t in sample["review_order"]),
                             "note": "per-topic exposure is in the sealed file; topics whose automatic class was printed "
                                     "in the 2026-11-03 session are not blind for its readers"},
                "sealed_predictions_sha256": sha(sealed_b),
                "files_sha256": {n: sha(b) for n, b in sorted(files.items())},
                "hidden_from_reviewer": list(HIDDEN_FIELDS)}
    d.mkdir(parents=True)
    (d / "sealed").mkdir()
    for n, b in files.items():
        (d / n).write_bytes(b)
    (d / "sealed" / "auto_predictions.json").write_bytes(sealed_b)
    text = json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    (d / "manifest.json").write_text(text, encoding="utf-8")
    td.mkdir(parents=True)
    (td / "manifest.json").write_text(text, encoding="utf-8")
    return d, manifest, sample


def tn_treatment(v):
    return {"coherent": "eligible", "mixed": "hold_split_candidate", "surface_form_cluster": "exclude_until_reclustered",
            "insufficient_evidence": "hold_unverified"}[v]


# ---------- evaluation ----------
def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def read_sheet(path, expected_ids, allow_partial=False):
    rows = list(csv.DictReader(Path(path).open(encoding="utf-8", newline="")))
    probs, done = [], []
    ids = [r["topic_id"] for r in rows]
    if sorted(ids) != sorted(expected_ids):
        probs.append("sheet topic IDs differ from the audit sample")
    for r in rows:
        filled = any((r.get(c) or "").strip() for c in ("human_validity", "reviewer_confidence", "enter_hierarchy"))
        if not filled:
            continue
        p = []
        if r["human_validity"].strip() not in VALIDITY:
            p.append(f"human_validity {r['human_validity']!r}")
        if r["reviewer_confidence"].strip() not in CONFIDENCE:
            p.append(f"reviewer_confidence {r['reviewer_confidence']!r}")
        if r["enter_hierarchy"].strip() not in YES_NO:
            p.append(f"enter_hierarchy {r['enter_hierarchy']!r}")
        sp = [x.strip() for x in (r.get("suspected_problems") or "").split(";") if x.strip()]
        if not sp or any(x not in PROBLEMS for x in sp):
            p.append(f"suspected_problems {r.get('suspected_problems')!r}")
        if not (r.get("reviewer") or "").strip() or (r.get("reviewer") or "").strip().lower() in ("auto", "classifier", "claude"):
            p.append("reviewer must be the human reviewer's name")
        if not (r.get("supporting_evidence") or "").strip():
            p.append("supporting_evidence missing")
        if p:
            probs.append(f"{r['topic_id']}: " + ", ".join(p))
        else:
            done.append({k: (v or "").strip() for k, v in r.items()})
    missing = len(expected_ids) - len(done)
    if missing and not allow_partial:
        probs.append(f"{missing} of {len(expected_ids)} topics have no complete human decision")
    return done, probs


def stratified_bootstrap(labels, strata, stat, B=BOOTSTRAP, seed=SEED):
    """labels: list of (stratum, auto, human). strata: {cls: N}. Returns [2.5%, 97.5%] of stat over resamples."""
    rng = np.random.default_rng(seed)
    by = {}
    for s, a, h in labels:
        by.setdefault(s, []).append((s, a, h))
    vals = []
    for _ in range(B):
        res = []
        for s, items in by.items():
            idx = rng.integers(0, len(items), len(items))
            res += [items[i] for i in idx]
        v = stat(res, strata)
        if v is not None and not math.isnan(v):
            vals.append(v)
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)] if vals else None


def pop_estimates(labels, strata):
    """Weighted population counts N_hat[(auto, human)] with weight N_h / n_h per stratum."""
    n_h = Counter(s for s, _, _ in labels)
    est = Counter()
    for s, a, h in labels:
        est[(a, h)] += strata[s] / n_h[s]
    return est


def pop_agreement(labels, strata):
    est = pop_estimates(labels, strata)
    tot = sum(est.values())
    return sum(v for (a, h), v in est.items() if a == h) / tot if tot else None


def pop_recall(cls):
    def f(labels, strata):
        est = pop_estimates(labels, strata)
        den = sum(v for (a, h), v in est.items() if h == cls)
        return est[(cls, cls)] / den if den else None
    return f


def pop_share(cls):
    def f(labels, strata):
        est = pop_estimates(labels, strata)
        tot = sum(est.values())
        return sum(v for (a, h), v in est.items() if h == cls) / tot if tot else None
    return f


def cohen_kappa(pairs):
    n = len(pairs)
    if not n:
        return None
    po = sum(a == h for a, h in pairs) / n
    ca, ch = Counter(a for a, _ in pairs), Counter(h for _, h in pairs)
    pe = sum(ca[c] * ch[c] for c in VALIDITY) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def evaluate(done, sealed, strata_N, partial=False):
    preds = sealed["predictions"]
    labels = [(preds[r["topic_id"]]["stratum"], preds[r["topic_id"]]["validity_auto"], r["human_validity"]) for r in done]
    pairs = [(a, h) for _, a, h in labels]
    cm = {a: {h: sum(1 for x, y in pairs if x == a and y == h) for h in VALIDITY} for a in VALIDITY}
    per = {}
    for c in VALIDITY:
        k_pred = sum(1 for a, _ in pairs if a == c)
        tp = cm[c][c]
        k_true = sum(1 for _, h in pairs if h == c)
        per[c] = {"auto_predicted_in_sample": k_pred, "human_labelled_in_sample": k_true,
                  "precision": None if not k_pred else round(tp / k_pred, 4), "precision_95ci_wilson": wilson(tp, k_pred),
                  "precision_note": "auto class = stratum, so stratum precision is also the population precision",
                  "recall_sample": None if not k_true else round(tp / k_true, 4),
                  "recall_population_weighted": None if not k_true else round(pop_recall(c)(labels, strata_N) or 0, 4),
                  "recall_population_95ci": None if not k_true else stratified_bootstrap(labels, strata_N, pop_recall(c)),
                  "population_share_by_human": round(pop_share(c)(labels, strata_N) or 0, 4),
                  "population_share_95ci": stratified_bootstrap(labels, strata_N, pop_share(c))}
    wrong = lambda cls: [r["topic_id"] for r in done if preds[r["topic_id"]]["validity_auto"] == cls and r["human_validity"] != cls]
    exposed = [r for r in done if preds[r["topic_id"]]["exposed_in_session_2026_11_03"]]
    blind = [r for r in done if not preds[r["topic_id"]]["exposed_in_session_2026_11_03"]]
    agree = lambda rs: None if not rs else round(sum(preds[r["topic_id"]]["validity_auto"] == r["human_validity"] for r in rs) / len(rs), 4)
    elig = [(preds[r["topic_id"]]["hierarchy_treatment_auto"] == "eligible", r["enter_hierarchy"] == "yes") for r in done]
    return {"status": "PARTIAL - not a validation result" if partial else "complete human review",
            "n_reviewed": len(done), "confusion_matrix_sample": {"rows": "automatic", "columns": "human", "counts": cm},
            "sample_agreement": agree(done), "sample_agreement_95ci_wilson": wilson(sum(a == h for a, h in pairs), len(pairs)),
            "cohen_kappa_sample": None if cohen_kappa(pairs) is None else round(cohen_kappa(pairs), 4),
            "sample_note": "the sample is stratified (12/12/6 from strata of different sizes); sample agreement and kappa "
                           "describe the sample, not the taxonomy",
            "population_agreement_weighted": None if not done else round(pop_agreement(labels, strata_N), 4),
            "population_agreement_95ci": stratified_bootstrap(labels, strata_N, pop_agreement),
            "population_weights": {c: f"N_h / n_h with N_h = {N}" for c, N in strata_N.items()},
            "per_class": per,
            "false_coherent": wrong("coherent"), "false_mixed": wrong("mixed"),
            "false_surface_form": wrong("surface_form_cluster"),
            "missed_by_class": {c: [r["topic_id"] for r in done if r["human_validity"] == c and
                                    preds[r["topic_id"]]["validity_auto"] != c] for c in VALIDITY},
            "hierarchy_gate_agreement": None if not elig else round(sum(a == b for a, b in elig) / len(elig), 4),
            "hierarchy_gate_auto_eligible_but_human_no": sum(a and not b for a, b in elig),
            "agreement_exposed_topics": {"n": len(exposed), "agreement": agree(exposed)},
            "agreement_blind_topics": {"n": len(blind), "agreement": agree(blind)},
            "by_reviewer_confidence": {c: {"n": sum(r["reviewer_confidence"] == c for r in done),
                                           "agreement": agree([r for r in done if r["reviewer_confidence"] == c])} for c in CONFIDENCE},
            "bootstrap": {"replicates": BOOTSTRAP, "seed": SEED, "method": "resample topics within each stratum"},
            "limits": ["one reviewer unless several sheets are combined; no inter-rater agreement",
                       "30 topics: intervals are wide", "insufficient_evidence was not a sampled stratum (no topics)",
                       "exposed topics are not blind for readers of the 2026-11-03 session"]}


def eval_md(e):
    L = [f"# Validity audit evaluation — {e['status']}", "", f"Reviewed topics: {e['n_reviewed']}", "",
         "## Confusion matrix (sample counts; rows = automatic, columns = human)", "",
         "| auto \\ human | " + " | ".join(VALIDITY) + " |", "|---|" + "---|" * len(VALIDITY)]
    for a in VALIDITY:
        L.append(f"| {a} | " + " | ".join(str(e["confusion_matrix_sample"]["counts"][a][h]) for h in VALIDITY) + " |")
    L += ["", f"- Sample agreement {e['sample_agreement']} (Wilson 95% {e['sample_agreement_95ci_wilson']}); Cohen's kappa "
          f"{e['cohen_kappa_sample']} — {e['sample_note']}",
          f"- **Population agreement (weighted) {e['population_agreement_weighted']}** (bootstrap 95% {e['population_agreement_95ci']})",
          f"- Hierarchy gate agreement {e['hierarchy_gate_agreement']}; auto-eligible but human 'no': "
          f"{e['hierarchy_gate_auto_eligible_but_human_no']}",
          f"- Blind topics {e['agreement_blind_topics']}; exposed topics {e['agreement_exposed_topics']}", "",
          "| class | precision (Wilson 95%) | recall, weighted (bootstrap 95%) | population share by human (95%) |",
          "|---|---|---|---|"]
    for c, p in e["per_class"].items():
        L.append(f"| {c} | {p['precision']} {p['precision_95ci_wilson']} | {p['recall_population_weighted']} "
                 f"{p['recall_population_95ci']} | {p['population_share_by_human']} {p['population_share_95ci']} |")
    L += ["", f"- False coherent: {e['false_coherent'] or '—'}", f"- False mixed: {e['false_mixed'] or '—'}",
          f"- False surface-form: {e['false_surface_form'] or '—'}", "", "Limits: " + "; ".join(e["limits"]), ""]
    return "\n".join(L) + "\n"


def run_evaluate(root=ROOT, run_id=RUN_ID, validity_run=None, sheet=None, allow_partial=False):
    d = audit_dir(root, run_id, validity_run)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    sealed_b = (d / "sealed" / "auto_predictions.json").read_bytes()
    if sha(sealed_b) != m["sealed_predictions_sha256"]:
        raise SystemExit("sealed predictions changed since the audit package was made")
    done, probs = read_sheet(sheet or d / "reviewer_sheet.csv", m["topics_sorted"], allow_partial)
    if probs:
        raise SystemExit("reviewer sheet not ready: " + "; ".join(probs[:8]))
    if not done:
        raise SystemExit("no human decisions yet: nothing to evaluate")
    partial = len(done) < len(m["topics_sorted"])
    e = evaluate(done, json.loads(sealed_b), {c: s["N"] for c, s in m["strata"].items()}, partial)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"evaluation_{'PARTIAL_' if partial else ''}{stamp}"
    (d / f"{name}.json").write_text(json.dumps(e, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (d / f"{name}.md").write_text(eval_md(e), encoding="utf-8")
    return d / f"{name}.md", e


# ---------- AI reviewer comparison (not human validation) ----------
AI_LABEL = "AI reviewer comparison — not human validated"
AI_REVIEWER = "claude_ai_reviewer"


def read_ai_sheet(path, expected_ids):
    """A complete AI review sheet (every row by AI_REVIEWER and tagged AI-generated) or problems."""
    rows = list(csv.DictReader(Path(path).open(encoding="utf-8", newline="")))
    probs = [f"{r['topic_id']}: reviewer must be {AI_REVIEWER} and notes must start 'AI-generated'" for r in rows
             if r.get("reviewer") != AI_REVIEWER or not (r.get("notes") or "").startswith("AI-generated")]
    done, p = read_sheet(path, expected_ids)
    return done, probs + p


def exposure_records(done, sealed, ids):
    """Both exposure records side by side; neither is changed. The union is used for the blind-only analysis."""
    original = sorted(t for t, v in sealed["predictions"].items() if v["exposed_in_session_2026_11_03"])
    declared = sorted(r["topic_id"] for r in done if "seen label before" in (r.get("notes") or "").lower())
    union = sorted(set(original) | set(declared))
    return {"original_sealed_flags": original, "ai_reviewer_declared": declared, "union_used": union,
            "no_known_exposure": sorted(set(ids) - set(union)), "identical": original == declared,
            "only_in_original": sorted(set(original) - set(declared)), "only_in_ai_declared": sorted(set(declared) - set(original))}


def agreement_block(e, done, sealed, weighted):
    preds = sealed["predictions"]
    rows = []
    for r in done:
        p = preds[r["topic_id"]]
        if p["validity_auto"] != r["human_validity"]:
            rows.append({"topic_id": r["topic_id"], "automatic": p["validity_auto"], "ai_reviewer": r["human_validity"],
                         "ai_confidence": r["reviewer_confidence"]})
    conflicts = [{"topic_id": r["topic_id"], "automatic_treatment": preds[r["topic_id"]]["hierarchy_treatment_auto"],
                  "ai_enter_hierarchy": r["enter_hierarchy"]} for r in done
                 if (preds[r["topic_id"]]["hierarchy_treatment_auto"] == "eligible") != (r["enter_hierarchy"] == "yes")]
    per = {c: {"automatic_count": v["auto_predicted_in_sample"], "ai_count": v["human_labelled_in_sample"],
               "share_of_automatic_c_that_ai_also_called_c": v["precision"],
               "wilson_95ci_exploratory": v["precision_95ci_wilson"],
               "share_of_ai_c_that_automatic_also_called_c_sample": v["recall_sample"],
               "share_of_ai_c_that_automatic_also_called_c_weighted": v["recall_population_weighted"] if weighted else None}
           for c, v in e["per_class"].items()}
    return {"label": AI_LABEL, "n_topics": e["n_reviewed"],
            "confusion_matrix": {"rows": "automatic classifier", "columns": "AI reviewer", "counts": e["confusion_matrix_sample"]["counts"]},
            "agreement_sample": e["sample_agreement"], "agreement_wilson_95ci_exploratory": e["sample_agreement_95ci_wilson"],
            "cohen_kappa_sample": e["cohen_kappa_sample"],
            "agreement_population_weighted": e["population_agreement_weighted"] if weighted else None,
            "agreement_population_weighted_95ci_exploratory": e["population_agreement_95ci"] if weighted else None,
            "per_class_agreement": per, "disagreements": rows,
            "disagreement_auto_coherent_ai_not": e["false_coherent"], "disagreement_auto_mixed_ai_not": e["false_mixed"],
            "disagreement_auto_surface_form_ai_not": e["false_surface_form"],
            "hierarchy_eligibility_conflicts": conflicts,
            "by_ai_confidence": e["by_reviewer_confidence"]}


def compare_ai(done, sealed, strata_N, ids):
    exp = exposure_records(done, sealed, ids)
    preds = sealed["predictions"]
    blind = [r for r in done if r["topic_id"] in set(exp["no_known_exposure"])]
    full = agreement_block(evaluate(done, sealed, strata_N), done, sealed, weighted=True)
    blind_strata = dict(Counter(preds[r["topic_id"]]["stratum"] for r in blind))
    return {"label": AI_LABEL, "exposure": exp, "all_topics": full,
            "no_known_exposure": None if not blind else {
                **agreement_block(evaluate(blind, sealed, strata_N), blind, sealed, weighted=False),
                "strata_present": blind_strata,
                "weighting": "not applied: exposure was not part of the sampling design, so the blind subset is not a "
                             "random sample within strata (unweighted, exploratory only)"},
            "weighting_note": "population weights (N_h / n_h) are used only for the full stratified sample of 30",
            "interpretation": ["agreement with an AI reviewer is not accuracy against ground truth",
                               "a disagreement is not a confirmed classifier error: either side may be wrong",
                               "the AI reviewer is the same model that built the classifier rules and wrote the six "
                               "development reviews, so agreement may be inflated by shared assumptions",
                               "30 topics (and fewer blind topics) give wide, exploratory intervals"]}


def ai_md(c):
    def block(b, title):
        cm = b["confusion_matrix"]["counts"]
        L = [f"## {title} — {AI_LABEL}", "", f"Topics: {b['n_topics']}", "",
             "| automatic \\ AI reviewer | " + " | ".join(VALIDITY) + " |", "|---|" + "---|" * len(VALIDITY)]
        L += [f"| {a} | " + " | ".join(str(cm[a][h]) for h in VALIDITY) + " |" for a in VALIDITY]
        L += ["", f"- Agreement (sample) {b['agreement_sample']} — Wilson 95% {b['agreement_wilson_95ci_exploratory']} (exploratory)",
              f"- Cohen's kappa (sample) {b['cohen_kappa_sample']}"]
        if b["agreement_population_weighted"] is not None:
            L.append(f"- Agreement, population-weighted by the sampling design: {b['agreement_population_weighted']} "
                     f"(bootstrap 95% {b['agreement_population_weighted_95ci_exploratory']}, exploratory)")
        else:
            L.append(f"- No population weighting: {b.get('weighting', '')}")
        if "strata_present" in b:
            L.append(f"- Strata present: {b['strata_present']}")
        L += ["", "| class | automatic | AI | share of automatic-c the AI also called c (Wilson 95%) | share of AI-c the classifier also called c |",
              "|---|---|---|---|---|"]
        for k, v in b["per_class_agreement"].items():
            L.append(f"| {k} | {v['automatic_count']} | {v['ai_count']} | {v['share_of_automatic_c_that_ai_also_called_c']} "
                     f"{v['wilson_95ci_exploratory']} | {v['share_of_ai_c_that_automatic_also_called_c_sample']}"
                     + (f" (weighted {v['share_of_ai_c_that_automatic_also_called_c_weighted']})"
                        if v["share_of_ai_c_that_automatic_also_called_c_weighted"] is not None else "") + " |")
        L += ["", "Disagreements (not confirmed errors):", ""]
        L += [f"- {d['topic_id']}: automatic `{d['automatic']}` vs AI `{d['ai_reviewer']}` (AI confidence {d['ai_confidence']})"
              for d in b["disagreements"]] or ["- none"]
        L += ["", f"- Automatic coherent, AI not (false-coherent-like disagreement): {b['disagreement_auto_coherent_ai_not'] or '—'}",
              f"- Automatic mixed, AI not: {b['disagreement_auto_mixed_ai_not'] or '—'}",
              f"- Automatic surface-form, AI not: {b['disagreement_auto_surface_form_ai_not'] or '—'}",
              "- Hierarchy eligibility conflicts: " + ("; ".join(f"{x['topic_id']} (automatic {x['automatic_treatment']}, AI "
                                                              f"enter={x['ai_enter_hierarchy']})" for x in b["hierarchy_eligibility_conflicts"]) or "none"), ""]
        return L
    e = c["exposure"]
    L = [f"# {AI_LABEL}", "", "Automatic topic-validity classifier vs `claude_review_sheet.csv`. **Not** a validation "
         "against human ground truth; the human `reviewer_sheet.csv` is still blank.", "",
         "## Exposure records (both kept unchanged)", "",
         f"- Original (sealed flags): {e['original_sealed_flags']}", f"- AI-declared (`seen label before`): {e['ai_reviewer_declared']}",
         f"- Identical: {e['identical']}; only original {e['only_in_original'] or '—'}; only AI {e['only_in_ai_declared'] or '—'}",
         f"- Union used for the blind-only analysis ({len(e['union_used'])}): {e['union_used']}",
         f"- No known exposure ({len(e['no_known_exposure'])}): {e['no_known_exposure']}", ""]
    L += block(c["all_topics"], "All 30 topics")
    if c["no_known_exposure"]:
        L += block(c["no_known_exposure"], "Topics with no known exposure")
    L += ["## Interpretation limits", ""] + [f"- {x}" for x in c["interpretation"]] + [f"- {c['weighting_note']}", ""]
    return "\n".join(L) + "\n"


def run_compare_ai(root=ROOT, run_id=RUN_ID, validity_run=None, sheet=None):
    d = audit_dir(root, run_id, validity_run)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    bad = [f for f, h in m["files_sha256"].items() if sha((d / f).read_bytes()) != h]
    sealed_b = (d / "sealed" / "auto_predictions.json").read_bytes()
    if bad or sha(sealed_b) != m["sealed_predictions_sha256"]:
        raise SystemExit(f"audit package changed since it was made: {bad or ['sealed/auto_predictions.json']}")
    done, probs = read_ai_sheet(sheet or d / "claude_review_sheet.csv", m["topics_sorted"])
    if probs:
        raise SystemExit("AI review sheet not usable: " + "; ".join(probs[:8]))
    c = compare_ai(done, json.loads(sealed_b), {k: s["N"] for k, s in m["strata"].items()}, m["topics_sorted"])
    c["inputs"] = {"ai_sheet_sha256": sha(Path(sheet or d / "claude_review_sheet.csv").read_bytes()),
                   "sealed_sha256": m["sealed_predictions_sha256"], "manifest_files_sha256": m["files_sha256"]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {f"ai_comparison_claude_{stamp}.json": json.dumps(c, indent=1, sort_keys=True) + "\n",
           f"ai_comparison_claude_{stamp}.md": ai_md(c),
           f"exposure_reconciliation_{stamp}.json": json.dumps({"label": AI_LABEL, **c["exposure"]}, indent=1, sort_keys=True) + "\n"}
    for n, text in out.items():
        with (d / n).open("x", encoding="utf-8") as fh:                 # never overwrite
            fh.write(text)
    return d / f"ai_comparison_claude_{stamp}.md", c


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["make", "evaluate", "compare-ai"])
    ap.add_argument("--validity-run", default="validity_v1_topic_naming_v1_qwen_qwen3.8-27b_pilot_20261103T210409Z")
    ap.add_argument("--sheet", help="evaluate: path of the filled reviewer sheet (default: the package's sheet)")
    ap.add_argument("--allow-partial", action="store_true", help="evaluate: progress check on a partly filled sheet")
    args = ap.parse_args()
    try:
        if args.cmd == "make":
            d, m, s = make(validity_run=args.validity_run)
            print(f"audit package -> {d.relative_to(ROOT)}")
            print(f"pool {m['procedure']['pool_size']} | strata " + ", ".join(
                f"{c}: n={v['n']} of N={v['N']} (p={v['inclusion_probability']:.3f}, weight {v['weight']:.2f})"
                for c, v in m["strata"].items()))
            print(f"unsampled classes {m['procedure']['unsampled_classes']} | diversity {m['diversity']}")
            print(f"exposed topics in sample: {m['exposure']['exposed_topics_in_sample']} of {len(m['topics_sorted'])}")
        elif args.cmd == "compare-ai":
            p, c = run_compare_ai(validity_run=args.validity_run, sheet=args.sheet)
            a, b = c["all_topics"], c["no_known_exposure"]
            print(f"{AI_LABEL} -> {p.relative_to(ROOT)}")
            print(f"all {a['n_topics']}: agreement {a['agreement_sample']} kappa {a['cohen_kappa_sample']} weighted "
                  f"{a['agreement_population_weighted']}" + (f" | no known exposure {b['n_topics']}: agreement "
                                                            f"{b['agreement_sample']} kappa {b['cohen_kappa_sample']}" if b else ""))
        else:
            p, e = run_evaluate(validity_run=args.validity_run, sheet=args.sheet, allow_partial=args.allow_partial)
            print(f"{e['status']} -> {p.relative_to(ROOT)}")
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
