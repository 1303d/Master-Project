"""Tests for Sprint 3 skill preparation and embedding validation, on small synthetic fixtures.

    py -m pytest tests/test_skill_prep.py -q

No model is downloaded and no vectors are generated: embedding tests cover only the checks around encode().
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from embed_skills import build_index, validate_config, validate_skills, validate_vectors  # noqa: E402
from prepare_skills import prepare, skill_key, validate_inputs  # noqa: E402

DESC_A = "Must know Python and SQL. Knowledge of Avaya phone systems, CMS and Call Witness."
DESC_B = "Uses python daily. Excel required."


def fixtures():
    postings = pd.DataFrame({"posting_id": ["p1", "p2"], "description": [DESC_A, DESC_B]})
    statements = pd.DataFrame({
        "statement_id": ["p1:skill:1", "p1:skill:2", "p1:skill:3", "p2:skill:1", "p2:skill:2"],
        "posting_id": ["p1", "p1", "p1", "p2", "p2"],
        "skill": ["Python", " SQL ", "CMS", "python", "Excel"],
        "evidence": ["know Python", "SQL", "Knowledge of... CMS", "python", "Excel required"],
        "evidence_in_text": ["True", "True", "False", "True", "True"],
    })
    start = DESC_A.index("Knowledge of")
    approved = pd.DataFrame([{
        "statement_id": "p1:skill:3", "posting_id": "p1", "original_skill": "CMS", "proposed_skill": "CMS",
        "original_evidence": "Knowledge of... CMS", "proposed_evidence": DESC_A[start:],
        "evidence_start": str(start), "evidence_end": str(len(DESC_A)), "decision": "keep",
        "reviewer_confirmation": "approved",
    }])
    return statements, approved, postings


# ---------- prepare_skills ----------
def test_key_is_lowercase_and_outer_trim_only():
    assert skill_key("  Microsoft  Excel ") == "microsoft  excel"
    assert skill_key("SOPs") == "sops"  # no plural stripping
    assert skill_key("A/C machines") == "a/c machines"  # punctuation kept


def test_correction_applied_and_originals_kept():
    st, ap, po = fixtures()
    validate_inputs(st, ap, po)
    m, _ = prepare(st, ap)
    row = m.set_index("statement_id").loc["p1:skill:3"]
    assert row["evidence"] == "Knowledge of Avaya phone systems, CMS and Call Witness."
    assert row["original_evidence"] == "Knowledge of... CMS"
    assert row["original_skill"] == "CMS" and row["review_status"] == "approved_flagged_entry"
    assert (m.set_index("statement_id").drop("p1:skill:3")["review_status"] == "not_manually_reviewed").all()
    assert m["statement_id"].tolist() == st["statement_id"].tolist()  # every statement link kept, same order


def test_counts_and_no_synonym_merge():
    st, ap, _ = fixtures()
    _, u = prepare(st, ap)
    u = u.set_index("skill_key")
    assert u.loc["python", "mention_count"] == 2 and u.loc["python", "posting_count"] == 2
    assert u.loc["sql", "display_label"] == " SQL "  # display = original spelling, not cleaned
    assert list(u.index) == sorted(u.index) and len(u) == 4
    assert u["mention_count"].sum() == len(st)


def test_display_label_tie_goes_to_first_seen():
    st, ap, _ = fixtures()
    _, u = prepare(st, ap)
    assert u.set_index("skill_key").loc["python", "display_label"] == "Python"


@pytest.mark.parametrize("col,value,msg", [
    ("posting_id", "p2", "posting_id"),
    ("original_skill", "Cms", "original_skill"),
    ("original_evidence", "something else", "original_evidence"),
    ("reviewer_confirmation", "pending", "reviewer_confirmation"),
    ("decision", "drop", "decision"),
    ("proposed_evidence", "Knowledge of Avaya", "exact text"),
    ("evidence_start", "0", "exact text"),
    ("statement_id", "p9:skill:1", "not in statements"),
])
def test_bad_approval_rejected(col, value, msg):
    st, ap, po = fixtures()
    ap.loc[0, col] = value
    with pytest.raises(ValueError, match=msg):
        validate_inputs(st, ap, po)


def test_statement_posting_must_exist():
    st, ap, po = fixtures()
    st.loc[4, "posting_id"] = "p9"
    with pytest.raises(ValueError, match="not in postings"):
        validate_inputs(st, ap, po)


def test_duplicate_ids_rejected():
    st, ap, po = fixtures()
    st.loc[1, "statement_id"] = "p1:skill:1"
    with pytest.raises(ValueError, match="duplicate statement_id"):
        validate_inputs(st, ap, po)


def test_cli_writes_manifest_and_refuses_overwrite(tmp_path):
    st, ap, po = fixtures()
    for name, df in [("st.csv", st), ("ap.csv", ap), ("po.csv", po)]:
        df.to_csv(tmp_path / name, index=False)
    cmd = [sys.executable, str(ROOT / "src" / "prepare_skills.py"), "--statements", str(tmp_path / "st.csv"),
           "--approved", str(tmp_path / "ap.csv"), "--postings", str(tmp_path / "po.csv"),
           "--out-dir", str(tmp_path / "out")]
    subprocess.run(cmd, check=True, capture_output=True)
    man = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert man["mentions"] == 5 and man["unique_skills"] == 4 and man["approved_flagged_entries"] == 1
    assert man["synonyms_merged"] is False and man["fully_manually_reviewed"] is False
    assert len(man["sha256"]) == 5
    again = subprocess.run(cmd, capture_output=True, text=True)
    assert again.returncode != 0 and "Refusing to overwrite" in again.stderr


# ---------- embed_skills (validation only) ----------
CONFIG = {"model_id": "BAAI/bge-small-en-v1.5", "revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
          "dimensions": 4, "device": "cpu", "input_column": "skill_key", "input_template": "{skill_key}",
          "normalize_embeddings": True}


def unit(n, d, seed=0):
    v = np.random.default_rng(seed).normal(size=(n, d)).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def test_good_vectors_pass():
    validate_vectors(unit(3, 4), 3, 4)


@pytest.mark.parametrize("break_it,msg", [
    (lambda v: v[:2], "shape"),
    (lambda v: v[:, :3], "shape"),
    (lambda v: v.astype(np.float64), "dtype"),
    (lambda v: np.where(np.arange(4) == 0, np.nan, v).astype(np.float32), "non-finite"),
    (lambda v: v * 2, "unit length"),
])
def test_bad_vectors_rejected(break_it, msg):
    with pytest.raises(ValueError, match=msg):
        validate_vectors(break_it(unit(3, 4)), 3, 4)


def test_config_must_pin_revision_and_have_no_prefix():
    validate_config(CONFIG)
    for change in [{"revision": "main"}, {"input_template": "query: {skill_key}"},
                   {"normalize_embeddings": False}]:
        with pytest.raises(ValueError):
            validate_config({**CONFIG, **change})
    with pytest.raises(ValueError, match="missing"):
        validate_config({k: v for k, v in CONFIG.items() if k != "revision"})


def test_index_maps_rows_explicitly():
    st, ap, _ = fixtures()
    _, u = prepare(st, ap)
    idx = build_index(u)
    assert idx["vector_row"].tolist() == list(range(len(u)))
    assert idx["skill_key"].tolist() == u["skill_key"].tolist()


def test_skills_table_checks():
    st, ap, _ = fixtures()
    _, u = prepare(st, ap)
    validate_skills(u)
    with pytest.raises(ValueError, match="duplicate"):
        validate_skills(pd.concat([u, u.head(1)]))
    with pytest.raises(ValueError, match="not normalised"):
        validate_skills(u.assign(skill_key=u["skill_key"].str.upper()))


def test_embed_cli_refuses_overwrite_before_loading_model(tmp_path):
    (tmp_path / "vectors.npy").write_bytes(b"existing")
    cmd = [sys.executable, str(ROOT / "src" / "embed_skills.py"), "--skills", "unused.csv",
           "--model-config", "unused.json", "--out-dir", str(tmp_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode != 0 and "Refusing to overwrite" in r.stderr
    assert (tmp_path / "vectors.npy").read_bytes() == b"existing"
