"""LLM skill extractor behind a LiteLLM Router: primary model with automatic fallback, traced in Langfuse.

    py src/llm_router.py "We need SQL and Python. Strong communication skills."    # one test call

Chain (only models that passed our dev test, see docs/HANDOFF.md):
  1. groq/qwen/qwen3.8-27b       (GROQ_API_KEY)    dev lenient F1 .74, test .75
  2. gemini/gemini-3.8-flash     (GEMINI_API_KEY)  dev lenient F1 .79 on 20 postings
A rate limit (429) or error on one model sends the call to the next; a model that failed is put on
cooldown so later calls skip it for a while. Each answer reports which model actually served it.
Langfuse tracing is on when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set (LANGFUSE_HOST optional).
"""
import json
import logging
import os
import sys
from pathlib import Path

import litellm
from dotenv import load_dotenv
from litellm import Router

from extract_skills import JSON_HINT

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
PROMPT = ROOT / "prompts" / "skill_extraction_v3.txt"
CHAIN = [  # (litellm model, key variable, extra provider params)
    ("groq/qwen/qwen3.8-27b", "GROQ_API_KEY", {"temperature": 0, "reasoning_format": "hidden"}),  # no <think> in JSON
    ("gemini/gemini-3.8-flash", "GEMINI_API_KEY", {}),  # Gemini 3+ deprecates temperature
]
litellm.suppress_debug_info = True
for _name in ("LiteLLM", "LiteLLM Router"):  # its error dumps are long; pipeline_events records the failure
    logging.getLogger(_name).setLevel(logging.CRITICAL)


def langfuse_on():
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


class Extractor:
    def __init__(self, cooldown=600):
        deployments = [{"model_name": f"extractor-{i}",
                        "litellm_params": {"model": m, "api_key": os.getenv(key), **extra}}
                       for i, (m, key, extra) in enumerate(CHAIN) if os.getenv(key)]
        if not deployments:
            sys.exit("No LLM key in .env (GROQ_API_KEY or GEMINI_API_KEY)")
        names = [d["model_name"] for d in deployments]
        self.primary = names[0]
        self.models = {d["model_name"]: d["litellm_params"]["model"] for d in deployments}
        self.router = Router(model_list=deployments, fallbacks=[{names[0]: names[1:]}] if len(names) > 1 else [],
                             num_retries=0, allowed_fails=0, cooldown_time=cooldown)
        if langfuse_on():
            litellm.callbacks = ["langfuse_otel"]

    def extract(self, system, text, trace=None):
        """Return (parsed_json, tokens_in, tokens_out, served_model)."""
        r = self.router.completion(
            model=self.primary, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system + JSON_HINT}, {"role": "user", "content": text}],
            metadata={"generation_name": "skill-extraction", **(trace or {})})
        u = r.usage
        return json.loads(r.choices[0].message.content), u.prompt_tokens, u.completion_tokens, r.model


if __name__ == "__main__":
    out, t_in, t_out, served = Extractor().extract(PROMPT.read_text(encoding="utf-8"), " ".join(sys.argv[1:]) or
                                                   "We need SQL and Python. Strong communication skills.")
    print(served, t_in, t_out, json.dumps(out)[:300])
