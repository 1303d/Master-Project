"""--types feeds the JSON hint, the schema enum and the cache key; the key manifest refuses other settings.

    py -m pytest tests/test_types_and_guard.py -q
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import extract_skills as ex  # noqa: E402

MODEL = "qwen/qwen3.8-27b"


@pytest.fixture(autouse=True)
def restore_globals(monkeypatch):
    for name in ("SCHEMA", "JSON_HINT", "SETTINGS", "TYPES"):  # use_typed_schema changes module globals
        monkeypatch.setattr(ex, name, getattr(ex, name))


def test_types_option():
    ex.use_typed_schema()  # default list: settings as in earlier typed runs (no "types" entry)
    default = ex.call_settings("groq", MODEL, typed=True)
    assert "types" not in default

    ex.use_typed_schema(["skill", "knowledge", "tool"])
    assert '"skill|knowledge|tool"' in ex.JSON_HINT and "credential" not in ex.JSON_HINT
    assert ex.SCHEMA["properties"]["skills"]["items"]["properties"]["type"]["enum"] == ["skill", "knowledge", "tool"]
    three = ex.call_settings("groq", MODEL, typed=True)
    assert three["types"] == ["skill", "knowledge", "tool"]
    assert ex.cache_key(MODEL, "sha", three, "text") != ex.cache_key(MODEL, "sha", default, "text")


def manifest(key, settings):
    return pd.DataFrame([{"posting_id": "li_1", "provider": "groq", "cache_key": key, "settings": settings}])


def test_manifest_guard(tmp_path):
    path = tmp_path / "cache_keys_run.csv"
    ex.check_manifest(path, manifest("k1", "{}"))  # no file yet: fine
    manifest("k1", "{}").to_csv(path, index=False)
    ex.check_manifest(path, manifest("k1", "{}"))  # same run again (resume): fine
    with pytest.raises(SystemExit):
        ex.check_manifest(path, manifest("k1", '{"typed": true}'))  # other settings
    with pytest.raises(SystemExit):
        ex.check_manifest(path, manifest("k2", "{}"))  # other model / prompt for the same posting
