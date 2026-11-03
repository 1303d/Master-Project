"""Gold-validation tests on a small synthetic repository (tmp_path). No real gold, test or agreement data is read.

    python -m pytest tests/validation -q
"""
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

from validation import adjudication, manifests, reporting  # noqa: E402
from validation.config import Config  # noqa: E402
from validation.full_posting import locate  # noqa: E402
from validation.matching import compare_annotation  # noqa: E402
from validation.reviews import ReviewStore  # noqa: E402
from validation.sampling import sample_fraction, sample_ids  # noqa: E402
from validation.sources import MissingArtifact  # noqa: E402
from validation.storage import stable_id  # noqa: E402

GOLD = """n,posting_id,sector,sector_fixed,title,company_name,location,suggested_skills,gold_skills,labeled_by,notes
1,p1,IT,IT,t,c,l,,Python; SQL; three years of experience,x,
2,p2,IT,IT,t,c,l,,Excel; communication,x,
3,p3,IT,IT,t,c,l,,Secret Test Skill,x,
4,p4,IT,IT,t,c,l,,AutoCAD,x,
5,p5,IT,IT,t,c,l,,Unknown Split Skill,x,
6,p6,IT,IT,t,c,l,,Java; Spark,x,
8,pdup,IT,IT,t,c,l,,Dup A,x,
9,pdup,IT,IT,t,c,l,,Dup B,x,
44,p44,IT,IT,t,c,l,,Protected Alpha,x,
47,p47,IT,IT,t,c,l,,Protected Beta,x,
"""
SPLIT = "posting_id,sector_eval,split\np1,IT,dev\np2,IT,dev\np3,IT,test\np4,IT,dev\np6,IT,dev\npdup,IT,dev\np44,IT,dev\np47,IT,dev\n"
ERR_A = "error,n,skill\nmissed,1,SQL\nextra,1,Tableau\nmissed,2,communication\nmissed,44,Protected Alpha\nextra,47,Protected Extra\nextra,3,Test Extra\n"
ERR_B = "error,n,skill\nmissed,1,SQL\nextra,2,PowerPoint\nextra,44,Protected Extra2\n"
REP_A = "- **Coverage:** 6 of 6 gold postings scored.\n| **All** | 6 | 9 | 9 | 1 | 1 | 1 | 1 | 1 | 1 |\n"
REP_B = "- **Coverage:** 5 of 6 gold postings scored; NOT scored (failed or not run): p6.\n"
DESC = {"p1": "We need Python and SQL. Three years of experience.", "p2": "Use Excel daily.  Strong communication skills.",
        "p4": "AutoCAD drafting.", "p6": "Java and Spark, plus Kafka streaming.",
        "p44": "PROTECTED TEXT A", "p47": "PROTECTED TEXT B", "p3": "TEST TEXT"}
CONFIG = {
    "reviewers": ["lochan", "dhanush", "priyanka"], "protected_postings_n": [44, 47], "allowed_split": "dev",
    "paths": {"gold": "data/gold/gold_labels.csv", "split": "data/gold/gold_split.csv", "rules": "data/gold/LABELING_RULES.md",
              "postings": ["data/gold/gold_postings_dev.csv"], "historical_audit": "reports/audit_dev_key.csv"},
    "gold_version": "v1",
    "runs": {"run_a": {"errors": "reports/errors_a.csv", "report": "reports/rep_a.md"},
             "run_b": {"errors": "reports/errors_b.csv", "report": "reports/rep_b.md"}},
    "part1": {"runs": ["run_a", "run_b"], "historical_counts": {"total": 7}},
    "part2": {"runs": ["run_b"], "sample_fraction": 1.0, "seed": 7},
    "part3": {"sample_size": 2, "seed": 11},
    "rule_choices": ["A", "B"],
}


