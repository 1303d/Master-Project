"""Sprint 4 step 3: provisional topic names from the frozen Sprint 4 snapshot + topic features.

    python src/topic_naming.py prepare --no-write --show 2   # offline dry run: verify, build, validate, estimate
    python src/topic_naming.py prepare                       # same, then write the prepare folder (never overwritten)
    python src/topic_naming.py verify                        # re-hash the prepare folder against its manifest
    python src/topic_naming.py generate --scope pilot --live # LIVE Groq calls: needs explicit approval first
    python src/topic_naming.py generate --live --resume <naming_run_id>   # continue a stopped / interrupted run

Inputs (read only, hash-checked first): data/processed/sprint4_input_<run>/ and sprint4_features_<run>/.
Nothing here writes to those folders, to Supabase, or changes memberships / centroids.

prepare   per topic, an evidence payload for the LLM:
            size (assigned / weak), transversal flag, cohesion band (low <= q25 < medium < q75 <= high of cos_mean
            over all topics), the 10 representative skills, up to N_EXTRA further ASSIGNED members spread evenly
            over the cosine-to-centroid range (centre -> edge), up to N_REF_HINTS ESCO / O*NET concepts linked
            (verdict known_skill) to assigned members, and the N_NEIGHBOURS most similar topics by their top skills.
            Weak members are never shown. The current label (= centroid skill) and anything from the intrusion test
            are never included.
          deterministic TOPIC-QUALITY flags (from features only, never from the LLM or the intrusion answer key):
            review flags  low_cohesion, weak_exceeds_assigned, no_reference_link, near_duplicate_topic
            info flags    transversal, low_reference_coverage
          a seeded, stratified 24-topic pilot (PILOT_STRATA, PILOT_SEED), recorded in the manifest.
          one pinned Groq request per topic, validated offline, plus offline cost and quota estimates. No API call.
generate  Groq OpenAI-compatible REST API (api.groq.com/openai/v1, plain HTTP, so no SDK retries), model MODEL_ID only:
          no fallback model, no other provider, no LiteLLM / Langfuse. The model is checked with GET /models/<id>
          before the first request. temperature 0, reasoning_effort none (no reasoning tokens), reasoning_format
          hidden (required with JSON mode), response_format json_object. Answers are cached locally in
          cache/topic_naming/groq/<key>.json, key = sha256(provider + model + all request settings + prompt sha +
          exact user message). A structurally invalid answer is a FAILED row and is never cached. Content problems
          are kept and FLAGGED. The LLM's own confidence is stored as llm_confidence, apart from the quality flags.
Rate      PROVIDER-REPORTED quota first: Groq headers (x-ratelimit-*-requests = per DAY, x-ratelimit-*-tokens = per
limits    MINUTE; their limits replace the configured RPD / TPM), Retry-After, and daily details parsed from 429
          messages (format undocumented; best effort). Kept in cache/topic_naming/groq/rate_state/provider_quota.json so a resume
          before Groq's reset makes no call. LOCAL ESTIMATES second: sliding 60 s / 24 h windows over this machine's
          request log (rate_state/request_log.jsonl), limits from config/rate_limits/<model>.json x a safety factor. Groq does
          not document how daily limits reset and its limits are per organization, so the local 24 h window is a
          conservative fallback, not Groq's rule: it decides RPD only when Groq reported nothing, and TPD always
          (Groq sends no TPD header). Every quota decision and reset time is labelled with its source.
          HTTP 429: wait Retry-After, else bounded exponential backoff with jitter; at most MAX_ATTEMPTS per topic;
          a Retry-After above MAX_RETRY_AFTER_S stops the run as quota exhausted. Requests are sequential.
Errors    400 (other than JSON-output validation) / 401 / 403 / 404 = request configuration error: the whole run
          stops at once (the same request would fail for every topic). 400 json_validate_failed and 422 = content
          failure of one topic. 429 / 5xx / 498 / connection = retried. Others fail the topic.
Cost      every API attempt (and every local cache hit) is one row of cost_report.csv. estimated_cost_usd =
          actual tokens x the published rates in config/pricing/<model>.json (Decimal). Groq returns no charge,
          so billed_cost_usd stays empty (unknown, never 0). Missing usage stops further live requests.
Resume    every finished topic is cached at once. --resume <run> starts a NEW run folder over the same topics: the
          previous run's completed topics come from the local cache (no API call), the rest are requested.
Outputs   data/processed/sprint4_naming_<run>/ (gitignored: contains member skills); tracked copies of manifests,
          cost and rate-limit reports (no member lists, no secrets) in reports/sprint4_naming/<run>/.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import platform
import random
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, deque
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import freeze_sprint4_input as fz  # noqa: E402
import topic_features as tf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = fz.RUN_ID
SCHEMA_VERSION = "sprint4_naming/3"
PROMPT_VERSION = "topic_naming_v1"
PROVIDER, MODEL_ID = "groq", "qwen/qwen3.8-27b"     # verified 2026-11-03: console.groq.com/docs/models (Preview)
MODEL_SLUG = MODEL_ID.replace("/", "_")
API_URL = "https://api.groq.com/openai/v1"
TEMPERATURE, REASONING_EFFORT, REASONING_FORMAT = 0, "none", "hidden"
RESPONSE_FORMAT = {"type": "json_object"}
MAX_COMPLETION_TOKENS = 512
N_REPS, N_EXTRA, N_REF_HINTS, N_NEIGHBOURS, N_NEIGHBOUR_SKILLS = 10, 20, 5, 3, 3
LOW_REF_COVERAGE = 0.30
MAX_USER_TOKENS = 3000          # rough estimate, chars / 4
PILOT_SEED, PILOT_PER_STRATUM = 20261104, 4
PILOT_STRATA = [  # (name, rule); applied in this order, a topic is chosen at most once
    ("transversal", "is_transversal"),
    ("low_cohesion", "flag low_cohesion and not transversal"),
    ("near_duplicate", "flag near_duplicate_topic (a neighbour centroid cosine >= 0.90)"),
    ("sparse_reference", "reference coverage_any < 0.30 (includes no link at all)"),
    ("weak_heavy", "n_weak > n_assigned"),
    ("baseline", "no review flag and not transversal"),
]
PILOT_COLS = ["topic_id", "stratum", "candidates", "also_matches", "size_tercile", "n_assigned", "topic_quality_flags"]
REVIEW_FLAGS = ("low_cohesion", "weak_exceeds_assigned", "no_reference_link", "near_duplicate_topic")
CONFIDENCE = ("high", "medium", "low")
OUTPUT_KEYS = ("provisional_name", "description", "supporting_skills", "confidence", "confidence_reason")
BODY_KEYS = {"model", "messages", "temperature", "max_completion_tokens", "reasoning_effort", "reasoning_format",
             "response_format"}
GENERIC_WORDS = {"skills", "skill", "various", "general", "miscellaneous", "misc", "other", "others", "etc", "stuff",
                 "assorted", "mixed", "topic", "cluster"}
NAME_WORDS, DESC_MAX_WORDS, SUPPORT_RANGE, NEAR_DUP_JACCARD = (2, 5), 30, (3, 6), 0.8
FORBIDDEN_KEYS = {"label", "answer", "answer_key", "intruder", "question", "question_id", "reviewer", "stratum"}
RESULT_COLS = ["topic_id", "status", "provisional_name", "description", "supporting_skills", "llm_confidence",
               "llm_confidence_reason", "topic_quality_flags", "name_flags", "review_required", "review_reason",
               "model", "served_model", "prompt_version", "prompt_sha256", "run_id", "clustering_run_id",
               "evidence_fingerprint", "cache_key", "cached", "resumed", "attempts", "estimated_cost_usd", "error"]
PROVENANCE_FIELDS = ("model", "served_model", "prompt_version", "prompt_sha256", "run_id", "clustering_run_id",
                     "evidence_fingerprint", "cache_key")
STATUSES = ("ok", "failed", "not_attempted")

# ---- cost / budget ----
RATE_KEYS = ("input", "output")
PRICING_MAX_AGE_DAYS = 30
OFFICIAL_PREFIXES = ("https://console.groq.com/", "https://groq.com/")
DEFAULT_BUDGET_USD = {"pilot": Decimal("1.00"), "all": Decimal("10.00")}
CHARS_PER_TOKEN_UPPER, CHARS_PER_TOKEN_TYPICAL = 2.5, 3.5   # assumptions (Qwen tokenizer not run locally)
REQUEST_OVERHEAD_TOKENS = 50    # assumption: chat template tokens
TYPICAL_OUTPUT_TOKENS = 200     # assumption for the typical estimate only (the upper bound uses max tokens)
MAX_ATTEMPTS = 5
RETRYABLE = {429, 498, 500, 502, 503, 504, 599}
CONFIG_ERROR_STATUSES = {400, 401, 403, 404}   # Groq errors page: fix the request / credentials, do not retry
CONTENT_ERROR_CODES = {"json_validate_failed"}  # Groq 400 code for JSON-mode output failures (seen in practice; not
                                               # on the errors page): a per-topic content failure, not a config error
BACKOFF_BASE_S, BACKOFF_CAP_S, BACKOFF_JITTER = 2.0, 60.0, 0.25
MAX_RETRY_AFTER_S = 600.0       # a longer Retry-After means a daily quota: stop and resume later
MAX_LIMITER_WAIT_S = 900.0      # never wait longer than this for one request
MINUTE_S, DAY_S = 60.0, 86400.0
MTOK, USD_Q = Decimal(1_000_000), Decimal("0.00000001")
SECRET_RE = re.compile(r"(gsk_[A-Za-z0-9]{8,}|sk-ant-[A-Za-z0-9_\-]{8,}|Bearer\s+\S+)")
COST_COLS = ["run_id", "topic_id", "attempt", "retry_count", "timestamp_utc", "requested_model", "served_model",
             "request_status", "api_call", "local_cache", "http_status", "error_class", "finish_reason", "input_tokens", "output_tokens",
             "reasoning_tokens", "cached_input_tokens", "total_tokens", "rate_limit_wait_s", "backoff_wait_s",
             "retry_after_s", "provider_remaining_requests_day", "provider_remaining_tokens_minute",
             "provider_reset_requests_day_s", "provider_reset_tokens_minute_s", "pricing_version", "pricing_sha256", "estimated_max_cost_usd",
             "estimated_input_cost_usd", "estimated_output_cost_usd", "estimated_cost_usd", "estimate_status",
             "estimate_note", "billed_cost_usd", "billing_status", "cumulative_estimated_cost_usd", "request_id", "error"]
RL_COLS = ["run_id", "topic_id", "attempt", "timestamp_utc", "event", "wait_s", "reason", "quota_source",
           "est_input_tokens", "est_output_tokens", "actual_tokens", "local_requests_last_minute",
           "local_tokens_last_minute", "local_requests_last_day", "local_tokens_last_day", "limit_rpm", "limit_rpd",
           "limit_tpm", "limit_tpd", "provider_limit_requests_day", "provider_remaining_requests_day",
           "provider_reset_requests_day_s", "provider_limit_tokens_minute", "provider_remaining_tokens_minute",
           "provider_reset_tokens_minute_s", "provider_retry_after_s"]
BILLING_STATUS = "not_determinable_from_api"
SLEEP, CLOCK, RNG = time.sleep, time.time, random.Random()   # tests replace them


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()


def usd(x):
    return "" if x is None else f"{Decimal(x).quantize(USD_Q):f}"


def jusd(x):
    return None if x is None else usd(x)


def naming_dir(root, run_id):
    return Path(root) / "data" / "processed" / f"sprint4_naming_{run_id}"


def prepare_dir(root, run_id, pv=PROMPT_VERSION):
    return naming_dir(root, run_id) / f"prepare_{pv}_{MODEL_SLUG}"


def tracked_dir(root, run_id):
    return Path(root) / "reports" / "sprint4_naming" / run_id


def cache_dir(root):
    return Path(root) / "cache" / "topic_naming" / PROVIDER


def rate_state_dir(root):
    return cache_dir(root) / "rate_state"


def prompt_path(root, pv=PROMPT_VERSION):
    return Path(root) / "prompts" / f"{pv}.txt"


def pricing_path(root):
    return Path(root) / "config" / "pricing" / f"{PROVIDER}_{MODEL_SLUG}.json"


def rate_limits_path(root):
    return Path(root) / "config" / "rate_limits" / f"{PROVIDER}_{MODEL_SLUG}.json"


# ---------- inputs ----------
def read_csv(path):
    return list(csv.DictReader(Path(path).open(encoding="utf-8", newline="")))


def load_inputs(root=ROOT, run_id=RUN_ID, expected=fz.EXPECTED):
    """Hash-verified snapshot + features, or SystemExit. Never reads the database or the intrusion key."""
    snap = tf.load_snapshot(root, run_id, expected)
    fd = tf.features_dir(root, run_id)
    if not (fd / "manifest.json").is_file():
        raise SystemExit(f"features missing: {fd} (run src/topic_features.py build first)")
    problems = tf.verify(root, run_id)
    if problems:
        raise SystemExit("features failed verification: " + "; ".join(problems))
    fm = json.loads((fd / "manifest.json").read_text(encoding="utf-8"))
    if fm["input_snapshot"]["data_fingerprint"] != snap["manifest"]["data_fingerprint"]:
        raise SystemExit("features were built from a different snapshot (data_fingerprint differs)")
    ids = [r["topic_id"] for r in sorted(read_csv(fd / "topic_ids.csv"), key=lambda r: int(r["row"]))]
    C = np.load(fd / "topic_centroids.npy", allow_pickle=False)
    if C.shape[0] != len(ids):
        raise SystemExit("topic_centroids.npy rows differ from topic_ids.csv")
    return {"snap": snap, "features_manifest": fm, "topic_ids": ids, "centroids": C,
            "features": {r["topic_id"]: r for r in read_csv(fd / "topic_features.csv")},
            "references": {r["topic_id"]: r for r in read_csv(fd / "reference_summary.csv")},
            "representatives": read_csv(fd / "representative_skills.csv"),
            "neighbours": read_csv(fd / "topic_neighbors.csv")}


# ---------- evidence ----------
def spread(items, k):
    """k items evenly spaced over an ordered list (all of them when there are k or fewer)."""
    if len(items) <= k:
        return list(items)
    idx = np.unique(np.round(np.linspace(0, len(items) - 1, k)).astype(int))
    return [items[i] for i in idx]


def band(x, q25, q75):
    return "low" if x <= q25 else "high" if x >= q75 else "medium"


def build_evidence(inp):
    """One record per topic (sorted topic_id): LLM payload + deterministic flags + metrics."""
    snap, ids, C = inp["snap"], inp["topic_ids"], inp["centroids"].astype(np.float64)
    V, row = snap["vectors"].astype(np.float64), snap["row"]
    links = {l["skill_key"]: l for l in snap["links"]}
    assigned = {t: [] for t in ids}
    for m in snap["memberships"]:
        if m["state"] == "assigned":
            assigned[m["topic_id"]].append(m["skill_key"])
    reps = {t: [] for t in ids}
    for r in sorted(inp["representatives"], key=lambda r: (r["topic_id"], int(r["rank"]))):
        reps[r["topic_id"]].append(r["skill_key"])
    nbrs = {t: [] for t in ids}
    for r in sorted(inp["neighbours"], key=lambda r: (r["topic_id"], int(r["rank"]))):
        nbrs[r["topic_id"]].append(r)
    F, Rf = inp["features"], inp["references"]
    cos_mean = np.array([float(F[t]["cos_mean"]) for t in ids])
    q25, q75 = float(np.percentile(cos_mean, 25)), float(np.percentile(cos_mean, 75))

    out = []
    for i, t in enumerate(ids):
        f, rf = F[t], Rf[t]
        n_a, n_w = int(f["n_assigned"]), int(f["n_weak"])
        if sorted(assigned[t]) != sorted(set(assigned[t])) or len(assigned[t]) != n_a:
            raise ValueError(f"{t}: assigned members differ from topic_features.csv")
        if not set(reps[t]) <= set(assigned[t]):
            raise ValueError(f"{t}: a representative skill is not an assigned member")
        members = sorted(assigned[t])
        cos = dict(zip(members, (V[[row[k] for k in members]] @ C[i]).tolist()))
        rest = sorted((k for k in members if k not in set(reps[t])), key=lambda k: (-round(cos[k], 12), k))
        extra = spread(rest, N_EXTRA)
        hints = Counter((links[k]["ref_label"], links[k]["source"]) for k in members
                        if k in links and links[k]["verdict"] == "known_skill" and links[k]["ref_label"])
        hints = sorted(hints.items(), key=lambda kv: (-kv[1], kv[0]))[:N_REF_HINTS]
        nb = nbrs[t][:N_NEIGHBOURS]
        coverage = float(rf["coverage_any"])
        max_nb = max((float(r["cosine"]) for r in nbrs[t]), default=0.0)
        transversal = f["is_transversal"] == "true"
        payload = {
            "topic_id": t,
            "size": {"assigned_members": n_a, "weak_members_not_shown": n_w},
            "cohesion_band": band(float(f["cos_mean"]), q25, q75),
            "transversal": transversal,
            "representative_skills": reps[t],
            "additional_members": extra,
            "reference_hints": [{"concept": lab, "source": src, "linked_members": n} for (lab, src), n in hints],
            "neighbour_topics": [{"topic_id": r["neighbour_id"], "similarity": round(float(r["cosine"]), 3),
                                  "top_skills": reps[r["neighbour_id"]][:N_NEIGHBOUR_SKILLS]} for r in nb],
        }
        flags = [x for x, on in (("low_cohesion", float(f["cos_mean"]) <= q25), ("weak_exceeds_assigned", n_w > n_a),
                                 ("no_reference_link", coverage == 0), ("near_duplicate_topic", max_nb >= tf.PAIR_FLAG)) if on]
        info = [x for x, on in (("transversal", transversal), ("low_reference_coverage", 0 < coverage < LOW_REF_COVERAGE)) if on]
        out.append({"topic_id": t, "payload": payload, "topic_quality_flags": flags, "info_flags": info,
                    "metrics": {"n_assigned": n_a, "n_weak": n_w, "cos_mean": float(f["cos_mean"]),
                                "cos_min": float(f["cos_min"]), "score_mean": float(f["score_mean"]),
                                "margin_median": float(f["margin_median"]), "coverage_any": coverage,
                                "max_neighbour_cosine": max_nb, "is_transversal": transversal}})
    return {"records": out, "cohesion_q25": q25, "cohesion_q75": q75}


def strata_overlap(records):
    """Do the bottom quartiles of score_mean (assignment confidence) and cos_mean (cohesion) pick the same topics?"""
    s = np.array([r["metrics"]["score_mean"] for r in records])
    c = np.array([r["metrics"]["cos_mean"] for r in records])
    a, b = set(np.flatnonzero(s <= np.percentile(s, 25))), set(np.flatnonzero(c <= np.percentile(c, 25)))
    return {"low_confidence": len(a), "low_cohesion": len(b), "overlap": len(a & b), "identical": a == b}


# ---------- pilot ----------
def stratum_rule(name, r):
    m, fl = r["metrics"], set(r["topic_quality_flags"])
    return {"transversal": m["is_transversal"],
            "low_cohesion": "low_cohesion" in fl and not m["is_transversal"],
            "near_duplicate": "near_duplicate_topic" in fl,
            "sparse_reference": m["coverage_any"] < LOW_REF_COVERAGE,
            "weak_heavy": m["n_weak"] > m["n_assigned"],
            "baseline": not fl and not m["is_transversal"]}[name]


def select_pilot(records, seed=PILOT_SEED, per=PILOT_PER_STRATUM):
    rng, chosen, rows = random.Random(seed), set(), []
    if per == 0:
        return rows
    for name, _ in PILOT_STRATA:
        cand = sorted(r["topic_id"] for r in records if stratum_rule(name, r) and r["topic_id"] not in chosen)
        if len(cand) < per:
            raise ValueError(f"pilot stratum {name}: only {len(cand)} candidates")
        for t in sorted(rng.sample(cand, per)):
            chosen.add(t)
            rows.append({"topic_id": t, "stratum": name, "candidates": len(cand)})
    by = {r["topic_id"]: r for r in records}
    sizes = np.array([r["metrics"]["n_assigned"] for r in records])
    t1, t2 = np.percentile(sizes, [100 / 3, 200 / 3])
    for p in rows:
        r = by[p["topic_id"]]
        n = r["metrics"]["n_assigned"]
        p.update({"also_matches": ";".join(s for s, _ in PILOT_STRATA if s != p["stratum"] and stratum_rule(s, r)),
                  "size_tercile": "small" if n <= t1 else "large" if n > t2 else "medium", "n_assigned": n,
                  "topic_quality_flags": ";".join(r["topic_quality_flags"])})
    return rows


# ---------- requests ----------
def user_message(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def request_settings():
    """Everything in the request besides system prompt and user message (part of the cache key)."""
    return {"provider": PROVIDER, "model": MODEL_ID, "temperature": TEMPERATURE, "max_completion_tokens": MAX_COMPLETION_TOKENS,
            "reasoning_effort": REASONING_EFFORT, "reasoning_format": REASONING_FORMAT, "response_format": RESPONSE_FORMAT}


def build_request(system, payload):
    user = user_message(payload)
    body = {"model": MODEL_ID, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": TEMPERATURE, "max_completion_tokens": MAX_COMPLETION_TOKENS,
            "reasoning_effort": REASONING_EFFORT, "reasoning_format": REASONING_FORMAT, "response_format": RESPONSE_FORMAT}
    key = sha(json.dumps({"settings": request_settings(), "prompt_sha256": sha(system), "user": user}, sort_keys=True))
    return {"topic_id": payload["topic_id"], "cache_key": key, "body": body}


def all_keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from all_keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from all_keys(v)


def validate_request(req, record, assigned, known_ids, secrets=()):
    """Offline checks of one request; returns a list of problems ([] = OK)."""
    p, t, body = [], record["topic_id"], req["body"]
    if set(body) != BODY_KEYS or body.get("model") != MODEL_ID:
        p.append("body: model not pinned or unexpected fields (fallback, tools, streaming, tracing?)")
    settings = {k: body.get(k) for k in BODY_KEYS - {"model", "messages"}}
    if settings != {k: v for k, v in request_settings().items() if k in settings}:
        p.append("body: temperature / max tokens / reasoning / response_format differ from the pinned settings")
    msgs = body.get("messages", [])
    if [m.get("role") for m in msgs] != ["system", "user"] or "JSON" not in str(msgs[0].get("content")):
        return p + ["messages: expected system + user; the system prompt must mention JSON (json_object mode)"]
    try:
        pl = json.loads(msgs[1]["content"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return p + ["user message is not valid JSON"]
    if pl != record["payload"] or pl.get("topic_id") != t or req["topic_id"] != t:
        p.append("user message differs from the evidence payload")
    reps, extra = pl.get("representative_skills", []), pl.get("additional_members", [])
    if len(reps) != min(N_REPS, len(assigned)) or len(set(reps)) != len(reps):
        p.append("representative_skills: wrong count or duplicates")
    if len(extra) > N_EXTRA or len(set(extra)) != len(extra) or set(extra) & set(reps):
        p.append("additional_members: too many, duplicates or overlap with representatives")
    if not set(reps + extra) <= set(assigned):
        p.append("a listed skill is not an assigned member of this topic")
    nb = pl.get("neighbour_topics", [])
    if len(nb) > N_NEIGHBOURS or any(n["topic_id"] == t or n["topic_id"] not in known_ids for n in nb):
        p.append("neighbour_topics: self, unknown id or too many")
    if len(pl.get("reference_hints", [])) > N_REF_HINTS:
        p.append("reference_hints: too many")
    if FORBIDDEN_KEYS & set(all_keys(pl)):
        p.append(f"forbidden keys in payload: {sorted(FORBIDDEN_KEYS & set(all_keys(pl)))}")
    if len(msgs[1]["content"]) / 4 > MAX_USER_TOKENS:
        p.append("user message too long")
    text = json.dumps(req)
    if any(s and s in text for s in secrets) or SECRET_RE.search(text):
        p.append("a secret value appears in the request")
    return p


# ---------- pricing and rate-limit configuration ----------
def check_date(p, today, probs):
    try:
        d = date.fromisoformat(p["verified_utc_date"])
        today = today or datetime.now(timezone.utc).date()
        if d > today:
            probs.append("verified_utc_date is in the future")
        elif (today - d).days > PRICING_MAX_AGE_DAYS:
            probs.append(f"verified {d} is older than {PRICING_MAX_AGE_DAYS} days: re-verify before a live run")
    except (KeyError, TypeError, ValueError):
        probs.append("verified_utc_date missing or not an ISO date")


def load_pricing(path, today=None):
    """Validated pricing snapshot (Decimal rates) or ValueError. Never guesses a price."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"pricing snapshot missing: {path}")
    raw = path.read_bytes()
    try:
        p = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"pricing snapshot is not JSON: {e}") from None
    probs = [f"missing {k}" for k in ("schema", "version", "provider", "model_id", "currency", "unit", "rates", "sources",
                                       "verified_utc_date") if k not in p]
    if probs:
        raise ValueError("pricing snapshot invalid: " + "; ".join(probs))
    if (p["provider"], p["model_id"]) != (PROVIDER, MODEL_ID):
        probs.append(f"snapshot is for {p['provider']}/{p['model_id']}, not {PROVIDER}/{MODEL_ID}")
    if (p["currency"], p["unit"]) != ("USD", "per_million_tokens"):
        probs.append("currency must be USD and unit per_million_tokens")
    rates = {}
    for k in RATE_KEYS:
        try:
            rates[k] = Decimal(str(p["rates"][k]))
            if not rates[k].is_finite() or rates[k] <= 0:
                probs.append(f"rate {k} must be a positive number")
        except (KeyError, InvalidOperation, TypeError):
            probs.append(f"rate {k} missing or not a number")
    if not p["sources"] or not all(str(s.get("url", "")).startswith(OFFICIAL_PREFIXES) for s in p["sources"]):
        probs.append("sources must be official Groq URLs")
    check_date(p, today, probs)
    if probs:
        raise ValueError("pricing snapshot invalid: " + "; ".join(probs))
    return {"data": p, "raw": raw, "sha256": sha(raw), "version": p["version"], "rates": rates}


