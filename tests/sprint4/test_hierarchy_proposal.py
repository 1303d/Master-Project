"""Sprint 4 Phase 3 hierarchy proposal: unit tests on synthetic data + an integration test on the frozen snapshot.
No network, no database. The integration test is skipped when the frozen snapshot is not on this machine.

    python -m pytest tests/sprint4/test_hierarchy_proposal.py -q
"""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import build_hierarchy_proposal as hp  # noqa: E402


def test_member_affinity_symmetric_and_counts_nearest_other():
    C = hp.unit(np.array([[1.0, 0, 0], [0.9, 0.1, 0], [0, 0, 1.0]]))
    X = hp.unit(np.array([[1.0, 0.05, 0], [1.0, 0.0, 0.01], [0.85, 0.15, 0], [0, 0.1, 1.0]]))
    A = hp.member_affinity(X, np.array([0, 0, 1, 2]), C)
    assert np.allclose(A, A.T)
    assert A[0, 1] > A[0, 2]          # topic-0 members point at topic 1, not topic 2


def test_profile_cosine_nan_without_profile():
    P = np.array([[3.0, 0], [6.0, 0], [0, 0]])
    S = hp.profile_cosine(P, np.array([True, True, False]))
    assert S[0, 1] == pytest.approx(1.0) and np.isnan(S[0, 2]) and np.isnan(S[2, 2])


def test_combined_distance_renormalises_and_is_valid():
    ccos = np.array([[1, 0.9], [0.9, 1.0]]); aff = np.array([[0, 0.2], [0.2, 0]])
    D1 = hp.combined_distance(ccos, aff, np.full((2, 2), np.nan))
    D2 = hp.combined_distance(ccos, aff, np.array([[1, 1.0], [1.0, 1]]))
    assert D1[0, 0] == 0 and D1[0, 1] == D1[1, 0] and D1[0, 1] >= 0
    assert D1[0, 1] == pytest.approx(0.7 * 0.1 / 0.85)       # ESCO term dropped, weights renormalised
    assert D2[0, 1] == pytest.approx(0.7 * 0.1 / 1.0)


def test_choose_cut_respects_limits():
    pts = np.array([[0.0], [0.01], [0.02], [1.0], [1.01], [2.0], [2.01], [3.0], [3.01], [4.0]])
    D = np.abs(pts - pts.T)
    Z = linkage(squareform(D, checks=False), method="average")
    t, lab, diag = hp.choose_cut(Z, len(pts), grid=np.round(np.arange(0.005, 0.5, 0.005), 3))
    sizes = np.bincount(lab)[1:]
    assert (sizes == 1).sum() / len(pts) <= hp.MAX_SINGLETON_SHARE and sizes.max() <= hp.MAX_PARENT_SIZE
    assert diag[-1]["threshold"] == t


def _toy(parent_ok=True):
    h = pd.DataFrame({"topic_id": ["T1", "T2", "T3", "T4"], "parent_id": ["P001", "P001", "P002" if parent_ok else "P009", ""],
                      "placement_state": ["PLACED", "PLACED", "PLACED", "UNRESOLVED_SINGLETON"]})
    p = pd.DataFrame({"parent_id": ["P001", "P002"], "n_children": [2, 1], "child_topic_ids": ["T1;T2", "T3"]})
    c = {t: np.array([1.0, 0]) for t in "T1 T2".split()} | {"T3": np.array([0, 1.0]), "T4": np.array([0.7, 0.7])}
    return h, p, c, {"P001": np.array([1.0, 0]), "P002": np.array([0, 1.0])}


def test_validate_flags_single_child_and_missing_parent():
    h, p, c, pc = _toy()
    probs, m = hp.validate(h, p, 4, c, pc)
    assert any("single-child" in x for x in probs) and m["unresolved"] == 1
    h2, p2, c2, pc2 = _toy(parent_ok=False)
    probs2, _ = hp.validate(h2, p2, 4, c2, pc2)
    assert any("missing parent" in x for x in probs2) and any("inconsistent" in x for x in probs2)


SNAP = ROOT / f"data/processed/sprint4_input_{hp.RUN}/vectors.npy"


@pytest.mark.skipif(not (SNAP.exists() and hp.AUDIT.exists() and hp.VALIDITY.exists()), reason="frozen inputs not on this machine")
def test_integration_deterministic_and_valid(tmp_path):
    m1 = hp.main(tmp_path / "a"); m2 = hp.main(tmp_path / "b")
    f = "hierarchy_proposal.csv"
    assert hashlib.sha256((tmp_path / "a" / f).read_bytes()).digest() == hashlib.sha256((tmp_path / "b" / f).read_bytes()).digest()
    assert m1["structural_problems"] == [] and m1 == m2
    h = pd.read_csv(tmp_path / "a" / f, dtype=str, keep_default_na=False)
    p = pd.read_csv(tmp_path / "a" / "parent_categories.csv", dtype=str, keep_default_na=False)
    assert len(h) == 374 and h.topic_id.is_unique and m1["placed"] + m1["unresolved"] == 374
    assert (h[h.placement_state.str.startswith("UNRESOLVED")].parent_id == "").all()
    assert h[h.topic_id == "T0104"].placement_state.iat[0] == "UNRESOLVED_EXCLUDED"     # user-approved INVESTIGATE_CLUSTER
    assert p.n_children.astype(int).min() >= 2 and (p.ai_label.str.contains("UNREVIEWED")).all()
    names = pd.read_csv(hp.NAMES, dtype=str, keep_default_na=False).set_index("topic_id").provisional_name
    assert (h.set_index("topic_id").provisional_name == names.loc[h.topic_id].values).all()   # names untouched