def make_repo(tmp, postings=True):
    def w(rel, text):
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    w("data/gold/gold_labels.csv", GOLD)
    w("data/gold/gold_split.csv", SPLIT)
    w("data/gold/LABELING_RULES.md", "# rules\n")
    w("reports/errors_a.csv", ERR_A)
    w("reports/errors_b.csv", ERR_B)
    w("reports/rep_a.md", REP_A)
    w("reports/rep_b.md", REP_B)
    w("reports/audit_dev_key.csv", "item_id,n,skill,source,runs\n1,1,SQL,gold-only (missed by model),v2\n2,44,Protected Alpha,gold-only (missed by model),v2\n")
    if postings:
        import csv
        buf = io.StringIO()
        wr = csv.writer(buf)
        wr.writerow(["n", "posting_id", "description"])
        for i, (pid, d) in enumerate(DESC.items()):
            wr.writerow([i, pid, d])
        w("data/gold/gold_postings_dev.csv", buf.getvalue())
    return Config(tmp, json.loads(json.dumps(CONFIG)))


@pytest.fixture
def cfg(tmp_path):
    return make_repo(tmp_path)


def all_text(cfg):
    """Everything the workflow wrote (manifests, reviews, reports)."""
    return "\n".join(p.read_text(encoding="utf-8") for p in (cfg.root / "data" / "validation").rglob("*") if p.is_file()) + \
        "\n".join(p.read_text(encoding="utf-8") for p in (cfg.root / "reports" / "validation").rglob("*") if p.is_file())


# 1 · 4 · 5 · 6 · 7 · 8
def test_disagreements_classified_and_protected(cfg):
    m, st = manifests.ensure(cfg, 1)
    got = {(i["posting_id"], i["type"], i["label"]): i["runs"] for i in m["items"]}
    assert st == "created"
    assert got == {("p1", "gold_only", "SQL"): ["run_a", "run_b"], ("p1", "model_only", "Tableau"): ["run_a"],
                   ("p2", "gold_only", "communication"): ["run_a"], ("p2", "model_only", "PowerPoint"): ["run_b"]}
    ex = m["population"]["excluded_postings"]
    assert ex == {"protected": 2, "other_split": 1, "unknown_split": 1, "duplicate": 2}
    text = all_text(cfg)
    for secret in ("Protected", "Secret Test", "Test Extra", "Unknown Split", "Dup A"):
        assert secret not in text
    assert m["population"]["historical_check"]["in_both"] == 1  # protected row of the old sheet is not compared


def test_stable_ids_and_no_duplicates_on_rebuild(cfg):
    m1, _ = manifests.ensure(cfg, 1)
    m2, st = manifests.ensure(cfg, 1)
    assert st == "unchanged" and m1["items"] == m2["items"]
    assert len({i["item_id"] for i in m1["items"]}) == len(m1["items"])
    assert stable_id("p1", "p1", "gold_only", "SQL") == stable_id("p1", "P1 ", "GOLD_ONLY", "sql")
    assert len(list(cfg.manifests_dir.glob("part1_v*.json"))) == 1


# 2
def test_agreements_exclude_missed_and_unscored(cfg):
    m, _ = manifests.ensure(cfg, 2)
    got = {(i["posting_id"], i["label"]) for i in m["items"]}
    # SQL was missed by run_b; p6 was not scored (would look like a full agreement); p44/p47 protected; p3 test
    assert got == {("p1", "Python"), ("p1", "three years of experience"), ("p2", "Excel"), ("p2", "communication"),
                   ("p4", "AutoCAD")}
    assert m["population"]["eligible_agreements"] == 5
    assert not any(k in json.dumps(m["items"]) for k in ("in_gold", "matched_by_runs", "agreement"))  # blind manifest
    key = manifests.part2_key(cfg, m["manifest_id"])
    assert set(key) == {i["item_id"] for i in m["items"]}


# 3
def test_sampling_is_deterministic():
    ids = [f"id{i}" for i in range(40)]
    assert sample_ids(ids, 12, 5) == sample_ids(list(reversed(ids)), 12, 5)
    assert sample_ids(ids, 12, 5) != sample_ids(ids, 12, 6)
    assert len(sample_fraction(ids, 0.25, 1)) == 10 and len(sample_fraction(ids[:2], 0.1, 1)) == 1


