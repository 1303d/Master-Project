"""Intrusion test v2 on a synthetic taxonomy (tmp_path). No database, no real topics, no real responses.

    python -m pytest tests/intrusion_v2 -q
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import intrusion_v2 as iv  # noqa: E402

RUN = "synthetic_run"


def synthetic_snapshot(n_topics=60, dims=32, seed=0):
    rng = np.random.default_rng(seed)
    unit = lambda v: v / np.linalg.norm(v)
    domains = [unit(rng.normal(size=dims)) for _ in range(8)]
    topics, members, vectors = {}, [], {}
    for i in range(n_topics):
        t = f"S{i:04d}"
        topics[t] = {"label": f"label {i}", "transversal": i % 10 == 0}
        centre = unit(domains[i % 8] + 0.6 * rng.normal(size=dims) / np.sqrt(dims) * 4)
        for j in range(10 + (i * 7) % 31):
            k = f"skill {i}-{j}"
            v = unit(centre + 0.35 * rng.normal(size=dims) / np.sqrt(dims) * 4).astype(np.float32)
            vectors[k] = v
            members.append({"skill_key": k, "topic_id": t, "state": "assigned", "score": float(v @ centre), "margin": 0.1})
        members.append({"skill_key": f"weak {i}", "topic_id": t, "state": "weak", "score": 0.6, "margin": 0.01})
    return {"run_id": RUN, "vectors_sha256": "f" * 64, "topics": topics, "members": members, "vectors": vectors}


def expected(snap):
    return {"topics": len(snap["topics"]), "members": len(snap["members"])}


@pytest.fixture
def snap():
    return synthetic_snapshot()


@pytest.fixture
def made(tmp_path, snap):
    out, rep = iv.make(tmp_path, snap, seed=7, run_id=RUN, expected=expected(snap))
    return tmp_path, out, rep


def key_of(root):
    return json.loads(iv.key_path(root, RUN).read_text())["key"]


def fill(root, reviewer, answers):
    """Synthetic reviewer: write answers into the reviewer's own template."""
    path = iv.out_dir(root, RUN) / "responses" / f"{reviewer}.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for r in rows:
        r["answer"] = answers.get(r["question_id"], "")
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_question_integrity_and_one_intruder(made, snap):
    root, out, rep = made
    qs, key = iv.load_questions(root, RUN), key_of(root)
    assert len(qs) == 24 and rep["strata_drawn"] == dict(iv.STRATA)
    assert len({key[q["question_id"]]["topic_id"] for q in qs}) == 24  # 24 distinct topics
    topic_of = {m["skill_key"]: m["topic_id"] for m in snap["members"]}
    for q in qs:
        k, opts = key[q["question_id"]], q["options"]
        assert list(opts) == list("ABCDE") and len(set(opts.values())) == 5
        assert opts[k["answer"]] == k["intruder"]["skill_key"]
        genuine = [v for x, v in opts.items() if x != k["answer"]]
        assert sorted(genuine) == sorted(g["skill_key"] for g in k["genuine"])
        assert all(topic_of[g] == k["topic_id"] for g in genuine) and topic_of[opts[k["answer"]]] != k["topic_id"]
        assert k["intruder"]["max_cos_to_genuine"] < k["intruder"]["synonym_limit_used"]  # not a near-synonym
        assert not snap["topics"][k["intruder"]["topic_id"]]["transversal"]
    letters = [key[q]["answer"] for q in key]
    assert max(letters.count(x) for x in "ABCDE") - min(letters.count(x) for x in "ABCDE") <= 1  # balanced positions


def test_reproducible(snap):
    a = iv.build(snap, seed=7)
    assert a == iv.build(snap, seed=7)
    assert a[0] != iv.build(snap, seed=8)[0]


def test_excluded_topics_never_used(snap):
    excl = tuple(sorted(snap["topics"])[:12])
    _, key, rep = iv.build(snap, seed=7, exclude=excl)
    used = {k["topic_id"] for k in key.values()} | {k["intruder"]["topic_id"] for k in key.values()}
    assert not used & set(excl) and rep["excluded_topics"] == list(excl)


def test_blinding_and_key_separation(made):
    root, out, _ = made
    key = key_of(root)
    secrets = {k["topic_id"] for k in key.values()} | {k["topic_label"] for k in key.values()}
    reviewer_files = [out / "questions.json", out / "manifest.json", *(out / "responses").glob("*.csv")]
    for f in reviewer_files:
        text = f.read_text(encoding="utf-8")
        assert not any(s in text for s in secrets), f.name
        assert '"answer": "' not in text and "score" not in text.replace("score_", "")
    assert iv.out_dir(root, RUN) not in iv.key_path(root, RUN).parents
    assert iv.key_path(root, RUN).relative_to(root).parts[:2] == ("data", "interim")  # gitignored folder
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["answer_key"]["sha256"] == iv.sha256_bytes(iv.key_path(root, RUN).read_bytes())


