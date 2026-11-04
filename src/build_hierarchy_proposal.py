"""Sprint 4 Phase 3: build a PROPOSED parent level above the 374 frozen leaf topics (read-only over inputs).

    .venv/bin/python src/build_hierarchy_proposal.py

Method (deterministic, documented in the validation report and manifest):
  1. Eligibility. A topic is NOT placed (state UNRESOLVED_EXCLUDED) when the validity screen says
     exclude_until_reclustered or the Phase 2/3 audit says INVESTIGATE_CLUSTER (incl. T0104, user-approved).
     Topics marked hold_split_candidate / POTENTIAL_SPLIT are placed but flagged low confidence (split pending).
  2. Topic distance = W_CENTROID*(1-centroid cosine) + W_MEMBER*(1-member affinity) + W_ESCO*(1-ESCO profile cosine)
       centroid cosine   : cosine of assigned-member centroids (frozen vectors)
       member affinity   : share of a topic's assigned members whose nearest *other* centroid is the other topic,
                           symmetrised and scaled by AFFINITY_SCALE (member-level evidence)
       ESCO profile      : cosine of the topics' ESCO v1.2.1 level-2 group histograms (confident ESCO links only);
                           when either topic has < MIN_LINKS links the ESCO term is dropped and weights renormalised
  3. Average-linkage agglomerative clustering of eligible topics; the cut is the smallest threshold on a fixed grid
     with singleton share <= MAX_SINGLETON_SHARE and parent size <= MAX_PARENT_SIZE. Singletons are UNRESOLVED_SINGLETON.
  4. Parent label: the ESCO level-2 group when >= LABEL_MIN_SHARE of the parent's linked members share it (and >=
     LABEL_MIN_LINKS links); otherwise the provisional name of the medoid child topic. Labels are AI-derived, unreviewed.
Nothing frozen is modified: topic IDs, names, memberships, aliases, embeddings and clustering stay as they are.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

ROOT = Path(__file__).resolve().parents[1]
RUN = "hdbscan_10_umap10_ms1_2026-10-23"
INP = ROOT / f"data/processed/sprint4_input_{RUN}"
FEAT = ROOT / f"data/processed/sprint4_features_{RUN}"
NAMING = ROOT / f"data/processed/sprint4_naming_{RUN}"
NAMES = NAMING / "assembled_topic_naming_v1_20261104T003642Z/results.csv"
VALIDITY = NAMING / "validity_v1_topic_naming_v1_qwen_qwen3.8-27b_pilot_20261103T210409Z/topic_validity_all.csv"
AUDIT = ROOT / f"reports/sprint4_naming/{RUN}/topic_quality_review_v1/phase2_phase3_audit_v1/topic_metrics_374.csv"
ESCO = Path(os.environ.get("ESCO_DIR", os.path.expanduser("~/Desktop/testing/references/esco_v1.2.1")))
OUT = ROOT / f"reports/sprint4_naming/{RUN}/hierarchy_proposal_v1"
VERSION = "hierarchy_proposal_v1"
LABEL = "AI-GENERATED, UNREVIEWED (pending human approval)"

W_CENTROID, W_MEMBER, W_ESCO = 0.70, 0.15, 0.15
AFFINITY_SCALE = 0.20          # affinity of 0.20 (20% of members point at the other topic) counts as full support
MIN_LINKS = 3                  # ESCO profile needs >= 3 confident ESCO-linked assigned members
GRID = np.round(np.arange(0.10, 0.5001, 0.005), 3)
MAX_SINGLETON_SHARE, MAX_PARENT_SIZE = 0.10, 30
ESCO_LEVEL = 2                 # ESCO skills-hierarchy level used for profiles and labels (Level 0 = pillar)
LABEL_MIN_SHARE, LABEL_MIN_LINKS = 0.50, 8
LOW_MARGIN = 0.02              # child closer to another parent by less than this -> low confidence
EXCLUDE_TREATMENT = {"exclude_until_reclustered"}
SPLIT_FLAGS = {"hold_split_candidate"}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


# ---------------------------------------------------------------- pure functions (unit-tested)
def unit(X):
    return X / np.linalg.norm(X, axis=1, keepdims=True)


def member_affinity(member_vecs, member_topic, centroids):
    """A[i, j] = share of topic i's members whose nearest centroid other than their own is j; symmetrised."""
    k = len(centroids)
    S = member_vecs @ centroids.T
    S[np.arange(len(S)), member_topic] = -np.inf
    other = S.argmax(1)
    A = np.zeros((k, k))
    np.add.at(A, (member_topic, other), 1.0)
    A /= np.maximum(np.bincount(member_topic, minlength=k), 1)[:, None]
    return (A + A.T) / 2