def test_part3_sample_excludes_protected_test_unknown(cfg):
    m, _ = manifests.ensure(cfg, 3)
    assert len(m["items"]) == 2
    assert {i["posting_id"] for i in m["items"]} <= {"p1", "p2", "p4", "p6"}
    assert all(i["description_sha256"] for i in m["items"])


# 9 · 13 · 14
def test_reviewer_files_locking_and_amendments(cfg):
    m, _ = manifests.ensure(cfg, 1)
    store, item = ReviewStore(cfg), next(i for i in m["items"] if i["type"] == "model_only")
    store.record("lochan", m, item["item_id"], "draft", {"decision": "ADD_TO_GOLD"})
    assert store.state("lochan", m["manifest_id"])[item["item_id"]]["status"] == "IN_REVIEW"
    with pytest.raises(ValueError, match="reason"):
        store.record("lochan", m, item["item_id"], "submit", {"decision": "ADD_TO_GOLD", "rule": "A"})
    store.record("lochan", m, item["item_id"], "submit", {"decision": "ADD_TO_GOLD", "rule": "A", "reason": "named tool"})
    with pytest.raises(ValueError, match="locked"):
        store.record("lochan", m, item["item_id"], "submit", {"decision": "KEEP_GOLD"})
    with pytest.raises(ValueError, match="locked"):
        store.record("lochan", m, item["item_id"], "draft", {"decision": "KEEP_GOLD"})
    with pytest.raises(ValueError, match="reason"):
        store.record("lochan", m, item["item_id"], "amend", {"decision": "KEEP_GOLD"})
    store.record("lochan", m, item["item_id"], "amend", {"decision": "KEEP_GOLD"}, amend_reason="re-read rule A")
    s = store.state("lochan", m["manifest_id"])[item["item_id"]]
    assert [v["version"] for v in s["versions"]] == [1, 2] and s["versions"][0]["data"]["decision"] == "ADD_TO_GOLD"
    assert s["latest"]["decision"] == "KEEP_GOLD"
    assert cfg.reviews_file("lochan").is_file() and not cfg.reviews_file("dhanush").exists()
    with pytest.raises(ValueError, match="unknown reviewer"):
        store.record("mallory", m, item["item_id"], "draft", {})
    with pytest.raises(ValueError, match="does not apply"):
        store.record("dhanush", m, item["item_id"], "submit", {"decision": "REMOVE_FROM_GOLD", "rule": "A", "reason": "x"})


# 12
def test_evidence_location():
    d = "Strong  Communication skills and SQL."
    assert locate(d, "SQL") == {"start": 33, "end": 36, "mode": "exact", "occurrences": 1}
    assert locate(d, "strong communication")["mode"] == "case_whitespace_insensitive"
    assert locate(d, "Python") is None and locate(d, "") is None


# 11 · 12
def test_full_posting_annotation_and_compare(cfg):
    m, _ = manifests.ensure(cfg, 3)
    item = m["items"][0]
    desc = DESC[item["posting_id"]]
    store = ReviewStore(cfg)
    word = desc.split()[0]
    with pytest.raises(ValueError, match="evidence not found"):
        store.record("priyanka", m, item["item_id"], "submit",
                     {"skills": [{"skill": "x", "evidence": "not in text at all", "confidence": "high"}]}, description=desc)
    draft = store.record("priyanka", m, item["item_id"], "draft",
                         {"skills": [{"skill": "x", "evidence": "nope", "confidence": "low"}]}, description=desc)
    assert draft["data"]["problems"]  # drafts may be incomplete, problems are recorded
    with pytest.raises(ValueError, match="hash mismatch"):
        store.record("priyanka", m, item["item_id"], "submit", {"skills": []}, description=desc + " changed")
    e = store.record("priyanka", m, item["item_id"], "submit",
                     {"skills": [{"skill": word, "evidence": word, "confidence": "high"}]}, description=desc)
    assert e["data"]["skills"][0]["location"]["start"] == 0 and e["data"]["description_sha256"] == item["description_sha256"]


