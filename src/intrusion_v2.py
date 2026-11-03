"""Blind three-reviewer word-intrusion test for the ACTIVE clustering run (Sprint 3 coherence check, v2).

    python src/intrusion_v2.py make                       # read-only snapshot of the active run -> questions + key
    python src/intrusion_v2.py validate --reviewer lochan # check your response file (no answers are revealed)
    python src/intrusion_v2.py submit   --reviewer lochan # lock your responses (cannot be overwritten)
    python src/intrusion_v2.py status                     # who has submitted (no answers shown)
    python src/intrusion_v2.py score                      # only when all three have submitted

Design (v1 = src/intrusion_test.py on origin/main: one anonymous rater, 5+1 options, far intruders, key next to items):
  - each question = 4 genuine members of one topic + 1 intruder from another topic, positions balanced A-E
  - topics are sampled by stratum: transversal, low confidence (low mean member score), long tail (low minimum
    member score = possible contamination), and large / medium / small size terciles
  - genuine members: random assigned members, skipping near-copies of each other (cosine >= GENUINE_MAX_COS)
  - intruder: an assigned member of a nearby but different, non-transversal topic (centroid rank 3-15), not a
    synonym (cosine to every genuine member < INTRUDER_MAX_COS) and closer to its own topic than to this one;
    the most similar such candidate among a seeded random pick of the closest ones, so intruders are plausible
  - reviewer files (questions.json, responses/<name>.csv) never contain topic IDs, labels, scores or the answer;
    the key lives in data/interim/ (gitignored) and only its SHA-256 is in the tracked manifest

The database is read inside a transaction the server confirms as READ ONLY. Nothing is written to Supabase.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "hdbscan_10_umap10_ms1_2026-10-23"
EXPECTED = {"topics": 374, "members": 11093}
REVIEWERS = ("lochan", "priyanka", "dhanush")
LETTERS = "ABCDE"
SEED = 20261103
STRATA = (("transversal", 4), ("low_confidence", 4), ("long_tail", 4), ("large", 4), ("medium", 4), ("small", 4))
GENUINE_MAX_COS = 0.95
INTRUDER_MAX_COS = (0.70, 0.75, 0.80)  # relaxed step by step only if no candidate passes; the used value is recorded
NEIGHBOUR_RANKS = (2, 15)  # skip the 2 nearest topics (near-duplicate topics), use the next ones
PLAUSIBLE_POOL = 10
# Topics whose members / labels were printed in the audit chat on 2026-11-02 (a reviewer has seen them).
EXCLUDE_TOPICS = ("T0007", "T0013", "T0024", "T0026", "T0053", "T0058", "T0072", "T0115", "T0126", "T0141", "T0328")


def out_dir(root, run_id):
    return Path(root) / "reports" / "intrusion_v2" / run_id


def key_path(root, run_id):
    return Path(root) / "data" / "interim" / "intrusion_v2" / run_id / "answer_key.json"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_new(path, text):
    """Create a file; never replace an existing one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as f:
        f.write(text)


# ---------- read-only snapshot of the active run ----------
def load_active_run(expected_run=RUN_ID):
    """Topics, assigned/weak memberships and the assigned members' vectors, from Supabase (read-only)."""
    import psycopg
    from dotenv import dotenv_values
    url = dotenv_values(ROOT / ".env").get("SUPABASE_DB_URL")
    if not url:
        sys.exit("SUPABASE_DB_URL is not set in .env")
    with psycopg.connect(url, connect_timeout=20, autocommit=False) as con:
        cur = con.cursor()
        cur.execute("set transaction read only")
        cur.execute("show transaction_read_only")
        if cur.fetchone()[0] != "on":
            sys.exit("the database did not confirm a read-only transaction; stopping")
        cur.execute("select run_id, vectors_sha256 from cluster_runs where is_active")
        active = cur.fetchall()
        if len(active) != 1 or active[0][0] != expected_run:
            sys.exit(f"active run is {[a[0] for a in active]}, expected {expected_run}; not substituting another run")
        run_id, vsha = active[0]
        cur.execute("""select t.topic_id, t.label, t.is_transversal from topics t
                       where t.level = 'topic' and t.status = 'active' and exists
                       (select 1 from skill_topics s where s.run_id = %s and s.topic_id = t.topic_id) order by 1""", (run_id,))
        topics = {t: {"label": lab, "transversal": bool(tr)} for t, lab, tr in cur.fetchall()}
        cur.execute("""select skill_key, topic_id, state, score, margin from skill_topics where run_id = %s
                       order by topic_id, skill_key""", (run_id,))
        members = [{"skill_key": k, "topic_id": t, "state": s, "score": float(sc), "margin": float(m) if m is not None else None}
                   for k, t, s, sc, m in cur.fetchall()]
        cur.execute("""select e.skill_key, e.embedding::text from skill_embeddings e join skill_topics s
                       on s.skill_key = e.skill_key and s.run_id = %s and s.state = 'assigned'
                       where e.vectors_sha256 = %s order by 1""", (run_id, vsha))
        vectors = {k: np.asarray(json.loads(v), dtype=np.float32) for k, v in cur.fetchall()}
        con.rollback()
    return {"run_id": run_id, "vectors_sha256": vsha, "topics": topics, "members": members, "vectors": vectors}