def profile_cosine(P, has):
    """Cosine between rows of histogram matrix P; NaN where either row lacks a profile."""
    N = np.linalg.norm(P, axis=1, keepdims=True)
    Q = np.divide(P, N, out=np.zeros_like(P), where=N > 0)
    S = Q @ Q.T
    S[~has, :] = np.nan
    S[:, ~has] = np.nan
    return S


def combined_distance(ccos, aff, esco):
    """Weighted distance; drops the ESCO term (renormalising weights) where it is NaN."""
    da, db = 1 - ccos, 1 - np.minimum(aff / AFFINITY_SCALE, 1.0)
    has = ~np.isnan(esco)
    dc = np.where(has, 1 - np.nan_to_num(esco), 0.0)
    w = np.where(has, W_CENTROID + W_MEMBER + W_ESCO, W_CENTROID + W_MEMBER)
    D = (W_CENTROID * da + W_MEMBER * db + np.where(has, W_ESCO * dc, 0.0)) / w
    D = (D + D.T) / 2
    np.fill_diagonal(D, 0.0)
    return np.clip(D, 0, None)


def choose_cut(Z, n, grid=GRID):
    """Smallest grid threshold meeting the singleton and size limits; returns (threshold, labels, diagnostics)."""
    diag = []
    for t in grid:
        lab = fcluster(Z, t=t, criterion="distance")
        sizes = np.bincount(lab)[1:]
        single = (sizes == 1).sum() / n
        diag.append({"threshold": float(t), "parents": int((sizes >= 2).sum()), "singleton_share": round(float(single), 4),
                     "max_size": int(sizes.max())})
        if single <= MAX_SINGLETON_SHARE and sizes.max() <= MAX_PARENT_SIZE:
            return float(t), lab, diag
    raise RuntimeError("no threshold on the grid meets the singleton/size limits")


def validate(h, parents, n_topics, centroids_by_topic, parent_centroids):
    """Structural + quality checks. Returns (problems, metrics)."""
    p = []
    if len(h) != n_topics or h.topic_id.duplicated().any():
        p.append("topic coverage / duplicate assignment")
    placed = h[h.parent_id != ""]
    if not set(placed.parent_id) <= set(parents.parent_id):
        p.append("child points to a missing parent")
    if (parents.n_children < 2).any():
        p.append("orphan / single-child parent")
    if set(parents.parent_id) & set(h.topic_id):
        p.append("parent and topic namespaces overlap (cycle risk)")
    if (placed.parent_id.isin(placed.topic_id)).any() or (h.placement_state.str.startswith("UNRESOLVED") & (h.parent_id != "")).any():
        p.append("cycle or unresolved topic with a parent")
    got = placed.groupby("parent_id").topic_id.apply(set).to_dict()
    want = {r.parent_id: set(r.child_topic_ids.split(";")) for r in parents.itertuples()}
    if got != want:
        p.append("parent-child lists inconsistent")
    viol = 0
    for r in placed.itertuples():
        s = {pid: float(centroids_by_topic[r.topic_id] @ c) for pid, c in parent_centroids.items()}
        viol += max(s, key=s.get) != r.parent_id
    metrics = {"topics": int(len(h)), "placed": int(len(placed)), "parents": int(len(parents)),
               "unresolved": int(h.placement_state.str.startswith("UNRESOLVED").sum()),
               "children_closer_to_other_parent": int(viol)}
    return p, metrics


