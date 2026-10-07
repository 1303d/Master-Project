"""Cross-check gold labels against the posting text.

For each labeled posting:
  - NOT IN TEXT: gold skills whose words are not found in the posting (possible mistake)
  - DROPPED: suggested skills the labeler removed (possible miss)
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STOP = {"and", "of", "the", "in", "for", "with", "to", "a", "skills", "skill", "knowledge", "drafting",
        "preparation", "management", "communication", "systems", "system"}


def words(s):
    return {w for w in re.findall(r"[a-z0-9+#.]+", s.lower()) if w not in STOP and len(w) > 1}


def grounded(skill, text_words):
    """True if at least half of the skill's content words appear in the text (prefix match)."""
    ws = words(skill)
    if not ws:
        return True
    hits = sum(any(t.startswith(w[:5]) for t in text_words) for w in ws)
    return hits / len(ws) >= 0.5


def split(s):
    return [x.strip() for x in s.split(";") if x.strip()]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    labels = pd.read_csv(ROOT / "data/gold/gold_labels.csv", dtype=str, keep_default_na=False)
    posts = pd.read_parquet(ROOT / "data/interim/postings_clean.parquet", columns=["posting_id", "description"])
    text = dict(zip(posts.posting_id, posts.description))
    done = labels[labels.gold_skills != ""]
    for _, r in done.iterrows():
        tw = words(text[r.posting_id])
        gold = split(r.gold_skills)
        not_in = [g for g in gold if not grounded(g, tw)]
        gold_w = set().union(*(words(g) for g in gold)) if gold else set()
        dropped = [s for s in split(r.suggested_skills) if not (words(s) & gold_w)]
        print(f"#{r.n} {r.title[:40]}  ({len(gold)} skills)")
        print(f"   NOT IN TEXT: {not_in or '-'}")
        print(f"   DROPPED:     {dropped or '-'}")


if __name__ == "__main__":
    main()
