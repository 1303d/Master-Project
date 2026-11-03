"""Sprint 4 step 3 (topic naming) on the synthetic taxonomy of test_topic_features.py, with a fake Groq HTTP session,
a fake clock (sleeping advances it, so no test waits) and simulated rate-limit headers. No database, no network.

    python -m pytest tests/sprint4 -q
"""
import csv
import json
import random
import shutil
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import freeze_sprint4_input as fz  # noqa: E402
import topic_features as tf  # noqa: E402
import topic_naming as tn  # noqa: E402
from test_topic_features import EXP, RUN, raw  # noqa: E402

TODAY = date(2026, 11, 3)
IDS = ["T0000", "T0001", "T0002"]
KEY = "gsk_TESTKEYtestkey1234567890abcdef"
USAGE = {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100}   # $0.0008 + $0.0004 = $0.0012
HDR = {"x-ratelimit-limit-requests": "1000", "x-ratelimit-remaining-requests": "999", "x-ratelimit-reset-requests": "1m26.4s",
       "x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "6900", "x-ratelimit-reset-tokens": "8.25s"}


# ---------- fakes ----------
class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t, self.slept = t, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class Resp:
    def __init__(self, status=200, data=None, headers=None, text=""):
        self.status_code, self.data, self.headers = status, data, dict(headers or {})
        self.text = text or (json.dumps(data) if data is not None else "")

    def json(self):
        if self.data is None:
            raise ValueError("no JSON")
        return self.data


def answer(body, conf="medium"):
    p = json.loads(body["messages"][1]["content"])
    return json.dumps({"provisional_name": f"Topic {p['topic_id']} Area", "description": "Shared competency.",
                       "supporting_skills": p["representative_skills"][:3], "confidence": conf, "confidence_reason": "Fits."})


def ok(body, usage=USAGE, model=tn.MODEL_ID, finish="stop", headers=HDR, content=None):
    return Resp(200, {"id": "chatcmpl-1", "model": model, "x_groq": {"id": "req_ok"}, "usage": usage,
                      "choices": [{"message": {"content": answer(body) if content is None else content}, "finish_reason": finish}]},
                headers)


def err(status, retry_after=None, text="rate limited", headers=HDR):
    h = dict(headers)
    if retry_after is not None:
        h["retry-after"] = str(retry_after)
    return Resp(status, {"error": {"message": text}}, h, text)


class Session:
    """script(body, call_number) -> Resp or raises."""

    def __init__(self, script=None, model_ok=True):
        self.calls, self.gets, self.model_ok = [], [], model_ok
        self.script = script or (lambda body, n: ok(body))

    def post(self, url, headers=None, json=None, timeout=None):
        assert url.endswith("/chat/completions") and headers["Authorization"] == f"Bearer {KEY}"
        self.calls.append(json)
        return self.script(json, len(self.calls))

    def get(self, url, headers=None, timeout=None):
        self.gets.append(url)
        return Resp(200, {"id": tn.MODEL_ID, "active": True, "context_window": 131072}) if self.model_ok else Resp(404, {})


@pytest.fixture
def root(tmp_path):
    fz.export(raw(), tmp_path, "c0ffee", expected=EXP)
    tf.build(tmp_path, RUN, expected=EXP)
    (tmp_path / "prompts").mkdir()
    shutil.copy(ROOT / "prompts" / f"{tn.PROMPT_VERSION}.txt", tmp_path / "prompts")
    for f in (tn.pricing_path, tn.rate_limits_path):
        f(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f(ROOT), f(tmp_path))
    return tmp_path


def prep(root, **kw):
    return tn.prepare(root, RUN, EXP, pilot_per=0, today=TODAY, **kw)


def run(root, session, ids=IDS, scope="pilot", name="r1", clock=None, **kw):
    if not tn.prepare_dir(root, RUN).exists():
        prep(root)
    clock = clock or Clock()
    out = tn.generate(tn.GroqBackend(session, key=KEY), ids, scope=scope, root=root, run_id=RUN, expected=EXP,
                      naming_run_id=name, today=TODAY, clock=clock, sleep=clock.sleep, rng=random.Random(0), **kw)
    return (*out, clock)


def rows_of(d, name):
    return list(csv.DictReader((d / name).open(encoding="utf-8")))


def assigned(root):
    out = {}
    for m in tf.load_snapshot(root, RUN, EXP)["memberships"]:
        if m["state"] == "assigned":
            out.setdefault(m["topic_id"], set()).add(m["skill_key"])
    return out


def limiter(clock, **limits):
    base = {"rpm": None, "rpd": None, "tpm": None, "tpd": None, "input_tpm": None, "output_tpm": None}
    return tn.RateLimiter({**base, **limits}, 1.0, clock, clock.sleep)


# ---------- unchanged safeguards ----------
def test_tampered_inputs_stop(root):
    f = tf.features_dir(root, RUN) / "topic_features.csv"
    f.write_bytes(f.read_bytes() + b"x")
    with pytest.raises(SystemExit, match="features failed verification"):
        prep(root, write=False)


def test_evidence_grounded_and_pilot_deterministic(root):
    res = prep(root, write=False)
    a = assigned(root)
    assert [r["topic_id"] for r in res["records"]] == IDS and res["problems"] == {}
    for r in res["records"]:
        listed = r["payload"]["representative_skills"] + r["payload"]["additional_members"]
        assert set(listed) <= a[r["topic_id"]] and not {"w1", "w2"} & set(listed) and "label" not in json.dumps(r["payload"])
    assert prep(root, write=False)["manifest"]["files_sha256"] == res["manifest"]["files_sha256"]
    recs = [{"topic_id": f"T{i:04d}", "topic_quality_flags": [f for f, on in (
                ("low_cohesion", i % 5 == 1), ("near_duplicate_topic", i % 5 == 2), ("weak_exceeds_assigned", i % 7 == 3)) if on],
             "metrics": {"is_transversal": i % 5 == 0, "coverage_any": 0.1 if i % 4 == 3 else 0.6,
                         "n_weak": 30 if i % 7 == 3 else 2, "n_assigned": 10 + i % 30}} for i in range(80)]
    assert tn.select_pilot(recs, seed=1) == tn.select_pilot(recs, seed=1) and len(tn.select_pilot(recs, seed=1)) == 24


def test_requests_pinned_to_groq_qwen(root):
    res = prep(root, write=False)
    req, rec = res["requests"][2], res["records"][2]
    b = req["body"]
    assert b["model"] == "qwen/qwen3.8-27b" and set(b) == tn.BODY_KEYS and b["temperature"] == 0
    assert (b["reasoning_effort"], b["reasoning_format"], b["response_format"]) == ("none", "hidden", {"type": "json_object"})
    assert [m["role"] for m in b["messages"]] == ["system", "user"]
    assert b["messages"][0]["content"] == (ROOT / "prompts" / "topic_naming_v1.txt").read_text()   # prompt unchanged
    a = assigned(root)
    assert tn.validate_request(req, rec, a["T0002"], set(IDS)) == []
    for extra in ({"stream": True}, {"model": "qwen/qwen3-32b"}, {"temperature": 0.7}, {"fallback": "x"}):
        bad = json.loads(json.dumps(req))
        bad["body"].update(extra)
        assert tn.validate_request(bad, rec, a["T0002"], set(IDS)), extra


def test_cache_key_covers_model_settings_prompt_payload(root, monkeypatch):
    p = prep(root, write=False)["records"][2]["payload"]
    k = tn.build_request("JSON", p)["cache_key"]
    assert tn.build_request("JSON", p)["cache_key"] == k and tn.build_request("JSON v2", p)["cache_key"] != k
    assert tn.build_request("JSON", dict(p, transversal=True))["cache_key"] != k
    monkeypatch.setattr(tn, "MAX_COMPLETION_TOKENS", 600)
    assert tn.build_request("JSON", p)["cache_key"] != k


def test_dry_run_makes_no_api_call(root, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("HTTP session created during a dry run")
    monkeypatch.setattr(requests, "Session", boom)
    monkeypatch.setattr(requests, "post", boom)
    res = prep(root, write=False)
    e = res["manifest"]["offline_estimate"]
    assert e["full_run"]["topics"] == 3 and e["full_run"]["quota"]["plan"] == "free" and e["pricing_error"] is None
    assert not tn.prepare_dir(root, RUN).exists() and not tn.cache_dir(root).exists()


# ---------- configuration ----------
def test_pricing_and_rate_limit_snapshots_hold_verified_values():
    p = tn.load_pricing(tn.pricing_path(ROOT), TODAY)
    assert p["rates"] == {"input": Decimal("0.80"), "output": Decimal("4.00")} and p["data"]["model_id"] == "qwen/qwen3.8-27b"
    assert p["data"]["sources"][0]["url"] == "https://console.groq.com/docs/models"
    f = tn.load_rate_limits(tn.rate_limits_path(ROOT), "free", TODAY)
    assert f["limits"] == {"rpm": 30, "rpd": 1000, "tpm": 8000, "tpd": 200000, "input_tpm": None, "output_tpm": None}
    assert f["safety"] == 0.9 and f["source"] == "https://console.groq.com/docs/rate-limits"
    d = tn.load_rate_limits(tn.rate_limits_path(ROOT), "developer", TODAY)
    assert (d["limits"]["rpm"], d["limits"]["tpm"], d["limits"]["rpd"]) == (1000, 250000, None)


@pytest.mark.parametrize("which, change, msg", [
    ("pricing", lambda p: p.update(model_id="qwen/qwen3-32b"), "not groq/qwen/qwen3.8-27b"),
    ("pricing", lambda p: p["rates"].pop("output"), "rate output missing"),
    ("pricing", lambda p: p.update(verified_utc_date="2026-09-01"), "older than 30 days"),
    ("pricing", lambda p: p.update(sources=[{"url": "https://example.com"}]), "official Groq"),
    ("limits", lambda p: p["plans"]["free"].update(tpm=-5), "limit tpm must be a positive"),
    ("limits", lambda p: p.update(safety_factor="2"), "safety_factor"),
    ("limits", lambda p: p.update(model_id="x"), "not groq/qwen")])
def test_configuration_validation_rejects(tmp_path, which, change, msg):
    src = tn.pricing_path(ROOT) if which == "pricing" else tn.rate_limits_path(ROOT)
    p = json.loads(src.read_text())
    change(p)
    f = tmp_path / "c.json"
    f.write_text(json.dumps(p))
    with pytest.raises(ValueError, match=msg):
        tn.load_pricing(f, TODAY) if which == "pricing" else tn.load_rate_limits(f, "free", TODAY)


# ---------- rate limiter ----------
def test_parse_groq_durations():
    assert tn.parse_duration("2m59.56s") == pytest.approx(179.56) and tn.parse_duration("7.66s") == pytest.approx(7.66)
    assert tn.parse_duration("120ms") == pytest.approx(0.12) and tn.parse_duration("1h2m") == pytest.approx(3720)
    assert tn.parse_duration("3") == 3.0 and tn.parse_duration("soon") is None and tn.parse_duration(None) is None


def test_headers_interpreted_as_requests_per_day_and_tokens_per_minute():
    h = tn.read_rate_headers({"X-RateLimit-Limit-Requests": "14400", "x-ratelimit-limit-tokens": "18000",
                              "x-ratelimit-remaining-requests": "14370", "x-ratelimit-remaining-tokens": "17997",
                              "x-ratelimit-reset-requests": "2m59.56s", "x-ratelimit-reset-tokens": "7.66s", "retry-after": "2"})
    assert (h["limit_requests_day"], h["limit_tokens_minute"]) == (14400, 18000)
    assert (h["remaining_requests_day"], h["remaining_tokens_minute"]) == (14370, 17997)
    c = Clock()
    lim = limiter(c, rpm=30, rpd=1000, tpm=8000, tpd=200000)
    lim.record(10, 5, {"x-ratelimit-limit-requests": "14400", "x-ratelimit-limit-tokens": "18000"})
    assert lim.limits == {**lim.configured, "rpd": 14400, "tpm": 18000}          # never mistaken for RPM / TPD
    assert lim.limits["rpm"] == 30 and lim.limits["tpd"] == 200000 and lim.header_adopted == {"rpd": 14400, "tpm": 18000}


def test_rpm_throttling_waits_for_the_window():
    c = Clock()
    lim = limiter(c, rpm=3)
    for _ in range(3):
        assert lim.check(1, 1)[0] == "go"
        lim.record(1, 1, {})
        c.t += 1
    action, wait, why, src = lim.check(1, 1)
    assert action == "wait" and "RPM" in why and src == "local_estimate" and wait == pytest.approx(60 - 3 + 0.05)
    log = []
    waited, stop = lim.acquire(1, 1, lambda *a: log.append(a))
    assert stop is None and waited == pytest.approx(57.05) and [e[0] for e in log] == ["throttle_wait", "go"]


def test_tpm_throttling_and_oversized_request():
    c = Clock()
    lim = limiter(c, tpm=1000)
    lim.record(500, 100, {})
    c.t += 10
    action, wait, why, _ = lim.check(300, 200)
    assert action == "wait" and "TPM" in why and wait == pytest.approx(50.05)
    assert lim.check(900, 200)[0] == "stop"                                        # one request above the cap
    lim2 = limiter(c, input_tpm=400, output_tpm=1000)
    lim2.record(300, 0, {})
    assert lim2.check(200, 10)[2].startswith("INPUT_TPM")


def test_tpm_header_remaining_tokens_wait():
    c = Clock()
    lim = limiter(c, tpm=8000)
    lim.record(100, 10, {**HDR, "x-ratelimit-remaining-tokens": "300", "x-ratelimit-reset-tokens": "8.25s"})
    action, wait, why, src = lim.check(400, 100)
    assert action == "wait" and "TPM (provider-reported)" in why and src == "provider_headers" and wait == pytest.approx(8.30)


def test_rpd_and_tpd_exhaustion_stop():
    c = Clock()
    lim = limiter(c, rpd=2)
    lim.record(1, 1, {})
    lim.record(1, 1, {})
    waited, stop = lim.acquire(1, 1, lambda *a: None)
    assert "daily request limit" in stop and lim.daily_exhaustion_events == 1
    lim = limiter(c, tpd=1000)
    lim.record(800, 100, {})
    assert "daily token limit" in lim.acquire(80, 50, lambda *a: None)[1]
    c.t += tn.DAY_S + 1                                                            # rolling 24 h window
    assert lim.check(80, 50)[0] == "go"


def test_rpd_header_zero_remaining_waits_or_stops():
    c = Clock()
    lim = limiter(c)
    lim.record(1, 1, {**HDR, "x-ratelimit-remaining-requests": "0", "x-ratelimit-reset-requests": "2m"})
    assert lim.check(1, 1)[:2] == ("wait", 120.0)
    lim.record(1, 1, {**HDR, "x-ratelimit-remaining-requests": "0", "x-ratelimit-reset-requests": "5h"})
    assert lim.check(1, 1)[0] == "stop"


def test_backoff_is_exponential_bounded_and_jittered():
    rng = random.Random(0)
    w = [tn.backoff_seconds(n, rng) for n in range(1, 10)]
    for n, x in enumerate(w, 1):
        base = min(tn.BACKOFF_CAP_S, tn.BACKOFF_BASE_S * 2 ** (n - 1))
        assert base <= x <= base * (1 + tn.BACKOFF_JITTER)
    assert max(w) <= tn.BACKOFF_CAP_S * 1.25


# ---------- cost ----------
def test_costs_exact_decimal_and_missing_usage():
    p = tn.load_pricing(tn.pricing_path(ROOT), TODAY)
    c = tn.price_usage(USAGE, p)
    assert (c["estimated_input_cost"], c["estimated_output_cost"], c["estimated_cost"]) == \
        (Decimal("0.0008"), Decimal("0.0004"), Decimal("0.0012"))
    c = tn.price_usage({**USAGE, "prompt_tokens_details": {"cached_tokens": 600}}, p)
    assert c["cached_input_tokens"] == 600 and "upper bound" in c["estimate_note"] and c["estimated_cost"] == Decimal("0.0012")
    for u in (None, {"prompt_tokens": 5}, {"prompt_tokens": -1, "completion_tokens": 2}):
        m = tn.price_usage(u, p)
        assert m["estimate_status"] == "missing_usage" and m["estimated_cost"] is None and tn.usd(m["estimated_cost"]) == ""


# ---------- generation ----------
def test_generate_writes_cost_and_rate_reports(root):
    s = Session()
    d, m, rows, cs, rs, clock = run(root, s)
    assert len(s.calls) == 3 and s.gets and m["run_status"] == "completed" and m["result_problems"] == []
    for f in ("cost_report.csv", "cost_summary.json", "cost_report.md", "pricing_snapshot.json",
              "rate_limit_report.csv", "rate_limit_summary.json"):
        assert (d / f).is_file() and (tn.tracked_dir(root, RUN) / "r1" / f).is_file(), f
    c = rows_of(d, "cost_report.csv")
    assert [r["request_status"] for r in c] == ["ok"] * 3 and all(r["estimated_cost_usd"] == "0.00120000" for r in c)
    assert all(r["billed_cost_usd"] == "" and r["billing_status"] == "not_determinable_from_api" for r in c)
    assert c[0]["provider_remaining_requests_day"] == "999" and c[0]["provider_remaining_tokens_minute"] == "6900"
    assert cs["cost_usd"]["estimated_total"] == "0.00360000" and cs["cost_usd"]["billed_total"] is None
    assert cs["average_estimated_cost_per_successful_topic_usd"] == "0.00120000" and cs["tokens"]["input"] == 3000
    assert rs["requests"] == {"total": 3, "successful": 3, "failed": 0, "http_429": 0}
    assert rs["limits_from_headers"] == {"rpd": 1000, "tpm": 8000} and rs["remaining_topics"] == 0
    assert rs["resume"]["resume_command"] is None
    assert "Billed cost: unknown" in (d / "cost_report.md").read_text()
    assert len((tn.rate_state_dir(root) / "request_log.jsonl").read_text().splitlines()) == 3


def test_local_cache_reuse(root):
    run(root, Session())
    s = Session()
    d, m, rows, cs, rs, _ = run(root, s, name="r2")
    assert s.calls == [] and all(r["cached"] for r in rows) and cs["topics"]["local_cache_hits"] == 3
    c = rows_of(d, "cost_report.csv")
    assert all(r["local_cache"] == "hit" and r["api_call"] == "false" and r["estimated_cost_usd"] == "0.00000000" for r in c)
    assert cs["api_attempts"] == 0 and rs["requests"]["total"] == 0


def test_429_with_retry_after(root):
    s = Session(lambda body, n: err(429, retry_after=3) if n == 1 else ok(body))
    d, m, rows, cs, rs, clock = run(root, s, ids=["T0002"])
    c = rows_of(d, "cost_report.csv")
    assert [(r["attempt"], r["http_status"], r["request_status"]) for r in c] == [("1", "429", "api_error"), ("2", "200", "ok")]
    assert c[0]["retry_after_s"] == "3.000" and c[0]["estimate_status"] == "no_usage_on_error" and c[0]["estimated_cost_usd"] == ""
    assert c[1]["retry_count"] == "1" and c[1]["backoff_wait_s"] == "3.000" and 3.0 in clock.slept
    assert rs["requests"]["http_429"] == 1 and rs["wait_seconds"]["backoff_and_retry_after"] == 3.0
    assert cs["error_attempts_without_usage"] == 1 and cs["cost_usd"]["estimate_status"].startswith("incomplete")
    assert rows[0]["status"] == "ok" and rows[0]["attempts"] == 2


def test_429_without_retry_after_uses_backoff(root):
    s = Session(lambda body, n: err(429) if n <= 2 else ok(body))
    d, m, rows, cs, rs, clock = run(root, s, ids=["T0002"])
    waits = [w for w in clock.slept]
    assert len(waits) == 2 and 2.0 <= waits[0] <= 2.5 and 4.0 <= waits[1] <= 5.0 and rows[0]["status"] == "ok"
    assert [r["event"] for r in rows_of(d, "rate_limit_report.csv")].count("backoff_wait") == 2


def test_retry_limit_is_bounded(root):
    s = Session(lambda body, n: err(429, retry_after=1))
    d, m, rows, cs, rs, clock = run(root, s, ids=["T0002"])
    assert len(s.calls) == tn.MAX_ATTEMPTS and rows[0]["status"] == "failed" and len(clock.slept) == tn.MAX_ATTEMPTS - 1
    assert rs["requests"]["http_429"] == tn.MAX_ATTEMPTS


def test_long_retry_after_stops_run_as_daily_quota(root):
    s = Session(lambda body, n: err(429, retry_after=3600))
    d, m, rows, cs, rs, clock = run(root, s)
    assert len(s.calls) == 1 and m["run_status"] == "quota_exhausted" and rs["daily_quota_exhaustion_events"] == 1
    assert [r["status"] for r in rows] == ["failed", "not_attempted", "not_attempted"] and clock.slept == []
    assert rs["resume"]["resume_command"].endswith("--resume r1")


def test_rpd_header_exhaustion_stops_and_resume_completes(root):
    s = Session(lambda body, n: ok(body, headers={**HDR, "x-ratelimit-remaining-requests": "0",
                                                  "x-ratelimit-reset-requests": "7h"}))
    d, m, rows, cs, rs, clock = run(root, s)
    assert len(s.calls) == 1 and m["run_status"] == "quota_exhausted"
    assert [r["status"] for r in rows] == ["ok", "not_attempted", "not_attempted"] and rs["remaining_topics"] == 2
    later = Clock(clock.t + 8 * 3600)
    s2 = Session()
    d2, m2, rows2, cs2, rs2, _ = run(root, s2, ids=None, name="r2", resume_from="r1", clock=later)
    assert len(s2.calls) == 2 and [r["status"] for r in rows2] == ["ok"] * 3 and len({r["topic_id"] for r in rows2}) == 3
    assert rows2[0]["cached"] and rows2[0]["resumed"] and rs2["resume"]["carried_over_completed"] == 1
    assert [json.loads(b["messages"][1]["content"])["topic_id"] for b in s2.calls] == ["T0001", "T0002"]


def test_tpd_exhaustion_from_earlier_runs_today(root):
    prep(root)
    clock = Clock()
    tn.rate_state_dir(root).mkdir(parents=True)
    (tn.rate_state_dir(root) / "request_log.jsonl").write_text(
        json.dumps({"t": clock.t - 3600, "in": 170000, "out": 9500, "run": "earlier"}) + "\n")
    s = Session()
    d, m, rows, cs, rs, _ = run(root, s, clock=clock)
    assert s.calls == [] and m["run_status"] == "quota_exhausted" and "daily token limit" in m["cost"]["stop_reason"]
    assert all(r["status"] == "not_attempted" for r in rows)


def test_throttling_inside_a_run_is_recorded(root, monkeypatch):
    lim = json.loads(tn.rate_limits_path(root).read_text())
    lim["plans"]["free"]["rpm"] = 2
    tn.rate_limits_path(root).write_text(json.dumps(lim))
    s = Session(lambda body, n: ok(body, headers={}))
    d, m, rows, cs, rs, clock = run(root, s)
    assert len(s.calls) == 3 and rs["throttle_events"] >= 1 and rs["wait_seconds"]["throttle"] > 50
    assert any(r["event"] == "throttle_wait" and "RPM" in r["reason"] for r in rows_of(d, "rate_limit_report.csv"))
    assert float(rows_of(d, "cost_report.csv")[2]["rate_limit_wait_s"]) > 50


def test_interrupted_run_recovery_without_duplicates(root):
    def script(body, n):
        if n == 2:
            raise KeyboardInterrupt
        return ok(body)
    with pytest.raises(KeyboardInterrupt):
        run(root, Session(script))
    d = tn.naming_dir(root, RUN) / "r1"
    res = [json.loads(x) for x in (d / "results.jsonl").read_text().splitlines()]
    assert [r["status"] for r in res] == ["ok", "not_attempted", "not_attempted"]
    assert json.loads((d / "cost_summary.json").read_text())["run_status"] == "interrupted"
    assert json.loads((d / "rate_limit_summary.json").read_text())["resume"]["resume_possible"] is True
    s2 = Session()
    d2, m2, rows2, *_ = run(root, s2, ids=None, name="r2", resume_from="r1")
    assert len(s2.calls) == 2 and [r["topic_id"] for r in rows2] == IDS and all(r["status"] == "ok" for r in rows2)


def test_resume_refuses_another_prompt(root):
    run(root, Session(lambda body, n: err(429, retry_after=3600)))
    prev = tn.naming_dir(root, RUN) / "r1" / "manifest.json"
    m = json.loads(prev.read_text())
    m["prompt_sha256"] = "0" * 64
    prev.write_text(json.dumps(m))
    with pytest.raises(SystemExit, match="cannot resume"):
        run(root, Session(), ids=None, name="r2", resume_from="r1")


def test_missing_usage_stops(root):
    s = Session(lambda body, n: ok(body, usage=None))
    d, m, rows, cs, rs, _ = run(root, s)
    assert len(s.calls) == 1 and "usage missing" in cs["stop_reason"] and cs["unknown_cost_attempts"] == 1
    assert rows_of(d, "cost_report.csv")[0]["estimated_cost_usd"] == "" and cs["average_estimated_cost_per_successful_topic_usd"] is None


def test_missing_pricing_blocks_live_run(root):
    prep(root)
    tn.pricing_path(root).unlink()
    with pytest.raises(ValueError, match="pricing snapshot missing"):
        run(root, Session())
    assert prep(root, write=False)["manifest"]["offline_estimate"]["pricing_error"].startswith("pricing snapshot missing")


def test_model_preflight_and_mismatch(root):
    s = Session(model_ok=False)
    with pytest.raises(SystemExit, match="pre-flight"):
        run(root, s)
    assert s.calls == []
    s = Session(lambda body, n: ok(body, model="qwen/qwen3-32b"))
    d, m, rows, cs, rs, _ = run(root, s, name="r2")
    assert len(s.calls) == 1 and rows[0]["status"] == "failed" and "pinned" in rows[0]["error"]
    assert [r["status"] for r in rows[1:]] == ["not_attempted"] * 2 and not list(tn.cache_dir(root).glob("*.json"))


def test_invalid_answer_not_cached(root):
    s = Session(lambda body, n: ok(body, content='{"provisional_name": "x"}'))
    d, m, rows, *_ = run(root, s, ids=["T0002"])
    assert rows[0]["status"] == "failed" and "missing keys" in rows[0]["error"] and not list(tn.cache_dir(root).glob("*.json"))


def test_budget_stops_before_request(root):
    s = Session()
    d, m, rows, cs, rs, _ = run(root, s, budget_usd="0.0001")
    assert s.calls == [] and all(r["status"] == "not_attempted" for r in rows) and "budget" in cs["stop_reason"]


def test_no_secrets_in_reports(root):
    s = Session(lambda body, n: err(401, text=f"invalid key {KEY} Bearer {KEY}") if n == 1 else ok(body))
    d, *_ = run(root, s, secrets=[KEY])
    for folder in (d, tn.tracked_dir(root, RUN) / "r1"):
        for f in folder.iterdir():
            text = f.read_text(encoding="utf-8")
            assert KEY not in text and "gsk_" not in text and "Bearer gsk" not in text, f
    assert "[REDACTED]" in (d / "cost_report.csv").read_text()


def test_frozen_inputs_untouched_and_reproducible(root, tmp_path):
    snap_m = (fz.snapshot_dir(root, RUN) / "manifest.json").read_bytes()
    d, m, rows, *_ = run(root, Session())
    assert fz.verify(root, RUN, EXP) == [] and tf.verify(root, RUN) == []
    assert (fz.snapshot_dir(root, RUN) / "manifest.json").read_bytes() == snap_m
    with pytest.raises(FileExistsError):
        run(root, Session())
    other = tmp_path / "other"
    fz.export(raw(), other, "c", expected=EXP)
    tf.build(other, RUN, expected=EXP)
    (other / "prompts").mkdir()
    shutil.copy(ROOT / "prompts" / f"{tn.PROMPT_VERSION}.txt", other / "prompts")
    for f in (tn.pricing_path, tn.rate_limits_path):
        f(other).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f(ROOT), f(other))
    d2, *_ = run(other, Session())
    assert (d / "results.csv").read_bytes() == (d2 / "results.csv").read_bytes()


# ---------- output validation ----------
GOOD = {"provisional_name": "Data Engineering", "description": "Building data pipelines.",
        "supporting_skills": ["z00", "z01", "z02"], "confidence": "high", "confidence_reason": "All fit."}


@pytest.mark.parametrize("bad, m_", [("not json", "Expecting"), ("[]", "not a JSON object"),
                                     ({k: v for k, v in GOOD.items() if k != "description"}, "missing keys"),
                                     (dict(GOOD, confidence="sure"), "confidence")])
def test_structural_errors_raise(bad, m_):
    with pytest.raises(ValueError, match=m_):
        tn.parse_answer(json.dumps(bad) if isinstance(bad, dict) else bad)


def test_content_flags_and_review_reasons():
    payload = {"representative_skills": ["z00", "z01", "python"], "additional_members": ["z02"]}
    assert tn.name_flags(tn.parse_answer(json.dumps(GOOD)), payload) == (["z00", "z01", "z02"], [])
    row = lambda t, n, conf="high", st="ok", tq=(): {"topic_id": t, "status": st, "provisional_name": n,
                                                     "llm_confidence": conf, "topic_quality_flags": list(tq), "name_flags": []}
    r = {x["topic_id"]: x for x in tn.finalise([row("T1", "Data Engineering"), row("T2", "data engineering!"),
                                                row("T3", "Nursing", conf="low"), row("T4", "Tax Law", tq=["low_cohesion"]),
                                                row("T5", "", st="not_attempted")])}
    assert "duplicate_name:T2" in r["T1"]["name_flags"] and r["T3"]["review_reason"] == "llm_confidence_low"
    assert r["T4"]["review_reason"] == "low_cohesion" and r["T5"]["review_reason"] == "not_attempted"
    full = {f: "x" for f in tn.PROVENANCE_FIELDS}
    okrow = {"topic_id": "T1", "status": "ok", "provisional_name": "A B", **full}
    assert tn.check_results([okrow], ["T1"]) == [] and tn.check_results([okrow, okrow], ["T1"])


# ---------- fail fast on request-configuration errors ----------
def bad_request(code=None, msg="`reasoning_effort` 'none' is not supported for this request", failed_generation=None):
    e = {"message": msg, "type": "invalid_request_error"}
    if code:
        e["code"] = code
    if failed_generation:
        e["failed_generation"] = failed_generation
    return Resp(400, {"error": e}, HDR)


def test_error_classes():
    assert tn.ApiErr(400, "x", body={"error": {"type": "invalid_request_error"}}).error_class == "config"
    assert tn.ApiErr(400, "x", body={"error": {"code": "json_validate_failed"}}).error_class == "content"
    assert tn.ApiErr(400, "x", body={"error": {"failed_generation": "{bad"}}).error_class == "content"
    assert [tn.ApiErr(s, "x").error_class for s in (401, 403, 404, 422, 429, 498, 503, 599, 413)] == \
        ["config", "config", "config", "content", "rate_limit", "transient", "transient", "transient", "other"]
    assert not tn.ApiErr(400, "x").retryable and tn.ApiErr(429, "x").retryable


@pytest.mark.parametrize("make, status", [
    (lambda: bad_request(), "400"),
    (lambda: Resp(401, {"error": {"message": "Invalid API Key", "type": "invalid_request_error", "code": "invalid_api_key"}}, HDR), "401"),
    (lambda: Resp(404, {"error": {"message": "The model does not exist", "type": "invalid_request_error",
                                  "code": "model_not_found"}}, HDR), "404")])
def test_config_error_stops_the_whole_run(root, make, status):
    s = Session(lambda body, n: make())
    d, m, rows, cs, rs, clock = run(root, s)
    assert len(s.calls) == 1 and clock.slept == [] and m["run_status"] == "config_error"   # not retried, not repeated
    assert [r["status"] for r in rows] == ["failed", "not_attempted", "not_attempted"]
    c = rows_of(d, "cost_report.csv")
    assert len(c) == 1 and (c[0]["http_status"], c[0]["error_class"]) == (status, "config") and "invalid_request_error" in c[0]["error"]
    assert "config_stop" in [r["event"] for r in rows_of(d, "rate_limit_report.csv")]
    assert rs["config_error"]["topic_id"] == "T0000" and rs["config_error"]["http_status"] == int(status)
    assert rs["resume"]["resume_possible"] is False and "fix the request" in rs["resume"]["note"]
    assert cs["stop_reason"].startswith("request configuration rejected") and "config error" in (d / "cost_report.md").read_text()
    assert all("request configuration rejected" in r["error"] for r in rows[1:])


@pytest.mark.parametrize("make", [
    lambda: bad_request(code="json_validate_failed", msg="Failed to generate JSON", failed_generation='{"provisional_name": '),
    lambda: Resp(422, {"error": {"message": "could not be followed", "type": "invalid_request_error"}}, HDR),
    lambda: Resp(413, {"error": {"message": "Request Entity Too Large", "type": "invalid_request_error"}}, HDR)])
def test_content_failures_fail_only_that_topic(root, make):
    s = Session(lambda body, n: make() if n == 1 else ok(body))
    d, m, rows, cs, rs, _ = run(root, s)
    assert len(s.calls) == 3 and m["run_status"] == "completed" and rs["config_error"] is None
    assert [r["status"] for r in rows] == ["failed", "ok", "ok"]
    assert rows_of(d, "cost_report.csv")[0]["error_class"] in ("content", "other")


def test_invalid_answer_is_not_a_config_error(root):
    s = Session(lambda body, n: ok(body, content="[]") if n == 1 else ok(body))
    d, m, rows, *_ = run(root, s)
    assert len(s.calls) == 3 and m["run_status"] == "completed" and [r["status"] for r in rows] == ["failed", "ok", "ok"]


# ---------- provider-reported vs locally estimated quota ----------
TPD_MSG = ("Rate limit reached for model `qwen/qwen3.8-27b` in organization `org_x` service tier `on_demand` on tokens "
           "per day (TPD): Limit 200000, Used 199100, Requested 1923. Please try again in 2h0m0s.")


def test_parse_quota_message():
    q = tn.parse_quota_message(TPD_MSG.replace("2h0m0s", "7m12.5s"))
    assert q == {"tokens_day": {"limit": 200000, "used": 199100, "requested": 1923, "retry_in_s": pytest.approx(432.5)}}
    assert tn.parse_quota_message("Rate limit reached on requests per minute (RPM)") == {}
    assert tn.parse_quota_message(None) == {}


def test_provider_quota_preferred_over_local_estimate():
    c = Clock()
    lim = limiter(c, rpd=2)
    lim.record(1, 1, {})
    lim.record(1, 1, {})
    action, _, why, src = lim.check(1, 1)
    assert (action, src) == ("stop", "local_estimate") and "local estimate" in why
    lim.record(1, 1, {"x-ratelimit-remaining-requests": "500", "x-ratelimit-reset-requests": "1h"})
    assert lim.check(1, 1)[0] == "go"                         # Groq says 500 left: the local 24 h count does not decide


def test_provider_reset_time_releases_quota_without_rolling_window():
    c = Clock()
    lim = limiter(c, rpd=1000)
    lim.record(1, 1, {"x-ratelimit-remaining-requests": "0", "x-ratelimit-reset-requests": "2m"})
    action, wait, why, src = lim.check(1, 1)
    assert (action, src) == ("wait", "provider_headers") and wait == pytest.approx(120) and "provider-reported" in why
    c.t += 121
    assert lim.check(1, 1)[0] == "go"                         # released by Groq's reset, not 24 h later
    lim.record(1, 1, {"x-ratelimit-remaining-requests": "0"})
    action, wait, why, _ = lim.check(1, 1)
    assert action == "stop" and wait is None and "no reset time" in why


def test_quota_report_labels_sources_separately():
    c = Clock()
    lim = limiter(c, rpm=30, rpd=1000, tpm=8000, tpd=200000)
    lim.record(1000, 100, HDR)
    lim.note_429(TPD_MSG, 7200)
    r = lim.report()
    p, loc = r["provider_reported"], r["local_estimate"]
    assert p["requests_per_day"]["remaining"] == 999 and p["tokens_per_minute"]["limit"] == 8000
    assert p["tokens_per_day"] == "not reported in headers by Groq" and p["from_429_messages"]["tokens_day"]["used"] == 199100
    assert "NOT Groq's reset rule" in loc["source"] and loc["tokens_last_day"] == 1100 and loc["caps_after_safety"]["tpd"] == 200000


def test_tpd_429_stops_with_provider_reset_and_resume_waits_for_it(root):
    s = Session(lambda body, n: ok(body) if n == 1 else err(429, retry_after=7200, text=TPD_MSG))
    d, m, rows, cs, rs, clock = run(root, s)
    assert len(s.calls) == 2 and m["run_status"] == "quota_exhausted"
    assert [r["status"] for r in rows] == ["ok", "failed", "not_attempted"]
    assert rs["quota"]["provider_reported"]["from_429_messages"]["tokens_day"]["limit"] == 200000
    assert rs["resume"]["not_before_is"] == "provider-reported" and rs["resume"]["not_before_utc"]
    assert "provider_429_message" in [r["quota_source"] for r in rows_of(d, "rate_limit_report.csv")]
    s2 = Session()                                             # resume before Groq's reset: no API call
    d2, m2, rows2, cs2, rs2, _ = run(root, s2, ids=None, name="r2", resume_from="r1", clock=Clock(clock.t + 600))
    assert s2.calls == [] and m2["run_status"] == "quota_exhausted" and rows2[0]["cached"]
    assert rs2["last_quota_stop"]["source"] == "provider_429_message"
    s3 = Session()                                             # after the reset: the rest completes, no duplicates
    d3, m3, rows3, *_ = run(root, s3, ids=None, name="r3", resume_from="r2", clock=Clock(clock.t + 7300))
    assert len(s3.calls) == 2 and [r["status"] for r in rows3] == ["ok"] * 3 and len({r["topic_id"] for r in rows3}) == 3


def test_rpd_provider_reset_respected_on_resume(root):
    s = Session(lambda body, n: ok(body, headers={**HDR, "x-ratelimit-remaining-requests": "0",
                                                  "x-ratelimit-reset-requests": "7h"}))
    d, m, rows, cs, rs, clock = run(root, s)
    assert rs["resume"]["not_before_is"] == "provider-reported" and rs["last_quota_stop"]["source"] == "provider_headers"
    s2 = Session()
    d2, m2, rows2, cs2, rs2, _ = run(root, s2, ids=None, name="r2", resume_from="r1", clock=Clock(clock.t + 3600))
    assert s2.calls == [] and rs2["last_quota_stop"]["source"] == "provider_headers"


def test_local_estimate_stop_is_labelled_as_estimate(root):
    prep(root)
    clock = Clock()
    tn.rate_state_dir(root).mkdir(parents=True)
    (tn.rate_state_dir(root) / "request_log.jsonl").write_text(
        json.dumps({"t": clock.t - 3600, "in": 170000, "out": 9500, "run": "earlier"}) + "\n")
    d, m, rows, cs, rs, _ = run(root, Session(), clock=clock)
    stop = rs["last_quota_stop"]
    assert stop["source"] == "local_estimate" and "local estimate" in stop["reason"] and "TPD header" in stop["reason"]
    assert rs["resume"]["not_before_is"] == "local estimate" and stop["available_in_s"] == pytest.approx(tn.DAY_S - 3600)
    assert "local_estimate" in [r["quota_source"] for r in rows_of(d, "rate_limit_report.csv")]