def load_rate_limits(path, plan="free", today=None):
    """Validated rate-limit configuration for one plan, or ValueError."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"rate-limit configuration missing: {path}")
    raw = path.read_bytes()
    try:
        p = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"rate-limit configuration is not JSON: {e}") from None
    probs, limits, safety = [], {}, None
    if (p.get("provider"), p.get("model_id")) != (PROVIDER, MODEL_ID):
        probs.append(f"rate limits are for {p.get('provider')}/{p.get('model_id')}, not {PROVIDER}/{MODEL_ID}")
    cfg = p.get("plans", {}).get(plan)
    if cfg is None:
        probs.append(f"unknown plan {plan!r}")
    else:
        if not str(cfg.get("source", "")).startswith(OFFICIAL_PREFIXES):
            probs.append("plan source must be an official Groq URL")
        for k in ("rpm", "rpd", "tpm", "tpd", "input_tpm", "output_tpm"):
            v = cfg.get(k)
            if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v <= 0):
                probs.append(f"limit {k} must be a positive integer or null")
            limits[k] = v
    try:
        safety = float(p["safety_factor"])
        if not 0 < safety <= 1:
            probs.append("safety_factor must be in (0, 1]")
    except (KeyError, TypeError, ValueError):
        probs.append("safety_factor missing or not a number")
    check_date(p, today, probs)
    if probs:
        raise ValueError("rate-limit configuration invalid: " + "; ".join(probs))
    return {"plan": plan, "limits": limits, "safety": safety, "raw": raw, "sha256": sha(raw), "source": cfg["source"]}


# ---------- cost ----------
def is_count(x):
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def usage_tokens(usage):
    """(prompt, completion) token counts, or None when missing."""
    if not isinstance(usage, dict):
        return None
    pin, pout = usage.get("prompt_tokens"), usage.get("completion_tokens")
    return (pin, pout) if is_count(pin) and is_count(pout) else None


def price_usage(usage, pricing):
    """Tokens + Decimal estimated cost at published rates. Costs None (unknown) when usage is missing."""
    out = {"input_tokens": None, "output_tokens": None, "reasoning_tokens": None, "cached_input_tokens": None,
           "total_tokens": None, "estimated_input_cost": None, "estimated_output_cost": None, "estimated_cost": None}
    tok = usage_tokens(usage)
    if tok is None:
        return {**out, "estimate_status": "missing_usage", "estimate_note": "response carried no valid token usage"}
    pin, pout = tok
    cached = ((usage.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0
    reasoning = ((usage.get("completion_tokens_details") or {}).get("reasoning_tokens")) or 0
    r = pricing["rates"]
    ic, oc = Decimal(pin) * r["input"] / MTOK, Decimal(pout) * r["output"] / MTOK
    note = "published-rate estimate"
    if cached:
        note += "; cached input priced at the full input rate (no verified cached rate): upper bound"
    return {**out, "input_tokens": pin, "output_tokens": pout, "reasoning_tokens": reasoning, "cached_input_tokens": cached,
            "total_tokens": usage.get("total_tokens") if is_count(usage.get("total_tokens")) else pin + pout,
            "estimated_input_cost": ic, "estimated_output_cost": oc, "estimated_cost": ic + oc,
            "estimate_status": "estimated", "estimate_note": note}


def estimate_input_tokens(body, chars_per_token):
    chars = sum(len(m["content"]) for m in body["messages"])
    return math.ceil(chars / chars_per_token) + REQUEST_OVERHEAD_TOKENS


def max_request_cost(body, pricing):
    """Upper-bound ESTIMATE for one attempt: conservative input tokens + max_completion_tokens output."""
    r = pricing["rates"]
    return (Decimal(estimate_input_tokens(body, CHARS_PER_TOKEN_UPPER)) * r["input"]
            + Decimal(body["max_completion_tokens"]) * r["output"]) / MTOK


def offline_estimate(reqs, selected_ids, pricing=None, limits=None):
    """Token, cost and quota estimates without any API call (one attempt per topic, no cache hits)."""
    def one(rs):
        typ = sum(estimate_input_tokens(q["body"], CHARS_PER_TOKEN_TYPICAL) + TYPICAL_OUTPUT_TOKENS for q in rs)
        up = sum(estimate_input_tokens(q["body"], CHARS_PER_TOKEN_UPPER) + MAX_COMPLETION_TOKENS for q in rs)
        e = {"topics": len(rs), "requests": len(rs), "tokens_typical": typ, "tokens_upper": up}
        if pricing:
            r = pricing["rates"]
            e["estimated_cost_typical_usd"] = usd(sum(
                ((Decimal(estimate_input_tokens(q["body"], CHARS_PER_TOKEN_TYPICAL)) * r["input"]
                  + Decimal(TYPICAL_OUTPUT_TOKENS) * r["output"]) / MTOK for q in rs), Decimal(0)))
            e["estimated_cost_upper_usd"] = usd(sum((max_request_cost(q["body"], pricing) for q in rs), Decimal(0)))
        if limits and rs:
            L, s = limits["limits"], limits["safety"]
            cap = lambda k: None if L.get(k) is None else max(1, int(L[k] * s))
            per_req_upper = up / len(rs)
            per_min = min((x for x in (cap("rpm"), cap("tpm") and int(cap("tpm") // per_req_upper)) if x is not None),
                          default=None)
            e["quota"] = {"plan": limits["plan"], "safety_factor": s,
                          "share_of_daily_requests": round(len(rs) / cap("rpd"), 4) if cap("rpd") else None,
                          "share_of_daily_tokens_typical": round(typ / cap("tpd"), 4) if cap("tpd") else None,
                          "share_of_daily_tokens_upper": round(up / cap("tpd"), 4) if cap("tpd") else None,
                          "days_needed_typical": math.ceil(typ / cap("tpd")) if cap("tpd") else 1,
                          "days_needed_upper": math.ceil(up / cap("tpd")) if cap("tpd") else 1,
                          "requests_per_minute_planning_upper": per_min,
                          "minutes_of_requests_upper": math.ceil(len(rs) / per_min) if per_min else None}
        return e
    sel = set(selected_ids)
    return {"selected": one([q for q in reqs if q["topic_id"] in sel]), "full_run": one(reqs),
            "pricing_version": pricing["version"] if pricing else None,
            "assumptions": {"chars_per_token_typical": CHARS_PER_TOKEN_TYPICAL, "chars_per_token_upper": CHARS_PER_TOKEN_UPPER,
                            "overhead_tokens": REQUEST_OVERHEAD_TOKENS, "typical_output_tokens": TYPICAL_OUTPUT_TOKENS,
                            "upper_output_tokens": MAX_COMPLETION_TOKENS, "no_local_cache_hits": True, "no_retries": True}}


class Ledger:
    """Cumulative ESTIMATED spend (published rates) + stop reason. One instance per generate run."""

    def __init__(self, budget):
        self.budget, self.spent, self.stop_reason = Decimal(budget), Decimal(0), None

    def remaining(self):
        return self.budget - self.spent

    def allow(self, estimate):
        if self.stop_reason:
            return False
        if self.spent + estimate > self.budget:
            self.stop_reason = (f"budget: next request estimated up to ${usd(estimate)}, remaining ${usd(self.remaining())} "
                                f"of ${usd(self.budget)}")
            return False
        return True

    def record(self, priced):
        if priced["estimate_status"] == "estimated":
            self.spent += priced["estimated_cost"]
            if self.spent > self.budget and not self.stop_reason:
                self.stop_reason = f"budget: estimated spend ${usd(self.spent)} exceeded ${usd(self.budget)} after a response"
        elif priced["estimate_status"] == "missing_usage" and not self.stop_reason:
            self.stop_reason = f"usage missing: {priced['estimate_note']}; live requests stopped until resolved"


# ---------- rate limiting ----------
def parse_duration(s):
    """Groq reset values such as '2m59.56s', '7.66s', '120ms', '1h2m' -> seconds (None if unreadable)."""
    if s is None:
        return None
    s = str(s).strip()
    try:
        return float(s)
    except ValueError:
        pass
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m(?!s))?(?:(\d+(?:\.\d+)?)s)?(?:(\d+(?:\.\d+)?)ms)?", s)
    if not s or not m or not any(m.groups()):
        return None
    h, mi, se, ms = (float(g) if g else 0.0 for g in m.groups())
    return h * 3600 + mi * 60 + se + ms / 1000


def parse_int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def read_rate_headers(headers):
    """Groq: *-requests = per DAY, *-tokens = per MINUTE (console.groq.com/docs/rate-limits)."""
    h = {str(k).lower(): v for k, v in (headers or {}).items()}
    return {"limit_requests_day": parse_int(h.get("x-ratelimit-limit-requests")),
            "remaining_requests_day": parse_int(h.get("x-ratelimit-remaining-requests")),
            "reset_requests_day_s": parse_duration(h.get("x-ratelimit-reset-requests")),
            "limit_tokens_minute": parse_int(h.get("x-ratelimit-limit-tokens")),
            "remaining_tokens_minute": parse_int(h.get("x-ratelimit-remaining-tokens")),
            "reset_tokens_minute_s": parse_duration(h.get("x-ratelimit-reset-tokens")),
            "retry_after_s": parse_duration(h.get("retry-after"))}


TPD_MSG_RE = re.compile(r"tokens per day \(TPD\):\s*Limit (\d+),\s*Used (\d+),\s*Requested (\d+)", re.I)
RPD_MSG_RE = re.compile(r"requests per day \(RPD\):\s*Limit (\d+),\s*Used (\d+),\s*Requested (\d+)", re.I)
TRY_AGAIN_RE = re.compile(r"try again in\s+((?:\d+(?:\.\d+)?(?:ms|h|m|s))+)", re.I)
QUOTA_SOURCES = {
    "provider_headers": "Groq x-ratelimit-* response headers (requests = per day, tokens = per minute)",
    "provider_retry_after": "Groq retry-after header on HTTP 429",
    "provider_429_message": "parsed from a Groq 429 error message (message format is not documented by Groq; best effort)",
    "local_estimate": "this machine's own request log, rolling windows; a conservative fallback, NOT Groq's reset rule "
                      "(Groq does not document how daily limits reset, and its limits are per organization)",
}


def parse_quota_message(message):
    """Daily quota details from a 429 message, e.g. 'Rate limit reached ... on tokens per day (TPD): Limit 200000,
    Used 199500, Requested 1900. Please try again in 7m12.5s.' Returns {} when the text has no such details."""
    out, m_try = {}, TRY_AGAIN_RE.search(message or "")
    for kind, rx in (("tokens_day", TPD_MSG_RE), ("requests_day", RPD_MSG_RE)):
        m = rx.search(message or "")
        if m:
            out[kind] = {"limit": int(m.group(1)), "used": int(m.group(2)), "requested": int(m.group(3)),
                         "retry_in_s": parse_duration(m_try.group(1)) if m_try else None}
    return out


