"""Sprint 4 Phase 3: Hierarchy Proposal v2 — corrected evaluation, configuration sweep, construction, naming,
v1 comparison and grandparent feasibility (read-only over every input; v1 and preflight outputs are never touched).

    .venv/bin/python src/build_hierarchy_proposal_v2.py

Corrections over v1 (from hierarchy_v2_preflight_v1):
  * placement confidence uses LEAVE-ONE-OUT child-to-parent similarity (the child is removed from its own parent)
  * ESCO profiles / purity use explicit skills-hierarchy levels (src/esco_levels.py), multi-parent aware
  * ESCO signals exclude links whose URI is not in v1.2.1 (the 212 discrepancies) and the 37 suspect accepted links
    (Phase 3 audit verdicts CONFIRMED_INCORRECT, LIKELY_INCORRECT, CONTEXT_DEPENDENT; includes the 3 'exact' matches)
  * suspicious parents include member-level mixing (sibling member affinity, weakest child pair)
Metric definitions (never mixed):
  coherence          mean pairwise cosine of child-topic centroids within a parent (child-child)
  loo_margin         cos(child, own parent without the child) - max cos(child, other parent)   (child-parent, LOO)
  parent_separation  cosine of a parent centroid to its nearest other parent centroid (parent-parent)
  sibling_affinity   share of a parent's assigned members whose nearest other topic is a sibling (member level)
  esco_purity_L1/L2  corrected purity (esco_levels.purity semantics) of the parent's usable ESCO links
  esco_coverage      share of the parent's assigned members with a usable ESCO link
Selection criteria are fixed in code (SELECTION) before the sweep is run; see the validation report.
Everything is AI-generated and unreviewed; nothing is human-approved.
"""
import hashlib
import itertools
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.metrics import adjusted_rand_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_hierarchy_proposal as hp  # noqa: E402
import esco_levels as el  # noqa: E402

ROOT = hp.ROOT
RUN = hp.RUN
V1 = hp.OUT
PREFLIGHT = ROOT / f"reports/sprint4_naming/{RUN}/hierarchy_v2_preflight_v1"
LINKS38 = ROOT / f"reports/sprint4_naming/{RUN}/topic_quality_review_v1/phase2_phase3_audit_v1/reference_link_verification_38.csv"
OUT = ROOT / f"reports/sprint4_naming/{RUN}/hierarchy_proposal_v2"
VERSION = "hierarchy_proposal_v2"
LABEL = "AI-GENERATED, UNREVIEWED (pending human approval)"
SUSPECT_VERDICTS = {"CONFIRMED_INCORRECT", "LIKELY_INCORRECT", "CONTEXT_DEPENDENT"}
LOW_MARGIN = 0.02
MIX_SIB, MIX_PAIR = 0.15, 0.75          # same thresholds as the preflight
LOW_COHERENCE = 0.82                    # absolute, fixed before the sweep (v1 p10 was 0.81)
NEAR_DUP_PARENT = 0.95
ESCO_MIN_LINKS = 3

# configuration space (deterministic order)
LINKAGES = ("average", "complete", "weighted")
WEIGHTS = {"v1_70_15_15": (0.70, 0.15, 0.15), "w60_20_20": (0.60, 0.20, 0.20), "w50_30_20": (0.50, 0.30, 0.20), "w80_10_10": (0.80, 0.10, 0.10)}
THRESHOLDS = tuple(round(x, 3) for x in np.arange(0.15, 0.501, 0.01))
CONSERVATIVE = ("keep_conflicts_low_confidence", "unplace_loo_conflicts")
SELECTION = {   # fixed before results are seen
    "hard": {"max_parent_size": 15, "min_placed_share_of_eligible": 0.60, "min_threshold_neighbour_ari": 0.80},
    "objective": "mean percentile rank of: confident_share_of_eligible, mean_parent_coherence, non_mixing_parent_share, "
                 "median_parent_esco_purity_L2 (higher is better for all four)",
    "tie_break": "v1 weights, then average linkage, then smaller threshold, then keep_conflicts",
}
GENERIC = {"management", "systems", "system", "skills", "skill", "knowledge", "operations", "processes", "process",
           "and", "of", "the", "for", "in", "with", "related", "topics", "techniques", "practices", "development"}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


