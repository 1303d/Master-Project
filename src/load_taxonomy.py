"""Load one clustering run + its skill library into the taxonomy tables (sql/taxonomy_schema.sql).

    py src/load_taxonomy.py --run RUN_DIR --library LIB_DIR --emb-dir EMB --aliases ALIASES.csv [--activate]

First load only: every cluster becomes a new persistent topic (T0001... by mentions, label = centroid skill,
provisional). Later runs need old -> new topic matching (Jaccard + Hungarian), not written yet: the script refuses
to load a second run while topics exist. member_of: clustered skills are 'assigned'; noise skills are 'weak'
members of their nearest topic centroid. score = cosine to that centroid, margin = best minus second best.
related_to: top-3 nearest skills by cosine. --activate makes this the active run (one at a time).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from cluster_skills import load
from db import connect

RELATED_PER_SKILL = 3


def copy_rows(cur, table, cols, rows):
    with cur.copy(f"copy {table} ({', '.join(cols)}) from stdin") as cp:
        for r in rows:
            cp.write_row(r)


def memberships(vectors, labels, clusters):
    """For every skill: (topic index, state, score, margin) against the cluster centroids."""
    C = np.stack([vectors[labels == c].mean(axis=0) for c in clusters])
    C /= np.linalg.norm(C, axis=1, keepdims=True)
    S = vectors @ C.T
    pos = {c: i for i, c in enumerate(clusters)}
    own = np.array([pos.get(l, -1) for l in labels])
    best = np.where(own >= 0, own, S.argmax(axis=1))
    score = S[np.arange(len(S)), best]
    S2 = S.copy()
    S2[np.arange(len(S)), best] = -np.inf
    margin = score - S2.max(axis=1)
    state = np.where(own >= 0, "assigned", "weak")
    return best, state, score, margin


def load_library(cur, library, links, topic_id, run_id):
    """skill_library + library_links rows (library-v2 columns are optional, so v1 outputs still load)."""
    get = lambda r, k: getattr(r, k, None) if not pd.isna(getattr(r, k, None)) else None
    copy_rows(cur, "skill_library", ["skill_key", "status", "n_postings", "n_unknown", "n_sectors", "top_share",
                                     "entropy", "rule_version", "run_id", "n_templates", "skill_type", "reuse_level"],
              [(r.skill_key, r.status, r.n_postings, r.n_unknown, r.n_sectors, r.top_share, r.entropy,
                r.rule_version, run_id, get(r, "n_templates"), get(r, "skill_type"), get(r, "reuse_level") or None)
               for r in library.itertuples()])
    copy_rows(cur, "library_links", ["skill_key", "topic_id", "n_postings", "lift", "p_value", "q_value", "strength",
                                     "n_templates"],
              [(r.skill_key, topic_id[r.group], r.n_postings, r.lift, r.p, r.q, r.strength, get(r, "n_templates"))
               for r in links.itertuples()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="cluster run folder (assignments.csv, topics.csv, run.json)")
    ap.add_argument("--library", required=True, help="build_library.py output folder")
    ap.add_argument("--emb-dir", required=True, help="the embeddings the run was clustered on")
    ap.add_argument("--aliases", required=True, help="aliases.csv from normalize_aliases.py")
    ap.add_argument("--activate", action="store_true")
    ap.add_argument("--library-only", action="store_true",
                    help="replace only skill_library + library_links for the already loaded run (topic ids unchanged)")
    args = ap.parse_args()

    run_dir, lib_dir = Path(args.run), Path(args.library)
    meta = json.loads((run_dir / "run.json").read_text())
    run_id = f"{meta['run_id']}_{meta['created_utc'][:10]}"
    vectors, index, vec_sha = load(args.emb_dir)
    if vec_sha != meta["vectors_sha256"]:
        raise SystemExit("--emb-dir is not the embedding this run was clustered on")
    assign = pd.read_csv(run_dir / "assignments.csv", keep_default_na=False)
    if (assign["skill_key"].to_numpy() != index["skill_key"].to_numpy()).any():
        raise SystemExit("assignments.csv rows do not line up with skill_index.csv")
    topics = pd.read_csv(run_dir / "topics.csv", keep_default_na=False)
    groups = pd.read_csv(lib_dir / "groups.csv").set_index("group")
    library = pd.read_csv(lib_dir / "library.csv", keep_default_na=False)
    links = pd.read_csv(lib_dir / "library_links.csv", keep_default_na=False)
    aliases = pd.read_csv(args.aliases, keep_default_na=False)

    clusters = topics["cluster"].tolist()                       # sorted by mentions
    topic_id = {c: f"T{i:04d}" for i, c in enumerate(clusters, 1)}
    labels = assign["cluster"].to_numpy()
    best, state, score, margin = memberships(vectors, labels, clusters)
    keys = index["skill_key"].to_numpy()
    sims = vectors @ vectors.T
    np.fill_diagonal(sims, -np.inf)
    near = np.argsort(-sims, axis=1)[:, :RELATED_PER_SKILL]

    if args.library_only:  # topic ids of this run already exist: map cluster -> topic id from run_clusters
        with connect() as con, con.transaction(), con.cursor() as cur:
            rows = cur.execute("select cluster_id, topic_id from run_clusters where run_id = %s", (run_id,)).fetchall()
            if not rows:
                raise SystemExit(f"run {run_id} is not loaded; load it first without --library-only")
            cur.execute("delete from skill_library where run_id = %s", (run_id,))  # cascades to library_links
            load_library(cur, library, links, {c: t for c, t in rows}, run_id)
        print(f"replaced library of {run_id}: {len(library)} library skills, {len(links)} links "
              f"({(links['strength'] == 'strong').sum()} strong)")
        return

    with connect() as con, con.transaction(), con.cursor() as cur:
        if cur.execute("select count(*) from topics").fetchone()[0]:
            raise SystemExit("topics already exist: loading a second run needs topic-id matching (not written yet)")
        params = {k: v for k, v in meta.items() if k not in ("run_id", "created_utc", "vectors_sha256", "metrics")}
        cur.execute("insert into cluster_runs (run_id, method, params, vectors_sha256, metrics) values (%s,%s,%s,%s,%s)",
                    (run_id, meta["method"], json.dumps(params), vec_sha, json.dumps(meta["metrics"])))
        copy_rows(cur, "topics", ["topic_id", "level", "label", "status", "is_transversal", "first_run", "last_run"],
                  [(topic_id[c], "topic", t.centroid_skill, "active", bool(groups.loc[c, "is_transversal"]), run_id,
                    run_id) for c, t in zip(clusters, topics.itertuples())])
        copy_rows(cur, "run_clusters", ["run_id", "cluster_id", "topic_id", "event"],
                  [(run_id, int(c), topic_id[c], "new") for c in clusters])
        copy_rows(cur, "skill_topics", ["run_id", "skill_key", "topic_id", "role", "state", "score", "margin"],
                  [(run_id, k, topic_id[clusters[b]], "primary", s, round(float(sc), 4), round(float(mg), 4))
                   for k, b, s, sc, mg in zip(keys, best, state, score, margin)])
        copy_rows(cur, "skill_relations", ["run_id", "skill_key", "related_key", "rank", "similarity"],
                  [(run_id, keys[i], keys[j], r, round(float(sims[i, j]), 4))
                   for i in range(len(keys)) for r, j in enumerate(near[i], 1)])
        copy_rows(cur, "skill_aliases", ["alias_key", "skill_key", "rule"],
                  [(a.skill_key, a.canonical_key, a.rules or None) for a in aliases.itertuples()])
        load_library(cur, library, links, topic_id, run_id)
        if args.activate:
            cur.execute("update cluster_runs set is_active = false where is_active")
            cur.execute("update cluster_runs set is_active = true where run_id = %s", (run_id,))
    print(f"loaded {run_id}: {len(clusters)} topics, {len(keys)} memberships ({(state == 'weak').sum()} weak), "
          f"{len(keys) * RELATED_PER_SKILL} relations, {len(library)} library skills, {len(links)} links"
          + (" (active)" if args.activate else ""))


if __name__ == "__main__":
    main()
