"""Sprint 4 step 3: Anthropic (Claude Sonnet 5.5) topic naming on the synthetic taxonomy, with a fake SDK client that
returns real anthropic Message objects (via messages.with_raw_response) and raises real SDK errors. Also pins the
Groq request construction and cache keys (golden values recorded before the provider refactor). No network.

    python -m pytest tests/sprint4 -q
"""
import csv
import hashlib
import json
import random
import shutil
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from anthropic.types import Message

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import topic_naming as tn  # noqa: E402
from test_topic_features import EXP, RUN  # noqa: E402
from test_topic_naming import IDS, KEY, TODAY, Clock, Session, root, run  # noqa: E402,F401  (root is a fixture)

A = tn.make_provider("anthropic")
SECRET = "sk-ant-api03-TESTSECRETtestsecret1234567890"
USAGE = {"input_tokens": 1500, "output_tokens": 120, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
         "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
         "service_tier": "standard", "inference_geo": "global"}            # $0.0030 + $0.0012 = $0.0042


def rfc(clock, s):
    return datetime.fromtimestamp(clock.t + s, timezone.utc).isoformat().replace("+00:00", "Z")


def headers(clock, req_rem=49, in_rem=28000, out_rem=7000, reset=20):
    return {"anthropic-ratelimit-requests-limit": "50", "anthropic-ratelimit-requests-remaining": str(req_rem),
            "anthropic-ratelimit-requests-reset": rfc(clock, reset),
            "anthropic-ratelimit-input-tokens-limit": "30000", "anthropic-ratelimit-input-tokens-remaining": str(in_rem),
            "anthropic-ratelimit-input-tokens-reset": rfc(clock, reset),
            "anthropic-ratelimit-output-tokens-limit": "8000", "anthropic-ratelimit-output-tokens-remaining": str(out_rem),
            "anthropic-ratelimit-output-tokens-reset": rfc(clock, reset), "request-id": "req_ok"}


def answer(body, conf="medium"):
    p = json.loads(body["messages"][0]["content"])
    return json.dumps({"provisional_name": f"Claude {p['topic_id']} Area", "description": "Shared competency.",
                       "supporting_skills": p["representative_skills"][:3], "confidence": conf, "confidence_reason": "Fits."})


class Raw:
    def __init__(self, msg, hdr):
        self._m, self.headers = msg, hdr

    def parse(self):
        return self._m


def ok(body, clock, usage=USAGE, model="claude-sonnet-5-5", stop="end_turn", content=None, hdr=None):
    msg = Message.model_validate({"id": "msg_1", "type": "message", "role": "assistant", "model": model,
                                  "content": [{"type": "text", "text": answer(body) if content is None else content}],
                                  "stop_reason": stop, "stop_sequence": None, "usage": usage})
    return Raw(msg, headers(clock) if hdr is None else hdr)


def err(status, clock, etype="rate_limit_error", message="rate limited", retry_after=None, details=None, cls=None):
    h = {"request-id": "req_err", **headers(clock)}
    if retry_after is not None:
        h["retry-after"] = str(retry_after)
    body = {"type": "error", "error": {"type": etype, "message": message, **({"details": details} if details else {})}}
    resp = httpx2.Response(status, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"), headers=h)
    cls = cls or {429: anthropic.RateLimitError, 400: anthropic.BadRequestError, 500: anthropic.InternalServerError}.get(
        status, anthropic.APIStatusError)
    return cls(message, response=resp, body=body)


class FakeAnthropic:
    """client.messages.with_raw_response.create(**body) and client.models.retrieve(id), like the SDK."""

    def __init__(self, clock, script=None, model_ok=True):
        self.clock, self.calls, self.model_ok = clock, [], model_ok
        self.script = script or (lambda body, n, c: ok(body, c))
        self.messages = SimpleNamespace(with_raw_response=SimpleNamespace(create=self._create))
        self.models = SimpleNamespace(retrieve=self._retrieve)

    def _create(self, **body):
        self.calls.append(body)
        r = self.script(body, len(self.calls), self.clock)
        if isinstance(r, Exception):
            raise r
        return r

    def _retrieve(self, model):
        if not self.model_ok:
            raise err(404, self.clock, "not_found_error", "model not found", cls=anthropic.NotFoundError)
        return SimpleNamespace(id=model)


@pytest.fixture
def aroot(root):
    for f in (tn.pricing_path, tn.rate_limits_path):
        f(root, A).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f(ROOT, A), f(root, A))
    return root


