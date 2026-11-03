"""Sprint 4 input snapshot: synthetic records only (no database).

    python -m pytest tests/sprint4 -q
"""
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import freeze_sprint4_input as fz  # noqa: E402

RUN = "synthetic_run"


def raw_records(n_topics=4, per=3, dims=8, seed=0):
    rng = np.random.default_rng(seed)
    topics, mem, emb, links = [], [], [], []
    for i in range(n_topics):
        t = f"T{i:04d}"
        topics.append({"topic_id": t, "cluster_id": i, "event": "new", "jaccard": None, "level": "topic", "label": f"l{i}",
                       "parent_topic_id": None, "status": "active", "is_transversal": i == 0, "split_from": None,
                       "merged_into": None, "first_run": RUN, "last_run": RUN, "label_reviewed_by": None})
        for j in range(per + 1):
            k = f"skill {i}-{j}"
            v = rng.normal(size=dims)
            v /= np.linalg.norm(v)
            mem.append({"skill_key": k, "topic_id": t, "role": "primary", "state": "weak" if j == per else "assigned",
                        "score": float(0.9 - j / 100), "margin": 0.05})
            emb.append({"skill_key": k, "model_id": "BAAI/bge-small-en-v1.5", "revision": "abc",
                        "embedding": "[" + ",".join(f"{x:.7g}" for x in v) + "]"})
            links.append({"skill_key": k, "verdict": "known_skill", "source": "ESCO skill", "ref_label": k,
                          "ref_id": f"http://esco/{i}/{j}", "score": 0.91, "match": "embed", "review_status": "auto",
                          "updated_at": datetime(2026, 10, 21, tzinfo=timezone.utc)})
    keys = [m["skill_key"] for m in mem]
    return {"run": {"run_id": RUN, "method": "hdbscan", "params": {"param": 10}, "vectors_sha256": "f" * 64,
                    "metrics": {"n_clusters": n_topics}, "is_active": True, "created_at": datetime(2026, 10, 23, tzinfo=timezone.utc)},
            "topics": topics, "memberships": mem, "embeddings": emb,
            "aliases": [{"alias_key": k + "s", "skill_key": k, "rule": "R1", "reviewed_by": None, "created_at": None} for k in keys],
            "reference_links": links,
            "library": [{"skill_key": keys[0], "status": "confirmed", "n_postings": 12, "n_templates": 11, "n_unknown": 0,
                         "n_sectors": 5, "top_share": 0.3, "entropy": 0.8, "skill_type": "skill", "reuse_level": None,
                         "rule_version": "library-v2", "run_id": RUN}],
            "library_links": [{"skill_key": keys[0], "topic_id": "T0001", "n_postings": 6, "n_templates": 6, "lift": 2.0,
                               "p_value": 0.01, "q_value": 0.04, "strength": "strong"}]}


def exp(raw):
    return {"topics": len(raw["topics"]), "skills": len(raw["memberships"]),
            "assigned": sum(m["state"] == "assigned" for m in raw["memberships"]),
            "weak": sum(m["state"] == "weak" for m in raw["memberships"]), "embeddings": len(raw["embeddings"]), "dims": 8}


def shuffled(raw, seed):
    r = json.loads(json.dumps(raw, default=str))
    r["run"]["created_at"] = raw["run"]["created_at"]
    for k in ("topics", "memberships", "embeddings", "aliases", "reference_links"):
        random.Random(seed).shuffle(r[k])
    for row in r["reference_links"]:  # restore datetime objects lost by the JSON copy
        row["updated_at"] = datetime.fromisoformat(row["updated_at"])
    return r


def test_valid_snapshot_has_no_problems():
    raw = raw_records()
    problems, counts = fz.check(raw, exp(raw))
    assert problems == [] and counts["transversal"] == 1 and counts["dims"] == 8


def test_serialization_is_deterministic_and_order_independent():
    raw = raw_records()
    a = fz.serialize(raw)
    assert a == fz.serialize(raw)
    assert a == fz.serialize(shuffled(raw, 1)) == fz.serialize(shuffled(raw, 2))
    V = np.load(__import__("io").BytesIO(a["vectors.npy"]))
    keys = [line.split(",")[1] for line in a["skills.csv"].decode().splitlines()[1:]]
    assert keys == sorted(keys) and V.shape == (16, 8) and V.dtype == np.float32