def verify_snapshot(snap, expected=EXPECTED):
    keys = [m["skill_key"] for m in snap["members"]]
    problems = []
    if len(snap["topics"]) != expected["topics"]:
        problems.append(f"topics {len(snap['topics'])} != {expected['topics']}")
    if len(keys) != expected["members"] or len(set(keys)) != len(keys):
        problems.append(f"members {len(keys)} (distinct {len(set(keys))}) != {expected['members']}")
    if any(m["score"] is None for m in snap["members"]):
        problems.append("membership scores missing")
    if any(not t["label"] for t in snap["topics"].values()):
        problems.append("topic labels missing")
    assigned = {m["skill_key"] for m in snap["members"] if m["state"] == "assigned"}
    if assigned - set(snap["vectors"]):
        problems.append(f"{len(assigned - set(snap['vectors']))} assigned skills have no vector")
    return problems


def snapshot_hash(snap):
    rows = sorted((m["skill_key"], m["topic_id"], m["state"], round(m["score"], 6)) for m in snap["members"])
    payload = json.dumps({"run": snap["run_id"], "vectors": snap["vectors_sha256"], "members": rows,
                          "topics": sorted((t, v["label"], v["transversal"]) for t, v in snap["topics"].items())})
    return sha256_bytes(payload.encode())


# ---------- sampling ----------
def topic_stats(snap):
    by = {}
    for m in snap["members"]:
        if m["state"] == "assigned":
            by.setdefault(m["topic_id"], []).append(m)
    stats = {}
    for t, ms in by.items():
        V = np.stack([snap["vectors"][m["skill_key"]] for m in ms])
        c = V.mean(axis=0)
        stats[t] = {"members": sorted(ms, key=lambda m: m["skill_key"]), "size": len(ms),
                    "mean_score": float(np.mean([m["score"] for m in ms])), "min_score": float(min(m["score"] for m in ms)),
                    "centroid": c / np.linalg.norm(c), "transversal": snap["topics"][t]["transversal"]}
    return stats


