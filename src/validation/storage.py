"""File helpers: hashes, stable IDs, atomic JSON writes, append-only JSONL event logs."""
import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()  # one writer at a time inside the dashboard process


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_id(prefix, *parts):
    """Same inputs -> same ID on every machine, so rebuilding never duplicates a finding."""
    key = "|".join(str(p).strip().lower() for p in parts)
    return f"{prefix}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]}"


def write_json_atomic(path, obj, overwrite=False):
    """Write via a temp file + rename, so a crash never leaves half a file. Refuses to replace by default."""
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path.name} already exists (never overwritten)")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def append_jsonl(path, record):
    """Append one event as one line (flushed + fsynced). Earlier lines are never rewritten."""
    path = Path(path)
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())


def read_jsonl(path):
    """All events of a log. A broken line (e.g. an unresolved Git merge) is reported, never silently dropped."""
    path = Path(path)
    if not path.is_file():
        return [], []
    events, bad = [], []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            bad.append(f"{path.name}:{i}")
    return events, bad


def git_head(root):
    """Current commit (read from .git, no git command), for provenance; None when unknown."""
    git = Path(root) / ".git"
    try:
        ref = (git / "HEAD").read_text().strip()
        if ref.startswith("ref: "):
            target = git / ref[5:]
            if target.is_file():
                return target.read_text().strip()[:12]
            packed = git / "packed-refs"
            for line in packed.read_text().splitlines() if packed.is_file() else []:
                if line.endswith(ref[5:]):
                    return line.split()[0][:12]
            return None
        return ref[:12]
    except OSError:
        return None