def arun(root, script=None, ids=IDS, scope="pilot", name="a1", clock=None, auth="test fixture: authorised", **kw):
    if not tn.prepare_dir(root, RUN, prov=A).exists():
        tn.prepare(root, RUN, EXP, pilot_per=0, today=TODAY, prov=A)
    clock = clock or Clock()
    client = FakeAnthropic(clock, script)
    out = tn.generate(tn.AnthropicBackend(A.model, client), ids, scope=scope, root=root, run_id=RUN, expected=EXP,
                      naming_run_id=name, today=TODAY, clock=clock, sleep=clock.sleep, rng=random.Random(0), prov=A,
                      key_authorization=auth, **kw)
    return (*out, client, clock)


def rows_of(d, name):
    return list(csv.DictReader((d / name).open(encoding="utf-8")))


# ---------- Groq is unchanged ----------
def test_groq_request_and_cache_key_are_byte_identical():
    payload = {"topic_id": "T9999", "size": {"assigned_members": 3, "weak_members_not_shown": 0}, "cohesion_band": "high",
               "transversal": False, "representative_skills": ["a", "b", "c"], "additional_members": [],
               "reference_hints": [], "neighbour_topics": []}
    q = tn.build_request("SYSTEM PROMPT JSON", payload)                 # default provider = Groq
    assert q["cache_key"] == "a94485152f7ab8e7998cd125b8d4bcb6857f0600a7599ae6a71628075f9737c2"
    assert tn.sha(json.dumps(q["body"], sort_keys=True)) == "11f1983c3bebb64abfd72f58a4bb11ec6e396543782e3edb7e57fe5f5ea8df05"
    assert tn.build_request("SYSTEM PROMPT JSON", payload, tn.GROQ) == q
    assert tn.request_settings() == {"provider": "groq", "model": "qwen/qwen3.8-27b", "temperature": 0,
                                     "max_completion_tokens": 512, "reasoning_effort": "none", "reasoning_format": "hidden",
                                     "response_format": {"type": "json_object"}}
    assert tn.prepare_dir(ROOT, RUN).name == "prepare_topic_naming_v1_qwen_qwen3.8-27b"
    assert tn.cache_dir(ROOT).parts[-3:] == ("cache", "topic_naming", "groq")


# ---------- Anthropic request ----------
def test_anthropic_request_shape_and_validation(aroot):
    res = tn.prepare(aroot, RUN, EXP, pilot_per=0, today=TODAY, prov=A, write=False)
    assert res["problems"] == {}
    q, rec = res["requests"][2], res["records"][2]
    b = q["body"]
    assert set(b) == {"model", "max_tokens", "system", "messages", "thinking", "output_config"} and b["model"] == "claude-sonnet-5-5"
    assert b["thinking"] == {"type": "between_tools"} and b["max_tokens"] == 1024
    fmt = b["output_config"]["format"]
    assert fmt["type"] == "json_schema" and fmt["schema"]["required"] == list(tn.OUTPUT_KEYS)
    assert fmt["schema"]["additionalProperties"] is False and b["system"] == (ROOT / "prompts/topic_naming_v1.txt").read_text()
    assert json.loads(b["messages"][0]["content"]) == rec["payload"]
    assert not {"temperature", "top_p", "top_k", "fallbacks", "metadata", "stream", "inference_geo", "service_tier"} & set(b)
    groq_q = tn.build_request(b["system"], rec["payload"])
    assert q["cache_key"] != groq_q["cache_key"]
    assigned = {m for m in rec["payload"]["representative_skills"] + rec["payload"]["additional_members"]}
    assert tn.validate_request(q, rec, assigned, set(IDS), prov=A) == []
    for extra in ({"temperature": 0}, {"fallbacks": "default"}, {"model": "claude-opus-5-5"}):
        bad = json.loads(json.dumps(q))
        bad["body"].update(extra)
        assert tn.validate_request(bad, rec, assigned, set(IDS), prov=A), extra
    with pytest.raises(ValueError, match="unsupported Anthropic model"):
        tn.make_provider("anthropic", "claude-opus-5-5")
    assert tn.prepare_dir(aroot, RUN, prov=A).name == "prepare_topic_naming_v1_anthropic_claude-sonnet-5-5"


