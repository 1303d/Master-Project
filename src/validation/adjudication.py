"""Team adjudication of submitted reviews, and the separate, versioned approved-change set.

Cases come from submitted reviews only: proposed changes, UNSURE, and reviewers who disagree.
Adjudication decisions go to data/validation/adjudication/<adjudicator>.jsonl (append-only).
APPROVED never touches a gold file; `approve_version` writes approved_versions/<name>/ (changes.csv +
manifest.json) as an explicit step, and a later script/human applies that change set to a new gold file.
"""
import csv
import io
import uuid
from collections import defaultdict

from validation import agreements, disagreements, full_posting, manifests
from validation.config import PARTS
from validation.reviews import ReviewStore
from validation.storage import append_jsonl, read_jsonl, sha256_file, stable_id, utc_now, write_json_atomic

DECISIONS = ("APPROVED", "REJECTED", "NEEDS_DISCUSSION")


def _change_key(c):
    return (c["action"], (c.get("from_label") or "").lower(), (c.get("to_label") or "").lower()) if c else None


def build_cases(cfg, store=None):
    """All open questions across the three parts, with every submitted review that supports them.
    Uses each reviewer's official (blind) version; amendments made after a reveal are only counted."""
    store = store or ReviewStore(cfg)
    cases = {}
    for part in PARTS:
        m = manifests.active(cfg, part)
        if not m:
            continue
        items = {i["item_id"]: i for i in m["items"]}
        for reviewer, st in store.all_states(m["manifest_id"]).items():
            for item_id, s in st.items():
                off = s["official"]
                if not off:
                    continue
                item = items.get(item_id)
                if item is None:
                    continue
                rows = []
                if part == 3:
                    for row in full_posting.compare(cfg, item["posting_id"], off):
                        ch = full_posting.proposed_change(row)
                        if ch or row["ambiguous"]:
                            label = row["reviewer_label"] or row["gold_label"]
                            rows.append((stable_id("c3", item["posting_id"], row["kind"], label), ch,
                                         {"kind": row["kind"], "ambiguous": row["ambiguous"], "label": label,
                                          "evidence": next((x["evidence"] for x in off["skills"]
                                                            if x["skill"] == row["reviewer_label"]), None)}))
                else:
                    mod = disagreements if part == 1 else agreements
                    rows.append((stable_id(f"c{part}", item_id), mod.proposed_change(item, off),
                                 {"kind": item.get("type", "agreement"), "label": item["label"],
                                  "decision": off["decision"], "rule": off.get("rule"),
                                  "reason": off.get("reason") or off.get("explanation")}))
                for case_id, change, detail in rows:
                    c = cases.setdefault(case_id, {"case_id": case_id, "part": part, "manifest_id": m["manifest_id"],
                                                   "item_id": item_id, "posting_id": item["posting_id"], "n": item["n"],
                                                   "label": detail["label"], "reviews": [], "changes": {}})
                    c["reviews"].append({"reviewer": reviewer, "version": s["official_version"],
                                         "post_reveal_amendments": sum(v["post_reveal"] for v in s["versions"]),
                                         "change": change, **detail})
                    if change:
                        c["changes"][_change_key(change)] = change
    out = []
    for c in cases.values():
        unsure = any(r.get("decision") == "UNSURE" or r.get("ambiguous") for r in c["reviews"])
        keys = {_change_key(r["change"]) for r in c["reviews"]}
        c["conflict"] = len(keys) > 1  # reviewers proposed different things (incl. change vs no change)
        c["proposed_changes"] = list(c.pop("changes").values())
        if c["proposed_changes"] or unsure or c["conflict"]:
            out.append(c)
    _apply_adjudication(cfg, out)
    return sorted(out, key=lambda c: (c["part"], int(c["n"]), c["label"].lower()))


def adjudication_events(cfg):
    events, bad = [], []
    for r in cfg.reviewers:
        ev, b = read_jsonl(cfg.adjudication_file(r))
        events += [e for e in ev if e.get("adjudicator") == r]
        bad += b
    return sorted(events, key=lambda e: e["ts"]), bad


