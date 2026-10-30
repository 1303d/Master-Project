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

Optional (added 2026-10-30; the strict and lenient numbers above are unchanged by them):
- --aliases skill_aliases_manual.csv: an extra "strict+alias" score. Both gold and predicted names are first
  mapped skill_key -> canonical_key (lowercased, exact key), then matched strictly.
- --same-postings-as RUN [RUN ...]: score only postings that every listed run also finished, so two
  versions are compared on the same postings (a failed posting would otherwise drop out of one run only).
- --baseline RUN --bootstrap N: paired bootstrap over postings; 95% interval of (this run - baseline) F1.
- --sector-source split: sectors from gold_split.csv sector_eval instead of the gold file.
"""
import argparse
import random
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


def load_aliases(path):
    """skill_key -> canonical_key (both lowercased). Chains are followed; a cycle stops at the first repeat."""
    a = pd.read_csv(path, encoding="utf-8-sig")
    m = dict(zip(a.skill_key.str.strip().str.lower(), a.canonical_key.str.strip().str.lower()))

    def canon(name):
        k, seen = name.strip().lower(), set()
        while k in m and k not in seen:
            seen.add(k)
            k = m[k]
        return k
    return canon


def run_name(model, tag=""):
    return f"{slug(model)}_{tag}" if tag else slug(model)


def done_postings(run):
    """posting_ids a run finished (status done, incl. zero-skill postings)."""
    d = pd.read_csv(PROCESSED / f"extraction_postings_{run}.csv")
    return set(d.loc[d.status == "done", "posting_id"] if "status" in d else d.posting_id)


def score(gold, by_post, canon=None):
    """Per-posting counts, plus the lenient misses and extras."""
    rows, misses, extras = [], [], []
    for r in gold.itertuples():
        g, p = split(r.gold_skills), by_post.get(r.posting_id, [])
        tp_s, _, _ = match(g, p, lenient=False)
        tp_l, fn, fp = match(g, p, lenient=True)
        row = {"n": r.n, "posting_id": r.posting_id, "sector": r.sector_eval, "gold": len(g), "pred": len(p),
               "tp_strict": tp_s, "tp_lenient": tp_l}
        if canon:
            row["tp_alias"] = match([canon(x) for x in g], [canon(x) for x in p], lenient=False)[0]
        rows.append(row)
        misses += [(r.n, x) for x in fn]
        extras += [(r.n, x) for x in fp]
    return pd.DataFrame(rows), misses, extras


def f1_of(d, col):
    return prf(d[col].sum(), d.pred.sum(), d.gold.sum())[2]


def paired_bootstrap(cur, base, col, n, seed=0):
    """95% interval of F1(cur) - F1(base), resampling postings with replacement (same draw for both runs)."""
    cur, base = cur.set_index("posting_id"), base.set_index("posting_id").loc[cur.posting_id]
    ids, rnd, diffs = list(cur.index), random.Random(seed), []
    for _ in range(n):
        s = [rnd.choice(ids) for _ in ids]
        diffs.append(f1_of(cur.loc[s], col) - f1_of(base.loc[s], col))
    diffs.sort()
    return f1_of(cur, col) - f1_of(base, col), diffs[int(0.025 * n)], diffs[int(0.975 * n) - 1]


def prf(tp, n_pred, n_gold):
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="model id used in extract_skills.py")
    ap.add_argument("--tag", default="", help="same --tag as extract_skills.py")
    ap.add_argument("--split", choices=["all", "dev", "test"], default="dev",
                    help="gold half to score (gold_split.csv). Default dev; test is for the final evaluation only")
    ap.add_argument("--gold", type=Path, default=GOLD, help="gold file, e.g. data/gold/gold_labels_v2.csv")
    ap.add_argument("--links", type=Path, default=None,
                    help="skill_links.csv from link_reference.py: drop predicted skills linked as traits (rule E)")
    ap.add_argument("--aliases", type=Path, default=None, help="alias CSV (skill_key, canonical_key): adds strict+alias")
    ap.add_argument("--same-postings-as", nargs="+", default=[], metavar="RUN",
                    help="other runs (model slug[_tag], e.g. qwen_qwen3.8-27b_v3): score only postings all finished")
    ap.add_argument("--baseline", default=None, metavar="RUN", help="run to compare with (paired bootstrap)")
    ap.add_argument("--bootstrap", type=int, default=2000, help="bootstrap draws for --baseline (default 2000)")
    ap.add_argument("--sector-source", choices=["gold", "split"], default="gold",
                    help="gold: sector_fixed, else sector, from the gold file (as before); split: gold_split.csv sector_eval")
    args = ap.parse_args()
    m = run_name(args.model, args.tag)
    PRED, DONE = PROCESSED / f"statements_{m}.csv", PROCESSED / f"extraction_postings_{m}.csv"
    name = m if args.split == "all" else f"{m}_{args.split}"
    if args.gold.resolve() != GOLD.resolve():
        name += "_" + args.gold.stem.removeprefix("gold_labels_")
    if args.links:
        name += "_notraits"
    if args.aliases:
        name += "_alias"
    if args.same_postings_as or args.baseline:
        name += "_paired"
    REPORT = ROOT / "reports" / f"sprint2_extraction_quality_{name}.md"
    gold = pd.read_csv(args.gold, encoding="utf-8-sig")
    halves = pd.read_csv(ROOT / "data" / "gold" / "gold_split.csv", encoding="utf-8-sig")
    if args.sector_source == "split":
        gold["sector_eval"] = gold.posting_id.map(halves.set_index("posting_id").sector_eval)
    else:  # a gold file without sector_fixed (e.g. a dev-only export) falls back to sector
        gold["sector_eval"] = gold.sector_fixed.fillna(gold.sector) if "sector_fixed" in gold else gold.sector
    if args.split != "all":
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
    keep = set(done.posting_id)
    others = list(dict.fromkeys(args.same_postings_as + ([args.baseline] if args.baseline else [])))
    for other in others:  # compare runs on the same postings only
        keep &= done_postings(other)
    not_shared = sorted(set(gold.posting_id) & set(done.posting_id) - keep)
    gold = gold[gold.posting_id.isin(keep)]  # only postings the extractor (and every compared run) finished
    coverage = f"{len(gold)} of {n_gold} gold postings scored" + (
        f"; NOT scored (failed or not run): {', '.join(missing)}" if missing else "") + (
        f"; NOT scored (not finished by {', '.join(others)}): {', '.join(not_shared)}" if not_shared else "")
    print(coverage)

    canon = load_aliases(args.aliases) if args.aliases else None
    df, misses, extras = score(gold, by_post, canon)
    zero_pred = df[(df.pred == 0) & (df.gold > 0)]
    pd.DataFrame([("missed", n, x) for n, x in misses] + [("extra", n, x) for n, x in extras],
                 columns=["error", "n", "skill"]).to_csv(ROOT / "reports" / f"errors_{name}.csv", index=False)

    def line(d, label):
        ps, rs, fs = prf(d.tp_strict.sum(), d.pred.sum(), d.gold.sum())
        pl, rl, fl = prf(d.tp_lenient.sum(), d.pred.sum(), d.gold.sum())
        extra = f" {f1_of(d, 'tp_alias'):.2f} |" if canon else ""
        return (f"| {label} | {len(d)} | {d.gold.sum()} | {d.pred.sum()} | {ps:.2f} | {rs:.2f} | {fs:.2f} "
                f"| {pl:.2f} | {rl:.2f} | {fl:.2f} |" + extra)

    head = ("| Group | Postings | Gold skills | Predicted | P strict | R strict | F1 strict | P lenient | R lenient "
            "| F1 lenient |" + (" F1 strict+alias |" if canon else "") + "\n|" + "---|" * (11 if canon else 10))

    compare = []
    if args.baseline:
        bpred = pd.read_csv(PROCESSED / f"statements_{args.baseline}.csv")
        if args.links:
            bpred = bpred[~bpred.skill.str.strip().str.lower().isin(traits)]
        bdf, _, _ = score(gold, bpred.groupby("posting_id").skill.apply(list).to_dict(), canon)
        compare = ["", f"## Compared with `{args.baseline}` (same {len(df)} postings, paired bootstrap, "
                       f"{args.bootstrap} draws)", "", "| Metric | Baseline F1 | This run F1 | Difference | 95% interval |",
                   "|---|---|---|---|---|"]
        for col, label in [("tp_strict", "strict"), ("tp_lenient", "lenient")] + ([("tp_alias", "strict+alias")] if canon else []):
            diff, lo, hi = paired_bootstrap(df, bdf, col, args.bootstrap)
            compare.append(f"| {label} | {f1_of(bdf, col):.3f} | {f1_of(df, col):.3f} | {diff:+.3f} | [{lo:+.3f}, {hi:+.3f}] |")
        compare += ["", "An interval that contains 0 means the difference is not shown on these postings."]
        print("\n".join(compare))
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
           f"- **Postings with gold skills but no predictions:** {len(zero_pred)}"
           + (f" ({', '.join(f'#{n}' for n in zero_pred.n)}): check these are real empty answers, not parsing problems."
              if len(zero_pred) else "."),
           f"- **Sectors from:** {'gold_split.csv sector_eval' if args.sector_source == 'split' else 'gold file (sector_fixed, else sector)'}.",
           f"- **Evidence check:** {ev:.0%} of predicted evidence phrases occur verbatim in the posting.",
           "", "## Overall (micro-averaged)", "", head, line(df, "**All**"), "",
           "## By sector", "", head] + [line(d, s) for s, d in df.groupby("sector")] + compare + [
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
