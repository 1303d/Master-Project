"""Sprint 4 task 2 (topic features) on a hand-made 4-D taxonomy with known answers. No database.

    python -m pytest tests/sprint4 -q
"""
import copy
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import freeze_sprint4_input as fz  # noqa: E402
import topic_features as tf  # noqa: E402

RUN = "synthetic_run"
R = 1 / np.sqrt(2)


def vec(*xs):
    v = np.asarray(xs, dtype=float)
    return v / np.linalg.norm(v)


def raw():
    members = [  # (skill, topic, state, vector)
        ("a", "T0000", "assigned", vec(1, 0, 0, 0)), ("b", "T0000", "assigned", vec(0, 1, 0, 0)),
        ("w1", "T0000", "weak", vec(0, 0, 1, 0)),
        ("c", "T0001", "assigned", vec(0, 0, 1, 0)), ("d", "T0001", "assigned", vec(0, 0, 0.6, 0.8)),
        ("w2", "T0001", "weak", vec(1, 0, 0, 0)),
    ] + [(f"z{i:02d}", "T0002", "assigned", vec(0.05 * i, 0, 0.1, 1)) for i in range(12)]
    topics = [{"topic_id": t, "cluster_id": i, "event": "new", "jaccard": None, "level": "topic", "label": f"label {t}",
               "parent_topic_id": None, "status": "active", "is_transversal": t == "T0000", "split_from": None,
               "merged_into": None, "first_run": RUN, "last_run": RUN, "label_reviewed_by": None}
              for i, t in enumerate(["T0000", "T0001", "T0002"])]
    link = lambda k, verdict, source, ref: {"skill_key": k, "verdict": verdict, "source": source, "ref_label": k, "ref_id": ref,
                                            "score": 0.9, "match": "meaning", "review_status": "auto",
                                            "updated_at": datetime(2026, 10, 21, tzinfo=timezone.utc)}
    links = [link("a", "known_skill", "ESCO skill", "esco:1"), link("b", "new_candidate", "ESCO skill", "esco:2"),
             link("c", "known_skill", "O*NET software", "2.E.1"), link("d", "trait", "ESCO attitude", "esco:t"),
             link("z00", "known_skill", "ESCO knowledge", "esco:9"), link("z01", "known_skill", "ESCO knowledge", "esco:9"),
             link("z02", "known_skill", "O*NET software", "2.E.2")]
    return {"run": {"run_id": RUN, "method": "hdbscan", "params": {}, "vectors_sha256": "f" * 64, "metrics": {},
                    "is_active": True, "created_at": datetime(2026, 10, 23, tzinfo=timezone.utc)},
            "topics": topics,
            "memberships": [{"skill_key": k, "topic_id": t, "role": "primary", "state": s, "score": 0.8, "margin": 0.1}
                            for k, t, s, _ in members],
            "embeddings": [{"skill_key": k, "model_id": "m", "revision": "r", "embedding": "[" + ",".join(repr(float(x)) for x in v) + "]"}
                           for k, _, _, v in members],
            "aliases": [], "reference_links": links, "library": [], "library_links": []}


EXP = {"topics": 3, "skills": 18, "assigned": 16, "weak": 2, "embeddings": 18, "dims": 4}


@pytest.fixture
def root(tmp_path):
    fz.export(raw(), tmp_path, "c0ffee", expected=EXP)
    return tmp_path


def features(root):
    return tf.compute(tf.load_snapshot(root, RUN, EXP))


def by_topic(rows):
    return {r["topic_id"]: r for r in rows}


def test_snapshot_hash_verified_before_use(root):
    snap = fz.snapshot_dir(root, RUN)
    (snap / "memberships.csv").write_bytes((snap / "memberships.csv").read_bytes().replace(b"0.8", b"0.7", 1))
    with pytest.raises(SystemExit, match="failed verification"):
        tf.load_snapshot(root, RUN, EXP)


def test_missing_snapshot_stops(tmp_path):
    with pytest.raises(SystemExit, match="snapshot missing"):
        tf.load_snapshot(tmp_path, RUN, EXP)


def test_centroid_assigned_only_and_unit_length(root):
    out = features(root)
    C = dict(zip(out["topic_ids"], out["centroids"]))
    assert np.allclose(C["T0000"], [R, R, 0, 0], atol=1e-6)            # weak w1 (0,0,1,0) excluded
    assert np.allclose(C["T0001"], vec(0, 0, 1.6, 0.8), atol=1e-6)    # weak w2 (1,0,0,0) excluded
    assert np.allclose(np.linalg.norm(out["centroids"], axis=1), 1, atol=1e-6)
    f = by_topic(out["features"])
    assert (f["T0000"]["n_assigned"], f["T0000"]["n_weak"], f["T0000"]["n_total"]) == (2, 1, 3)
    assert f["T0000"]["resultant"] == pytest.approx(R) and f["T0000"]["is_transversal"] is True
    assert f["T0000"]["cos_mean"] == pytest.approx(R) and f["T0000"]["dispersion"] == pytest.approx(1 - R)