# ======================================================================================= context
class Ctx:
    """All frozen evidence needed to build and evaluate any parent assignment, precomputed once."""

    def __init__(self):
        I, F = hp.INP, hp.FEAT
        self.ids = read(F / "topic_ids.csv").topic_id.tolist(); self.ti = {t: i for i, t in enumerate(self.ids)}
        sk = read(I / "skills.csv"); V = np.load(I / "vectors.npy").astype(np.float64)
        mem = read(I / "memberships.csv"); a = mem[mem.state == "assigned"].copy()
        row = dict(zip(sk.skill_key, sk.vector_row.astype(int)))
        a["vi"] = a.skill_key.map(row); a["t"] = a.topic_id.map(self.ti)
        self.a = a.reset_index(drop=True); self.X = V[a.vi.values]; self.mt = a.t.values
        k = len(self.ids)
        self.C = np.load(F / "topic_centroids.npy").astype(np.float64)
        self.sum = np.zeros((k, V.shape[1])); np.add.at(self.sum, self.mt, self.X)
        self.n = np.bincount(self.mt, minlength=k).astype(float)
        S = self.X @ self.C.T; S[np.arange(len(S)), self.mt] = -np.inf; self.nearest_other = S.argmax(1)
        self.N = np.zeros((k, k)); np.add.at(self.N, (self.mt, self.nearest_other), 1.0)    # member-level cross-topic counts
        self.ccos = self.C @ self.C.T
        self.aff = hp.member_affinity(self.X, self.mt, self.C)
        self.names = read(hp.NAMES).set_index("topic_id").provisional_name
        val = read(hp.VALIDITY).set_index("topic_id"); aud = read(hp.AUDIT).set_index("topic_id")
        act = aud.ai_review_action.str.split(" ").str[0]
        self.excluded = {t for t in self.ids if val.at[t, "hierarchy_treatment"] in hp.EXCLUDE_TREATMENT or act.get(t) == "INVESTIGATE_CLUSTER"}
        self.split = {t for t in self.ids if val.at[t, "hierarchy_treatment"] in hp.SPLIT_FLAGS or act.get(t) == "POTENTIAL_SPLIT"}
        self.treatment = val.hierarchy_treatment; self.audit_action = aud.ai_review_action
        # ESCO: corrected levels, excluding unresolvable and suspect links
        self.level_of, self.parents_esco, self.glabels, self.esco_skills = el.load(hp.ESCO)
        RL = read(I / "reference_links.csv")
        suspect = set(read(LINKS38).query("ai_verdict in @SUSPECT_VERDICTS", local_dict={"SUSPECT_VERDICTS": SUSPECT_VERDICTS}).canonical_skill_key)
        self.suspect = suspect
        lk = self.a.merge(RL, on="skill_key")
        lk = lk[(lk.verdict == "known_skill") & lk.source.str.startswith("ESCO")]
        self.esco_excluded = {"uri_not_in_v121": int((~lk.ref_id.isin(self.esco_skills)).sum()),
                              "suspect_accepted": int(lk.skill_key.isin(suspect).sum())}
        lk = lk[lk.ref_id.isin(self.esco_skills) & ~lk.skill_key.isin(suspect)]
        self.G = {}
        for lv in (1, 2):
            groups = sorted({g for u in lk.ref_id for g in el.ancestors_at_level(u, lv, self.level_of, self.parents_esco)})
            gi = {g: i for i, g in enumerate(groups)}
            W = np.zeros((k, len(groups))); used = np.zeros(k)
            for t, u in zip(lk.t.values, lk.ref_id.values):
                gs = el.ancestors_at_level(u, lv, self.level_of, self.parents_esco)
                if gs:
                    used[t] += 1
                    for g in gs:
                        W[t, gi[g]] += 1 / len(gs)
            self.G[lv] = (groups, W, used)
        groups2, W2, used2 = self.G[2]
        self.esco_cos = hp.profile_cosine(W2, used2 >= ESCO_MIN_LINKS)
        self.rep = {t: g.sort_values("vi").skill_key.tolist() for t, g in self.a.groupby("topic_id")}
        self.links_by_skill = lk.groupby("skill_key").ref_id.first().to_dict()


# ======================================================================================= construction
def distance(ctx, idx, w):
    wc, wm, we = w
    da = 1 - ctx.ccos[np.ix_(idx, idx)]
    db = 1 - np.minimum(ctx.aff[np.ix_(idx, idx)] / hp.AFFINITY_SCALE, 1.0)
    es = ctx.esco_cos[np.ix_(idx, idx)]; has = ~np.isnan(es)
    D = (wc * da + wm * db + np.where(has, we * (1 - np.nan_to_num(es)), 0.0)) / np.where(has, wc + wm + we, wc + wm)
    D = (D + D.T) / 2; np.fill_diagonal(D, 0.0)
    return np.clip(D, 0, None)


def partition(ctx, link, w, t):
    E = [ctx.ti[x] for x in ctx.ids if x not in ctx.excluded]
    Z = linkage(squareform(distance(ctx, E, w), checks=False), method=link)
    lab = fcluster(Z, t=t, criterion="distance")
    return E, lab


def loo_margins(ctx, groups):
    """groups: list of lists of topic indices. Returns {topic: (margin, own_loo, best_other_group_index)}."""
    if not groups:
        return {}
    P = np.stack([ctx.sum[g].sum(0) for g in groups]); Pn = P / np.linalg.norm(P, axis=1, keepdims=True)
    out = {}
    for gi, g in enumerate(groups):
        for j in g:
            own = P[gi] - ctx.sum[j]; own_cos = float(ctx.C[j] @ own / np.linalg.norm(own))
            s = Pn @ ctx.C[j]; s[gi] = -np.inf
            bo = int(s.argmax()); out[j] = (own_cos - float(s[bo]), own_cos, bo)
    return out


