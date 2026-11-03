"""Progress metrics for the Gold Validation page and exportable reports (reports/validation/, never overwritten).

Proposals are counted as proposals: nothing here calls a gold label wrong until adjudication approves it.
All counts use each reviewer's official (blind) version: amendments made after a reveal never change them.
"""
import json
from collections import Counter
from datetime import datetime, timezone

from validation import adjudication, manifests
from validation.config import PARTS
from validation.reviews import ReviewStore
from validation.storage import utc_now

OPEN = ("SUBMITTED", "NEEDS_DISCUSSION")


def summary(cfg):
    store = ReviewStore(cfg)
    cases = adjudication.build_cases(cfg, store)
    status = Counter(c["status"] for c in cases)
    out = {"generated_utc": utc_now(), "parts": {}, "team": {}}
    per_reviewer = {r: {} for r in cfg.reviewers}
    for part in PARTS:
        m = manifests.active(cfg, part)
        if not m:
            out["parts"][part] = {"manifest": None}
            continue
        ids = {i["item_id"] for i in m["items"]}
        states = store.all_states(m["manifest_id"])
        reviewed = {i for st in states.values() for i, s in st.items() if s["official"] and i in ids}
        decisions = Counter(s["official"]["decision"] for st in states.values() for s in st.values()
                            if s["official"] and part != 3)
        pc = [c for c in cases if c["part"] == part]
        kinds = Counter(r["kind"] for c in pc for r in c["reviews"])
        p = {"manifest": m["manifest_id"], "items": len(ids), "reviewed": len(reviewed), "pending": len(ids - reviewed),
             "unresolved": sum(c["status"] in OPEN for c in pc), "stale_sources": manifests.stale_sources(cfg, m)}
        if part == 1:
            p.update(total_disagreements=m["population"]["total"], proposed_additions=decisions["ADD_TO_GOLD"],
                     proposed_removals=decisions["REMOVE_FROM_GOLD"], proposed_revisions=decisions["REVISE_GOLD"],
                     unsure=decisions["UNSURE"])
        elif part == 2:
            p.update(eligible_agreements=m["population"]["eligible_agreements"], sampled=len(ids),
                     invalid_labels_found=decisions["INVALID_SKILL"], revision_requests=decisions["NEEDS_REVISION"],
                     unsure=decisions["UNSURE"])
        else:
            p.update(selected_postings=len(ids), completed_reviews=len(reviewed),
                     candidate_shared_omissions=kinds["shared_omission"], candidate_reviewer_only=kinds["reviewer_only"],
                     candidate_unsupported_gold=kinds["gold_only"], naming_differences=kinds["naming_difference"])
        out["parts"][part] = p
        for r, st in states.items():
            per_reviewer[r][part] = {"submitted": sum(1 for i, s in st.items() if s["official"] and i in ids),
                                     "drafts": sum(1 for s in st.values() if s["status"] == "IN_REVIEW"), "total": len(ids)}
    out["team"] = {"per_reviewer": per_reviewer, "awaiting_adjudication": status["SUBMITTED"],
                   "needs_discussion": status["NEEDS_DISCUSSION"], "approved": status["APPROVED"],
                   "rejected": status["REJECTED"], "cases": len(cases),
                   "remaining_unreviewed_items": sum(p.get("pending", 0) for p in out["parts"].values())}
    return out


def to_markdown(s):
    lines = ["# Gold validation — progress report", "", f"Generated {s['generated_utc']} (UTC). "
             "Counts of proposals and candidates are not confirmed gold errors until adjudication approves them.", ""]
    names = {1: "Part 1 — Disagreements", 2: "Part 2 — Agreements (blind)", 3: "Part 3 — Full postings"}
    for part, p in s["parts"].items():
        lines += [f"## {names[int(part)]}", ""]
        lines += [f"- {k.replace('_', ' ')}: {v if not isinstance(v, list) else (', '.join(v) or 'none')}" for k, v in p.items()]
        lines.append("")
    t = s["team"]
    lines += ["## Team", "", "| Reviewer | Part 1 | Part 2 | Part 3 |", "|---|---|---|---|"]
    for r, parts in t["per_reviewer"].items():
        lines.append(f"| {r} | " + " | ".join(f"{v['submitted']}/{v['total']}" for v in parts.values()) + " |")
    lines += ["", f"- cases: {t['cases']} · awaiting adjudication: {t['awaiting_adjudication']} · needs discussion: "
              f"{t['needs_discussion']} · approved: {t['approved']} · rejected: {t['rejected']}",
              f"- remaining unreviewed items: {t['remaining_unreviewed_items']}", ""]
    return "\n".join(lines)


def export(cfg):
    """Write a timestamped .md + .json pair; an existing report is never replaced."""
    s = summary(cfg)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    md, js = (cfg.reports_dir / f"validation_progress_{stamp}.{ext}" for ext in ("md", "json"))
    if md.exists() or js.exists():
        raise FileExistsError(f"{md.name} already exists; try again in a second")
    md.write_text(to_markdown(s), encoding="utf-8", newline="\n")
    js.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8", newline="\n")
    return [cfg.rel(md), cfg.rel(js)]
