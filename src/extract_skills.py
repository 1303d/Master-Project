"""Extract skill statements from the gold postings with a free-tier LLM (brief p.7).

    py src/extract_skills.py --provider groq --list-models
    py src/extract_skills.py --provider groq --model qwen/qwen3.8-27b --limit 3   # small test
    py src/extract_skills.py --provider gemini --model gemini-3.8-flash           # the 50 dev gold postings
    py src/extract_skills.py ... --postings data/gold/gold_postings_test.csv --allow-test   # final run only

Providers: gemini (Google AI Studio, GEMINI_API_KEY), groq (GROQ_API_KEY), openrouter (OPENROUTER_API_KEY)
and anthropic (ANTHROPIC_API_KEY).
Keys are read from .env.
The model is never guessed: pass --model.

Input:  data/gold/gold_postings_dev.csv by default (contacts already masked). Postings that gold_split.csv
        marks as test are refused unless --allow-test is given (held-out set, final evaluation only).
Output: data/processed/statements_<model>.csv          one row per skill statement
        data/processed/extraction_postings_<model>.csv every posting (status done / failed, incl. zero-skill), tokens
        reports/token_usage.csv                        one row per run: calls, tokens in/out (written even if stopped)
        reports/token_calls.csv                        one row per paid API call, written at once
Cache:  cache/<provider>/<sha256>.json                 key = model + prompt + call settings + text; re-runs are free.
        Call settings = JSON hint (changes with --typed / --types), --typed, temperature, reasoning_format
        (+ types when --types is not the default list).
        --legacy-cache-key reuses caches written before this change (key = model + prompt + text) and
        refuses a cached answer whose JSON hint differs, so typed and untyped answers never mix.
        Answers are validated first: a malformed answer counts as FAILED and is never cached.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
POSTINGS = ROOT / "data" / "gold" / "gold_postings_dev.csv"  # default: dev only (was all 100 gold postings)
SPLIT = ROOT / "data" / "gold" / "gold_split.csv"
PROMPT = ROOT / "prompts" / "skill_extraction_v1.txt"
PROMPT_VERSION = "skill_extraction_v1"
PROCESSED = ROOT / "data" / "processed"
USAGE = ROOT / "reports" / "token_usage.csv"

SCHEMA = {
    "type": "object",
    "properties": {"skills": {"type": "array", "items": {
        "type": "object",
        "properties": {"skill": {"type": "string"}, "evidence": {"type": "string"}},
        "required": ["skill", "evidence"]}}},
    "required": ["skills"],
}
JSON_HINT = '\nReturn exactly this JSON shape: {"skills": [{"skill": "...", "evidence": "..."}]}'
# The cache key stays model + prompt + text (existing caches remain valid); the JSON hint is recorded in each
# new cache file instead, and a changed hint is reported when an old answer is reused.
SETTINGS = {"json_hint_sha256": hashlib.sha256(JSON_HINT.encode()).hexdigest()[:16]}
TEMPERATURE = 0.0  # set from --temperature in main()
CALLS_LOG = ROOT / "reports" / "token_calls.csv"
# --typed: every item also gets a type; only SCORED_TYPES go to statements_*.csv, all items to typed_*.csv
TYPES = ["skill", "knowledge", "tool", "credential", "education", "experience", "task", "other"]
DEFAULT_TYPES = list(TYPES)
SCORED_TYPES = {"skill", "knowledge", "tool"}


def use_typed_schema(types=None):
    """types: the allowed type list (--types); it feeds the JSON hint and the schema enum."""
    global SCHEMA, JSON_HINT, SETTINGS, TYPES
    TYPES = list(types or DEFAULT_TYPES)
    item = SCHEMA["properties"]["skills"]["items"]
    item = {**item, "properties": {**item["properties"], "type": {"type": "string", "enum": TYPES}},
            "required": item["required"] + ["type"]}
    SCHEMA = {**SCHEMA, "properties": {"skills": {"type": "array", "items": item}}}
    JSON_HINT = ('\nReturn exactly this JSON shape: {"skills": [{"skill": "...", "type": "' + "|".join(TYPES)
                 + '", "evidence": "..."}]}')
    SETTINGS = {"json_hint_sha256": hashlib.sha256(JSON_HINT.encode()).hexdigest()[:16]}


def validate_output(out):
    """Return (skills, n_dropped). Raises ValueError when the answer is not {"skills": [...]}, so a malformed
    answer is reported as a failure and never cached. Items without a non-empty text "skill" are dropped."""
    if not isinstance(out, dict) or not isinstance(out.get("skills"), list):
        raise ValueError(f"malformed output: expected {{'skills': [...]}}, got {type(out).__name__}")
    skills = [{"skill": s["skill"].strip(), "evidence": str(s.get("evidence") or "").strip(),
               "type": str(s.get("type") or "").strip().lower()}
              for s in out["skills"] if isinstance(s, dict) and isinstance(s.get("skill"), str) and s["skill"].strip()]
    return skills, len(out["skills"]) - len(skills)


def log_call(provider, model, prompt_version, posting_id, t_in, t_out):
    """Append one paid API call at once, so tokens are counted even if the run is killed later."""
    new = not CALLS_LOG.exists()
    with CALLS_LOG.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["called_at", "provider", "model", "prompt_version", "posting_id", "tokens_in", "tokens_out"])
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), provider, model, prompt_version,
                    posting_id, t_in, t_out])


def call_settings(provider, model, typed):
    """Everything besides model, prompt and text that changes the answer. Part of the cache key, stored in
    each cache file."""
    s = {**SETTINGS, "typed": typed, "temperature": None if provider == "anthropic" else TEMPERATURE}
    if typed and TYPES != DEFAULT_TYPES:  # only when changed, so earlier typed caches keep their key
        s["types"] = list(TYPES)
    if provider in ("groq", "openrouter") and "qwen3" in model:  # GroqBackend.extract (OpenRouter inherits it)
        s["reasoning_format"] = "hidden"
    return s


def cache_key(model, prompt_sha, settings, text, legacy=False):
    if legacy:  # the key used before 2026-10-30: settings not included
        return hashlib.sha256(f"{model}|{prompt_sha}|{text}".encode()).hexdigest()
    return hashlib.sha256(f"{model}|{prompt_sha}|{json.dumps(settings, sort_keys=True)}|{text}".encode()).hexdigest()


def check_manifest(path, new):
    """Stop when cache_keys_<run>.csv already exists for this run name with other call settings or other keys
    (other model / prompt / settings) for the same postings: a run name must mean one set of settings."""
    if not path.exists():
        return
    old = pd.read_csv(path)
    if "settings" in old.columns and set(old.settings.dropna()) - set(new.settings):
        sys.exit(f"{path.name} exists with different call settings: use another --tag, or delete it on purpose.")
    both = old.merge(new, on="posting_id", suffixes=("_old", ""))
    if (both.cache_key_old != both.cache_key).any():
        sys.exit(f"{path.name} exists with different cache keys (model, prompt or settings changed): "
                 f"use another --tag, or delete it on purpose.")


def test_ids():
    """posting_ids that gold_split.csv marks as test (empty set when the file is missing)."""
    if not SPLIT.exists():
        return set()
    split = pd.read_csv(SPLIT, encoding="utf-8-sig")
    return set(split.loc[split.split == "test", "posting_id"])


def slug(model):
    """File-safe model name: 'qwen/qwen3.8-27b' -> 'qwen_qwen3.8-27b'."""
    return re.sub(r"[^\w.-]", "_", model)


def run_suffix(model, tag=""):
    """Run name used in output file names: statements_<run>.csv, cache_keys_<run>.csv."""
    return f"{slug(model)}_{tag}" if tag else slug(model)


class ApiError(Exception):
    def __init__(self, code, message, retry_after=None):
        super().__init__(f"{code}: {message}")
        self.code, self.retry_after = code, retry_after

    @property
    def retryable(self):
        return self.code == 429 or self.code >= 500


class GeminiBackend:
    name = "google-ai-studio"

    def __init__(self, model):
        from google import genai
        key = os.getenv("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY is missing in .env")
        self.client, self.model = genai.Client(api_key=key), model

    def list_models(self):
        return [m.name for m in self.client.models.list()
                if "generateContent" in (getattr(m, "supported_actions", None) or [])]

    def extract(self, system, text):
        """Return (parsed_json, tokens_in, tokens_out)."""
        from google.genai import errors, types
        try:
            r = self.client.models.generate_content(
                model=self.model, contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=system, temperature=TEMPERATURE,
                    response_mime_type="application/json", response_json_schema=SCHEMA))
        except errors.APIError as e:
            raise ApiError(e.code, str(e)[:200])
        u = r.usage_metadata
        return json.loads(r.text), u.prompt_token_count or 0, (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)


class GroqBackend:
    """Groq's OpenAI-compatible chat API, called with plain requests (no extra package)."""

    name = "groq"
    URL = "https://api.groq.com/openai/v1"

    def __init__(self, model):
        key = os.getenv("GROQ_API_KEY") or sys.exit("GROQ_API_KEY is missing in .env")
        self.headers, self.model = {"Authorization": f"Bearer {key}"}, model

    def list_models(self):
        r = requests.get(f"{self.URL}/models", headers=self.headers, timeout=30)
        return sorted(m["id"] for m in r.json()["data"])

    def extract(self, system, text):
        body = {"model": self.model, "temperature": TEMPERATURE, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system + JSON_HINT}, {"role": "user", "content": text}]}
        if "qwen3" in self.model:
            body["reasoning_format"] = "hidden"  # keep <think> text out of the JSON answer
        try:
            r = requests.post(f"{self.URL}/chat/completions", headers=self.headers, json=body, timeout=120)
        except requests.RequestException as e:
            raise ApiError(599, str(e)[:200])
        if r.status_code != 200:
            ra = r.headers.get("retry-after")
            raise ApiError(r.status_code, r.text[:200], float(ra) if ra else None)
        d = r.json()
        u = d.get("usage", {})
        return json.loads(d["choices"][0]["message"]["content"]), u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