def assign(ctx, link, w, t, mode):
    E, lab = partition(ctx, link, w, t)
    cl = {}
    for j, c in zip(E, lab):
        cl.setdefault(c, []).append(j)
    groups = sorted((sorted(v) for v in cl.values() if len(v) >= 2), key=lambda v: v[0])
    removed = set()
    if mode == "unplace_loo_conflicts":
        for _ in range(10):                      # deterministic fixed-point: drop children with LOO margin < 0
            m = loo_margins(ctx, groups)
            bad = {j for j, (mg, _, _) in m.items() if mg < 0}
            if not bad:
                break
            removed |= bad                       # only true LOO conflicts; partners left alone become singletons
            groups = [g for g in ([x for x in g if x not in bad] for g in groups) if len(g) >= 2]
    placed = {j for g in groups for j in g}
    conflict_unplaced = removed - placed
    return groups, placed, conflict_unplaced, E


# ======================================================================================= evaluation (shared v1/v2)
def evaluate(ctx, groups, eligible):
    """Corrected metrics for any parent assignment (groups = lists of topic indices)."""
    m = loo_margins(ctx, groups)
    P = np.stack([ctx.sum[g].sum(0) for g in groups]) if groups else np.zeros((0, ctx.C.shape[1]))
    Pn = P / np.linalg.norm(P, axis=1, keepdims=True) if groups else P
    PP = Pn @ Pn.T if groups else np.zeros((0, 0)); np.fill_diagonal(PP, -1) if groups else None
    prow = []
    for gi, g in enumerate(groups):
        sub = ctx.ccos[np.ix_(g, g)]; iu = np.triu_indices(len(g), 1)
        sib = ctx.N[np.ix_(g, g)].sum() / ctx.n[g].sum()
        r = {"gi": gi, "n_children": len(g), "coherence": float(sub[iu].mean()), "min_child_pair_cos": float(sub[iu].min()),
             "sibling_affinity": float(sib), "parent_separation": float(PP[gi].max()) if len(groups) > 1 else float("nan"),
             "nearest_parent_gi": int(PP[gi].argmax()) if len(groups) > 1 else -1,
             "split_pending_children": sum(ctx.ids[j] in ctx.split for j in g)}
        for lv in (1, 2):
            groups_l, W, used = ctx.G[lv]; wsum = W[g].sum(0); u = used[g].sum()
            r[f"esco_purity_L{lv}"] = float(wsum.max() / u) if u >= ESCO_MIN_LINKS else float("nan")
            r[f"esco_top_L{lv}"] = ctx.glabels.get(groups_l[int(wsum.argmax())], "") if u >= ESCO_MIN_LINKS else ""
            r[f"esco_used_L{lv}"] = int(u)
        r["esco_coverage"] = float(ctx.G[2][2][g].sum() / ctx.n[g].sum())
        r["mixing"] = bool(sib < MIX_SIB or r["min_child_pair_cos"] < MIX_PAIR)
        r["low_coherence"] = r["coherence"] < LOW_COHERENCE
        r["near_duplicate_parent"] = bool(r["parent_separation"] >= NEAR_DUP_PARENT)
        r["many_split_pending"] = r["split_pending_children"] >= 2
        r["suspicious"] = r["mixing"] or r["low_coherence"] or r["near_duplicate_parent"] or r["many_split_pending"]
        prow.append(r)
    pdf = pd.DataFrame(prow)
    margins = np.array([v[0] for v in m.values()]) if m else np.array([])
    placed = len(m); conf = int((margins >= LOW_MARGIN).sum()) if placed else 0
    summ = {"parents": len(groups), "eligible": len(eligible), "placed": placed, "confident": conf,
            "low_confidence": placed - conf, "loo_conflicts": int((margins < 0).sum()) if placed else 0,
            "low_margin_0_to_0.02": int(((margins >= 0) & (margins < LOW_MARGIN)).sum()) if placed else 0,
            "unresolved": len(ctx.ids) - placed, "confident_share_of_eligible": conf / len(eligible),
            "placed_share_of_eligible": placed / len(eligible),
            "median_loo_margin": float(np.median(margins)) if placed else float("nan"),
            "mean_parent_coherence": float(pdf.coherence.mean()) if len(pdf) else float("nan"),
            "median_parent_separation": float(pdf.parent_separation.median()) if len(pdf) else float("nan"),
            "mixing_parents": int(pdf.mixing.sum()) if len(pdf) else 0,
            "non_mixing_parent_share": float(1 - pdf.mixing.mean()) if len(pdf) else float("nan"),
            "median_parent_esco_purity_L1": float(pdf.esco_purity_L1.median()) if len(pdf) else float("nan"),
            "median_parent_esco_purity_L2": float(pdf.esco_purity_L2.median()) if len(pdf) else float("nan"),
            "mean_parent_esco_coverage": float(pdf.esco_coverage.mean()) if len(pdf) else float("nan"),
            "suspicious_parents": int(pdf.suspicious.sum()) if len(pdf) else 0,
            "near_duplicate_parent_pairs": int((np.triu(PP, 1) >= NEAR_DUP_PARENT).sum()) if len(groups) > 1 else 0,
            "max_parent_size": int(pdf.n_children.max()) if len(pdf) else 0,
            "median_parent_size": float(pdf.n_children.median()) if len(pdf) else float("nan"),
            "parents_with_split_pending": int((pdf.split_pending_children > 0).sum()) if len(pdf) else 0}
    return summ, pdf, m