# ---------------------------------------------------------------- build
def main(out=OUT):
    if out.exists() and any(out.iterdir()):
        sys.exit(f"refusing to overwrite {out}")
    inputs = {"skills": INP / "skills.csv", "vectors": INP / "vectors.npy", "memberships": INP / "memberships.csv",
              "topics": INP / "topics.csv", "reference_links": INP / "reference_links.csv", "snapshot_manifest": INP / "manifest.json",
              "topic_ids": FEAT / "topic_ids.csv", "topic_centroids": FEAT / "topic_centroids.npy", "features_manifest": FEAT / "manifest.json",
              "names": NAMES, "validity": VALIDITY, "audit_topic_metrics": AUDIT}
    esco_files = {"esco_broader": ESCO / "broaderRelationsSkillPillar_en.csv", "esco_skill_groups": ESCO / "skillGroups_en.csv",
                  "esco_hierarchy": ESCO / "skillsHierarchy_en.csv"}
    use_esco = all(p.exists() for p in esco_files.values())
    if use_esco:
        inputs.update(esco_files)
    before = {k: sha256(p) for k, p in inputs.items()}
    for d, man in ((INP, "snapshot_manifest"), (FEAT, "features_manifest")):
        for f, hsh in json.loads(inputs[man].read_text())["files_sha256"].items():
            assert sha256(d / f) == hsh, f"frozen input {d.name}/{f} does not match its manifest"

    sk = read(inputs["skills"]); V = np.load(inputs["vectors"]).astype(np.float64)
    mem = read(inputs["memberships"]); tp = read(inputs["topics"]); ids = read(inputs["topic_ids"])
    names = read(inputs["names"]).set_index("topic_id"); val = read(inputs["validity"]).set_index("topic_id")
    aud = read(inputs["audit_topic_metrics"]).set_index("topic_id")
    T = ids.topic_id.tolist(); ti = {t: i for i, t in enumerate(T)}
    assert len(T) == 374 == len(tp) == len(names) == len(val) == len(aud) and V.shape == (11093, 384) and len(mem) == 11093
    assert (tp.parent_topic_id == "").all(), "topics already have parents; this script only proposes the first level"
    C = np.load(inputs["topic_centroids"]).astype(np.float64)
    row = dict(zip(sk.skill_key, sk.vector_row.astype(int)))
    a = mem[mem.state == "assigned"].copy(); a["vi"] = a.skill_key.map(row); a["ti"] = a.topic_id.map(ti)
    C2 = unit(np.stack([V[a.vi[a.ti == j]].mean(0) for j in range(len(T))]))
    assert np.abs(C - C2).max() < 1e-5, "stored centroids differ from assigned-member centroids"

    # eligibility
    act = aud.ai_review_action.str.split(" ").str[0]
    excluded = {t for t in T if val.at[t, "hierarchy_treatment"] in EXCLUDE_TREATMENT or act.get(t) == "INVESTIGATE_CLUSTER"}
    split_flag = {t for t in T if val.at[t, "hierarchy_treatment"] in SPLIT_FLAGS or act.get(t) == "POTENTIAL_SPLIT"}
    E = [t for t in T if t not in excluded]; ei = [ti[t] for t in E]

    # evidence matrices
    ccos = C @ C.T
    aff = member_affinity(V[a.vi.values], a.ti.values, C)
    groups, glabel = None, {}
    if use_esco:
        br = read(inputs["esco_broader"]); par = br.groupby("conceptUri").broaderUri.first().to_dict()
        glabel = read(inputs["esco_skill_groups"]).set_index("conceptUri").preferredLabel.to_dict()

        hier = read(inputs["esco_hierarchy"])
        level_of = {u: lv for lv in range(4) for u in hier[f"Level {lv} URI"] if u}

        def level2(u):
            seen = set()
            while u in par and u not in seen:
                seen.add(u); u = par[u]
                if level_of.get(u) == ESCO_LEVEL:
                    return u
            return None
        RL = read(inputs["reference_links"])
        lk = a.merge(RL, on="skill_key")
        lk = lk[(lk.verdict == "known_skill") & lk.source.str.startswith("ESCO")].copy()
        lk["g2"] = lk.ref_id.map(level2); lk = lk[lk.g2.notna()]
        groups = sorted(lk.g2.unique()); gi = {g: i for i, g in enumerate(groups)}
        P = np.zeros((len(T), len(groups)))
        np.add.at(P, (lk.ti.values, lk.g2.map(gi).values), 1.0)
        has = P.sum(1) >= MIN_LINKS
        esco = profile_cosine(P, has)
    else:
        P = np.zeros((len(T), 1)); esco = np.full((len(T), len(T)), np.nan)
    D = combined_distance(ccos[np.ix_(ei, ei)], aff[np.ix_(ei, ei)], esco[np.ix_(ei, ei)])
    Z = linkage(squareform(D, checks=False), method="average")
    thr, lab, diag = choose_cut(Z, len(E))

    # parents (ordered deterministically by smallest child topic id)
    clusters = {}
    for t, c in zip(E, lab):
        clusters.setdefault(c, []).append(t)
    multi = sorted((sorted(v) for v in clusters.values() if len(v) >= 2), key=lambda v: v[0])
    singletons = sorted(v[0] for v in clusters.values() if len(v) == 1)
    nA = a.groupby("topic_id").size()
    prow, parent_of, pcent = [], {}, {}
    for n, kids in enumerate(multi, 1):
        pid = f"P{n:03d}"
        ks = [ti[t] for t in kids]
        cen = unit(V[a.vi[a.ti.isin(ks)]].mean(0)[None])[0]
        pcent[pid] = cen
        medoid = kids[int(np.argmax(C[ks] @ cen))]
        hist = P[ks].sum(0); nlinks = int(hist.sum())
        top_g = groups[int(hist.argmax())] if use_esco and nlinks else ""
        share = float(hist.max() / nlinks) if nlinks else 0.0
        if use_esco and nlinks >= LABEL_MIN_LINKS and share >= LABEL_MIN_SHARE:
            label, src = f"{glabel.get(top_g, top_g)}", "esco_level2_majority"
        else:
            label, src = f"{names.at[medoid, 'provisional_name']} (and related topics)", "medoid_child_name"
        sub = ccos[np.ix_(ks, ks)]
        coherence = float((sub.sum() - len(ks)) / (len(ks) * (len(ks) - 1)))
        members = V[a.vi[a.ti.isin(ks)]]
        prow.append({"parent_id": pid, "proposed_label": label, "label_source": label_basis(src),
                     "n_children": len(kids), "child_topic_ids": ";".join(kids),
                     "child_names": " | ".join(names.at[t, "provisional_name"] for t in kids),
                     "medoid_topic": medoid, "n_assigned_skills": int(nA.loc[kids].sum()),
                     "child_centroid_coherence": round(coherence, 4),
                     "member_cos_to_parent_mean": round(float((members @ cen).mean()), 4),
                     "esco_linked_members": nlinks, "esco_top_level2_group": glabel.get(top_g, top_g),
                     "esco_top_group_share": round(share, 4),
                     "children_split_pending": sum(t in split_flag for t in kids), "ai_label": LABEL})
        for t in kids:
            parent_of[t] = pid
    parents = pd.DataFrame(prow)
    dup = parents.proposed_label.duplicated(keep=False) & (parents.label_source == label_basis("esco_level2_majority"))
    parents.loc[dup, "proposed_label"] = parents.loc[dup, "proposed_label"] + " — " + parents.loc[dup, "medoid_topic"].map(lambda t: names.at[t, "provisional_name"])
    pids = list(pcent); PC = np.stack([pcent[p] for p in pids])
    PP = PC @ PC.T; np.fill_diagonal(PP, -1)
    parents["nearest_parent"] = [pids[i] for i in PP.argmax(1)]
    parents["nearest_parent_cos"] = np.round(PP.max(1), 4)

    hrows = []
    for t in T:
        j = ti[t]; pid = parent_of.get(t, "")
        if t in excluded:
            state, reason = "UNRESOLVED_EXCLUDED", ("validity screen: exclude_until_reclustered" if val.at[t, "hierarchy_treatment"] in EXCLUDE_TREATMENT
                                                    else f"audit action: {aud.at[t, 'ai_review_action']}")
        elif pid == "":
            state, reason = "UNRESOLVED_SINGLETON", f"no parent within threshold {thr}"
        else:
            s = PC @ C[j]; own = s[pids.index(pid)]; s2 = np.sort(s)[-2] if len(s) > 1 else -1
            margin = own - max(x for k, x in enumerate(s) if pids[k] != pid)
            low = t in split_flag or margin < LOW_MARGIN or pids[int(s.argmax())] != pid
            state = "PLACED_LOW_CONFIDENCE" if low else "PLACED"
            reason = "; ".join(r for r, on in (("split pending (validity/audit)", t in split_flag),
                                                (f"margin {margin:.3f} < {LOW_MARGIN}", margin < LOW_MARGIN),
                                                ("closer to another parent", pids[int(s.argmax())] != pid)) if on)
        hrows.append({"topic_id": t, "provisional_name": names.at[t, "provisional_name"], "parent_id": pid,
                      "proposed_parent_label": parents.set_index("parent_id").at[pid, "proposed_label"] if pid else "",
                      "placement_state": state, "placement_note": reason,
                      "cos_to_own_parent": round(float(pcent[pid] @ C[j]), 4) if pid else "",
                      "best_other_parent": (pids[int(np.argsort(PC @ C[j])[-1])] if pids[int(np.argsort(PC @ C[j])[-1])] != pid
                                            else pids[int(np.argsort(PC @ C[j])[-2])]) if pids else "",
                      "validity_treatment": val.at[t, "hierarchy_treatment"], "audit_action": aud.at[t, "ai_review_action"],
                      "n_assigned": int(nA.get(t, 0)), "ai_label": LABEL})
    h = pd.DataFrame(hrows)
    unresolved = h[h.placement_state.str.startswith("UNRESOLVED") | (h.placement_state == "PLACED_LOW_CONFIDENCE")].copy()
    problems, metrics = validate(h, parents, len(T), {t: C[ti[t]] for t in T}, pcent)
    metrics.update({"placed_high": int((h.placement_state == "PLACED").sum()), "placed_low_confidence": int((h.placement_state == "PLACED_LOW_CONFIDENCE").sum()),
                    "unresolved_excluded": int((h.placement_state == "UNRESOLVED_EXCLUDED").sum()),
                    "unresolved_singleton": int((h.placement_state == "UNRESOLVED_SINGLETON").sum()),
                    "threshold": thr, "eligible_topics": len(E), "parent_size_min_med_max": [int(parents.n_children.min()), float(parents.n_children.median()), int(parents.n_children.max())],
                    "parent_coherence_median": round(float(parents.child_centroid_coherence.median()), 4),
                    "inter_parent_nearest_cos_median": round(float(parents.nearest_parent_cos.median()), 4),
                    "inter_parent_pairs_ge_0.95": int((np.triu(PP, 1) >= 0.95).sum()),
                    "labels_esco": int((parents.label_source == label_basis("esco_level2_majority")).sum()),
                    "labels_medoid": int((parents.label_source == label_basis("medoid_child_name")).sum()),
                    "esco_used": use_esco, "structural_problems": problems})
    q = parents.child_centroid_coherence.quantile(0.10)
    suspicious = parents[(parents.child_centroid_coherence <= q) | ((parents.esco_linked_members >= LABEL_MIN_LINKS) & (parents.esco_top_group_share < 0.30))
                         | (parents.children_split_pending >= 2) | (parents.nearest_parent_cos >= 0.95)].copy()
    out.mkdir(parents=True, exist_ok=True)
    h.to_csv(out / "hierarchy_proposal.csv", index=False)
    parents.to_csv(out / "parent_categories.csv", index=False)
    unresolved.to_csv(out / "unresolved_placements.csv", index=False)
    pd.DataFrame(diag).to_csv(out / "cut_threshold_sweep.csv", index=False)
    (out / "validation_report.md").write_text(report(metrics, parents, suspicious, h), encoding="utf-8")
    assert before == {k: sha256(p) for k, p in inputs.items()}, "an input changed during the run"
    man = {"version": VERSION, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "script": "src/build_hierarchy_proposal.py", "script_sha256": sha256(__file__), "ai_label": LABEL,
           "parameters": {"W_CENTROID": W_CENTROID, "W_MEMBER": W_MEMBER, "W_ESCO": W_ESCO, "AFFINITY_SCALE": AFFINITY_SCALE,
                          "MIN_LINKS": MIN_LINKS, "grid": [float(GRID[0]), float(GRID[-1]), 0.005], "MAX_SINGLETON_SHARE": MAX_SINGLETON_SHARE,
                          "MAX_PARENT_SIZE": MAX_PARENT_SIZE, "LABEL_MIN_SHARE": LABEL_MIN_SHARE, "LABEL_MIN_LINKS": LABEL_MIN_LINKS,
                          "LOW_MARGIN": LOW_MARGIN, "ESCO_LEVEL": ESCO_LEVEL, "linkage": "average", "exclude_treatment": sorted(EXCLUDE_TREATMENT),
                          "exclude_audit_action": "INVESTIGATE_CLUSTER", "split_flags": sorted(SPLIT_FLAGS) + ["POTENTIAL_SPLIT"]},
           "inputs": {k: {"path": str(p).replace(str(Path.home()), "~"), "sha256": before[k]} for k, p in inputs.items()},
           "outputs": {f: sha256(out / f) for f in sorted(os.listdir(out))}, "metrics": metrics,
           "frozen_unchanged": True, "human_approved": False}
    (out / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(json.dumps(metrics, indent=1))
    return metrics


def label_basis(src):
    return {"esco_level2_majority": "ESCO v1.2.1 skills-hierarchy Level 2 group shared by >= 50% of the parent's ESCO-linked members (duplicates suffixed with the medoid child name)",
            "medoid_child_name": "provisional name of the most central child topic"}[src]


def report(m, parents, suspicious, h):
    L = [f"# Proposed topic hierarchy — {VERSION}", "",
         f"> **{LABEL}.** A proposed first parent level above the 374 frozen leaf topics. No topic, name, membership, "
         "alias, embedding or clustering output was changed. Every parent, label and placement needs human review.", "",
         "## Method", "",
         "1. **Eligibility.** Topics the validity screen marks `exclude_until_reclustered` or the Phase 2/3 audit marks "
         "`INVESTIGATE_CLUSTER` (incl. T0104, user-approved) are not placed (`UNRESOLVED_EXCLUDED`). Split candidates "
         "(`hold_split_candidate` / `POTENTIAL_SPLIT`) are placed but flagged low confidence.",
         f"2. **Distance** = {W_CENTROID}·(1 − centroid cosine) + {W_MEMBER}·(1 − member affinity) + {W_ESCO}·(1 − ESCO profile cosine). "
         f"Member affinity = share of a topic's assigned members whose nearest other centroid is the other topic (scaled by {AFFINITY_SCALE}). "
         f"ESCO profile = histogram of ESCO v1.2.1 level-2 groups of confidently linked members (needs ≥ {MIN_LINKS}; else the term is dropped).",
         f"3. **Average-linkage** agglomerative clustering of eligible topics; cut = smallest grid threshold with singleton share "
         f"≤ {MAX_SINGLETON_SHARE} and parent size ≤ {MAX_PARENT_SIZE} (sweep in `cut_threshold_sweep.csv`). Chosen: **{m['threshold']}**.",
         f"4. **Labels** come only from children: ESCO level-2 group if ≥ {LABEL_MIN_SHARE:.0%} of ≥ {LABEL_MIN_LINKS} linked members share it, "
         "else the medoid child's provisional name + \"(and related topics)\".", "",
         "**Trade-offs.** Centroid similarity dominates (embedding geometry); member affinity and ESCO profiles damp "
         "word-form look-alikes but cannot remove them. ESCO links are automatic and partly wrong (see the Phase 2/3 audit), "
         "so ESCO-based labels are broad. Average linkage can chain; parent coherence and suspicious groups are reported below.", "",
         "## Results", "", "| Measure | Value |", "|---|---|"]
    keys = ["topics", "eligible_topics", "parents", "placed", "placed_high", "placed_low_confidence", "unresolved",
            "unresolved_excluded", "unresolved_singleton", "parent_size_min_med_max", "parent_coherence_median",
            "inter_parent_nearest_cos_median", "inter_parent_pairs_ge_0.95", "children_closer_to_other_parent",
            "labels_esco", "labels_medoid", "esco_used"]
    L += [f"| {k} | {m[k]} |" for k in keys]
    L += ["", "## Structural validation", "",
          "Checks: topic coverage (374, no duplicates), every placed child has an existing parent, no single-child parents, "
          "disjoint parent/topic ID namespaces (no cycles; depth 2), parent-child lists consistent, unresolved topics have no parent.", "",
          f"**Problems: {m['structural_problems'] or 'none'}**", "",
          "## Suspicious parent groups", "",
          "Flagged when child-centroid coherence is in the lowest 10%, the ESCO top-group share is < 0.30 (with ≥ 8 links), "
          "≥ 2 children are split candidates, or the nearest other parent has cosine ≥ 0.95.", "",
          "| Parent | Label (AI) | Children | Coherence | ESCO top share | Split-pending children | Child names |", "|---|---|---:|---:|---:|---:|---|"]
    L += [f"| {r.parent_id} | {r.proposed_label} | {r.n_children} | {r.child_centroid_coherence} | {r.esco_top_group_share} | "
          f"{r.children_split_pending} | {r.child_names[:160]} |" for r in suspicious.itertuples()]
    L += ["", "## Remaining work (not done here)", "",
          "- Human review of every parent, label and placement; record over- and under-merging (brief, Sprint 4).",
          "- Re-cluster or reassign the excluded topics, then place them.",
          "- Decide split candidates before fixing their parents.",
          "- Upper levels (grandparents) are not proposed in v1.",
          "- Correction: the Phase 2/3 audit column `esco_purity_level2` used the first group under the ESCO pillar, which is "
          "ESCO skills-hierarchy **Level 1**; this proposal uses true **Level 2** (from `skillsHierarchy_en.csv`). The audit files were not changed.",
          "- Nearest-neighbour agreement / purity are audit metrics only; not yet part of a hierarchy evaluation pipeline."]
    return "\n".join(L)


if __name__ == "__main__":
    main()
