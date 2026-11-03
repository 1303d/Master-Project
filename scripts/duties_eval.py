"""Score the two-pass setup (v8 + duties pass) against v8, per model, and apply the pre-registered rule.

    py scripts/duties_eval.py

Needs finished runs <model>_v8 and <model>_v8_duties (all 50 dev postings). Merges them with merge_runs.py,
scores with src/evaluate.py functions (v3-proposed gold, dev, gold_split sectors), and writes
reports/v8_dev_evaluation_2026-10-30/duties_*.csv plus duties_result.md.
Rule (duties_decision_rule.md): adopt if F1 strict >= v8's and P strict >= v8's - 0.02.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import merge_runs  # noqa: E402
from evaluate import f1_of, load_aliases, match, norm, paired_bootstrap, prf, score, split  # noqa: E402

OUT = ROOT / "reports" / "v8_dev_evaluation_2026-10-30"
P = ROOT / "data" / "processed"
MODELS = {"qwen": "qwen_qwen3.8-27b", "haiku": "claude-haiku-5-5"}


def collapse(items):
    """Near-duplicates = same words after cutting each to 5 letters ("cycle counts" ~ "cycle counting").
    Returns (items with only the first of each group, [(kept, dropped), ...])."""
    kept, first, pairs = [], {}, []
    for x in items:
        k = frozenset(w[:5] for w in norm(x))
        if k in first:
            pairs.append((first[k], x))
        else:
            first[k] = x
            kept.append(x)
    return kept, pairs


def main():
    gold = pd.read_csv(ROOT / "data/gold/gold_labels_v3_dev_proposed.csv", encoding="utf-8-sig")
    halves = pd.read_csv(ROOT / "data/gold/gold_split.csv", encoding="utf-8-sig")
    gold = gold[gold.posting_id.isin(halves.loc[halves.split == "dev", "posting_id"])].copy()
    gold["sector_eval"] = gold.posting_id.map(halves.set_index("posting_id").sector_eval)
    long = pd.read_excel(ROOT / "data/gold/audit/gold_audit_dev_v3_proposed.xlsx", "Recommended Gold (long)")
    original = {(r.n, str(r.skill).strip().lower()) for r in long.itertuples()
                if r.under_review == "No" and not r.status.startswith("NEW")}
    canon = load_aliases(ROOT / "config/skill_aliases_manual.csv")
    near = []
    md, scores, diffs, counts, top = ["# Two-pass (v8 + duties) vs v8, dev, v3-proposed gold", ""], [], [], [], []
    for name, m in MODELS.items():
        base, duty, two = f"{m}_v8", f"{m}_v8_duties", f"{m}_v8+duties"
        for r in (base, duty):
            d = pd.read_csv(P / f"extraction_postings_{r}.csv")
            assert (d.status == "done").sum() == 50, f"{r} has not finished all 50 postings: do not score"
        merge_runs.main(base, duty, two)
        pv8, p2 = (pd.read_csv(P / f"statements_{r}.csv") for r in (base, two))
        b8, b2 = (x.groupby("posting_id").skill.apply(list).to_dict() for x in (pv8, p2))
        s8, s2 = score(gold, b8, canon)[0], score(gold, b2, canon)[0]
        for label, s in [("v8", s8), ("v8+duties", s2)]:
            ps, rs, fs = prf(s.tp_strict.sum(), s.pred.sum(), s.gold.sum())
            pl, rl, fl = prf(s.tp_lenient.sum(), s.pred.sum(), s.gold.sum())
            scores.append({"model": name, "setup": label, "predicted": s.pred.sum(), "P_strict": ps, "R_strict": rs,
                           "F1_strict": fs, "P_lenient": pl, "R_lenient": rl, "F1_lenient": fl,
                           "F1_strict_alias": f1_of(s, "tp_alias")})
        for col, label in [("tp_strict", "strict"), ("tp_lenient", "lenient"), ("tp_alias", "strict+alias")]:
            diff, lo, hi = paired_bootstrap(s2, s8, col, 2000)
            diffs.append({"model": name, "metric": label, "F1_v8": f1_of(s8, col), "F1_two_pass": f1_of(s2, col),
                          "diff": diff, "ci95_low": lo, "ci95_high": hi, "contains_0": "yes" if lo <= 0 <= hi else "no"})
        # counts beyond F1
        added = p2.merge(pv8[["posting_id", "skill"]], how="left", indicator=True).query("_merge == 'left_only'")
        rec, extras_added, collapsed = 0, [], {}
        for g in gold.itertuples():
            labels = split(g.gold_skills)
            miss8 = set(match(labels, b8.get(g.posting_id, []), True)[1])
            miss2 = set(match(labels, b2.get(g.posting_id, []), True)[1])
            rec += sum(1 for x in miss8 - miss2 if (g.n, x.strip().lower()) in original)
            new = added.loc[added.posting_id == g.posting_id, "skill"].tolist()
            fp2 = match(labels, b2.get(g.posting_id, []), True)[2]
            extras_added += [x for x in new if x in fp2]
            kept, pairs = collapse(b2.get(g.posting_id, []))
            collapsed[g.posting_id] = kept
            near += [{"model": name, "n": g.n, "kept": k, "near_duplicate": x} for k, x in pairs]
        # diagnostic only (the rule uses the standard score): near-duplicate pairs collapsed into one item
        sc_col = score(gold, collapsed)[0]
        p_col = prf(sc_col.tp_strict.sum(), sc_col.pred.sum(), sc_col.gold.sum())
        orig_miss = sum(1 for g in gold.itertuples() for x in match(split(g.gold_skills), b8.get(g.posting_id, []), True)[1]
                        if (g.n, x.strip().lower()) in original)
        counts.append({"model": name, "items_added_after_merge": len(added),
                       "added_matched_gold_strict": int(s2.tp_strict.sum() - s8.tp_strict.sum()),
                       "added_matched_gold_lenient": int(s2.tp_lenient.sum() - s8.tp_lenient.sum()),
                       "original_misses_v8": orig_miss, "original_misses_recovered": rec,
                       "added_not_matching_gold": len(extras_added),
                       "near_duplicate_pairs_after_merge": len([x for x in near if x["model"] == name]),
                       "P_strict_collapsed (diagnostic)": p_col[0], "F1_strict_collapsed (diagnostic)": p_col[2]})
        top += [{"model": name, "added_item_not_in_gold": k, "count": v}
                for k, v in pd.Series([x.strip().lower() for x in extras_added]).value_counts().head(10).items()]
    sc, df_d, ct, tp = pd.DataFrame(scores), pd.DataFrame(diffs), pd.DataFrame(counts), pd.DataFrame(top)
    for df, f in [(sc, "duties_scores"), (df_d, "duties_paired"), (ct, "duties_counts"), (tp, "duties_top_added_not_gold"),
                  (pd.DataFrame(near, columns=["model", "n", "kept", "near_duplicate"]), "duties_near_duplicate_pairs")]:
        df.to_csv(OUT / f"{f}.csv", index=False)
    dec = []
    for name in MODELS:
        a = sc[(sc.model == name) & (sc.setup == "v8")].iloc[0]
        b = sc[(sc.model == name) & (sc.setup == "v8+duties")].iloc[0]
        ok = b.F1_strict >= a.F1_strict and b.P_strict >= a.P_strict - 0.02
        dec.append({"model": name, "F1_strict_v8": a.F1_strict, "F1_strict_two_pass": b.F1_strict, "P_strict_v8": a.P_strict,
                    "P_strict_two_pass": b.P_strict, "decision": "adopt two-pass" if ok else "keep v8"})
    dec = pd.DataFrame(dec)
    dec.to_csv(OUT / "duties_decision.csv", index=False)
    pd.set_option("display.width", 250)
    for title, df in [("Scores", sc), ("Paired bootstrap (2,000 draws, same 50 postings)", df_d),
                      ("Counts", ct), ("Top 10 added items that did not match gold", tp), ("Decision (pre-registered rule)", dec)]:
        md += [f"## {title}", "", "```", df.to_string(index=False, float_format=lambda v: f"{v:.3f}"), "```", ""]
    (OUT / "duties_result.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
