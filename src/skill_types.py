"""Give every canonical skill a type, from its ESCO / O*NET reference link (rule E) and the human reviews.

    py src/skill_types.py --skills data/processed/.../canonical_v2/unique_skills.csv --out data/processed/.../canonical_v2/skill_types.csv

skill_type (from Supabase skill_links, so review decisions count):
  trait        verdict trait (ESCO attitude / O*NET Work Style, or a reviewer said so)
  not_a_skill  a reviewer said so
  tool         known skill linked to O*NET software / software category (excel, sap, python)
  knowledge    known skill linked to ESCO knowledge / O*NET Knowledge (accounting, gaap)
  skill        known skill linked to an ESCO skill / O*NET Transferable or Essential Skills (negotiation)
  unknown      new_candidate: no reference match strong enough, so no type is claimed
A reviewed alias ("excel" -> "microsoft excel") takes the type of its target. A reviewer's "it is a skill" without a
reference keeps type skill.
reuse_level: ESCO's own scope (transversal / cross-sector / sector-specific / occupation-specific) when the link is ESCO.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402

TYPE_OF_SOURCE = {"O*NET software": "tool", "O*NET software category": "tool", "ESCO knowledge": "knowledge",
                  "O*NET Knowledge": "knowledge", "ESCO skill": "skill", "O*NET Transferable Skills": "skill",
                  "O*NET Essential Skills": "skill"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills", required=True, help="unique_skills.csv (canonical keys)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    keys = pd.read_csv(args.skills, keep_default_na=False)["skill_key"]
    links = pd.DataFrame(db.connect().execute("select skill_key, verdict, source, ref_label, ref_id from skill_links").fetchall(),
                         columns=["skill_key", "verdict", "source", "ref_label", "ref_id"]).set_index("skill_key")
    reuse = pd.read_csv(ROOT / "data" / "reference" / "esco_skills.csv", usecols=["uri", "reuse_level"]).set_index("uri")["reuse_level"]

    def typed(k, depth=0):
        if k not in links.index:
            return "unknown", "", "no link"
        r = links.loc[k]
        if r.verdict in ("trait", "not_a_skill"):
            return r.verdict, "", r.source
        if r.source == "human review":  # alias -> inherit from the target, else the reviewer's verdict
            target = (r.ref_label or "").lower()
            if target and target != k and depth < 3:
                t, lvl, src = typed(target, depth + 1)
                return t, lvl, f"alias of {target} ({src})"
            return ("skill" if r.verdict == "known_skill" else "unknown"), "", "human review"
        if r.verdict != "known_skill":
            return "unknown", "", f"no strong match (nearest: {r.source})"
        return TYPE_OF_SOURCE.get(r.source, "unknown"), reuse.get(r.ref_id, "") if r.ref_id else "", r.source

    out = pd.DataFrame([(k, *typed(k)) for k in keys], columns=["skill_key", "skill_type", "reuse_level", "type_source"])
    out["reuse_level"] = out["reuse_level"].fillna("")
    out.to_csv(args.out, index=False)
    print(out["skill_type"].value_counts().to_string())
    print("-> " + args.out)


if __name__ == "__main__":
    main()
