"""Score extracted skills against the hand-labelled gold set (precision / recall / F1).

    py src/evaluate.py --model qwen/qwen3.8-27b

Input:  data/gold/gold_labels.csv (gold_skills, ";"-separated),
        data/processed/statements_<model>.csv, data/processed/extraction_postings_<model>.csv
Output: reports/sprint2_extraction_quality_<model>.md

Matching (one-to-one, per posting; maximum matching, so the score does not depend on list order),
after normalising both names (lowercase, filler words removed,
simple plural -> singular):
- strict:  normalised names are equal, also with spaces removed ("multi-tasking" = "multitasking");
           "analyses" is read as "analysis"
- lenient: equal, OR all words of one name appear in the other
           ("prototyping" ~ "high-fidelity prototyping", "Visio" ~ "Microsoft Visio")
The gold set has no evidence offsets, so matching is by name only.
"""
import argparse
import re
from pathlib import Path

import pandas as pd

from extract_skills import slug

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold" / "gold_labels.csv"
PROCESSED = ROOT / "data" / "processed"
USAGE = ROOT / "reports" / "token_usage.csv"

FILLER = {"skill", "skills", "strong", "excellent", "proficiency", "proficient", "knowledge", "experience",
          "ability", "basic", "of", "in", "with", "the", "a", "an", "and", "&", "using", "use"}


def split(s):
    return [x.strip() for x in str(s).split(";") if x.strip()] if isinstance(s, str) else []


def norm(name):
    words = re.sub(r"[^\w+#./ ]", " ", name.lower().replace("&", " and ")).split()
    words = [w[:-4] + "ysis" if w.endswith("yses") else w for w in words]  # analyses -> analysis
    words = [w[:-3] + "y" if len(w) > 4 and w.endswith("ies") else w for w in words]  # strategies -> strategy
    words = [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "sis")) else w for w in words]
    return tuple(w for w in words if w not in FILLER) or tuple(words)


def pairs_ok(a, b, lenient):
    if a == b or "".join(a) == "".join(b):  # "multi tasking" == "multitasking"
        return True
    return lenient and (set(a) <= set(b) or set(b) <= set(a))