def test_compare_categories():
    rows = compare_annotation(["Python", "Microsoft Excel", "Kafka", "Docker"], ["python", "Excel", "SQL"], ["Kafka"])
    kinds = {(r["kind"], r["reviewer_label"], r["gold_label"]) for r in rows}
    assert kinds == {("match", "Python", "python"), ("naming_difference", "Microsoft Excel", "Excel"),
                     ("reviewer_only", "Kafka", None), ("shared_omission", "Docker", None), ("gold_only", None, "SQL")}


# 15 · 17
def test_adjudication_transitions_and_nondestructive_gold(cfg):
    gold_before = cfg.p("gold").read_bytes()
    m, _ = manifests.ensure(cfg, 1)
    store = ReviewStore(cfg)
    item = next(i for i in m["items"] if i["label"] == "Tableau")
    store.record("lochan", m, item["item_id"], "submit", {"decision": "ADD_TO_GOLD", "rule": "A", "reason": "listed tool"})
    store.record("dhanush", m, item["item_id"], "submit", {"decision": "KEEP_GOLD"})
    case = next(c for c in adjudication.build_cases(cfg) if c["item_id"] == item["item_id"])
    assert case["status"] == "SUBMITTED" and case["conflict"]
    with pytest.raises(ValueError, match="rationale"):
        adjudication.adjudicate(cfg, "priyanka", case["case_id"], "APPROVED", "")
    adjudication.adjudicate(cfg, "priyanka", case["case_id"], "APPROVED", "rule A: named tool")
    assert next(c for c in adjudication.build_cases(cfg) if c["case_id"] == case["case_id"])["status"] == "APPROVED"
    adjudication.adjudicate(cfg, "dhanush", case["case_id"], "REJECTED", "only a preference")
    assert next(c for c in adjudication.build_cases(cfg) if c["case_id"] == case["case_id"])["status"] == "NEEDS_DISCUSSION"
    adjudication.adjudicate(cfg, "dhanush", case["case_id"], "APPROVED", "agreed after discussion")
    assert next(c for c in adjudication.build_cases(cfg) if c["case_id"] == case["case_id"])["status"] == "APPROVED"
    out, n = adjudication.approve_version(cfg, "v1_test")
    assert n == 1 and "add,,Tableau" in (out / "changes.csv").read_text()
    with pytest.raises(FileExistsError):
        adjudication.approve_version(cfg, "v1_test")
    assert cfg.p("gold").read_bytes() == gold_before
    assert len(adjudication.adjudication_events(cfg)[0]) == 3  # full history kept (the refused call wrote nothing)


# 16 · 18
def test_source_hash_change_requires_new_version(cfg):
    m1, _ = manifests.ensure(cfg, 1)
    store = ReviewStore(cfg)
    store.record("lochan", m1, m1["items"][0]["item_id"], "submit", {"decision": "UNSURE"})
    cfg.p("gold").write_text(GOLD.replace("Excel; communication", "Excel; communication; Word"), encoding="utf-8")
    assert "data/gold/gold_labels.csv" in manifests.stale_sources(cfg, m1)
    with pytest.raises(manifests.StaleSources):
        manifests.ensure(cfg, 1)
    m2, st = manifests.ensure(cfg, 1, new_version=True)
    assert st == "new_version" and m2["manifest_id"] == "part1_v2"
    assert (cfg.manifests_dir / "part1_v1.json").is_file()
    assert store.state("lochan", "part1_v2") == {} and store.state("lochan", "part1_v1")  # never mixed


# 19
def test_missing_artifacts(tmp_path):
    cfg = make_repo(tmp_path, postings=False)
    m, _ = manifests.ensure(cfg, 3)
    assert all(i["description_sha256"] is None for i in m["items"])
    with pytest.raises(ValueError, match="not on this machine"):
        ReviewStore(cfg).record("lochan", m, m["items"][0]["item_id"], "submit",
                                {"skills": [{"skill": "a", "evidence": "a", "confidence": "high"}]}, description=None)
    cfg.p("gold").unlink()
    with pytest.raises(MissingArtifact):
        manifests.ensure(cfg, 1)