class OpenRouterBackend(GroqBackend):
    """OpenRouter speaks the same OpenAI-compatible API as Groq; only the URL and key differ."""

    name = "openrouter"
    URL = "https://openrouter.ai/api/v1"

    def __init__(self, model):
        key = os.getenv("OPENROUTER_API_KEY") or sys.exit("OPENROUTER_API_KEY is missing in .env")
        self.headers, self.model = {"Authorization": f"Bearer {key}"}, model


class AnthropicBackend:
    """Claude via the official anthropic SDK; output_config.format forces JSON that matches SCHEMA."""

    name = "anthropic"

    @staticmethod
    def strict():
        """Strict structured output needs additionalProperties: false on every object (built at call time,
        so --typed is picked up)."""
        return {**SCHEMA, "additionalProperties": False,
                "properties": {"skills": {"type": "array", "items": {**SCHEMA["properties"]["skills"]["items"],
                                                                     "additionalProperties": False}}}}

    def __init__(self, model):
        import anthropic
        os.getenv("ANTHROPIC_API_KEY") or sys.exit("ANTHROPIC_API_KEY is missing in .env")
        self.client, self.model = anthropic.Anthropic(), model

    def list_models(self):
        return sorted(m.id for m in self.client.models.list())

    def extract(self, system, text):
        import anthropic
        try:
            r = self.client.messages.create(
                model=self.model, max_tokens=16000, system=system,
                messages=[{"role": "user", "content": text}],
                output_config={"format": {"type": "json_schema", "schema": self.strict()}})
        except anthropic.APIStatusError as e:
            ra = e.response.headers.get("retry-after")
            raise ApiError(e.status_code, str(e.message)[:200], float(ra) if ra else None)
        except anthropic.APIConnectionError as e:
            raise ApiError(599, str(e)[:200])
        if r.stop_reason != "end_turn":
            raise ValueError(f"stop_reason {r.stop_reason}")
        out = next(b.text for b in r.content if b.type == "text")
        return json.loads(out), r.usage.input_tokens, r.usage.output_tokens


