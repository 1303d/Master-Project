"""Sprint 4 step 3c (validity audit) on synthetic rows and the fake-Groq pilot. No network, no database.

    python -m pytest tests/sprint4 -q
"""
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import topic_validity as tv  # noqa: E402
import validity_audit as va  # noqa: E402
from test_topic_features import EXP  # noqa: E402
from test_topic_naming import RUN, Session, root, run  # noqa: E402,F401  (root is a pytest fixture)


def fake_rows(n_coh=300, n_mix=40, n_sur=30, dev=va.DEV_TOPICS):
    rows, rng = [], random.Random(3)
    classes = ["coherent"] * n_coh + ["mixed"] * n_mix + ["surface_form_cluster"] * n_sur
    for i, c in enumerate(classes):
        rows.append({"topic_id": f"T{i + 1000:04d}", "validity_auto": c, "validity_auto_reason": "x",
                     "cohesion_band": rng.choice(["low", "medium", "high"]), "cos_mean": rng.random(),
                     "coverage_any": rng.random(), "n_assigned": rng.randint(10, 90), "n_weak": rng.randint(0, 50),
                     "in_pilot": "false", "provisional_name": ""})
    rows += [dict(rows[0], topic_id=t, validity_auto="surface_form_cluster") for t in dev]
    return rows


# ---------- sampling ----------
def test_sample_sizes_exclusion_and_probabilities():
    rows = fake_rows()
    s = va.select_sample(rows)
    assert s["pool_size"] == 370 and not set(va.DEV_TOPICS) & set(s["review_order"])
    assert {c: v["n"] for c, v in s["strata"].items()} == va.PLAN and len(set(s["review_order"])) == 30
    assert {c: v["N"] for c, v in s["strata"].items()} == {"coherent": 300, "mixed": 40, "surface_form_cluster": 30}
    for c, v in s["strata"].items():
        assert v["inclusion_probability"] == v["n"] / v["N"] and v["weight"] == v["N"] / v["n"]
        assert all(s["chosen"][t][1]["validity_auto"] == c for t in v["topics"])


def test_sample_reproducible_and_seed_dependent():
    rows = fake_rows()
    a, b = va.select_sample(rows), va.select_sample(rows)
    assert a["review_order"] == b["review_order"] and va.select_sample(rows, seed=7)["review_order"] != a["review_order"]
    order = [a["chosen"][t][0] for t in a["review_order"]]
    assert order != sorted(order, key=list(va.PLAN).index)                       # shuffled, not grouped by stratum


def test_systematic_sampling_gives_equal_inclusion_probability():
    pool = list(range(17))
    hits = Counter()
    for seed in range(6000):
        picks, _, _ = va.systematic(pool, 5, random.Random(seed))
        assert len(set(picks)) == 5
        hits.update(picks)
    for i in pool:
        assert abs(hits[i] / 6000 - 5 / 17) < 0.03


def test_sample_spreads_over_cohesion_and_size():
    s = va.select_sample(fake_rows())
    d = va.diversity(s)
    assert set(d["cohesion_band"]) == {"low", "medium", "high"} and d["n_assigned"][1] - d["n_assigned"][0] > 30


# ---------- blinding ----------
def test_blind_check_catches_leaks():
    ev = [{"topic_id": "T1", "representative_skills": ["payment processing"], "weak_examples": [], "assigned_members": [],
           "neighbour_topics": []}]
    assert va.check_blind({"a.md": b"payment processing"}, ev, ["Payment Processing"]) == []   # name = a member skill
    assert va.check_blind({"a.md": b"Media Strategy"}, ev, ["Media Strategy"])
    ev2 = [dict(ev[0], representative_skills=["agile project management methodologies"])]
    assert va.check_blind({"a.md": b"| agile project management methodologies |"}, ev2, ["Project Management Methodologies"]) == []
    assert va.check_blind({"a.md": b"auto: surface_form_cluster"}, ev, [])
    assert va.check_blind({"a.md": b"ok"}, [dict(ev[0], validity_auto="mixed")], [])


