"""Sprint 4 Phase 3: Hierarchy Proposal v2.1 — targeted refinement of v2 (no new clustering sweep).

    .venv/bin/python src/build_hierarchy_proposal_v2_1.py

Starts from hierarchy_proposal_v2 and applies, deterministically:
  1. conflict refinement: each v2 child whose leave-one-out (LOO) margin is < 0 is (A) kept, (B) moved or (C) unresolved.
     A move needs ALL of: positive LOO margin at the destination that beats the current one; destination coherence
     >= LOW_COHERENCE after the move; no member-level mixing at the destination after the move; member-level support
     (share of the topic's members whose nearest other topic lies in the destination) >= that of the current parent and > 0.
     A topic moves at most once (no oscillation); unresolved is terminal. Without an acceptable move: margin < -NEAR_TIE ->
     unresolved, otherwise kept as a near-tie (low confidence). Parents left with one child are dissolved.
  2. weak pairs: two-child parents with sibling member affinity < MIX_SIB AND no shared descriptive term AND ESCO L2
     profile cosine < 0.5 (or unavailable) are dissolved (both children unresolved).
  3. consolidation: parent pairs with centroid cosine >= CONSOLIDATE_COS are merged only if the merged parent is coherent,
     not mixing, keeps every child's LOO margin >= 0 and has coherence >= the lower of the two.
  4. labels from TF-IDF terms shared by children (names, descriptions, member skills, member evidence quotes) and verified
     ESCO groups (37 suspect links and links not in v1.2.1 excluded). No child-name concatenation; unsupported labels are
     marked UNRESOLVED_LABEL.
Authoritative placement confidence (all versions): CONFIDENT = LOO margin >= 0.02 AND not a split candidate.
Read-only over every input. AI-generated, unreviewed, never human-approved.
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
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_hierarchy_proposal as hp  # noqa: E402
import build_hierarchy_proposal_v2 as v2  # noqa: E402

ROOT = hp.ROOT
V2DIR = v2.OUT
OUT = ROOT / f"reports/sprint4_naming/{hp.RUN}/hierarchy_proposal_v2_1"
VERSION = "hierarchy_proposal_v2_1"
LABEL = v2.LABEL
LOW_MARGIN, NEAR_TIE = v2.LOW_MARGIN, 0.02
LOW_COHERENCE, MIX_SIB, MIX_PAIR = v2.LOW_COHERENCE, v2.MIX_SIB, v2.MIX_PAIR
CONSOLIDATE_COS = 0.92
MAX_ITER, TOP_DEST = 10, 3
EXTRA_STOP = {"ability", "abilities", "including", "related", "use", "using", "various", "work", "working", "skills", "skill",
              "knowledge", "proficiency", "experience", "competence", "application", "applying", "understanding", "practices",
              "management", "systems", "techniques", "processes", "operations", "development", "related", "topics", "tasks"}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


# --------------------------------------------------------------------------------------- group helpers
def group_stats(ctx, g):
    sub = ctx.ccos[np.ix_(g, g)]; iu = np.triu_indices(len(g), 1)
    sib = ctx.N[np.ix_(g, g)].sum() / ctx.n[g].sum()
    return {"coherence": float(sub[iu].mean()), "min_pair": float(sub[iu].min()), "sib": float(sib),
            "mixing": bool(sib < MIX_SIB or sub[iu].min() < MIX_PAIR)}


def centroids(ctx, parents):
    keys = sorted(parents)
    P = np.stack([ctx.sum[parents[k]].sum(0) for k in keys])
    return keys, P


def loo(ctx, parents, j, own):
    """LOO scores of topic j against every parent (own parent without j). Returns (scores dict, margin)."""
    keys, P = centroids(ctx, parents)
    s = {}
    for k, v in zip(keys, P):
        vec = v - ctx.sum[j] if k == own else v
        if np.linalg.norm(vec) > 0:
            s[k] = float(ctx.C[j] @ vec / np.linalg.norm(vec))
    others = [x for kk, x in s.items() if kk != own]
    return s, (s[own] - max(others)) if own in s and others else float("nan")


def support(ctx, j, g):
    return float(ctx.N[j, [x for x in g if x != j]].sum() / ctx.n[j])


def authoritative(ctx, groups):
    """CONFIDENT = LOO margin >= 0.02 and not split-pending (applied identically to every version)."""
    m = v2.loo_margins(ctx, groups)
    conf = sum(1 for j, (mg, _, _) in m.items() if mg >= LOW_MARGIN and ctx.ids[j] not in ctx.split)
    return conf, m


# --------------------------------------------------------------------------------------- refinement
def try_place(ctx, parents, j, exclude=()):
    """Option B for a topic without a parent: best LOO destination passing the same checks as a move (margin > 0)."""
    s = {}
    for k, g in parents.items():
        if k in exclude:
            continue
        v = ctx.sum[g].sum(0); s[k] = float(ctx.C[j] @ v / np.linalg.norm(v))
    for sc, dest in sorted(((v, k) for k, v in s.items()), key=lambda x: (-x[0], x[1]))[:TOP_DEST]:
        trial = {k: list(v) for k, v in parents.items()}; trial[dest] = sorted(trial[dest] + [j])
        _, mg = loo(ctx, trial, j, dest); st = group_stats(ctx, trial[dest]); sup = support(ctx, j, trial[dest])
        if mg > 0 and st["coherence"] >= LOW_COHERENCE and not st["mixing"] and sup > 0:
            return dest, trial, mg, sup
    return None


def refine(ctx, parents):
    parents = {k: sorted(v) for k, v in parents.items()}
    owner = {j: k for k, v in parents.items() for j in v}
    decisions, moved, unresolved = {}, set(), {}
    for it in range(MAX_ITER):
        _, m = authoritative(ctx, [parents[k] for k in sorted(parents)])
        order = sorted((mg, ctx.ids[j], j) for j, (mg, _, _) in m.items() if mg < 0 and j not in moved and j not in unresolved)
        changed = False
        for _, _, j in order:
            if j not in owner:
                continue
            own = owner[j]
            s, mg = loo(ctx, parents, j, own)
            if not (mg < 0):
                continue
            src_sup = support(ctx, j, parents[own])
            cands = sorted(((sc, k) for k, sc in s.items() if k != own), key=lambda x: (-x[0], x[1]))[:TOP_DEST]
            done = False
            for sc, dest in cands:
                trial = {k: list(v) for k, v in parents.items()}
                trial[own] = [x for x in trial[own] if x != j]; trial[dest] = sorted(trial[dest] + [j])
                if len(trial[own]) < 2:
                    trial.pop(own)
                _, new_mg = loo(ctx, trial, j, dest)
                st = group_stats(ctx, trial[dest]); dsup = support(ctx, j, trial[dest])
                ok = new_mg > 0 and new_mg > mg and st["coherence"] >= LOW_COHERENCE and not st["mixing"] and dsup > 0 and dsup >= src_sup
                if ok:
                    decisions[j] = {"decision": "MOVE", "from": own, "to": dest, "margin_before": mg, "margin_after": new_mg,
                                    "support_from": src_sup, "support_to": dsup, "iteration": it,
                                    "reason": f"LOO margin {mg:.3f} -> {new_mg:.3f}; destination coherence {st['coherence']:.3f}, sibling affinity {st['sib']:.3f}"}
                    orphans = [r for r in parents[own] if r != j] if own not in trial else []
                    parents = {k: v for k, v in trial.items()}
                    owner[j] = dest; moved.add(j); changed = done = True
                    for r in orphans:
                        place_orphan(ctx, parents, owner, r, own, decisions, unresolved, moved, it)
                    break
            if not done:
                if mg < -NEAR_TIE:
                    parents[own] = [x for x in parents[own] if x != j]; owner.pop(j)
                    unresolved[j] = "UNRESOLVED_CONFLICT"
                    decisions[j] = {"decision": "UNRESOLVE", "from": own, "to": "", "margin_before": mg, "margin_after": float("nan"),
                                    "support_from": src_sup, "support_to": float("nan"), "iteration": it,
                                    "reason": f"LOO margin {mg:.3f} < -{NEAR_TIE} and no destination passes all move checks"}
                    if len(parents[own]) < 2:
                        for r in parents.pop(own):
                            owner.pop(r, None)
                            place_orphan(ctx, parents, owner, r, own, decisions, unresolved, moved, it)
                    changed = True
                else:
                    decisions.setdefault(j, {"decision": "KEEP_NEAR_TIE", "from": own, "to": own, "margin_before": mg, "margin_after": mg,
                                             "support_from": src_sup, "support_to": src_sup, "iteration": it,
                                             "reason": f"near-tie (margin {mg:.3f} >= -{NEAR_TIE}); no destination passes all checks"})
        if not changed:
            break
    return parents, decisions, unresolved


def place_orphan(ctx, parents, owner, r, old, decisions, unresolved, moved, it):
    owner.pop(r, None)
    res = try_place(ctx, parents, r)
    if res is None:
        unresolved[r] = "UNRESOLVED_PARENT_DISSOLVED"
        decisions[r] = {"decision": "UNRESOLVE_ORPHAN", "from": old, "to": "", "margin_before": float("nan"), "margin_after": float("nan"),
                        "support_from": float("nan"), "support_to": float("nan"), "iteration": it,
                        "reason": "partner left its parent; no destination passes the move checks"}
        return
    dest, trial, mg, sup = res
    parents.clear(); parents.update(trial); owner[r] = dest; moved.add(r)
    decisions[r] = {"decision": "MOVE_ORPHAN", "from": old, "to": dest, "margin_before": float("nan"), "margin_after": mg,
                    "support_from": float("nan"), "support_to": sup, "iteration": it,
                    "reason": f"partner left its parent; placed where LOO margin is {mg:.3f}"}


# --------------------------------------------------------------------------------------- labels
def topic_docs(ctx):
    """(label docs, support docs): label terms come from child names + assigned member skills (noun phrases);
    descriptions and member evidence quotes are used only to count supporting evidence."""
    res = read(hp.NAMES).set_index("topic_id")
    pm = read(v2.ROOT / "data/interim/prepared_mentions.csv")
    al = read(hp.INP / "aliases.csv"); pm["canon"] = pm.skill_key.map(dict(zip(al.alias_key, al.skill_key)))
    ev = pm.groupby("canon").evidence.apply(lambda x: " ".join(x.head(3)))
    label_docs, support_docs = [], []
    for t in ctx.ids:
        mem = ctx.rep.get(t, [])
        label_docs.append(" . ".join([res.at[t, "provisional_name"]] * 2 + mem))
        support_docs.append((res.at[t, "description"] + " " + " ".join(ev.get(k, "") for k in mem)).lower())
    return label_docs, support_docs


def term_matrix(docs):
    stop = list(ENGLISH_STOP_WORDS | EXTRA_STOP)
    vec = TfidfVectorizer(stop_words=stop, ngram_range=(1, 2), min_df=2, max_df=0.05, token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z+#]{2,}\b",
                          sublinear_tf=True)
    M = vec.fit_transform(docs)
    return M, np.array(vec.get_feature_names_out())


def label_parent(ctx, g, M, terms, stats, support_docs):
    sub = M[g].toarray(); present = (sub > 0).sum(0); need = max(2, int(np.ceil(len(g) / 2)))
    score = np.where(present >= need, sub.sum(0), 0)
    order = [i for i in np.argsort(-score) if score[i] > 0]
    picked = []
    for i in order:
        t = terms[i]; tw = set(t.split()); ts = {w[:5] for w in t.split()}
        if len(tw) < len(t.split()) or len(ts) < len(t.split()) or any(ts & {w[:5] for w in p.split()} for p in picked):
            continue                              # no repeated words inside or across picked terms
        picked.append(t)
        if len(picked) == 2:
            break
    evidence_support = {p: sum(p in support_docs[j] for j in g) for p in picked}
    # verified ESCO L2 / L1 groups (suspect + unresolvable links already excluded in ctx.G)
    esco = {}
    for lv in (2, 1):
        groups_l, W, used = ctx.G[lv]; u = used[g].sum(); w = W[g].sum(0)
        if u >= 8 and w.max() / u >= 0.5:
            esco[lv] = (ctx.glabels.get(groups_l[int(w.argmax())], ""), float(w.max() / u), int(u))
    def stem(s):
        return {x[:5] for x in re.findall(r"[a-z]+", s.lower()) if len(x) > 3}
    agree = {lv: bool(stem(lab) & set().union(*(stem(p) for p in picked))) if picked else False for lv, (lab, _, _) in esco.items()}
    reasons = []
    if picked:
        label = " and ".join(p.title() for p in picked)
        lv_ag = next((lv for lv in (2, 1) if agree.get(lv)), None)
        if lv_ag is not None:
            conf, basis = "high", f"shared descriptive terms agreeing with verified ESCO L{lv_ag} group '{esco[lv_ag][0]}'"
        elif esco:
            conf, basis = "medium", "shared descriptive terms (verified ESCO majority exists but does not match)"
            reasons.append(f"ESCO majority '{next(iter(esco.values()))[0]}' disagrees with child terms")
        else:
            conf, basis = "medium", "shared descriptive terms (no verified ESCO majority)"
        state = "PROVISIONAL_LABEL"
    elif esco:
        lv = 2 if 2 in esco else 1
        label, conf, basis, state = esco[lv][0][:1].upper() + esco[lv][0][1:], "low", f"verified ESCO L{lv} majority only", "PROVISIONAL_LABEL"
        reasons.append("no descriptive term shared by the children")
    else:
        label, conf, basis, state = "UNRESOLVED_LABEL", "low", "no shared descriptive term and no verified ESCO majority", "UNRESOLVED_LABEL"
        reasons.append("no supportable label")
    if picked and min(evidence_support.values()) == 0:
        conf = "low"; reasons.append("a label term is not found in any child description or posting quote")
    if stats["mixing"]:
        conf = "low"; reasons.append("member-level mixing")
    if stats["coherence"] < LOW_COHERENCE:
        conf = "low"; reasons.append(f"coherence {stats['coherence']:.3f} < {LOW_COHERENCE}")
    P = ctx.sum[g].sum(0); P /= np.linalg.norm(P)
    mem = ctx.a[ctx.a.t.isin(g)]; reps = mem.skill_key.values[np.argsort(-(ctx.X[mem.index.values] @ P))][:8]
    return {"proposed_label": label, "label_state": state, "label_confidence": conf, "label_basis": basis,
            "supporting_terms": "; ".join(picked),
            "terms_found_in_child_descriptions_or_quotes": "; ".join(f"{p}: {c}/{len(g)}" for p, c in evidence_support.items()), "esco_evidence": "; ".join(f"L{lv} '{a}' {b:.2f} over {c} links" for lv, (a, b, c) in sorted(esco.items())) or "none verified",
            "representative_member_skills": "; ".join(reps), "label_uncertainty": "; ".join(reasons), "needs_label_review": conf == "low" or state == "UNRESOLVED_LABEL"}


# --------------------------------------------------------------------------------------- comparison
def version_metrics(ctx, groups, eligible, labels_conf=None):
    s, pdf, m = v2.evaluate(ctx, groups, eligible)
    conf, _ = authoritative(ctx, groups)
    placed = s["placed"]
    s.update({"confident_authoritative": conf, "low_confidence_authoritative": placed - conf,
              "confident_margin_only": s.pop("confident"), "loo_conflict_rate": s["loo_conflicts"] / placed if placed else float("nan"),
              "low_margin_rate": s["low_margin_0_to_0.02"] / placed if placed else float("nan"),
              "parents_size_2": int((pdf.n_children == 2).sum()) if len(pdf) else 0,
              "parents_size_3_5": int(pdf.n_children.between(3, 5).sum()) if len(pdf) else 0,
              "parents_size_6plus": int((pdf.n_children >= 6).sum()) if len(pdf) else 0})
    s.pop("low_confidence", None)
    if labels_conf is not None:
        for c in ("high", "medium", "low"):
            s[f"labels_{c}"] = int((labels_conf == c).sum())
    return s, pdf, m


def common_population(ctx, versions):
    common = set.intersection(*[{j for g in gs for j in g} for gs in versions.values()])
    rows = []
    for name, gs in versions.items():
        m = v2.loo_margins(ctx, gs); owner = {j: gi for gi, g in enumerate(gs) for j in g}
        mg = np.array([m[j][0] for j in sorted(common)])
        coh = [group_stats(ctx, gs[owner[j]])["coherence"] for j in sorted(common)]
        mix = [group_stats(ctx, gs[owner[j]])["mixing"] for j in sorted(common)]
        rows.append({"version": name, "common_topics": len(common), "conflict_rate": float((mg < 0).mean()),
                     "low_margin_rate": float(((mg >= 0) & (mg < LOW_MARGIN)).mean()), "median_margin": float(np.median(mg)),
                     "confident_authoritative_rate": float(np.mean([(mg_ >= LOW_MARGIN and ctx.ids[j] not in ctx.split) for j, mg_ in zip(sorted(common), mg)])),
                     "mean_coherence_of_parent": float(np.mean(coh)), "share_in_mixing_parent": float(np.mean(mix))})
    return pd.DataFrame(rows), common


def coverage_tradeoff():
    """Existing v2 sweep re-ranked WITHOUT the 60% placement floor (no new sweep)."""
    sw = read(V2DIR / "configuration_sweep.csv")
    for c in sw.columns:
        if c not in ("linkage", "weights", "mode"):
            sw[c] = pd.to_numeric(sw[c], errors="coerce")
    f = sw[(sw.max_parent_size <= 15) & (sw.neighbour_ari >= 0.80) & (sw.parents >= 2)].copy()
    keys = ["confident_share_of_eligible", "mean_parent_coherence", "non_mixing_parent_share", "median_parent_esco_purity_L2"]
    for k in keys:
        f[f"r_{k}"] = f[k].rank(pct=True)
    f["objective_no_floor"] = f[[f"r_{k}" for k in keys]].mean(axis=1)
    f["placed_share_bin"] = pd.cut(f.placed_share_of_eligible, [0, .3, .4, .5, .6, .7, .8, .9, 1.0])
    t = f.sort_values("objective_no_floor", ascending=False).groupby("placed_share_bin", observed=True).head(1)
    cols = ["placed_share_bin", "linkage", "weights", "threshold", "mode", "placed", "confident", "loo_conflicts", "mean_parent_coherence",
            "mixing_parents", "median_parent_esco_purity_L2", "objective_no_floor"]
    best = f.sort_values("objective_no_floor", ascending=False).iloc[0]
    return t[cols].sort_values("placed_share_bin"), best


# --------------------------------------------------------------------------------------- main
def main(out=OUT):
    if out.exists() and any(out.iterdir()):
        sys.exit(f"refusing to overwrite {out}")
    inputs = {"v2_manifest": V2DIR / "manifest.json", "v2_parents": V2DIR / "parent_categories.csv", "v2_hierarchy": V2DIR / "hierarchy_proposal.csv",
              "v2_sweep": V2DIR / "configuration_sweep.csv", "v1_parents": v2.V1 / "parent_categories.csv", "v1_manifest": v2.V1 / "manifest.json",
              "preflight_manifest": v2.PREFLIGHT / "manifest.json", "names": hp.NAMES, "mentions": ROOT / "data/interim/prepared_mentions.csv",
              "aliases": hp.INP / "aliases.csv", "links38": v2.LINKS38}
    miss = [k for k, p in inputs.items() if not Path(p).exists()]
    if miss:
        sys.exit(f"BLOCKED: missing inputs {miss}")
    before = {k: sha256(p) for k, p in inputs.items()}
    for d in (V2DIR, v2.V1, v2.PREFLIGHT):
        man = json.loads((d / "manifest.json").read_text())
        assert all(sha256(d / f) == h for f, h in man["outputs"].items()), f"{d.name} outputs changed"
    ctx = v2.Ctx()
    eligible = [ctx.ti[t] for t in ctx.ids if t not in ctx.excluded]
    p2 = read(inputs["v2_parents"]); p1 = read(inputs["v1_parents"])
    v2parents = {r.parent_id: sorted(ctx.ti[t] for t in r.child_topic_ids.split(";")) for r in p2.itertuples()}
    v1groups = [sorted(ctx.ti[t] for t in r.child_topic_ids.split(";")) for r in p1.itertuples()]
    h2 = read(inputs["v2_hierarchy"]).set_index("topic_id")

    # Step 1: reconcile
    m2 = v2.loo_margins(ctx, [v2parents[k] for k in sorted(v2parents)])
    rec = {"v2_margin_ge_0.02": sum(1 for mg, _, _ in m2.values() if mg >= LOW_MARGIN),
           "v2_margin_ge_0.02_split_pending": sum(1 for j, (mg, _, _) in m2.items() if mg >= LOW_MARGIN and ctx.ids[j] in ctx.split),
           "v2_state_PLACED_CONFIDENT": int((h2.placement_state == "PLACED_CONFIDENT").sum()),
           "v2_manifest_comparison_confident": json.loads(inputs["v2_manifest"].read_text())["metrics_v2"]["confident"]}
    rec["reconciled"] = (rec["v2_margin_ge_0.02"] == rec["v2_manifest_comparison_confident"]
                         and rec["v2_margin_ge_0.02"] - rec["v2_margin_ge_0.02_split_pending"] == rec["v2_state_PLACED_CONFIDENT"])
    assert rec["reconciled"], f"cannot reconcile confidence counts: {rec}"

    # Step 2: conflict analysis for every v2 placed topic
    owner2 = {j: k for k, v in v2parents.items() for j in v}
    crow = []
    for j in sorted(owner2):
        s, mg = loo(ctx, v2parents, j, owner2[j])
        alt = sorted(((sc, k) for k, sc in s.items() if k != owner2[j]), key=lambda x: (-x[0], x[1]))[:3]
        crow.append({"topic_id": ctx.ids[j], "provisional_name": ctx.names[ctx.ids[j]], "v2_parent": owner2[j], "loo_cos_own": round(s[owner2[j]], 4),
                     "alt1": alt[0][1], "alt1_cos": round(alt[0][0], 4), "alt2": alt[1][1] if len(alt) > 1 else "", "alt2_cos": round(alt[1][0], 4) if len(alt) > 1 else "",
                     "margin": round(mg, 4), "class": "CONFLICT" if mg < 0 else "NEAR_TIE" if mg < LOW_MARGIN else "CLEAR",
                     "member_support_own": round(support(ctx, j, v2parents[owner2[j]]), 4), "member_support_alt1": round(support(ctx, j, v2parents[alt[0][1]] + [j]), 4),
                     "split_candidate": ctx.ids[j] in ctx.split})
    conflicts = pd.DataFrame(crow)

    # Step 3: refinement; Step 4: weak pairs + consolidation
    parents, decisions, unresolved = refine(ctx, v2parents)
    label_docs, support_docs = topic_docs(ctx)
    M, terms = term_matrix(label_docs)
    cons = []
    for k in sorted(list(parents)):
        g = parents.get(k)
        if g is None or len(g) != 2:
            continue
        st = group_stats(ctx, g); sub = M[g].toarray(); shared = int(((sub > 0).sum(0) == 2).sum())
        ec = ctx.esco_cos[g[0], g[1]]
        weak = st["sib"] < MIX_SIB and shared == 0 and (np.isnan(ec) or ec < 0.5)
        cons.append({"parent_id": k, "kind": "two_child_pair", "children": ";".join(ctx.ids[x] for x in g), "coherence": round(st["coherence"], 4),
                     "sibling_affinity": round(st["sib"], 4), "shared_descriptive_terms": shared, "esco_profile_cos": None if np.isnan(ec) else round(float(ec), 4),
                     "decision": "DISSOLVE_WEAK_PAIR" if weak else "KEEP_PAIR",
                     "reason": "low member affinity, no shared terms, no ESCO agreement" if weak else "pair supported by member affinity, shared terms or ESCO"})
        if weak:
            for x in parents.pop(k):
                unresolved[x] = "UNRESOLVED_WEAK_PAIR"
    keys, P = centroids(ctx, parents); Pn = P / np.linalg.norm(P, axis=1, keepdims=True); PP = Pn @ Pn.T
    pairs = sorted(((PP[a, b], keys[a], keys[b]) for a in range(len(keys)) for b in range(a + 1, len(keys)) if PP[a, b] >= CONSOLIDATE_COS), reverse=True)
    merged_once = set()
    for c, a, b in pairs:
        if a in merged_once or b in merged_once or a not in parents or b not in parents:
            continue
        mg = sorted(parents[a] + parents[b]); st = group_stats(ctx, mg)
        trial = {k: v for k, v in parents.items() if k not in (a, b)}; trial[a] = mg
        margins_ok = all(loo(ctx, trial, j, a)[1] >= 0 for j in mg)
        ok = st["coherence"] >= max(LOW_COHERENCE, min(group_stats(ctx, parents[a])["coherence"], group_stats(ctx, parents[b])["coherence"])) and not st["mixing"] and margins_ok
        cons.append({"parent_id": f"{a}+{b}", "kind": "near_duplicate_pair", "children": ";".join(ctx.ids[x] for x in mg), "coherence": round(st["coherence"], 4),
                     "sibling_affinity": round(st["sib"], 4), "parent_cos": round(float(c), 4),
                     "decision": "CONSOLIDATE" if ok else "KEEP_SEPARATE",
                     "reason": "merged parent coherent, not mixing, all LOO margins >= 0" if ok else
                               f"merge rejected (coherence {st['coherence']:.3f}, mixing {st['mixing']}, margins_ok {margins_ok})"})
        if ok:
            parents = trial; merged_once |= {a, b}
    cons = pd.DataFrame(cons)

    # final tables
    owner = {j: k for k, v in parents.items() for j in v}
    groups_final = [parents[k] for k in sorted(parents)]
    _, mfin = authoritative(ctx, groups_final)
    pstats = {k: group_stats(ctx, parents[k]) for k in parents}
    plabels = {k: label_parent(ctx, parents[k], M, terms, pstats[k], support_docs) for k in sorted(parents)}
    _, pdf_fin, _ = v2.evaluate(ctx, groups_final, eligible)
    prow = []
    for gi, k in enumerate(sorted(parents)):
        r = pdf_fin.iloc[gi]
        prow.append({"parent_id": k, **plabels[k], "n_children": len(parents[k]), "child_topic_ids": ";".join(ctx.ids[x] for x in parents[k]),
                     "child_names": " | ".join(ctx.names[ctx.ids[x]] for x in parents[k]), "coherence": round(r.coherence, 4),
                     "sibling_affinity": round(r.sibling_affinity, 4), "min_child_pair_cos": round(r.min_child_pair_cos, 4),
                     "parent_separation": round(r.parent_separation, 4), "esco_purity_L1": round(r.esco_purity_L1, 4), "esco_purity_L2": round(r.esco_purity_L2, 4),
                     "esco_coverage": round(r.esco_coverage, 4), "flag_mixing": bool(r.mixing), "flag_low_coherence": bool(r.low_coherence),
                     "suspicious": bool(r.suspicious), "v2_children_same": sorted(parents[k]) == v2parents.get(k), "ai_label": LABEL, "human_approved": False})
    parents_df = pd.DataFrame(prow)
    hrow, drow = [], []
    for t in ctx.ids:
        j = ctx.ti[t]; k = owner.get(j, "")
        if t in ctx.excluded:
            st = "UNRESOLVED_EXCLUDED"
        elif j in unresolved:
            st = unresolved[j]
        elif not k:
            st = "UNRESOLVED_SINGLETON"
        else:
            mg = mfin[j][0]; st = "PLACED_CONFIDENT" if mg >= LOW_MARGIN and t not in ctx.split else "PLACED_LOW_CONFIDENCE"
        hrow.append({"topic_id": t, "provisional_name": ctx.names[t], "parent_id": k, "proposed_parent_label": plabels[k]["proposed_label"] if k else "",
                     "placement_state": st, "loo_margin": round(mfin[j][0], 4) if j in mfin else "", "split_candidate": t in ctx.split,
                     "v2_parent": h2.at[t, "parent_id"], "v2_state": h2.at[t, "placement_state"], "ai_label": LABEL, "human_approved": False})
        if j in owner2:
            d = decisions.get(j)
            if d is None:
                fin = "KEEP" if k == owner2[j] else ("CONSOLIDATED" if k else st)
                d = {"decision": fin, "from": owner2[j], "to": k, "margin_before": m2[j][0], "margin_after": mfin[j][0] if j in mfin else float("nan"),
                     "reason": "no conflict" if fin == "KEEP" else "parent consolidated" if fin == "CONSOLIDATED" else st}
            elif d["decision"] in ("MOVE", "KEEP_NEAR_TIE") and not k:
                d = {**d, "decision": d["decision"] + "_THEN_" + st}
            drow.append({"topic_id": t, "v2_parent": owner2[j], "final_parent": k, "final_state": st, **{x: d.get(x, "") for x in ("decision", "margin_before", "margin_after", "support_from", "support_to", "reason")}})
    h = pd.DataFrame(hrow); dec = pd.DataFrame(drow)

    # comparison (identical definitions)
    v2conf = read(inputs["v2_parents"]).label_confidence
    s1, _, _ = version_metrics(ctx, v1groups, eligible)
    s2, _, _ = version_metrics(ctx, [v2parents[k] for k in sorted(v2parents)], eligible, v2conf)
    s3, _, _ = version_metrics(ctx, groups_final, eligible, parents_df.label_confidence)
    comp = pd.DataFrame([{"metric": k, "v1": s1.get(k), "v2": s2.get(k), "v2_1": s3.get(k)} for k in s3])
    common, cset = common_population(ctx, {"v1": v1groups, "v2": [v2parents[k] for k in sorted(v2parents)], "v2_1": groups_final})
    tradeoff, best_nf = coverage_tradeoff()
    labels_df = parents_df[["parent_id", "proposed_label", "label_state", "label_confidence", "label_basis", "supporting_terms", "esco_evidence",
                            "terms_found_in_child_descriptions_or_quotes", "representative_member_skills", "label_uncertainty", "needs_label_review", "child_names"]]

    # validation
    probs = []
    if len(h) != 374 or not h.topic_id.is_unique: probs.append("coverage/duplicates")
    if (h[h.topic_id.isin(ctx.excluded)].parent_id != "").any(): probs.append("excluded topic placed")
    if h.set_index("topic_id").at["T0104", "placement_state"] != "UNRESOLVED_EXCLUDED": probs.append("T0104 not excluded")
    if (h.placement_state.str.startswith("UNRESOLVED") & (h.parent_id != "")).any(): probs.append("unresolved with parent")
    if not set(h[h.parent_id != ""].parent_id) <= set(parents_df.parent_id): probs.append("missing parent")
    if (parents_df.n_children < 2).any(): probs.append("single-child parent")
    if set(parents_df.parent_id) & set(h.topic_id): probs.append("namespace overlap")
    if parents_df.proposed_label.str.contains(" / |and related topics|miscellaneous|other skills", case=False).any(): probs.append("generic/concatenated label")
    if sum(len(v) for v in parents.values()) != len(owner): probs.append("duplicate placement")
    if h.human_approved.any() or parents_df.human_approved.any(): probs.append("human approval set")

    out.mkdir(parents=True, exist_ok=True)
    files = {"hierarchy_proposal.csv": h, "parent_categories.csv": parents_df, "topic_placement_decisions.csv": dec,
             "placement_conflict_analysis.csv": conflicts, "parent_consolidation_analysis.csv": cons, "label_evidence.csv": labels_df,
             "fair_comparison.csv": comp, "common_population_comparison.csv": common, "coverage_quality_tradeoff.csv": tradeoff}
    for f, d in files.items():
        d.to_csv(out / f, index=False)
    (out / "validation_report.md").write_text(report(rec, conflicts, dec, cons, comp, common, tradeoff, best_nf, parents_df, h, probs), encoding="utf-8")
    assert before == {k: sha256(p) for k, p in inputs.items()}, "an input changed"
    man = {"version": VERSION, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "scripts": {s: sha256(ROOT / "src" / s) for s in ("build_hierarchy_proposal_v2_1.py", "build_hierarchy_proposal_v2.py", "build_hierarchy_proposal.py", "esco_levels.py")},
           "inputs": {k: {"path": str(p).replace(str(Path.home()), "~"), "sha256": before[k]} for k, p in inputs.items()},
           "outputs": {f: sha256(out / f) for f in sorted(os.listdir(out))},
           "parameters": {"LOW_MARGIN": LOW_MARGIN, "NEAR_TIE": NEAR_TIE, "LOW_COHERENCE": LOW_COHERENCE, "MIX_SIB": MIX_SIB, "MIX_PAIR": MIX_PAIR,
                          "CONSOLIDATE_COS": CONSOLIDATE_COS, "MAX_ITER": MAX_ITER, "TOP_DEST": TOP_DEST},
           "confidence_definition": "CONFIDENT = LOO margin >= 0.02 AND not split-pending (all versions)", "reconciliation": rec,
           "metrics": {"v1": s1, "v2": s2, "v2_1": s3}, "common_population_size": len(cset), "structural_problems": probs,
           "decision_counts": dec.decision.value_counts().to_dict(), "ai_label": LABEL, "human_approved": False}
    (out / "manifest.json").write_text(json.dumps(man, indent=1, default=float), encoding="utf-8")
    print(json.dumps({"reconcile": rec, "decisions": man["decision_counts"], "v2": s2, "v2_1": s3, "problems": probs}, indent=1, default=float))
    return man


def report(rec, conflicts, dec, cons, comp, common, tradeoff, best_nf, parents_df, h, probs):
    f = lambda x: f"{x:.3f}" if isinstance(x, float) else str(x)
    L = ["# Hierarchy Proposal v2.1 — validation report", "",
         f"> **{LABEL}.** Targeted refinement of v2 (no new clustering sweep). Frozen inputs, v1, v2 and preflight outputs unchanged. Nothing is human-approved.", "",
         "## 1. Confidence count reconciliation", "",
         f"v2 comparison table used *LOO margin ≥ 0.02* = {rec['v2_margin_ge_0.02']}; v2 placement states also required *not split-pending*: "
         f"{rec['v2_margin_ge_0.02']} − {rec['v2_margin_ge_0.02_split_pending']} split-pending = {rec['v2_state_PLACED_CONFIDENT']}. Reconciled: {rec['reconciled']}.",
         "**Authoritative definition (all versions below): CONFIDENT = LOO margin ≥ 0.02 AND not split-pending.** The margin-only count is reported as `confident_margin_only`.", "",
         "## 2. Conflict diagnosis (v2 placed topics)", "", f"{conflicts['class'].value_counts().to_dict()} (split candidates among conflicts: "
         f"{int(conflicts[conflicts['class'] == 'CONFLICT'].split_candidate.sum())}).", "",
         "## 3–4. Decisions", "", "| Decision | Topics |", "|---|---:|"]
    L += [f"| {k} | {v} |" for k, v in dec.decision.value_counts().items()]
    L += ["", f"Pair / consolidation analysis: {cons.decision.value_counts().to_dict() if len(cons) else {}}.", "",
          "## 5. Labels", "", f"States {parents_df.label_state.value_counts().to_dict()}; confidence {parents_df.label_confidence.value_counts().to_dict()}.", "",
          "## 6. Fair comparison (identical corrected definitions)", "", "| Metric | v1 | v2 | v2.1 |", "|---|---:|---:|---:|"]
    L += [f"| {r.metric} | {f(r.v1)} | {f(r.v2)} | {f(r.v2_1)} |" for r in comp.itertuples()]
    L += ["", "### Common placed-topic population", "", "| Version | Topics | Conflict rate | Low-margin rate | Median margin | Confident rate | Mean parent coherence | In mixing parent |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    L += [f"| {r.version} | {r.common_topics} | {r.conflict_rate:.3f} | {r.low_margin_rate:.3f} | {r.median_margin:.3f} | {r.confident_authoritative_rate:.3f} | "
          f"{r.mean_coherence_of_parent:.3f} | {r.share_in_mixing_parent:.3f} |" for r in common.itertuples()]
    L += ["", "### Coverage–quality trade-off (v2 sweep re-ranked without the 60% floor; no new sweep)", "",
          "| Placed share | Config | Placed | Confident (margin) | LOO conflicts | Coherence | Mixing parents | ESCO L2 |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    L += [f"| {r.placed_share_bin} | {r.linkage}/{r.weights}/{r.threshold}/{r.mode} | {r.placed:.0f} | {r.confident:.0f} | {r.loo_conflicts:.0f} | "
          f"{r.mean_parent_coherence:.3f} | {r.mixing_parents:.0f} | {r.median_parent_esco_purity_L2:.3f} |" for r in tradeoff.itertuples()]
    L += ["", f"Without the floor the top-ranked configuration would be {best_nf.linkage}/{best_nf.weights}/{best_nf.threshold}/{best_nf['mode']} "
          f"placing {best_nf.placed:.0f} topics — higher quality scores only by placing far fewer topics.", "",
          "## 7. Validation", "", f"Placement states: {h.placement_state.value_counts().to_dict()}.", "", f"**Structural problems: {probs or 'none'}**"]
    return "\n".join(L)


if __name__ == "__main__":
    main()
