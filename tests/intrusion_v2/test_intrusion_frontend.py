"""Intrusion v2 reviewer page + API (app/intrusion_api.py) on a synthetic taxonomy (tmp_path).

No database, no network, no real responses: answers here are synthetic and written only under tmp_path.
The one test that touches the real repository only READS the frozen questions.json (never responses or the key).
"""
import csv
import io
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import intrusion_api as ia  # noqa: E402
import intrusion_v2 as iv  # noqa: E402
from test_intrusion_v2 import RUN, expected, synthetic_snapshot  # noqa: E402


def call(app, method, path, body=None, query=""):
    raw = json.dumps(body).encode() if body is not None else b""
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query, "CONTENT_LENGTH": str(len(raw)),
           "wsgi.input": io.BytesIO(raw)}
    got = {}
    out = b"".join(app(env, lambda s, h: got.update(s=s, h=dict(h))))
    is_json = got["h"].get("Content-Type") == "application/json"
    return got["s"], (json.loads(out) if is_json else out.decode())


@pytest.fixture
def root(tmp_path):
    iv.make(tmp_path, synthetic_snapshot(), seed=7, run_id=RUN, expected=expected(synthetic_snapshot()))
    return tmp_path


@pytest.fixture
def api(root):
    return ia.IntrusionAPI(root, RUN)


def answer(api, reviewer, qid, letter, note=None):
    body = {"reviewer": reviewer, "question_id": qid, "answer": letter}
    if note is not None:
        body["note"] = note
    return call(api, "POST", "/api/intrusion-v2/answer", body)


def qids(api):
    return [q["question_id"] for q in call(api, "GET", "/api/intrusion-v2/questions")[1]["questions"]]