# ---------- sheet and evaluation ----------
def label(t, v, conf="high", hier="no", reviewer="Lochan"):
    return {"topic_id": t, "human_validity": v, "supporting_evidence": "members x, y", "suspected_problems": "none",
            "reviewer_confidence": conf, "enter_hierarchy": hier, "notes": "", "reviewer": reviewer, "reviewed_utc": "2026-11-05"}


def known_case():
    preds, done = {}, []
    for i in range(12):
        t = f"C{i:02d}"
        preds[t] = {"stratum": "coherent", "validity_auto": "coherent", "hierarchy_treatment_auto": "eligible",
                    "exposed_in_session_2026_11_03": i < 3}
        done.append(label(t, "coherent" if i < 10 else "mixed", hier="yes" if i < 10 else "no"))
    for i in range(12):
        t = f"M{i:02d}"
        preds[t] = {"stratum": "mixed", "validity_auto": "mixed", "hierarchy_treatment_auto": "hold_split_candidate",
                    "exposed_in_session_2026_11_03": False}
        done.append(label(t, "mixed" if i < 6 else "coherent"))
    for i in range(6):
        t = f"S{i:02d}"
        preds[t] = {"stratum": "surface_form_cluster", "validity_auto": "surface_form_cluster",
                    "hierarchy_treatment_auto": "exclude_until_reclustered", "exposed_in_session_2026_11_03": True}
        done.append(label(t, "surface_form_cluster"))
    return {"predictions": preds}, done, {"coherent": 300, "mixed": 40, "surface_form_cluster": 30}


def test_evaluation_metrics_known_answer():
    sealed, done, N = known_case()
    e = va.evaluate(done, sealed, N)
    cm = e["confusion_matrix_sample"]["counts"]
    assert cm["coherent"]["coherent"] == 10 and cm["coherent"]["mixed"] == 2 and cm["mixed"]["coherent"] == 6
    assert e["sample_agreement"] == round(22 / 30, 4)
    pc = e["per_class"]
    assert pc["coherent"]["precision"] == round(10 / 12, 4) and pc["mixed"]["precision"] == 0.5
    assert pc["surface_form_cluster"]["precision"] == 1.0
    assert e["population_agreement_weighted"] == round(300 / 370, 4)               # (250 + 20 + 30) / 370
    assert pc["coherent"]["recall_population_weighted"] == round(250 / 270, 4)
    assert pc["mixed"]["recall_population_weighted"] == round(20 / 70, 4)
    assert pc["coherent"]["recall_sample"] == round(10 / 16, 4)                     # differs from the weighted value
    assert sorted(e["false_coherent"]) == ["C10", "C11"] and len(e["false_mixed"]) == 6 and e["false_surface_form"] == []
    lo, hi = e["population_agreement_95ci"]
    assert lo <= 300 / 370 <= hi and e["status"] == "complete human review"
    assert e["agreement_exposed_topics"]["n"] == 9 and e["agreement_blind_topics"]["n"] == 21
    assert e["hierarchy_gate_auto_eligible_but_human_no"] == 2


def write_sheet(path, rows):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=va.SHEET_COLS)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            w.writerow({"review_order": i, **{k: r.get(k, "") for k in va.SHEET_COLS if k != "review_order"}})


def test_sheet_validation(tmp_path):
    ids = ["T1", "T2"]
    f = tmp_path / "s.csv"
    write_sheet(f, [{"topic_id": "T1"}, {"topic_id": "T2"}])
    done, probs = va.read_sheet(f, ids)
    assert done == [] and any("2 of 2 topics have no complete human decision" in p for p in probs)
    write_sheet(f, [label("T1", "valid"), label("T2", "coherent", reviewer="claude")])
    _, probs = va.read_sheet(f, ids)
    assert any("human_validity" in p for p in probs) and any("reviewer must be" in p for p in probs)
    write_sheet(f, [label("T1", "mixed"), {"topic_id": "T2"}])
    done, probs = va.read_sheet(f, ids, allow_partial=True)
    assert len(done) == 1 and probs == []
    assert va.read_sheet(f, ids)[1]                                                  # not complete without the flag


def package(tmp_path, sealed, ids, N):
    d = tmp_path / "pkg"
    (d / "sealed").mkdir(parents=True)
    b = json.dumps(sealed).encode()
    (d / "sealed" / "auto_predictions.json").write_bytes(b)
    (d / "manifest.json").write_text(json.dumps({"sealed_predictions_sha256": va.sha(b), "topics_sorted": sorted(ids),
                                                 "strata": {c: {"N": n} for c, n in N.items()}}))
    return d