# ---------- dashboard (WSGI) ----------
def call(app, method, path, body=None, query=""):
    raw = json.dumps(body).encode() if body is not None else b""
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query, "CONTENT_LENGTH": str(len(raw)),
           "wsgi.input": io.BytesIO(raw)}
    status = {}
    out = b"".join(app(env, lambda s, h: status.update(s=s, h=dict(h))))
    return status["s"], (json.loads(out) if status["h"]["Content-Type"] == "application/json" else out.decode())


@pytest.fixture
def api(cfg):
    from validation_api import ValidationAPI
    a = ValidationAPI(cfg)
    assert call(a, "POST", "/api/validation/build", {})[0] == "200 OK"
    return a


# 10
def test_blind_views(api, cfg):
    s, d = call(api, "GET", "/api/validation/items", query="part=2&reviewer=lochan")
    assert s == "200 OK" and set(d["items"][0]) == {"item_id", "posting_id", "n", "status", "draft", "latest", "versions", "label"}
    item = d["items"][0]["item_id"]
    assert call(api, "GET", "/api/validation/reveal", query=f"item={item}&reviewer=lochan")[0] == "403 Forbidden"
    call(api, "POST", "/api/validation/review", {"reviewer": "dhanush", "part": 2, "item_id": item, "action": "submit",
                                                 "data": {"decision": "INVALID_SKILL", "explanation": "years, not a skill"}})
    cases = call(api, "GET", "/api/validation/cases", query="reviewer=lochan")[1]
    assert cases and all(c.get("redacted") for c in cases if c["part"] == 2)  # lochan has not reviewed it yet
    call(api, "POST", "/api/validation/review", {"reviewer": "lochan", "part": 2, "item_id": item, "action": "submit",
                                                 "data": {"decision": "VALID_SKILL"}})
    s, d = call(api, "GET", "/api/validation/reveal", query=f"item={item}&reviewer=lochan")
    assert s == "200 OK" and d["reference"]["source"] == "agreement" and d["others"]["dhanush"]["decision"] == "INVALID_SKILL"
    p3 = call(api, "GET", "/api/validation/items", query="part=3&reviewer=lochan")[1]["items"][0]
    assert call(api, "GET", "/api/validation/compare", query=f"item={p3['item_id']}&reviewer=lochan")[0] == "403 Forbidden"


def test_posting_text_never_served_for_protected_or_test(api):
    for pid in ("p44", "p47", "p3", "p5"):
        with pytest.raises(ValueError):
            api.description(pid)
    s, d = call(api, "GET", "/api/validation/posting", query="part=1&item=nope")
    assert s == "400 Bad Request"


