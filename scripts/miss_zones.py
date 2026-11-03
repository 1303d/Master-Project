"""Where in the posting do the missed gold labels sit? No API calls: posting text + existing predictions only.

    py scripts/miss_zones.py

For each lenient miss on an ORIGINAL gold label (no audit finding; v3-proposed gold, dev), find the posting segment
(line / sentence) that holds the label's words and tag it:
  zone: requirement (the segment asks for it: "experience with", "knowledge of", "required", ... or sits under a
        qualifications heading) / duty (starts with a duty verb, "responsible for", "you will", or sits under a
        duties heading) / elsewhere / not in text
  form: list (the segment has 2+ separators: , ; / or the label is in parentheses) / sentence
Runs: Qwen v8, Haiku v8, and "Qwen-only" = Qwen v8 misses that Haiku v8 found (the gap between the models).
Heuristic tags: check the sample in miss_zones_sample.csv by hand before relying on small differences.
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluate import match, norm, split  # noqa: E402

OUT = ROOT / "reports" / "v8_dev_evaluation_2026-10-30"
REQ_HEAD = re.compile(r"qualif|requirement|what you (bring|need|have)|must have|preferred|skills|education|who you are|about you", re.I)
DUTY_HEAD = re.compile(r"responsib|duties|what you('ll| will) do|essential functions|job functions|day to day|your role|the role", re.I)
REQ_CUE = re.compile(r"experience (with|in|using)|knowledge of|proficien|ability to|able to|familiar|required|preferred|"
                     r"skills? in|understanding of|must (have|be)|years|expertise|background in|working knowledge|fluent|degree", re.I)
VERBS = (r"perform|prepar|manag|maintain|develop|assist|provid|coordinat|review|conduct|support|ensur|creat|design|"
         r"build|draft|lead|monitor|process|track|analy[sz]|implement|overse|work|collaborat|handl|schedul|respond|"
         r"identif|plan|test|install|repair|operat|train|communicat|serv|administer|document|gather|specif|migrat|updat|"
         r"troubleshoot|resolv|instruct|initiat|introduc|establish|generat|approv|execut|deliver|organi[sz]|negotiat|"
         r"evaluat|assess|investigat|research|writ|edit|reconcil|calculat|inspect|clean|load|pack|sort|select|receiv|"
         r"stor|ship|answer|greet|educat|assur|facilitat|participat|report|prospect|sell|represent|attend|advis|counsel|"
         r"diagnos|administ|record|enter|verif|audit|recommend|driv|own|partner|mentor|supervis|direct|configur|deploy")
# duty: the segment (or its main clause after an optional "The <role>" subject) starts with a duty verb
DUTY_CUE = re.compile(rf"^\W*(you will|will |responsible for|(the [\w ]{{1,40}}? )?({VERBS})\w*\b)", re.I)


def segments(text):
    """(segment, last heading seen) pairs; segments = lines split again at sentence ends."""
    out, head = [], ""
    # run-together bullets ("interactionsProvide remarkable ..."): break before a capitalised duty verb
    text = re.sub(r"(?<=[a-z.])([A-Z][a-z]+)",
                  lambda m: (chr(10) if re.match(rf"({VERBS})", m[1].lower()) else "") + m[1], text)
    for line in text.splitlines():
        line = line.strip(" •*-\t")
        if not line:
            continue
        if len(line.split()) <= 6 and not line.endswith("."):  # a short line without a full stop = a heading
            head = line
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", line):
            out.append((s, head))
    return out


def stems(words):
    return {w[:5] for w in words}  # "palletizing" ~ "palletize", "testing" ~ "test" (short words stay whole)


def locate(label, segs):
    want = stems(norm(label))
    best, best_hit = None, 0
    for s, head in segs:
        hit = len(want & stems(norm(s)))
        if hit > best_hit:
            best, best_hit = (s, head), hit
        if hit == len(want):
            return s, head, "full"
    if best and best_hit * 2 >= len(want):
        return best[0], best[1], "partial"
    return None, None, "not in text"


def tag(label, seg, head):
    if seg is None:
        return "not in text", ""
    zone = ("requirement" if REQ_CUE.search(seg) else "duty" if DUTY_CUE.search(seg)
            else "requirement" if REQ_HEAD.search(head) else "duty" if DUTY_HEAD.search(head) else "elsewhere")
    in_paren = any(set(norm(label)) <= set(norm(p)) for p in re.findall(r"\(([^)]*)\)", seg))
    form = "list" if len(re.findall(r",|;|/| and/or ", seg)) >= 2 or in_paren else "sentence"
    return zone, form


def main():
    gold = pd.read_csv(ROOT / "data/gold/gold_labels_v3_dev_proposed.csv", encoding="utf-8-sig")
    posts = pd.read_csv(ROOT / "data/gold/gold_postings_dev.csv", encoding="utf-8-sig").set_index("posting_id")
    gold = gold[gold.posting_id.isin(posts.index)]  # dev only
    long = pd.read_excel(ROOT / "data/gold/audit/gold_audit_dev_v3_proposed.xlsx", "Recommended Gold (long)")
    original = {(r.n, str(r.skill).strip().lower()) for r in long.itertuples()
                if r.under_review == "No" and not r.status.startswith("NEW")}
    pred = {m: pd.read_csv(ROOT / f"data/processed/statements_{r}.csv").groupby("posting_id").skill.apply(list).to_dict()
            for m, r in [("qwen", "qwen_qwen3.8-27b_v8"), ("haiku", "claude-haiku-5-5_v8")]}
    rows = []
    for g in gold.itertuples():
        labels = split(g.gold_skills)
        miss = {m: set(match(labels, pred[m].get(g.posting_id, []), True)[1]) for m in pred}
        segs = segments(posts.loc[g.posting_id, "description"])
        for x in labels:
            if (g.n, x.strip().lower()) not in original or not (x in miss["qwen"] or x in miss["haiku"]):
                continue
            seg, head, found = locate(x, segs)
            zone, form = tag(x, seg, head)
            rows.append({"n": g.n, "label": x, "qwen_missed": x in miss["qwen"], "haiku_missed": x in miss["haiku"],
                         "zone": zone, "form": form, "found": found, "heading": head or "", "segment": (seg or "")[:220]})
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "miss_zones.csv", index=False)
    groups = {"Qwen v8 misses": d[d.qwen_missed], "Haiku v8 misses": d[d.haiku_missed],
              "Qwen-only (Haiku found it)": d[d.qwen_missed & ~d.haiku_missed]}
    summ = []
    for name, x in groups.items():
        for (z, f), n in x.groupby(["zone", "form"]).size().items():
            summ.append({"group": name, "zone": z, "form": f, "count": n, "share": n / len(x)})
    s = pd.DataFrame(summ)
    s.to_csv(OUT / "miss_zones_summary.csv", index=False)
    d[d.qwen_missed].sample(25, random_state=0).to_csv(OUT / "miss_zones_sample.csv", index=False)
    for name, x in groups.items():
        print(f"\n{name}: {len(x)}")
        print(x.groupby(["zone", "form"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