def sweep(ctx):
    rows, parts = [], {}
    for link, (wn, w) in itertools.product(LINKAGES, WEIGHTS.items()):
        labs = {}
        for t in THRESHOLDS:
            E, lab = partition(ctx, link, w, t); labs[t] = lab
        for i, t in enumerate(THRESHOLDS):
            nb = [labs[THRESHOLDS[k]] for k in (i - 1, i + 1) if 0 <= k < len(THRESHOLDS)]
            ari = min(adjusted_rand_score(labs[t], x) for x in nb)
            for mode in CONSERVATIVE:
                groups, placed, cu, E = assign(ctx, link, w, t, mode)
                s, _, _ = evaluate(ctx, groups, E)
                rows.append({"linkage": link, "weights": wn, "threshold": t, "mode": mode, "neighbour_ari": round(ari, 4), **s})
    df = pd.DataFrame(rows)
    h = SELECTION["hard"]
    df["feasible"] = (df.max_parent_size <= h["max_parent_size"]) & (df.placed_share_of_eligible >= h["min_placed_share_of_eligible"]) \
        & (df.neighbour_ari >= h["min_threshold_neighbour_ari"]) & (df.parents >= 2)
    f = df[df.feasible].copy()
    keys = ["confident_share_of_eligible", "mean_parent_coherence", "non_mixing_parent_share", "median_parent_esco_purity_L2"]
    for k in keys:
        f[f"rank_{k}"] = f[k].rank(pct=True)
    f["objective"] = f[[f"rank_{k}" for k in keys]].mean(axis=1)
    f["tb_w"] = (f.weights != "v1_70_15_15").astype(int); f["tb_l"] = f.linkage.map({x: i for i, x in enumerate(LINKAGES)})
    f["tb_m"] = (f["mode"] != CONSERVATIVE[0]).astype(int)
    f = f.sort_values(["objective", "tb_w", "tb_l", "threshold", "tb_m"], ascending=[False, True, True, True, True])
    df = df.merge(f[["linkage", "weights", "threshold", "mode", "objective"]], how="left", on=["linkage", "weights", "threshold", "mode"])
    best = f.iloc[0]
    return df, (best.linkage, best.weights, float(best.threshold), best["mode"])


# ======================================================================================= naming
def stems(s):
    return {w[:5] for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 2 and w not in GENERIC}