def strata_pools(stats, eligible):
    ts = sorted(eligible)
    sizes = sorted(stats[t]["size"] for t in ts)
    lo, hi = sizes[len(sizes) // 3], sizes[2 * len(sizes) // 3]
    q = lambda key, frac: sorted(stats[t][key] for t in ts)[max(0, int(len(ts) * frac) - 1)]
    mean_cut, min_cut = q("mean_score", 0.25), q("min_score", 0.25)
    nt = [t for t in ts if not stats[t]["transversal"]]
    return {"transversal": [t for t in ts if stats[t]["transversal"]],
            "low_confidence": [t for t in nt if stats[t]["mean_score"] <= mean_cut],
            "long_tail": [t for t in nt if stats[t]["min_score"] <= min_cut],
            "large": [t for t in nt if stats[t]["size"] > hi],
            "medium": [t for t in nt if lo < stats[t]["size"] <= hi],
            "small": [t for t in nt if stats[t]["size"] <= lo]}, {"size_terciles": [lo, hi], "mean_score_q25": mean_cut,
                                                                  "min_score_q25": min_cut}


def pick_genuine(stats, vectors, t, rng):
    ms = stats[t]["members"][:]
    rng.shuffle(ms)
    chosen = []
    for m in ms:
        v = vectors[m["skill_key"]]
        if all(float(v @ vectors[c["skill_key"]]) < GENUINE_MAX_COS for c in chosen):
            chosen.append(m)
        if len(chosen) == 4:
            return chosen
    return None


def pick_intruder(stats, vectors, t, genuine, rng, excluded):
    G = np.stack([vectors[m["skill_key"]] for m in genuine])
    gc = G.mean(axis=0)
    gc /= np.linalg.norm(gc)
    others = [o for o in sorted(stats) if o != t and not stats[o]["transversal"] and o not in excluded]
    near = sorted(others, key=lambda o: -float(stats[o]["centroid"] @ stats[t]["centroid"]))[NEIGHBOUR_RANKS[0]:NEIGHBOUR_RANKS[1]]
    cands = [(o, m) for o in near for m in stats[o]["members"]]
    for limit in INTRUDER_MAX_COS:
        ok = []
        for o, m in cands:
            v = vectors[m["skill_key"]]
            max_g, to_here, to_own = float(np.max(G @ v)), float(v @ gc), float(v @ stats[o]["centroid"])
            if max_g < limit and to_own > to_here:
                ok.append((to_here, o, m, max_g))
        if ok:
            ok.sort(key=lambda x: (-x[0], x[2]["skill_key"]))
            to_here, o, m, max_g = rng.choice(ok[:PLAUSIBLE_POOL])
            return {"skill_key": m["skill_key"], "topic_id": o, "cos_to_genuine_centroid": round(to_here, 4),
                    "max_cos_to_genuine": round(max_g, 4), "synonym_limit_used": limit}
    return None


def build(snap, seed=SEED, strata=STRATA, exclude=EXCLUDE_TOPICS):
    """Pure function: snapshot -> (questions for reviewers, answer key, sampling report)."""
    rng = random.Random(seed)
    stats = topic_stats(snap)
    excluded = set(exclude)
    eligible = [t for t in stats if t not in excluded]
    pools, cuts = strata_pools(stats, eligible)
    chosen, skipped, drawn = [], [], {}
    for name, k in strata:
        pool = [t for t in pools[name] if t not in {c["topic_id"] for c in chosen}]
        rng.shuffle(pool)
        drawn[name] = 0
        for t in pool:
            if drawn[name] == k:
                break
            genuine = pick_genuine(stats, snap["vectors"], t, rng)
            intruder = pick_intruder(stats, snap["vectors"], t, genuine, rng, excluded) if genuine else None
            if genuine is None or intruder is None:
                skipped.append({"topic_id": t, "stratum": name,
                                "reason": "fewer than 4 distinct genuine members" if genuine is None else "no suitable intruder"})
                continue
            chosen.append({"topic_id": t, "stratum": name, "genuine": genuine, "intruder": intruder})
            drawn[name] += 1
    positions = [i % 5 for i in range(len(chosen))]  # balanced: each letter is the answer about equally often
    rng.shuffle(positions)
    rng.shuffle(chosen)
    questions, key = [], {}
    for i, (c, pos) in enumerate(zip(chosen, positions), 1):
        qid = f"Q{i:02d}"
        opts = [m["skill_key"] for m in c["genuine"]]
        rng.shuffle(opts)
        opts.insert(pos, c["intruder"]["skill_key"])
        questions.append({"question_id": qid, "options": dict(zip(LETTERS, opts))})
        t = stats[c["topic_id"]]
        key[qid] = {"answer": LETTERS[pos], "topic_id": c["topic_id"], "topic_label": snap["topics"][c["topic_id"]]["label"],
                    "stratum": c["stratum"], "topic_size": t["size"], "topic_mean_score": round(t["mean_score"], 4),
                    "genuine": [{"skill_key": m["skill_key"], "score": round(m["score"], 4)} for m in c["genuine"]],
                    "intruder": c["intruder"]}
    report = {"strata_requested": dict(strata), "strata_drawn": drawn, "pool_sizes": {k: len(v) for k, v in pools.items()},
              "cuts": cuts, "skipped_topics": skipped, "excluded_topics": sorted(excluded),
              "eligible_topics": len(eligible), "questions": len(questions)}
    return questions, key, report


# ---------- files ----------
def template_csv(questions, reviewer):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["reviewer", "question_id", *LETTERS, "answer", "note"])
    for q in questions:
        w.writerow([reviewer, q["question_id"], *(q["options"][x] for x in LETTERS), "", ""])
    return buf.getvalue()