def match(gold, pred, lenient):
    """One-to-one matching with the most possible pairs (maximum bipartite matching, augmenting paths).
    Unlike a greedy pass, the number of matches does not depend on the order of the lists."""
    g, p = [norm(x) for x in gold], [norm(x) for x in pred]
    edges = [[j for j, b in enumerate(p) if pairs_ok(a, b, lenient)] for a in g]
    owner = {}  # predicted index -> gold index

    def augment(i, seen):
        for j in edges[i]:
            if j not in seen:
                seen.add(j)
                if j not in owner or augment(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    for i in range(len(g)):
        augment(i, set())
    used_g, used_p = set(owner.values()), set(owner)
    return len(owner), [gold[i] for i in range(len(g)) if i not in used_g], [pred[j] for j in range(len(p)) if j not in used_p]


def prf(tp, n_pred, n_gold):
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="model id used in extract_skills.py")
    ap.add_argument("--tag", default="", help="same --tag as extract_skills.py")
    ap.add_argument("--split", choices=["all", "dev", "test"], default="all", help="gold half to score (gold_split.csv)")
    ap.add_argument("--gold", type=Path, default=GOLD, help="gold file, e.g. data/gold/gold_labels_v2.csv")
    ap.add_argument("--links", type=Path, default=None,
                    help="skill_links.csv from link_reference.py: drop predicted skills linked as traits (rule E)")
    args = ap.parse_args()
    m = f"{slug(args.model)}_{args.tag}" if args.tag else slug(args.model)
    PRED, DONE = PROCESSED / f"statements_{m}.csv", PROCESSED / f"extraction_postings_{m}.csv"
    name = m if args.split == "all" else f"{m}_{args.split}"
    if args.gold.resolve() != GOLD.resolve():
        name += "_" + args.gold.stem.removeprefix("gold_labels_")
    if args.links:
        name += "_notraits"
    REPORT = ROOT / "reports" / f"sprint2_extraction_quality_{name}.md"
    gold = pd.read_csv(args.gold)
    gold["sector_eval"] = gold.sector_fixed.fillna(gold.sector)
    if args.split != "all":
        halves = pd.read_csv(ROOT / "data" / "gold" / "gold_split.csv")
        gold = gold[gold.posting_id.isin(halves.loc[halves.split == args.split, "posting_id"])]
    pred = pd.read_csv(PRED)
    if args.links:
        links = pd.read_csv(args.links)
        traits = set(links.loc[links.verdict == "trait", "skill"])
        pred = pred[~pred.skill.str.strip().str.lower().isin(traits)]
    by_post = pred.groupby("posting_id").skill.apply(list).to_dict()
    done = pd.read_csv(DONE)
    if "status" in done:  # newer runs also list failed postings
        done = done[done.status == "done"]
    n_gold = len(gold)
    missing = sorted(set(gold.posting_id) - set(done.posting_id))
    gold = gold[gold.posting_id.isin(done.posting_id)]  # only postings the extractor ran on
    coverage = f"{len(gold)} of {n_gold} gold postings scored" + (
        f"; NOT scored (failed or not run): {', '.join(missing)}" if missing else "")
    print(coverage)

    rows, misses, extras = [], [], []
    for r in gold.itertuples():
        g, p = split(r.gold_skills), by_post.get(r.posting_id, [])
        tp_s, _, _ = match(g, p, lenient=False)
        tp_l, fn, fp = match(g, p, lenient=True)
        rows.append({"n": r.n, "sector": r.sector_eval, "gold": len(g), "pred": len(p), "tp_strict": tp_s, "tp_lenient": tp_l})
        misses += [(r.n, x) for x in fn]
        extras += [(r.n, x) for x in fp]
    df = pd.DataFrame(rows)
    pd.DataFrame([("missed", n, x) for n, x in misses] + [("extra", n, x) for n, x in extras],
                 columns=["error", "n", "skill"]).to_csv(ROOT / "reports" / f"errors_{name}.csv", index=False)

    def line(d, label):
        ps, rs, fs = prf(d.tp_strict.sum(), d.pred.sum(), d.gold.sum())
        pl, rl, fl = prf(d.tp_lenient.sum(), d.pred.sum(), d.gold.sum())
        return f"| {label} | {len(d)} | {d.gold.sum()} | {d.pred.sum()} | {ps:.2f} | {rs:.2f} | {fs:.2f} | {pl:.2f} | {rl:.2f} | {fl:.2f} |"

    head = "| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient | F1 lenient |\n|---|---|---|---|---|---|---|---|---|---|"
    model = pred.model.iloc[0] if len(pred) else "?"
    ev = pred.evidence_in_text.mean() if len(pred) else 0
    usage = pd.read_csv(USAGE) if USAGE.exists() else pd.DataFrame()
    usage = usage[usage.model == model] if len(usage) else usage
    zero = df[df.gold == 0]

    out = [f"# Sprint 2 — Extraction quality report (Section B, skills)", "",
           f"- **Extractor:** `{model}` via {pred.provider.iloc[0] if len(pred) else '?'}, prompt `{pred.prompt_version.iloc[0] if len(pred) else '?'}`",
           f"- **Gold set:** {len(df)} postings, {df.gold.sum()} gold skills (`{args.gold.resolve().relative_to(ROOT)}`)."
           + (" Predicted skills linked as traits (ESCO/O*NET, rule E) are dropped." if args.links else ""),
           "  Labels are LLM-suggested (Claude/ChatGPT) and human-corrected."
           + (" **The extractor is a Claude model, so it is not independent of the suggestions** "
              "(see `src/bias_check.py`)." if "claude" in model.lower() else
              " The extractor is not one of the suggesting models."),
           f"- **Coverage:** {coverage}.",
           f"- **Evidence check:** {ev:.0%} of predicted evidence phrases occur verbatim in the posting.",
           "", "## Overall (micro-averaged)", "", head, line(df, "**All**"), "",
           "## By sector", "", head] + [line(d, s) for s, d in df.groupby("sector")] + [
           "", f"## Zero-skill postings", "",
           f"{len(zero)} gold postings have no skills; the extractor predicted {int(zero.pred.sum())} skills for them.",
           "", "## Matching rules", "", __doc__.split("Matching", 1)[1].strip(), "",
           "## LLM token usage", "",
           f"Total for the {len(done)} scored postings (each paid once, cached after): "
           f"**{int(done.tokens_in.sum()):,} input** and **{int(done.tokens_out.sum()):,} output** tokens "
           f"(output includes thinking tokens). Per-run log (`reports/token_usage.csv`):", "",
           ("| " + " | ".join(usage.columns) + " |\n|" + "---|" * len(usage.columns) + "\n"
            + "\n".join("| " + " | ".join(map(str, r)) + " |" for r in usage.itertuples(index=False))
            if len(usage) else "No API calls logged."), "",
           f"## Error samples (lenient)", "", "**Missed gold skills (false negatives), first 25:**", ""]
    out += [f"- #{n}: {x}" for n, x in misses[:25]]
    out += ["", "**Extra predicted skills (false positives), first 25:**", ""]
    out += [f"- #{n}: {x}" for n, x in extras[:25]]
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out[:12]))
    print(f"\nReport -> {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
