"""Hierarchy Proposal v2.2: vectorised margins, sequential placement gates, label detectors, end-to-end determinism.

    python -m pytest tests/sprint4/test_hierarchy_proposal_v2_2.py -q
"""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_hierarchy_proposal as hp  # noqa: E402
import build_hierarchy_proposal_v2 as v2  # noqa: E402
import build_hierarchy_proposal_v2_1 as v21  # noqa: E402
import build_hierarchy_proposal_v2_2 as v22  # noqa: E402
from test_hierarchy_proposal_v2 import fake_ctx  # noqa: E402


def test_vectorised_margins_match_reference_definition():
    ctx = fake_ctx()
    parents = {"Q001": [0, 1], "Q002": [2, 3]}
    a = v22.all_margins(ctx, parents); b = v2.loo_margins(ctx, [parents[k] for k in sorted(parents)])
    assert set(a) == set(b) and np.allclose([a[k][0] for k in sorted(a)], [b[k][0] for k in sorted(a)])


def test_sequential_placement_respects_gates_and_is_deterministic():
    ctx = fake_ctx()
    start = {"Q001": [0, 1]}                                # topics 2, 3 unplaced candidates; only one parent
    r1 = v22.sequential_placement(ctx, start, [2, 3]); r2 = v22.sequential_placement(ctx, start, [2, 3])
    assert r1[0] == r2[0] and [a["topic"] for a in r1[1]] == [a["topic"] for a in r2[1]]
    assert start == {"Q001": [0, 1]}                         # input not mutated
    for a in r1[1]:
        assert all(a["gates"].values()) and a["new_conflicts"] == 0
    placed = [j for g in r1[0].values() for j in g]
    assert len(placed) == len(set(placed)) and set(r1[3]) | {a["topic"] for a in r1[1]} == {2, 3}
    assert set(r1[0]) == {"Q001"}                            # no new parents created
    assert r1[1] == [] and sorted(r1[3]) == [2, 3]           # one parent only: no margin can be computed -> nothing forced in


@pytest.mark.parametrize("label, dup", [("Planning Tools and Plan", True), ("Therapy and Therapeutic", True),
                                        ("Network and Networking", True), ("Cyber and Security", False), ("Regulations and Rules", False)])
def test_label_root_detector(label, dup):
    assert bool(v22.label_quality([label]).same_root_duplicate.iloc[0]) is dup


def test_label_quality_flags_concatenation_and_generic():
    q = v22.label_quality(["A / B", "X (and related topics)", "UNRESOLVED_LABEL", "Electrical"])
    assert q.concatenated.tolist() == [True, False, False, False] and q.generic.tolist() == [False, True, False, False]
    assert q.unresolved.tolist() == [False, False, True, False]


INPUTS = all(Path(p).exists() for p in (v22.V21 / "manifest.json", v2.OUT / "manifest.json", v2.V1 / "manifest.json", hp.ESCO / "skillsHierarchy_en.csv"))


@pytest.mark.skipif(not INPUTS, reason="prior hierarchy versions or ESCO export not on this machine")
def test_v2_2_end_to_end(tmp_path):
    protect = [v2.V1, v2.PREFLIGHT, v2.OUT, v22.V21]
    before = {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for d in protect for f in d.iterdir()}
    m1 = v22.main(tmp_path / "a"); m2 = v22.main(tmp_path / "b")
    assert before == {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for d in protect for f in d.iterdir()}
    assert {k: v for k, v in m1["outputs"].items() if k != "manifest.json"} == {k: v for k, v in m2["outputs"].items() if k != "manifest.json"}
    assert m1["structural_problems"] == [] and m1["human_approved"] is False and m1["v2_1_verified_counts"] == v22.EXPECT_V21
    h = pd.read_csv(tmp_path / "a" / "hierarchy_proposal.csv", dtype=str, keep_default_na=False)
    assert len(h) == 374 and h.topic_id.is_unique and h.set_index("topic_id").at["T0104", "placement_state"] == "UNRESOLVED_EXCLUDED"
    assert (h[h.placement_state == "UNRESOLVED_EXCLUDED"].parent_id == "").all() and (h.human_approved == "False").all()
    rec = pd.read_csv(tmp_path / "a" / "recovered_placements.csv")
    rej = pd.read_csv(tmp_path / "a" / "rejected_candidate_placements.csv", keep_default_na=False)
    assert len(rec) + len(rej) == m1["candidates"] == 137 and (rec.new_conflicts == 0).all()
    assert (rej.failed_gates != "").all()