def make(root=ROOT, snap=None, seed=SEED, run_id=RUN_ID, expected=EXPECTED):
    out, kp = out_dir(root, run_id), key_path(root, run_id)
    if (out / "questions.json").exists() or kp.exists():
        sys.exit(f"{out} already has a test; never regenerated (responses are tied to these questions)")
    snap = snap or load_active_run(run_id)
    problems = verify_snapshot(snap, expected)
    if problems:
        sys.exit("active run does not match the expected taxonomy: " + "; ".join(problems))
    questions, key, report = build(snap, seed)
    key_text = json.dumps({"run_id": run_id, "seed": seed, "key": key}, indent=1) + "\n"
    q_text = json.dumps({"run_id": run_id, "instructions": "Each question lists 5 skills. Four belong together; "
                         "pick the one that does not belong (A-E).", "questions": questions}, indent=1) + "\n"
    write_new(kp, key_text)
    write_new(out / "questions.json", q_text)
    for r in REVIEWERS:
        write_new(out / "responses" / f"{r}.csv", template_csv(questions, r))
    manifest = {"test": "intrusion_v2", "run_id": run_id, "vectors_sha256": snap["vectors_sha256"],
                "snapshot_sha256": snapshot_hash(snap), "generated_utc": now(), "seed": seed,
                "settings": {"strata": dict(STRATA), "genuine_max_cos": GENUINE_MAX_COS, "intruder_max_cos": INTRUDER_MAX_COS,
                             "neighbour_ranks": NEIGHBOUR_RANKS, "plausible_pool": PLAUSIBLE_POOL, "options": 5},
                "sampling": {k: v for k, v in report.items() if k != "skipped_topics"},
                "skipped_topic_count": len(report["skipped_topics"]),
                "questions_sha256": sha256_bytes(q_text.encode()),
                "answer_key": {"path": kp.relative_to(root).as_posix(), "sha256": sha256_bytes(key_text.encode()),
                               "note": "gitignored; only its hash is tracked, so it cannot be changed after reviews"},
                "reviewers": list(REVIEWERS), "chance_accuracy": 0.2}
    write_new(out / "manifest.json", json.dumps(manifest, indent=1) + "\n")
    return out, report


def load_questions(root, run_id):
    return json.loads((out_dir(root, run_id) / "questions.json").read_text(encoding="utf-8"))["questions"]


def validate(root, run_id, reviewer):
    """Return (answers {qid: letter}, problems, missing qids). Never reads the answer key."""
    if reviewer not in REVIEWERS:
        raise ValueError(f"unknown reviewer {reviewer!r}; choose one of {', '.join(REVIEWERS)}")
    qs = {q["question_id"]: q for q in load_questions(root, run_id)}
    path = out_dir(root, run_id) / "responses" / f"{reviewer}.csv"
    answers, problems = {}, []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.DictReader(f), 2):
            qid, a = (r.get("question_id") or "").strip(), (r.get("answer") or "").strip().upper()
            if (r.get("reviewer") or "").strip().lower() != reviewer:
                problems.append(f"line {i}: reviewer column is not {reviewer}")
            if qid not in qs:
                problems.append(f"line {i}: unknown question {qid!r}")
                continue
            if qid in answers:
                problems.append(f"line {i}: {qid} answered twice")
                continue
            if any((r.get(x) or "").strip() != qs[qid]["options"][x] for x in LETTERS):
                problems.append(f"line {i}: options of {qid} were edited")
            if a and a not in LETTERS:
                problems.append(f"line {i}: answer {a!r} is not one of A-E")
            answers[qid] = a if a in LETTERS else ""
    missing = sorted(q for q in qs if not answers.get(q))
    return {q: a for q, a in answers.items() if a}, problems, missing