class RateLimiter:
    """Request / token limiter. Provider-reported quota (Groq headers, 429 details) is preferred; the local sliding
    windows over this machine's request log (60 s and 24 h) are a conservative fallback and are labelled as estimates.
    events = (time, input tokens, output tokens). check() -> (action, seconds, reason, source)."""

    def __init__(self, limits, safety, clock=None, sleep=None, history=(), max_wait=MAX_LIMITER_WAIT_S):
        self.configured, self.limits, self.safety = dict(limits), dict(limits), float(safety)
        self.clock, self.sleep, self.max_wait = clock or CLOCK, sleep or SLEEP, max_wait
        self.events = deque(sorted(history))
        self.provider, self.provider_daily = {}, {}   # headers snapshot / 429-message details, absolute reset times
        self.throttle_wait_s, self.daily_exhaustion_events, self.header_adopted = 0.0, 0, {}
        self.last_stop = None

    def cap(self, k):
        v = self.limits.get(k)
        return None if v is None else max(1, int(v * self.safety))

    def usage(self, now=None):
        now = self.clock() if now is None else now
        day = [e for e in self.events if e[0] > now - DAY_S]
        minute = [e for e in day if e[0] > now - MINUTE_S]
        return {"requests_last_minute": len(minute), "tokens_last_minute": sum(e[1] + e[2] for e in minute),
                "requests_last_day": len(day), "tokens_last_day": sum(e[1] + e[2] for e in day),
                "_minute": minute, "_day": day}

    @staticmethod
    def _free_at(events, size, used, need, cap, span, now):
        """Seconds until enough of `events` leave a window of `span` s for used + need <= cap (None if never)."""
        for e in events:
            if used + need <= cap:
                break
            used -= size(e)
            if used + need <= cap:
                return e[0] + span - now
        return 0.0 if used + need <= cap else None

    def check(self, est_in, est_out):
        now, est = self.clock(), est_in + est_out
        u, p = self.usage(now), self.provider
        minute, day = u["_minute"], u["_day"]
        stop_or_wait = lambda left: "stop" if left is None or left > self.max_wait else "wait"
        # daily requests: provider headers first; the local 24 h window only when Groq reported nothing
        if p.get("remaining_requests_day") is not None:
            at = p.get("reset_requests_day_at")
            available = p["remaining_requests_day"] if at is None or now < at else max(p["remaining_requests_day"], 1)
            if available < 1:
                left = None if at is None else at - now
                return (stop_or_wait(left), left, f"daily request limit (provider-reported): 0 requests remaining"
                        + (f", x-ratelimit-reset-requests in {left:.0f}s" if left is not None else ", no reset time"),
                        "provider_headers")
        elif self.cap("rpd") and u["requests_last_day"] + 1 > self.cap("rpd"):
            left = self._free_at(day, lambda e: 1, len(day), 1, self.cap("rpd"), DAY_S, now)
            return ("stop", left, f"daily request limit (local estimate): {len(day)} of {self.cap('rpd')} requests in "
                    f"this machine's last 24 h; Groq's reset rule is not documented", "local_estimate")
        for kind in ("requests_day", "tokens_day"):
            d = self.provider_daily.get(kind)
            if d and d.get("retry_at") is not None and now < d["retry_at"]:
                left = d["retry_at"] - now
                return (stop_or_wait(left), left, f"daily {kind.split('_')[0][:-1]} limit (provider-reported in a 429 "
                        f"message): used {d['used']} of {d['limit']}, retry in {left:.0f}s", "provider_429_message")
        # daily tokens: Groq sends no TPD header, so the local estimate is the only pre-request check
        if self.cap("tpd") and u["tokens_last_day"] + est > self.cap("tpd"):
            left = self._free_at(day, lambda e: e[1] + e[2], u["tokens_last_day"], est, self.cap("tpd"), DAY_S, now)
            return ("stop", left, f"daily token limit (local estimate): {u['tokens_last_day']} + {est} > {self.cap('tpd')} "
                    f"tokens in this machine's last 24 h; Groq reports no TPD header and does not document the reset",
                    "local_estimate")
        waits = []
        if self.cap("rpm") and len(minute) + 1 > self.cap("rpm"):
            waits.append((minute[len(minute) - self.cap("rpm")][0] + MINUTE_S - now,
                          f"RPM (local estimate): {len(minute)} requests in the last minute", "local_estimate"))
        for key, size, need in (("tpm", lambda e: e[1] + e[2], est), ("input_tpm", lambda e: e[1], est_in),
                                ("output_tpm", lambda e: e[2], est_out)):
            cap = self.cap(key)
            if not cap:
                continue
            if need > cap:
                return "stop", None, f"{key.upper()}: one request needs {need} tokens, above the per-minute cap {cap}", \
                    "local_estimate"
            w = self._free_at(minute, size, sum(size(e) for e in minute), need, cap, MINUTE_S, now)
            if w:
                waits.append((w, f"{key.upper()} (local estimate): tokens in the last minute + {need} > {cap}", "local_estimate"))
        if p.get("remaining_tokens_minute") is not None and p["remaining_tokens_minute"] < est:
            at = p.get("reset_tokens_minute_at")
            if at is not None and at > now:
                waits.append((at - now, f"TPM (provider-reported): {p['remaining_tokens_minute']} tokens left this minute "
                              f"< {est}", "provider_headers"))
        if waits:
            w, why, src = max(waits)
            return "wait", max(w, 0.0) + 0.05, why, src
        return "go", 0.0, "", ""

    def acquire(self, est_in, est_out, log):
        """Wait (bounded) until a request may go. Returns (seconds waited, stop reason or None)."""
        waited = 0.0
        for _ in range(1000):
            action, w, why, src = self.check(est_in, est_out)
            log("throttle_wait" if action == "wait" else "quota_stop" if action == "stop" else "go", w, why, src)
            if action == "go":
                return waited, None
            if action == "wait" and waited + w > self.max_wait:
                action, why = "stop", f"waiting {waited + w:.0f}s would exceed {self.max_wait:.0f}s: {why}"
            if action == "stop":
                self.note_stop(why, src, w)
                return waited, why
            self.sleep(w)
            waited += w
            self.throttle_wait_s += w
        self.note_stop("limiter did not converge", "", None)
        return waited, "limiter did not converge"

    def note_stop(self, why, source, available_in_s):
        if why.startswith("daily"):
            self.daily_exhaustion_events += 1
        now = self.clock()
        self.last_stop = {"reason": why, "source": source, "available_in_s": available_in_s,
                          "available_at_utc": None if available_in_s is None else
                          datetime.fromtimestamp(now + available_in_s, timezone.utc).isoformat(timespec="seconds"),
                          "available_at_is": "provider-reported" if source.startswith("provider") else
                          "local estimate" if source == "local_estimate" else "unknown"}

    def record(self, in_tokens, out_tokens, headers):
        """Count one request (tokens actually used; 0 when unknown) and keep Groq's header values as provider data."""
        now = self.clock()
        self.events.append((now, int(in_tokens or 0), int(out_tokens or 0)))
        h = read_rate_headers(headers)
        if any(v is not None for k, v in h.items() if k != "retry_after_s"):
            self.provider = {"observed_at": now, **{k: h[k] for k in ("limit_requests_day", "remaining_requests_day",
                                                                      "limit_tokens_minute", "remaining_tokens_minute")},
                             "reset_requests_day_at": None if h["reset_requests_day_s"] is None else now + h["reset_requests_day_s"],
                             "reset_tokens_minute_at": None if h["reset_tokens_minute_s"] is None else now + h["reset_tokens_minute_s"]}
        for hk, lk in (("limit_requests_day", "rpd"), ("limit_tokens_minute", "tpm")):
            if h[hk] is not None:
                self.limits[lk] = h[hk]
                self.header_adopted[lk] = h[hk]
        return h

    def note_429(self, message, retry_after):
        """Keep daily-quota details a 429 message reveals (provider-reported); returns them."""
        now, found = self.clock(), parse_quota_message(message)
        for kind, d in found.items():
            wait = d["retry_in_s"] if d["retry_in_s"] is not None else retry_after
            self.provider_daily[kind] = {**d, "observed_at": now, "retry_at": None if wait is None else now + wait}
        return found

    def export_state(self):
        return {"provider": self.provider, "provider_daily": self.provider_daily}

    def load_state(self, d, now):
        """Restore provider-reported quota from an earlier run (ignored when older than a day)."""
        prov = (d or {}).get("provider") or {}
        if prov.get("observed_at") and prov["observed_at"] > now - DAY_S:
            self.provider = prov
            for hk, lk in (("limit_requests_day", "rpd"), ("limit_tokens_minute", "tpm")):
                if prov.get(hk) is not None:
                    self.limits[lk] = prov[hk]
                    self.header_adopted[lk] = prov[hk]
        self.provider_daily = {k: v for k, v in ((d or {}).get("provider_daily") or {}).items()
                               if v.get("observed_at", 0) > now - DAY_S}

    def report(self):
        """Provider-reported and locally estimated quota, labelled separately (times in UTC)."""
        now = self.clock()
        ts = lambda t: None if t is None else datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")
        p = self.provider
        u = {k: v for k, v in self.usage(now).items() if not k.startswith("_")}
        return {
            "provider_reported": {
                "source": QUOTA_SOURCES["provider_headers"], "observed_at_utc": ts(p.get("observed_at")),
                "requests_per_day": {"limit": p.get("limit_requests_day"), "remaining": p.get("remaining_requests_day"),
                                     "reset_at_utc": ts(p.get("reset_requests_day_at"))},
                "tokens_per_minute": {"limit": p.get("limit_tokens_minute"), "remaining": p.get("remaining_tokens_minute"),
                                      "reset_at_utc": ts(p.get("reset_tokens_minute_at"))},
                "tokens_per_day": "not reported in headers by Groq",
                "from_429_messages": {k: {**{x: v[x] for x in ("limit", "used", "requested")},
                                          "retry_at_utc": ts(v.get("retry_at")), "source": QUOTA_SOURCES["provider_429_message"]}
                                      for k, v in self.provider_daily.items()}},
            "local_estimate": {"source": QUOTA_SOURCES["local_estimate"], **u,
                               "caps_after_safety": {k: self.cap(k) for k in ("rpm", "rpd", "tpm", "tpd")},
                               "used_for": "RPD only when Groq reported nothing; TPD always (no provider TPD header); "
                                           "RPM/TPM together with the provider TPM header"},
        }