BACKENDS = {"gemini": GeminiBackend, "groq": GroqBackend, "openrouter": OpenRouterBackend,
            "anthropic": AnthropicBackend}

DEV_POSTINGS = ROOT / "data" / "gold" / "gold_postings_dev.csv"
GOLD_LABELS = ROOT / "data" / "gold" / "gold_labels.csv"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def build_examples(posts, k, examples_file):
    """Semantic search: for each posting, k worked examples = the k shortest of its 5 most similar postings
    in examples_file (never itself), shown with their human-labelled skills.
    examples_file: CSV with posting_id, description, gold_skills. It must not contain test postings. If it
    contains dev gold postings, dev scores are no longer independent of the labels (a warning is printed);
    use postings labelled under the frozen rules that are NOT in the gold set."""
    dev = pd.read_csv(examples_file, encoding="utf-8-sig")
    missing = {"posting_id", "description", "gold_skills"} - set(dev.columns)
    if missing:
        sys.exit(f"--examples-file needs columns posting_id, description, gold_skills (missing: {', '.join(missing)})")
    if dev.posting_id.isin(test_ids()).any():
        sys.exit("--examples-file contains test postings: never show held-out labels to the model.")
    if SPLIT.exists():
        split = pd.read_csv(SPLIT, encoding="utf-8-sig")
        overlap = dev.posting_id.isin(split.loc[split.split == "dev", "posting_id"]).sum()
        if overlap:
            print(f"  WARNING: {overlap} example postings are dev gold postings; dev scores of this run are "
                  f"tuned on dev labels and must not be compared with zero-shot runs.", flush=True)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBED_MODEL)
    dev_vec = model.encode(dev.description.tolist(), normalize_embeddings=True)
    post_vec = model.encode(posts.description.tolist(), normalize_embeddings=True)
    blocks = {}
    for i, pid in enumerate(posts.posting_id):
        nearest = [j for j in (dev_vec @ post_vec[i]).argsort()[::-1] if dev.posting_id.iat[j] != pid][:5]
        chosen = sorted(nearest, key=lambda j: len(dev.description.iat[j]))[:k]
        blocks[pid] = "\n\n".join(
            f"EXAMPLE POSTING:\n{dev.description.iat[j]}\nSKILLS (labelled by a human): {dev.gold_skills.fillna('').iat[j]}"
            for j in chosen)
    return blocks


