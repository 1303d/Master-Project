"""Extract skill statements from the gold postings with a free-tier LLM (brief p.7).

    py src/extract_skills.py --provider groq --list-models
    py src/extract_skills.py --provider groq --model qwen/qwen3.8-27b --limit 3   # small test
    py src/extract_skills.py --provider gemini --model gemini-3.8-flash           # all 100 gold postings

Providers: gemini (Google AI Studio, GEMINI_API_KEY), groq (GROQ_API_KEY), openrouter (OPENROUTER_API_KEY)
and anthropic (ANTHROPIC_API_KEY).
Keys are read from .env.
The model is never guessed: pass --model.

Input:  data/gold/gold_postings.csv (contacts already masked)
Output: data/processed/statements_<model>.csv          one row per skill statement
        data/processed/extraction_postings_<model>.csv every posting (status done / failed, incl. zero-skill), tokens
        reports/token_usage.csv                        one row per run: calls, tokens in/out (written even if stopped)
        reports/token_calls.csv                        one row per paid API call, written at once
Cache:  cache/<provider>/<sha256>.json                 key = model + prompt + text; re-runs are free.
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
POSTINGS = ROOT / "data" / "gold" / "gold_postings.csv"
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
CALLS_LOG = ROOT / "reports" / "token_calls.csv"


def validate_output(out):
    """Return (skills, n_dropped). Raises ValueError when the answer is not {"skills": [...]}, so a malformed
    answer is reported as a failure and never cached. Items without a non-empty text "skill" are dropped."""
    if not isinstance(out, dict) or not isinstance(out.get("skills"), list):
        raise ValueError(f"malformed output: expected {{'skills': [...]}}, got {type(out).__name__}")
    skills = [{"skill": s["skill"].strip(), "evidence": str(s.get("evidence") or "").strip()}
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


def slug(model):
    """File-safe model name: 'qwen/qwen3.8-27b' -> 'qwen_qwen3.8-27b'."""
    return re.sub(r"[^\w.-]", "_", model)


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
                    system_instruction=system, temperature=0,
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
        body = {"model": self.model, "temperature": 0, "response_format": {"type": "json_object"},
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
    # strict structured output needs additionalProperties: false on every object
    STRICT = {**SCHEMA, "additionalProperties": False,
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
                output_config={"format": {"type": "json_schema", "schema": self.STRICT}})
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


def build_examples(posts, k):
    """Semantic search: for each posting, k worked examples = the k shortest of its 5 most similar
    DEV gold postings (never itself, never a test posting), shown with their human-labelled skills."""
    from sentence_transformers import SentenceTransformer
    dev = pd.read_csv(DEV_POSTINGS, encoding="utf-8-sig").merge(
        pd.read_csv(GOLD_LABELS)[["posting_id", "gold_skills"]], on="posting_id")
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
    ap.add_argument("--examples", type=int, default=0, help="add K similar dev gold postings as examples (semantic search)")
    args = ap.parse_args()
    prompt_version = args.prompt.stem + (f"+knn{args.examples}" if args.examples else "")
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
    cache = ROOT / "cache" / args.provider
    cache.mkdir(parents=True, exist_ok=True)
    backend, rows, done, failed, calls, tok_in, tok_out = None, [], [], [], 0, 0, 0
    warned, lf = False, langfuse_client()

    blocks = build_examples(posts, args.examples) if args.examples else {}
    try:  # the summary below is written even if the run stops early (Ctrl+C, crash)
        for p in posts.itertuples():
            text = (f"{blocks[p.posting_id]}\n\nNOW EXTRACT THE SKILLS FROM THIS POSTING:\n{p.description}"
                    if blocks else p.description)
            key = hashlib.sha256(f"{model}|{prompt_sha}|{text}".encode()).hexdigest()
            path = cache / f"{key}.json"
            try:
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if not warned and data.get("settings", SETTINGS) != SETTINGS:
                        print("  note: some cached answers were made with a different JSON hint", flush=True)
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
                            "prompt_version": prompt_version, "prompt_sha256": prompt_sha, "settings": SETTINGS,
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
                             "provider": Backend.name, "model": model, "prompt_version": prompt_version})
    finally:
        if lf:
            lf.flush()
        write_outputs(args, model, prompt_version, posts, rows, done, failed, calls, tok_in, tok_out, Backend.name)


def write_outputs(args, model, prompt_version, posts, rows, done, failed, calls, tok_in, tok_out, provider):
    PROCESSED.mkdir(parents=True, exist_ok=True)
    suffix = f"{slug(model)}_{args.tag}" if args.tag else slug(model)
    out_path = PROCESSED / f"statements_{suffix}.csv"
    pd.DataFrame(rows, columns=["statement_id", "posting_id", "skill", "evidence", "evidence_in_text", "provider",
                                "model", "prompt_version"]).to_csv(out_path, index=False)
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
