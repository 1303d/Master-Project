"""Merge safe spelling variants of skill keys before clustering (Sprint 3, step 1 of the clustering review).

    py src/normalize_aliases.py --mentions PREPARED_MENTIONS.csv --skills UNIQUE_SKILLS.csv --out-dir OUT

Rules (deterministic, conservative; anything else is left for a reviewed alias table):
  R1 hyphens / dashes -> space, collapse spaces, strip trailing . , ;      problem-solving -> problem solving
  R2 leading "ms " -> "microsoft "                                          ms excel -> microsoft excel
  R3 drop a trailing " skills"/" skill" only if the shorter key exists      communication skills -> communication
  R4 human-verified aliases from config/skill_aliases_manual.csv            excel -> microsoft excel
Output: OUT/aliases.csv (skill_key, canonical_key, rules), OUT/unique_skills.csv (same columns as
prepare_skills.py, one row per canonical key, ready for embed_skills.py). Refuses to overwrite outputs.
"""
import argparse
import re
from pathlib import Path

import pandas as pd

OUTPUTS = ["aliases.csv", "unique_skills.csv"]
NOT_MICROSOFT = {"ms drg"}  # MS-DRG = Medicare Severity Diagnosis Related Groups
ROOT = Path(__file__).resolve().parents[1]
MANUAL = pd.read_csv(ROOT / "config" / "skill_aliases_manual.csv", keep_default_na=False)     .set_index("skill_key")["canonical_key"].to_dict()


def rule1(key):
    key = re.sub(r"[‐-―-]+", " ", key)
    return re.sub(r"\s+", " ", key).strip().rstrip(".,;").strip()


def rule2(key):
    return "microsoft " + key[3:] if key.startswith("ms ") and key not in NOT_MICROSOFT else key


def canonical_map(keys):
    """Return {skill_key: (canonical_key, rules)} for every input key."""
    step = {}
    for k in keys:
        c, rules = k, []
        for name, fn in (("R1", rule1), ("R2", rule2)):
            new = fn(c)
            if new != c:
                c, rules = new, rules + [name]
        step[k] = (c, rules)
    known = {c for c, _ in step.values()}
    out = {}
    for k, (c, rules) in step.items():
        short = re.sub(r" skills?$", "", c)
        if short != c and short and short in known:
            c, rules = short, rules + ["R3"]
        if MANUAL.get(c) in known:  # R4: human-verified alias, only onto a key that exists
            c, rules = MANUAL[c], rules + ["R4"]
        out[k] = (c, ";".join(rules))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mentions", required=True, help="prepared_mentions.csv from prepare_skills.py")
    ap.add_argument("--skills", required=True, help="unique_skills.csv from prepare_skills.py")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    existing = [f for f in OUTPUTS if (out_dir / f).exists()]
    if existing:
        raise SystemExit(f"refusing to overwrite {existing} in {out_dir}")
    skills = pd.read_csv(args.skills, keep_default_na=False)
    mentions = pd.read_csv(args.mentions, keep_default_na=False, usecols=["posting_id", "skill_key"])

    cmap = canonical_map(skills["skill_key"])
    aliases = pd.DataFrame([(k, c, r) for k, (c, r) in cmap.items()], columns=["skill_key", "canonical_key", "rules"])
    skills = skills.merge(aliases, on="skill_key")
    mentions["canonical_key"] = mentions["skill_key"].map(lambda k: cmap[k][0])

    # display label = label of the most-mentioned member; counts recomputed from mentions (no double counting)
    label = skills.sort_values("mention_count", ascending=False).drop_duplicates("canonical_key")
    agg = mentions.groupby("canonical_key").agg(mention_count=("posting_id", "size"),
                                                posting_count=("posting_id", "nunique")).reset_index()
    canon = agg.merge(label[["canonical_key", "display_label"]], on="canonical_key")
    canon = canon.rename(columns={"canonical_key": "skill_key"})[["skill_key", "display_label", "mention_count",
                                                                  "posting_count"]].sort_values("skill_key")

    out_dir.mkdir(parents=True, exist_ok=True)
    aliases.to_csv(out_dir / "aliases.csv", index=False)
    canon.to_csv(out_dir / "unique_skills.csv", index=False)
    merged = aliases[aliases["skill_key"] != aliases["canonical_key"]]
    print(f"{len(skills)} keys -> {len(canon)} canonical ({len(merged)} merged: "
          f"{merged['rules'].str.split(';').explode().value_counts().to_dict()})")


if __name__ == "__main__":
    main()