def _apply_adjudication(cfg, cases):
    events, _ = adjudication_events(cfg)
    by_case = defaultdict(list)
    for e in events:
        by_case[e["case_id"]].append(e)
    for c in cases:
        hist = by_case.get(c["case_id"], [])
        latest = {}
        for e in hist:
            latest[e["adjudicator"]] = e  # each adjudicator's latest word counts
        decisions = {(e["decision"], _change_key(e.get("change"))) for e in latest.values()}
        c["history"] = hist
        if not hist:
            c["status"] = "SUBMITTED"
        elif len(decisions) > 1:
            c["status"] = "NEEDS_DISCUSSION"  # adjudicators disagree: never resolved silently
        else:
            c["status"] = next(iter(decisions))[0]
        c["final_change"] = next(iter(latest.values()))["change"] if c["status"] == "APPROVED" else None


def adjudicate(cfg, adjudicator, case_id, decision, rationale, change=None):
    adjudicator = cfg.check_reviewer(adjudicator)
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
    if not str(rationale or "").strip():
        raise ValueError("a rationale is required")
    case = next((c for c in build_cases(cfg) if c["case_id"] == case_id), None)
    if case is None:
        raise ValueError(f"unknown case {case_id}")
    if decision == "APPROVED":
        if not change and len(case["proposed_changes"]) == 1:
            change = case["proposed_changes"][0]
        if not change or change.get("action") not in ("add", "remove", "revise"):
            raise ValueError("APPROVED needs exactly one change (add / remove / revise)")
        if change["action"] in ("add", "revise") and not str(change.get("to_label") or "").strip():
            raise ValueError("the approved change needs the final label")
        change = {"action": change["action"], "from_label": change.get("from_label"),
                  "to_label": str(change.get("to_label") or "").strip() or None}
    event = {"event_id": uuid.uuid4().hex, "ts": utc_now(), "adjudicator": adjudicator, "case_id": case_id,
             "part": case["part"], "manifest_id": case["manifest_id"], "posting_id": case["posting_id"],
             "decision": decision, "rationale": str(rationale).strip(), "change": change if decision == "APPROVED" else None}
    append_jsonl(cfg.adjudication_file(adjudicator), event)
    return event


def approve_version(cfg, name):
    """Write the APPROVED changes as a new, never-overwritten change set. Gold files are not modified."""
    if not name or any(ch in name for ch in r'\/:*?"<>| '):
        raise ValueError("give a simple version name, e.g. gold_v1_validation_2026-11")
    out = cfg.approved_dir / name
    if out.exists():
        raise FileExistsError(f"{cfg.rel(out)} already exists (never overwritten)")
    approved = [c for c in build_cases(cfg) if c["status"] == "APPROVED"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["case_id", "part", "manifest_id", "posting_id", "n", "action", "from_label", "to_label",
                "adjudicators", "rationale"])
    for c in approved:
        ch, last = c["final_change"], c["history"][-1]
        w.writerow([c["case_id"], c["part"], c["manifest_id"], c["posting_id"], c["n"], ch["action"],
                    ch.get("from_label") or "", ch.get("to_label") or "",
                    ";".join(sorted({e["adjudicator"] for e in c["history"]})), last["rationale"]])
    out.mkdir(parents=True)
    (out / "changes.csv").write_text(buf.getvalue(), encoding="utf-8", newline="")
    write_json_atomic(out / "manifest.json", {
        "name": name, "created_utc": utc_now(), "base_gold": {"file": cfg.rel(cfg.p("gold")),
                                                              "sha256": sha256_file(cfg.p("gold")),
                                                              "version": cfg.data.get("gold_version")},
        "manifests": {p: (manifests.active(cfg, p) or {}).get("manifest_id") for p in PARTS},
        "approved_changes": len(approved),
        "note": "Change set only. Gold files were not modified. Protected agreement postings are never included."})
    return out, len(approved)