def test_run_evaluate_refuses_blank_tampered_and_marks_partial(tmp_path, monkeypatch):
    sealed, done, N = known_case()
    ids = [r["topic_id"] for r in done]
    d = package(tmp_path, sealed, ids, N)
    monkeypatch.setattr(va, "audit_dir", lambda *a: d)
    write_sheet(d / "reviewer_sheet.csv", [{"topic_id": t} for t in ids])
    with pytest.raises(SystemExit, match="not ready"):
        va.run_evaluate(sheet=d / "reviewer_sheet.csv")
    write_sheet(d / "reviewer_sheet.csv", done[:5] + [{"topic_id": t} for t in ids[5:]])
    p, e = va.run_evaluate(sheet=d / "reviewer_sheet.csv", allow_partial=True)
    assert e["status"].startswith("PARTIAL") and "PARTIAL" in p.name and e["n_reviewed"] == 5
    write_sheet(d / "reviewer_sheet.csv", done)
    p, e = va.run_evaluate(sheet=d / "reviewer_sheet.csv")
    assert e["status"] == "complete human review" and "PARTIAL" not in p.name
    (d / "sealed" / "auto_predictions.json").write_text("{}")
    with pytest.raises(SystemExit, match="sealed predictions changed"):
        va.run_evaluate(sheet=d / "reviewer_sheet.csv")


# ---------- end to end on the synthetic taxonomy ----------
def test_make_package_end_to_end(root, monkeypatch):
    run(root, Session())
    res = tv.build(root, RUN, "r1", expected=EXP)
    tv.write(res, root, RUN, "r1")
    vrun = "validity_v1_r1"
    plan = {c: 1 for c in Counter(r["validity_auto"] for r in res["rows"])}
    vdir = tv.tn.naming_dir(root, RUN) / vrun
    before = {f.name: va.sha(f.read_bytes()) for f in vdir.iterdir()}
    d, m, s = va.make(root, RUN, vrun, expected=EXP, plan=plan)
    assert {f.name: va.sha(f.read_bytes()) for f in vdir.iterdir()} == before          # validity outputs unchanged
    for f in ("blinded_evidence.md", "blinded_evidence.jsonl", "reviewer_sheet.csv", "REVIEW_INSTRUCTIONS.md",
              "manifest.json", "sealed/auto_predictions.json"):
        assert (d / f).is_file(), f
    reviewer_text = "".join((d / f).read_text() for f in ("blinded_evidence.md", "blinded_evidence.jsonl", "reviewer_sheet.csv"))
    assert "validity_auto" not in reviewer_text and "Topic T0" not in reviewer_text and "llm" not in reviewer_text.lower()
    sheet = list(csv.DictReader((d / "reviewer_sheet.csv").open()))
    assert all(not r["human_validity"] and not r["enter_hierarchy"] for r in sheet)     # never pre-filled
    tracked = (tv.tn.tracked_dir(root, RUN) / f"{va.AUDIT_NAME}_{vrun}" / "manifest.json").read_text()
    tm = json.loads(tracked)
    assert all(t not in json.dumps(tm["strata"]) for t in tm["topics_sorted"])       # no topic -> stratum mapping
    assert all(t not in json.dumps({k: v for k, v in tm.items() if k != "topics_sorted"}) for t in tm["topics_sorted"])
    assert m["sealed_predictions_sha256"] == va.sha((d / "sealed" / "auto_predictions.json").read_bytes())
    with pytest.raises(FileExistsError):
        va.make(root, RUN, vrun, expected=EXP, plan=plan)


def test_reference_text_marks_uncertainty_and_missing_scores():
    assert "can be wrong" in va.ref_text({"verdict": "known_skill", "source": "ESCO skill", "ref_label": "x", "match": "meaning", "score": "0.7"})
    assert "can be wrong" in va.ref_text({"verdict": "known_skill", "source": "ESCO skill", "ref_label": "x", "match": "exact", "score": ""})
    assert "human-reviewed" in va.ref_text({"verdict": "known_skill", "source": "ESCO skill", "ref_label": "x", "match": "review", "score": ""})
    assert "unreliable" in va.ref_text({"verdict": "new_candidate", "source": "ESCO skill", "ref_label": "y", "match": "meaning", "score": None})
    assert va.ref_text(None) == "no reference row"


