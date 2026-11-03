"""merge_runs.py: an empty or identical second run changes nothing; repeats are dropped with evaluate.py's norm().

    py -m pytest tests/test_merge_runs.py -q
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import merge_runs as mr  # noqa: E402

COLS = ["statement_id", "posting_id", "skill", "evidence", "evidence_in_text", "provider", "model", "prompt_version"]


def write_run(p, name, items, posts=("li_1", "li_2")):
    rows = [{"statement_id": f"{pid}:skill:{i}", "posting_id": pid, "skill": s, "evidence": s, "evidence_in_text": True,
             "provider": "groq", "model": "m", "prompt_version": name} for i, (pid, s) in enumerate(items, 1)]
    pd.DataFrame(rows, columns=COLS).to_csv(p / f"statements_{name}.csv", index=False)
    pd.DataFrame([{"posting_id": pid, "status": "done", "n_skills": 0, "tokens_in": 10, "tokens_out": 5} for pid in posts]
                 ).to_csv(p / f"extraction_postings_{name}.csv", index=False)


@pytest.fixture
def p(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "P", tmp_path)
    write_run(tmp_path, "a", [("li_1", "cycle counts"), ("li_1", "Excel"), ("li_2", "Python")])
    return tmp_path


def skills(p, name):
    return pd.read_csv(p / f"statements_{name}.csv")[["posting_id", "skill"]].values.tolist()


def test_empty_second_run_gives_first_back(p):
    write_run(p, "empty", [])
    mr.main("a", "empty", "out")
    assert skills(p, "out") == skills(p, "a")


def test_same_run_twice_gives_first_back(p):
    mr.main("a", "a", "out")
    assert skills(p, "out") == skills(p, "a")


def test_repeats_dropped_with_norm(p):
    # plural and case variants are the same item under norm(); a new skill is added once
    write_run(p, "b", [("li_1", "Cycle Count"), ("li_1", "excel"), ("li_2", "SQL"), ("li_2", "sql")])
    mr.main("a", "b", "out")
    assert skills(p, "out") == skills(p, "a") + [["li_2", "SQL"]]
