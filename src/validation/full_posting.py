"""Part 3 — independent annotation of whole postings (finds skills that both the model and gold missed).

The reviewer starts from an empty form: no gold labels, no model output, no AI suggestions. Each skill needs
an evidence phrase that occurs in the posting; the location is stored. Comparison with gold opens only after
the annotation is submitted, and every later change is a new version.
"""
import re

from validation.matching import compare_annotation
from validation.sampling import sample_ids
from validation.sources import load_errors, load_gold, load_postings
from validation.storage import sha256_text, stable_id

CONFIDENCE = ("high", "medium", "low")


def item_id(posting_id):
    return stable_id("p3", posting_id)


def build(cfg):
    part = cfg.part(3)
    gold, gold_stats = load_gold(cfg)
    chosen = sample_ids(gold, part["sample_size"], part["seed"])
    texts, path = load_postings(cfg, chosen)
    items = sorted(({"item_id": item_id(pid), "posting_id": pid, "n": gold[pid]["n"],
                     "description_sha256": sha256_text(texts[pid]) if pid in texts else None} for pid in chosen),
                   key=lambda x: int(x["n"]))
    stats = {"eligible_postings": len(gold), "excluded_postings": gold_stats, "sampled": len(items),
             "sample_size": part["sample_size"], "seed": part["seed"],
             "postings_file": cfg.rel(path) if path else None}
    return items, stats


def locate(description, evidence):
    """Where the evidence occurs: exact first, then ignoring case and runs of whitespace. None = not found."""
    if not evidence:
        return None
    i = description.find(evidence)
    if i >= 0:
        return {"start": i, "end": i + len(evidence), "mode": "exact", "occurrences": description.count(evidence)}
    pattern = r"\s+".join(re.escape(w) for w in evidence.split())
    m = list(re.finditer(pattern, description, flags=re.IGNORECASE))
    if m:
        return {"start": m[0].start(), "end": m[0].end(), "mode": "case_whitespace_insensitive", "occurrences": len(m)}
    return None


def validate(item, data, description, final):
    """Check a draft (final=False: evidence may still be wrong) or a submission (final=True: all must be valid)."""
    skills, seen, problems = [], set(), []
    for i, s in enumerate(data.get("skills") or [], 1):
        name, ev = str(s.get("skill") or "").strip(), str(s.get("evidence") or "").strip()
        conf = str(s.get("confidence") or "").strip().lower()
        if not name and not ev:
            continue
        loc = locate(description, ev) if description is not None else None
        if not name:
            problems.append(f"row {i}: skill name is empty")
        if name.lower() in seen:
            problems.append(f"row {i}: '{name}' is listed twice")
        seen.add(name.lower())
        if not ev:
            problems.append(f"row {i}: evidence is required")
        elif description is not None and loc is None:
            problems.append(f"row {i}: evidence not found in the posting")
        if conf not in CONFIDENCE:
            problems.append(f"row {i}: confidence must be high, medium or low")
        skills.append({"skill": name, "evidence": ev, "location": loc, "confidence": conf,
                       "notes": str(s.get("notes") or "").strip()})
    if final:
        if description is None:
            raise ValueError("the posting text is not on this machine, so evidence cannot be checked (see Source versions)")
        if problems:
            raise ValueError("; ".join(problems))
    return {"skills": skills, "overall_confidence": str(data.get("overall_confidence") or "").strip().lower(),
            "notes": str(data.get("notes") or "").strip(),
            "description_sha256": sha256_text(description) if description is not None else None,
            "problems": problems}


def model_extras(cfg, posting_id):
    """Model-only labels of the configured runs for one posting (used only after submission)."""
    gold, _ = load_gold(cfg)
    out = []
    for run_id in cfg.part(1)["runs"]:
        rows, _ = load_errors(cfg, run_id, gold)
        out += [r["label"] for r in rows if r["posting_id"] == posting_id and r["type"] == "model_only"]
    return out


def compare(cfg, posting_id, submitted):
    gold, _ = load_gold(cfg)
    if posting_id not in gold:
        raise ValueError("posting is not eligible")
    return compare_annotation([s["skill"] for s in submitted["skills"]], gold[posting_id]["labels"],
                              model_extras(cfg, posting_id))


def proposed_change(row):
    """Comparison row -> candidate gold change for adjudication (None = nothing to decide)."""
    if row["kind"] in ("reviewer_only", "shared_omission"):
        return {"action": "add", "from_label": None, "to_label": row["reviewer_label"]}
    if row["kind"] == "gold_only":
        return {"action": "remove", "from_label": row["gold_label"], "to_label": None}
    if row["kind"] == "naming_difference":
        return {"action": "revise", "from_label": row["gold_label"], "to_label": row["reviewer_label"]}
    return None
