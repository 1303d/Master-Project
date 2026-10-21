"""Focused tests for the scoring, validation and cleaning code.

    py -m pytest tests -q

The last test reproduces the official test-set score; it is skipped when the extraction output
(data/processed/, shared on Drive, not in Git) is not on this machine.
"""
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluate import match, norm  # noqa: E402
from extract_skills import validate_output  # noqa: E402
from gold_tool import hide_contacts  # noqa: E402


# ---------- evaluate.match ----------
def test_strict_needs_same_name():
    assert match(["SQL"], ["sql"], lenient=False)[0] == 1
    assert match(["multi-tasking"], ["multitasking"], lenient=False)[0] == 1
    assert match(["Visio"], ["Microsoft Visio"], lenient=False)[0] == 0


def test_lenient_accepts_word_subset():
    assert match(["Visio"], ["Microsoft Visio"], lenient=True)[0] == 1
    assert match(["prototyping"], ["high-fidelity prototyping"], lenient=True)[0] == 1


def test_one_to_one():
    tp, missed, extra = match(["python"], ["python", "Python"], lenient=True)
    assert tp == 1 and missed == [] and len(extra) == 1


def test_maximum_matching_beats_greedy():
    # Greedy pairs "excel" with "excel macros vba" first and then cannot place "excel macros".
    # The maximum matching finds both pairs: excel <-> excel pivot, excel macros <-> excel macros vba.
    gold, pred = ["excel", "excel macros"], ["excel macros vba", "excel pivot"]
    assert match(gold, pred, lenient=True)[0] == 2


def test_score_does_not_depend_on_order():
    gold = ["excel", "excel macros", "sql", "sql server", "python", "communication"]
    pred = ["excel macros vba", "excel pivot", "microsoft sql server", "sql", "python 3", "written communication"]
    expected = match(gold, pred, lenient=True)[0]
    rng = random.Random(0)
    for _ in range(20):
        g, p = gold[:], pred[:]
        rng.shuffle(g), rng.shuffle(p)
        assert match(g, p, lenient=True)[0] == expected


def test_norm_drops_filler_and_plurals():
    assert norm("Strong knowledge of financial analyses") == norm("financial analysis")


# ---------- extract_skills.validate_output ----------
@pytest.mark.parametrize("bad", [[], "text", None, {"skill": "x"}, {"skills": "SQL"}])
def test_malformed_output_raises(bad):
    with pytest.raises(ValueError):
        validate_output(bad)


def test_bad_items_dropped_and_counted():
    skills, dropped = validate_output({"skills": [
        {"skill": " SQL ", "evidence": " SQL "}, {"skill": ""}, {"evidence": "x"}, "Python", {"skill": 5},
        {"skill": "Excel"}]})
    assert skills == [{"skill": "SQL", "evidence": "SQL"}, {"skill": "Excel", "evidence": ""}]
    assert dropped == 4


# ---------- cleaning ----------
def test_contacts_masked():
    out = hide_contacts("Mail jane.doe@acme.com or call +1 (617) 555-1234 today")
    assert "jane.doe" not in out and "555" not in out and "[EMAIL]" in out and "[PHONE]" in out


def test_greenhouse_html_cleaned():
    pipeline = pytest.importorskip("pipeline")
    html = "&lt;p&gt;We need &lt;strong&gt;SQL&lt;/strong&gt;.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;"
    assert pipeline.clean(html) == "We need SQL.\n\n- Python"


def test_text_hash_ignores_case_and_spacing():
    db = pytest.importorskip("db")
    assert db.text_hash("Data  Analyst\nSQL") == db.text_hash("data analyst sql")
    assert db.text_hash("Data Analyst") != db.text_hash("Data Scientist")


# ---------- official evaluation ----------
def test_reproduce_official_test_score():
    if not (ROOT / "data" / "processed" / "statements_qwen_qwen3.8-27b_v3.csv").exists():
        pytest.skip("extraction output not on this machine (data/processed is shared via Drive)")
    out = subprocess.run([sys.executable, str(ROOT / "src" / "evaluate.py"), "--model", "qwen/qwen3.8-27b",
                          "--tag", "v3", "--split", "test"], capture_output=True, text=True, check=True).stdout
    row = next(line for line in out.splitlines() if line.startswith("| **All**"))
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert cells[1:4] == ["50", "649", "657"]          # postings, gold skills, predicted (gold after 2026-10-21 review)
    assert (cells[6], cells[9]) == ("0.66", "0.74")    # strict F1, lenient F1
