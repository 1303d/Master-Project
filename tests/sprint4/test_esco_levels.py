"""ESCO level definitions: Level 1 and Level 2 must never be confused (synthetic hierarchy + real v1.2.1 when present).

    python -m pytest tests/sprint4/test_esco_levels.py -q
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import esco_levels as el  # noqa: E402
import build_hierarchy_proposal as hp  # noqa: E402

# L0 root -> L1 "A" -> L2 "A1" -> L3 "A1x" -> skill s1 ; s2 has two L2 ancestors (A1, B1)
LEVEL_OF = {"root": 0, "A": 1, "B": 1, "A1": 2, "B1": 2, "A1x": 3}
PARENTS = {"s1": ["A1x"], "A1x": ["A1"], "A1": ["A"], "A": ["root"], "B1": ["B"], "B": ["root"], "s2": ["A1", "B1"]}
SKILLS = {"s1", "s2"}


def test_ancestors_by_explicit_level():
    assert el.ancestors_at_level("s1", 1, LEVEL_OF, PARENTS) == {"A"}
    assert el.ancestors_at_level("s1", 2, LEVEL_OF, PARENTS) == {"A1"}
    assert el.ancestors_at_level("s1", 3, LEVEL_OF, PARENTS) == {"A1x"}
    assert el.ancestors_at_level("s2", 2, LEVEL_OF, PARENTS) == {"A1", "B1"}     # multi-parent aware


def test_legacy_rule_returns_level_1_not_level_2():
    g = el.legacy_first_parent_group("s1", PARENTS)
    assert LEVEL_OF[g] == 1 and g != next(iter(el.ancestors_at_level("s1", 2, LEVEL_OF, PARENTS)))


def test_purity_levels_and_missing_handling():
    by_topic = {"T": ["s1", "s2", "s1", "zz-not-in-esco"]}
    p1 = el.purity(by_topic, 1, LEVEL_OF, PARENTS, SKILLS).iloc[0]
    p2 = el.purity(by_topic, 2, LEVEL_OF, PARENTS, SKILLS).iloc[0]
    assert p1.n_uri_not_in_v121 == 1 and p1.n_used == 3 and p2.n_used == 3
    assert p2.top_group_uri == "A1" and p2.purity == pytest.approx((1 + 0.5 + 1) / 3, abs=1e-4)   # s2 splits 0.5/0.5
    assert p1.top_group_uri == "A" and p1.level == 1 and p2.level == 2
    assert el.purity({"T": ["s1", "s1"]}, 2, LEVEL_OF, PARENTS, SKILLS).iloc[0].purity is None     # < 3 usable links


ESCO = hp.ESCO


@pytest.mark.skipif(not (ESCO / "skillsHierarchy_en.csv").exists(), reason="ESCO v1.2.1 export not on this machine")
def test_real_v121_levels():
    level_of, parents, labels, skills = el.load(ESCO)
    counts = {lv: sum(1 for v in level_of.values() if v == lv) for lv in el.LEVELS}
    assert counts == {0: 4, 1: 28, 2: 156, 3: 452}
    l1 = {labels[u] for u, lv in level_of.items() if lv == 1}
    assert "communication, collaboration and creativity" in l1                       # a Level 1 group
    some = [u for u in list(skills)[:3000] if el.legacy_first_parent_group(u, parents)]
    assert some and all(level_of.get(el.legacy_first_parent_group(u, parents)) in (0, 1) for u in some)
    for u in some[:500]:
        assert all(level_of[g] == 2 for g in el.ancestors_at_level(u, 2, level_of, parents))