def rows(root, reviewer):
    with (iv.out_dir(root, RUN) / "responses" / f"{reviewer}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------- questions ----------
def test_frozen_repository_questions_load_unchanged():
    """The real frozen file: 24 questions x 5 options, byte-identical to the hash in the tracked manifest."""
    out = iv.out_dir(ROOT, iv.RUN_ID)
    if not (out / "questions.json").exists():
        pytest.skip("frozen intrusion v2 questions not in this checkout")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert iv.sha256_bytes((out / "questions.json").read_bytes()) == manifest["questions_sha256"]
    d = ia.IntrusionAPI(ROOT).questions()
    assert len(d["questions"]) == 24 and len({q["question_id"] for q in d["questions"]}) == 24
    assert all(sorted(q) == ["options", "question_id"] and sorted(q["options"]) == list("ABCDE")
               and all(q["options"][x].strip() for x in "ABCDE") for q in d["questions"])


def test_questions_endpoint_is_blind(api, root):
    s, d = call(api, "GET", "/api/intrusion-v2/questions")
    assert s == "200 OK" and len(d["questions"]) == 24
    assert all(len(q["options"]) == 5 for q in d["questions"])
    on_disk = json.loads((iv.out_dir(root, RUN) / "questions.json").read_text())["questions"]
    assert [q["options"] for q in d["questions"]] == [q["options"] for q in on_disk]  # order and options unchanged


def test_answer_key_never_returned(api, root):
    key = json.loads(iv.key_path(root, RUN).read_text())["key"]
    secrets = {k["topic_id"] for k in key.values()} | {k["topic_label"] for k in key.values()} | \
              {k["stratum"] for k in key.values()} | {"intruder", "answer_key", "topic_id", "stratum", "genuine"}
    qs = qids(api)
    answer(api, "lochan", qs[0], "B")
    bodies = [call(api, "GET", "/api/intrusion-v2/questions")[1], call(api, "GET", "/api/intrusion-v2/responses", query="reviewer=lochan")[1],
              call(api, "GET", "/api/intrusion-v2/progress", query="reviewer=lochan")[1], call(api, "GET", "/api/intrusion-v2/team")[1],
              answer(api, "lochan", qs[1], "C")[1]]
    text = json.dumps(bodies)
    assert not [s for s in secrets if s in text]
    for path in ("score", "key", "answer_key", "../../data/interim/intrusion_v2/synthetic_run/answer_key.json"):
        assert call(api, "GET", f"/api/intrusion-v2/{path}")[0] == "404 Not Found"


def test_page_has_no_answer_material():
    page = (ROOT / "app" / "static" / "intrusion_v2.html").read_text(encoding="utf-8")
    js = (ROOT / "app" / "static" / "intrusion_v2.js").read_text(encoding="utf-8")
    assert "Skill Pipeline — Intrusion v2" in page
    assert not any(w in (page + js).lower() for w in ("answer_key", "intruder", "topic_id", "stratum", "localstorage"))


# ---------- persistence ----------
def test_answers_persist_across_refresh_and_update_in_place(api, root):
    q = qids(api)
    assert answer(api, "lochan", q[0], "a", note="first try")[0] == "200 OK"  # lower case accepted, stored upper
    assert answer(api, "lochan", q[0], "D")[1]["answer"] == "D"              # change = update, note kept
    fresh = ia.IntrusionAPI(root, RUN)                                          # "page refresh / server restart"
    d = call(fresh, "GET", "/api/intrusion-v2/responses", query="reviewer=lochan")[1]
    assert d["answers"] == {q[0]: "D"} and d["notes"] == {q[0]: "first try"} and d["answered"] == 1
    r = rows(root, "lochan")
    assert len(r) == 24 and [x["question_id"] for x in r].count(q[0]) == 1      # no duplicate rows
    assert list(r[0]) == ia.HEADER                                              # exact existing schema
    assert iv.validate(root, RUN, "lochan")[1] == []                            # the scorer's checks still pass


def test_reviewers_are_separate(api, root):
    q = qids(api)
    answer(api, "lochan", q[0], "A")
    answer(api, "priyanka", q[0], "E")
    pr = call(api, "GET", "/api/intrusion-v2/responses", query="reviewer=priyanka")[1]
    assert pr["answers"] == {q[0]: "E"} and "lochan" not in json.dumps(pr)
    assert call(api, "GET", "/api/intrusion-v2/responses", query="reviewer=dhanush")[1]["answers"] == {}
    assert {r["reviewer"] for r in rows(root, "priyanka")} == {"priyanka"}


def test_missing_response_file_is_recreated_from_frozen_questions(api, root):
    p = iv.out_dir(root, RUN) / "responses" / "dhanush.csv"
    blank = p.read_bytes()
    p.unlink()  # a teammate's clone: responses/ is gitignored
    assert call(api, "GET", "/api/intrusion-v2/responses", query="reviewer=dhanush")[0] == "200 OK"
    assert p.read_bytes() == blank


# ---------- validation and safety ----------
@pytest.mark.parametrize("body", [
    {"reviewer": "mallory", "question_id": "Q01", "answer": "A"},
    {"reviewer": "../../etc/passwd", "question_id": "Q01", "answer": "A"},
    {"reviewer": "lochan", "question_id": "Q99", "answer": "A"},
    {"reviewer": "lochan", "question_id": "../questions", "answer": "A"},
    {"reviewer": "lochan", "question_id": "Q01", "answer": "F"},
    {"reviewer": "lochan", "question_id": "Q01", "answer": ""},
    {"reviewer": "lochan", "question_id": "Q01", "answer": "AB"},
])
def test_invalid_input_rejected(api, root, body):
    before = (iv.out_dir(root, RUN) / "responses" / "lochan.csv").read_bytes()
    s, d = call(api, "POST", "/api/intrusion-v2/answer", body)
    assert s == "400 Bad Request" and "error" in d
    assert (iv.out_dir(root, RUN) / "responses" / "lochan.csv").read_bytes() == before
    assert sorted(p.name for p in (iv.out_dir(root, RUN) / "responses").glob("*.csv")) == ["dhanush.csv", "lochan.csv", "priyanka.csv"]


def test_get_with_bad_reviewer_rejected(api):
    assert call(api, "GET", "/api/intrusion-v2/responses", query="reviewer=../x")[0] == "400 Bad Request"
    assert call(api, "GET", "/api/intrusion-v2/responses")[0] == "400 Bad Request"


def test_interrupted_save_leaves_file_intact(api, root, monkeypatch):
    q = qids(api)
    answer(api, "lochan", q[0], "B")
    path = iv.out_dir(root, RUN) / "responses" / "lochan.csv"
    before = path.read_bytes()

    def crash(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(ia.os, "replace", crash)
    s, d = answer(api, "lochan", q[1], "C")
    assert s == "500 Internal Server Error" and d["error"].startswith("save failed")
    assert path.read_bytes() == before                                     # old file untouched
    assert not list(path.parent.glob(".lochan.*.tmp"))                     # no temp file left behind
    monkeypatch.undo()
    assert answer(api, "lochan", q[1], "C")[0] == "200 OK"                 # works again afterwards


def test_concurrent_saves_do_not_corrupt(api, root):
    q = qids(api)
    errors = []

    def worker(i):
        s, _ = answer(api, "lochan", q[i], "ABCDE"[i % 5])
        if s != "200 OK":
            errors.append(s)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(q))] + \
              [threading.Thread(target=worker, args=(0,)) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    answers, problems, missing = iv.validate(root, RUN, "lochan")
    assert problems == [] and missing == [] and len(rows(root, "lochan")) == 24
    assert answers == {qid: "ABCDE"[i % 5] for i, qid in enumerate(q)}


# ---------- submission ----------
def test_submit_requires_all_answers_and_confirmation(api):
    q = qids(api)
    answer(api, "lochan", q[0], "A")
    assert call(api, "POST", "/api/intrusion-v2/submit", {"reviewer": "lochan", "confirm": True})[0] == "400 Bad Request"
    for i, qid in enumerate(q):
        answer(api, "lochan", qid, "ABCDE"[i % 5])
    assert call(api, "POST", "/api/intrusion-v2/submit", {"reviewer": "lochan"})[0] == "400 Bad Request"  # no confirm


def test_submit_locks_and_existing_scorer_still_works(api, root):
    q = qids(api)
    for r in iv.REVIEWERS:
        for i, qid in enumerate(q):
            answer(api, r, qid, "ABCDE"[(i + len(r)) % 5])
        s, d = call(api, "POST", "/api/intrusion-v2/submit", {"reviewer": r, "confirm": True})
        assert s == "200 OK" and d["answered"] == 24 and "score" not in json.dumps(d).lower()
        if r == "lochan":  # not everyone yet: still no score anywhere
            assert call(api, "GET", "/api/intrusion-v2/team")[1] == {
                "submitted": {"lochan": True, "priyanka": False, "dhanush": False}, "all_submitted": False}
    path = iv.out_dir(root, RUN) / "responses" / "lochan.csv"
    before = path.read_bytes()
    s, d = answer(api, "lochan", q[0], "E")
    assert s == "409 Conflict" and d["locked"] and path.read_bytes() == before
    assert call(api, "POST", "/api/intrusion-v2/submit", {"reviewer": "lochan", "confirm": True})[0] == "409 Conflict"
    assert call(api, "GET", "/api/intrusion-v2/progress", query="reviewer=lochan")[1]["submitted"] is True
    result = iv.score(root, RUN)  # the CLI scorer accepts what the page submitted (hash checks included)
    assert result["final"] and result["correctness"]["overall"]["n"] == 72


# ---------- route in the dashboard server ----------
def test_validation_route_renders_intrusion_v2_without_supabase(monkeypatch):
    import server  # app/server.py (importing it loads .env; the settings below override for this test)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("UI_PASSWORD", raising=False)
    app = server.App()
    s, page = call(app, "GET", "/validation")
    assert s == "200 OK" and "Skill Pipeline — Intrusion v2" in page
    assert "Gold Validation" not in page and "Agreements" not in page and "adjudicat" not in page.lower()
    assert app.con is None  # no database connection was opened
    if (iv.out_dir(ROOT, iv.RUN_ID) / "questions.json").exists():
        s, d = call(app, "GET", "/api/intrusion-v2/questions")
        assert s == "200 OK" and len(d["questions"]) == 24 and app.con is None
    assert call(app, "GET", "/static/intrusion_v2.js")[0] == "200 OK"
    assert call(app, "GET", "/api/validation/status")[0] == "200 OK"  # Gold Validation API kept


def test_validation_route_needs_login_when_password_set(monkeypatch):
    import server
    monkeypatch.setenv("UI_PASSWORD", "synthetic-test-password")
    app = server.App()
    assert call(app, "GET", "/validation")[0] == "303 See Other"
    assert call(app, "GET", "/api/intrusion-v2/questions")[0] == "401 Unauthorized"