# ---------- AI reviewer comparison ----------
def ai_rows(done, seen=()):
    return [dict(r, reviewer=va.AI_REVIEWER, notes="AI-generated by claude_ai_reviewer; NOT human-verified."
                 + (" seen label before" if r["topic_id"] in seen else "")) for r in done]


def test_exposure_union_keeps_both_records():
    sealed, done, _ = known_case()                                   # sealed flags: C00-C02 and S00-S05
    ids = [r["topic_id"] for r in done]
    e = va.exposure_records(ai_rows(done, seen={"C00", "M05"}), sealed, ids)
    assert e["original_sealed_flags"] == ["C00", "C01", "C02", "S00", "S01", "S02", "S03", "S04", "S05"]
    assert e["ai_reviewer_declared"] == ["C00", "M05"] and not e["identical"]
    assert e["only_in_original"] == ["C01", "C02", "S00", "S01", "S02", "S03", "S04", "S05"] and e["only_in_ai_declared"] == ["M05"]
    assert set(e["union_used"]) == set(e["original_sealed_flags"]) | {"M05"} and len(e["no_known_exposure"]) == 20


def test_compare_ai_labels_blind_subset_and_weights():
    sealed, done, N = known_case()
    ids = [r["topic_id"] for r in done]
    c = va.compare_ai(ai_rows(done, seen={"M05"}), sealed, N, ids)
    a, b = c["all_topics"], c["no_known_exposure"]
    assert c["label"] == a["label"] == b["label"] == va.AI_LABEL
    assert a["agreement_sample"] == round(22 / 30, 4) and a["agreement_population_weighted"] == round(300 / 370, 4)
    assert b["n_topics"] == 20 and b["agreement_population_weighted"] is None and "not applied" in b["weighting"]
    assert b["strata_present"] == {"coherent": 9, "mixed": 11}                       # no blind surface topics
    assert sorted(a["disagreement_auto_coherent_ai_not"]) == ["C10", "C11"] and len(a["disagreements"]) == 8
    assert {x["topic_id"] for x in a["hierarchy_eligibility_conflicts"]} == {"C10", "C11"}
    md = va.ai_md(c)
    assert md.count(va.AI_LABEL) >= 3 and "accuracy" not in md.replace("not accuracy", "") and "not confirmed errors" in md


def test_ai_sheet_must_be_ai_tagged(tmp_path):
    sealed, done, _ = known_case()
    ids = [r["topic_id"] for r in done]
    f = tmp_path / "ai.csv"
    write_sheet(f, done)                                                             # human-style rows
    assert va.read_ai_sheet(f, ids)[1]
    write_sheet(f, ai_rows(done))
    rows, probs = va.read_ai_sheet(f, ids)
    assert probs == [] and len(rows) == 30


def test_run_compare_ai_checks_hashes_and_never_overwrites(tmp_path, monkeypatch):
    sealed, done, N = known_case()
    ids = [r["topic_id"] for r in done]
    d = package(tmp_path, sealed, ids, N)
    m = json.loads((d / "manifest.json").read_text())
    write_sheet(d / "reviewer_sheet.csv", [{"topic_id": t} for t in ids])
    m["files_sha256"] = {"reviewer_sheet.csv": va.sha((d / "reviewer_sheet.csv").read_bytes())}
    (d / "manifest.json").write_text(json.dumps(m))
    write_sheet(d / "claude_review_sheet.csv", ai_rows(done))
    monkeypatch.setattr(va, "audit_dir", lambda *a: d)
    p, c = va.run_compare_ai()
    assert p.name.startswith("ai_comparison_claude_") and not list(d.glob("evaluation_*"))
    assert all(not r["human_validity"] for r in csv.DictReader((d / "reviewer_sheet.csv").open()))   # human sheet untouched
    (d / "reviewer_sheet.csv").write_text("changed")
    with pytest.raises(SystemExit, match="changed since it was made"):
        va.run_compare_ai()