def backoff_seconds(attempt, rng=None):
    rng = rng or RNG
    return min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2 ** (attempt - 1)) * (1 + rng.uniform(0, BACKOFF_JITTER))


def load_history(path, now):
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
            if e["t"] > now - DAY_S:
                out.append((float(e["t"]), int(e["in"]), int(e["out"])))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return out


# ---------- output validation ----------
def norm(s):
    return " ".join(re.sub(r"[^a-z0-9+#]+", " ", s.lower()).split())


def parse_answer(content):
    """Structured answer or ValueError (structural problem -> failed row, never cached)."""
    out = json.loads(content) if isinstance(content, str) else content
    if not isinstance(out, dict):
        raise ValueError("answer is not a JSON object")
    missing = [k for k in OUTPUT_KEYS if k not in out]
    if missing:
        raise ValueError(f"missing keys: {missing}")
    for k in ("provisional_name", "description", "confidence_reason"):
        if not isinstance(out[k], str) or not out[k].strip():
            raise ValueError(f"{k} must be a non-empty string")
    if not isinstance(out["supporting_skills"], list) or not all(isinstance(s, str) for s in out["supporting_skills"]):
        raise ValueError("supporting_skills must be a list of strings")
    if out["confidence"] not in CONFIDENCE:
        raise ValueError(f"confidence must be one of {CONFIDENCE}")
    return {k: (out[k].strip() if isinstance(out[k], str) else [s.strip() for s in out[k]]) for k in OUTPUT_KEYS}


def name_flags(ans, payload):
    """Content checks on one valid answer. Returns (supporting skills kept, flags)."""
    allowed = set(payload["representative_skills"]) | set(payload["additional_members"])
    kept = [s for s in dict.fromkeys(ans["supporting_skills"]) if s in allowed]
    words = norm(ans["provisional_name"]).split()
    member_names = {norm(s) for s in allowed}
    flags = []
    if len(words) > NAME_WORDS[1] or (len(words) < NAME_WORDS[0] and " ".join(words) not in member_names):
        flags.append("name_length")
    if set(words) & GENERIC_WORDS:
        flags.append("generic_name")
    if len(kept) < len(ans["supporting_skills"]):
        flags.append("unsupported_supporting_skills")
    if len(kept) < SUPPORT_RANGE[0]:
        flags.append("few_supporting_skills")
    if len(ans["description"].split()) > DESC_MAX_WORDS:
        flags.append("description_too_long")
    return kept, flags


def cross_name_flags(rows):
    """duplicate_name / near_duplicate_name across all ok rows (normalised exact match / token Jaccard)."""
    ok = [r for r in rows if r["status"] == "ok"]
    toks = {r["topic_id"]: set(norm(r["provisional_name"]).split()) for r in ok}
    extra = {r["topic_id"]: [] for r in ok}
    for i, a in enumerate(ok):
        for b in ok[i + 1:]:
            ta, tb = toks[a["topic_id"]], toks[b["topic_id"]]
            if norm(a["provisional_name"]) == norm(b["provisional_name"]):
                kind = "duplicate_name"
            elif ta and tb and len(ta & tb) / len(ta | tb) >= NEAR_DUP_JACCARD:
                kind = "near_duplicate_name"
            else:
                continue
            extra[a["topic_id"]].append(f"{kind}:{b['topic_id']}")
            extra[b["topic_id"]].append(f"{kind}:{a['topic_id']}")
    return extra


