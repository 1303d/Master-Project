"""Hierarchy Proposal v2.1: refinement rules on synthetic data + end-to-end determinism/protection on the real inputs.

    python -m pytest tests/sprint4/test_hierarchy_proposal_v2_1.py -q
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
from test_hierarchy_proposal_v2 import fake_ctx  # noqa: E402


def test_authoritative_confidence_excludes_split_candidates():
    ctx = fake_ctx()
    conf, m = v21.authoritative(ctx, [[0, 1], [2, 3]])
    margin_only = sum(1 for mg, _, _ in m.values() if mg >= v21.LOW_MARGIN)
    assert conf <= margin_only
    assert conf == sum(1 for j, (mg, _, _) in m.items() if mg >= v21.LOW_MARGIN and ctx.ids[j] not in ctx.split)


def test_refine_moves_only_with_evidence_and_never_twice():
    ctx = fake_ctx()
    start = {"Q001": [0, 1], "Q002": [2, 3]}
    parents, decisions, unresolved = v21.refine(ctx, start)
    placed = [j for g in parents.values() for j in g]
    assert len(placed) == len(set(placed))                                   # no duplicate placement
    assert all(len(g) >= 2 for g in parents.values())                       # no single-child parent
    assert sum(1 for d in decisions.values() if d["decision"].startswith("MOVE")) <= 4
    for j, d in decisions.items():
        if d["decision"] == "MOVE":
            assert d["margin_after"] > 0 and d["margin_after"] > d["margin_before"] and d["support_to"] >= d["support_from"]
    assert set(unresolved) | set(placed) <= {0, 1, 2, 3} and not (set(unresolved) & set(placed))
    assert start == {"Q001": [0, 1], "Q002": [2, 3]}                          # input not mutated


def test_refine_is_deterministic():
    a = v21.refine(fake_ctx(), {"Q001": [0, 1], "Q002": [2, 3]})
    b = v21.refine(fake_ctx(), {"Q001": [0, 1], "Q002": [2, 3]})
    assert a[0] == b[0] and a[2] == b[2] and {k: v["decision"] for k, v in a[1].items()} == {k: v["decision"] for k, v in b[1].items()}


INPUTS = all(Path(p).exists() for p in (v21.V2DIR / "manifest.json", v2.V1 / "manifest.json", v2.PREFLIGHT / "manifest.json", hp.ESCO / "skillsHierarchy_en.csv"))


@pytest.mark.skipif(not INPUTS, reason="v1/v2/preflight outputs or ESCO export not on this machine")
def test_v2_1_end_to_end(tmp_path):
    protect = [v2.V1, v2.PREFLIGHT, v21.V2DIR]
    before = {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for d in protect for f in d.iterdir()}
    m1 = v21.main(tmp_path / "a"); m2 = v21.main(tmp_path / "b")
    assert before == {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for d in protect for f in d.iterdir()}
    assert {f: h for f, h in m1["outputs"].items() if f != "manifest.json"} == {f: h for f, h in m2["outputs"].items() if f != "manifest.json"}
    assert m1["reconciliation"]["reconciled"] and m1["structural_problems"] == [] and m1["human_approved"] is False
    h = pd.read_csv(tmp_path / "a" / "hierarchy_proposal.csv", dtype=str, keep_default_na=False)
    p = pd.read_csv(tmp_path / "a" / "parent_categories.csv", dtype=str, keep_default_na=False)
    assert len(h) == 374 and h.topic_id.is_unique and h.set_index("topic_id").at["T0104", "placement_state"] == "UNRESOLVED_EXCLUDED"
    assert (h[h.placement_state == "UNRESOLVED_EXCLUDED"].parent_id == "").all() and (h.human_approved == "False").all()
    assert not p.proposed_label.str.contains(" / |and related topics|miscellaneous", case=False).any()
    c = pd.read_csv(tmp_path / "a" / "common_population_comparison.csv")
    assert list(c.version) == ["v1", "v2", "v2_1"] and c.common_topics.nunique() == 1
    comp = pd.read_csv(tmp_path / "a" / "fair_comparison.csv").set_index("metric")
    assert comp.at["confident_authoritative", "v2"] == m1["reconciliation"]["v2_state_PLACED_CONFIDENT"]
