"""Read the source artifacts with row-level protection.

Every row is checked before it is kept: only `allowed_split` (dev) postings, never the protected agreement
postings, never duplicates or unknown splits. Excluded rows are only counted (never printed or stored).
"""
import csv
import re
from pathlib import Path

csv.field_size_limit(10_000_000)  # posting descriptions are long


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split_labels(s):
    """Same rule as evaluate.split: ';'-separated, stripped, empty items dropped."""
    return [x.strip() for x in str(s or "").split(";") if x.strip()]


class MissingArtifact(Exception):
    def __init__(self, path, hint=""):
        super().__init__(f"missing artifact: {path}" + (f" ({hint})" if hint else ""))
        self.path, self.hint = str(path), hint


def require(cfg, path, hint=""):
    if path is None or not Path(path).is_file():
        raise MissingArtifact(cfg.shown(path), hint)
    return Path(path)


def load_split(cfg):
    return {r["posting_id"]: r.get("split", "") for r in read_csv(require(cfg, cfg.p("split")))}


def load_gold(cfg):
    """Eligible gold postings: {posting_id: {"n", "posting_id", "sector", "labels"}} + exclusion counts."""
    split = load_split(cfg)
    rows = read_csv(require(cfg, cfg.p("gold"), "tracked in Git: pull the repository"))
    ids = [r["posting_id"] for r in rows]
    stats = {"protected": 0, "other_split": 0, "unknown_split": 0, "duplicate": 0}
    gold = {}
    for r in rows:
        pid, n = r["posting_id"], str(r["n"]).strip()
        if n in cfg.protected_n:
            stats["protected"] += 1
            continue
        s = split.get(pid)
        if s is None or s == "":
            stats["unknown_split"] += 1
            continue
        if s != cfg.allowed_split:
            stats["other_split"] += 1
            continue
        if ids.count(pid) > 1:
            stats["duplicate"] += 1
            continue
        gold[pid] = {"n": n, "posting_id": pid, "sector": r.get("sector_fixed") or r.get("sector", ""),
                     "labels": split_labels(r.get("gold_skills"))}
    return gold, stats


def report_info(path):
    """Postings a run did NOT score (from the evaluate.py report) and its gold total, when parseable."""
    if path is None or not Path(path).is_file():
        return {"not_scored": None, "gold_total": None}
    text = Path(path).read_text(encoding="utf-8")
    m = re.search(r"NOT scored \(failed or not run\): ([^\n.]+)", text)
    total = re.search(r"^\| \*\*All\*\* \| \d+ \| (\d+) \|", text, re.M)
    return {"not_scored": [x.strip() for x in m.group(1).split(",")] if m else [],
            "gold_total": int(total.group(1)) if total else None}


def load_errors(cfg, run_id, gold):
    """Error rows of one run for eligible postings: [{"posting_id", "n", "type", "label"}] + exclusion count.
    error 'missed' = gold-only (missed by the model), 'extra' = model-only."""
    run = cfg.run(run_id)
    by_n = {g["n"]: g for g in gold.values()}
    out, excluded = [], 0
    for r in read_csv(require(cfg, run["errors"], "written by src/evaluate.py")):
        g = by_n.get(str(r["n"]).strip())  # protected / test / unknown n are not in `gold`
        label = str(r.get("skill") or "").strip()
        if g is None or not label or r.get("error") not in ("missed", "extra"):
            excluded += 1
            continue
        out.append({"posting_id": g["posting_id"], "n": g["n"],
                    "type": "gold_only" if r["error"] == "missed" else "model_only", "label": label})
    return out, excluded


def load_postings(cfg, allowed_ids):
    """Descriptions for the allowed posting IDs only ({} + path=None when the Drive file is not here)."""
    path = cfg.postings_file()
    if path is None:
        return {}, None
    allowed = set(allowed_ids)
    texts = {r["posting_id"]: r.get("description") or "" for r in read_csv(path) if r.get("posting_id") in allowed}
    return texts, path