def finalise(rows):
    """Add cross-topic name flags, then review_required / review_reason (deterministic)."""
    extra = cross_name_flags(rows)
    for r in rows:
        nf = r["name_flags"] + extra.get(r["topic_id"], [])
        r["name_flags"] = nf
        reasons = list(r["topic_quality_flags"]) + nf
        if r["status"] == "failed":
            reasons.append("generation_failed")
        elif r["status"] == "not_attempted":
            reasons.append("not_attempted")
        elif r["llm_confidence"] == "low":
            reasons.append("llm_confidence_low")
        r["review_required"], r["review_reason"] = bool(reasons), ";".join(reasons)
    return rows


def check_results(rows, expected_ids):
    """Every expected topic exactly once, with an explicit status and provenance; [] = OK."""
    p, ids = [], [r["topic_id"] for r in rows]
    if len(ids) != len(set(ids)):
        p.append("duplicate topic IDs")
    if set(ids) != set(expected_ids):
        p.append(f"missing {sorted(set(expected_ids) - set(ids))[:5]} / unexpected {sorted(set(ids) - set(expected_ids))[:5]}")
    for r in rows:
        if r["status"] not in STATUSES:
            p.append(f"{r['topic_id']}: bad status {r['status']!r}")
        if r["status"] != "ok" and not r.get("error"):
            p.append(f"{r['topic_id']}: {r['status']} without error")
        need = PROVENANCE_FIELDS if r["status"] == "ok" else tuple(f for f in PROVENANCE_FIELDS if f != "served_model")
        if any(not r.get(f) for f in need):
            p.append(f"{r['topic_id']}: missing provenance")
        if r["status"] == "ok" and not r["provisional_name"]:
            p.append(f"{r['topic_id']}: ok without a name")
    return p


# ---------- files / provenance ----------
def jsonl(rows):
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str) + "\n" for r in rows).encode("utf-8")


def cell(v):
    if isinstance(v, list):
        return ";".join(map(str, v))
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Decimal):
        return usd(v)
    if isinstance(v, float):
        return f"{v:.3f}"
    return "" if v is None else v


def csv_bytes(rows, cols):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow([cell(r[c]) for c in cols])
    return buf.getvalue().encode("utf-8")


def git(root, *a):
    try:
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def code_version(root):
    head, dirty = git(root, "rev-parse", "HEAD"), git(root, "status", "--porcelain")
    return {"commit": head and head + ("+uncommitted" if dirty else ""),
            "script_sha256": sha(Path(__file__).read_bytes()), "numpy": np.__version__,
            "python": platform.python_version(), "platform": platform.machine()}


def provenance_gaps(root, inp, overlap):
    gaps = []
    for label, m in (("input snapshot", inp["snap"]["manifest"].get("source_commit")),
                     ("topic features", inp["features_manifest"]["code"].get("commit"))):
        c = (m or "").split("+")[0]
        if not c or git(root, "cat-file", "-e", c + "^{commit}") is None:
            gaps.append(f"{label} manifest records source commit {m!r}, which is not in this repository's history")
    fc, here = inp["features_manifest"]["code"], {"python": platform.python_version(), "numpy": np.__version__}
    if (fc.get("python"), fc.get("numpy")) != (here["python"], here["numpy"]):
        gaps.append(f"topic features were built with Python {fc.get('python')} / numpy {fc.get('numpy')}; this run "
                    f"uses Python {here['python']} / numpy {here['numpy']} (outputs still hash-verified)")
    if overlap["identical"]:
        gaps.append(f"intrusion v2 'low confidence' and 'low cohesion' bottom quartiles are the same {overlap['overlap']} "
                    "topics (score_mean and cos_mean both measure cosine to centroid): one signal, not two; the "
                    "intrusion result is single-reviewer and exploratory, so it is not used to name or flag topics")
    gaps.append("ESCO / O*NET purity is unavailable (snapshot has no broader-group data); reference hints are "
                "per-skill matcher output and can be wrong")
    return gaps


def model_manifest():
    return {"provider": PROVIDER, "model_id": MODEL_ID, "api": f"{API_URL} (REST, no SDK retries)",
            **{k: v for k, v in request_settings().items() if k not in ("provider", "model")},
            "fallback": None, "tracing": None, "model_status": "Preview (may be discontinued at short notice)"}


def load_optional(fn, *a):
    try:
        return fn(*a), None
    except ValueError as e:
        return None, str(e)


def prepare(root=ROOT, run_id=RUN_ID, expected=fz.EXPECTED, write=True, secrets=(), pilot_per=PILOT_PER_STRATUM,
            today=None, plan="free"):
    pdir, tdir = prepare_dir(root, run_id), tracked_dir(root, run_id) / prepare_dir(root, run_id).name
    if write and (pdir.exists() or tdir.exists()):
        raise FileExistsError(f"{pdir.name} already exists; never overwritten")
    pp = prompt_path(root)
    system = pp.read_text(encoding="utf-8")
    inp = load_inputs(root, run_id, expected)
    ev = build_evidence(inp)
    if jsonl(build_evidence(inp)["records"]) != jsonl(ev["records"]):
        raise ValueError("evidence is not deterministic")
    records = ev["records"]
    assigned = {t: set() for t in inp["topic_ids"]}
    for m in inp["snap"]["memberships"]:
        if m["state"] == "assigned":
            assigned[m["topic_id"]].add(m["skill_key"])
    known = set(inp["topic_ids"])
    reqs = [build_request(system, r["payload"]) for r in records]
    problems = {r["topic_id"]: validate_request(q, r, assigned[r["topic_id"]], known, secrets) for q, r in zip(reqs, records)}
    problems = {t: p for t, p in problems.items() if p}
    if len(records) != len(inp["topic_ids"]) or len({r["topic_id"] for r in records}) != len(records):
        problems["_all"] = ["evidence does not cover every topic exactly once"]
    pilot = select_pilot(records, per=pilot_per)
    overlap = strata_overlap(records)
    pricing, pricing_err = load_optional(load_pricing, pricing_path(root), today)
    limits, limits_err = load_optional(load_rate_limits, rate_limits_path(root), plan, today)
    estimate = offline_estimate(reqs, [p["topic_id"] for p in pilot], pricing, limits)
    estimate = {"pilot": estimate.pop("selected"), **estimate, "pricing_error": pricing_err, "rate_limits_error": limits_err}
    sizes = [len(q["body"]["messages"][1]["content"]) for q in reqs]
    flag_rows = [{"topic_id": r["topic_id"], "topic_quality_flags": r["topic_quality_flags"], "info_flags": r["info_flags"],
                  **{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r["metrics"].items()}} for r in records]
    files = {"evidence.jsonl": jsonl(records), "requests.jsonl": jsonl(reqs),
             "topic_flags.csv": csv_bytes(flag_rows, list(flag_rows[0])),
             "pilot_topics.csv": csv_bytes(pilot, PILOT_COLS)}
    hashes = {f: sha(b) for f, b in sorted(files.items())}
    manifest = {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "stage": "prepare",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs": {"snapshot_fingerprint": inp["snap"]["manifest"]["data_fingerprint"],
                   "features_fingerprint": inp["features_manifest"]["data_fingerprint"]},
        "prompt": {"version": PROMPT_VERSION, "path": pp.relative_to(root).as_posix(), "sha256": sha(system)},
        "model": model_manifest(),
        "pricing_snapshot": pricing and {"version": pricing["version"], "sha256": pricing["sha256"],
                                         "path": pricing_path(root).relative_to(root).as_posix()},
        "rate_limits": limits and {"plan": limits["plan"], "limits": limits["limits"], "safety": limits["safety"],
                                   "sha256": limits["sha256"], "path": rate_limits_path(root).relative_to(root).as_posix()},
        "offline_estimate": estimate,
        "code": code_version(root),
        "settings": {"n_representatives": N_REPS, "n_additional_members": N_EXTRA, "additional_members_selection":
                     "assigned non-representative members sorted by cosine to centroid desc, evenly spaced picks",
                     "n_reference_hints": N_REF_HINTS, "n_neighbours": N_NEIGHBOURS, "n_neighbour_skills": N_NEIGHBOUR_SKILLS,
                     "cohesion_band": {"q25": ev["cohesion_q25"], "q75": ev["cohesion_q75"], "metric": "cos_mean"},
                     "review_flags": list(REVIEW_FLAGS), "near_duplicate_cosine": tf.PAIR_FLAG,
                     "low_reference_coverage": LOW_REF_COVERAGE, "max_user_tokens_estimate": MAX_USER_TOKENS},
        "pilot": {"seed": PILOT_SEED, "per_stratum": pilot_per, "strata": [{"name": n, "rule": r} for n, r in PILOT_STRATA],
                  "topics": [{k: p[k] for k in ("topic_id", "stratum", "also_matches", "size_tercile")} for p in pilot]},
        "counts": {"topics": len(records), "requests": len(reqs), "request_problems": sum(map(len, problems.values())),
                   "pilot": len(pilot), "review_flagged": sum(bool(r["topic_quality_flags"]) for r in records),
                   **{f: sum(f in r["topic_quality_flags"] for r in records) for f in REVIEW_FLAGS},
                   **{f: sum(f in r["info_flags"] for r in records) for f in ("transversal", "low_reference_coverage")},
                   "user_message_chars": {"min": min(sizes), "median": int(np.median(sizes)), "max": max(sizes)}},
        "intrusion_strata_overlap": overlap,
        "provenance_gaps": provenance_gaps(root, inp, overlap),
        "excluded": "no LLM output, no intrusion-test data, no current topic labels, no weak members, no posting text",
        "files_sha256": hashes,
        "data_fingerprint": sha("\n".join(f"{k}:{v}" for k, v in hashes.items())),
    }
    if write and not problems:
        pdir.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=f".{pdir.name}.", dir=pdir.parent))
        for n, b in files.items():
            (tmp / n).write_bytes(b)
        text = json.dumps(manifest, indent=1, sort_keys=True) + "\n"
        (tmp / "manifest.json").write_text(text, encoding="utf-8")
        os.rename(tmp, pdir)
        tdir.mkdir(parents=True, exist_ok=True)
        with (tdir / "manifest.json").open("x", encoding="utf-8") as fh:
            fh.write(text)
    return {"manifest": manifest, "records": records, "requests": reqs, "pilot": pilot, "problems": problems}


def verify(root=ROOT, run_id=RUN_ID):
    d = prepare_dir(root, run_id)
    tm = tracked_dir(root, run_id) / d.name / "manifest.json"
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    p = [f"{f}: hash differs" for f, h in m["files_sha256"].items() if not (d / f).is_file() or sha((d / f).read_bytes()) != h]
    if not tm.is_file() or tm.read_text(encoding="utf-8") != (d / "manifest.json").read_text(encoding="utf-8"):
        p.append("tracked manifest copy missing or different")
    return p


# ---------- Groq backend ----------
class ApiErr(Exception):
    def __init__(self, status, message, retry_after=None, usage=None, request_id=None, headers=None, body=None):
        super().__init__(message)
        self.status, self.message, self.retry_after = status, message, retry_after
        self.usage, self.request_id, self.headers = usage, request_id, headers or {}
        e = (body or {}).get("error") if isinstance(body, dict) else None
        e = e if isinstance(e, dict) else {}
        self.error_type, self.error_code, self.failed_generation = e.get("type"), e.get("code"), bool(e.get("failed_generation"))

    @property
    def error_class(self):
        """rate_limit / transient (retried) | content (this topic fails) | config (stop the run) | other (topic fails)."""
        if self.status == 429:
            return "rate_limit"
        if self.status in RETRYABLE:
            return "transient"
        if (self.status == 400 and (self.error_code in CONTENT_ERROR_CODES or self.failed_generation)) or self.status == 422:
            return "content"
        if self.status in CONFIG_ERROR_STATUSES:
            return "config"
        return "other"

    @property
    def retryable(self):
        return self.error_class in ("rate_limit", "transient")


