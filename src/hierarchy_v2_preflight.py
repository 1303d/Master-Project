"""Sprint 4 Hierarchy v2 preflight: v1 integrity, corrected ESCO levels, ESCO URI discrepancies, hierarchy metric
checks (read-only over every input; v1 artifacts are never modified).

    .venv/bin/python src/hierarchy_v2_preflight.py

Writes reports/sprint4_naming/<run>/hierarchy_v2_preflight_v1/ (refuses to overwrite). No API calls.
"""
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_hierarchy_proposal as hp  # noqa: E402
import esco_levels as el  # noqa: E402

ROOT = hp.ROOT
V1 = hp.OUT
OUT = ROOT / f"reports/sprint4_naming/{hp.RUN}/hierarchy_v2_preflight_v1"
AUDIT_DIR = hp.AUDIT.parent
MIXING_SIBLING_AFFINITY = 0.15    # share of a parent's members whose nearest other topic is a sibling
MIXING_MIN_PAIR_COS = 0.75        # weakest child-pair centroid cosine
URI_RE = re.compile(r"http://data\.europa\.eu/esco/skill/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
FILLER = {"skill", "skills", "strong", "excellent", "proficiency", "proficient", "knowledge", "experience",
          "ability", "basic", "of", "in", "with", "the", "a", "an", "and", "&", "using", "use"}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def norm(name):
    """Copy of evaluate.norm (the normaliser link_reference.py used for 'exact' matches)."""
    words = re.sub(r"[^\w+#./ ]", " ", name.lower().replace("&", " and ")).split()
    words = [w[:-4] + "ysis" if w.endswith("yses") else w for w in words]
    words = [w[:-3] + "y" if len(w) > 4 and w.endswith("ies") else w for w in words]
    words = [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "sis")) else w for w in words]
    return tuple(w for w in words if w not in FILLER) or tuple(words)


def stems(s):
    return {w[:4] for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) >= 3 and w not in FILLER}


# ---------------------------------------------------------------- pure metric helpers (unit-tested)
def loo_parent_scores(child_vec, child_idx, parent_members, member_topic, member_vecs):
    """Cosine of a child centroid to every parent centroid, leaving the child's own members out."""
    out = {}
    for pid, kids in parent_members.items():
        m = np.isin(member_topic, [k for k in kids if k != child_idx])
        if m.any():
            c = member_vecs[m].mean(0)
            out[pid] = float(child_vec @ (c / np.linalg.norm(c)))
    return out


def sibling_affinity(kids, member_topic, nearest_other):
    """Share of the parent's assigned members whose nearest other topic centroid is a sibling."""
    m = np.isin(member_topic, kids)
    return float(np.isin(nearest_other[m], kids).mean()) if m.any() else float("nan")


def mixing_candidate(sib_aff, min_pair):
    return bool(sib_aff < MIXING_SIBLING_AFFINITY or min_pair < MIXING_MIN_PAIR_COS)