def name_parent(ctx, g, r):
    """Provisional label from child names, member skills and verified ESCO groups. Never 'and related topics'."""
    kids = [ctx.ids[j] for j in g]; cn = [ctx.names[t] for t in kids]
    P = ctx.sum[g].sum(0); P = P / np.linalg.norm(P)
    mem = ctx.a[ctx.a.t.isin(g)]; sc = ctx.X[mem.index.values] @ P
    reps = mem.skill_key.values[np.argsort(-sc)][:8].tolist()
    words = Counter(w for n in cn for w in {x for x in re.findall(r"[A-Za-z][A-Za-z+/#.-]*", n) if x.lower() not in GENERIC and len(x) > 2})
    shared = [w for w, c in words.most_common() if c >= max(2, (len(cn) + 1) // 2)][:3]
    esco = r["esco_top_L2"]; pur = r["esco_purity_L2"]; used = r["esco_used_L2"]
    esco_ok = bool(esco) and not np.isnan(pur) and pur >= 0.5 and used >= 8
    esco_agrees = esco_ok and bool(stems(esco) & (set().union(*(stems(n) for n in cn)) | set().union(*(stems(x) for x in reps))))
    reasons = []
    if shared:
        label = " ".join(shared) + ": " + "; ".join(n for n in cn[:4]) + (f" (+{len(cn) - 4})" if len(cn) > 4 else "")
        basis = "shared child-name terms"
    elif esco_agrees:
        label = f"{esco[0].upper()}{esco[1:]}: " + "; ".join(cn[:4]) + (f" (+{len(cn) - 4})" if len(cn) > 4 else "")
        basis = "verified ESCO Level 2 group agreeing with child names / member skills"
    else:
        label = " / ".join(cn[:4]) + (f" (+{len(cn) - 4})" if len(cn) > 4 else "")
        basis = "child topic names only (no shared terms, no agreeing ESCO group)"
        reasons.append("no shared child-name terms and no agreeing verified ESCO group")
    conf = "high" if (shared and esco_agrees) else "medium" if (shared or esco_agrees) else "low"
    if r["mixing"]:
        conf = "low"; reasons.append("member-level mixing flag")
    if r["low_coherence"]:
        conf = "low"; reasons.append(f"coherence {r['coherence']:.3f} < {LOW_COHERENCE}")
    if esco_ok and not esco_agrees:
        reasons.append(f"ESCO majority '{esco}' does not match child names or member skills (not used)")
    if not esco_ok:
        reasons.append("no verified ESCO Level 2 majority (purity < 0.5 or < 8 usable links)")
    return {"proposed_label": label, "label_basis": basis, "label_confidence": conf,
            "needs_label_review": conf == "low", "label_uncertainty": "; ".join(reasons),
            "representative_member_skills": "; ".join(reps),
            "reference_evidence": (f"ESCO L2 '{esco}' purity {pur:.2f} over {used} usable links" if esco else "none usable")}


# ======================================================================================= v1 recomputation
def v1_groups(ctx):
    p = read(V1 / "parent_categories.csv")
    return [sorted(ctx.ti[t] for t in r.child_topic_ids.split(";")) for r in p.itertuples()], p


def grandparent_feasibility(ctx, groups, pdf):
    """Cluster v2 parent centroids (average linkage, cosine) at a few cuts; report ESCO L1 consistency and mixing."""
    if len(groups) < 4:
        return pd.DataFrame()
    P = np.stack([ctx.sum[g].sum(0) for g in groups]); P /= np.linalg.norm(P, axis=1, keepdims=True)
    D = np.clip(1 - P @ P.T, 0, None); np.fill_diagonal(D, 0)
    Z = linkage(squareform((D + D.T) / 2, checks=False), method="average")
    rows = []
    for t in (0.06, 0.08, 0.10, 0.12, 0.15):
        lab = fcluster(Z, t=t, criterion="distance"); gp = {}
        for gi, c in enumerate(lab):
            gp.setdefault(c, []).append(gi)
        multi = [v for v in gp.values() if len(v) >= 2]
        pur = []
        for v in multi:
            topics = [j for gi in v for j in groups[gi]]
            groups_l, W, used = ctx.G[1]; u = used[topics].sum()
            if u >= ESCO_MIN_LINKS:
                pur.append(W[topics].sum(0).max() / u)
        rows.append({"cut": t, "grandparents": len(multi), "parents_grouped": sum(map(len, multi)),
                     "parents_alone": sum(len(v) == 1 for v in gp.values()),
                     "median_grandparent_esco_L1_purity": float(np.median(pur)) if pur else float("nan"),
                     "largest_grandparent": max(map(len, gp.values()))})
    return pd.DataFrame(rows)


# ======================================================================================= main
def main(out=OUT):
    if out.exists() and any(out.iterdir()):
        sys.exit(f"refusing to overwrite {out}")
    inputs = {"v1_manifest": V1 / "manifest.json", "v1_parents": V1 / "parent_categories.csv", "v1_hierarchy": V1 / "hierarchy_proposal.csv",
              "preflight_manifest": PREFLIGHT / "manifest.json", "links38": LINKS38,
              "skills": hp.INP / "skills.csv", "vectors": hp.INP / "vectors.npy", "memberships": hp.INP / "memberships.csv",
              "reference_links": hp.INP / "reference_links.csv", "topic_centroids": hp.FEAT / "topic_centroids.npy",
              "topic_ids": hp.FEAT / "topic_ids.csv", "names": hp.NAMES, "validity": hp.VALIDITY, "audit_metrics": hp.AUDIT,
              "esco_skills": hp.ESCO / "skills_en.csv", "esco_hierarchy": hp.ESCO / "skillsHierarchy_en.csv",
              "esco_broader": hp.ESCO / "broaderRelationsSkillPillar_en.csv"}
    miss = [k for k, p in inputs.items() if not Path(p).exists()]
    if miss:
        sys.exit(f"BLOCKED: missing inputs {miss}")
    before = {k: sha256(p) for k, p in inputs.items()}
    pre = json.loads(inputs["preflight_manifest"].read_text())
    assert pre["ready_for_v2"] is True and all(sha256(PREFLIGHT / f) == h for f, h in pre["outputs"].items()), "preflight not READY / changed"
    m1 = json.loads(inputs["v1_manifest"].read_text())
    assert all(sha256(V1 / f) == h for f, h in m1["outputs"].items()), "v1 outputs changed"
    for d, f in ((hp.INP, "manifest.json"), (hp.FEAT, "manifest.json")):
        for name, hsh in json.loads((d / f).read_text())["files_sha256"].items():
            assert sha256(d / name) == hsh, f"frozen {d.name}/{name} changed"

    ctx = Ctx()
    assert len(ctx.ids) == 374 and len(ctx.a) == 8646 and len(ctx.suspect) == 37
    sw, (link, wn, thr, mode) = sweep(ctx)
    groups, placed, conflict_unplaced, E = assign(ctx, link, WEIGHTS[wn], thr, mode)
    s2, pdf2, m2 = evaluate(ctx, groups, E)
    g1, p1 = v1_groups(ctx); s1, pdf1, m1m = evaluate(ctx, g1, [ctx.ti[x] for x in ctx.ids if x not in ctx.excluded])

    # parents
    prow = []
    for r in pdf2.to_dict("records"):
        g = groups[r["gi"]]; pid = f"Q{r['gi'] + 1:03d}"
        nm = name_parent(ctx, g, r)
        prow.append({"parent_id": pid, **nm, "n_children": r["n_children"], "child_topic_ids": ";".join(ctx.ids[j] for j in g),
                     "child_names": " | ".join(ctx.names[ctx.ids[j]] for j in g),
                     "coherence": round(r["coherence"], 4), "min_child_pair_cos": round(r["min_child_pair_cos"], 4),
                     "sibling_affinity": round(r["sibling_affinity"], 4), "parent_separation": round(r["parent_separation"], 4),
                     "nearest_parent": f"Q{r['nearest_parent_gi'] + 1:03d}" if r["nearest_parent_gi"] >= 0 else "",
                     "esco_purity_L1": round(r["esco_purity_L1"], 4), "esco_top_L1": r["esco_top_L1"],
                     "esco_purity_L2": round(r["esco_purity_L2"], 4), "esco_top_L2": r["esco_top_L2"],
                     "esco_usable_links_L2": r["esco_used_L2"], "esco_coverage": round(r["esco_coverage"], 4),
                     "split_pending_children": r["split_pending_children"],
                     "flag_mixing": r["mixing"], "flag_low_coherence": r["low_coherence"],
                     "flag_near_duplicate_parent": r["near_duplicate_parent"], "flag_many_split_pending": r["many_split_pending"],
                     "suspicious": r["suspicious"], "ai_label": LABEL, "human_approved": False})
    parents = pd.DataFrame(prow)
    pid_of = {j: f"Q{gi + 1:03d}" for gi, g in enumerate(groups) for j in g}
    plab = parents.set_index("parent_id").proposed_label
    hrows = []
    for t in ctx.ids:
        j = ctx.ti[t]
        if t in ctx.excluded:
            st, note = "UNRESOLVED_EXCLUDED", ("validity: exclude_until_reclustered" if ctx.treatment[t] in hp.EXCLUDE_TREATMENT else f"audit: {ctx.audit_action[t]}")
        elif j in conflict_unplaced:
            st, note = "UNRESOLVED_LOO_CONFLICT", "closer to another parent once removed from its own (leave-one-out)"
        elif j not in pid_of:
            st, note = "UNRESOLVED_SINGLETON", f"no partner within threshold {thr}"
        else:
            mg = m2[j][0]
            low = t in ctx.split or mg < LOW_MARGIN
            st = "PLACED_LOW_CONFIDENCE" if low else "PLACED_CONFIDENT"
            note = "; ".join(x for x, on in (("split pending", t in ctx.split), (f"LOO margin {mg:.3f} < {LOW_MARGIN}", mg < LOW_MARGIN)) if on)
        hrows.append({"topic_id": t, "provisional_name": ctx.names[t], "parent_id": pid_of.get(j, ""), "proposed_parent_label": plab.get(pid_of.get(j, ""), ""),
                      "placement_state": st, "placement_note": note,
                      "loo_cos_to_own_parent": round(m2[j][1], 4) if j in m2 else "", "loo_margin": round(m2[j][0], 4) if j in m2 else "",
                      "best_other_parent": f"Q{m2[j][2] + 1:03d}" if j in m2 else "",
                      "validity_treatment": ctx.treatment[t], "audit_action": ctx.audit_action[t], "n_assigned": int(ctx.n[j]),
                      "v1_parent": "", "ai_label": LABEL, "human_approved": False})
    h = pd.DataFrame(hrows)
    v1h = read(V1 / "hierarchy_proposal.csv").set_index("topic_id")
    h["v1_parent"] = h.topic_id.map(v1h.parent_id); h["v1_state"] = h.topic_id.map(v1h.placement_state)
    unresolved = h[h.placement_state != "PLACED_CONFIDENT"].copy()

    # validation
    probs = []
    if len(h) != 374 or not h.topic_id.is_unique: probs.append("coverage/duplicates")
    pl = h[h.parent_id != ""]
    if not set(pl.parent_id) <= set(parents.parent_id): probs.append("missing parent reference")
    if (parents.n_children < 2).any(): probs.append("single-child parent")
    if set(parents.parent_id) & set(h.topic_id): probs.append("namespace overlap (cycle risk)")
    if (h.placement_state.str.startswith("UNRESOLVED") & (h.parent_id != "")).any(): probs.append("unresolved topic with parent")
    if (h[h.topic_id.isin(ctx.excluded)].parent_id != "").any(): probs.append("excluded topic forced into a parent")
    if pl.groupby("parent_id").topic_id.apply(set).to_dict() != {r.parent_id: set(r.child_topic_ids.split(";")) for r in parents.itertuples()}:
        probs.append("parent-child lists inconsistent")
    if parents.proposed_label.str.contains("and related topics|miscellaneous|other skills", case=False).any(): probs.append("generic parent label")
    if h.human_approved.any() or parents.human_approved.any(): probs.append("human approval set")

    # known v1 problem parents
    known = []
    for pid in ("P035", "P046", "P052", "P080", "P085"):
        kids = p1.set_index("parent_id").at[pid, "child_topic_ids"].split(";")
        v2p = sorted({pid_of.get(ctx.ti[t], "unresolved") for t in kids})
        known.append({"v1_parent": pid, "v1_children": ";".join(kids), "v1_child_names": " | ".join(ctx.names[t] for t in kids),
                      "v1_flagged_suspicious_v1rules": pid in set(re.findall(r"^\| (P\d{3}) \|", (V1 / "validation_report.md").read_text(), re.M)),
                      "v1_mixing_corrected": bool(pdf1.mixing.values[p1.parent_id.tolist().index(pid)]),
                      "v2_placement": "; ".join(f"{ctx.ids[ctx.ti[t]]}->{pid_of.get(ctx.ti[t], h.set_index('topic_id').at[t, 'placement_state'])}" for t in kids),
                      "children_still_together_in_v2": len(v2p) == 1 and v2p[0] != "unresolved",
                      "v2_parents_suspicious": "; ".join(f"{q}:{bool(parents.set_index('parent_id').at[q, 'suspicious'])}" for q in v2p if q != "unresolved")})
    known = pd.DataFrame(known)
    # split-candidate sensitivity: metrics with split-pending topics removed from parents
    g_ns = [x for x in ([j for j in g if ctx.ids[j] not in ctx.split] for g in groups) if len(x) >= 2]
    s_ns, _, _ = evaluate(ctx, g_ns, [j for j in E if ctx.ids[j] not in ctx.split])
    comp = pd.DataFrame([{"metric": k, "v1": s1[k], "v2": s2[k], "v2_without_split_candidates": s_ns.get(k)} for k in s2])
    better_if_higher = {"confident", "confident_share_of_eligible", "placed", "placed_share_of_eligible", "median_loo_margin", "mean_parent_coherence",
                        "non_mixing_parent_share", "median_parent_esco_purity_L1", "median_parent_esco_purity_L2", "mean_parent_esco_coverage"}
    better_if_lower = {"loo_conflicts", "low_margin_0_to_0.02", "mixing_parents", "suspicious_parents", "near_duplicate_parent_pairs",
                       "median_parent_separation", "low_confidence", "unresolved"}
    comp["direction"] = comp.metric.map(lambda k: "higher_better" if k in better_if_higher else "lower_better" if k in better_if_lower else "context")
    def verdict(r):
        if r.direction == "context" or pd.isna(r.v1) or pd.isna(r.v2) or r.v1 == r.v2: return "same/context"
        up = r.v2 > r.v1
        return "improved" if (up and r.direction == "higher_better") or (not up and r.direction == "lower_better") else "worse"
    comp["v2_vs_v1"] = comp.apply(verdict, axis=1)
    gpf = grandparent_feasibility(ctx, groups, pdf2)
    susp = parents[parents.suspicious].copy()

    out.mkdir(parents=True, exist_ok=True)
    files = {"hierarchy_proposal.csv": h, "parent_categories.csv": parents, "unresolved_placements.csv": unresolved,
             "v1_vs_v2_comparison.csv": comp, "configuration_sweep.csv": sw, "suspicious_parent_review.csv": susp,
             "known_v1_problem_parents.csv": known, "grandparent_feasibility.csv": gpf}
    for f, d in files.items():
        d.to_csv(out / f, index=False)
    sel = {"linkage": link, "weights": wn, "weights_values": WEIGHTS[wn], "threshold": thr, "mode": mode}
    (out / "validation_report.md").write_text(report(s1, s2, s_ns, comp, parents, h, known, gpf, sw, sel, probs, ctx), encoding="utf-8")
    assert before == {k: sha256(p) for k, p in inputs.items()}, "an input changed"
    man = {"version": VERSION, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "scripts": {s: sha256(ROOT / "src" / s) for s in ("build_hierarchy_proposal_v2.py", "build_hierarchy_proposal.py", "esco_levels.py")},
           "inputs": {k: {"path": str(p).replace(str(Path.home()), "~"), "sha256": before[k]} for k, p in inputs.items()},
           "outputs": {f: sha256(out / f) for f in sorted(os.listdir(out))},
           "selection_criteria": SELECTION, "selected_configuration": sel,
           "configuration_space": {"linkages": LINKAGES, "weights": WEIGHTS, "thresholds": [THRESHOLDS[0], THRESHOLDS[-1], 0.01], "modes": CONSERVATIVE},
           "esco_excluded_links": ctx.esco_excluded, "suspect_links": sorted(ctx.suspect),
           "metrics_v1_corrected": s1, "metrics_v2": s2, "metrics_v2_without_split_candidates": s_ns, "structural_problems": probs,
           "ai_label": LABEL, "human_approved": False}
    (out / "manifest.json").write_text(json.dumps(man, indent=1, default=float), encoding="utf-8")
    print(json.dumps({"selected": sel, "v1": s1, "v2": s2, "problems": probs}, indent=1, default=float))
    return man


def report(s1, s2, s_ns, comp, parents, h, known, gpf, sw, sel, probs, ctx):
    f = lambda x: f"{x:.3f}" if isinstance(x, float) else str(x)
    L = [f"# Hierarchy Proposal v2 — validation report", "",
         f"> **{LABEL}.** Proposed parent level above the 374 frozen leaf topics. No topic, name, membership, alias, link, "
         "embedding, clustering output, v1 file or preflight file was changed. Nothing is human-approved.", "",
         "## Corrected evaluation framework (applied identically to v1 and v2)", "",
         "| Metric | Definition |", "|---|---|",
         "| coherence | mean pairwise cosine of child-topic centroids within a parent (child-child) |",
         "| LOO margin | cos(child, own parent without the child) − max cos(child, any other parent) |",
         "| parent separation | cosine of a parent centroid to its nearest other parent centroid (parent-parent) |",
         "| sibling affinity | share of a parent's assigned members whose nearest other topic is a sibling (member level) |",
         "| ESCO purity L1 / L2 | largest-group share of usable ESCO links at skills-hierarchy Level 1 / Level 2, multi-parent (1/|groups|) |",
         "| ESCO coverage | share of assigned members with a usable Level 2 ESCO link |", "",
         f"ESCO exclusions: {ctx.esco_excluded['uri_not_in_v121']} assigned-member links whose URI is not in v1.2.1 and "
         f"{ctx.esco_excluded['suspect_accepted']} links of the 37 suspect skills (Phase 3 verdicts CONFIRMED/LIKELY_INCORRECT, CONTEXT_DEPENDENT; "
         "includes unity, scales, design experience). Source files untouched.", "",
         "Suspicious parent = member-level mixing (sibling affinity < 0.15 or weakest child pair < 0.75) or coherence < 0.82 or "
         "nearest parent ≥ 0.95 or ≥ 2 split-pending children. Thresholds fixed before the sweep.", "",
         "## Configuration sweep and selection", "",
         f"Space: linkage {list(LINKAGES)} × weights {list(WEIGHTS)} × thresholds {THRESHOLDS[0]}–{THRESHOLDS[-1]} (step 0.01) × "
         f"{list(CONSERVATIVE)} = {len(sw)} configurations (`configuration_sweep.csv`).", "",
         f"Criteria fixed before running: hard {SELECTION['hard']}; objective = {SELECTION['objective']}; tie-break = {SELECTION['tie_break']}.", "",
         f"Feasible configurations: {int(sw.feasible.sum())}. **Selected: {sel}.**", "",
         "## v1 vs v2 (same corrected definitions)", "",
         "| Metric | v1 | v2 | v2 without split candidates | v2 vs v1 |", "|---|---:|---:|---:|---|"]
    L += [f"| {r.metric} | {f(r.v1)} | {f(r.v2)} | {f(r.v2_without_split_candidates)} | {r.v2_vs_v1} |" for r in comp.itertuples()]
    L += ["", f"Improved: {', '.join(comp[comp.v2_vs_v1 == 'improved'].metric)}.",
          f"Worse (trade-offs): {', '.join(comp[comp.v2_vs_v1 == 'worse'].metric) or 'none'}.", "",
          "## Placement states", "", "| State | Topics |", "|---|---:|"]
    L += [f"| {k} | {v} |" for k, v in h.placement_state.value_counts().items()]
    L += ["", "## Parent labels", "", f"Label confidence: {parents.label_confidence.value_counts().to_dict()}; "
          f"basis: {parents.label_basis.value_counts().to_dict()}; flagged for label review: {int(parents.needs_label_review.sum())}.", "",
          "## Structural validation", "", "Coverage (374 unique), parent references, no single-child parents, disjoint ID namespaces (depth 2, no cycles), "
          "unresolved/excluded topics without parents, consistent child lists, no generic labels, no human approval set.", "",
          f"**Problems: {probs or 'none'}**", "",
          "## Known v1 problem parents", "", "| v1 parent | Children | v1 flagged (v1 rules) | v1 mixing (corrected) | v2 placement | Together in v2 | v2 parent suspicious |", "|---|---|---|---|---|---|---|"]
    L += [f"| {r.v1_parent} | {r.v1_child_names} | {r.v1_flagged_suspicious_v1rules} | {r.v1_mixing_corrected} | {r.v2_placement} | {r.children_still_together_in_v2} | {r.v2_parents_suspicious} |"
          for r in known.itertuples()]
    L += ["", "## Suspicious v2 parents", "", "| Parent | Label | Coherence | Sibling aff. | Weakest pair | Flags |", "|---|---|---:|---:|---:|---|"]
    for r in parents[parents.suspicious].itertuples():
        fl = [n for n, on in (("mixing", r.flag_mixing), ("low coherence", r.flag_low_coherence), ("near-dup parent", r.flag_near_duplicate_parent),
                              ("split pending", r.flag_many_split_pending)) if on]
        L.append(f"| {r.parent_id} | {r.proposed_label[:90]} | {r.coherence} | {r.sibling_affinity} | {r.min_child_pair_cos} | {', '.join(fl)} |")
    L += ["", "## Grandparent feasibility (not constructed)", "",
          "The brief (Sprint 4) asks to \"build a multi-level hierarchy\" and \"build parent levels above the leaves\"; it fixes no depth. "
          "Grouping the v2 parents by centroid (average linkage) at several cuts:", "",
          "| Cut | Grandparents | Parents grouped | Parents alone | Median ESCO L1 purity | Largest |", "|---:|---:|---:|---:|---:|---:|"]
    L += [f"| {r.cut} | {r.grandparents} | {r.parents_grouped} | {r.parents_alone} | {f(r.median_grandparent_esco_L1_purity)} | {r.largest_grandparent} |" for r in gpf.itertuples()]
    L += ["", "## Remaining work", "",
          "- Human review of every parent, label and placement (none approved); document over/under-merging (brief).",
          "- Excluded topics need re-clustering or member reassignment before placement.",
          "- Split decisions for split-pending topics; LOO-conflict topics need a human placement decision.",
          "- Suspect and unresolvable ESCO links remain in the source files until a human approves unlinking/remapping.",
          "- Grandparent level: decision for the team (see feasibility table)."]
    return "\n".join(L)


if __name__ == "__main__":
    main()