class GroqBackend:
    """Groq REST API over one HTTP session. send(body) -> dict(content, finish_reason, model, usage, request_id,
    headers). No retries here: generate() retries and logs every attempt."""

    def __init__(self, session=None, key=None):
        import requests
        if key is None:
            from dotenv import dotenv_values
            key = os.getenv("GROQ_API_KEY") or dotenv_values(ROOT / ".env").get("GROQ_API_KEY")
        if not key:
            raise SystemExit("GROQ_API_KEY is missing")
        self.session, self.headers = session or requests.Session(), {"Authorization": f"Bearer {key}"}
        self._exc = requests.RequestException

    def check_model(self):
        """Live pre-flight: GET /models/<id> must return this model, active."""
        try:
            r = self.session.get(f"{API_URL}/models/{MODEL_ID}", headers=self.headers, timeout=30)
        except self._exc as e:
            return False, f"model check failed: {type(e).__name__}"
        if r.status_code != 200:
            return False, f"model check HTTP {r.status_code}"
        d = r.json()
        if d.get("id") != MODEL_ID or d.get("active") is False:
            return False, f"model {MODEL_ID} not available (id={d.get('id')!r}, active={d.get('active')!r})"
        return True, f"model {MODEL_ID} available (context_window={d.get('context_window')})"

    def send(self, body):
        try:
            r = self.session.post(f"{API_URL}/chat/completions", headers=self.headers, json=body, timeout=120)
        except self._exc as e:
            raise ApiErr(599, f"{type(e).__name__}: connection failed") from None
        hdr = {str(k).lower(): v for k, v in dict(r.headers).items()}
        if r.status_code != 200:
            try:
                body = r.json() or {}
            except ValueError:
                body = {}
            err = body.get("error") if isinstance(body.get("error"), dict) else {}
            raise ApiErr(r.status_code, str(err.get("message") or r.text or "")[:300], parse_duration(hdr.get("retry-after")),
                         body.get("usage"), hdr.get("x-request-id"), hdr, body)
        d = r.json()
        ch = (d.get("choices") or [{}])[0]
        return {"content": (ch.get("message") or {}).get("content") or "", "finish_reason": ch.get("finish_reason"),
                "model": d.get("model"), "usage": d.get("usage"), "headers": hdr,
                "request_id": (d.get("x_groq") or {}).get("id") or hdr.get("x-request-id") or d.get("id")}


# ---------- generation ----------
def redact(text, secrets):
    text = SECRET_RE.sub("[REDACTED]", text)
    for s in secrets:
        if s:
            text = text.replace(s, "[REDACTED]")
    return text


def summarise_costs(attempts, rows, ledger, pricing, meta, estimate):
    api = [a for a in attempts if a["api_call"]]
    est = [a for a in api if a["estimate_status"] == "estimated"]
    unknown = [a for a in api if a["estimate_status"] == "missing_usage"]
    err_no_usage = [a for a in api if a["estimate_status"] == "no_usage_on_error"]
    tok = lambda k: sum(a[k] for a in api if is_count(a[k]))
    total = sum((a["estimated_cost"] for a in est), Decimal(0))
    ok = [r for r in rows if r["status"] == "ok"]
    ok_api = [r for r in ok if not r["cached"]]
    avg = total / len(ok_api) if ok_api and not unknown else None
    remaining = meta["total_topics"] - meta["completed_overall"]
    return {
        "run_id": meta["naming_run_id"], "scope": meta["scope"], "run_status": meta["run_status"],
        "stop_reason": meta["stop_reason"], "requested_model": MODEL_ID,
        "served_models": sorted({a["served_model"] for a in api if a["served_model"]}),
        "pricing_snapshot": {"file": "pricing_snapshot.json", "version": pricing["version"], "sha256": pricing["sha256"],
                             "verified_utc_date": pricing["data"]["verified_utc_date"],
                             "sources": [s["url"] for s in pricing["data"]["sources"]]},
        "budget_usd": usd(ledger.budget), "budget_basis": "estimated cost at published rates (Groq returns no charge)",
        "budget_note": "pre-request checks use an estimate and cannot guarantee an exact cap",
        "topics": {"requested": len(rows), "attempted": sum(r["status"] != "not_attempted" for r in rows),
                   "successful": len(ok), "successful_via_api": len(ok_api), "failed": sum(r["status"] == "failed" for r in rows),
                   "not_attempted": sum(r["status"] == "not_attempted" for r in rows),
                   "local_cache_hits": sum(a["local_cache"] == "hit" for a in attempts),
                   "resumed_from_previous_run": sum(bool(r.get("resumed")) for r in rows)},
        "api_attempts": len(api), "retries": sum(a["retry_count"] > 0 for a in api),
        "api_attempts_by_status": dict(sorted(Counter(a["request_status"] for a in api).items())),
        "tokens": {"input": tok("input_tokens"), "output": tok("output_tokens"), "reasoning": tok("reasoning_tokens"),
                   "cached_input": tok("cached_input_tokens"), "total": tok("total_tokens"),
                   "note": "local cache hits make no API call; cached_input = provider-side prompt caching, if reported"},
        "cost_usd": {"estimated_total": usd(total),
                     "estimated_input": usd(sum((a["estimated_input_cost"] for a in est), Decimal(0))),
                     "estimated_output": usd(sum((a["estimated_output_cost"] for a in est), Decimal(0))),
                     "estimate_basis": "actual tokens x published Groq rates",
                     "estimate_status": "complete" if not unknown and not err_no_usage else
                                        "incomplete: see unknown_cost_attempts / error_attempts_without_usage",
                     "billed_total": None, "billing_status": BILLING_STATUS,
                     "billing_note": "Groq returns no charge and does not document free-tier billing; check the Groq "
                                     "console. Unknown billing is never reported as zero"},
        "unknown_cost_attempts": len(unknown), "error_attempts_without_usage": len(err_no_usage),
        "average_estimated_cost_per_successful_topic_usd": jusd(avg),
        "this_run_estimated_cost_usd": usd(total),
        "projection": {"total_topics": meta["total_topics"], "completed_overall": meta["completed_overall"],
                       "remaining_topics": remaining,
                       "estimated_cost_remaining_usd": jusd(avg * remaining) if avg is not None else None,
                       "projected_full_run_usd": jusd(avg * meta["total_topics"]) if avg is not None else None,
                       "basis": "average estimated cost per successful topic in this run (None when unknown)"},
        "offline_estimate": estimate,
    }


def summarise_rate(rl_rows, attempts, rows, limiter, rl_cfg, meta, backoff_total):
    api = [a for a in attempts if a["api_call"]]
    left = any(r["status"] != "ok" for r in rows)
    return {
        "run_id": meta["naming_run_id"], "run_status": meta["run_status"], "stop_reason": meta["stop_reason"],
        "plan": rl_cfg["plan"], "config_sha256": rl_cfg["sha256"], "source": rl_cfg["source"], "safety_factor": rl_cfg["safety"],
        "limits_configured": limiter.configured, "limits_used_at_end": limiter.limits,
        "limits_from_headers": limiter.header_adopted,
        "header_meaning": {"x-ratelimit-*-requests": "per day (RPD)", "x-ratelimit-*-tokens": "per minute (TPM)"},
        "requests": {"total": len(api), "successful": sum(a["request_status"] == "ok" for a in api),
                     "failed": sum(a["request_status"] != "ok" for a in api),
                     "http_429": sum(a["http_status"] == 429 for a in api)},
        "wait_seconds": {"throttle": round(limiter.throttle_wait_s, 3), "backoff_and_retry_after": round(backoff_total, 3),
                         "total": round(limiter.throttle_wait_s + backoff_total, 3)},
        "tokens": {"input": sum(a["input_tokens"] or 0 for a in api), "output": sum(a["output_tokens"] or 0 for a in api)},
        "quota": limiter.report(),
        "quota_sources": QUOTA_SOURCES,
        "last_quota_stop": limiter.last_stop,
        "config_error": meta["config_error"],
        "daily_quota_exhaustion_events": limiter.daily_exhaustion_events,
        "remaining_topics": sum(r["status"] != "ok" for r in rows),
        "resume": {"resumed_from": meta["resumed_from"], "carried_over_completed": meta["carried_over"],
                   "resume_possible": left and not meta["config_error"],
                   "not_before_utc": (limiter.last_stop or {}).get("available_at_utc"),
                   "not_before_is": (limiter.last_stop or {}).get("available_at_is", "not applicable"),
                   "note": "fix the request settings first" if meta["config_error"] else
                           "a provider-reported time is Groq's; a local estimate is conservative; unknown = try later",
                   "resume_command": f"python src/topic_naming.py generate --live --resume {meta['naming_run_id']}"
                   if left else None},
        "throttle_events": sum(r["event"] == "throttle_wait" for r in rl_rows),
    }


def cost_markdown(s, r):
    t, c, k = s["topics"], s["cost_usd"], s["tokens"]
    lines = [f"# Topic naming cost and rate-limit report — {s['run_id']}", "",
             f"- Scope **{s['scope']}**, run status **{s['run_status']}**" + (f" (stop: {s['stop_reason']})" if s["stop_reason"] else ""),
             f"- Model requested `{s['requested_model']}`; served {', '.join(f'`{m}`' for m in s['served_models']) or '—'}",
             f"- Pricing `{s['pricing_snapshot']['version']}` (verified {s['pricing_snapshot']['verified_utc_date']}; "
             f"sha {s['pricing_snapshot']['sha256'][:12]}); source {s['pricing_snapshot']['sources'][0]}",
             f"- Budget ${s['budget_usd']} on {s['budget_basis']} — {s['budget_note']}", "",
             "| Topics | requested | successful | failed | not attempted | local cache hits | resumed |",
             "|---|---|---|---|---|---|---|",
             f"| | {t['requested']} | {t['successful']} | {t['failed']} | {t['not_attempted']} | {t['local_cache_hits']} | "
             f"{t['resumed_from_previous_run']} |", "",
             "| Tokens | input | output | reasoning | cached input |", "|---|---|---|---|---|",
             f"| | {k['input']} | {k['output']} | {k['reasoning']} | {k['cached_input']} |", "",
             f"**Estimated cost (published rates): ${c['estimated_total']}** ({c['estimate_status']}). "
             f"**Billed cost: unknown** ({c['billing_status']}: {c['billing_note']}).", "",
             f"- API attempts {s['api_attempts']} {s['api_attempts_by_status']}, retries {s['retries']}; unknown-cost attempts "
             f"{s['unknown_cost_attempts']}; error attempts without usage {s['error_attempts_without_usage']}",
             f"- Average estimated cost per successful topic: ${s['average_estimated_cost_per_successful_topic_usd'] or 'unknown'}",
             f"- Remaining topics {s['projection']['remaining_topics']} → estimated "
             f"${s['projection']['estimated_cost_remaining_usd'] or 'unknown'}; projected full run "
             f"${s['projection']['projected_full_run_usd'] or 'unknown'}", "",
             "## Rate limits", "",
             f"- Plan `{r['plan']}` × safety {r['safety_factor']}; configured {r['limits_configured']}; from headers "
             f"{r['limits_from_headers'] or '—'} (requests headers = per day, tokens headers = per minute)",
             f"- Requests {r['requests']}; waits {r['wait_seconds']} s; daily quota exhaustion events "
             f"{r['daily_quota_exhaustion_events']}",
             f"- **Provider-reported** RPD {r['quota']['provider_reported']['requests_per_day']}, TPM "
             f"{r['quota']['provider_reported']['tokens_per_minute']}, TPD: "
             f"{r['quota']['provider_reported']['tokens_per_day']}; from 429 messages "
             f"{r['quota']['provider_reported']['from_429_messages'] or '—'}",
             f"- **Local estimate** (this machine, rolling windows; not Groq's reset rule): "
             f"{r['quota']['local_estimate']['requests_last_day']} requests / "
             f"{r['quota']['local_estimate']['tokens_last_day']} tokens in the last 24 h",
             f"- Last quota stop: {r['last_quota_stop'] or '—'}" + (f"; **config error**: {r['config_error']}" if r['config_error'] else ""),
             f"- Remaining topics {r['remaining_topics']}; resume: {r['resume']['resume_command'] or 'not needed'}"
             f" (not before {r['resume']['not_before_utc'] or 'unknown'}, {r['resume']['not_before_is']})", ""]
    e = s["offline_estimate"]
    lines += ["## Offline estimate before the run (no API call)", "",
              "| | topics | tokens typical / upper | est. cost typical / upper |", "|---|---|---|---|"]
    for key in ("selected", "full_run"):
        if key in e:
            x = e[key]
            lines.append(f"| {key.replace('_', ' ')} | {x['topics']} | {x['tokens_typical']} / {x['tokens_upper']} | "
                         f"${x.get('estimated_cost_typical_usd')} / ${x.get('estimated_cost_upper_usd')} |")
    lines += ["", "Estimates are not billed charges. Unknown amounts are never shown as 0."]
    return "\n".join(lines) + "\n"


