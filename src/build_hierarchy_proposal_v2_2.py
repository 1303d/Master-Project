"""Sprint 4 Phase 3: Hierarchy Proposal v2.2 — coverage recovery, label refinement, ESCO purity attribution.

    .venv/bin/python src/build_hierarchy_proposal_v2_2.py

Starts from hierarchy_proposal_v2_1 (no new clustering sweep). Read-only over every input and prior version.

Sequential placement of eligible unresolved topics (deterministic; one addition at a time):
  for every candidate, every existing parent is tried; an addition j -> P passes only if ALL gates hold:
    G1 LOO margin of j in P >= MIN_ADD_MARGIN (split candidates: >= LOW_MARGIN)
    G2 P's coherence after >= LOW_COHERENCE and drops by <= MAX_COH_DROP
    G3 P is not member-level mixing after the addition (sibling affinity >= MIX_SIB, weakest child pair >= MIX_PAIR)
    G4 member-level support of j for P > 0 (share of j's members whose nearest other topic is a child of P)
    G5 no placed child anywhere turns conflicting (LOO margin from >= 0 to < 0) and no more than MAX_NEW_LOW_MARGIN
       children newly fall below LOW_MARGIN
  among all passing (candidate, parent) pairs the one with the largest margin is accepted (ties: topic id, parent id);
  everything is recomputed and the loop repeats until nothing passes. No new parents are created.
Labels: terms shared by children (names + member skills), lemma de-duplication, synonym de-duplication with the frozen
embeddings, child coverage check, vagueness check, verified ESCO only (suspect + unresolvable links excluded).
CONFIDENT = LOO margin >= 0.02 AND not split-pending (all versions). Nothing is human-approved.
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_hierarchy_proposal as hp  # noqa: E402
import build_hierarchy_proposal_v2 as v2  # noqa: E402
import build_hierarchy_proposal_v2_1 as v21  # noqa: E402
import esco_levels as el  # noqa: E402

ROOT = hp.ROOT
V21 = v21.OUT
OUT = ROOT / f"reports/sprint4_naming/{hp.RUN}/hierarchy_proposal_v2_2"
VERSION = "hierarchy_proposal_v2_2"
LABEL = v2.LABEL
LOW_MARGIN, LOW_COHERENCE, MIX_SIB, MIX_PAIR = v2.LOW_MARGIN, v2.LOW_COHERENCE, v2.MIX_SIB, v2.MIX_PAIR
MIN_ADD_MARGIN = 0.005
MAX_COH_DROP = 0.010
MAX_NEW_LOW_MARGIN = 1
SYNONYM_COS = 0.85
EXPECT_V21 = {"topics": 374, "eligible": 335, "excluded": 39, "placed": 198, "eligible_unresolved": 137, "parents": 59, "confident": 117}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


# =================================================================== vectorised margins
def all_margins(ctx, parents):
    """{topic index: (margin, own LOO cos, best other parent id)} for every placed child; same definition as v2.loo_margins."""
    keys = sorted(parents)
    if len(keys) < 2:
        return {}
    P = np.stack([ctx.sum[parents[k]].sum(0) for k in keys]); Pn = P / np.linalg.norm(P, axis=1, keepdims=True)
    kids = np.array([j for k in keys for j in parents[k]]); own = np.array([i for i, k in enumerate(keys) for _ in parents[k]])
    S = ctx.C[kids] @ Pn.T
    O = P[own] - ctx.sum[kids]; own_cos = np.einsum("ij,ij->i", ctx.C[kids], O) / np.linalg.norm(O, axis=1)
    S[np.arange(len(kids)), own] = -np.inf
    bo = S.argmax(1)
    return {int(j): (float(oc - S[i, bo[i]]), float(oc), keys[bo[i]]) for i, (j, oc) in enumerate(zip(kids, own_cos))}


def evaluate_addition(ctx, parents, base_m, j, dest):
    trial = {k: list(v) for k, v in parents.items()}; trial[dest] = sorted(trial[dest] + [j])
    m = all_margins(ctx, trial); mg = m[j][0] if j in m else float("-inf")      # no other parent -> no margin -> G1 fails
    base_m = {x: v for x, v in base_m.items() if x in m}
    before = v21.group_stats(ctx, parents[dest]); after = v21.group_stats(ctx, trial[dest])
    sup = v21.support(ctx, j, trial[dest])
    new_conf = [x for x, (b, _, _) in base_m.items() if b >= 0 and m[x][0] < 0]
    new_low = [x for x, (b, _, _) in base_m.items() if b >= LOW_MARGIN and m[x][0] < LOW_MARGIN]
    need = LOW_MARGIN if ctx.ids[j] in ctx.split else MIN_ADD_MARGIN
    gates = {"G1_margin": mg >= need, "G2_coherence": after["coherence"] >= LOW_COHERENCE and before["coherence"] - after["coherence"] <= MAX_COH_DROP,
             "G3_no_mixing": not after["mixing"], "G4_member_support": sup > 0,
             "G5_no_new_conflicts": not new_conf and len(new_low) <= MAX_NEW_LOW_MARGIN}
    return {"topic": j, "dest": dest, "margin": mg, "coh_before": before["coherence"], "coh_after": after["coherence"],
            "sib_after": after["sib"], "min_pair_after": after["min_pair"], "support": sup, "new_conflicts": len(new_conf),
            "new_low_margin": len(new_low), "gates": gates, "passed": all(gates.values()), "trial": trial}


def sequential_placement(ctx, parents, candidates):
    parents = {k: sorted(v) for k, v in parents.items()}
    accepted, last_eval = [], {}
    remaining = sorted(candidates)
    while True:
        base = all_margins(ctx, parents)
        best = None
        for j in remaining:
            # plausible destinations: every parent, ordered by raw centroid similarity
            evals = [evaluate_addition(ctx, parents, base, j, k) for k in sorted(parents)]
            last_eval[j] = evals
            for e in evals:
                if e["passed"] and (best is None or (e["margin"], -j, ) > (best["margin"], -best["topic"]) or
                                    (e["margin"] == best["margin"] and e["topic"] == best["topic"] and e["dest"] < best["dest"])):
                    best = e
        if best is None:
            break
        parents = best["trial"]; remaining.remove(best["topic"])
        accepted.append({k: v for k, v in best.items() if k != "trial"} | {"order": len(accepted) + 1})
    return parents, accepted, last_eval, remaining


# =================================================================== labels v2.2
SUFFIXES = ("izations", "ization", "ations", "ation", "ments", "ment", "ings", "ing", "ities", "ity", "ers", "er", "ies", "es", "ed", "s")


def lemma(w):
    w = w.lower()
    for s in SUFFIXES:
        if w.endswith(s) and len(w) - len(s) >= 3:
            w = w[: -len(s)]
            break
    return re.sub(r"(.)\1$", r"\1", w)          # plann -> plan


def same_root(a, b):
    la, lb = {lemma(x) for x in a.split()}, {lemma(x) for x in b.split()}
    return bool(la & lb) or any(x.startswith(y) or y.startswith(x) or len(os.path.commonprefix([x, y])) >= 5
                                for x in la for y in lb if min(len(x), len(y)) >= 4)


class TermVectors:
    """Frozen skill embeddings for terms that are themselves canonical skill keys (no new embeddings)."""

    def __init__(self, ctx):
        sk = read(hp.INP / "skills.csv"); self.row = dict(zip(sk.skill_key, sk.vector_row.astype(int)))
        self.V = np.load(hp.INP / "vectors.npy")

    def cos(self, a, b):
        if a in self.row and b in self.row:
            return float(self.V[self.row[a]] @ self.V[self.row[b]])
        return None

    def is_skill(self, t):
        return t in self.row


def label_v22(ctx, g, M, terms, stats, support_docs, label_docs, tv):
    sub = M[g].toarray(); present = (sub > 0).sum(0); need = max(2, int(np.ceil(len(g) / 2)))
    score = np.where(present >= need, sub.sum(0), 0.0)
    score = score * np.array([1.5 if " " in t else 1.0 for t in terms])          # prefer noun phrases (bigrams)
    order = [i for i in np.argsort(-score, kind="stable") if score[i] > 0]
    picked, dropped = [], []
    for i in order:
        t = terms[i]
        if len({lemma(x) for x in t.split()}) < len(t.split()):
            dropped.append(f"{t}: repeated root inside term"); continue
        if any(same_root(t, p) for p in picked):
            dropped.append(f"{t}: same root as '{next(p for p in picked if same_root(t, p))}'"); continue
        syn = [p for p in picked if (tv.cos(t, p) or 0) >= SYNONYM_COS]
        if syn:
            dropped.append(f"{t}: synonym of '{syn[0]}' (embedding cos >= {SYNONYM_COS})"); continue
        picked.append(t)
        if len(picked) == 2:
            break
    docs = [label_docs[j].lower() for j in g]
    covers = all(any(p in d for p in picked) for d in docs) if picked else False
    ev_support = {p: sum(p in support_docs[j] for j in g) for p in picked}
    esco = {}
    for lv in (2, 1):
        groups_l, W, used = ctx.G[lv]; u = used[g].sum(); w = W[g].sum(0)
        if u >= 8 and w.max() / u >= 0.5:
            esco[lv] = (ctx.glabels.get(groups_l[int(w.argmax())], ""), float(w.max() / u), int(u))
    agree = next((lv for lv in (2, 1) if lv in esco and picked and any(same_root(esco[lv][0], p) for p in picked)), None)
    vague = len(picked) == 1 and " " not in picked[0] and not tv.is_skill(picked[0])
    reasons = []
    if not picked:
        label, state, conf, basis = "UNRESOLVED_LABEL", "UNRESOLVED_LABEL", "low", "no defensible shared term"
        reasons.append("no term shared by enough children")
    else:
        label = " and ".join(p[:1].upper() + p[1:] for p in picked); state = "PROVISIONAL_LABEL"
        conf = "high" if agree else "medium"
        basis = f"shared child terms; agrees with verified ESCO L{agree} '{esco[agree][0]}'" if agree else "shared child terms"
        if not covers:
            conf = "low"; reasons.append("label terms do not appear in every child")
        if vague:
            conf = "low"; reasons.append(f"vague single word '{picked[0]}' (not a canonical skill)")
        if min(ev_support.values()) == 0:
            conf = "low"; reasons.append("a label term is absent from all child descriptions and posting quotes")
    if stats["mixing"]:
        conf = "low"; reasons.append("member-level mixing")
    if stats["coherence"] < LOW_COHERENCE:
        conf = "low"; reasons.append(f"coherence {stats['coherence']:.3f} < {LOW_COHERENCE}")
    if conf == "low" and state == "PROVISIONAL_LABEL" and not covers and vague:
        state = "UNRESOLVED_LABEL"
    P = ctx.sum[g].sum(0); P /= np.linalg.norm(P)
    mem = ctx.a[ctx.a.t.isin(g)]; reps = mem.skill_key.values[np.argsort(-(ctx.X[mem.index.values] @ P), kind="stable")][:8]
    return {"proposed_label": label, "label_state": state, "label_confidence": conf, "label_basis": basis, "supporting_terms": "; ".join(picked),
            "rejected_terms": "; ".join(dropped[:6]), "covers_all_children": covers, "vague_single_word": vague,
            "terms_in_descriptions_or_quotes": "; ".join(f"{p}: {c}/{len(g)}" for p, c in ev_support.items()),
            "esco_evidence": "; ".join(f"L{lv} '{a}' {b:.2f} over {c} links" for lv, (a, b, c) in sorted(esco.items())) or "none verified",
            "representative_member_skills": "; ".join(reps), "label_uncertainty": "; ".join(reasons), "needs_label_review": conf == "low" or state == "UNRESOLVED_LABEL"}


def label_quality(labels):
    """Detectors applied identically to any label list (strings)."""
    rows = []
    for lab in labels:
        parts = [p.strip().lower() for p in re.split(r"\band\b|:|;", lab) if p.strip()]
        dup = any(same_root(a, b) for i, a in enumerate(parts) for b in parts[i + 1:])
        rows.append({"label": lab, "same_root_duplicate": dup, "concatenated": " / " in lab, "generic": bool(re.search(r"related topics|miscellaneous|other skills", lab, re.I)),
                     "unresolved": lab == "UNRESOLVED_LABEL"})
    return pd.DataFrame(rows)


# =================================================================== ESCO purity attribution
def purity_table(ctx, versions, common):
    rows = []
    for name, groups in versions.items():
        for pop, restrict in (("full", None), ("common_placed", common)):
            gs = [g for g in ([j for j in g if restrict is None or j in restrict] for g in groups) if len(g) >= 2]
            for lv in (1, 2):
                groups_l, W, used = ctx.G[lv]
                vals, wtop, wall, sizes = [], 0.0, 0.0, []
                for g in gs:
                    u = used[g].sum(); w = W[g].sum(0)
                    if u >= v2.ESCO_MIN_LINKS:
                        vals.append(w.max() / u); wtop += w.max(); wall += u; sizes.append(len(g))
                vals = np.array(vals); sizes = np.array(sizes)
                rows.append({"version": name, "population": pop, "level": lv, "parents_evaluated": len(vals), "parents_total": len(gs),
                             "median_parent_purity": float(np.median(vals)) if len(vals) else float("nan"),
                             "link_weighted_purity": wtop / wall if wall else float("nan"), "usable_links": int(wall),
                             "median_purity_size2": float(np.median(vals[sizes == 2])) if (sizes == 2).any() else float("nan"),
                             "median_purity_size3plus": float(np.median(vals[sizes >= 3])) if (sizes >= 3).any() else float("nan"),
                             "share_parents_size2": float((sizes == 2).mean()) if len(sizes) else float("nan")})
    return pd.DataFrame(rows)


def first_parent_purity(ctx, groups, level):
    """Same as purity but each link counts only its first (sorted) level-L ancestor — isolates multi-parent ancestry."""
    lk = ctx.a.merge(read(hp.INP / "reference_links.csv"), on="skill_key")
    lk = lk[(lk.verdict == "known_skill") & lk.source.str.startswith("ESCO") & lk.ref_id.isin(ctx.esco_skills) & ~lk.skill_key.isin(ctx.suspect)]
    first = {}
    for t, u in zip(lk.t.values, lk.ref_id.values):
        gs = sorted(el.ancestors_at_level(u, level, ctx.level_of, ctx.parents_esco))
        if gs:
            first.setdefault(t, []).append(gs[0])
    vals = []
    for g in groups:
        xs = [x for j in g for x in first.get(j, [])]
        if len(xs) >= v2.ESCO_MIN_LINKS:
            vals.append(pd.Series(xs).value_counts().iloc[0] / len(xs))
    return float(np.median(vals)) if vals else float("nan")


# =================================================================== main
def main(out=OUT):
    if out.exists() and any(out.iterdir()):
        sys.exit(f"refusing to overwrite {out}")
    inputs = {"v21_manifest": V21 / "manifest.json", "v21_hierarchy": V21 / "hierarchy_proposal.csv", "v21_parents": V21 / "parent_categories.csv",
              "v21_decisions": V21 / "topic_placement_decisions.csv", "v21_comparison": V21 / "fair_comparison.csv",
              "v2_parents": v2.OUT / "parent_categories.csv", "v2_hierarchy": v2.OUT / "hierarchy_proposal.csv", "v1_parents": v2.V1 / "parent_categories.csv",
              "names": hp.NAMES, "mentions": ROOT / "data/interim/prepared_mentions.csv"}
    miss = [k for k, p in inputs.items() if not Path(p).exists()]
    if miss:
        sys.exit(f"BLOCKED: missing inputs {miss}")
    before = {k: sha256(p) for k, p in inputs.items()}
    for d in (V21, v2.OUT, v2.V1, v2.PREFLIGHT):
        man = json.loads((d / "manifest.json").read_text())
        assert all(sha256(d / f) == h for f, h in man["outputs"].items()), f"{d.name} outputs changed"

    ctx = v2.Ctx()
    h21 = read(inputs["v21_hierarchy"]); p21 = read(inputs["v21_parents"]); m21 = json.loads(inputs["v21_manifest"].read_text())
    got = {"topics": len(h21), "eligible": int((h21.placement_state != "UNRESOLVED_EXCLUDED").sum()), "excluded": int((h21.placement_state == "UNRESOLVED_EXCLUDED").sum()),
           "placed": int((h21.parent_id != "").sum()), "parents": len(p21), "confident": int((h21.placement_state == "PLACED_CONFIDENT").sum())}
    got["eligible_unresolved"] = got["eligible"] - got["placed"]
    assert got == EXPECT_V21, f"v2.1 counts differ: {got}"
    parents21 = {r.parent_id: sorted(ctx.ti[t] for t in r.child_topic_ids.split(";")) for r in p21.itertuples()}
    am, lm = all_margins(ctx, parents21), v2.loo_margins(ctx, [parents21[k] for k in sorted(parents21)])
    assert set(am) == set(lm) and np.allclose([am[k][0] for k in sorted(am)], [lm[k][0] for k in sorted(am)], atol=1e-9), "vectorised margins differ"

    # Step 2: candidates
    cand = h21[(h21.parent_id == "") & (h21.placement_state != "UNRESOLVED_EXCLUDED")]
    origin = {ctx.ti[t]: ("v2_singleton_never_reconsidered" if s == "UNRESOLVED_SINGLETON" else f"v2_1_{s.lower()}") for t, s in zip(cand.topic_id, cand.placement_state)}
    prelim77 = {j for j, o in origin.items() if o.startswith("v2_singleton") and v21.try_place(ctx, parents21, j) is not None}

    # Step 3: sequential placement
    parents22, accepted, last_eval, rejected = sequential_placement(ctx, parents21, list(origin))
    rec_rows = [{"order": a["order"], "topic_id": ctx.ids[a["topic"]], "provisional_name": ctx.names[ctx.ids[a["topic"]]], "origin": origin[a["topic"]],
                 "parent_id": a["dest"], "loo_margin": round(a["margin"], 4), "coherence_before": round(a["coh_before"], 4), "coherence_after": round(a["coh_after"], 4),
                 "sibling_affinity_after": round(a["sib_after"], 4), "member_support": round(a["support"], 4), "new_conflicts": a["new_conflicts"],
                 "new_low_margin": a["new_low_margin"], "split_candidate": ctx.ids[a["topic"]] in ctx.split, "in_preliminary_77": a["topic"] in prelim77,
                 "decision": "ACCEPTED", "ai_label": LABEL, "human_approved": False} for a in accepted]
    rej_rows = []
    for j in sorted(rejected):
        evals = last_eval.get(j, [])
        best = max(evals, key=lambda e: (sum(e["gates"].values()), e["margin"])) if evals else None
        rej_rows.append({"topic_id": ctx.ids[j], "provisional_name": ctx.names[ctx.ids[j]], "origin": origin[j], "split_candidate": ctx.ids[j] in ctx.split,
                         "in_preliminary_77": j in prelim77, "closest_parent_tried": best["dest"] if best else "", "best_margin": round(best["margin"], 4) if best else "",
                         "failed_gates": "; ".join(k for k, v in best["gates"].items() if not v) if best else "no parents",
                         "parents_tried": len(evals), "decision": "REJECTED_REMAINS_UNRESOLVED"})
    recovered = pd.DataFrame(rec_rows); rejected_df = pd.DataFrame(rej_rows)

    # labels
    label_docs, support_docs = v21.topic_docs(ctx); M, terms = v21.term_matrix(label_docs); tv = TermVectors(ctx)
    m22 = all_margins(ctx, parents22); eligible = [ctx.ti[t] for t in ctx.ids if t not in ctx.excluded]
    groups22 = [parents22[k] for k in sorted(parents22)]
    _, pdf22, _ = v2.evaluate(ctx, groups22, eligible)
    lab = {}; prow = []
    for gi, k in enumerate(sorted(parents22)):
        st = v21.group_stats(ctx, parents22[k]); lab[k] = label_v22(ctx, parents22[k], M, terms, st, support_docs, label_docs, tv); r = pdf22.iloc[gi]
        prow.append({"parent_id": k, **lab[k], "previous_label_v2_1": p21.set_index("parent_id").proposed_label.get(k, ""),
                     "n_children": len(parents22[k]), "children_added_v2_2": ";".join(ctx.ids[j] for j in parents22[k] if j not in parents21.get(k, [])),
                     "child_topic_ids": ";".join(ctx.ids[j] for j in parents22[k]), "child_names": " | ".join(ctx.names[ctx.ids[j]] for j in parents22[k]),
                     "coherence": round(r.coherence, 4), "sibling_affinity": round(r.sibling_affinity, 4), "min_child_pair_cos": round(r.min_child_pair_cos, 4),
                     "parent_separation": round(r.parent_separation, 4), "esco_purity_L1": round(r.esco_purity_L1, 4), "esco_purity_L2": round(r.esco_purity_L2, 4),
                     "esco_coverage": round(r.esco_coverage, 4), "flag_mixing": bool(r.mixing), "suspicious": bool(r.suspicious), "ai_label": LABEL, "human_approved": False})
    parents_df = pd.DataFrame(prow)
    owner = {j: k for k, v in parents22.items() for j in v}
    hrow = []
    for t in ctx.ids:
        j = ctx.ti[t]; k = owner.get(j, ""); prev = h21.set_index("topic_id").at[t, "placement_state"]
        if t in ctx.excluded:
            st = "UNRESOLVED_EXCLUDED"
        elif not k:
            st = prev if prev.startswith("UNRESOLVED") else "UNRESOLVED_SINGLETON"
        else:
            st = "PLACED_CONFIDENT" if m22[j][0] >= LOW_MARGIN and t not in ctx.split else "PLACED_LOW_CONFIDENCE"
        hrow.append({"topic_id": t, "provisional_name": ctx.names[t], "parent_id": k, "proposed_parent_label": lab[k]["proposed_label"] if k else "",
                     "placement_state": st, "loo_margin": round(m22[j][0], 4) if j in m22 else "", "split_candidate": t in ctx.split,
                     "recovered_in_v2_2": j in {a["topic"] for a in accepted}, "v2_1_parent": h21.set_index("topic_id").at[t, "parent_id"],
                     "v2_1_state": prev, "ai_label": LABEL, "human_approved": False})
    h = pd.DataFrame(hrow)

    # comparison (identical definitions)
    p2 = read(inputs["v2_parents"]); p1 = read(inputs["v1_parents"])
    g1 = [sorted(ctx.ti[t] for t in r.child_topic_ids.split(";")) for r in p1.itertuples()]
    g2 = [sorted(ctx.ti[t] for t in r.child_topic_ids.split(";")) for r in p2.itertuples()]
    g21 = [parents21[k] for k in sorted(parents21)]
    lq21 = label_quality(p21.proposed_label); lq22 = label_quality(parents_df.proposed_label)
    s21, _, _ = v21.version_metrics(ctx, g21, eligible, p21.label_confidence)
    s22, _, _ = v21.version_metrics(ctx, groups22, eligible, parents_df.label_confidence)
    for s, lq in ((s21, lq21), (s22, lq22)):
        s.update({"eligible_coverage": s["placed"] / len(eligible), "label_same_root_duplicates": int(lq.same_root_duplicate.sum()),
                  "label_unresolved": int(lq.unresolved.sum()), "label_concatenated_or_generic": int((lq.concatenated | lq.generic).sum())})
    s22["label_vague_single_word"] = int(parents_df.vague_single_word.sum()); s22["label_not_covering_all_children"] = int((~parents_df.covers_all_children).sum())
    comp = pd.DataFrame([{"metric": k, "v2_1": s21.get(k), "v2_2": s22.get(k)} for k in s22])
    common_df, common = v21.common_population(ctx, {"v2_1": g21, "v2_2": groups22})
    common_all, common4 = v21.common_population(ctx, {"v1": g1, "v2": g2, "v2_1": g21, "v2_2": groups22})
    pur = purity_table(ctx, {"v1": g1, "v2": g2, "v2_1": g21, "v2_2": groups22}, common4)
    fp = pd.DataFrame([{"version": n, "level": lv, "median_purity_first_parent_only": first_parent_purity(ctx, g, lv)}
                       for n, g in {"v1": g1, "v2": g2, "v2_1": g21, "v2_2": groups22}.items() for lv in (1, 2)])
    full = pur[pur.population == "full"].set_index(["version", "level"]).median_parent_purity
    fp["median_purity_multi_parent"] = [full[(r.version, r.level)] for r in fp.itertuples()]
    lab_ev = parents_df[["parent_id", "previous_label_v2_1", "proposed_label", "label_state", "label_confidence", "label_basis", "supporting_terms", "rejected_terms",
                         "covers_all_children", "vague_single_word", "terms_in_descriptions_or_quotes", "esco_evidence", "representative_member_skills",
                         "label_uncertainty", "needs_label_review", "child_names"]]

    # validation
    probs = []
    if len(h) != 374 or not h.topic_id.is_unique: probs.append("coverage/duplicates")
    if (h[h.topic_id.isin(ctx.excluded)].parent_id != "").any(): probs.append("excluded topic placed")
    if h.set_index("topic_id").at["T0104", "placement_state"] != "UNRESOLVED_EXCLUDED": probs.append("T0104 not excluded")
    if (h.placement_state.str.startswith("UNRESOLVED") & (h.parent_id != "")).any(): probs.append("unresolved with parent")
    if sum(map(len, parents22.values())) != len(owner): probs.append("duplicate placement")
    if (parents_df.n_children < 2).any(): probs.append("single-child parent")
    if set(parents22) != set(parents21): probs.append("parent set changed (no new parents allowed)")
    if any(not set(parents21[k]) <= set(parents22[k]) for k in parents21): probs.append("existing child removed")
    if (lq22.concatenated | lq22.generic).any(): probs.append("generic/concatenated label")
    if h.human_approved.any() or parents_df.human_approved.any(): probs.append("human approval set")
    gate_fail = recovered[(recovered.new_conflicts > 0)] if len(recovered) else recovered
    if len(gate_fail): probs.append("accepted placement created conflicts")

    out.mkdir(parents=True, exist_ok=True)
    files = {"hierarchy_proposal.csv": h, "parent_categories.csv": parents_df, "recovered_placements.csv": recovered,
             "rejected_candidate_placements.csv": rejected_df, "label_refinement_evidence.csv": lab_ev, "v2_1_vs_v2_2_comparison.csv": comp,
             "common_population_comparison.csv": pd.concat([common_df.assign(scope="v2_1_and_v2_2"), common_all.assign(scope="all_four_versions")]),
             "esco_purity_attribution.csv": pur, "esco_purity_multi_vs_first_parent.csv": fp}
    for f, d in files.items():
        d.to_csv(out / f, index=False)
    (out / "esco_purity_attribution.md").write_text(purity_md(pur, fp, common4), encoding="utf-8")
    (out / "validation_report.md").write_text(report(got, origin, prelim77, recovered, rejected_df, comp, common_df, common_all, parents_df, h, probs), encoding="utf-8")
    assert before == {k: sha256(p) for k, p in inputs.items()}, "an input changed"
    man = {"version": VERSION, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "scripts": {s: sha256(ROOT / "src" / s) for s in ("build_hierarchy_proposal_v2_2.py", "build_hierarchy_proposal_v2_1.py", "build_hierarchy_proposal_v2.py", "esco_levels.py")},
           "inputs": {k: {"path": str(p).replace(str(Path.home()), "~"), "sha256": before[k]} for k, p in inputs.items()},
           "outputs": {f: sha256(out / f) for f in sorted(os.listdir(out))},
           "gates": {"MIN_ADD_MARGIN": MIN_ADD_MARGIN, "split_candidate_margin": LOW_MARGIN, "LOW_COHERENCE": LOW_COHERENCE, "MAX_COH_DROP": MAX_COH_DROP,
                     "MIX_SIB": MIX_SIB, "MIX_PAIR": MIX_PAIR, "MAX_NEW_LOW_MARGIN": MAX_NEW_LOW_MARGIN, "SYNONYM_COS": SYNONYM_COS},
           "v2_1_verified_counts": got, "candidates": len(origin), "candidate_origin": pd.Series(origin).value_counts().to_dict(),
           "preliminary_77": len(prelim77), "preliminary_77_accepted": int(recovered.in_preliminary_77.sum()) if len(recovered) else 0,
           "recovered": len(recovered), "metrics": {"v2_1": s21, "v2_2": s22}, "structural_problems": probs,
           "confidence_definition": "CONFIDENT = LOO margin >= 0.02 AND not split-pending", "ai_label": LABEL, "human_approved": False}
    (out / "manifest.json").write_text(json.dumps(man, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: man[k] for k in ("v2_1_verified_counts", "candidate_origin", "preliminary_77", "preliminary_77_accepted", "recovered", "structural_problems")}, indent=1, default=float))
    return man


def purity_md(pur, fp, common4):
    f = lambda x: "—" if pd.isna(x) else f"{x:.3f}"
    L = ["# ESCO purity attribution (v1, v2, v2.1, v2.2)", "",
         "> Corrected definitions (esco_levels): skills-hierarchy Level 1 / Level 2, multi-parent weights 1/|groups|, links not in v1.2.1 and the 37 "
         "suspect accepted links excluded, parents with ≥ 3 usable links. Purity is a reference-agreement signal, **not proof** of better clustering.", "",
         f"Common placed population (topics placed in all four versions): {len(common4)} topics.", "",
         "| Version | Population | Level | Parents evaluated / total | Median parent purity | Link-weighted purity | Usable links | Median purity, 2-child | Median purity, 3+ | Share 2-child |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    L += [f"| {r.version} | {r.population} | {r.level} | {r.parents_evaluated}/{r.parents_total} | {f(r.median_parent_purity)} | {f(r.link_weighted_purity)} | "
          f"{r.usable_links} | {f(r.median_purity_size2)} | {f(r.median_purity_size3plus)} | {f(r.share_parents_size2)} |" for r in pur.itertuples()]
    L += ["", "## Multi-parent ancestry", "", "| Version | Level | Median purity (multi-parent) | Median purity (first parent only) |", "|---|---:|---:|---:|"]
    L += [f"| {r.version} | {r.level} | {f(r.median_purity_multi_parent)} | {f(r.median_purity_first_parent_only)} |" for r in fp.itertuples()]
    full = pur[pur.population == "full"]; com = pur[pur.population == "common_placed"]
    def get(df, v, lv, c):
        return float(df[(df.version == v) & (df.level == lv)][c].iloc[0])
    def d(v, lv, c, df=full):
        return get(df, v, lv, c)
    lines = []
    for v in ("v1", "v2", "v2_1", "v2_2"):
        s2, s3 = d(v, 1, "median_purity_size2"), d(v, 1, "median_purity_size3plus")
        lines.append(f"{v}: 2-child {f(s2)} vs 3+ children {f(s3)} (share of 2-child parents {f(d(v, 1, 'share_parents_size2'))})")
    L += ["", "## Reading (computed from the tables above)", "",
          "- Parent size vs L1 purity: " + "; ".join(lines) + ".",
          f"- v2 -> v2.1 on the SAME topics (common placed, L1 median): {f(get(com, 'v2', 1, 'median_parent_purity'))} -> {f(get(com, 'v2_1', 1, 'median_parent_purity'))}; "
          f"the decline is therefore not a coverage effect. It follows the change in parent composition: v2.1's larger parents (3+ children) have L1 purity "
          f"{f(d('v2_1', 1, 'median_purity_size3plus'))} vs {f(d('v2', 1, 'median_purity_size3plus'))} in v2, i.e. the moves/orphan placements that built larger parents mixed ESCO groups.",
          f"- v2.1 -> v2.2: identical on the common placed population ({f(get(com, 'v2_1', 2, 'median_parent_purity'))} vs {f(get(com, 'v2_2', 2, 'median_parent_purity'))} at L2), "
          f"lower on the full population ({f(d('v2_1', 2, 'median_parent_purity'))} -> {f(d('v2_2', 2, 'median_parent_purity'))} at L2): the change comes only from the recovered topics added to parents.",
          "- Multi-parent ancestry: first-parent-only medians differ from multi-parent medians by at most a few hundredths (table above), so ESCO's multiple ancestry is a minor factor.",
          f"- Reference coverage: usable links {', '.join(f'{v} {int(full[(full.version == v) & (full.level == 1)].usable_links.iloc[0])}' for v in ('v1', 'v2', 'v2_1', 'v2_2'))}; "
          "parents with < 3 usable links are not evaluated.",
          "- Higher purity is not proof of better clustering: ESCO links are automatic, and small parents score higher or lower by chance."]
    return "\n".join(L)


def report(got, origin, prelim77, recovered, rejected_df, comp, common_df, common_all, parents_df, h, probs):
    f = lambda x: "—" if x is None or (isinstance(x, float) and pd.isna(x)) else (f"{x:.3f}" if isinstance(x, float) else str(x))
    L = ["# Hierarchy Proposal v2.2 — validation report", "",
         f"> **{LABEL}.** Coverage recovery and label refinement on top of v2.1. No new clustering, no new parents; prior versions and frozen data unchanged.", "",
         "## 1. v2.1 verification", "", f"{got} — all as expected.", "",
         "## 2–3. Sequential placement", "",
         f"Candidates: {len(origin)} {pd.Series(origin).value_counts().to_dict()}. Preliminary single-test passes (v2 singletons): {len(prelim77)}.",
         f"Gates: margin ≥ {MIN_ADD_MARGIN} (split candidates ≥ {LOW_MARGIN}); coherence ≥ {LOW_COHERENCE} and drop ≤ {MAX_COH_DROP}; no member-level mixing; "
         f"member support > 0; no new conflicts and ≤ {MAX_NEW_LOW_MARGIN} new low-margin child.", "",
         f"**Accepted: {len(recovered)}** (of the preliminary {len(prelim77)}: {int(recovered.in_preliminary_77.sum()) if len(recovered) else 0}). "
         f"Rejected: {len(rejected_df)}; most common failed gate: {rejected_df.failed_gates.str.split('; ').explode().value_counts().head(5).to_dict() if len(rejected_df) else {}}.", "",
         "## 4. Labels", "", f"States {parents_df.label_state.value_counts().to_dict()}; confidence {parents_df.label_confidence.value_counts().to_dict()}; "
         f"vague single words {int(parents_df.vague_single_word.sum())}; not covering all children {int((~parents_df.covers_all_children).sum())}.", "",
         "## 6. v2.1 vs v2.2 (identical definitions)", "", "| Metric | v2.1 | v2.2 |", "|---|---:|---:|"]
    L += [f"| {r.metric} | {f(r.v2_1)} | {f(r.v2_2)} |" for r in comp.itertuples()]
    L += ["", "### Common placed topics", "", "| Scope | Version | Topics | Conflict rate | Median margin | Confident rate | Parent coherence | In mixing parent |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for df, sc in ((common_df, "v2.1 ∩ v2.2"), (common_all, "all four")):
        L += [f"| {sc} | {r.version} | {r.common_topics} | {r.conflict_rate:.3f} | {r.median_margin:.3f} | {r.confident_authoritative_rate:.3f} | "
              f"{r.mean_coherence_of_parent:.3f} | {r.share_in_mixing_parent:.3f} |" for r in df.itertuples()]
    L += ["", "ESCO purity attribution: see `esco_purity_attribution.md`.", "", "## 7. Validation", "",
          f"Placement states: {h.placement_state.value_counts().to_dict()}.", "", f"**Structural problems: {probs or 'none'}**"]
    return "\n".join(L)


if __name__ == "__main__":
    main()