def test_make_refuses_to_regenerate_and_checks_taxonomy(made, snap, tmp_path_factory):
    root, _, _ = made
    with pytest.raises(SystemExit, match="never regenerated"):
        iv.make(root, snap, seed=7, run_id=RUN, expected=expected(snap))
    with pytest.raises(SystemExit, match="does not match"):
        iv.make(tmp_path_factory.mktemp("x"), snap, seed=7, run_id=RUN, expected={"topics": 374, "members": 11093})


def test_validation_catches_bad_responses(made):
    root, out, _ = made
    path = out / "responses" / "lochan.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    rows[0]["answer"] = "F"
    rows[1]["A"] = "edited option"
    rows[2]["reviewer"] = "dhanush"
    rows.append(dict(rows[3], answer="A"))           # duplicate question
    rows.append(dict(rows[4], question_id="Q99"))     # unknown question
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    answers, problems, missing = iv.validate(root, RUN, "lochan")
    text = " | ".join(problems)
    for msg in ("not one of A-E", "were edited", "reviewer column", "answered twice", "unknown question"):
        assert msg in text
    assert len(missing) >= 20
    with pytest.raises(ValueError, match="not submitted"):
        iv.submit(root, RUN, "lochan")
    with pytest.raises(ValueError, match="unknown reviewer"):
        iv.validate(root, RUN, "mallory")


def test_submit_locks_and_scoring(made):
    root, out, _ = made
    key = key_of(root)
    qids = sorted(key)
    wrong = lambda a: "B" if a == "A" else "A"
    fill(root, "lochan", {q: key[q]["answer"] for q in qids})                                   # 24/24
    fill(root, "priyanka", {q: key[q]["answer"] if i % 2 == 0 else wrong(key[q]["answer"]) for i, q in enumerate(qids)})  # 12/24
    fill(root, "dhanush", {q: key[q]["answer"] if i % 4 else wrong(key[q]["answer"]) for i, q in enumerate(qids)})        # 18/24
    iv.submit(root, RUN, "lochan")
    with pytest.raises(ValueError, match="already submitted"):
        iv.submit(root, RUN, "lochan")
    with pytest.raises(ValueError, match="waiting for"):
        iv.score(root, RUN)
    partial = iv.score(root, RUN, allow_partial=True)
    assert partial["final"] is False and partial["correctness"]["per_reviewer"]["lochan"]["correct"] == 24
    iv.submit(root, RUN, "priyanka")
    iv.submit(root, RUN, "dhanush")
    assert iv.status(root, RUN) == {"lochan": True, "priyanka": True, "dhanush": True}
    res = iv.score(root, RUN)
    c, a = res["correctness"], res["agreement"]
    assert res["final"] and [c["per_reviewer"][r]["correct"] for r in ("lochan", "priyanka", "dhanush")] == [24, 12, 18]
    assert c["overall"]["correct"] == 54 and c["overall"]["n"] == 72
    # questions 0,4,8,... : all three right -> unanimous; others disputed (priyanka or dhanush wrong)
    assert a["unanimous"] == 6 and a["disputed"] == 18 and set(res["adjudication"]) == {r["question_id"] for r in res["questions"] if r["agreement"] == "disputed"}
    assert sum(v["n"] for v in c["by_stratum"].values()) == 72
    p = iv.write_score(root, RUN, res)
    assert p.is_file() and p.parent.name == "scores"


def test_tampering_detected(made):
    root, out, _ = made
    key = key_of(root)
    for r in iv.REVIEWERS:
        fill(root, r, {q: key[q]["answer"] for q in key})
        iv.submit(root, RUN, r)
    assert iv.score(root, RUN)["agreement"]["fleiss_kappa"] == pytest.approx(1.0)
    with (out / "responses" / "dhanush.csv").open("a", encoding="utf-8") as f:
        f.write("\n")
    with pytest.raises(ValueError, match="changed after submission"):
        iv.score(root, RUN)
    kp = iv.key_path(root, RUN)
    kp.write_text(kp.read_text().replace('"answer": "A"', '"answer": "B"', 1))
    with pytest.raises(ValueError, match="does not match the hash"):
        iv.score(root, RUN)


def test_wilson_and_kappa():
    lo, hi = iv.wilson(12, 24)
    assert lo < 0.5 < hi and iv.wilson(0, 0) == (0.0, 0.0)
    assert iv.fleiss_kappa([[3, 0, 0, 0, 0], [0, 3, 0, 0, 0]]) == pytest.approx(1.0)
