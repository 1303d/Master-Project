"""Extract skill statements from the gold postings with a free-tier LLM (brief p.7).

    py src/extract_skills.py --provider groq --list-models
    py src/extract_skills.py --provider groq --model qwen/qwen3.8-27b --limit 3   # small test
    py src/extract_skills.py --provider gemini --model gemini-3.8-flash           # all 100 gold postings

Providers: gemini (Google AI Studio, GEMINI_API_KEY) and groq (GROQ_API_KEY). Keys are read from .env.
The model is never guessed: pass --model.

Input:  data/gold/gold_postings.csv (contacts already masked)
Output: data/processed/statements_<model>.csv          one row per skill statement
        data/processed/extraction_postings_<model>.csv every posting run (incl. zero-skill), tokens
        reports/token_usage.csv                        one row per run: calls, tokens in/out
Cache:  cache/<provider>/<sha256>.json                 key = model + prompt + text; re-runs are free
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


BACKENDS = {"gemini": GeminiBackend, "groq": GroqBackend}


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
    ap.add_argument("--delay", type=float, default=4.0, help="seconds between API calls (free-tier pacing)")
    ap.add_argument("--list-models", action="store_true")
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    Backend = BACKENDS[args.provider]

    if args.list_models:
        print("\n".join(Backend(args.model).list_models()))
        return
    if not args.model:
        sys.exit("Pass --model <id> (run --list-models first).")
    model = args.model

    system = PROMPT.read_text(encoding="utf-8")
    prompt_sha = hashlib.sha256(system.encode()).hexdigest()
    posts = pd.read_csv(POSTINGS, encoding="utf-8-sig")
    if args.limit:
        posts = posts.head(args.limit)
    cache = ROOT / "cache" / args.provider
    cache.mkdir(parents=True, exist_ok=True)
    backend, rows, done, failed, calls, tok_in, tok_out = None, [], [], [], 0, 0, 0

    for p in posts.itertuples():
        key = hashlib.sha256(f"{model}|{prompt_sha}|{p.description}".encode()).hexdigest()
        path = cache / f"{key}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            backend = backend or Backend(model)
            if calls:
                time.sleep(args.delay)
            try:
                out, t_in, t_out = call_with_retry(backend, system, p.description)
            except (ApiError, ValueError, KeyError) as e:  # keep going; a re-run retries only uncached postings
                print(f"#{p.n} {p.posting_id}: FAILED ({str(e)[:80]})", flush=True)
                failed.append(p.posting_id)
                continue
            data = {"posting_id": p.posting_id, "provider": Backend.name, "model": model,
                    "prompt_version": PROMPT_VERSION, "prompt_sha256": prompt_sha,
                    "tokens_in": t_in, "tokens_out": t_out, "output": out}
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            calls, tok_in, tok_out = calls + 1, tok_in + t_in, tok_out + t_out
        skills = [s for s in data["output"].get("skills", []) if s.get("skill")]
        print(f"#{p.n} {p.posting_id}: {len(skills)} skills", flush=True)
        done.append({"posting_id": p.posting_id, "n_skills": len(skills),  # tokens paid once, when first called
                     "tokens_in": data["tokens_in"], "tokens_out": data["tokens_out"]})
        low = p.description.lower()
        for i, s in enumerate(skills, 1):
            ev = str(s.get("evidence", "")).strip()
            rows.append({"statement_id": f"{p.posting_id}:skill:{i}", "posting_id": p.posting_id,
                         "skill": s["skill"].strip(), "evidence": ev, "evidence_in_text": bool(ev) and ev.lower() in low,
                         "provider": Backend.name, "model": model, "prompt_version": PROMPT_VERSION})

    PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED / f"statements_{slug(model)}.csv"
    pd.DataFrame(rows, columns=["statement_id", "posting_id", "skill", "evidence", "evidence_in_text", "provider",
                                "model", "prompt_version"]).to_csv(out_path, index=False)
    pd.DataFrame(done).to_csv(PROCESSED / f"extraction_postings_{slug(model)}.csv", index=False)
    new = not USAGE.exists()
    with USAGE.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["run_at", "provider", "model", "prompt_version", "postings", "api_calls", "tokens_in", "tokens_out"])
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), Backend.name, model,
                    PROMPT_VERSION, len(posts), calls, tok_in, tok_out])
    if failed:
        print(f"\n{len(failed)} postings FAILED (not scored). Re-run the same command to retry them.")
    print(f"\n{len(rows)} statements -> {out_path.relative_to(ROOT)} | new API calls {calls} | tokens in {tok_in:,} out {tok_out:,}")


if __name__ == "__main__":
    main()