def langfuse_client():
    """Langfuse client when LANGFUSE_PUBLIC_KEY / _SECRET_KEY are in .env, else None (tracing is optional)."""
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None
    from langfuse import Langfuse
    return Langfuse(host=os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL"))


def call_with_retry(backend, system, text, attempts=8):
    for i in range(attempts):
        try:
            return backend.extract(system, text)
        except ApiError as e:
            if not e.retryable or i == attempts - 1:
                raise
            wait = e.retry_after or min(120, 5 * 2 ** i)
            print(f"  {e.code} from API, retrying in {wait:.0f}s", flush=True)
            time.sleep(wait)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=BACKENDS, required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=None, help="only the first N postings")
    ap.add_argument("--postings", type=Path, default=POSTINGS, help="CSV with n, posting_id, description")
    ap.add_argument("--tag", default="", help="output suffix, e.g. sample2000 -> statements_<model>_sample2000.csv")
    ap.add_argument("--delay", type=float, default=4.0, help="seconds between API calls (free-tier pacing)")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--prompt", type=Path, default=PROMPT, help="prompt file; its file name is the prompt_version")
    ap.add_argument("--examples", type=int, default=0, help="add K similar labelled postings as examples (semantic search)")
    ap.add_argument("--examples-file", type=Path, default=None,
                    help="CSV (posting_id, description, gold_skills) to take --examples from; required with --examples")
    ap.add_argument("--temperature", type=float, default=0.0,
                    help="sampling temperature (default 0, as in all earlier runs; part of the cache key)")
    ap.add_argument("--allow-test", action="store_true", help="allow test postings (final evaluation only)")
    ap.add_argument("--legacy-cache-key", action="store_true",
                    help="reuse caches written before call settings joined the key (reproduces old runs for free)")
    ap.add_argument("--typed", action="store_true", help="ask for a type per item; score only skill/knowledge/tool")
    ap.add_argument("--types", default=",".join(DEFAULT_TYPES),
                    help="with --typed: comma list of allowed types (default: all 8); part of the cache key")
    args = ap.parse_args()
    if args.typed:
        use_typed_schema([t.strip() for t in args.types.split(",") if t.strip()])
    global TEMPERATURE
    TEMPERATURE = args.temperature
    if args.examples and not args.examples_file:
        sys.exit("--examples needs --examples-file (labelled postings that are not test postings).")
    prompt_version = args.prompt.stem + (f"+knn{args.examples}-{args.examples_file.stem}" if args.examples else "")
    load_dotenv(ROOT / ".env")
    Backend = BACKENDS[args.provider]

    if args.list_models:
        print("\n".join(Backend(args.model).list_models()))
        return
    if not args.model:
        sys.exit("Pass --model <id> (run --list-models first).")
    model = args.model

    system = args.prompt.read_text(encoding="utf-8")
    prompt_sha = hashlib.sha256(system.encode()).hexdigest()
    posts = pd.read_csv(args.postings, encoding="utf-8-sig")
    if args.limit:
        posts = posts.head(args.limit)
    n_test = int(posts.posting_id.isin(test_ids()).sum())
    if n_test and not args.allow_test:
        sys.exit(f"{n_test} of these postings are TEST postings (gold_split.csv). The held-out set is for the "
                 f"final evaluation only: pass --allow-test to run it.")
    settings = call_settings(args.provider, model, args.typed)
    if args.legacy_cache_key:
        print("  note: --legacy-cache-key: cache key without call settings (pre-2026-10-30 caches)", flush=True)
    cache = ROOT / "cache" / args.provider
    cache.mkdir(parents=True, exist_ok=True)
    backend, rows, done, failed, calls, tok_in, tok_out = None, [], [], [], 0, 0, 0
    warned, lf = False, langfuse_client()

    blocks = build_examples(posts, args.examples, args.examples_file) if args.examples else {}
    text_of = lambda p: (f"{blocks[p.posting_id]}\n\nNOW EXTRACT THE SKILLS FROM THIS POSTING:\n{p.description}"
                         if blocks else p.description)
    # Key manifest, written BEFORE the run: load_supabase.py --run and the UI progress counter read the cache
    # through it, so they never rebuild the key (and its call settings) themselves.
    PROCESSED.mkdir(parents=True, exist_ok=True)
    manifest = pd.DataFrame([{"posting_id": p.posting_id, "provider": args.provider,
                              "cache_key": cache_key(model, prompt_sha, settings, text_of(p), legacy=args.legacy_cache_key),
                              "settings": json.dumps(settings, sort_keys=True)} for p in posts.itertuples()])
    check_manifest(PROCESSED / f"cache_keys_{run_suffix(model, args.tag)}.csv", manifest)
    manifest.to_csv(PROCESSED / f"cache_keys_{run_suffix(model, args.tag)}.csv", index=False)
    try:  # the summary below is written even if the run stops early (Ctrl+C, crash)
        for p in posts.itertuples():
            text = text_of(p)
            key = cache_key(model, prompt_sha, settings, text, legacy=args.legacy_cache_key)
            path = cache / f"{key}.json"
            try:
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    old = data.get("settings", {})
                    if old.get("json_hint_sha256", SETTINGS["json_hint_sha256"]) != SETTINGS["json_hint_sha256"]:
                        # e.g. an untyped answer read by a --typed run (only possible with --legacy-cache-key)
                        raise ValueError("cached answer was made with a different JSON hint (typed vs untyped); "
                                         "run without --legacy-cache-key")
                    if not warned and not args.legacy_cache_key and old != settings:
                        print("  note: cached settings differ from this run", flush=True)
                        warned = True
                    skills, dropped = validate_output(data["output"])
                else:
                    backend = backend or Backend(model)
                    if calls:
                        time.sleep(args.delay)
                    gen = lf and lf.start_observation(  # one Langfuse generation per paid call (not cache hits)
                        name="skill-extraction", as_type="generation", model=model, input=text,
                        metadata={"posting_id": p.posting_id, "prompt_version": prompt_version, "tag": args.tag})
                    try:
                        out, t_in, t_out = call_with_retry(backend, system, text)
                    except ApiError as e:
                        if gen:
                            gen.update(level="ERROR", status_message=str(e)[:200]).end()
                        raise
                    if gen:
                        gen.update(output=out, usage_details={"input": t_in, "output": t_out}).end()
                    calls, tok_in, tok_out = calls + 1, tok_in + t_in, tok_out + t_out
                    log_call(Backend.name, model, prompt_version, p.posting_id, t_in, t_out)
                    skills, dropped = validate_output(out)  # malformed -> ValueError -> not cached
                    data = {"posting_id": p.posting_id, "provider": Backend.name, "model": model,
                            "prompt_version": prompt_version, "prompt_sha256": prompt_sha, "settings": settings,
                            "tokens_in": t_in, "tokens_out": t_out, "output": out}
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            except (ApiError, ValueError, KeyError) as e:  # keep going; a re-run retries only uncached postings
                print(f"#{p.n} {p.posting_id}: FAILED ({str(e)[:80]})", flush=True)
                failed.append(p.posting_id)
                continue
            print(f"#{p.n} {p.posting_id}: {len(skills)} skills" + (f" ({dropped} malformed items dropped)" if dropped else ""),
                  flush=True)
            done.append({"posting_id": p.posting_id, "status": "done", "n_skills": len(skills),
                         "tokens_in": data["tokens_in"], "tokens_out": data["tokens_out"]})  # tokens paid once
            low = p.description.lower()
            for i, s in enumerate(skills, 1):
                ev = s["evidence"]
                rows.append({"statement_id": f"{p.posting_id}:skill:{i}", "posting_id": p.posting_id,
                             "skill": s["skill"], "evidence": ev, "evidence_in_text": bool(ev) and ev.lower() in low,
                             "provider": Backend.name, "model": model, "prompt_version": prompt_version,
                             "type": s["type"]})
    finally:
        if lf:
            lf.flush()
        write_outputs(args, model, prompt_version, posts, rows, done, failed, calls, tok_in, tok_out, Backend.name)