def submit(root, run_id, reviewer):
    answers, problems, missing = validate(root, run_id, reviewer)
    if problems or missing:
        raise ValueError(f"not submitted: {len(problems)} problems, {len(missing)} unanswered ({', '.join(missing[:8])})")
    path = out_dir(root, run_id) / "responses" / f"{reviewer}.csv"
    rec = {"reviewer": reviewer, "submitted_utc": now(), "responses_sha256": sha256_bytes(path.read_bytes()),
           "answers": answers}
    try:
        write_new(out_dir(root, run_id) / "submitted" / f"{reviewer}.json", json.dumps(rec, indent=1) + "\n")
    except FileExistsError:
        raise ValueError(f"{reviewer} has already submitted; a submission is never overwritten") from None
    return rec


def status(root, run_id):
    sub = out_dir(root, run_id) / "submitted"
    return {r: (sub / f"{r}.json").is_file() for r in REVIEWERS}


# ---------- scoring ----------
def wilson(k, n, z=1.96):  # same interval as v1 (src/intrusion_test.py)
    if n == 0:
        return 0.0, 0.0
    p = k / n
    mid, half = (p + z * z / (2 * n)) / (1 + z * z / n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return mid - half, mid + half


def fleiss_kappa(table):
    """table: rows = questions, columns = counts per category, same number of raters per row."""
    n = sum(table[0]) if table else 0
    if n < 2 or not table:
        return None
    N, k = len(table), len(table[0])
    p_j = [sum(r[j] for r in table) / (N * n) for j in range(k)]
    P_i = [(sum(c * c for c in r) - n) / (n * (n - 1)) for r in table]
    P_bar, P_e = sum(P_i) / N, sum(p * p for p in p_j)
    return None if P_e == 1 else (P_bar - P_e) / (1 - P_e)


def score(root, run_id, key_file=None, allow_partial=False):
    out = out_dir(root, run_id)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    kp = Path(key_file) if key_file else Path(root) / manifest["answer_key"]["path"]
    key_bytes = kp.read_bytes()
    if sha256_bytes(key_bytes) != manifest["answer_key"]["sha256"]:
        raise ValueError("answer key does not match the hash in manifest.json (changed or wrong file)")
    key = json.loads(key_bytes)["key"]
    done = {r: json.loads((out / "submitted" / f"{r}.json").read_text(encoding="utf-8"))
            for r, ok in status(root, run_id).items() if ok}
    if len(done) < len(REVIEWERS) and not allow_partial:
        raise ValueError(f"waiting for {', '.join(r for r in REVIEWERS if r not in done)}; scores are only final with all three")
    for r, rec in done.items():  # the response file must still be the one that was submitted
        if sha256_bytes((out / "responses" / f"{r}.csv").read_bytes()) != rec["responses_sha256"]:
            raise ValueError(f"{r}'s response file changed after submission")
    qids = sorted(key)
    per_rev = {}
    for r, rec in done.items():
        k = sum(rec["answers"].get(q) == key[q]["answer"] for q in qids)
        per_rev[r] = {"correct": k, "n": len(qids), "accuracy": round(k / len(qids), 3),
                      "ci95": [round(x, 3) for x in wilson(k, len(qids))]}
    rows, table = [], []
    for q in qids:
        picks = {r: rec["answers"].get(q) for r, rec in done.items()}
        correct = sum(p == key[q]["answer"] for p in picks.values())
        unanimous = len(set(picks.values())) == 1
        rows.append({"question_id": q, "topic_id": key[q]["topic_id"], "topic_label": key[q]["topic_label"],
                     "stratum": key[q]["stratum"], "picks": picks, "answer": key[q]["answer"], "n_correct": correct,
                     "agreement": "unanimous" if unanimous else "disputed",
                     "needs_adjudication": (not unanimous) or correct * 2 < len(picks)})
        table.append([list(picks.values()).count(x) for x in LETTERS])
    total = sum(v["correct"] for v in per_rev.values())
    n_all = len(qids) * len(done)
    by_stratum = {}
    for row in rows:
        s = by_stratum.setdefault(row["stratum"], [0, 0])
        s[0] += row["n_correct"]
        s[1] += len(row["picks"])
    revs = list(done)
    pairwise = {f"{a}-{b}": round(sum(done[a]["answers"].get(q) == done[b]["answers"].get(q) for q in qids) / len(qids), 3)
                for i, a in enumerate(revs) for b in revs[i + 1:]}
    return {"run_id": run_id, "final": len(done) == len(REVIEWERS), "reviewers": revs, "chance": 0.2,
            "correctness": {"per_reviewer": per_rev,
                            "overall": {"correct": total, "n": n_all, "accuracy": round(total / n_all, 3) if n_all else None,
                                        "ci95": [round(x, 3) for x in wilson(total, n_all)],
                                        "note": "pooled over reviewers; answers to the same question are not independent"},
                            "by_stratum": {k: {"correct": a, "n": b, "accuracy": round(a / b, 3)} for k, (a, b) in by_stratum.items()}},
            "agreement": {"pairwise_same_choice": pairwise, "fleiss_kappa": fleiss_kappa(table) if len(revs) > 1 else None,
                          "unanimous": sum(r["agreement"] == "unanimous" for r in rows),
                          "disputed": sum(r["agreement"] == "disputed" for r in rows),
                          "note": "agreement says reviewers chose alike, not that they were right"},
            "questions": rows, "adjudication": [r["question_id"] for r in rows if r["needs_adjudication"]]}


def write_score(root, run_id, result):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir(root, run_id) / "scores" / f"score_{stamp}{'' if result['final'] else '_PARTIAL'}.json"
    write_new(path, json.dumps(result, indent=1) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("make")
    for c in ("validate", "submit"):
        sub.add_parser(c).add_argument("--reviewer", required=True, choices=REVIEWERS)
    sub.add_parser("status")
    s = sub.add_parser("score")
    s.add_argument("--key", help="answer_key.json (default: path in manifest.json)")
    s.add_argument("--allow-partial", action="store_true", help="score before all three submitted (marked PARTIAL)")
    args = ap.parse_args()
    try:
        if args.cmd == "make":
            out, rep = make()
            print(f"{rep['questions']} questions from {rep['questions']} topics -> {out.relative_to(ROOT)}")
            print("strata drawn:", rep["strata_drawn"], "| skipped topics:", len(rep["skipped_topics"]),
                  "| excluded (shown in chat):", len(rep["excluded_topics"]))
            print("answer key written to the gitignored data/interim/ folder; its contents are not printed")
        elif args.cmd == "validate":
            answers, problems, missing = validate(ROOT, RUN_ID, args.reviewer)
            print(f"{args.reviewer}: {len(answers)} answered, {len(missing)} missing, {len(problems)} problems")
            for p in problems:
                print("  -", p)
        elif args.cmd == "submit":
            rec = submit(ROOT, RUN_ID, args.reviewer)
            print(f"submitted {len(rec['answers'])} answers for {args.reviewer} at {rec['submitted_utc']} (locked)")
        elif args.cmd == "status":
            for r, ok in status(ROOT, RUN_ID).items():
                print(f"{r:10} {'submitted' if ok else 'not yet'}")
        else:
            res = score(ROOT, RUN_ID, args.key, args.allow_partial)
            path = write_score(ROOT, RUN_ID, res)
            c, a = res["correctness"], res["agreement"]
            print(f"{'FINAL' if res['final'] else 'PARTIAL'} -> {path.relative_to(ROOT)}")
            for r, v in c["per_reviewer"].items():
                print(f"  {r:9} {v['correct']}/{v['n']} = {v['accuracy']:.2f}  95% CI {v['ci95'][0]:.2f}-{v['ci95'][1]:.2f}")
            print(f"  overall  {c['overall']['correct']}/{c['overall']['n']} = {c['overall']['accuracy']}  (chance 0.20)")
            print(f"  agreement: unanimous {a['unanimous']}, disputed {a['disputed']}, Fleiss kappa {a['fleiss_kappa']}")
            print(f"  needs adjudication: {', '.join(res['adjudication']) or 'none'}")
    except (ValueError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