# 20 · 21
def test_dashboard_navigation_and_persistence(api, cfg):
    s, html = call(api, "GET", "/validation")
    assert s == "200 OK"
    for tab in ("Part 1: Disagreements", "Part 2: Agreements", "Part 3: Full Postings", "Team Adjudication",
                "Progress &amp; Reports", "Source Versions"):
        assert tab in html
    assert 'href="/validation"' in (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert "ValidationAPI" in (ROOT / "app" / "server.py").read_text(encoding="utf-8")
    item = call(api, "GET", "/api/validation/items", query="part=1&reviewer=priyanka")[1]["items"][0]
    s, _ = call(api, "POST", "/api/validation/review", {"reviewer": "priyanka", "part": 1, "item_id": item["item_id"],
                                                        "action": "draft", "data": {"decision": "UNSURE"}})
    assert s == "200 OK"
    from validation_api import ValidationAPI
    fresh = ValidationAPI(Config(cfg.root, cfg.data))  # "restart"
    again = call(fresh, "GET", "/api/validation/items", query="part=1&reviewer=priyanka")[1]["items"]
    assert next(i for i in again if i["item_id"] == item["item_id"])["status"] == "IN_REVIEW"
    s, st = call(fresh, "GET", "/api/validation/status")
    assert s == "200 OK" and st["summary"]["team"]["per_reviewer"]["priyanka"]["1"]["drafts"] == 1
    s, d = call(fresh, "POST", "/api/validation/export", {})
    assert s == "200 OK" and all((cfg.root / f).is_file() for f in d["files"])


# 22 · 23
def test_outputs_are_repo_relative_and_git_trackable(api, cfg):
    for f in cfg.manifests_dir.glob("part?_v?.json"):
        m = json.loads(f.read_text(encoding="utf-8"))
        assert str(cfg.root) not in json.dumps(m)
        paths = [k for k in m["sources"] if k != "settings"] + [m["rules"]["file"]]
        assert paths and all("\\" not in p and not Path(p).is_absolute() for p in paths)
    if shutil.which("git") is None:
        pytest.skip("git not installed")
    shared = ["data/validation/manifests/part1_v1.json", "data/validation/manifests/part2_v2.json",
              "data/validation/adjudication/lochan.jsonl", "data/validation/approved_versions/x/changes.csv",
              "reports/validation/validation_progress_x.md", "data/validation/config/validation_config.yaml",
              "data/validation/reviews/lochan/.gitkeep",
              "reports/intrusion_v2/run/questions.json", "reports/intrusion_v2/run/manifest.json"]
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--no-index", *shared], capture_output=True, text=True)
    assert r.stdout.strip() == "", f"ignored by .gitignore: {r.stdout}"
    # blind material: answer keys and reviewer responses must never be committable by accident
    private = ["data/validation/manifests/part2_v1_key.json", "data/validation/manifests/part2_v9_key.json",
               "data/validation/reviews/lochan/events.jsonl", "data/validation/reviews/priyanka/events.jsonl",
               "reports/intrusion_v2/run/responses/lochan.csv", "reports/intrusion_v2/run/submitted/lochan.json",
               "data/interim/intrusion_v2/run/answer_key.json"]
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--no-index", *private], capture_output=True, text=True)
    assert sorted(r.stdout.split()) == sorted(private), f"NOT ignored: {set(private) - set(r.stdout.split())}"


def test_summary_counts(api, cfg):
    s = reporting.summary(cfg)
    assert s["parts"][1]["total_disagreements"] == 4 and s["parts"][2]["sampled"] == 5 and s["parts"][3]["selected_postings"] == 2


# ---------- blind scoring: reveals and post-reveal amendments (2026-11-02) ----------
def _p2(api, reviewer, item, action, decision, reason=""):
    data = {"decision": decision, "explanation": "x" if decision != "VALID_SKILL" else ""}
    return call(api, "POST", "/api/validation/review", {"reviewer": reviewer, "part": 2, "item_id": item, "action": action,
                                                        "data": data, "amend_reason": reason})


def test_reveal_is_logged_once_and_needs_submission(api, cfg):
    item = call(api, "GET", "/api/validation/items", query="part=2&reviewer=lochan")[1]["items"][0]["item_id"]
    assert call(api, "GET", "/api/validation/reveal", query=f"item={item}&reviewer=lochan")[0] == "403 Forbidden"
    assert not any(e["action"] == "reveal" for e in ReviewStore(cfg).events("lochan")[0])  # refused = not logged
    _p2(api, "lochan", item, "submit", "VALID_SKILL")
    for _ in range(2):
        assert call(api, "GET", "/api/validation/reveal", query=f"item={item}&reviewer=lochan")[0] == "200 OK"
    reveals = [e for e in ReviewStore(cfg).events("lochan")[0] if e["action"] == "reveal"]
    assert len(reveals) == 1 and reveals[0]["item_id"] == item and reveals[0]["via"] == "reveal"
    assert call(api, "POST", "/api/validation/review", {"reviewer": "lochan", "part": 2, "item_id": item,
                                                        "action": "reveal", "data": {}})[0] == "400 Bad Request"


def test_post_reveal_amendment_never_changes_official_scores(api, cfg):
    items = [i["item_id"] for i in call(api, "GET", "/api/validation/items", query="part=2&reviewer=lochan")[1]["items"]]
    a, b = items[0], items[1]
    # a: amended BEFORE any reveal -> the amendment is the official (blind) result
    _p2(api, "lochan", a, "submit", "VALID_SKILL")
    _p2(api, "lochan", a, "amend", "INVALID_SKILL", "re-read rule A")
    # b: amended AFTER the reveal -> kept in the log, but the submitted version stays official
    _p2(api, "lochan", b, "submit", "VALID_SKILL")
    before = reporting.summary(cfg)["parts"][2]
    assert call(api, "GET", "/api/validation/reveal", query=f"item={b}&reviewer=lochan")[0] == "200 OK"
    _p2(api, "lochan", b, "amend", "INVALID_SKILL", "saw the reference")
    st = ReviewStore(cfg).state("lochan", "part2_v1")
    assert st[a]["official"]["decision"] == "INVALID_SKILL" and st[a]["official_version"] == 2
    assert st[b]["latest"]["decision"] == "INVALID_SKILL"  # the reviewer still sees their newest version
    assert st[b]["official"]["decision"] == "VALID_SKILL" and st[b]["official_version"] == 1
    assert [v["post_reveal"] for v in st[b]["versions"]] == [False, True]  # auditable
    after = reporting.summary(cfg)["parts"][2]
    assert after["invalid_labels_found"] == before["invalid_labels_found"] == 1  # only item a
    cases = {c["item_id"]: c for c in adjudication.build_cases(cfg)}
    assert a in cases and b not in cases  # b's blind decision proposes nothing
    shown = call(api, "GET", "/api/validation/items", query="part=2&reviewer=lochan")[1]["items"]
    assert next(i for i in shown if i["item_id"] == b)["versions"][1]["post_reveal"] is True


def test_part3_compare_and_unredacted_cases_count_as_reveal(api, cfg):
    p3 = call(api, "GET", "/api/validation/items", query="part=3&reviewer=lochan")[1]["items"][0]
    text = DESC[p3["posting_id"]]
    word = text.split()[0]
    sub = {"reviewer": "lochan", "part": 3, "item_id": p3["item_id"], "action": "submit",
           "data": {"skills": [{"skill": word, "evidence": word, "confidence": "high"}]}}
    assert call(api, "POST", "/api/validation/review", sub)[0] == "200 OK"
    assert call(api, "GET", "/api/validation/compare", query=f"item={p3['item_id']}&reviewer=lochan")[0] == "200 OK"
    st = ReviewStore(cfg).state("lochan", "part3_v1")[p3["item_id"]]
    assert st["revealed"]
    item2 = call(api, "GET", "/api/validation/items", query="part=2&reviewer=dhanush")[1]["items"][0]["item_id"]
    _p2(api, "lochan", item2, "submit", "INVALID_SKILL")           # makes a Part 2 case
    _p2(api, "dhanush", item2, "submit", "VALID_SKILL")
    call(api, "GET", "/api/validation/cases", query="reviewer=dhanush")  # dhanush now sees lochan's decision
    assert ReviewStore(cfg).state("dhanush", "part2_v1")[item2]["revealed"]
    assert not ReviewStore(cfg).state("priyanka", "part2_v1")  # a reviewer who saw nothing logs nothing


def test_rules_change_makes_manifests_stale(cfg):
    m1, _ = manifests.ensure(cfg, 3)  # part 3 has no model runs: only gold, split, settings and rules
    assert manifests.stale_sources(cfg, m1) == []
    cfg.p("rules").write_text("# rules\n- new rule\n", encoding="utf-8")
    assert manifests.stale_sources(cfg, m1) == ["data/gold/LABELING_RULES.md"]
    with pytest.raises(manifests.StaleSources):
        manifests.ensure(cfg, 3)
    m2, st = manifests.ensure(cfg, 3, new_version=True)
    assert st == "new_version" and m2["items"] == m1["items"] and m2["rules"]["sha256"] != m1["rules"]["sha256"]
    assert (cfg.manifests_dir / "part3_v1.json").is_file() and manifests.stale_sources(cfg, m2) == []
