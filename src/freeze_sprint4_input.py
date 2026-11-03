"""Freeze the active Sprint 3 taxonomy as an immutable local snapshot for Sprint 4 (read-only export).

    python src/freeze_sprint4_input.py export [--env PATH/.env]          # Supabase (read-only) -> snapshot
    python src/freeze_sprint4_input.py verify [--db --env PATH/.env]     # re-hash files; --db: compare with Supabase

Output: data/processed/sprint4_input_<run_id>/ (gitignored: vectors are 17 MB) with run.json, topics.csv,
skills.csv, memberships.csv, vectors.npy, aliases.csv, reference_links.csv, library.csv, library_links.csv and
manifest.json. A copy of the manifest goes to reports/sprint4_input/<run_id>/manifest.json (tracked), so anyone can
check a snapshot they received. Nothing is ever overwritten; Supabase is only read, inside a transaction the
server confirms as READ ONLY.

Determinism: rows are sorted by their key columns (Python string order), floats are written with repr(), CSVs use
"\\n" line ends, JSON uses sorted keys, and vectors.npy rows follow skills.csv (vector_row = sorted skill_key order).
The snapshot time lives only in the manifest, so unchanged data always gives identical file hashes.

Note: load_embeddings.py stored the vectors as text with 7 significant digits, so vectors.npy here is the database
copy (float32), not byte-identical to the original file; the original file hash is kept as `source_vectors_sha256`.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "hdbscan_10_umap10_ms1_2026-10-23"
EXPECTED = {"topics": 374, "skills": 11093, "assigned": 8646, "weak": 2447, "embeddings": 11093, "dims": 384}
SCHEMA_VERSION = "sprint4_input/1"
NORM_TOL = 1e-5

COLUMNS = {
    "topics.csv": ["topic_id", "cluster_id", "event", "jaccard", "level", "label", "parent_topic_id", "status",
                   "is_transversal", "split_from", "merged_into", "first_run", "last_run", "label_reviewed_by"],
    "skills.csv": ["vector_row", "skill_key"],
    "memberships.csv": ["skill_key", "topic_id", "role", "state", "score", "margin"],
    "aliases.csv": ["alias_key", "skill_key", "rule", "reviewed_by", "created_at"],
    "reference_links.csv": ["skill_key", "verdict", "source", "ref_label", "ref_id", "score", "match", "review_status",
                            "updated_at"],
    "library.csv": ["skill_key", "status", "n_postings", "n_templates", "n_unknown", "n_sectors", "top_share", "entropy",
                    "skill_type", "reuse_level", "rule_version", "run_id"],
    "library_links.csv": ["skill_key", "topic_id", "n_postings", "n_templates", "lift", "p_value", "q_value", "strength"],
}
SORT = {"topics.csv": ["topic_id"], "skills.csv": ["skill_key"], "memberships.csv": ["skill_key", "topic_id"],
        "aliases.csv": ["alias_key"], "reference_links.csv": ["skill_key"], "library.csv": ["skill_key"],
        "library_links.csv": ["skill_key", "topic_id"]}


def snapshot_dir(root, run_id):
    return Path(root) / "data" / "processed" / f"sprint4_input_{run_id}"


def tracked_manifest(root, run_id):
    return Path(root) / "reports" / "sprint4_input" / run_id / "manifest.json"


def sha256(b):
    return hashlib.sha256(b).hexdigest()


# ---------- read-only fetch ----------
def connect(env):
    import psycopg
    from dotenv import dotenv_values
    url = os.getenv("SUPABASE_DB_URL") or dotenv_values(env).get("SUPABASE_DB_URL")
    if not url:
        sys.exit(f"SUPABASE_DB_URL not found (environment or {env})")
    return psycopg.connect(url, connect_timeout=20, autocommit=False)


def fetch(con, run_id=RUN_ID):
    """Everything the snapshot needs, read in one transaction the server confirms as READ ONLY."""
    cur = con.cursor()
    cur.execute("set transaction read only")
    cur.execute("show transaction_read_only")
    if cur.fetchone()[0] != "on":
        raise RuntimeError("the database did not confirm a read-only transaction")

    def rows(sql, *args):
        cur.execute(sql, args)
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    active = rows("select * from cluster_runs where is_active")
    if len(active) != 1 or active[0]["run_id"] != run_id:
        raise RuntimeError(f"active run is {[a['run_id'] for a in active]}, expected {run_id}")
    run = active[0]
    raw = {
        "run": run,
        "topics": rows("""select t.*, rc.cluster_id, rc.event, rc.jaccard from run_clusters rc
                          join topics t using (topic_id) where rc.run_id = %s""", run_id),
        "memberships": rows("select skill_key, topic_id, role, state, score, margin from skill_topics where run_id = %s", run_id),
        "embeddings": rows("""select skill_key, model_id, revision, embedding::text as embedding from skill_embeddings
                              where vectors_sha256 = %s""", run["vectors_sha256"]),
        "aliases": rows("""select alias_key, skill_key, rule, reviewed_by, created_at from skill_aliases a
                           where exists (select 1 from skill_topics s where s.run_id = %s and s.skill_key = a.skill_key)""", run_id),
        "reference_links": rows("""select l.* from skill_links l where exists
                                   (select 1 from skill_topics s where s.run_id = %s and s.skill_key = l.skill_key)""", run_id),
        "library": rows("select * from skill_library where run_id = %s", run_id),
        "library_links": rows("""select l.* from library_links l where exists
                                 (select 1 from run_clusters rc where rc.run_id = %s and rc.topic_id = l.topic_id)""", run_id),
    }
    con.rollback()
    return raw


# ---------- deterministic serialization ----------
def cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "is_finite"):  # Decimal
        return str(v)
    return str(v)


def to_csv(rows, cols, sort):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in sorted(rows, key=lambda r: tuple((r[c] is None, r[c] if r[c] is not None else "") for c in sort)):
        w.writerow([cell(r.get(c)) for c in cols])
    return buf.getvalue().encode("utf-8")


def vectors_of(raw):
    keys = sorted(e["skill_key"] for e in raw["embeddings"])
    by = {e["skill_key"]: e["embedding"] for e in raw["embeddings"]}
    V = np.asarray([json.loads(by[k]) if isinstance(by[k], str) else by[k] for k in keys], dtype=np.float32)
    return keys, V


def serialize(raw):
    """raw -> {file name: bytes}. Same data in any order -> same bytes."""
    keys, V = vectors_of(raw)
    buf = io.BytesIO()
    np.save(buf, V, allow_pickle=False)
    run = {k: cell(v) if isinstance(v, datetime) else v for k, v in raw["run"].items()}
    files = {
        "run.json": (json.dumps(run, sort_keys=True, indent=1, default=str) + "\n").encode("utf-8"),
        "skills.csv": to_csv([{"vector_row": i, "skill_key": k} for i, k in enumerate(keys)], COLUMNS["skills.csv"], ["vector_row"]),
        "vectors.npy": buf.getvalue(),
    }
    for name in ("topics", "memberships", "aliases", "reference_links", "library", "library_links"):
        f = f"{name}.csv"
        files[f] = to_csv(raw[name], COLUMNS[f], SORT[f])
    return dict(sorted(files.items()))


# ---------- verification ----------
def check(raw, expected=EXPECTED):
    """Integrity problems ([] = OK) and the counts, from the raw records (same checks run on exported files)."""
    p = []
    topics = [t["topic_id"] for t in raw["topics"]]
    mem = raw["memberships"]
    skills = [m["skill_key"] for m in mem]
    emb = [e["skill_key"] for e in raw["embeddings"]]
    tset, sset, eset = set(topics), set(skills), set(emb)
    counts = {"topics": len(tset), "transversal": sum(bool(t["is_transversal"]) for t in raw["topics"]),
              "skills": len(sset), "assigned": sum(m["state"] == "assigned" for m in mem),
              "weak": sum(m["state"] == "weak" for m in mem), "embeddings": len(eset)}
    if len(topics) != len(tset):
        p.append("duplicate topic IDs")
    if len(skills) != len(sset):
        p.append("a skill has more than one membership row")
    if len(emb) != len(eset):
        p.append("duplicate embeddings")
    if missing := {m["topic_id"] for m in mem} - tset:
        p.append(f"{len(missing)} memberships point to unknown topics")
    if sset - eset:
        p.append(f"{len(sset - eset)} skills have no embedding")
    if eset - sset:
        p.append(f"{len(eset - sset)} embeddings belong to no skill")
    if tset - {m["topic_id"] for m in mem if m["state"] == "assigned"}:
        p.append("a topic has no assigned member")
    if any(m["score"] is None for m in mem):
        p.append("membership scores missing")
    _, V = vectors_of(raw)
    counts["dims"] = int(V.shape[1]) if V.ndim == 2 and len(V) else 0
    if V.ndim != 2 or not np.isfinite(V).all():
        p.append("embeddings contain NaN or infinite values")
    elif len(V):
        norms = np.linalg.norm(V, axis=1)
        if (bad := int((np.abs(norms - 1) > NORM_TOL).sum())):
            p.append(f"{bad} vectors are not unit length (tolerance {NORM_TOL})")
    models = {(e["model_id"], e["revision"]) for e in raw["embeddings"]}
    if len(models) != 1:
        p.append(f"embeddings come from {len(models)} model versions")
    for name, col, ref in (("aliases", "skill_key", sset), ("reference_links", "skill_key", sset),
                           ("library", "skill_key", sset), ("library_links", "skill_key", sset),
                           ("library_links", "topic_id", tset)):
        if {r[col] for r in raw[name]} - ref:
            p.append(f"{name}.{col} has values outside the snapshot")
    for k, v in expected.items():
        if counts.get(k) != v:
            p.append(f"{k}: {counts.get(k)} != expected {v}")
    return p, counts


def raw_from_files(d):
    """Rebuild the raw records from an exported snapshot (strings), for verify."""
    d = Path(d)
    read = lambda f: list(csv.DictReader((d / f).open(encoding="utf-8", newline="")))
    V = np.load(d / "vectors.npy", allow_pickle=False)
    keys = [r["skill_key"] for r in read("skills.csv")]
    run = json.loads((d / "run.json").read_text(encoding="utf-8"))
    mem = read("memberships.csv")
    for m in mem:
        m["score"] = float(m["score"]) if m["score"] else None
    topics = read("topics.csv")
    for t in topics:
        t["is_transversal"] = t["is_transversal"] == "true"
    return {"run": run, "topics": topics, "memberships": mem,
            "embeddings": [{"skill_key": k, "model_id": None, "revision": None, "embedding": v} for k, v in zip(keys, V)],
            **{n: read(f"{n}.csv") for n in ("aliases", "reference_links", "library", "library_links")}}


def git_commit(root):
    """HEAD commit, plus '+uncommitted' when the working tree has changes (read-only git commands)."""
    try:
        run = lambda *a: subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout
        return run("rev-parse", "HEAD").strip() + ("+uncommitted" if run("status", "--porcelain").strip() else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def build_manifest(raw, files, counts, commit, snapshot_utc):
    model = sorted({(e["model_id"], e["revision"]) for e in raw["embeddings"]})
    hashes = {f: sha256(b) for f, b in files.items()}
    rows = {f: b.decode("utf-8").count("\n") - 1 for f, b in files.items() if f.endswith(".csv")}
    return {"schema_version": SCHEMA_VERSION, "run_id": raw["run"]["run_id"], "source_commit": commit,
            "snapshot_utc": snapshot_utc, "read_only_transaction": True,
            "embedding_model": {"model_id": model[0][0], "revision": model[0][1]} if len(model) == 1 else model,
            "source_vectors_sha256": raw["run"]["vectors_sha256"],
            "vectors": {"shape": [counts["embeddings"], counts["dims"]], "dtype": "float32",
                        "note": "database copy (7 significant digits from load_embeddings.py), rows = skills.csv order"},
            "counts": counts, "rows": rows, "files_sha256": hashes,
            "data_fingerprint": sha256("\n".join(f"{f}:{h}" for f, h in sorted(hashes.items())).encode()),
            "ordering": {**{f: s for f, s in SORT.items()}, "vectors.npy": "row i = skills.csv vector_row i (sorted skill_key)"},
            "excluded": "no postings text, statements, gold labels, credentials or review data"}


def export(raw, root=ROOT, commit=None, again=None, expected=EXPECTED):
    """Write the snapshot (refuses to overwrite). `again` = a second, independent fetch that must serialize identically."""
    run_id = raw["run"]["run_id"]
    out, mcopy = snapshot_dir(root, run_id), tracked_manifest(root, run_id)
    if out.exists() or mcopy.exists():
        raise FileExistsError(f"snapshot for {run_id} already exists ({out.name}); never overwritten")
    problems, counts = check(raw, expected)
    if problems:
        raise ValueError("snapshot checks failed: " + "; ".join(problems))
    files = serialize(raw)
    if files != serialize(raw):
        raise ValueError("serialization is not deterministic")
    if again is not None and {f: sha256(b) for f, b in serialize(again).items()} != {f: sha256(b) for f, b in files.items()}:
        raise ValueError("two reads of the database gave different data (it changed during export); try again")
    manifest = build_manifest(raw, files, counts, commit, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
    for f, b in files.items():
        (tmp / f).write_bytes(b)
    text = json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    (tmp / "manifest.json").write_text(text, encoding="utf-8")
    os.rename(tmp, out)  # the snapshot appears complete or not at all
    mcopy.parent.mkdir(parents=True, exist_ok=True)
    with mcopy.open("x", encoding="utf-8") as fh:
        fh.write(text)
    return out, manifest


def verify(root=ROOT, run_id=RUN_ID, expected=EXPECTED, fresh_raw=None):
    """Re-hash every file against the manifest (and the tracked copy), re-run the integrity checks on the files,
    and optionally compare with a fresh database read. Returns a list of problems ([] = OK)."""
    d = snapshot_dir(root, run_id)
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    p = []
    tm = tracked_manifest(root, run_id)
    if not tm.is_file() or tm.read_text(encoding="utf-8") != (d / "manifest.json").read_text(encoding="utf-8"):
        p.append("tracked manifest copy missing or different")
    for f, h in manifest["files_sha256"].items():
        if not (d / f).is_file() or sha256((d / f).read_bytes()) != h:
            p.append(f"{f}: hash differs from manifest")
    if p:
        return p
    raw = raw_from_files(d)
    for e in raw["embeddings"]:
        e["model_id"], e["revision"] = manifest["embedding_model"]["model_id"], manifest["embedding_model"]["revision"]
    p += check(raw, expected)[0]
    if fresh_raw is not None and {f: sha256(b) for f, b in serialize(fresh_raw).items()} != manifest["files_sha256"]:
        p.append("the database now differs from the snapshot (drift)")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["export", "verify"])
    ap.add_argument("--env", default=str(ROOT / ".env"), help=".env with SUPABASE_DB_URL (not copied anywhere)")
    ap.add_argument("--db", action="store_true", help="verify: also compare with a fresh read-only database read")
    args = ap.parse_args()
    try:
        if args.cmd == "export":
            with connect(args.env) as con:
                raw, again = fetch(con), fetch(con)
            out, m = export(raw, ROOT, git_commit(ROOT), again)
            print(f"snapshot -> {out.relative_to(ROOT)} (manifest copy: {tracked_manifest(ROOT, RUN_ID).relative_to(ROOT)})")
            print("counts:", json.dumps(m["counts"]), "| fingerprint:", m["data_fingerprint"][:16])
        else:
            fresh = None
            if args.db:
                with connect(args.env) as con:
                    fresh = fetch(con)
            problems = verify(ROOT, RUN_ID, fresh_raw=fresh)
            print("OK: all hashes and checks pass" + (" and the database matches" if args.db else "") if not problems
                  else "PROBLEMS:\n  " + "\n  ".join(problems))
            sys.exit(1 if problems else 0)
    except (RuntimeError, ValueError, FileExistsError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