def write_outputs(args, model, prompt_version, posts, rows, done, failed, calls, tok_in, tok_out, provider):
    PROCESSED.mkdir(parents=True, exist_ok=True)
    suffix = run_suffix(model, args.tag)
    out_path = PROCESSED / f"statements_{suffix}.csv"
    cols = ["statement_id", "posting_id", "skill", "evidence", "evidence_in_text", "provider", "model", "prompt_version"]
    if args.typed:  # all items with their type; statements_*.csv keeps only the scored types
        pd.DataFrame(rows, columns=cols + ["type"]).to_csv(PROCESSED / f"typed_{suffix}.csv", index=False)
        rows = [r for r in rows if r["type"] in SCORED_TYPES]
    pd.DataFrame(rows, columns=cols).to_csv(out_path, index=False)
    pd.DataFrame(done + [{"posting_id": pid, "status": "failed"} for pid in failed],
                 columns=["posting_id", "status", "n_skills", "tokens_in", "tokens_out"]
                 ).to_csv(PROCESSED / f"extraction_postings_{suffix}.csv", index=False)
    new = not USAGE.exists()
    with USAGE.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["run_at", "provider", "model", "prompt_version", "postings", "api_calls", "tokens_in", "tokens_out"])
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), provider, model,
                    prompt_version, len(posts), calls, tok_in, tok_out])
    if failed:
        print(f"\n{len(failed)} postings FAILED (not scored). Re-run the same command to retry them.")
    print(f"\n{len(rows)} statements -> {out_path.relative_to(ROOT)} | new API calls {calls} | tokens in {tok_in:,} out {tok_out:,}")


if __name__ == "__main__":
    main()