# ---------------------------------------------------------------- main
def main(out=OUT):
    if out.exists() and any(out.iterdir()):
        sys.exit(f"refusing to overwrite {out}")
    esco = hp.ESCO
    inputs = {"v1_manifest": V1 / "manifest.json", "v1_hierarchy": V1 / "hierarchy_proposal.csv",
              "v1_parents": V1 / "parent_categories.csv", "v1_report": V1 / "validation_report.md",
              "v1_script": ROOT / "src/build_hierarchy_proposal.py", "audit_metrics": hp.AUDIT,
              "audit_links": AUDIT_DIR / "reference_link_verification_38.csv",
              "reference_links": hp.INP / "reference_links.csv", "memberships": hp.INP / "memberships.csv",
              "skills": hp.INP / "skills.csv", "vectors": hp.INP / "vectors.npy",
              "topic_centroids": hp.FEAT / "topic_centroids.npy", "topic_ids": hp.FEAT / "topic_ids.csv",
              **{f"esco_{n}": esco / f for n, f in [("skills", "skills_en.csv"), ("hierarchy", "skillsHierarchy_en.csv"),
                                                     ("broader", "broaderRelationsSkillPillar_en.csv"),
                                                     ("schemes", "conceptSchemes_en.csv")]}}
    missing = [k for k, p in inputs.items() if not Path(p).exists()]
    if missing:
        sys.exit(f"BLOCKED: missing inputs {missing}")
    before = {k: sha256(p) for k, p in inputs.items()}

    # 1. v1 integrity --------------------------------------------------------------------------------------
    m1 = json.loads(inputs["v1_manifest"].read_text())
    v1 = {"output_hashes_ok": all(sha256(V1 / f) == h for f, h in m1["outputs"].items()),
          "script_hash_ok": sha256(inputs["v1_script"]) == m1["script_sha256"],
          "input_hashes_ok": all(sha256(Path(v["path"].replace("~", str(Path.home())))) == v["sha256"] for v in m1["inputs"].values())}
    with tempfile.TemporaryDirectory() as tmp:
        hp.main(Path(tmp) / "rerun")
        v1["rerun_identical"] = all(sha256(V1 / f) == sha256(Path(tmp) / "rerun" / f) for f in m1["outputs"] if f != "manifest.json")
    h = read(inputs["v1_hierarchy"]); p = read(inputs["v1_parents"])
    ids = read(inputs["topic_ids"]).topic_id.tolist()
    v1.update({"topics": len(h), "ids_match": set(h.topic_id) == set(ids) and h.topic_id.is_unique, "parents": len(p),
               "states": h.placement_state.value_counts().to_dict(),
               "excluded_with_parent": int(((h.placement_state == "UNRESOLVED_EXCLUDED") & (h.parent_id != "")).sum()),
               "unresolved_with_parent": int((h.placement_state.str.startswith("UNRESOLVED") & (h.parent_id != "")).sum())})

    # 2. ESCO levels + corrected purity ----------------------------------------------------------------------
    level_of, parents, labels, skills = el.load(esco)
    RL = read(inputs["reference_links"]); mem = read(inputs["memberships"])
    a = mem[mem.state == "assigned"]
    lk = a.merge(RL, on="skill_key")
    lk = lk[(lk.verdict == "known_skill") & lk.source.str.startswith("ESCO")]
    by_topic = {t: lk[lk.topic_id == t].ref_id.tolist() for t in ids}
    pur1 = el.purity(by_topic, 1, level_of, parents, skills).set_index("topic_id")
    pur2 = el.purity(by_topic, 2, level_of, parents, skills).set_index("topic_id")
    aud = read(inputs["audit_metrics"]).set_index("topic_id")
    legacy_level = pd.Series([level_of.get(el.legacy_first_parent_group(u, parents)) for u in lk.ref_id if u in skills]).value_counts().to_dict()
    pur = pd.DataFrame({"topic_id": ids,
                        "esco_purity_L1_v2": [pur1.at[t, "purity"] for t in ids], "top_group_L1": [labels.get(pur1.at[t, "top_group_uri"], "") for t in ids],
                        "esco_purity_L2_v2": [pur2.at[t, "purity"] for t in ids], "top_group_L2": [labels.get(pur2.at[t, "top_group_uri"], "") for t in ids],
                        "n_links": [pur1.at[t, "n_links"] for t in ids], "n_used_L1": [pur1.at[t, "n_used"] for t in ids],
                        "n_used_L2": [pur2.at[t, "n_used"] for t in ids], "n_uri_not_in_v121": [pur1.at[t, "n_uri_not_in_v121"] for t in ids],
                        "audit_v1_column_esco_purity_level2_is_really_L1": [aud.at[t, "esco_purity_level2"] for t in ids]})
    esco_summary = {"source": str(esco).replace(str(Path.home()), "~"), "version": "ESCO v1.2.1 (classification, en, csv)",
                    "groups_per_level": {lv: sum(1 for x in level_of.values() if x == lv) for lv in el.LEVELS},
                    "level0_labels": sorted(labels[u] for u, lv in level_of.items() if lv == 0),
                    "skills_with_multiple_broader": sum(1 for k, v in parents.items() if k in skills and len(v) > 1),
                    "legacy_rule_true_levels": {str(k): int(v) for k, v in legacy_level.items()},
                    "links_with_multiple_L2_ancestors": int(sum(len(el.ancestors_at_level(u, 2, level_of, parents)) > 1 for u in lk.ref_id if u in skills)),
                    "purity_L1_median": float(pd.to_numeric(pur.esco_purity_L1_v2).median()),
                    "purity_L2_median": float(pd.to_numeric(pur.esco_purity_L2_v2).median()),
                    "topics_with_purity_L2": int(pd.to_numeric(pur.esco_purity_L2_v2).notna().sum())}

    # 3. ESCO URI discrepancies -------------------------------------------------------------------------------
    E = read(inputs["esco_skills"]); cs = read(inputs["esco_schemes"])
    scheme_of = {}
    for r in cs.itertuples():
        for u in (x.strip() for x in r.hasTopConcept.split(",")):
            scheme_of.setdefault(u, []).append(r.preferredLabel)
    skills_text = inputs["esco_skills"].read_text(encoding="utf-8")
    lab2uri = {}
    for r in E.itertuples():
        for lb in [r.preferredLabel] + [x for x in r.altLabels.split("\n") if x]:
            lab2uri.setdefault(lb.strip().lower(), r.conceptUri)
    confirmed = set(read(inputs["audit_links"]).query("ai_verdict == 'CONFIRMED_INCORRECT'").canonical_skill_key)
    dis = RL[RL.source.str.startswith("ESCO") & ~RL.ref_id.isin(set(E.conceptUri))].copy()
    topic_of = dict(zip(mem.skill_key, mem.topic_id)); state_of = dict(zip(mem.skill_key, mem.state))
    rows = []
    for r in dis.itertuples():
        u = r.ref_id
        if not URI_RE.fullmatch(u):
            cls, ev = "INVALID_IDENTIFIER", "not an ESCO skill URI"
        elif r.verdict == "known_skill" and r.skill_key in confirmed:
            cls, ev = "INCORRECT_ACCEPTED_MAPPING", "Phase 3 audit: CONFIRMED_INCORRECT"
        elif u in scheme_of or u in skills_text:
            cls, ev = "MISSING_REFERENCE_EXPORT", ("listed in v1.2.1 concept scheme(s): " + "; ".join(sorted(set(scheme_of[u])))
                                                   if u in scheme_of else "referenced in a v1.2.1 scope note") + "; no record in skills_en"
        elif r.ref_label.strip().lower() in lab2uri:
            cls, ev = "VERSION_MISMATCH", f"label exists in v1.2.1 under {lab2uri[r.ref_label.strip().lower()]}"
        else:
            cls, ev = "UNRESOLVED", "URI and label not found in v1.2.1; v1.2 API export (data/reference/esco_skills.csv) not available"
        lexical = bool(stems(r.skill_key) & stems(r.ref_label))
        rows.append({"skill_key": r.skill_key, "topic_id": topic_of.get(r.skill_key, ""), "membership_state": state_of.get(r.skill_key, ""),
                     "verdict": r.verdict, "source": r.source, "ref_label": r.ref_label, "ref_id": u, "score": r.score, "match": r.match,
                     "classification": cls, "evidence": ev,
                     "v121_uri_for_same_label": lab2uri.get(r.ref_label.strip().lower(), ""),
                     "mapping_quality_flag": ("" if r.verdict != "known_skill" else "lexical_overlap" if lexical else "no_lexical_overlap_review"),
                     "proposed_handling": {"MISSING_REFERENCE_EXPORT": "flag; exclude from ESCO-based metrics until the record is available",
                                           "VERSION_MISMATCH": "flag; candidate remap to the v1.2.1 URI (human approval)",
                                           "UNRESOLVED": "flag; exclude from ESCO-based metrics",
                                           "INCORRECT_ACCEPTED_MAPPING": "flag; unlink pending human approval",
                                           "INVALID_IDENTIFIER": "flag; exclude"}[cls]})
    disc = pd.DataFrame(rows)

    # 3b. the three 'exact' matches ------------------------------------------------------------------------------
    trace = []
    for k in ("unity", "scales", "design experience"):
        r = RL.set_index("skill_key").loc[k]
        key = norm(k); hits = []
        for e in E.itertuples():
            for lb, kind in [(e.preferredLabel, "preferred")] + [(x, "alt") for x in e.altLabels.split("\n") if x] + [(x, "hidden") for x in e.hiddenLabels.split("\n") if x]:
                if norm(lb) == key:
                    hits.append(f"{e.preferredLabel} [{kind}: '{lb}']")
        accepted_label_hit = any(h.startswith(r.ref_label + " [") for h in hits)
        trace.append({"skill_key": k, "normalised_key": " ".join(key), "accepted_ref_label": r.ref_label, "ref_id": r.ref_id,
                      "v121_labels_with_same_key": " | ".join(hits) or "none",
                      "explained_by_v121": accepted_label_hit,
                      "explanation": ("normaliser drops filler 'experience' -> ('design',); v1.2.1 'think creatively' has alt label 'design'"
                                      if accepted_label_hit else
                                      "no v1.2.1 label of the accepted concept normalises to this key; the match came from the v1.2 API export "
                                      "(data/reference/esco_skills.csv), which is not available locally"),
                      "correct_v121_candidate": next((h for h in hits if not h.startswith(r.ref_label)), ""),
                      "accepted_mapping_correct": False})
    trace = pd.DataFrame(trace)

    # 4. hierarchy metric checks -------------------------------------------------------------------------------
    C = np.load(inputs["topic_centroids"]).astype(np.float64); ti = {t: i for i, t in enumerate(ids)}
    sk = read(inputs["skills"]); V = np.load(inputs["vectors"]).astype(np.float64)
    row = dict(zip(sk.skill_key, sk.vector_row.astype(int)))
    mt = a.topic_id.map(ti).values; X = V[a.skill_key.map(row).values]
    S = X @ C.T; S[np.arange(len(S)), mt] = -np.inf; nearest_other = S.argmax(1)
    v1_susp = set(re.findall(r"^\| (P\d{3}) \|", inputs["v1_report"].read_text(), re.M))
    pm = {r.parent_id: [ti[t] for t in r.child_topic_ids.split(";")] for r in p.itertuples()}
    prow = []
    for r in p.itertuples():
        ks = pm[r.parent_id]; sub = C[ks] @ C[ks].T
        coh = (sub.sum() - len(ks)) / (len(ks) * (len(ks) - 1)); mn = float(sub[np.triu_indices(len(ks), 1)].min())
        sa = sibling_affinity(ks, mt, nearest_other)
        prow.append({"parent_id": r.parent_id, "n_children": len(ks), "child_names": r.child_names,
                     "coherence_recomputed": round(float(coh), 4), "coherence_v1": float(r.child_centroid_coherence),
                     "coherence_match": abs(coh - float(r.child_centroid_coherence)) < 1e-4,
                     "min_child_pair_cos": round(mn, 4), "sibling_member_affinity": round(sa, 4),
                     "v1_suspicious": r.parent_id in v1_susp, "mixing_candidate_v2_rule": mixing_candidate(sa, mn)})
    pchk = pd.DataFrame(prow)
    crow = []
    for r in h[h.parent_id != ""].itertuples():
        j = ti[r.topic_id]; sc = loo_parent_scores(C[j], j, pm, mt, X)
        own = sc[r.parent_id]; best = max((v, k) for k, v in sc.items() if k != r.parent_id)
        crow.append({"topic_id": r.topic_id, "parent_id": r.parent_id, "v1_state": r.placement_state,
                     "cos_to_own_parent_v1_self_inclusive": r.cos_to_own_parent, "cos_to_own_parent_loo": round(own, 4),
                     "best_other_parent_loo": best[1], "cos_best_other_loo": round(best[0], 4), "margin_loo": round(own - best[0], 4),
                     "closer_to_other_parent_loo": own < best[0]})
    cchk = pd.DataFrame(crow)
    hm = {"coherence_all_match": bool(pchk.coherence_match.all()),
          "metric_scales": {"coherence": "mean pairwise cosine between child-topic centroids (child-child)",
                            "cos_to_own_parent (v1)": "child centroid vs member-weighted parent centroid that INCLUDES the child (self-inclusive, biased upward)",
                            "nearest_parent_cos (v1)": "parent centroid vs parent centroid (parent-parent; means of many members, so higher than child-child)",
                            "verdict": "the three are not on one scale; v1 compared them only implicitly. v2 must use leave-one-out child-to-parent scores."},
          "v1_children_closer_to_other_parent": int(m1["metrics"]["children_closer_to_other_parent"]),
          "loo_children_closer_to_other_parent": int(cchk.closer_to_other_parent_loo.sum()),
          "loo_margin_lt_0.02": int((cchk.margin_loo < hp.LOW_MARGIN).sum()), "placed_children": int(len(cchk)),
          "v1_suspicious_parents": len(v1_susp), "v2_rule_mixing_candidates": int(pchk.mixing_candidate_v2_rule.sum()),
          "mixing_not_in_v1_suspicious": sorted(pchk[pchk.mixing_candidate_v2_rule & ~pchk.v1_suspicious].parent_id),
          "P080": pchk[pchk.parent_id == "P080"].iloc[0][["sibling_member_affinity", "min_child_pair_cos", "v1_suspicious", "mixing_candidate_v2_rule"]].to_dict()}

    # 5. write -------------------------------------------------------------------------------------------------
    out.mkdir(parents=True, exist_ok=True)
    files = {"esco_purity_v2.csv": pur, "esco_uri_discrepancies_212.csv": disc, "esco_exact_match_trace.csv": trace,
             "hierarchy_parent_checks.csv": pchk, "hierarchy_child_placement_loo.csv": cchk}
    for f, d in files.items():
        d.to_csv(out / f, index=False)
    counts = {"discrepancy_rows": len(disc), "distinct_uris": int(disc.ref_id.nunique()),
              "by_class_rows": disc.classification.value_counts().to_dict(),
              "by_class_distinct_uris": disc.drop_duplicates("ref_id").classification.value_counts().to_dict(),
              "accepted_known_skill_rows": int((disc.verdict == "known_skill").sum()),
              "accepted_rows_no_lexical_overlap": int((disc.mapping_quality_flag == "no_lexical_overlap_review").sum()),
              "assigned_member_rows": int((disc.membership_state == "assigned").sum())}
    ready = (all(v1[k] for k in ("output_hashes_ok", "script_hash_ok", "input_hashes_ok", "rerun_identical", "ids_match"))
             and v1["excluded_with_parent"] == 0 and len(disc) == 212)
    (out / "preflight_report.md").write_text(report(v1, esco_summary, counts, trace, hm, pchk, ready), encoding="utf-8")
    assert before == {k: sha256(p) for k, p in inputs.items()}, "an input changed"
    man = {"version": "hierarchy_v2_preflight_v1", "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "scripts": {s: sha256(ROOT / "src" / s) for s in ("hierarchy_v2_preflight.py", "esco_levels.py", "build_hierarchy_proposal.py")},
           "inputs": {k: {"path": str(p).replace(str(Path.home()), "~"), "sha256": before[k]} for k, p in inputs.items()},
           "outputs": {f: sha256(out / f) for f in sorted(os.listdir(out))},
           "v1_integrity": v1, "esco": esco_summary, "discrepancies": counts, "hierarchy_metrics": hm,
           "thresholds": {"MIXING_SIBLING_AFFINITY": MIXING_SIBLING_AFFINITY, "MIXING_MIN_PAIR_COS": MIXING_MIN_PAIR_COS},
           "ready_for_v2": ready, "human_approved": False}
    (out / "manifest.json").write_text(json.dumps(man, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"v1": v1, "esco": esco_summary, "discrepancies": counts, "hierarchy": hm, "ready": ready}, indent=1, default=str))
    return man


