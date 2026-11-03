"""Part 2 — blind check of labels the model and gold agree on (agreement does not prove correctness).

The reviewer sees only the posting and the candidate label. Which run matched it, and that it is in gold,
live in a separate key file that the API reveals only after the reviewer has submitted that item.
"""
from collections import Counter

from validation.sampling import sample_fraction
from validation.sources import load_errors, load_gold, report_info
from validation.storage import stable_id

DECISIONS = ("VALID_SKILL", "INVALID_SKILL", "NEEDS_REVISION", "UNSURE")


def item_id(posting_id, label):
    return stable_id("p2", posting_id, label)


def build(cfg):
    part = cfg.part(2)
    gold, gold_stats = load_gold(cfg)
    missed, skipped = {}, Counter()
    unreliable = set()
    for run_id in part["runs"]:
        rows, _ = load_errors(cfg, run_id, gold)
        not_scored = report_info(cfg.run(run_id)["report"])["not_scored"]
        if not_scored is None:
            raise ValueError(f"run {run_id}: its report is needed to know which postings were scored")
        unreliable |= set(not_scored)  # unscored postings have no error rows, so they would look like full agreement
        m = missed.setdefault(run_id, {})
        for r in rows:
            if r["type"] == "gold_only":
                m.setdefault(r["posting_id"], Counter())[r["label"].lower()] += 1
        for pid, labels in m.items():  # stale error file (older gold) -> agreements cannot be trusted
            if any(lab not in {g.lower() for g in gold[pid]["labels"]} for lab in labels):
                unreliable.add(pid)
    population = []
    for pid, g in gold.items():
        if pid in unreliable:
            skipped["posting_unscored_or_stale"] += 1
            continue
        seen = set()
        for label in g["labels"]:
            if label.lower() in seen:
                skipped["duplicate_label"] += 1
                continue
            seen.add(label.lower())
            if all(missed.get(r, {}).get(pid, Counter())[label.lower()] == 0 for r in part["runs"]):
                population.append({"item_id": item_id(pid, label), "posting_id": pid, "n": g["n"], "label": label})
    by_id = {p["item_id"]: p for p in population}
    chosen = sample_fraction(by_id, part["sample_fraction"], part["seed"])
    items = sorted((by_id[i] for i in chosen), key=lambda x: (int(x["n"]), x["label"].lower()))
    key = {i["item_id"]: {"source": "agreement", "in_gold": True, "matched_by_runs": list(part["runs"])} for i in items}
    stats = {"eligible_postings": len(gold), "excluded_postings": gold_stats, "skipped": dict(skipped),
             "eligible_agreements": len(population), "sampled": len(items),
             "sample_fraction": part["sample_fraction"], "seed": part["seed"]}
    return items, stats, key


def validate(item, data):
    d = data.get("decision")
    if d not in DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
    explanation = str(data.get("explanation") or "").strip()
    if d in ("INVALID_SKILL", "NEEDS_REVISION") and not explanation:
        raise ValueError("explain why the label is invalid or needs revision")
    if d == "NEEDS_REVISION" and not str(data.get("proposed_label") or "").strip():
        raise ValueError("NEEDS_REVISION needs the proposed label")
    return {"decision": d, "explanation": explanation, "proposed_label": str(data.get("proposed_label") or "").strip(),
            "rule": str(data.get("rule") or "").strip()}


def proposed_change(item, decision):
    if decision["decision"] == "INVALID_SKILL":
        return {"action": "remove", "from_label": item["label"], "to_label": None}
    if decision["decision"] == "NEEDS_REVISION":
        return {"action": "revise", "from_label": item["label"], "to_label": decision["proposed_label"]}
    return None
