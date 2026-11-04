"""Sprint 4 step 3b (topic validity) on synthetic data and the fake-Groq pilot of test_topic_naming.py.
No network, no database.

    python -m pytest tests/sprint4 -q
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import topic_validity as tv  # noqa: E402
from test_topic_naming import IDS, RUN, Session, root, run  # noqa: E402,F401  (root is a pytest fixture)

VOCAB = {"vendor", "management", "payment", "processing", "coding", "languages", "bar", "regulations"}


def sig(members, band="medium", n_weak=0, coverage=0.5):
    s = tv.form_signals(members, VOCAB)
    return {**s, "cohesion_band": band, "n_assigned": len(members), "n_weak": n_weak, "coverage_any": coverage}


# ---------- signals and rules ----------
def test_acronym_detection():
    assert tv.acronym_like("ams", VOCAB) and tv.acronym_like("as9100", VOCAB) and tv.acronym_like("gc/ms", VOCAB)
    assert not tv.acronym_like("coding", VOCAB) and not tv.acronym_like("vendor management", VOCAB)
    assert not tv.acronym_like("payment", VOCAB) and tv.acronym_like("box", set())   # unknown short token


def test_stem_merges_word_forms():
    s = tv.form_signals(["purchasing", "purchase orders", "purchases", "deal registration"], set())
    assert s["head_word"] == "purch" and s["head_word_share"] == 0.75


@pytest.mark.parametrize("members, kw, expected", [
    (["gmp", "glp", "gcp", "gds", "gtp", "gms", "g code", "g suite", "grc", "gre"], {}, "surface_form_cluster"),      # same initial
    (["ams", "mes", "ims", "ats", "ias", "ids", "oas", "aas", "lis", "nms"], {}, "surface_form_cluster"),             # acronyms
    (["as9100", "ts16949", "five9", "7ks", "999", "a429", "j1939", "ca7", "as400", "rapid7"], {}, "surface_form_cluster"),
    (["containers", "chutes", "flexibility", "doilies", "pontoon", "umbrella", "sponges", "boating", "packing", "turbocourt"],
     {"band": "low"}, "mixed"),
    (["coding", "coding languages", "bar coding", "data coding", "matter coding", "charge coding", "method coding",
      "equipment coding", "hb coding", "simulink coder"], {"n_weak": 16}, "mixed"),                                      # weak > assigned
    (["vendor management", "vendor relations", "vendor risk", "vendor evaluation", "vendor coordination", "vendor liaison",
      "vendor negotiation", "vendor master", "vendor comparison", "vendor collaboration"], {"band": "high"}, "coherent"),
    (["iso 9001", "iso 14001", "iso 27001", "iso 13485", "iso 45001", "iso 22000", "iso 50001", "iso 17025", "iso 9000",
      "iso 31000"], {}, "coherent"),                                                                                     # digits but shared word
    (["arabic", "bengali", "cantonese", "creole", "french", "german", "hindi", "korean", "polish", "tagalog"],
     {"band": "low"}, "mixed"),                                                                                          # documented false positive
    (["alpha thing", "beta item", "gamma piece", "delta part", "omega bit", "sigma unit", "kappa block", "theta node",
      "lambda unit2", "zeta object"], {"coverage": 0.0}, "insufficient_evidence"),
    (["vendor a", "vendor b", "vendor c"], {}, "insufficient_evidence"),                                                  # < 10 assigned
])
def test_classification_rules(members, kw, expected):
    assert tv.classify(sig(members, **kw))[0] == expected


# ---------- integration on the fake pilot ----------
EXP = __import__("test_topic_features").EXP


def test_llm_output_does_not_decide_validity(root, monkeypatch):
    run(root, Session())
    base = tv.build(root, RUN, "r1", expected=EXP)["rows"]
    real = tv.load_pilot

    def flipped(*a):
        m, rows, h = real(*a)
        return m, {t: dict(r, llm_confidence="low" if r["llm_confidence"] != "low" else "high",
                           provisional_name="Something Else") for t, r in rows.items()}, h
    monkeypatch.setattr(tv, "load_pilot", flipped)
    other = tv.build(root, RUN, "r1", expected=EXP)["rows"]
    assert [r["validity_auto"] for r in base] == [r["validity_auto"] for r in other]
    assert [r["llm_confidence"] for r in base] != [r["llm_confidence"] for r in other]
    assert {r["topic_id"] for r in base} == set(IDS)


def review_file(root, topics):
    f = Path(root) / "config" / "topic_validity" / "pilot_review_v1.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"reviewer": "test", "status": "proposed", "topics": topics}))
    return f


def test_build_keeps_fields_separate_and_flags_non_coherent(root):
    run(root, Session())
    review_file(root, {"T0002": {"validity": "mixed", "root_causes": ["clustering_behavior"], "evidence": ["synthetic"]}})
    res = tv.build(root, RUN, "r1", expected=EXP)
    by = {r["topic_id"]: r for r in res["rows"]}
    assert tv.check_rows(res["rows"], IDS) == []
    r = by["T0002"]
    assert (r["llm_confidence"], r["validity_review"], r["validity_final"], r["validity_source"]) == ("medium", "mixed", "mixed", "review")
    assert r["cohesion_band"] in ("low", "medium", "high") and r["hierarchy_treatment"] == "hold_split_candidate"
    assert r["review_required"] and "validity mixed" in r["review_reason"]
    for x in res["rows"]:
        assert (x["validity_final"] == "coherent") == (x["hierarchy_treatment"] == "eligible")


def test_check_rows_rejects_eligible_non_coherent():
    row = {"topic_id": "T1", "validity_auto": "surface_form_cluster", "validity_final": "surface_form_cluster",
           "hierarchy_treatment": "eligible", "review_required": False, "validity_source": "auto", "root_causes": [],
           "head_word_share": 0.0, "acronym_share": 0.9, "digit_share": 0.0}
    assert any("not hierarchy-eligible" in p for p in tv.check_rows([row], ["T1"]))
    hidden = dict(row, validity_auto="coherent", validity_final="coherent")
    assert any("coherent despite surface-form" in p for p in tv.check_rows([hidden], ["T1"]))
    assert any("exactly once" in p for p in tv.check_rows([row, row], ["T1"]))


@pytest.mark.parametrize("topic, msg", [
    ({"validity": "valid", "root_causes": ["embedding_similarity"], "evidence": ["x"]}, "validity"),
    ({"validity": "mixed", "root_causes": ["bad_luck"], "evidence": ["x"]}, "root_causes"),
    ({"validity": "mixed", "root_causes": [], "evidence": ["x"]}, "root_causes"),
    ({"validity": "mixed", "root_causes": ["clustering_behavior"], "evidence": []}, "evidence")])
def test_review_file_validation(tmp_path, topic, msg):
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"reviewer": "t", "status": "proposed", "topics": {"T1": topic}}))
    with pytest.raises(ValueError, match=msg):
        tv.load_review(f)


def test_pilot_outputs_unchanged_and_no_overwrite(root):
    run(root, Session())
    d = tv.tn.naming_dir(root, RUN) / "r1"
    before = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in d.iterdir()}
    res = tv.build(root, RUN, "r1", expected=EXP)
    out, summary = tv.write(res, root, RUN, "r1")
    assert {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in d.iterdir()} == before
    assert summary["checks"] == [] and summary["naming_run_files_sha256"]["results.jsonl"] == before["results.jsonl"]
    assert (out / "topic_validity_review.md").is_file() and (out / "topic_validity_all.csv").is_file()
    tracked = (tv.tn.tracked_dir(root, RUN) / "validity_v1_r1" / "validity_summary.json").read_text()
    assert "z00" not in tracked                                                   # tracked copy lists no members
    with pytest.raises(FileExistsError):
        tv.write(res, root, RUN, "r1")


def test_changed_pilot_run_is_refused(root):
    run(root, Session())
    p = tv.tn.naming_dir(root, RUN) / "r1" / "results.jsonl"
    p.write_text(p.read_text().replace("Area", "Zone"))
    with pytest.raises(SystemExit, match="changed since it was written"):
        tv.build(root, RUN, "r1", expected=EXP)