def report(v1, es, dc, trace, hm, pchk, ready):
    L = ["# Hierarchy v2 preflight (v1)", "",
         "> Read-only checks. v1 artifacts, frozen inputs and accepted reference mappings were not changed. "
         "Findings and proposed handling are AI-generated and pending human approval.", "",
         f"**Verdict: {'READY FOR HIERARCHY PROPOSAL V2' if ready else 'BLOCKED FOR HIERARCHY PROPOSAL V2'}**", "",
         "## 1. v1 integrity", "", "| Check | Result |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in v1.items()]
    L += ["", "## 2. ESCO levels (corrected)", "",
          f"Source: {es['source']} ({es['version']}). Levels from `skillsHierarchy_en.csv`; parents from `broaderRelationsSkillPillar_en.csv`.", "",
          f"- Groups per level: {es['groups_per_level']} (Level 0 = {', '.join(es['level0_labels'])}).",
          f"- The audit column `esco_purity_level2` used the first-parent chain's `path[-2]`; for every resolvable link it is a **Level {list(es['legacy_rule_true_levels'])}** group "
          f"({es['legacy_rule_true_levels']}). It is renamed here as `audit_v1_column_esco_purity_level2_is_really_L1`; the audit file is unchanged.",
          f"- Corrected metric `esco_purity/2` (`src/esco_levels.py`): explicit level, multi-parent aware (weight 1/|groups|), links whose URI is not in v1.2.1 or "
          f"that have no ancestor at the level are counted and excluded; ≥ 3 usable links required.",
          f"- {es['skills_with_multiple_broader']} ESCO concepts have several broader parents; {es['links_with_multiple_L2_ancestors']} of our links have > 1 Level 2 ancestor "
          "(v1 hierarchy used the first parent only).",
          f"- Medians over topics: Level 1 purity {es['purity_L1_median']:.3f}, Level 2 purity {es['purity_L2_median']:.3f} ({es['topics_with_purity_L2']} topics).", "",
          "## 3. ESCO URI discrepancies (212 links)", "",
          f"Rows: {dc['discrepancy_rows']}; distinct URIs: {dc['distinct_uris']}; accepted (`known_skill`) rows: {dc['accepted_known_skill_rows']} "
          f"(no lexical overlap with the label: {dc['accepted_rows_no_lexical_overlap']}); rows on assigned members: {dc['assigned_member_rows']}.", "",
          "| Class | Links | Distinct URIs |", "|---|---:|---:|"]
    for c in ("VERSION_MISMATCH", "INVALID_IDENTIFIER", "MISSING_REFERENCE_EXPORT", "INCORRECT_ACCEPTED_MAPPING", "UNRESOLVED"):
        L.append(f"| {c} | {dc['by_class_rows'].get(c, 0)} | {dc['by_class_distinct_uris'].get(c, 0)} |")
    L += ["", "Rule order: invalid URI → Phase 3 confirmed-incorrect accepted link → URI referenced by v1.2.1 (concept scheme / scope note) "
          "without a record → label present in v1.2.1 under another URI → unresolved. No accepted mapping was replaced.", "",
          "## 4. The three 'exact' matches", "", "| Skill | Normalised key | Accepted label | v1.2.1 labels with the same key | Explained by v1.2.1 | Explanation |", "|---|---|---|---|---|---|"]
    L += [f"| {r.skill_key} | {r.normalised_key} | {r.accepted_ref_label} | {r.v121_labels_with_same_key} | {r.explained_by_v121} | {r.explanation} |" for r in trace.itertuples()]
    L += ["", "`link_reference.py` marks a match exact when `evaluate.norm` keys are equal; `norm` lower-cases, drops filler words "
          "(including 'experience', 'knowledge', 'skill') and strips a plural 's'. All three accepted mappings are wrong in context.", "",
          "## 5. Hierarchy similarity metrics", ""]
    L += [f"- **{k}**: {v}" for k, v in hm["metric_scales"].items()]
    L += [f"- Coherence recomputed for all 90 parents: match = {hm['coherence_all_match']}.",
          f"- Children closer to another parent: v1 (self-inclusive) {hm['v1_children_closer_to_other_parent']}; leave-one-out "
          f"**{hm['loo_children_closer_to_other_parent']} of {hm['placed_children']}**; LOO margin < {hp.LOW_MARGIN}: {hm['loo_margin_lt_0.02']}.",
          "- v1 never forced an excluded topic into a parent (see section 1).", "",
          "## 6. Suspicious-parent detection", "",
          f"- v1 flagged {hm['v1_suspicious_parents']} parents; its rules are implemented as documented (coherence p10, ESCO share < 0.30 with ≥ 8 links, "
          "≥ 2 split-pending children, nearest parent ≥ 0.95), but none of them measures member-level mixing.",
          f"- New member-level rule (sibling member affinity < {MIXING_SIBLING_AFFINITY} or weakest child pair < {MIXING_MIN_PAIR_COS}): "
          f"{hm['v2_rule_mixing_candidates']} candidates; not flagged by v1: {', '.join(hm['mixing_not_in_v1_suspicious'])}.",
          f"- P080 (Keyboarding and Typing | Switching Equipment): {hm['P080']}.",
          "- The new rule is a heuristic: some candidates are sensible pairs of distinct topics (e.g. Recruitment | Onboarding).", "",
          "| Parent | Children | Sibling affinity | Weakest pair | v1 flag | v2 rule | Child names |", "|---|---:|---:|---:|---|---|---|"]
    L += [f"| {r.parent_id} | {r.n_children} | {r.sibling_member_affinity} | {r.min_child_pair_cos} | {r.v1_suspicious} | {r.mixing_candidate_v2_rule} | {r.child_names[:120]} |"
          for r in pchk[pchk.mixing_candidate_v2_rule].sort_values("sibling_member_affinity").itertuples()]
    L += ["", "## 7. Remaining blockers / conditions for v2", "",
          "- Use leave-one-out child-to-parent scores for placement confidence and consistency checks.",
          "- Use `esco_purity/2` (explicit level, multi-parent) and exclude the 212 unresolvable links from ESCO features.",
          "- Add the member-level mixing check to the suspicious-parent rules.",
          "- The three wrong 'exact' links and the 34 wrong accepted links stay as they are until a human approves unlinking/remapping; v2 should down-weight or exclude them.",
          "- The v1.2 API export (`data/reference/esco_skills.csv`) is not available, so UNRESOLVED links cannot be traced further."]
    return "\n".join(L)


if __name__ == "__main__":
    main()
