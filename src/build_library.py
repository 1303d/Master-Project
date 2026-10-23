"""Build the cross-sector skill library and its weighted links to skill groups (Sprint 3, ER model).

    py src/build_library.py --mentions PREPARED_MENTIONS.csv --aliases ALIASES.csv --run RUN_DIR --out-dir OUT

The library is a label on a canonical skill (keyed by skill_key), not a second identity.
Library skill (rule v1, fixed before looking): seen in >= MIN_POSTINGS postings, in >= MIN_SECTORS of the 8 named
sectors, and no sector holds more than MAX_SECTOR_SHARE of its postings. Sector = the posting's first-listed
LinkedIn job function, grouped as in make_gold_sample.py. "Mixed" and unknown-sector postings (e.g. Greenhouse)
count in n_postings but not in n_sectors / top_share / entropy (n_unknown reports them).
  entropy = sector entropy over the 8 named sectors, divided by ln 8 (0 = one sector, 1 = perfectly even)
  status  = confirmed if n_postings >= CONFIRMED_POSTINGS, else candidate (an evidence level, not proof)
Groups (topics of RUN_DIR/assignments.csv) are flagged is_transversal when more than TRANSVERSAL_SHARE of their
mentions come from library skills. Flagged groups and a skill's own group are not link targets.
Link skill -> group, tested for every eligible pair (the FDR family, zero-overlap pairs included as p = 1).
Rule library-v2 counts TEMPLATES, not postings: unit = (Kaggle company_id, normalised job title), so one employer's
job posted in many cities counts once. A posting without a company is its own unit. Whole companies were tried and
rejected: staffing firms (TEKsystems, Dice) post many unrelated roles, which raised every baseline (2026-10-22).
In the 2026-10-22 sample: 1,931 postings -> 1,901 units (24 repeated templates, 54 postings).
  n_postings  = postings that have the skill and any skill of the group (shown, not tested)
  n_templates = units (company + title) with at least one such posting
  lift        = n_templates * N / (units with the skill * units with the group), N = all units
  p / q       = hypergeometric p-value of the unit overlap / Benjamini-Hochberg q over the whole family
  strength    = strong if n_templates >= MIN_LINK_TEMPLATES and lift >= MIN_LIFT and q < MAX_Q, else weak
--types (skill_types.py output) adds skill_type / reuse_level to library.csv.
Output: OUT/library.csv, OUT/library_links.csv (top LINKS_PER_SKILL per skill: strong first, then by p),
OUT/groups.csv (group, size, is_transversal). Checks the outputs before writing. Refuses to overwrite.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import hypergeom

from make_gold_sample import RAW, SECTOR_OF_FUNCTION

RULE_VERSION = "library-v2"
N_NAMED_SECTORS = 8
MIN_POSTINGS = 5
MIN_SECTORS = 4
MAX_SECTOR_SHARE = 0.5
CONFIRMED_POSTINGS = 10
MIN_LINK_TEMPLATES = 5
MIN_LIFT = 1.5
MAX_Q = 0.05
TRANSVERSAL_SHARE = 0.5
LINKS_PER_SKILL = 5
OUTPUTS = ["library.csv", "library_links.csv", "groups.csv"]


def posting_sectors():
    funcs = pd.read_csv(RAW / "jobs" / "job_skills.csv").merge(pd.read_csv(RAW / "mappings" / "skills.csv"),
                                                              on="skill_abr")
    first = funcs.drop_duplicates("job_id")
    return pd.Series(first["skill_name"].map(SECTOR_OF_FUNCTION).fillna("Mixed").to_numpy(),
                     index="li_" + first["job_id"].astype(str))


def posting_units():
    """posting_id -> 'c<company_id>|<normalised title>' (one job template) for Kaggle postings with a company."""
    raw = pd.read_csv(RAW / "postings.csv", usecols=["job_id", "company_id", "title"]).dropna(subset=["company_id"])
    title = raw["title"].fillna("").str.lower().str.replace(r"[^a-z ]", " ", regex=True).str.split().str.join(" ")
    unit = "c" + raw["company_id"].astype("int64").astype(str) + "|" + title
    return pd.Series(unit.to_numpy(), index="li_" + raw["job_id"].astype(str))


def bh(p):
    """Benjamini-Hochberg adjusted q-values."""
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)
    q = p[order] * len(p) / np.arange(1, len(p) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(len(p))
    out[order] = np.minimum(q, 1.0)
    return out


def entropy(sectors):
    p = sectors.value_counts(normalize=True).to_numpy()
    return float(-(p * np.log(p)).sum() / np.log(N_NAMED_SECTORS))


def check(lib, links, groups, skills, n_family):
    assert lib.index.is_unique and lib.index.isin(skills).all(), "library keys must be unique canonical skills"
    assert lib["status"].isin(["confirmed", "candidate"]).all() and lib["entropy"].between(0, 1).all()
    strong = links[links["strength"] == "strong"]
    assert ((strong["n_templates"] >= MIN_LINK_TEMPLATES) & (strong["lift"] >= MIN_LIFT)
            & (strong["q"] < MAX_Q)).all(), "a strong link breaks the rule"
    assert not links["group"].isin(groups.index[groups["is_transversal"]]).any(), "link to a transversal group"
    assert links[["skill_key", "group"]].drop_duplicates().shape[0] == len(links)
    assert n_family >= len(links)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mentions", required=True, help="prepared_mentions.csv (posting_id, skill_key)")
    ap.add_argument("--aliases", required=True, help="aliases.csv from normalize_aliases.py")
    ap.add_argument("--run", required=True, help="cluster run folder with assignments.csv")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--types", help="skill_types.csv from skill_types.py (optional)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    existing = [f for f in OUTPUTS if (out_dir / f).exists()]
    if existing:
        raise SystemExit(f"refusing to overwrite {existing} in {out_dir}")

    alias = pd.read_csv(args.aliases, keep_default_na=False).set_index("skill_key")["canonical_key"]
    m = pd.read_csv(args.mentions, keep_default_na=False, usecols=["posting_id", "skill_key"])
    m["skill_key"] = m["skill_key"].map(alias)
    m = m.drop_duplicates()
    m["sector"] = m["posting_id"].map(posting_sectors()).fillna("Unknown")
    assign = pd.read_csv(Path(args.run) / "assignments.csv", keep_default_na=False).set_index("skill_key")["cluster"]
    m["group"] = m["skill_key"].map(assign)
    m["unit"] = m["posting_id"].map(posting_units()).fillna(m["posting_id"])

    # library rule
    named = m[~m["sector"].isin(["Mixed", "Unknown"])]
    spread = named.groupby("skill_key")["sector"].agg(n_sectors="nunique",
                                                     top_share=lambda s: s.value_counts(normalize=True).iloc[0],
                                                     entropy=entropy)
    total = m.groupby("skill_key")["posting_id"].nunique().rename("n_postings")
    unknown = m[m["sector"] == "Unknown"].groupby("skill_key")["posting_id"].nunique().rename("n_unknown")
    templates = m.groupby("skill_key")["unit"].nunique().rename("n_templates")
    lib = spread.join(total, how="inner").join(templates).join(unknown).fillna({"n_unknown": 0})
    lib = lib[(lib["n_postings"] >= MIN_POSTINGS) & (lib["n_sectors"] >= MIN_SECTORS)
              & (lib["top_share"] <= MAX_SECTOR_SHARE)].copy()
    lib["status"] = np.where(lib["n_postings"] >= CONFIRMED_POSTINGS, "confirmed", "candidate")
    lib["own_group"] = lib.index.map(assign)
    lib["rule_version"] = RULE_VERSION
    lib = lib.sort_values("n_postings", ascending=False).round({"top_share": 4, "entropy": 4})
    lib["n_unknown"] = lib["n_unknown"].astype(int)
    if args.types:
        types = pd.read_csv(args.types, keep_default_na=False).set_index("skill_key")[["skill_type", "reuse_level"]]
        lib = lib.join(types)

    # groups and the transversal flag (kept, not deleted; only excluded as link targets)
    N = m["unit"].nunique()
    unit_of = m.drop_duplicates("posting_id").set_index("posting_id")["unit"]
    grouped = m[m["group"] >= 0]
    lib_share = grouped["skill_key"].isin(lib.index).groupby(grouped["group"]).mean()
    groups = pd.DataFrame({"size": assign[assign >= 0].value_counts(), "library_mention_share": lib_share.round(4)})
    groups["is_transversal"] = groups["library_mention_share"] > TRANSVERSAL_SHARE
    group_posts = grouped.groupby("group")["posting_id"].apply(set)
    group_units = grouped.groupby("group")["unit"].apply(set)
    targets = [g for g in group_posts.index if not groups.loc[g, "is_transversal"]]
    skill_posts = m.groupby("skill_key")["posting_id"].apply(set)
    skill_units = m.groupby("skill_key")["unit"].apply(set)

    # every eligible (skill, group) pair = the FDR family
    rows = []
    for skill, r in lib.iterrows():
        sp, su = skill_posts[skill], skill_units[skill]
        for g in targets:
            if g == r["own_group"]:
                continue
            both_posts = sp & group_posts[g]
            both, gu = len({unit_of[x] for x in both_posts}), group_units[g]
            p = hypergeom.sf(both - 1, N, len(gu), len(su)) if both else 1.0
            rows.append((skill, int(g), len(both_posts), both, both * N / (len(su) * len(gu)), p))
    fam = pd.DataFrame(rows, columns=["skill_key", "group", "n_postings", "n_templates", "lift", "p"])
    fam["q"] = bh(fam["p"])
    fam["strong"] = (fam["n_templates"] >= MIN_LINK_TEMPLATES) & (fam["lift"] >= MIN_LIFT) & (fam["q"] < MAX_Q)
    links = (fam[fam["n_postings"] > 0].sort_values(["skill_key", "strong", "p"], ascending=[True, False, True])
             .groupby("skill_key").head(LINKS_PER_SKILL).copy())
    links["strength"] = np.where(links["strong"], "strong", "weak")
    links = links.drop(columns="strong")
    check(lib, links, groups, set(assign.index), len(fam))  # before rounding: q = 0.04996 would print as 0.05
    links = links.round({"lift": 3})
    links["p"], links["q"] = links["p"].map("{:.3g}".format).astype(float), links["q"].map("{:.3g}".format).astype(float)

    out_dir.mkdir(parents=True, exist_ok=True)
    lib.rename_axis("skill_key").reset_index().to_csv(out_dir / "library.csv", index=False)
    links.to_csv(out_dir / "library_links.csv", index=False)
    groups.rename_axis("group").reset_index().to_csv(out_dir / "groups.csv", index=False)
    print(f"{len(lib)} library skills ({(lib['status'] == 'confirmed').sum()} confirmed, "
          f"{(lib['own_group'] == -1).sum()} were noise); {groups['is_transversal'].sum()} transversal groups flagged; "
          f"FDR family {len(fam)} pairs, {fam['strong'].sum()} strong in family; "
          f"{len(links)} links kept ({(links['strength'] == 'strong').sum()} strong) from {N} templates "
          f"({m['posting_id'].nunique()} postings)")


if __name__ == "__main__":
    main()
