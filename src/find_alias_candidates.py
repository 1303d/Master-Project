"""Cross-check the canonical skill keys for duplicates (same skill, two names) with three independent signals.

    py src/find_alias_candidates.py --dir data/processed/sprint3_full_2026-10-22/canonical --out reports/alias_candidates.csv

Signals for a pair of keys:
  rule    equal after removing "(...)" parts, plurals, punctuation and spaces (power bi = powerbi,
          accounts payable (ap) = accounts payable); tagged "plural" when only a plural differs (canvas vs canva!)
  level   one key = a level word + the other key (advanced excel = excel; "basic life support" needs a human)
  vendor  one key = a vendor word + the other key (adobe photoshop = photoshop; never adobe suite = google suite;
          "google analytics" vs "analytics" needs a human)
  embed   cosine >= COS_MIN between the bge-small embeddings (mutual top-5 neighbours)
  ref     both keys link to the same ESCO / O*NET entry with a strong match (Supabase skill_links)
Tier: high = rule (spelling only); medium = level or vendor AND embed or ref; low = anything else. Hand checks of
samples: embed / ref alone are often broad vs narrow ("trend analysis" vs "market trend analysis"), and a level /
vendor word alone is often wrong ("sap erp" vs "erp"), so low is not a merge suggestion. One row per alias -> keep: the key equal to its reference label if there is one
(excel -> microsoft excel), else the more-mentioned key. Nothing is merged here:
accepted rows go to config/skill_aliases_manual.csv (rule R4 of normalize_aliases.py).
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402

LEVEL = r"advanced|basic|intermediate|expert|beginner|proficient|strong|excellent|solid|working knowledge of|knowledge of"
VENDOR = r"microsoft|ms|adobe|google|apache|amazon|aws|ibm|oracle|sap|salesforce|autodesk|atlassian"
COS_MIN, K = 0.93, 5
STRONG_REF = 0.9  # skill_links score for a reference match to count (exact matches have score 1 or null)


def singular(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")) else w


def norm(key, plural=True):
    k = re.sub(r"\([^)]*\)", " ", key.lower()).replace("&", " and ")
    return "".join(singular(w) if plural else w for w in re.findall(r"[a-z0-9+#]+", k))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="canonical folder (unique_skills.csv, embeddings/)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    d = Path(args.dir)
    skills = pd.read_csv(d / "unique_skills.csv", keep_default_na=False).set_index("skill_key")
    index = pd.read_csv(d / "embeddings" / "skill_index.csv", keep_default_na=False)
    vectors = np.load(d / "embeddings" / "vectors.npy")
    keys = list(index["skill_key"])
    pairs = defaultdict(set)  # (a, b) sorted -> signals

    groups = defaultdict(list)
    for k in keys:
        if norm(k):
            groups[norm(k)].append(k)
    for g in groups.values():
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                sig = {"rule"} | ({"plural"} if norm(g[i], False) != norm(g[j], False) else set())
                pairs[tuple(sorted((g[i], g[j])))] |= sig
    for words, name in ((LEVEL, "level"), (VENDOR, "vendor")):  # strip ONE leading word on one side only:
        for k in keys:                                           # adobe photoshop = photoshop, never adobe x = google x
            m = re.match(rf"^(?:{words})\s+(.+)$", k)
            for other in groups.get(norm(m.group(1)), []) if m else []:
                if other != k:
                    pairs[tuple(sorted((k, other)))].add(name)

    top = np.zeros((len(keys), K), dtype=int)
    for s in range(0, len(keys), 2000):  # chunked: the full 11k x 11k matrix would be 0.5 GB
        sim = vectors[s:s + 2000] @ vectors.T
        for r in range(sim.shape[0]):
            sim[r, s + r] = -1
        top[s:s + 2000] = np.argsort(-sim, axis=1)[:, :K]
    for i in range(len(keys)):
        for j in top[i]:
            if i < j and i in top[j] and float(vectors[i] @ vectors[j]) >= COS_MIN:
                pairs[(keys[i], keys[j]) if keys[i] < keys[j] else (keys[j], keys[i])].add("embed")

    links = pd.DataFrame(db.connect().execute(
        "select skill_key, ref_label, score, match from skill_links where ref_label is not null and verdict <> 'new_candidate'"
    ).fetchall(), columns=["skill_key", "ref_label", "score", "match"])
    links = links[(links["score"].isna()) | (links["score"] >= STRONG_REF)]
    ref = links.set_index("skill_key")["ref_label"].str.lower().to_dict()
    by_ref = defaultdict(list)
    for k in keys:
        if k in ref:
            by_ref[ref[k]].append(k)
    for g in by_ref.values():
        if 2 <= len(g) <= 6:  # bigger groups are broad concepts (many narrower skills), not synonyms
            for i in range(len(g)):
                for j in range(i + 1, len(g)):
                    pairs[tuple(sorted((g[i], g[j])))].add("ref")
    def tier(sig):  # checked by hand on samples: embed / ref matches are often broad vs narrow, not synonyms
        if "rule" in sig:
            return "high"
        # a level / vendor word alone matched wrong pairs (sap erp ~ erp, cloud ~ google cloud); with a meaning or
        # reference match it was mostly right (outlook ~ microsoft outlook, illustrator ~ adobe illustrator)
        return "medium" if sig & {"level", "vendor"} and sig & {"embed", "ref"} else "low"

    mentions = lambda k: int(skills.loc[k, "mention_count"]) if k in skills.index else 0
    def target(a, b):  # alias -> name to keep: without a level word, else equal to its reference label, else more mentioned
        for x, y in ((a, b), (b, a)):
            if re.match(rf"^(?:{LEVEL})\s+", x) and not re.match(rf"^(?:{LEVEL})\s+", y):
                return x, y
        if ref.get(a) == a and ref.get(b) != b:
            return b, a
        if ref.get(b) == b and ref.get(a) != a:
            return a, b
        return (a, b) if (mentions(a), a) < (mentions(b), b) else (b, a)

    out = []
    for (a, b), sig in pairs.items():
        alias, keep = target(a, b)
        out.append({"tier": tier(sig), "alias": alias, "keep": keep, "alias_mentions": mentions(alias),
                    "keep_mentions": mentions(keep), "signals": ";".join(sorted(sig)),
                    "cos": round(float(vectors[keys.index(a)] @ vectors[keys.index(b)]), 3),
                    "ref_alias": ref.get(alias, ""), "ref_keep": ref.get(keep, ""), "accept": ""})
    res = pd.DataFrame(out)
    # high pairs inside one spelling group all point at the group's most-mentioned key (no chains, no cycles)
    high = res["tier"] == "high"
    groups = defaultdict(set)
    for r in res[high].itertuples():
        groups[norm(r.alias)] |= {r.alias, r.keep}
    best = {k: max(g, key=lambda m: (ref.get(m) == m, mentions(m), m)) for g in groups.values() for k in g}
    res.loc[high, "keep"] = res.loc[high, "alias"].map(best)
    res = res[res["alias"] != res["keep"]].drop_duplicates(["alias", "keep"])
    res["keep_mentions"] = res["keep"].map(mentions)
    res = res.sort_values(["tier", "keep_mentions"], key=lambda c: c.map({"high": 0, "medium": 1, "low": 2}) if c.name == "tier" else -c)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(args.out, index=False)
    print(res["tier"].value_counts().reindex(["high", "medium", "low"]).to_string())
    print("-> " + args.out)


if __name__ == "__main__":
    main()
