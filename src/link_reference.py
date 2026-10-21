"""Link extracted skills to ESCO v1.2 + O*NET 31.0 and give each one a verdict (rule E, LABELING_RULES.md).

    py src/link_reference.py                       # all statements_*.csv + gold, writes skill_links.csv
    py src/link_reference.py --write-gold-v2       # also writes data/gold/gold_labels_v2.csv

Reference lists (from src/download_reference.py):
  trait  = O*NET Work Styles + ESCO's transversal "attitudes and values" items (labels and alt labels)
  skill  = every other ESCO skill/knowledge item (labels and alt labels), O*NET Software Skills
           (workplace examples + categories), O*NET Knowledge, Essential Skills, Transferable Skills
Matching, per unique skill string:
  1. exact   - normalised names are equal (same normaliser as evaluate.py); a trait wins a tie
  2. meaning - otherwise the closest reference name by BAAI/bge-small-en-v1.5 cosine similarity,
               accepted when >= --threshold, or >= --trait-threshold when the closest entry is a trait
               (a trait removes the item, so it needs a stricter bar: at 0.85-0.88 "change control" ->
               "adapt to change" and "code compliance" -> "follow ethical code of conduct" were wrong)
Verdict: known_skill / trait (the matched entry's kind), or new_candidate when nothing matches.
new_candidate items are kept, never rejected: they go to a human (rule E).

Output: data/processed/skill_links.csv - one row per unique skill (lowercased): verdict, source, ref_label,
        ref_id, score, match, n_statements
"""
import argparse
from pathlib import Path

import pandas as pd

from evaluate import norm, split

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "data" / "reference"
PROCESSED = ROOT / "data" / "processed"
GOLD = ROOT / "data" / "gold" / "gold_labels.csv"
LINKS = PROCESSED / "skill_links.csv"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def reference():
    """One row per reference name: name, kind (skill / trait), source, ref_label, ref_id."""
    esco = pd.read_csv(REF / "esco_skills.csv").fillna("")
    att = pd.read_csv(REF / "esco_attitudes.csv")
    trait_uris = set(esco.loc[esco.uri.isin(att.uri) & (esco.reuse_level == "transversal"), "uri"])
    rows = []
    for r in esco.itertuples():
        kind = "trait" if r.uri in trait_uris else "skill"
        source = "ESCO attitude" if kind == "trait" else f"ESCO {r.skill_type or 'skill'}"
        for name in [r.label] + [a for a in r.alt_labels.split("|") if a]:
            rows.append((name, kind, source, r.label, r.uri))
    onet = lambda f: pd.read_csv(REF / "onet" / f"{f}.txt", sep="\t", dtype=str)
    for r in onet("Work Styles")[["Element ID", "Element Name"]].drop_duplicates().itertuples(index=False):
        rows.append((r[1], "trait", "O*NET Work Style", r[1], r[0]))
    sw = onet("Software Skills")
    for r in sw[["Element ID", "Workplace Example"]].drop_duplicates().itertuples(index=False):
        rows.append((r[1], "skill", "O*NET software", r[1], r[0]))
    for r in sw[["Element ID", "Element Name"]].drop_duplicates().itertuples(index=False):
        rows.append((r[1], "skill", "O*NET software category", r[1], r[0]))
    for f in ["Knowledge", "Essential Skills", "Transferable Skills"]:
        for r in onet(f)[["Element ID", "Element Name"]].drop_duplicates().itertuples(index=False):
            rows.append((r[1], "skill", f"O*NET {f}", r[1], r[0]))
    ref = pd.DataFrame(rows, columns=["name", "kind", "source", "ref_label", "ref_id"])
    ref = ref[ref.name.str.strip() != ""]
    ref["key"] = ref.name.map(norm)
    # traits first, so an exact tie between a trait and a skill entry is read as a trait (rule E)
    return ref.sort_values("kind", ascending=False, kind="stable").drop_duplicates(["key", "kind"])


def link(skills, ref, threshold, trait_threshold):
    exact = {r.key: r for r in ref.drop_duplicates("key").itertuples()}  # keys are word tuples
    out, todo = [], []
    for s in skills:
        e = exact.get(norm(s))
        if e is not None:
            out.append((s, e.kind, e.source, e.ref_label, e.ref_id, 1.0, "exact"))
        else:
            todo.append(s)
    if todo:
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer(EMBED_MODEL)
        names = ref.name.tolist()
        emb_ref = model.encode(names, batch_size=512, normalize_embeddings=True, convert_to_tensor=True,
                               show_progress_bar=True)
        emb = model.encode(todo, batch_size=512, normalize_embeddings=True, convert_to_tensor=True)
        for s, hit in zip(todo, util.semantic_search(emb, emb_ref, top_k=1)):
            e = ref.iloc[hit[0]["corpus_id"]]
            score = round(float(hit[0]["score"]), 3)
            kind = e.kind if score >= (trait_threshold if e.kind == "trait" else threshold) else "new_candidate"
            out.append((s, kind, e.source, e.ref_label, e.ref_id, score, "meaning"))
    df = pd.DataFrame(out, columns=["skill", "verdict", "source", "ref_label", "ref_id", "score", "match"])
    df["verdict"] = df.verdict.replace({"skill": "known_skill"})
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--threshold", type=float, default=0.85, help="min cosine similarity for a meaning match")
    ap.add_argument("--trait-threshold", type=float, default=0.88, help="min similarity for a trait match")
    ap.add_argument("--write-gold-v2", action="store_true", help="gold v1 minus items linked as traits")
    args = ap.parse_args()

    runs = {p.stem.removeprefix("statements_"): pd.read_csv(p) for p in sorted(PROCESSED.glob("statements_*.csv"))}
    gold = pd.read_csv(GOLD, encoding="utf-8-sig")
    gold_items = [x for s in gold.gold_skills for x in split(s)]
    counts = pd.Series([s.strip().lower() for d in runs.values() for s in d.skill.dropna()]
                       + [x.strip().lower() for x in gold_items]).value_counts()

    links = link(counts.index.tolist(), reference(), args.threshold, args.trait_threshold)
    links["n_statements"] = links.skill.map(counts)
    links.sort_values("n_statements", ascending=False).to_csv(LINKS, index=False)
    verdict = links.set_index("skill").verdict
    print(f"{len(links)} unique skills -> {LINKS.relative_to(ROOT)} "
          f"(threshold {args.threshold}, traits {args.trait_threshold})")

    def shares(items, label):
        v = pd.Series([verdict[x.strip().lower()] for x in items]).value_counts(normalize=True)
        print(f"  {label:45} " + " | ".join(f"{k} {v.get(k, 0):.0%}" for k in ["known_skill", "trait", "new_candidate"]))

    shares(gold_items, f"gold v1 ({len(gold_items)} items)")
    for name, d in runs.items():
        shares(d.skill.dropna(), f"{name} ({len(d)})")

    if args.write_gold_v2:
        v2 = gold.copy()
        keep = lambda s: [x for x in split(s) if verdict[x.strip().lower()] != "trait"]
        drop = lambda s: [x for x in split(s) if verdict[x.strip().lower()] == "trait"]
        v2["removed_traits"] = v2.gold_skills.map(lambda s: "; ".join(drop(s)))
        v2["gold_skills"] = v2.gold_skills.map(lambda s: "; ".join(keep(s)))
        path = ROOT / "data" / "gold" / "gold_labels_v2.csv"
        v2.to_csv(path, index=False, encoding="utf-8-sig")
        n = sum(len(drop(s)) for s in gold.gold_skills)
        print(f"gold v2: removed {n} trait items -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