def test_prepare_makes_no_api_call(aroot, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("SDK client created during prepare")
    monkeypatch.setattr(anthropic, "Anthropic", boom)
    res = tn.prepare(aroot, RUN, EXP, pilot_per=0, today=TODAY, prov=A, write=False)
    e = res["manifest"]["offline_estimate"]
    assert e["pricing_error"] is None and e["rate_limits_error"] is None and e["full_run"]["quota"]["plan"] == "conservative"


# ---------- pricing and token accounting ----------
def test_pricing_snapshot_and_costs():
    pr = tn.load_pricing(tn.pricing_path(ROOT, A), TODAY, A)
    assert pr["rates"] == {"input": Decimal("2.00"), "output": Decimal("10.00"), "cache_write_5m": Decimal("2.50"),
                           "cache_write_1h": Decimal("4.00"), "cache_read": Decimal("0.10")}
    c = A.price_usage(USAGE, pr)
    assert (c["estimated_input_cost"], c["estimated_output_cost"], c["estimated_cache_cost"], c["estimated_cost"]) == \
        (Decimal("0.003"), Decimal("0.0012"), Decimal(0), Decimal("0.0042"))
    u = dict(USAGE, input_tokens=1000, output_tokens=100, cache_creation_input_tokens=2000, cache_read_input_tokens=3000,
             cache_creation={"ephemeral_5m_input_tokens": 1500, "ephemeral_1h_input_tokens": 500})
    c = A.price_usage(u, pr)
    assert c["estimated_cache_cost"] == Decimal("0.00605") and c["estimated_cost"] == Decimal("0.00905")
    assert (c["cache_creation_input_tokens"], c["cache_read_input_tokens"], c["total_tokens"]) == (2000, 3000, 6100)
    assert A.usage_tokens(u) == (3000, 100)                              # ITPM counts input + cache writes
    for bad, why in ((dict(USAGE, server_tool_use={"web_search_requests": 1}), "server tool"),
                     (dict(USAGE, service_tier="priority"), "service tier"), (dict(USAGE, inference_geo="us"), "inference_geo"),
                     (dict(USAGE, cache_creation_input_tokens=10, cache_creation=None), "breakdown")):
        r = A.price_usage(bad, pr)
        assert r["estimate_status"] == "unpriced" and why in r["estimate_note"] and r["estimated_cost"] is None
    assert A.price_usage(None, pr)["estimate_status"] == "missing_usage"
    with pytest.raises(ValueError, match="not anthropic/claude-sonnet-5-5"):
        tn.load_pricing(tn.pricing_path(ROOT), TODAY, A)                 # Groq file offered for Anthropic


# ---------- rate limits ----------
def test_anthropic_headers_and_per_minute_limiter():
    c = Clock()
    h = tn.read_anthropic_rate_headers(headers(c, req_rem=10, in_rem=1000, out_rem=500, reset=30), now=c.t)
    assert (h["limit_requests_minute"], h["remaining_input_tokens_minute"], h["limit_output_tokens_minute"]) == (10 * 5, 1000, 8000)
    assert h["reset_input_tokens_minute_s"] == pytest.approx(30, abs=1) and h["remaining_requests_day"] is None
    cfg = tn.load_rate_limits(tn.rate_limits_path(ROOT, A), None, TODAY, A)
    assert cfg["plan"] == "conservative" and cfg["limits"]["rpm"] == 50 and cfg["limits"]["input_tpm"] == 30000
    lim = tn.RateLimiter(cfg["limits"], cfg["safety"], c, c.sleep, header_reader=A.read_rate_headers)
    lim.record(1500, 120, headers(c, in_rem=1000, reset=30))
    assert lim.header_adopted == {"rpm": 50, "input_tpm": 30000, "output_tpm": 8000}
    action, wait, why, src = lim.check(2000, 1024)
    assert (action, src) == ("wait", "provider_headers") and "ITPM (provider-reported)" in why and wait == pytest.approx(30, abs=1)
    c.t += 31
    assert lim.check(2000, 1024)[0] == "go"
    rep = lim.report()["provider_reported"]
    assert rep["input_tokens_per_minute"]["remaining"] == 1000 and rep["requests_per_minute"]["limit"] == 50
    assert tn.read_rate_headers({"x-ratelimit-limit-requests": "1000"})["limit_requests_day"] == 1000   # Groq reader intact


# ---------- generation ----------
def test_generate_records_every_required_field(aroot):
    d, m, rows, cs, rs, client, clock = arun(aroot, secrets=[SECRET], name=None)
    assert len(client.calls) == 3 and m["run_status"] == "completed" and m["result_problems"] == []
    assert m["provider"] == "anthropic" and m["model"] == "claude-sonnet-5-5" and m["key_authorization"] == "test fixture: authorised"
    assert m["model_settings"]["sampling"] is None and m["model_settings"]["fallback"] is None
    c = rows_of(d, "cost_report.csv")
    for r, body in zip(c, client.calls):
        assert (r["provider"], r["requested_model"], r["served_model"], r["prompt_version"]) == \
            ("anthropic", "claude-sonnet-5-5", "claude-sonnet-5-5", "topic_naming_v1")
        assert r["payload_sha256"] == tn.sha(body["messages"][0]["content"]) and float(r["latency_ms"]) >= 0
        assert (r["input_tokens"], r["output_tokens"], r["cache_creation_input_tokens"], r["cache_read_input_tokens"]) == \
            ("1500", "120", "0", "0")
        assert (r["estimated_input_cost_usd"], r["estimated_output_cost_usd"], r["estimated_cache_cost_usd"],
                r["estimated_cost_usd"]) == ("0.00300000", "0.00120000", "0.00000000", "0.00420000")
        assert r["validation_status"] == "valid" and r["http_status"] == "200" and r["retry_count"] == "0"
        assert r["billed_cost_usd"] == "" and r["provider_remaining_requests_minute"] == "49"
    assert c[-1]["cumulative_estimated_cost_usd"] == "0.01260000" and cs["cost_usd"]["estimated_total"] == "0.01260000"
    assert cs["provider"] == "anthropic" and cs["latency_ms"]["n"] == 3 and cs["tokens"]["cache_creation_input"] == 0
    reqs = [json.loads(x) for x in (d / "raw_requests.jsonl").read_text().splitlines()]
    resps = [json.loads(x) for x in (d / "raw_responses.jsonl").read_text().splitlines()]
    assert len(reqs) == 3 and all(q["body"]["model"] == "claude-sonnet-5-5" for q in reqs) and all("latency_ms" in x for x in resps)
    assert rs["limits_from_headers"] == {"rpm": 50, "input_tpm": 30000, "output_tpm": 8000} and rs["provider"] == "anthropic"
    assert len(list(tn.cache_dir(aroot, A).glob("*.json"))) == 3 and not tn.cache_dir(aroot).exists()   # Groq cache untouched
    assert all(r["provider"] == "anthropic" for r in rows) and "claude-sonnet-5-5_pilot" in m["run_id"]
    for f in (*d.iterdir(), *(tn.tracked_dir(aroot, RUN) / m["run_id"]).iterdir()):
        assert SECRET not in f.read_text() and "sk-ant-" not in f.read_text(), f


def test_key_authorization_required(aroot):
    with pytest.raises(SystemExit, match="key-authorization"):
        arun(aroot, auth="")


def test_retries_for_429_and_5xx_are_bounded_and_logged(aroot):
    plan = {1: (429, 2), 2: (529, None), 3: (500, None), 4: (502, None), 5: (503, None)}

    def script(body, n, c):
        if n in plan:
            status, ra = plan[n]
            return err(status, c, "overloaded_error" if status == 529 else "api_error", f"HTTP {status}", retry_after=ra)
        return ok(body, c)
    d, m, rows, cs, rs, client, clock = arun(aroot, script, ids=["T0002"])
    assert rows[0]["status"] == "failed" and len(client.calls) == tn.MAX_ATTEMPTS        # bounded: 5 attempts, all errors
    c = rows_of(d, "cost_report.csv")
    assert [r["http_status"] for r in c] == ["429", "529", "500", "502", "503"]
    assert [r["error_class"] for r in c] == ["rate_limit"] + ["transient"] * 4 and all(r["latency_ms"] for r in c)
    assert clock.slept[0] == 2.0 and len(clock.slept) == 4 and rs["http_errors"]["http_529"] == 1
    d2, m2, rows2, *_ = arun(aroot, lambda body, n, c: err(529, c, "overloaded_error") if n == 1 else ok(body, c),
                             ids=["T0002"], name="a2")
    assert rows2[0]["status"] == "ok" and rows2[0]["attempts"] == 2


@pytest.mark.parametrize("make", [
    lambda c: err(429, c, "rate_limit_error", "You have reached your API usage limits ...",
                  details={"error_code": "enforced_spend_limit_reached"}),
    lambda c: err(400, c, "invalid_request_error", "You have reached your specified API usage limits. Access resumes ...")])
def test_spend_limits_stop_without_retry(aroot, make):
    d, m, rows, cs, rs, client, clock = arun(aroot, lambda body, n, c: make(c))
    assert len(client.calls) == 1 and clock.slept == [] and m["run_status"] == "spend_limit_reached"
    assert [r["status"] for r in rows] == ["failed", "not_attempted", "not_attempted"]
    assert rows_of(d, "cost_report.csv")[0]["error_class"] == "quota" and rs["spend_limit"]["topic_id"] == "T0000"
    assert rs["resume"]["resume_possible"] is False and "spend_limit_stop" in [r["event"] for r in rows_of(d, "rate_limit_report.csv")]


def test_config_error_and_model_mismatch_stop(aroot):
    d, m, *_ = arun(aroot, lambda body, n, c: err(400, c, "invalid_request_error", "thinking.type: invalid"))
    assert m["run_status"] == "config_error"
    d, m, rows, cs, rs, client, _ = arun(aroot, lambda body, n, c: ok(body, c, model="claude-sonnet-5"), name="a2")
    assert len(client.calls) == 1 and rows[0]["status"] == "failed" and "pinned" in rows[0]["error"]
    assert not list(tn.cache_dir(aroot, A).glob("*.json"))


def test_refusal_and_max_tokens_are_billed_failures(aroot):
    def script(body, n, c):
        return ok(body, c, stop="refusal", content="") if n == 1 else ok(body, c, stop="max_tokens", content='{"provisional')
    d, m, rows, cs, *_ = arun(aroot, script, ids=["T0000", "T0001"])
    c = rows_of(d, "cost_report.csv")
    assert [r["request_status"] for r in c] == ["refusal", "incomplete"] and all(r["validation_status"].startswith("invalid") for r in c)
    assert cs["cost_usd"]["estimated_total"] == "0.00840000" and not list(tn.cache_dir(aroot, A).glob("*.json"))


def test_unpriced_or_missing_usage_stops(aroot):
    d, m, rows, cs, rs, client, _ = arun(aroot, lambda body, n, c: ok(body, c, usage=dict(USAGE, inference_geo="us")))
    assert len(client.calls) == 1 and "unpriced" in cs["stop_reason"] and cs["unknown_cost_attempts"] == 1


def test_budgets(aroot):
    *_, cs, rs, client, _ = arun(aroot, ids=["T0002"])
    assert cs["budget_usd"] == "1.00000000"
    *_, cs, rs, client, _ = arun(aroot, ids=["T0001"], scope="all", name="a2")
    assert cs["budget_usd"] == "10.00000000"
    d, m, rows, cs, rs, client, _ = arun(aroot, ids=["T0000"], budget_usd="0.001", name="a3")
    assert client.calls == [] and rows[0]["status"] == "not_attempted" and "budget" in cs["stop_reason"]


def test_resume_inherits_scope_and_does_not_repeat_requests(aroot):
    def stop_after_first(body, n, c):
        return ok(body, c) if n == 1 else err(429, c, details={"error_code": "enforced_spend_limit_reached"})
    d, m, rows, cs, rs, client, clock = arun(aroot, stop_after_first, scope="all", name=None)
    assert [r["status"] for r in rows] == ["ok", "failed", "not_attempted"] and "_all_" in m["run_id"]
    assert "--provider anthropic" in rs["resume"]["resume_command"] or rs["resume"]["resume_command"] is None
    d2, m2, rows2, cs2, rs2, client2, _ = arun(aroot, ids=None, scope=None, name=None, resume_from=m["run_id"])
    assert m2["scope"] == "all" and cs2["budget_usd"] == "10.00000000" and "_all_" in m2["run_id"]
    assert len(client2.calls) == 2 and rows2[0]["cached"] and [r["status"] for r in rows2] == ["ok"] * 3
    asked = [json.loads(b["messages"][0]["content"])["topic_id"] for b in client2.calls]
    assert asked == ["T0001", "T0002"]


def test_groq_scope_inherited_on_resume(root):
    *_, m, rows, cs, rs, clock = run(root, Session(lambda body, n: __import__("test_topic_naming").err(429, retry_after=3600)),
                                     scope="all")
    out = tn.generate(tn.GroqBackend(Session(), key=KEY), None, scope=None, root=root, run_id=RUN, expected=EXP,
                      today=TODAY, clock=Clock(clock.t + 7200), sleep=lambda s: None, rng=random.Random(0),
                      resume_from=m["run_id"])
    assert out[1]["scope"] == "all" and out[3]["budget_usd"] == "10.00000000" and "_all_" in out[1]["run_id"]


def test_resume_refuses_other_provider(aroot):
    run(aroot, Session(), ids=["T0000"])
    with pytest.raises(SystemExit, match="another prompt, provider"):
        arun(aroot, ids=None, name="a9", resume_from="r1")


# ---------- selection and assembly ----------
def test_only_missing_selection_cache_isolation_and_assembly(aroot):
    run(aroot, Session(), ids=["T0000"])                                  # one Qwen answer
    groq_files = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in tn.cache_dir(aroot).glob("*.json")}
    sel = tn.select_missing(aroot, RUN, "groq", EXP)
    assert (sel["present"], sel["missing"]) == (["T0000"], ["T0001", "T0002"])
    with pytest.raises(ValueError, match="2 topics have no name"):
        tn.assemble(aroot, RUN, [tn.GROQ, A], EXP, write=False)
    _, m0, part = tn.assemble(aroot, RUN, [tn.GROQ, A], EXP, allow_incomplete=True, write=False)
    assert m0["complete"] is False and m0["counts"] == {"topics": 3, "groq": 1, "missing": 2}
    d, m, rows, cs, rs, client, _ = arun(aroot, ids=sel["missing"], scope="all",
                                         selection={k: sel[k] for k in ("only_missing_from", "missing_count")})
    assert [json.loads(b["messages"][0]["content"])["topic_id"] for b in client.calls] == ["T0001", "T0002"]
    assert m["selection"]["missing_count"] == 2
    assert {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in tn.cache_dir(aroot).glob("*.json")} == groq_files
    out, man, res = tn.assemble(aroot, RUN, [tn.GROQ, A], EXP)
    by = {r["topic_id"]: r for r in res}
    assert man["complete"] and man["counts"] == {"topics": 3, "groq": 1, "anthropic": 2} and len(by) == 3
    groq_name = json.loads((tn.naming_dir(aroot, RUN) / "r1" / "results.jsonl").read_text().splitlines()[0])["provisional_name"]
    assert (by["T0000"]["source_provider"], by["T0000"]["source_model"], by["T0000"]["source_run_id"]) == \
        ("groq", "qwen/qwen3.8-27b", "r1") and by["T0000"]["provisional_name"] == groq_name
    assert by["T0001"]["source_provider"] == "anthropic" and by["T0001"]["source_run_id"] == m["run_id"]
    assert all(r["provisional"] is True and r["human_validated"] is False and r["source_cache_key"] for r in res)
    assert (tn.tracked_dir(aroot, RUN) / out.name / "manifest.json").is_file()
    assert json.loads((out / "manifest.json").read_text())["files_sha256"]["results.jsonl"] == \
        hashlib.sha256((out / "results.jsonl").read_bytes()).hexdigest()


def test_auto_run_ids_are_unique_within_one_second(aroot, monkeypatch):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(tn, "datetime", Frozen)
    ids = [arun(aroot, ids=["T0000"], name=None)[1]["run_id"] for _ in range(3)]
    assert ids == ["topic_naming_v1_claude-sonnet-5-5_pilot_20261104T120000Z",
                   "topic_naming_v1_claude-sonnet-5-5_pilot_20261104T120000Z_2",
                   "topic_naming_v1_claude-sonnet-5-5_pilot_20261104T120000Z_3"]
    with pytest.raises(FileExistsError):                                  # an explicit name is never reused
        arun(aroot, ids=["T0000"], name=ids[0])
