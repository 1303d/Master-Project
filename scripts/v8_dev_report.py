"""Build reports/v8_dev_evaluation_2026-10-30.md and its CSV tables (dev split only; scoring = src/evaluate.py).

    py scripts/v8_dev_report.py

Reads finished runs only (every run listed below has all 50 dev postings done). It never reads test postings.
"""
import hashlib
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluate import f1_of, load_aliases, match, norm, pairs_ok, paired_bootstrap, prf, score, split  # noqa: E402

OUT = ROOT / "reports" / "v8_dev_evaluation_2026-10-30"
REPORT = ROOT / "reports" / "v8_dev_evaluation_2026-10-30.md"
P = ROOT / "data" / "processed"
GOLDS = {"v2": ROOT / "data/gold/gold_labels_v2.csv", "v3_dev_proposed": ROOT / "data/gold/gold_labels_v3_dev_proposed.csv"}
ALIASES = ROOT / "config" / "skill_aliases_manual.csv"
LINKS = P / "skill_links.csv"
AUDIT = ROOT / "data/gold/audit/gold_audit_dev_v3_proposed.xlsx"
RUNS = {  # run name -> (model, provider, prompt file, typed, delay s)
    "claude-haiku-5-5_v3": ("claude-haiku-5-5", "anthropic", "skill_extraction_v3.txt", False, "4 (default, earlier run)"),
    "claude-haiku-5-5_v8a": ("claude-haiku-5-5", "anthropic", "skill_extraction_v8a.txt", True, "1"),
    "claude-haiku-5-5_v8": ("claude-haiku-5-5", "anthropic", "skill_extraction_v8.txt", True, "1"),
    "qwen_qwen3.8-27b_v3": ("qwen/qwen3.8-27b", "groq", "skill_extraction_v3.txt", False, "4 (default, earlier run)"),
    "qwen_qwen3.8-27b_v5": ("qwen/qwen3.8-27b", "groq", "skill_extraction_v5.txt", False, "4 (default, earlier run)"),
    "qwen_qwen3.8-27b_v8": ("qwen/qwen3.8-27b", "groq", "skill_extraction_v8.txt", True, "40"),
}
MAIN = {"claude-haiku-5-5": "claude-haiku-5-5_v8", "qwen/qwen3.8-27b": "qwen_qwen3.8-27b_v8"}  # chosen prompt v8
PRICE = {"in": 0.10, "out": 0.50, "batch_in": 0.05, "batch_out": 0.25}  # USD / MTok, Haiku 5.5, prompts <= 100k
PRICE_SRC = "https://platform.claude.com/docs/en/about-claude/pricing (read 2026-10-30)"
TRAIT_WORDS = {"attention to detail", "detail-oriented", "detail oriented", "detail orientation"}
RULE_LIST = ["filing", "answering phones", "scanning documents", "bathing patients", "processing customer invoices",
             "preparing reports", "meeting coordination", "work orders", "attend court hearings",
             "file and maintain records", "answer call lights", "process routine paperwork",  # rules 9 / 17
             "pharmaceuticals", "healthcare", "medical devices", "residential solar market", "commercial environments",
             "general liability", "heavy duty trucks",  # rule 10
             "revenue growth", "profitability", "operational efficiency", "safety culture", "accuracy"]  # rule 11
RULE_NORM = {norm(x) for x in RULE_LIST}
md, csvs = [], []


def save(df, name):
    df.to_csv(OUT / f"{name}.csv", index=False)
    csvs.append(f"reports/v8_dev_evaluation_2026-10-30/{name}.csv")
    return df