def test_representatives_ranked_and_capped(root):
    reps = [r for r in features(root)["representatives"] if r["topic_id"] == "T0002"]
    assert len(reps) == tf.TOP_SKILLS and [r["rank"] for r in reps] == list(range(1, 11))
    assert all(reps[i]["cosine"] >= reps[i + 1]["cosine"] for i in range(9))
    t0 = [r for r in features(root)["representatives"] if r["topic_id"] == "T0000"]
    assert [r["skill_key"] for r in t0] == ["a", "b"]  # tie on cosine -> skill_key order; fewer than 10 -> all


def test_missing_confidence_is_not_zero(root):
    snap = tf.load_snapshot(root, RUN, EXP)
    snap["memberships"] = copy.deepcopy(snap["memberships"])
    for m in snap["memberships"]:
        if m["topic_id"] == "T0001":
            m["score"], m["margin"] = "", ""
    f = by_topic(tf.compute(snap)["features"])
    assert f["T0001"]["score_mean"] is None and f["T0001"]["n_missing_score"] == 3
    assert f["T0000"]["score_mean"] == pytest.approx(0.8)
    row = tf.csv_bytes([f["T0001"]], ["topic_id", "score_mean"]).decode().splitlines()[1]
    assert row == "T0001,"  # empty cell, not 0.000000


def test_reference_coverage_counts_distinct_assigned_skills(root):
    r = by_topic(features(root)["references"])
    assert (r["T0000"]["n_esco_confident"], r["T0000"]["n_confident"], r["T0000"]["coverage_any"]) == (1, 1, 0.5)  # b is only a candidate
    assert (r["T0001"]["n_onet_confident"], r["T0001"]["n_trait"], r["T0001"]["coverage_any"]) == (1, 1, 0.5)     # weak w2 not counted
    assert (r["T0002"]["n_esco_confident"], r["T0002"]["n_onet_confident"], r["T0002"]["n_no_link_row"]) == (2, 1, 9)
    assert r["T0002"]["top_concept_share"] == pytest.approx(2 / 3)  # two skills share esco:9
    assert r["T0002"]["link_types"] == "ESCO knowledge=2;O*NET software=1"
    assert all(x["purity"] is None and x["purity_status"].startswith("unavailable") for x in r.values())


def test_similarity_symmetric_diagonal_and_neighbours(root):
    out = features(root)
    S = out["similarity"]
    assert S.shape == (3, 3) and np.array_equal(S, S.T) and np.allclose(np.diag(S), 1, atol=1e-6)
    assert tf.check(out) == []
    n = [x for x in out["neighbours"] if x["topic_id"] == "T0000"]
    assert len(n) == 2 and n[0]["cosine"] >= n[1]["cosine"] and all(x["neighbour_id"] != "T0000" for x in n)


def test_stable_ordering_and_determinism(root):
    snap = tf.load_snapshot(root, RUN, EXP)
    a = tf.serialize(tf.compute(snap))
    shuffled = dict(snap, topics=random.Random(1).sample(snap["topics"], 3),
                    memberships=random.Random(2).sample(snap["memberships"], len(snap["memberships"])))
    assert tf.serialize(tf.compute(shuffled)) == a
    assert features(root)["topic_ids"] == ["T0000", "T0001", "T0002"]


def test_malformed_inputs_rejected(root):
    snap = tf.load_snapshot(root, RUN, EXP)
    bad = dict(snap, memberships=snap["memberships"] + [{"skill_key": "a", "topic_id": "T9999", "role": "primary",
                                                          "state": "assigned", "score": "0.5", "margin": "0.1"}])
    with pytest.raises(ValueError, match="unknown topic"):
        tf.compute(bad)
    no_assigned = dict(snap, memberships=[m for m in snap["memberships"] if not (m["topic_id"] == "T0001" and m["state"] == "assigned")])
    with pytest.raises(ValueError, match="without assigned members"):
        tf.compute(no_assigned)


def test_build_manifest_verify_and_no_overwrite(root):
    d, m, _ = tf.build(root, RUN, expected=EXP)
    assert m["input_snapshot"]["data_fingerprint"] == fz.json.loads((fz.snapshot_dir(root, RUN) / "manifest.json").read_text())["data_fingerprint"]
    assert m["shapes"]["topic_similarity.npy"] == [3, 3] and m["counts"]["weak"] == 2
    assert tf.verify(root, RUN) == []
    with pytest.raises(FileExistsError):
        tf.build(root, RUN, expected=EXP)
    (d / "topic_features.csv").write_bytes(b"tampered")
    assert any("topic_features.csv" in p for p in tf.verify(root, RUN))


def test_builds_are_byte_identical(tmp_path):
    hashes = []
    for name in ("one", "two"):
        r = tmp_path / name
        fz.export(raw(), r, "c", expected=EXP)
        hashes.append(tf.build(r, RUN, expected=EXP)[1]["files_sha256"])
    assert hashes[0] == hashes[1]
