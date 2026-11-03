"""Part 1 — disagreements between model runs and the gold set (model-only extras, gold-only misses)."""
from collections import Counter

from validation.sources import load_errors, load_gold, read_csv
from validation.storage import stable_id

HIST_TYPE = {"model-only (extra)": "model_only", "gold-only (missed by model)": "gold_only"}
DECISIONS = ("KEEP_GOLD", "ADD_TO_GOLD", "REMOVE_FROM_GOLD", "REVISE_GOLD", "UNSURE")
CHANGES = ("ADD_TO_GOLD", "REMOVE_FROM_GOLD", "REVISE_GOLD")


def item_id(posting_id, kind, label):
    return stable_id("p1", posting_id, kind, label)


def build(cfg):
    """Items + population counts. Same finding in several runs = one item listing all runs."""
    part = cfg.part(1)
    gold, gold_stats = load_gold(cfg)
    items, excluded, stale = {}, {}, Counter()
    for run_id in part["runs"]:
        rows, excluded[run_id] = load_errors(cfg, run_id, gold)
        for r in rows:
            iid = item_id(r["posting_id"], r["type"], r["label"])
            it = items.setdefault(iid, {"item_id": iid, "posting_id": r["posting_id"], "n": r["n"], "type": r["type"],
                                        "label": r["label"], "runs": [], "stale": False})
            if run_id not in it["runs"]:
                it["runs"].append(run_id)
            # a "missed" label that is no longer in the current gold file -> the run used an older gold
            if r["type"] == "gold_only" and r["label"].lower() not in {g.lower() for g in gold[r["posting_id"]]["labels"]}:
                it["stale"] = True
                stale[run_id] += 1
    items = sorted(items.values(), key=lambda x: (int(x["n"]), x["type"], x["label"].lower()))
    counts = Counter(i["type"] for i in items)
    population = {"eligible_postings": len(gold), "excluded_postings": gold_stats,
                  "excluded_error_rows_per_run": excluded, "stale_rows_per_run": dict(stale),
                  "model_only": counts["model_only"], "gold_only": counts["gold_only"], "total": len(items),
                  "historical": part.get("historical_counts"), "historical_check": historical_check(cfg, gold, items)}
    return items, population


def historical_check(cfg, gold, items):
    """Compare with the earlier audit sheet on eligible postings only (counts only, nothing is printed)."""
    path = cfg.p("historical_audit")
    if not path.is_file():
        return {"available": False}
    eligible_n = {g["n"] for g in gold.values()}
    hist = {(r["n"], HIST_TYPE.get(r["source"], r["source"]), r["skill"].strip().lower())
            for r in read_csv(path) if str(r["n"]).strip() in eligible_n}
    mine = {(i["n"], i["type"], i["label"].lower()) for i in items}
    return {"available": True, "historical_items_on_eligible_postings": len(hist), "rebuilt_items": len(mine),
            "in_both": len(hist & mine), "only_historical": len(hist - mine), "only_rebuilt": len(mine - hist),
            "note": "The historical total (437) also counted the protected agreement postings, which are excluded here."}


def validate(item, data):
    d = data.get("decision")
    if d not in DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
    if d == "ADD_TO_GOLD" and item["type"] == "gold_only":
        raise ValueError("ADD_TO_GOLD does not apply: this label is already in gold")
    if d == "REMOVE_FROM_GOLD" and item["type"] == "model_only":
        raise ValueError("REMOVE_FROM_GOLD does not apply: this label is not in gold")
    if d == "REVISE_GOLD" and not str(data.get("proposed_label") or "").strip():
        raise ValueError("REVISE_GOLD needs the proposed label")
    if d in CHANGES and not str(data.get("reason") or "").strip():
        raise ValueError("a reason is required for every proposed change")
    if d in CHANGES and not str(data.get("rule") or "").strip():
        raise ValueError("choose the labelling rule that supports the change")
    return {"decision": d, "proposed_label": str(data.get("proposed_label") or "").strip(),
            "rule": str(data.get("rule") or "").strip(), "reason": str(data.get("reason") or "").strip()}


def proposed_change(item, decision):
    """What a decision proposes for gold (None = no change). Only adjudication can approve it."""
    d = decision["decision"]
    if d == "ADD_TO_GOLD":
        return {"action": "add", "from_label": None, "to_label": decision["proposed_label"] or item["label"]}
    if d == "REMOVE_FROM_GOLD":
        return {"action": "remove", "from_label": item["label"], "to_label": None}
    if d == "REVISE_GOLD":
        if item["type"] == "model_only":  # add under a corrected wording
            return {"action": "add", "from_label": None, "to_label": decision["proposed_label"]}
        return {"action": "revise", "from_label": item["label"], "to_label": decision["proposed_label"]}
    return None