def generate(backend, topic_ids=None, *, scope, root=ROOT, run_id=RUN_ID, expected=fz.EXPECTED, naming_run_id=None,
             budget_usd=None, plan="free", resume_from=None, max_attempts=MAX_ATTEMPTS, today=None, secrets=(),
             clock=None, sleep=None, rng=None, check_model=True):
    """Name topics sequentially with rate limiting, cost tracking, budget stops and resume. Re-verifies first."""
    clock, sleep, rng = clock or CLOCK, sleep or SLEEP, rng or RNG
    if scope not in DEFAULT_BUDGET_USD:
        raise ValueError(f"scope must be one of {sorted(DEFAULT_BUDGET_USD)}")
    budget = Decimal(str(budget_usd)) if budget_usd is not None else DEFAULT_BUDGET_USD[scope]
    if not budget.is_finite() or budget <= 0:
        raise ValueError("budget must be a positive amount")
    pricing = load_pricing(pricing_path(root), today)
    rl_cfg = load_rate_limits(rate_limits_path(root), plan, today)
    pdir = prepare_dir(root, run_id)
    if not (pdir / "manifest.json").is_file():
        raise FileNotFoundError(f"prepare folder missing: {pdir} (run prepare first)")
    problems = verify(root, run_id)
    if problems:
        raise SystemExit("prepare folder failed verification: " + "; ".join(problems))
    pm = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
    system = prompt_path(root).read_text(encoding="utf-8")
    if sha(system) != pm["prompt"]["sha256"]:
        raise SystemExit("prompt changed since prepare: make a new prompt version instead")
    inp = load_inputs(root, run_id, expected)
    records = {r["topic_id"]: r for r in build_evidence(inp)["records"]}
    if sha(jsonl(list(records.values()))) != pm["files_sha256"]["evidence.jsonl"]:
        raise SystemExit("evidence differs from the prepared evidence")
    prev_ok = set()
    if resume_from:
        prev_dir = naming_dir(root, run_id) / resume_from
        if not (prev_dir / "manifest.json").is_file() or not (prev_dir / "results.jsonl").is_file():
            raise FileNotFoundError(f"cannot resume: {resume_from} has no manifest / results")
        prev = json.loads((prev_dir / "manifest.json").read_text(encoding="utf-8"))
        if (prev.get("prompt_sha256"), prev.get("model"), prev.get("evidence_fingerprint")) != \
                (sha(system), MODEL_ID, pm["files_sha256"]["evidence.jsonl"]):
            raise SystemExit("cannot resume: the previous run used another prompt, model or evidence")
        topic_ids = topic_ids or prev["topic_ids"]
        prev_ok = {r["topic_id"] for r in map(json.loads, (prev_dir / "results.jsonl").read_text(encoding="utf-8").splitlines())
                   if r["status"] == "ok"}
    if not topic_ids:
        raise ValueError("no topic IDs given")
    unknown = [t for t in topic_ids if t not in records]
    if unknown or len(set(topic_ids)) != len(topic_ids):
        raise ValueError(f"unknown or repeated topic IDs: {unknown[:5]}")
    naming_run_id = naming_run_id or f"{PROMPT_VERSION}_{MODEL_SLUG}_{scope}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    out_dir, tdir = naming_dir(root, run_id) / naming_run_id, tracked_dir(root, run_id) / naming_run_id
    if out_dir.exists() or tdir.exists():
        raise FileExistsError(f"{naming_run_id} exists; never overwritten")
    if check_model:
        ok, why = backend.check_model()
        if not ok:
            raise SystemExit(f"model pre-flight failed: {why}")
    reqs = {t: build_request(system, records[t]["payload"]) for t in records}
    estimate = offline_estimate(list(reqs.values()), topic_ids, pricing, rl_cfg)
    cdir = cache_dir(root)
    cdir.mkdir(parents=True, exist_ok=True)
    rate_state_dir(root).mkdir(parents=True, exist_ok=True)
    hist_path = rate_state_dir(root) / "request_log.jsonl"
    limiter = RateLimiter(rl_cfg["limits"], rl_cfg["safety"], clock, sleep, load_history(hist_path, clock()))
    quota_path = rate_state_dir(root) / "provider_quota.json"
    if quota_path.is_file():
        try:
            limiter.load_state(json.loads(quota_path.read_text(encoding="utf-8")), clock())
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass
    save_quota = lambda: quota_path.write_text(json.dumps(limiter.export_state(), sort_keys=True), encoding="utf-8")
    out_dir.mkdir(parents=True)
    base = {"model": MODEL_ID, "prompt_version": PROMPT_VERSION, "prompt_sha256": sha(system), "run_id": naming_run_id,
            "clustering_run_id": run_id, "evidence_fingerprint": pm["files_sha256"]["evidence.jsonl"]}
    ledger, attempts, rl_rows, rows, raw_log = Ledger(budget), [], [], [], []
    state = {"backoff": 0.0, "stop": None, "config_error": None}
    fh = (out_dir / "cost_report.csv").open("w", encoding="utf-8", newline="")
    rfh = (out_dir / "rate_limit_report.csv").open("w", encoding="utf-8", newline="")
    writer, rwriter = csv.writer(fh, lineterminator="\n"), csv.writer(rfh, lineterminator="\n")
    writer.writerow(COST_COLS)
    rwriter.writerow(RL_COLS)
    now_iso = lambda: datetime.fromtimestamp(clock(), timezone.utc).isoformat(timespec="seconds")

    def rl_log(t, n, event, wait=0.0, reason="", est=(None, None), actual=None, h=None, source=""):
        u, h = limiter.usage(), h or {}
        row = {"run_id": naming_run_id, "topic_id": t, "attempt": n, "timestamp_utc": now_iso(), "event": event,
               "wait_s": round(float(wait or 0), 3), "reason": reason, "quota_source": source,
               "est_input_tokens": est[0], "est_output_tokens": est[1], "actual_tokens": actual,
               **{f"local_{k}": v for k, v in u.items() if not k.startswith("_")},
               **{f"limit_{k}": limiter.limits.get(k) for k in ("rpm", "rpd", "tpm", "tpd")},
               **{f"provider_{k}": h.get(k) for k in ("limit_requests_day", "remaining_requests_day", "reset_requests_day_s",
                                                      "limit_tokens_minute", "remaining_tokens_minute",
                                                      "reset_tokens_minute_s", "retry_after_s")}}
        rl_rows.append(row)
        rwriter.writerow([cell(row[c]) for c in RL_COLS])
        rfh.flush()

    def log(t, n, status, *, api_call, local="miss", http=None, finish=None, served="", priced=None, est=None,
            req_id="", error="", rl_wait=0.0, backoff=0.0, h=None, error_class=""):
        if priced is None:
            priced = {**price_usage(None, pricing), "estimate_status": "no_api_call", "estimate_note": ""}
            if not api_call:
                priced.update({k: Decimal(0) for k in ("estimated_input_cost", "estimated_output_cost", "estimated_cost")})
        h = h or {}
        a = {"run_id": naming_run_id, "topic_id": t, "attempt": n, "retry_count": max(0, n - 1) if api_call else 0,
             "timestamp_utc": now_iso(), "requested_model": MODEL_ID, "served_model": served or "", "request_status": status,
             "api_call": api_call, "local_cache": local, "http_status": http or "", "error_class": error_class,
             "finish_reason": finish or "",
             "rate_limit_wait_s": round(rl_wait, 3), "backoff_wait_s": round(backoff, 3), "retry_after_s": h.get("retry_after_s"),
             **{f"provider_{k}": h.get(k) for k in ("remaining_requests_day", "remaining_tokens_minute",
                                                    "reset_requests_day_s", "reset_tokens_minute_s")},
             "pricing_version": pricing["version"], "pricing_sha256": pricing["sha256"], "estimated_max_cost_usd": est,
             "billed_cost_usd": None, "billing_status": BILLING_STATUS if api_call else "no_api_call",
             "cumulative_estimated_cost_usd": ledger.spent, "request_id": req_id or "", "error": redact(error, secrets),
             **{k: priced[k] for k in ("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens",
                                       "total_tokens", "estimated_input_cost", "estimated_output_cost", "estimated_cost",
                                       "estimate_status", "estimate_note")}}
        a.update({"estimated_input_cost_usd": a["estimated_input_cost"], "estimated_output_cost_usd": a["estimated_output_cost"],
                  "estimated_cost_usd": a["estimated_cost"]})
        attempts.append(a)
        writer.writerow([cell(a[c]) for c in COST_COLS])
        fh.flush()

    def record_request(tin, tout, headers):
        h = limiter.record(tin, tout, headers)
        save_quota()
        with hist_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": clock(), "in": int(tin or 0), "out": int(tout or 0), "run": naming_run_id}) + "\n")
        return h

    def topic_cost(t):
        vals = [a["estimated_cost"] for a in attempts if a["topic_id"] == t and a["api_call"]]
        return None if any(v is None for v in vals) else sum(vals, Decimal(0))

    def name_topic(t):
        rec, req = records[t], reqs[t]
        row = {c: "" for c in RESULT_COLS} | base | {"topic_id": t, "cache_key": req["cache_key"], "cached": False,
                                                       "resumed": t in prev_ok, "topic_quality_flags": rec["topic_quality_flags"],
                                                       "name_flags": [], "supporting_skills": [], "attempts": 0}
        n_api = lambda: sum(a["topic_id"] == t and a["api_call"] for a in attempts)

        def fail(status, error):
            row.update({"status": status, "error": redact(error, secrets), "estimated_cost_usd": topic_cost(t), "attempts": n_api()})
            return row

        def accept(ans, served):
            kept, nf = name_flags(ans, rec["payload"])
            row.update({"status": "ok", "provisional_name": ans["provisional_name"], "description": ans["description"],
                        "supporting_skills": kept, "llm_confidence": ans["confidence"],
                        "llm_confidence_reason": ans["confidence_reason"], "name_flags": nf, "served_model": served,
                        "estimated_cost_usd": topic_cost(t), "attempts": n_api()})
            return row

        cpath = cdir / f"{req['cache_key']}.json"
        if cpath.is_file():
            try:
                hit = json.loads(cpath.read_text(encoding="utf-8"))
                if hit.get("cache_key") != req["cache_key"] or hit.get("served_model") != MODEL_ID:
                    raise ValueError("cache entry does not match this request")
                ans = parse_answer(hit["content"])
            except (ValueError, KeyError, json.JSONDecodeError):
                hit = None
            if hit:
                log(t, 0, "local_cache_hit", api_call=False, local="hit", served=hit["served_model"],
                    req_id=hit.get("request_id", ""))
                row["cached"] = True
                return accept(ans, hit["served_model"])
        est_in = estimate_input_tokens(req["body"], CHARS_PER_TOKEN_UPPER)
        est_pair = (est_in, MAX_COMPLETION_TOKENS)
        backoff_before = 0.0
        for n in range(1, max_attempts + 1):
            est = max_request_cost(req["body"], pricing)
            if not ledger.allow(est):
                log(t, n, "budget_stop", api_call=False, est=est, error=ledger.stop_reason)
                return fail("not_attempted" if n == 1 else "failed", ledger.stop_reason)
            waited, stop = limiter.acquire(*est_pair, lambda ev, w, why, src: rl_log(t, n, ev, w, why, est_pair, source=src))
            if stop:
                state["stop"] = f"rate limit: {stop}"
                log(t, n, "rate_limit_stop", api_call=False, est=est, error=stop, rl_wait=waited)
                return fail("not_attempted" if n == 1 else "failed", state["stop"])
            try:
                resp = backend.send(req["body"])
            except ApiErr as e:
                h = record_request(*(usage_tokens(e.usage) or (0, 0)), e.headers)
                h["retry_after_s"] = e.retry_after if e.retry_after is not None else h.get("retry_after_s")
                priced = (price_usage(e.usage, pricing) if usage_tokens(e.usage) else
                          {**price_usage(None, pricing), "estimate_status": "no_usage_on_error",
                           "estimate_note": "provider returned an error without usage"})
                ledger.record(priced)
                cls = e.error_class
                daily = limiter.note_429(e.message, e.retry_after) if e.status == 429 else {}
                if daily:
                    save_quota()
                log(t, n, "api_error", api_call=True, http=e.status, priced=priced, est=est, req_id=e.request_id,
                    error=f"{e.status} {e.error_type or ''}/{e.error_code or ''}: {e.message}", rl_wait=waited,
                    backoff=backoff_before, h=h, error_class=cls)
                rl_log(t, n, f"http_{e.status}", 0.0, redact(e.message[:160], secrets), est_pair, None, h,
                       source="provider_429_message" if daily else "provider_headers" if e.status == 429 else "")
                if cls == "config":
                    state["stop"] = (f"request configuration rejected: HTTP {e.status} {e.error_type or ''} "
                                     f"{e.error_code or ''}: {e.message}")
                    state["config_error"] = {"topic_id": t, "attempt": n, "http_status": e.status, "type": e.error_type,
                                             "code": e.error_code, "message": e.message, "request_id": e.request_id}
                    rl_log(t, n, "config_stop", 0.0, redact(state["stop"][:200], secrets), est_pair, None, h)
                    return fail("failed", state["stop"])
                if not e.retryable or n == max_attempts or ledger.stop_reason:
                    return fail("failed", f"API error {e.status}: {e.message}")
                wait = e.retry_after if (e.status == 429 and e.retry_after is not None) else backoff_seconds(n, rng)
                if wait > MAX_RETRY_AFTER_S:
                    state["stop"] = f"daily quota (provider-reported): Retry-After {wait:.0f}s exceeds {MAX_RETRY_AFTER_S:.0f}s"
                    limiter.note_stop(state["stop"], "provider_retry_after", wait)
                    rl_log(t, n, "quota_stop", wait, state["stop"], source="provider_retry_after")
                    return fail("failed", state["stop"])
                rl_log(t, n, "retry_after_wait" if e.status == 429 and e.retry_after is not None else "backoff_wait", wait,
                       f"HTTP {e.status}", source="provider_retry_after" if e.retry_after is not None else "")
                sleep(wait)
                state["backoff"] += wait
                backoff_before = wait
                continue
            tok = usage_tokens(resp["usage"]) or (0, 0)
            h = record_request(tok[0], tok[1], resp["headers"])
            priced = price_usage(resp["usage"], pricing)
            ledger.record(priced)
            rl_log(t, n, "response", 0.0, "", est_pair, sum(tok), h)
            served, finish = resp["model"], resp["finish_reason"]
            raw_log.append({"topic_id": t, "attempt": n, "cache_key": req["cache_key"], "served_model": served,
                            "finish_reason": finish, "request_id": resp["request_id"], "usage": resp["usage"],
                            "content": redact(resp["content"] or "", secrets)})
            ans, status, error = None, "ok", ""
            if served != MODEL_ID:
                status, error = "model_mismatch", f"served model {served!r} differs from pinned {MODEL_ID!r}"
                state["stop"] = state["stop"] or error
            elif finish != "stop":
                status, error = "incomplete", f"finish_reason {finish}"
            else:
                try:
                    ans = parse_answer(resp["content"])
                except (ValueError, json.JSONDecodeError) as e:
                    status, error = "invalid_answer", f"{type(e).__name__}: {str(e)[:200]}"
            log(t, n, status, api_call=True, http=200, finish=finish, served=served, priced=priced, est=est,
                req_id=resp["request_id"], error=error, rl_wait=waited, backoff=backoff_before, h=h)
            if status != "ok":
                return fail("failed", error)
            tmp = cpath.with_suffix(".tmp")
            tmp.write_text(json.dumps({"cache_key": req["cache_key"], "content": resp["content"], "served_model": served,
                                       "request_id": resp["request_id"], "usage": resp["usage"],
                                       "estimated_cost_usd": jusd(priced["estimated_cost"]), "pricing_version": pricing["version"],
                                       "request_sha256": sha(json.dumps(req["body"], sort_keys=True)),
                                       "created_utc": now_iso()}, ensure_ascii=False, default=str), encoding="utf-8")
            os.replace(tmp, cpath)
            return accept(ans, served)
        return fail("failed", "no attempt left")

    stop_reason = lambda: ledger.stop_reason or state["stop"]
    run_status = "running"
    try:
        for t in sorted(topic_ids):
            if stop_reason():
                rows.append({c: "" for c in RESULT_COLS} | base | {
                    "topic_id": t, "status": "not_attempted", "error": stop_reason(), "cached": False, "resumed": t in prev_ok,
                    "attempts": 0, "cache_key": reqs[t]["cache_key"], "topic_quality_flags": records[t]["topic_quality_flags"],
                    "name_flags": [], "supporting_skills": []})
                continue
            rows.append(name_topic(t))
        run_status = ("config_error" if state["config_error"] else
                      "quota_exhausted" if state["stop"] and limiter.daily_exhaustion_events
                      else "stopped" if stop_reason() else "completed")
    except KeyboardInterrupt:
        run_status = "interrupted"
        raise
    except BaseException:
        run_status = "crashed"
        raise
    finally:
        fh.close()
        rfh.close()
        done = {r["topic_id"] for r in rows}
        for t in sorted(set(topic_ids) - done):
            tried = any(a["topic_id"] == t and a["api_call"] for a in attempts)
            rows.append({c: "" for c in RESULT_COLS} | base | {
                "topic_id": t, "status": "failed" if tried else "not_attempted", "error": f"run {run_status}",
                "cached": False, "resumed": t in prev_ok, "attempts": sum(a["topic_id"] == t and a["api_call"] for a in attempts),
                "estimated_cost_usd": topic_cost(t), "cache_key": reqs[t]["cache_key"],
                "topic_quality_flags": records[t]["topic_quality_flags"], "name_flags": [], "supporting_skills": []})
        rows.sort(key=lambda r: r["topic_id"])
        finalise(rows)
        meta = {"naming_run_id": naming_run_id, "scope": scope, "run_status": run_status, "stop_reason": stop_reason(),
                "total_topics": pm["counts"]["topics"], "completed_overall": sum(r["status"] == "ok" for r in rows),
                "resumed_from": resume_from, "carried_over": len(prev_ok & set(topic_ids)),
                "config_error": state["config_error"]}
        cs = summarise_costs(attempts, rows, ledger, pricing, meta, estimate)
        rs = summarise_rate(rl_rows, attempts, rows, limiter, rl_cfg, meta, state["backoff"])
        files = {"results.jsonl": jsonl(rows), "results.csv": csv_bytes(rows, RESULT_COLS),
                 "review_queue.csv": csv_bytes([r for r in rows if r["review_required"]], RESULT_COLS),
                 "raw_responses.jsonl": jsonl(raw_log),
                 "cost_summary.json": (json.dumps(cs, indent=1, sort_keys=True, default=str) + "\n").encode("utf-8"),
                 "rate_limit_summary.json": (json.dumps(rs, indent=1, sort_keys=True, default=str) + "\n").encode("utf-8"),
                 "cost_report.md": cost_markdown(cs, rs).encode("utf-8"),
                 "pricing_snapshot.json": pricing["raw"], "rate_limits_snapshot.json": rl_cfg["raw"]}
        files = {n: redact(b.decode("utf-8"), secrets).encode("utf-8") for n, b in files.items()}
        for n, b in files.items():
            (out_dir / n).write_bytes(b)
        streamed = {n: (out_dir / n).read_bytes() for n in ("cost_report.csv", "rate_limit_report.csv")}
        hashes = {n: sha(b) for n, b in sorted({**files, **streamed}.items())}
        manifest = {"schema_version": SCHEMA_VERSION, "stage": "generate", **base, "scope": scope, "run_status": run_status,
                    "topic_ids": sorted(topic_ids), "resumed_from": resume_from, "prepare_fingerprint": pm["data_fingerprint"],
                    "model_settings": model_manifest(), "rate_plan": plan, "budget_usd": usd(budget),
                    "generated_utc": now_iso(), "code": code_version(root), "result_problems": check_results(rows, topic_ids),
                    "cost": {k: cs[k] for k in ("this_run_estimated_cost_usd", "unknown_cost_attempts",
                                               "error_attempts_without_usage", "api_attempts", "stop_reason")},
                    "files_sha256": hashes}
        text = redact(json.dumps(manifest, indent=1, sort_keys=True, default=str) + "\n", secrets)
        (out_dir / "manifest.json").write_text(text, encoding="utf-8")
        tdir.mkdir(parents=True, exist_ok=True)
        for n in ("cost_summary.json", "rate_limit_summary.json", "cost_report.md", "pricing_snapshot.json"):
            (tdir / n).write_bytes(files[n])
        for n, b in streamed.items():
            (tdir / n).write_bytes(b)
        (tdir / "manifest.json").write_text(text, encoding="utf-8")
    return out_dir, manifest, rows, cs, rs


