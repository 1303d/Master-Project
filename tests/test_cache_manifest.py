"""The loader finds new-format cache entries through the key manifest, and old ones through the legacy key.

    py -m pytest tests/test_cache_manifest.py -q
"""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import extract_skills as ex  # noqa: E402
import load_supabase as ls  # noqa: E402

MODEL, TEXT = "qwen/qwen3.8-27b", "We need Python and a valid RN license."


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "ROOT", tmp_path)
    (tmp_path / "cache" / "groq").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    prompt = tmp_path / "p.txt"
    prompt.write_text("extract skills", encoding="utf-8")
    posts = pd.DataFrame([{"posting_id": "li_1", "description": TEXT}])
    return prompt, posts, hashlib.sha256(b"extract skills").hexdigest()


def write_cache(tmp_path, key, skills):
    (tmp_path / "cache" / "groq" / f"{key}.json").write_text(
        json.dumps({"provider": "groq", "output": {"skills": skills}}), encoding="utf-8")


def test_new_format_key_via_manifest(tmp_path, monkeypatch):
    prompt, posts, sha = setup(tmp_path, monkeypatch)
    settings = ex.call_settings("groq", MODEL, typed=True)
    key = ex.cache_key(MODEL, sha, settings, TEXT)
    assert key != hashlib.sha256(f"{MODEL}|{sha}|{TEXT}".encode()).hexdigest()  # really a new-format key
    write_cache(tmp_path, key, [{"skill": "Python", "type": "tool", "evidence": "Python"},
                                {"skill": "RN license", "type": "credential", "evidence": "RN license"}])
    pd.DataFrame([{"posting_id": "li_1", "provider": "groq", "cache_key": key}]).to_csv(
        tmp_path / "data" / "processed" / "cache_keys_testrun.csv", index=False)

    rows, done = ls.cached_statements(posts, "groq", MODEL, prompt, None, run="testrun")
    assert done == 1 and [r["skill"] for r in rows] == ["Python"]  # credential is not a scored type
    # without the manifest the legacy key is used, and a new-format entry is not found
    assert ls.cached_statements(posts, "groq", MODEL, prompt, None)[1] == 0


def test_legacy_key_still_works(tmp_path, monkeypatch):
    prompt, posts, sha = setup(tmp_path, monkeypatch)
    write_cache(tmp_path, hashlib.sha256(f"{MODEL}|{sha}|{TEXT}".encode()).hexdigest(),
                [{"skill": "Python", "evidence": "Python"}])  # untyped answer from before 2026-10-30
    rows, done = ls.cached_statements(posts, "groq", MODEL, prompt, None)
    assert done == 1 and [r["skill"] for r in rows] == ["Python"]
