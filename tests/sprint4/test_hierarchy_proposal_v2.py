"""Hierarchy Proposal v2: corrected metrics and naming on synthetic data, plus an end-to-end determinism test.
No network, no database.

    python -m pytest tests/sprint4/test_hierarchy_proposal_v2.py -q
"""
import hashlib
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import build_hierarchy_proposal as hp  # noqa: E402
import build_hierarchy_proposal_v2 as v2  # noqa: E402


def fake_ctx():
    # 4 topics, 2 members each; topics 0,1 alike; topic 2 alike topic 3 except it sits nearer topic 1
    X = hp.unit(np.array([[1, 0, 0], [1, .1, 0], [1, .2, 0], [.9, .3, 0], [.6, .8, 0], [.5, .9, 0], [0, .2, 1], [0, .1, 1.]]))
    mt = np.array([0, 0, 1, 1, 2, 2, 3, 3])
    k = 4; S = np.zeros((k, 3)); np.add.at(S, mt, X)
    C = hp.unit(S); n = np.bincount(mt).astype(float)
    sc = X @ C.T; sc[np.arange(8), mt] = -np.inf; no = sc.argmax(1)
    N = np.zeros((k, k)); np.add.at(N, (mt, no), 1.0)
    W = np.array([[3.0, 0], [3, 0], [3, 0], [0, 3]])   # parent [2,3] mixes alpha and beta
    used = np.array([3.0, 3, 3, 3])
    a = pd.DataFrame({"skill_key": [f"s{i}" for i in range(8)], "t": mt})
    return SimpleNamespace(sum=S, C=C, n=n, N=N, ccos=C @ C.T, G={1: (["g1", "g2"], W, used), 2: (["g1", "g2"], W, used)},
                           ids=["T0", "T1", "T2", "T3"], split={"T3"}, glabels={"g1": "alpha group", "g2": "beta group"},
                           a=a, X=X, names={"T0": "Web Front-End Development", "T1": "Web Application Development",
                                            "T2": "Keyboarding and Typing", "T3": "Switching Equipment"})


def test_loo_margin_detects_misplaced_child():
    ctx = fake_ctx()
    m = v2.loo_margins(ctx, [[0, 1], [2, 3]])
    assert m[0][0] > 0 and m[1][0] > 0            # topics 0 and 1 belong together
    assert m[2][0] < 0                            # topic 2 is closer to the other parent once it is left out


def test_evaluate_keeps_definitions_separate():
    ctx = fake_ctx()
    s, pdf, _ = v2.evaluate(ctx, [[0, 1], [2, 3]], [0, 1, 2, 3])
    assert set(["coherence", "parent_separation", "sibling_affinity", "esco_purity_L1", "esco_purity_L2", "esco_coverage"]) <= set(pdf.columns)
    assert s["placed"] == 4 and s["loo_conflicts"] >= 1 and s["parents"] == 2
    assert pdf.esco_purity_L2.tolist() == [1.0, 0.5]       # second parent mixes two ESCO groups
    assert pdf.split_pending_children.tolist() == [0, 1]


def test_names_never_generic_and_flag_uncertainty():
    ctx = fake_ctx()
    _, pdf, _ = v2.evaluate(ctx, [[0, 1], [2, 3]], [0, 1, 2, 3])
    r0, r1 = pdf.to_dict("records")
    n0 = v2.name_parent(ctx, [0, 1], r0); n1 = v2.name_parent(ctx, [2, 3], r1)
    for n in (n0, n1):
        assert "related topics" not in n["proposed_label"].lower() and "miscellaneous" not in n["proposed_label"].lower()
    assert n0["label_basis"] == "shared child-name terms" and n0["proposed_label"].startswith("Web")
    assert n1["label_confidence"] == "low" and n1["needs_label_review"] and n1["label_uncertainty"]


INPUTS = all(Path(p).exists() for p in (v2.V1 / "manifest.json", v2.PREFLIGHT / "manifest.json", v2.LINKS38, hp.ESCO / "skillsHierarchy_en.csv"))


@pytest.mark.skipif(not INPUTS, reason="v1 / preflight / audit / ESCO inputs not on this machine")
def test_v2_end_to_end_deterministic(tmp_path):
    protect = [v2.V1, v2.PREFLIGHT]
    before = {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for d in protect for f in d.iterdir()}
    m1 = v2.main(tmp_path / "a"); m2 = v2.main(tmp_path / "b")
    after = {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for d in protect for f in d.iterdir()}
    assert before == after                                                   # v1 and preflight untouched
    for f in m1["outputs"]:
        if f != "manifest.json":
            assert m1["outputs"][f] == m2["outputs"][f], f                   # deterministic regeneration
    assert m1["structural_problems"] == [] and m1["human_approved"] is False and len(m1["suspect_links"]) == 37
    h = pd.read_csv(tmp_path / "a" / "hierarchy_proposal.csv", dtype=str, keep_default_na=False)
    p = pd.read_csv(tmp_path / "a" / "parent_categories.csv", dtype=str, keep_default_na=False)
    assert len(h) == 374 and h.topic_id.is_unique and (h.human_approved == "False").all()
    assert (h[h.placement_state.str.startswith("UNRESOLVED")].parent_id == "").all()
    assert h.set_index("topic_id").at["T0104", "placement_state"] == "UNRESOLVED_EXCLUDED"
    assert not p.proposed_label.str.contains("and related topics", case=False).any()
    c = pd.read_csv(tmp_path / "a" / "v1_vs_v2_comparison.csv")
    assert set(c.metric) == set(m1["metrics_v1_corrected"]) == set(m1["metrics_v2"])     # identical metric definitions