# ---------- CLI ----------
def summary(res):
    m = res["manifest"]
    c = m["counts"]
    print(f"inputs verified | snapshot {m['inputs']['snapshot_fingerprint'][:12]} | features {m['inputs']['features_fingerprint'][:12]}")
    mm = m["model"]
    print(f"prompt {m['prompt']['version']} sha {m['prompt']['sha256'][:12]} | model {mm['provider']}/{mm['model_id']} "
          f"temperature={mm['temperature']} reasoning_effort={mm['reasoning_effort']} reasoning_format={mm['reasoning_format']} "
          f"response_format={mm['response_format']['type']} max_completion_tokens={mm['max_completion_tokens']} fallback=None")
    print(f"topics prepared {c['topics']} | requests {c['requests']} | request problems {c['request_problems']}")
    print("review flags: " + ", ".join(f"{f} {c[f]}" for f in REVIEW_FLAGS) + f" | any {c['review_flagged']}")
    print(f"pilot (seed {m['pilot']['seed']}): " + ", ".join(p["topic_id"] for p in res["pilot"]))
    e = m["offline_estimate"]
    for err in ("pricing_error", "rate_limits_error"):
        if e.get(err):
            print(f"{err}: {e[err]}")
    if m["pricing_snapshot"]:
        print(f"pricing {m['pricing_snapshot']['version']}")
    if m["rate_limits"]:
        print(f"rate limits plan {m['rate_limits']['plan']} {m['rate_limits']['limits']} x safety {m['rate_limits']['safety']}")
    for k in ("pilot", "full_run"):
        x = e[k]
        print(f"  {k:<8} topics {x['topics']:<4} tokens typical {x['tokens_typical']:<7} upper {x['tokens_upper']:<7} "
              f"est. cost typical ${x.get('estimated_cost_typical_usd')} upper ${x.get('estimated_cost_upper_usd')}")
        if "quota" in x:
            print(f"           quota: {x['quota']}")
    print("provenance gaps:\n  - " + "\n  - ".join(m["provenance_gaps"]))
    for t, p in res["problems"].items():
        print(f"PROBLEM {t}: {p}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["prepare", "verify", "generate"])
    ap.add_argument("--no-write", action="store_true", help="prepare: dry run, write nothing")
    ap.add_argument("--show", type=int, default=0, help="prepare: print N pilot payloads (one per stratum first)")
    ap.add_argument("--scope", choices=["pilot", "all"], default="pilot")
    ap.add_argument("--plan", choices=["free", "developer"], default="free", help="rate-limit plan (default free)")
    ap.add_argument("--budget-usd", help="generate: estimated-cost cap for this run (default pilot 1.00, all 10.00)")
    ap.add_argument("--resume", help="generate: previous naming_run_id to continue (same topics, completed ones from cache)")
    ap.add_argument("--live", action="store_true", help="generate: required, makes real Groq API calls")
    args = ap.parse_args()
    from dotenv import dotenv_values
    secrets = [v for v in dotenv_values(ROOT / ".env").values() if v and len(v) >= 8]
    try:
        if args.cmd == "prepare":
            res = prepare(write=not args.no_write, secrets=secrets, plan=args.plan)
            summary(res)
            by = {r["topic_id"]: r for r in res["records"]}
            seen, picks = set(), []
            for p in res["pilot"]:
                if p["stratum"] not in seen:
                    seen.add(p["stratum"])
                    picks.append(p["topic_id"])
            for t in picks[:args.show]:
                print(f"\n--- payload {t} ---\n" + json.dumps(by[t]["payload"], ensure_ascii=False, indent=1))
            if res["problems"]:
                sys.exit(1)
            print("\nDRY RUN: nothing written, no API call" if args.no_write
                  else f"\nwritten -> {prepare_dir(ROOT, RUN_ID).relative_to(ROOT)}")
        elif args.cmd == "verify":
            p = verify()
            print("OK: prepare outputs match their manifest" if not p else "PROBLEMS:\n  " + "\n  ".join(p))
            sys.exit(1 if p else 0)
        else:
            if not args.live:
                sys.exit("generate makes live Groq API calls; add --live once it is approved")
            pm = json.loads((prepare_dir(ROOT, RUN_ID) / "manifest.json").read_text(encoding="utf-8"))
            ids = None if args.resume else (
                [p["topic_id"] for p in pm["pilot"]["topics"]] if args.scope == "pilot"
                else [r["topic_id"] for r in read_csv(prepare_dir(ROOT, RUN_ID) / "topic_flags.csv")])
            d, m, _, cs, rs = generate(GroqBackend(), ids, scope=args.scope, budget_usd=args.budget_usd, plan=args.plan,
                                       resume_from=args.resume, secrets=secrets)
            print(f"-> {d.relative_to(ROOT)} | status {m['run_status']} | est. cost ${cs['this_run_estimated_cost_usd']} "
                  f"(billed: unknown) | 429s {rs['requests']['http_429']} | waits {rs['wait_seconds']['total']}s | "
                  f"remaining {rs['remaining_topics']} | problems {m['result_problems']}")
            if rs["resume"]["resume_command"]:
                print(f"resume later with: {rs['resume']['resume_command']}")
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
