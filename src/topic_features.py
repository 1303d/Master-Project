"""Sprint 4 task 2: topic features from the frozen Sprint 4 input snapshot (offline, deterministic).

    python src/topic_features.py build     # verify the snapshot, compute features, write a new output folder
    python src/topic_features.py verify    # re-hash the outputs against their manifest

Input:  data/processed/sprint4_input_<run>/ (src/freeze_sprint4_input.py). Every file is checked against its
        manifest first; nothing is rebuilt from the database.
Output: data/processed/sprint4_features_<run>/ (gitignored) + tracked manifest copy in
        reports/sprint4_features/<run>/manifest.json. Never overwritten.

Method
  centroid      unweighted mean of the ASSIGNED members' unit vectors, then L2-normalised. Each skill counts once
                (no mention weighting: the snapshot has no mention counts, and weighting would let a few frequent
                generic skills pull the centre). Weak members are excluded: they are noise points attached to their
                nearest topic, so they are not evidence of what the topic is.
  cosine        member vector . centroid (both unit length)
  resultant     length of the mean vector before normalising (1 = all members identical; lower = more spread)
  dispersion    1 - mean cosine of assigned members to the centroid
  confidence    the Sprint 3 membership score (cosine to its centroid) and margin, as stored; missing stays missing
  reference     per topic, DISTINCT assigned skills with a confident link (verdict known_skill), split by ESCO /
                O*NET; link types from the `source` field. Reference purity needs broader groups, which the snapshot
                does not have, so it is reported as unavailable. `top_concept_share` = share of linked assigned skills
                that share the most common reference concept (same ref_id), a concentration measure, not purity.
  similarity    cosine between topic centroids, 374 x 374, rows/columns in topic_ids.csv order (sorted topic_id).
                Pairs at or above PAIR_FLAG are listed for HUMAN inspection; nothing is merged.
CSV floats are rounded to 6 decimals; arrays are float32. Same snapshot + same code -> identical file hashes.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import platform
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import freeze_sprint4_input as fz  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = fz.RUN_ID
SCHEMA_VERSION = "sprint4_features/1"
TOP_SKILLS, TOP_NEIGHBOURS, PAIR_FLAG = 10, 5, 0.90
NORM_TOL = 1e-5


def features_dir(root, run_id):
    return Path(root) / "data" / "processed" / f"sprint4_features_{run_id}"


def tracked_manifest(root, run_id):
    return Path(root) / "reports" / "sprint4_features" / run_id / "manifest.json"


def num(x):
    return "" if x is None else f"{x:.6f}"


def stats(values):
    """mean / median / min / max / quartiles of a list; None for an empty list (missing, not zero)."""
    if not values:
        return {k: None for k in ("mean", "median", "min", "max", "p25", "p75")}
    a = np.asarray(values, dtype=np.float64)
    return {"mean": float(a.mean()), "median": float(np.median(a)), "min": float(a.min()), "max": float(a.max()),
            "p25": float(np.percentile(a, 25)), "p75": float(np.percentile(a, 75))}


# ---------- input ----------
def load_snapshot(root=ROOT, run_id=RUN_ID, expected=fz.EXPECTED):
    """Verified snapshot or SystemExit. Never falls back to the database."""
    d = fz.snapshot_dir(root, run_id)
    if not (d / "manifest.json").is_file():
        raise SystemExit(f"snapshot missing: {d} (run src/freeze_sprint4_input.py export first)")
    try:
        problems = fz.verify(root, run_id, expected)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as e:
        raise SystemExit(f"snapshot unreadable: {e}") from None
    if problems:
        raise SystemExit("snapshot failed verification: " + "; ".join(problems))
    read = lambda f: list(csv.DictReader((d / f).open(encoding="utf-8", newline="")))
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    skills = read("skills.csv")
    return {"manifest": manifest, "topics": read("topics.csv"), "skills": skills,
            "row": {s["skill_key"]: int(s["vector_row"]) for s in skills},
            "vectors": np.load(d / "vectors.npy", allow_pickle=False),
            "memberships": read("memberships.csv"), "links": read("reference_links.csv")}


# ---------- features ----------
def compute(snap):
    topics = sorted(snap["topics"], key=lambda t: t["topic_id"])
    tids = [t["topic_id"] for t in topics]
    V, row = snap["vectors"].astype(np.float64), snap["row"]
    by = {t: {"assigned": [], "weak": []} for t in tids}
    for m in snap["memberships"]:
        if m["topic_id"] not in by:
            raise ValueError(f"membership of {m['skill_key']} points to unknown topic {m['topic_id']}")
        if m["state"] not in ("assigned", "weak"):
            raise ValueError(f"unknown membership state {m['state']!r}")
        by[m["topic_id"]][m["state"]].append(m)
    empty = [t for t in tids if not by[t]["assigned"]]
    if empty:
        raise ValueError(f"topics without assigned members (no centroid can be made): {', '.join(empty)}")
    links = {l["skill_key"]: l for l in snap["links"]}

    C = np.zeros((len(tids), V.shape[1]))
    feats, reps, refs = [], [], []
    for i, t in enumerate(tids):
        a = sorted(by[t]["assigned"], key=lambda m: m["skill_key"])
        w = by[t]["weak"]
        M = V[[row[m["skill_key"]] for m in a]]
        mean = M.mean(axis=0)
        resultant = float(np.linalg.norm(mean))
        if resultant < 1e-9:
            raise ValueError(f"{t}: centroid has zero length")
        c = mean / resultant
        C[i] = c
        cos = M @ c
        order = sorted(range(len(a)), key=lambda j: (-round(float(cos[j]), 12), a[j]["skill_key"]))
        for rank, j in enumerate(order[:TOP_SKILLS], 1):
            reps.append({"topic_id": t, "rank": rank, "skill_key": a[j]["skill_key"], "vector_row": row[a[j]["skill_key"]],
                         "cosine": float(cos[j])})
        score = lambda ms, k: [float(m[k]) for m in ms if m.get(k) not in (None, "")]
        s_a, s_w, mg_a, cs = stats(score(a, "score")), stats(score(w, "score")), stats(score(a, "margin")), stats(list(map(float, cos)))
        topic = next(x for x in topics if x["topic_id"] == t)
        feats.append({"topic_id": t, "label": topic["label"], "label_reviewed": bool(topic["label_reviewed_by"]),
                      "is_transversal": topic["is_transversal"] == "true", "n_assigned": len(a), "n_weak": len(w),
                      "n_total": len(a) + len(w), "score_mean": s_a["mean"], "score_median": s_a["median"],
                      "score_p25": s_a["p25"], "score_p75": s_a["p75"], "margin_median": mg_a["median"],
                      "weak_score_mean": s_w["mean"], "cos_mean": cs["mean"], "cos_min": cs["min"], "cos_max": cs["max"],
                      "resultant": resultant, "dispersion": 1 - cs["mean"],
                      "n_missing_score": sum(m.get("score") in (None, "") for m in a + w)})
        conf = [links[m["skill_key"]] for m in a if m["skill_key"] in links and links[m["skill_key"]]["verdict"] == "known_skill"]
        esco = {l["skill_key"] for l in conf if l["source"].startswith("ESCO")}
        onet = {l["skill_key"] for l in conf if l["source"].startswith("O*NET")}
        traits = {m["skill_key"] for m in a if links.get(m["skill_key"], {}).get("verdict") == "trait"}
        concepts = Counter(l["ref_id"] for l in conf if l["ref_id"])
        types = Counter(l["source"] for l in conf)
        refs.append({"topic_id": t, "n_assigned": len(a), "n_no_link_row": sum(m["skill_key"] not in links for m in a),
                     "n_esco_confident": len(esco), "n_onet_confident": len(onet),
                     "n_confident": len({l["skill_key"] for l in conf}), "n_trait": len(traits),
                     "coverage_esco": len(esco) / len(a), "coverage_onet": len(onet) / len(a),
                     "coverage_any": len({l["skill_key"] for l in conf}) / len(a),
                     "top_concept_share": (concepts.most_common(1)[0][1] / len(conf)) if conf else None,
                     "link_types": ";".join(f"{k}={v}" for k, v in sorted(types.items())),
                     "purity": None, "purity_status": "unavailable: snapshot has no ESCO/O*NET broader-group data"})
    C = C.astype(np.float32)
    S = C.astype(np.float64) @ C.astype(np.float64).T
    S = ((S + S.T) / 2).astype(np.float32)
    neighbours, pairs = [], []
    for i, t in enumerate(tids):
        order = sorted((j for j in range(len(tids)) if j != i), key=lambda j: (-round(float(S[i, j]), 6), tids[j]))
        for rank, j in enumerate(order[:TOP_NEIGHBOURS], 1):
            mutual = i in sorted((k for k in range(len(tids)) if k != j), key=lambda k: (-round(float(S[j, k]), 6), tids[k]))[:1]
            neighbours.append({"topic_id": t, "rank": rank, "neighbour_id": tids[j], "cosine": float(S[i, j]),
                               "mutual_nearest": rank == 1 and mutual, "flag_for_review": float(S[i, j]) >= PAIR_FLAG})
        for j in range(i + 1, len(tids)):
            if S[i, j] >= PAIR_FLAG:
                pairs.append({"topic_a": t, "topic_b": tids[j], "cosine": float(S[i, j]),
                              "transversal_involved": feats[i]["is_transversal"] or feats[j]["is_transversal"]})
    pairs.sort(key=lambda p: (-round(p["cosine"], 6), p["topic_a"], p["topic_b"]))
    return {"topic_ids": tids, "centroids": C, "similarity": S, "features": feats, "representatives": reps,
            "references": refs, "neighbours": neighbours, "pairs": pairs}


def check(out):
    C, S, n = out["centroids"], out["similarity"], len(out["topic_ids"])
    p = []
    if len(set(out["topic_ids"])) != n or out["topic_ids"] != sorted(out["topic_ids"]):
        p.append("topic IDs not unique and sorted")
    if C.shape[0] != n or not np.isfinite(C).all():
        p.append("centroids: wrong count or non-finite values")
    if np.abs(np.linalg.norm(C, axis=1) - 1).max() > NORM_TOL:
        p.append("centroids are not unit length")
    if S.shape != (n, n) or not np.isfinite(S).all() or not np.array_equal(S, S.T):
        p.append("similarity matrix not square, finite and symmetric")
    if np.abs(np.diag(S) - 1).max() > 1e-4:
        p.append("similarity diagonal is not ~1")
    return p


# ---------- files ----------
def csv_bytes(rows, cols):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow([num(r[c]) if isinstance(r[c], float) else ("true" if r[c] is True else "false" if r[c] is False
                    else "" if r[c] is None else r[c]) for c in cols])
    return buf.getvalue().encode("utf-8")


def npy_bytes(a):
    buf = io.BytesIO()
    np.save(buf, a, allow_pickle=False)
    return buf.getvalue()


def serialize(out):
    cols = lambda rows: list(rows[0]) if rows else []
    files = {"topic_ids.csv": csv_bytes([{"row": i, "topic_id": t} for i, t in enumerate(out["topic_ids"])], ["row", "topic_id"]),
             "topic_centroids.npy": npy_bytes(out["centroids"]), "topic_similarity.npy": npy_bytes(out["similarity"]),
             "topic_features.csv": csv_bytes(out["features"], cols(out["features"])),
             "representative_skills.csv": csv_bytes(out["representatives"], cols(out["representatives"])),
             "reference_summary.csv": csv_bytes(out["references"], cols(out["references"])),
             "topic_neighbors.csv": csv_bytes(out["neighbours"], cols(out["neighbours"])),
             "similar_topic_pairs.csv": csv_bytes(out["pairs"], ["topic_a", "topic_b", "cosine", "transversal_involved"])}
    return dict(sorted(files.items()))


def code_version(root):
    import subprocess
    try:
        run = lambda *a: subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout
        commit = run("rev-parse", "HEAD").strip() + ("+uncommitted" if run("status", "--porcelain").strip() else "")
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {"commit": commit, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "numpy": np.__version__, "python": platform.python_version(), "platform": platform.machine()}


def build(root=ROOT, run_id=RUN_ID, snap=None, expected=fz.EXPECTED):
    out_dir, mcopy = features_dir(root, run_id), tracked_manifest(root, run_id)
    if out_dir.exists() or mcopy.exists():
        raise FileExistsError(f"{out_dir.name} already exists; never overwritten")
    snap = snap or load_snapshot(root, run_id, expected)
    out = compute(snap)
    problems = check(out)
    if problems:
        raise ValueError("feature checks failed: " + "; ".join(problems))
    files = serialize(out)
    if files != serialize(compute(snap)):
        raise ValueError("feature generation is not deterministic")
    hashes = {f: hashlib.sha256(b).hexdigest() for f, b in files.items()}
    f = out["features"]
    manifest = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "input_snapshot": {"dir": fz.snapshot_dir(root, run_id).relative_to(root).as_posix(),
                                   "data_fingerprint": snap["manifest"]["data_fingerprint"]},
                "code": code_version(root),
                "settings": {"top_skills": TOP_SKILLS, "top_neighbours": TOP_NEIGHBOURS, "pair_flag_cosine": PAIR_FLAG,
                             "centroid": "unweighted mean of assigned members' unit vectors, L2-normalised; weak excluded",
                             "confident_link": "reference_links.verdict == known_skill; ESCO/O*NET from source prefix",
                             "purity": "unavailable (no broader-group data in the snapshot)", "csv_float_decimals": 6},
                "counts": {"topics": len(out["topic_ids"]), "transversal": sum(x["is_transversal"] for x in f),
                           "assigned": sum(x["n_assigned"] for x in f), "weak": sum(x["n_weak"] for x in f),
                           "representatives": len(out["representatives"]), "neighbour_rows": len(out["neighbours"]),
                           "flagged_pairs": len(out["pairs"])},
                "shapes": {"topic_centroids.npy": list(out["centroids"].shape), "topic_similarity.npy": list(out["similarity"].shape)},
                "ordering": {"topic_ids.csv / arrays": "sorted topic_id", "representative_skills.csv": "topic_id, rank (cosine desc, skill_key)",
                             "topic_neighbors.csv": "topic_id, rank (cosine desc, topic_id)", "similar_topic_pairs.csv": "cosine desc, topic ids"},
                "files_sha256": hashes,
                "data_fingerprint": hashlib.sha256("\n".join(f"{k}:{v}" for k, v in sorted(hashes.items())).encode()).hexdigest()}
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
    for name, b in files.items():
        (tmp / name).write_bytes(b)
    text = json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    (tmp / "manifest.json").write_text(text, encoding="utf-8")
    os.rename(tmp, out_dir)
    mcopy.parent.mkdir(parents=True, exist_ok=True)
    with mcopy.open("x", encoding="utf-8") as fh:
        fh.write(text)
    return out_dir, manifest, out


def verify(root=ROOT, run_id=RUN_ID):
    d = features_dir(root, run_id)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    p = [f"{f}: hash differs" for f, h in m["files_sha256"].items()
         if not (d / f).is_file() or hashlib.sha256((d / f).read_bytes()).hexdigest() != h]
    tm = tracked_manifest(root, run_id)
    if not tm.is_file() or tm.read_text(encoding="utf-8") != (d / "manifest.json").read_text(encoding="utf-8"):
        p.append("tracked manifest copy missing or different")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "verify"])
    args = ap.parse_args()
    try:
        if args.cmd == "build":
            d, m, _ = build()
            print(f"features -> {d.relative_to(ROOT)} | counts {json.dumps(m['counts'])} | fingerprint {m['data_fingerprint'][:16]}")
        else:
            problems = verify()
            print("OK: all output hashes match" if not problems else "PROBLEMS:\n  " + "\n  ".join(problems))
            sys.exit(1 if problems else 0)
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