@pytest.mark.parametrize("breaker, msg", [
    (lambda r: r["memberships"].append(dict(r["memberships"][0])), "more than one membership"),
    (lambda r: r["memberships"].__setitem__(0, {**r["memberships"][0], "topic_id": "T9999"}), "unknown topics"),
    (lambda r: r["embeddings"].pop(), "no embedding"),
    (lambda r: r["embeddings"].append(dict(r["embeddings"][0])), "duplicate embeddings"),
    (lambda r: r["embeddings"].__setitem__(0, {**r["embeddings"][0], "embedding": "[" + ",".join(["NaN"] * 8) + "]"}), "NaN"),
    (lambda r: r["embeddings"].__setitem__(0, {**r["embeddings"][0], "embedding": "[" + ",".join(["0.5"] * 8) + "]"}), "unit length"),
    (lambda r: r["embeddings"].__setitem__(0, {**r["embeddings"][0], "revision": "other"}), "model versions"),
    (lambda r: r["topics"].append(dict(r["topics"][0])), "duplicate topic"),
    (lambda r: r["reference_links"].append({**r["reference_links"][0], "skill_key": "ghost"}), "outside the snapshot"),
])
def test_integrity_problems_detected(breaker, msg):
    raw = raw_records()
    e = exp(raw)
    breaker(raw)
    problems, _ = fz.check(raw, e)
    assert any(msg in p for p in problems), problems


def test_wrong_counts_are_reported():
    raw = raw_records()
    problems, _ = fz.check(raw, {**exp(raw), "topics": 374})
    assert any("topics: 4 != expected 374" in p for p in problems)


def test_export_verify_and_refuse_overwrite(tmp_path):
    raw = raw_records()
    out, m = fz.export(raw, tmp_path, "c0ffee", again=shuffled(raw, 3), expected=exp(raw))
    assert out == fz.snapshot_dir(tmp_path, RUN) and m["source_commit"] == "c0ffee"
    assert set(m["files_sha256"]) == {"run.json", "topics.csv", "skills.csv", "memberships.csv", "vectors.npy",
                                      "aliases.csv", "reference_links.csv", "library.csv", "library_links.csv"}
    assert all(fz.sha256((out / f).read_bytes()) == h for f, h in m["files_sha256"].items())
    assert fz.tracked_manifest(tmp_path, RUN).read_text() == (out / "manifest.json").read_text()
    assert m["rows"]["memberships.csv"] == 16 and m["embedding_model"]["revision"] == "abc"
    assert fz.verify(tmp_path, RUN, exp(raw)) == []
    assert fz.verify(tmp_path, RUN, exp(raw), fresh_raw=raw) == []
    with pytest.raises(FileExistsError):
        fz.export(raw, tmp_path, "c0ffee", expected=exp(raw))
    changed = raw_records()
    changed["memberships"][1]["score"] = 0.5
    assert "drift" in " ".join(fz.verify(tmp_path, RUN, exp(raw), fresh_raw=changed))
    (out / "topics.csv").write_bytes((out / "topics.csv").read_bytes() + b"x")
    assert any("topics.csv: hash differs" in p for p in fz.verify(tmp_path, RUN, exp(raw)))


def test_timestamp_does_not_change_data_hashes(tmp_path):
    raw = raw_records()
    _, m1 = fz.export(raw, tmp_path / "a", "c", expected=exp(raw))
    _, m2 = fz.export(raw, tmp_path / "b", "c", expected=exp(raw))
    assert m1["files_sha256"] == m2["files_sha256"] and m1["data_fingerprint"] == m2["data_fingerprint"]


def test_export_refuses_bad_data_and_changing_database(tmp_path):
    raw = raw_records()
    bad = raw_records()
    bad["embeddings"].pop()
    with pytest.raises(ValueError, match="checks failed"):
        fz.export(bad, tmp_path, "c", expected=exp(raw))
    moved = raw_records()
    moved["memberships"][0]["margin"] = 0.2
    with pytest.raises(ValueError, match="two reads"):
        fz.export(raw, tmp_path, "c", again=moved, expected=exp(raw))
    assert not fz.snapshot_dir(tmp_path, RUN).exists()  # nothing half-written
