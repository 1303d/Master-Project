"""Hierarchy v2 preflight: metric helpers on synthetic data, then the full preflight on the frozen inputs when present.

    python -m pytest tests/sprint4/test_hierarchy_v2_preflight.py -q
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import hierarchy_v2_preflight as pf  # noqa: E402
import build_hierarchy_proposal as hp  # noqa: E402


def test_loo_removes_self_inclusion_bias():
    # child topic 0 sits in P1 with an unrelated sibling (topic 1); topic 2 (P2) is its real neighbour
    vecs = hp.unit(np.array([[0.0, 1.0], [0.05, 1.0], [1.0, 0.0], [1.0, 0.02], [0.1, 1.0], [0.12, 1.0]]))
    topic = np.array([0, 0, 1, 1, 2, 2])
    child = hp.unit(vecs[topic == 0].mean(0)[None])[0]
    sc = pf.loo_parent_scores(child, 0, {"P1": [0, 1], "P2": [2]}, topic, vecs)
    selfinc = vecs[np.isin(topic, [0, 1])].mean(0)
    selfinc_score = float(child @ (selfinc / np.linalg.norm(selfinc)))
    assert set(sc) == {"P1", "P2"}
    assert selfinc_score > sc["P1"] + 0.3          # the child's own members inflate the self-inclusive score
    assert sc["P2"] > sc["P1"]                      # leave-one-out reveals the better parent


def test_sibling_affinity_and_mixing_rule():
    topic = np.array([0, 0, 1, 1]); nearest_other = np.array([1, 5, 0, 7])
    assert pf.sibling_affinity([0, 1], topic, nearest_other) == pytest.approx(0.5)
    assert pf.mixing_candidate(0.10, 0.9) and pf.mixing_candidate(0.5, 0.70) and not pf.mixing_candidate(0.5, 0.9)


def test_norm_reproduces_exact_match_keys():
    assert pf.norm("design experience") == ("design",) and pf.norm("scales") == ("scale",) and pf.norm("Unity") == ("unity",)


INPUTS_PRESENT = (hp.OUT / "manifest.json").exists() and (hp.ESCO / "skillsHierarchy_en.csv").exists()


@pytest.mark.skipif(not INPUTS_PRESENT, reason="v1 outputs or ESCO export not on this machine")
def test_preflight_end_to_end(tmp_path):
    v1_before = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in hp.OUT.iterdir()}
    man = pf.main(tmp_path / "pre")
    assert {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in hp.OUT.iterdir()} == v1_before   # v1 untouched
    v1 = man["v1_integrity"]
    assert v1["rerun_identical"] and v1["ids_match"] and v1["excluded_with_parent"] == 0 and v1["topics"] == 374
    assert man["esco"]["legacy_rule_true_levels"] == {"1": man["esco"]["legacy_rule_true_levels"]["1"]}   # old metric = Level 1 only
    d = pd.read_csv(tmp_path / "pre" / "esco_uri_discrepancies_212.csv", dtype=str, keep_default_na=False)
    assert len(d) == 212 and d.classification.isin({"VERSION_MISMATCH", "INVALID_IDENTIFIER", "MISSING_REFERENCE_EXPORT",
                                                    "INCORRECT_ACCEPTED_MAPPING", "UNRESOLVED"}).all()
    t = pd.read_csv(tmp_path / "pre" / "esco_exact_match_trace.csv", dtype=str, keep_default_na=False).set_index("skill_key")
    assert t.at["design experience", "explained_by_v121"] == "True" and t.at["unity", "explained_by_v121"] == "False"
    pc = pd.read_csv(tmp_path / "pre" / "hierarchy_parent_checks.csv", dtype=str, keep_default_na=False).set_index("parent_id")
    assert pc.coherence_match.eq("True").all()
    assert pc.at["P080", "mixing_candidate_v2_rule"] == "True" and pc.at["P080", "v1_suspicious"] == "False"
    hm = man["hierarchy_metrics"]
    assert hm["loo_children_closer_to_other_parent"] >= hm["v1_children_closer_to_other_parent"]
    assert json.loads((tmp_path / "pre" / "manifest.json").read_text())["human_approved"] is False
