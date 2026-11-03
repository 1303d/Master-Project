"""Reviewer decisions as append-only events: data/validation/reviews/<reviewer>/events.jsonl.

Each reviewer writes only their own file, so teammates' pushes do not conflict. Actions:
  draft   save work in progress (allowed until the item is submitted)
  submit  lock the review (version 1); a second submit is refused
  amend   a new version with a reason; earlier versions stay in the log unchanged
  reveal  written by the server (never by a POST) when a reviewer is shown the reference, gold labels or other
          reviewers' decisions for an item (Parts 2-3). It is the point where the review stops being blind.

Official (blind) result = the last version submitted BEFORE the reviewer's first reveal of that item. Amendments
after a reveal are kept in the log and shown (post_reveal = true) but never change the official result, so the
reported scores and the adjudication cases stay blind. Order = order of lines in the append-only file.
"""
import uuid

from validation import agreements, disagreements, full_posting
from validation.storage import append_jsonl, read_jsonl, sha256_text, utc_now

PART_MODULES = {1: disagreements, 2: agreements, 3: full_posting}
ACTIONS = ("draft", "submit", "amend")  # what a reviewer may POST
REVEAL = "reveal"  # server-side audit event only


def _clean(part, item, data, description, final):
    if part == 3:
        return full_posting.validate(item, data, description, final)
    if not final:  # drafts of parts 1-2 may be incomplete
        return {k: str(v or "").strip() for k, v in data.items() if k in ("decision", "proposed_label", "rule", "reason", "explanation")}
    return PART_MODULES[part].validate(item, data)


class ReviewStore:
    def __init__(self, cfg):
        self.cfg = cfg

    def events(self, reviewer):
        events, bad = read_jsonl(self.cfg.reviews_file(reviewer))
        return [e for e in events if e.get("reviewer") == reviewer], bad

    def state(self, reviewer, manifest_id):
        """{item_id: {"status", "draft", "versions", "latest", "official", "official_version", "revealed"}}
        for one reviewer and one manifest. latest = newest version (the reviewer's own view); official = blind
        result used for scores and adjudication (see module docstring); revealed = time of the first reveal."""
        out = {}
        for e in self.events(reviewer)[0]:
            if e.get("manifest_id") != manifest_id:
                continue  # never mix decisions made on another manifest / gold version
            s = out.setdefault(e["item_id"], {"status": "PENDING", "draft": None, "versions": [], "latest": None,
                                              "official": None, "official_version": None, "revealed": None})
            if e["action"] == REVEAL:
                s["revealed"] = s["revealed"] or e["ts"]
            elif e["action"] == "draft" and not s["versions"]:
                s["draft"], s["status"] = e["data"], "IN_REVIEW"
            elif e["action"] in ("submit", "amend"):
                post = s["revealed"] is not None
                s["versions"].append({"version": e["version"], "ts": e["ts"], "action": e["action"],
                                      "data": e["data"], "amend_reason": e.get("amend_reason"), "post_reveal": post})
                s["latest"], s["draft"], s["status"] = e["data"], None, "SUBMITTED"
                if not post:
                    s["official"], s["official_version"] = e["data"], e["version"]
        return out

    def record_reveal(self, reviewer, manifest, item_ids, via):
        """Log that `reviewer` was shown answers for these items (once per item). Call only after the
        permission check passed, i.e. the reviewer has submitted the item."""
        reviewer = self.cfg.check_reviewer(reviewer)
        st = self.state(reviewer, manifest["manifest_id"])
        for item_id in item_ids:
            if st.get(item_id, {}).get("revealed"):
                continue
            append_jsonl(self.cfg.reviews_file(reviewer), {
                "event_id": uuid.uuid4().hex, "ts": utc_now(), "reviewer": reviewer, "part": manifest["part"],
                "manifest_id": manifest["manifest_id"], "item_id": item_id, "action": REVEAL, "via": via,
                "version": None, "amend_reason": None, "data": None, "sources": manifest["sources"]})

    def all_states(self, manifest_id):
        return {r: self.state(r, manifest_id) for r in self.cfg.reviewers}

    def record(self, reviewer, manifest, item_id, action, data, description=None, amend_reason=""):
        reviewer = self.cfg.check_reviewer(reviewer)
        if action not in ACTIONS:
            raise ValueError(f"action must be one of {', '.join(ACTIONS)}")
        item = next((i for i in manifest["items"] if i["item_id"] == item_id), None)
        if item is None:
            raise ValueError(f"{item_id} is not in {manifest['manifest_id']}")
        part = manifest["part"]
        if part == 3 and description is not None and item.get("description_sha256"):
            if sha256_text(description) != item["description_sha256"]:
                raise ValueError("the posting text differs from the one sampled (hash mismatch); get the shared file")
        cur = self.state(reviewer, manifest["manifest_id"]).get(item_id, {"versions": []})
        submitted = bool(cur["versions"])
        if action in ("draft", "submit") and submitted:
            raise ValueError("already submitted: the submission is locked; use 'amend' to add a new version")
        if action == "amend":
            if not submitted:
                raise ValueError("nothing to amend: submit first")
            if not str(amend_reason or "").strip():
                raise ValueError("an amendment needs a reason")
        clean = _clean(part, item, data or {}, description, final=action != "draft")
        event = {"event_id": uuid.uuid4().hex, "ts": utc_now(), "reviewer": reviewer, "part": part,
                 "manifest_id": manifest["manifest_id"], "item_id": item_id, "action": action,
                 "version": len(cur["versions"]) + 1 if action != "draft" else None,
                 "amend_reason": str(amend_reason or "").strip() or None, "data": clean,
                 "sources": manifest["sources"]}
        append_jsonl(self.cfg.reviews_file(reviewer), event)
        return event