def table(df, floatfmt=3):
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f":
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else f"{v:.{floatfmt}f}")
    return "\n".join(["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
                     + ["| " + " | ".join(str(v).replace("|", "/") for v in r) + " |" for r in df.itertuples(index=False)])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_gold(name):
    g = pd.read_csv(GOLDS[name], encoding="utf-8-sig")
    halves = pd.read_csv(ROOT / "data/gold/gold_split.csv", encoding="utf-8-sig")
    g = g[g.posting_id.isin(halves.loc[halves.split == "dev", "posting_id"])].copy()
    g["sector_eval"] = g.posting_id.map(halves.set_index("posting_id").sector_eval)  # --sector-source split
    return g


def preds(run, drop_traits=False):
    d = pd.read_csv(P / f"statements_{run}.csv")
    if drop_traits:
        links = pd.read_csv(LINKS)
        d = d[~d.skill.str.strip().str.lower().isin(set(links.loc[links.verdict == "trait", "skill"]))]
    return d, d.groupby("posting_id").skill.apply(list).to_dict()


canon = load_aliases(ALIASES)
gold = {k: load_gold(k) for k in GOLDS}
done = {r: set(pd.read_csv(P / f"extraction_postings_{r}.csv").query("status == 'done'").posting_id) for r in RUNS}
shared = set.intersection(*done.values())
assert all(len(v) == 50 for v in done.values()) and len(shared) == 50, "every run must have all 50 dev postings"
scored = {}  # (run, gold) -> per-posting frame
for r in RUNS:
    for g in GOLDS:
        scored[r, g] = score(gold[g], preds(r)[1], canon)[0]

# ---------- 1. Run manifest
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
stamp = lambda f: (OUT / f).read_text().split() if (OUT / f).exists() else []
q_end = [l.split("ended ")[1] for l in (OUT / "run_Q8_stops.txt").read_text().splitlines() if "ended" in l]
times = {"claude-haiku-5-5_v8a": stamp("run_H8a_start.txt"), "claude-haiku-5-5_v8": stamp("run_H8_start.txt"),
         "qwen_qwen3.8-27b_v8": stamp("run_Q8_start.txt")[:1] + q_end}
rows = []
for r, (model, prov, prompt, typed, delay) in RUNS.items():
    m = P / f"cache_keys_{r}.csv"
    st = json.loads(pd.read_csv(m).settings.iloc[0]) if m.exists() and "settings" in pd.read_csv(m) else {}
    t = times.get(r, [])
    rows.append({"run": r, "model_id": model, "provider": prov, "prompt": prompt, "prompt_sha256": sha(ROOT / "prompts" / prompt),
                 "typed": typed, "types": ",".join(st.get("types", [])) or ("all 8" if typed else "-"),
                 "temperature": st.get("temperature", "None (anthropic default)" if prov == "anthropic" else 0.0),
                 "reasoning_format": st.get("reasoning_format", "-"), "delay_s": delay,
                 "started_utc": t[0] if t else "earlier run (cache reused)", "ended_utc": t[-1] if len(t) > 1 else "",
                 "postings_scored": len(done[r]), "failed": 0})
man = save(pd.DataFrame(rows), "01_run_manifest")
gold_sha = save(pd.DataFrame([{"gold": k, "file": str(v.relative_to(ROOT)), "sha256": sha(v)} for k, v in GOLDS.items()]
                             + [{"gold": "audit", "file": str(AUDIT.relative_to(ROOT)), "sha256": sha(AUDIT)},
                                {"gold": "aliases", "file": str(ALIASES.relative_to(ROOT)), "sha256": sha(ALIASES)}]),
                "01_input_files")
stops = (OUT / "run_Q8_stops.txt").read_text().strip().splitlines()
md += ["# v8 dev evaluation (Haiku and Qwen), 2026-10-30", "",
       "Dev split only (50 postings). Scoring = `src/evaluate.py` functions, unchanged. Sectors = `gold_split.csv` "
       "sector_eval (`--sector-source split`). Aliases = `config/skill_aliases_manual.csv`.", "",
       "## 1. Run manifest", "", f"- **Code commit:** `{commit}` (runs used commit `768d388`; later commits add only this report).",
       "- **Qwen v8 stops / resumes:** first run 2026-10-30T05:29:56Z; 36/50 done when the Claude Code session ended "
       "during a 429 wait (retry-after up to 1,121 s). " + " ".join(stops) + ". Same settings; 14 new calls; 0 failed.",
       "- Qwen v3 / v5 and Haiku v3 were rebuilt from the cache (`--legacy-cache-key`, 0 calls).", "",
       table(man), "", table(gold_sha), ""]

# ---------- 2. Main results
rows = []
for (r, g), df in scored.items():
    ps, rs, fs = prf(df.tp_strict.sum(), df.pred.sum(), df.gold.sum())
    pl, rl, fl = prf(df.tp_lenient.sum(), df.pred.sum(), df.gold.sum())
    nt = score(gold[g], preds(r, drop_traits=True)[1])[0]
    rows.append({"run": r, "gold": g, "postings": len(df), "gold_items": df.gold.sum(), "predicted": df.pred.sum(),
                 "P_strict": ps, "R_strict": rs, "F1_strict": fs, "P_lenient": pl, "R_lenient": rl, "F1_lenient": fl,
                 "F1_strict_alias": f1_of(df, "tp_alias"), "F1_strict_traits_dropped": f1_of(nt, "tp_strict")})
main = save(pd.DataFrame(rows).sort_values(["gold", "run"]), "02_main_results")
md += ["## 2. Main results", "", "F1 traits dropped = predicted items linked as `trait` in `skill_links.csv` removed "
       "(extra column only).", "", table(main), ""]

# ---------- 3. Paired comparisons (v3-proposed gold)
pairs = [("claude-haiku-5-5_v8a", "claude-haiku-5-5_v3"), ("claude-haiku-5-5_v8", "claude-haiku-5-5_v8a"),
         ("claude-haiku-5-5_v8", "claude-haiku-5-5_v3"), ("qwen_qwen3.8-27b_v8", "qwen_qwen3.8-27b_v3"),
         ("qwen_qwen3.8-27b_v8", "claude-haiku-5-5_v8")]
rows = []
for cur, base in pairs:
    c, b = scored[cur, "v3_dev_proposed"], scored[base, "v3_dev_proposed"]
    for col, label in [("tp_strict", "strict"), ("tp_lenient", "lenient"), ("tp_alias", "strict+alias")]:
        d, lo, hi = paired_bootstrap(c, b, col, 2000)
        rows.append({"this": cur, "baseline": base, "metric": label, "baseline_F1": f1_of(b, col), "this_F1": f1_of(c, col),
                     "diff": d, "ci95_low": lo, "ci95_high": hi, "interval_contains_0": "yes" if lo <= 0 <= hi else "no"})
paired = save(pd.DataFrame(rows), "03_paired_comparisons")
md += ["## 3. Paired comparisons (v3-proposed gold, same 50 postings, 2,000 bootstrap draws, seed 0)", "", table(paired), ""]
for cur, base in pairs:
    s = paired[(paired.this == cur) & (paired.baseline == base) & (paired.metric == "strict")].iloc[0]
    md.append(f"- {cur} vs {base}: strict {s['diff']:+.3f} [{s.ci95_low:+.3f}, {s.ci95_high:+.3f}] -> "
              + ("interval contains 0 (difference not shown)." if s.interval_contains_0 == "yes" else "interval excludes 0."))
md.append("")

# ---------- 4. Prompt decision
a, b = scored["claude-haiku-5-5_v8a", "v3_dev_proposed"], scored["claude-haiku-5-5_v8", "v3_dev_proposed"]
pa, _, fa = prf(a.tp_strict.sum(), a.pred.sum(), a.gold.sum())
pb, _, fb = prf(b.tp_strict.sum(), b.pred.sum(), b.gold.sum())
chosen = "v8" if fb >= fa and pb >= pa - 0.02 else "v8a"
dec = save(pd.DataFrame([{"F1_strict_v8a": fa, "F1_strict_v8": fb, "P_strict_v8a": pa, "P_strict_v8": pb,
                          "F1_rule_met": fb >= fa, "precision_rule_met": pb >= pa - 0.02, "chosen": chosen}]), "04_prompt_decision")
md += ["## 4. Prompt decision", "", "Rule (fixed before results): choose v8 if strict F1(v8) >= F1(v8a) and strict "
       "P(v8) >= P(v8a) - 0.02 (Haiku, v3-proposed gold, same postings); else v8a.", "", table(dec, 4), "",
       f"**Chosen: {chosen}.** Qwen was run on {chosen} only.", ""]

# ---------- 5. Per sector
rows = []
for model, r in MAIN.items():
    df = scored[r, "v3_dev_proposed"]
    for sec, d in df.groupby("sector"):
        ps, rs, fs = prf(d.tp_strict.sum(), d.pred.sum(), d.gold.sum())
        pl, rl, fl = prf(d.tp_lenient.sum(), d.pred.sum(), d.gold.sum())
        rows.append({"model": model, "sector": sec, "postings": len(d), "gold_items": d.gold.sum(), "P_strict": ps,
                     "R_strict": rs, "F1_strict": fs, "P_lenient": pl, "R_lenient": rl, "F1_lenient": fl,
                     "note": "too small to interpret" if len(d) < 5 else ""})
md += ["## 5. Per sector (v3-proposed gold, prompt v8)", "", table(save(pd.DataFrame(rows), "05_per_sector")), ""]

# ---------- 6. Error breakdown
long = pd.read_excel(AUDIT, "Recommended Gold (long)")
find = pd.read_excel(AUDIT, "Audit Findings")
review = find[find.recommended_action == "REVIEW"]
review_by_n = review.groupby("n").recommended_skill.apply(lambda s: [str(x) for x in s if pd.notna(x)]).to_dict()
status = {(r.n, str(r.skill).strip().lower()): ("review" if r.under_review == "Yes" else
                                                 "audit_added_or_revised" if r.status.startswith("NEW") else "original")
          for r in long.itertuples()}
links = pd.read_csv(LINKS)
trait_keys = set(links.loc[links.verdict == "trait", "skill"]) | TRAIT_WORDS
summ, near, top = [], [], []
for r in list(MAIN.values()) + ["qwen_qwen3.8-27b_v5"]:
    g, by = gold["v3_dev_proposed"], preds(r)[1]
    miss_cls, extra_cls = {}, {}
    per_post_orig = {}
    for row in g.itertuples():
        _, fn, fp = match(split(row.gold_skills), by.get(row.posting_id, []), lenient=True)
        for x in fn:
            c = status.get((row.n, x.strip().lower()), "original")
            miss_cls[c] = miss_cls.get(c, 0) + 1
            if c == "original":
                per_post_orig.setdefault(row.n, []).append(x)
        for x in fp:
            k = x.strip().lower()
            if any(pairs_ok(norm(x), norm(c), True) for c in review_by_n.get(row.n, [])):
                c = "REVIEW candidate"
            elif k in trait_keys:
                c = "trait"
            elif norm(x) in RULE_NORM:
                c = "rule-list violation"
            elif len(norm(x)) == 1:
                c = "single word"
            elif [m for m in fn if set(norm(m)) & set(norm(x))]:
                c = "near-miss wording"
                near += [{"run": r, "n": row.n, "extra": x, "missed_gold": m} for m in fn if set(norm(m)) & set(norm(x))]
            else:
                c = "other"
            extra_cls[c] = extra_cls.get(c, 0) + 1
    summ += [{"run": r, "error": "miss", "class": k, "count": v} for k, v in sorted(miss_cls.items())]
    summ += [{"run": r, "error": "extra", "class": k, "count": v} for k, v in sorted(extra_cls.items())]
    top += [{"run": r, "n": n, "misses_on_original_gold": len(v), "missed": "; ".join(v)}
            for n, v in sorted(per_post_orig.items(), key=lambda kv: -len(kv[1]))[:10]]
md += ["## 6. Error breakdown (lenient, v3-proposed gold)", "",
       "Classes are checked in this order; each error is counted once. 'Original' = gold label with no audit finding.", "",
       table(save(pd.DataFrame(summ), "06_error_classes")), "",
       f"Near-miss pairs (extra shares a word with a missed gold item in the same posting): "
       f"{len(near)} pairs, all in `06_near_miss_pairs.csv`. First 15:", "",
       table(save(pd.DataFrame(near), "06_near_miss_pairs").head(15)), "",
       "Top 10 postings by misses on original gold labels:", "", table(save(pd.DataFrame(top), "06_top_miss_postings")), ""]

# ---------- 7. Instruction-following checks
logs = {"claude-haiku-5-5_v8a": ["run_H8a.log"], "claude-haiku-5-5_v8": ["run_H8.log"],
        "qwen_qwen3.8-27b_v8": ["run_Q8.log", "run_Q8_resume1.log"]}
rows, zero_rows, examples = [], [], []
manifests = {r: pd.read_csv(P / f"cache_keys_{r}.csv").set_index("posting_id") for r in RUNS}
for r, (model, prov, *_ ) in RUNS.items():
    d, by = preds(r)
    low = d.skill.str.strip().str.lower()
    trait = d[low.isin(TRAIT_WORDS)]
    rule = d[d.skill.map(lambda s: norm(s) in RULE_NORM)]
    scope = []
    for pid, items in by.items():
        ks = {x.strip().lower() for x in items}
        for x in ks:
            m = re.match(r"(month|quarter|year)[- ]end (.+)", x)
            if m and any(y != x and y.endswith(m.group(2)) and re.match(r"(month|quarter|year)[- ]end", y) for y in ks):
                scope.append(f"{pid}: {x}")
    fails = sum((OUT / f).read_text().count("FAILED") for f in logs.get(r, []) if (OUT / f).exists())
    rows.append({"run": r, "attention_to_detail_or_detail_oriented": len(trait), "scope_duplicate_items": len(scope),
                 "rule_9_10_11_literal_matches": len(rule), "teamwork": int((low == "teamwork").sum()),
                 "team_player": int((low == "team player").sum()), "evidence_verbatim_rate": d.evidence_in_text.mean(),
                 "json_failures": fails if r in logs else "0 (earlier run, all done)"})
    examples += [{"run": r, "check": "trait", "item": f"{x.posting_id}: {x.skill}"} for x in trait.head(5).itertuples()]
    examples += [{"run": r, "check": "rule list", "item": f"{x.posting_id}: {x.skill}"} for x in rule.head(5).itertuples()]
    examples += [{"run": r, "check": "scope duplicate", "item": s} for s in scope[:5]]
    df = scored[r, "v3_dev_proposed"]
    for z in df[(df.pred == 0) & (df.gold > 0)].itertuples():
        key = manifests[r].loc[z.posting_id, "cache_key"]
        raw = json.loads((ROOT / "cache" / prov / f"{key}.json").read_text(encoding="utf-8"))["output"]
        zero_rows.append({"run": r, "n": z.n, "posting_id": z.posting_id, "gold_items": z.gold,
                          "raw_answer": json.dumps(raw, ensure_ascii=False)[:300]})
md += ["## 7. Instruction-following checks", "", table(save(pd.DataFrame(rows), "07_instruction_checks")), "",
       "Examples (max 5 per check and run):", "", table(save(pd.DataFrame(examples), "07_examples")), "",
       "Postings with gold skills but zero predictions:", "",
       table(save(pd.DataFrame(zero_rows, columns=["run", "n", "posting_id", "gold_items", "raw_answer"]), "07_zero_predictions"))
       if zero_rows else "None in any run.", ""]

# ---------- 8. Types
rows, sample = [], []
for r in ["claude-haiku-5-5_v8a", "claude-haiku-5-5_v8", "qwen_qwen3.8-27b_v8"]:
    t = pd.read_csv(P / f"typed_{r}.csv")
    vc = t.type.value_counts()
    rows.append({"run": r, "items": len(t), **{k: int(vc.get(k, 0)) for k in ["skill", "knowledge", "tool"]},
                 "other_types": int(len(t) - vc.reindex(["skill", "knowledge", "tool"]).fillna(0).sum())})
for model, r in MAIN.items():
    t = pd.read_csv(P / f"typed_{r}.csv")
    s = t.sample(30, random_state=0)
    sample += [{"model": model, "posting_id": x.posting_id, "item": x.skill, "type": x.type, "evidence": x.evidence,
                "human_check": ""} for x in s.itertuples()]
save(pd.DataFrame(sample), "08_type_sample_for_human_check")
md += ["## 8. Types", "", table(save(pd.DataFrame(rows), "08_type_distribution")), "",
       "30 random typed items per model (seed 0) for a human check: `08_type_sample_for_human_check.csv` "
       "(`human_check` left empty).", ""]

# ---------- 9. Tokens, limits, cost
calls = pd.read_csv(ROOT / "reports/token_calls.csv")
lim = json.loads((OUT / "groq_limits_headers.json").read_text())
rows = []
for model, r in MAIN.items():
    e = pd.read_csv(P / f"extraction_postings_{r}.csv")
    tot = e.tokens_in + e.tokens_out
    rows.append({"model": model, "run": r, "in_mean": e.tokens_in.mean(), "in_median": e.tokens_in.median(),
                 "in_max": e.tokens_in.max(), "out_mean": e.tokens_out.mean(), "out_median": e.tokens_out.median(),
                 "out_max": e.tokens_out.max(), "total_mean": tot.mean(), "calls": len(e)})
tok = save(pd.DataFrame(rows), "09_tokens_per_posting")
q429 = sum((OUT / f).read_text().count("429 from API") for f in logs["qwen_qwen3.8-27b_v8"])
calls["t"] = pd.to_datetime(calls.called_at)
g = calls[calls.provider == "groq"]
first_long = pd.Timestamp("2026-10-30T06:47:31Z")  # time the 1,121 s retry-after was seen
window = g[(g.t > first_long - pd.Timedelta(hours=24)) & (g.t <= first_long)]
used_24h = int(window.tokens_in.sum() + window.tokens_out.sum())
qm, hm = tok.set_index("model").total_mean, tok.set_index("model")
proj = []
for tpd in [200_000, used_24h]:
    total = qm["qwen/qwen3.8-27b"] * 2000
    proj.append({"model": "qwen/qwen3.8-27b", "assumption": f"TPD {tpd:,}" + (" (Dhanush's figure, unmeasured)" if tpd == 200_000
                 else " (Groq tokens logged in the 24 h before the long 429s began: an estimate of the real TPD)"),
                 "total_tokens_2000": round(total), "days_by_tokens": round(total / tpd, 1),
                 "days_by_requests": round(2000 / int(lim["x-ratelimit-limit-requests"]), 1),
                 "cost_usd": 0.0})
h = hm.loc["claude-haiku-5-5"]
cin, cout = h.in_mean * 2000 / 1e6, h.out_mean * 2000 / 1e6
proj.append({"model": "claude-haiku-5-5", "assumption": f"standard price, {PRICE_SRC}", "total_tokens_2000": round(h.total_mean * 2000),
             "days_by_tokens": "", "days_by_requests": "", "cost_usd": cin * PRICE["in"] + cout * PRICE["out"]})
proj.append({"model": "claude-haiku-5-5", "assumption": "Message Batches API (50% off; not yet checked for this key)",
             "total_tokens_2000": round(h.total_mean * 2000), "days_by_tokens": "", "days_by_requests": "",
             "cost_usd": cin * PRICE["batch_in"] + cout * PRICE["batch_out"]})
md += ["## 9. Tokens, limits and cost", "", table(tok, 0), "",
       f"- Qwen hidden reasoning share: **not recorded** (the extractor stores only `completion_tokens`; "
       f"`reasoning_format=hidden` output tokens include the reasoning).",
       f"- Qwen v8 calls: 50 paid (36 + 14 on resume), 0 failed, {q429} retries after 429.",
       f"- Groq limits (headers {lim['read_at']}): requests/day {lim['x-ratelimit-limit-requests']}, tokens/min "
       f"{lim['x-ratelimit-limit-tokens']}. Tokens/day is not in the headers; read it on the console Limits page.",
       f"- Groq tokens logged in the 24 h before the long 429s: {used_24h:,}.", "",
       table(save(pd.DataFrame(proj), "09_projection_2000"), 2), ""]

# ---------- 10. Independence check
bias = subprocess.run([sys.executable, str(ROOT / "src/bias_check.py"), "--split", "dev", "--runs",
                       "claude-haiku-5-5:v8", "qwen/qwen3.8-27b:v8", "claude-haiku-5-5:v3", "qwen/qwen3.8-27b:v3"],
                      capture_output=True, text=True, cwd=ROOT / "src").stdout.strip()
v2 = gold["v2"].set_index("posting_id")
rows = []
for model, r in MAIN.items():
    by = preds(r)[1]
    hit = {"accepted": [0, 0, 0], "human": [0, 0, 0]}  # strict hits, lenient hits, items
    for row in gold["v3_dev_proposed"].itertuples():
        g = split(row.gold_skills)
        _, human, _ = match(g, split(v2.loc[row.posting_id, "suggested_skills"]), lenient=False)
        acc = [x for x in g if x not in human]
        for part, items in [("accepted", acc), ("human", human)]:
            hit[part][0] += match(items, by.get(row.posting_id, []), False)[0]
            hit[part][1] += match(items, by.get(row.posting_id, []), True)[0]
            hit[part][2] += len(items)
    for part, (s, l, n) in hit.items():
        rows.append({"model": model, "gold_part": "accepted LLM suggestion" if part == "accepted" else "human-added / rewritten",
                     "items": n, "recall_strict": s / n, "recall_lenient": l / n})
ind = save(pd.DataFrame(rows), "10_independence")
md += ["## 10. Independence check", "", "`src/bias_check.py --split dev` (gold_labels.csv v1, lenient):", "", "```", bias, "```",
       "", "v3-proposed gold split by v2 `suggested_skills` (strict match = accepted suggestion):", "", table(ind), ""]

# ---------- 11. Ten example postings
g = gold["v3_dev_proposed"].sort_values("n")
picked, seen = [], set()
for row in g.itertuples():  # first posting of each sector in n order, then fill by n order
    if row.sector_eval not in seen:
        picked.append(row.n); seen.add(row.sector_eval)
for row in g.itertuples():
    if len(picked) >= 10:
        break
    if row.n not in picked:
        picked.append(row.n)
picked = sorted(picked[:10])
hb, qb = preds(MAIN["claude-haiku-5-5"])[1], preds(MAIN["qwen/qwen3.8-27b"])[1]
rows = []
for row in g[g.n.isin(picked)].itertuples():
    gl = split(row.gold_skills)

    def mark(pred):
        _, fn, fp = match(gl, pred, True)
        return "; ".join(x if x in fp else f"✓{x}" for x in pred)
    rows.append({"n": row.n, "sector": row.sector_eval, "gold": "; ".join(gl), "haiku_v8": mark(hb.get(row.posting_id, [])),
                 "qwen_v8": mark(qb.get(row.posting_id, []))})
md += ["## 11. Ten example postings (one per sector in `n` order, then by `n`)", "",
       "✓ = matched a gold item (lenient). Unmarked = extra.", "", table(save(pd.DataFrame(rows), "11_examples")), ""]

# ---------- 12. Facts for the batch decision
gap = {m: ind[(ind.model == m) & (ind.gold_part == "accepted LLM suggestion")].recall_strict.iloc[0]
          - ind[(ind.model == m) & (ind.gold_part != "accepted LLM suggestion")].recall_strict.iloc[0] for m in MAIN}
x = paired[(paired.this == "qwen_qwen3.8-27b_v8") & (paired.baseline == "claude-haiku-5-5_v8")].set_index("metric")
mr = main[main.gold == "v3_dev_proposed"].set_index("run")
pj = pd.DataFrame(proj)
facts = save(pd.DataFrame([
    {"model": "claude-haiku-5-5 (v8)", "F1_strict": mr.loc["claude-haiku-5-5_v8", "F1_strict"],
     "F1_lenient": mr.loc["claude-haiku-5-5_v8", "F1_lenient"], "Qwen_minus_Haiku_strict_ci95": "",
     "2000_postings": f"${pj.cost_usd.iloc[2]:.2f} standard / ${pj.cost_usd.iloc[3]:.2f} batch, paid key",
     "independence": f"strict recall accepted-suggestion minus human-added: {gap['claude-haiku-5-5']:+.3f}; "
                     "Claude model, same family as the suggesting LLM"},
    {"model": "qwen/qwen3.8-27b (v8)", "F1_strict": mr.loc["qwen_qwen3.8-27b_v8", "F1_strict"],
     "F1_lenient": mr.loc["qwen_qwen3.8-27b_v8", "F1_lenient"],
     "Qwen_minus_Haiku_strict_ci95": f"{x.loc['strict', 'diff']:+.3f} [{x.loc['strict', 'ci95_low']:+.3f}, {x.loc['strict', 'ci95_high']:+.3f}]",
     "2000_postings": f"{pj.days_by_tokens.iloc[0]:.1f} days at 200k TPD; {pj.days_by_tokens.iloc[1]:.1f} days at ~{used_24h:,} (observed); free",
     "independence": f"strict recall accepted-suggestion minus human-added: {gap['qwen/qwen3.8-27b']:+.3f}; "
                     "not a suggesting model"}]), "12_batch_facts")
md += ["## 12. Facts for the batch decision (no recommendation)", "", table(facts), ""]

# ---------- 13 / 14
md += ["## 13. Problems found", "",
       "1. `tests/test_core.py:97-101` `test_reproduce_official_test_score` runs `evaluate.py --split test`; running the "
       "full test suite scores the test split. It also fails now: `evaluate.py` prints only the first 12 report lines "
       "and the `**All**` row moved below them (Desktop's 2 new header lines). It was run once by accident on "
       "2026-10-30 (old v3 predictions, numbers unchanged, report file reverted); skipped since.",
       "2. `tests/test_core.py:72` expected `validate_output` items without the `type` key (stale since `--typed`); "
       "fixed in `768d388`.",
       "3. Instructions name `data/skill_aliases_manual.csv`; the file is `config/skill_aliases_manual.csv`.",
       "4. `src/evaluate.py:166-172` report name has no baseline in it: `--baseline X` and `--baseline Y` for the same "
       "run write the same `..._paired.md` (second overwrites first). Numbers here come from this script instead.",
       "5. `prompts/skill_extraction_v8.txt`: the duty scan is rule 17 but sits between rules 12 and 13 (numbering "
       "out of order). Not edited (hard rule 3).",
       "6. `src/extract_skills.py` GroqBackend stores only `completion_tokens`, so Qwen's hidden reasoning share "
       "cannot be reported.",
       "7. The Qwen run is a child of the Claude Code session: it stopped when the session ended during a 429 wait. "
       "For the 2,000 batch, run it outside Claude Code (or as a scheduled task).",
       "8. Groq tokens/day is not in the response headers; 1,121 s retry-after waits started after "
       f"{used_24h:,} Groq tokens in 24 h.",
       "9. `CLAUDE.md` (cache row) still says the key is model + prompt + text and 'never change the formula'; "
       "since 2026-10-30 call settings are in the key (old caches via `--legacy-cache-key`).",
       "10. `gold_labels_v3_dev_proposed.csv` has no `sector_fixed`; all scores here use `gold_split.csv` sector_eval.",
       "", "## 14. Files produced", "", "- `reports/v8_dev_evaluation_2026-10-30.md` (this file)",
       "- `scripts/v8_dev_report.py` (builds this report)",
       "- `data/processed/statements_*`, `typed_*`, `extraction_postings_*`, `cache_keys_*` for "
       "claude-haiku-5-5_v8a, claude-haiku-5-5_v8, qwen_qwen3.8-27b_v8",
       "- run logs and limits: `reports/v8_dev_evaluation_2026-10-30/run_*.log`, `run_*_start.txt`, "
       "`run_Q8_stops.txt`, `groq_limits_headers.json`"] + [f"- `{c}`" for c in csvs]
REPORT.write_text("\n".join(md) + "\n", encoding="utf-8")
print(f"Report -> {REPORT.relative_to(ROOT)} ({len(csvs)} CSV tables)")
