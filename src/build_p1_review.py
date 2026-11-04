"""Build the P1 topic review report (Markdown + CSV) from the review workbook and frozen evidence.

    .venv/bin/python src/build_p1_review.py

Read-only: the workbook, memberships and reference links are only read. AI recommendations come
from p1_ai_recommendations_v1.json (written by Claude Code, NOT human-validated) and are kept in
clearly labelled columns. No API calls.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN = "hdbscan_10_umap10_ms1_2026-10-23"
REVIEW = ROOT / f"reports/sprint4_naming/{RUN}/topic_quality_review_v1"
WB = REVIEW / "sprint4_topic_quality_review.xlsx"
OUT = REVIEW / "p1_review"
RECS = OUT / "p1_ai_recommendations_v1.json"
INP = ROOT / f"data/processed/sprint4_input_{RUN}"
SOURCES = {"workbook": WB, "memberships": INP / "memberships.csv",
           "reference_links": INP / "reference_links.csv", "ai_recommendations": RECS}
LABEL = "AI-GENERATED, NOT HUMAN-VALIDATED"
FLAG_WHY = {
    "low_cohesion": "cos_mean {cos:.3f} is at or below the 25th percentile of all 374 topics",
    "near_duplicate_topic": "a neighbour centroid has cosine >= 0.90 ({dups})",
    "weak_exceeds_assigned": "{weak} weak members > {n} assigned members",
    "llm_confidence_low": "the naming model rated its own name 'low' confidence",
    "generic_name": "the name contains a generic word from the naming stage's list",
    "no_reference_link": "no assigned member has a confident ESCO / O*NET link",
    "unsupported_supporting_skills": "the model cited supporting skills that are not in the evidence it was given",
    "few_supporting_skills": "fewer supporting skills than the prompt asks for",
    "duplicate_name": "another topic got the same provisional name ({other})",
}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    before = {k: sha256(p) for k, p in SOURCES.items()}
    q = pd.read_excel(WB, "Review_Queue", dtype=str, keep_default_na=False)
    p1 = q[q["Review priority"].str.startswith("P1")].copy()
    assert len(p1) == 20 and p1["Topic ID"].is_unique
    assert (p1[["Reviewer decision", "Proposed corrected name", "Reviewer notes", "Reviewer ID", "Review timestamp"]] == "").all().all()
    mem = pd.read_csv(SOURCES["memberships"], dtype=str, keep_default_na=False)
    ref = pd.read_csv(SOURCES["reference_links"], dtype=str, keep_default_na=False).rename(columns={"score": "ref_score"})
    recs = json.loads(RECS.read_text())["topics"]
    assert set(recs) == set(p1["Topic ID"]), "recommendations must cover exactly the 20 P1 topics"

    rows = []
    for _, r in p1.iterrows():
        t = r["Topic ID"]
        m = mem[mem.topic_id == t].merge(ref, on="skill_key", how="left")
        m["s"] = m.score.astype(float)
        a, w = m[m.state == "assigned"].sort_values("s", ascending=False), m[m.state == "weak"].sort_values("s", ascending=False)
        assert len(a) == int(r["Assigned member count"]) and len(w) == int(r["Weak member count"])
        links = a[a.verdict == "known_skill"]
        why = []
        for f in [x for x in r["Review flags"].split(";") if x]:
            k, _, other = f.partition(":")
            why.append(f"{f}: " + FLAG_WHY.get(k, "flag from the naming stage").format(
                cos=float(r["Cohesion metric (cos_mean)"]), dups=r["Potential duplicate topic IDs"],
                weak=r["Weak member count"], n=r["Assigned member count"], other=other))
        rc = recs[t]
        rows.append({
            "topic_id": t, "provisional_name": r["Provisional name"], "description": r["Description"],
            "source_model": r["Source provider and model"], "model_confidence": r["Model confidence"],
            "model_confidence_reason": r["Model confidence reason"],
            "review_flags": r["Review flags"], "why_flagged": " | ".join(why),
            "n_assigned": int(r["Assigned member count"]), "n_weak": int(r["Weak member count"]),
            "cos_mean": float(r["Cohesion metric (cos_mean)"]), "cos_min": float(r["Cohesion min (cos_min)"]),
            "transversal": r["Transversal topic"],
            "representative_skills": r["Representative skills (cosine to centroid)"],
            "near_duplicates": r["Potential duplicate topic IDs"],
            "reference_coverage": r["Reference-link status"], "reference_link_types": r["Reference link types"],
            "member_reference_links": "; ".join(f"{s} -> {l} [{src}]" for s, l, src in zip(links.skill_key, links.ref_label, links.source)),
            "validity_screening": r["Validity screening (auto rules)"], "validity_reason": r["Validity screening reason"],
            "validity_ai_proposed_not_human": r["Validity AI-proposed review (not human)"],
            "hierarchy_treatment": r["Hierarchy treatment (screening)"],
            "assigned_members": "; ".join(a.skill_key), "weak_members": "; ".join(w.skill_key),
            "ai_recommendation": rc["ai_recommendation"], "ai_confidence": rc["ai_confidence"],
            "ai_evidence_sufficiency": rc["evidence_sufficiency"], "ai_rationale": rc["rationale"],
            "ai_secondary_notes": rc["secondary"], "ai_label": LABEL,
        })
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "p1_topic_review.csv", index=False)

    gen = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    cnt = df.ai_recommendation.value_counts()
    suff = df.ai_evidence_sufficiency.value_counts()
    L = [f"# Sprint 4 — P1 topic quality review ({len(df)} topics)", "",
         f"> **{LABEL}.** Every recommendation below was written by Claude Code from the frozen evidence. "
         "None is a reviewer decision. The workbook's reviewer fields were not touched; names, memberships and "
         "validity classes were not changed.", "",
         f"Generated {gen} by `src/build_p1_review.py`. Sources (sha256): " +
         "; ".join(f"`{p.relative_to(ROOT)}` {before[k][:12]}…" for k, p in SOURCES.items()), "",
         "P1 rule: review flags include `low_cohesion` and `near_duplicate_topic`, and model confidence is `low`.", "",
         "## Summary", "", f"AI recommendation counts ({LABEL.lower()}):", "", "| Recommendation | Topics |", "|---|---|"]
    L += [f"| {d} | {int(cnt.get(d, 0))} |" for d in ["KEEP", "RENAME", "INVESTIGATE_CLUSTER", "POTENTIAL_MERGE", "UNSURE"]]
    L += ["", "| Evidence sufficiency | Topics |", "|---|---|"] + [f"| {k} | {int(v)} |" for k, v in suff.items()]
    L += ["", "| Topic | Name | Validity (rules) | cos_mean | Assigned / weak | AI recommendation | AI conf. | Evidence |",
          "|---|---|---|---|---|---|---|---|"]
    L += [f"| {r.topic_id} | {r.provisional_name} | {r.validity_screening} | {r.cos_mean:.3f} | {r.n_assigned} / {r.n_weak} | "
          f"{r.ai_recommendation} | {r.ai_confidence} | {r.ai_evidence_sufficiency} |" for r in df.itertuples()]
    L += ["", "### Where the evidence is insufficient or partial", ""]
    L += [f"- **{r.topic_id}** ({r.ai_evidence_sufficiency}): {r.ai_secondary_notes}" for r in df.itertuples()
          if r.ai_evidence_sufficiency != "sufficient"]
    L += ["", "### Evidence gaps that apply to all P1 topics", "",
          "- No posting counts or supporting posting snippets per member are in the Sprint 4 snapshot, so ambiguous strings (acronyms, 'site', 'scales') cannot be checked against their posting context here.",
          "- `known_skill` reference links are automatic (`review_status = auto`) and some are wrong (e.g. food styling -> hairdressing, classical hand analysis -> read palms, dock carts -> moor vessels). Reference coverage therefore overstates how well some topics are grounded.",
          "- ESCO / O*NET broader-group purity is unavailable in the snapshot.", "",
          "## Topics", ""]
    for r in df.itertuples():
        L += [f"### {r.topic_id} — {r.provisional_name}", "",
              f"*{r.description}*", "",
              f"- **Source / model confidence:** {r.source_model} / {r.model_confidence} — {r.model_confidence_reason}",
              f"- **Members:** {r.n_assigned} assigned, {r.n_weak} weak · **cohesion** cos_mean {r.cos_mean:.3f} (min {r.cos_min:.3f}) · transversal {r.transversal}",
              f"- **Near-duplicates (centroid cosine):** {r.near_duplicates or '—'}",
              f"- **Reference coverage:** {r.reference_coverage} ({r.reference_link_types})",
              f"- **Validity screening:** {r.validity_screening} — {r.validity_reason} · hierarchy: {r.hierarchy_treatment}"
              + (f" · AI-proposed (not human): {r.validity_ai_proposed_not_human}" if r.validity_ai_proposed_not_human else ""),
              f"- **Review flags:** `{r.review_flags}`", "", "**Why flagged (source evidence)**", ""]
        L += [f"- {x}" for x in r.why_flagged.split(" | ")]
        L += ["", f"**Representative skills:** {r.representative_skills}", "",
              f"**Assigned members ({r.n_assigned}):** {r.assigned_members}", "",
              f"**Weak members ({r.n_weak}):** {r.weak_members or '—'}", "",
              f"**Confident member links:** {r.member_reference_links or '—'}", "",
              f"> **AI recommendation ({LABEL}): {r.ai_recommendation}** · confidence {r.ai_confidence} · evidence {r.ai_evidence_sufficiency}",
              f"> ", f"> {r.ai_rationale}", f"> ", f"> *Also:* {r.ai_secondary_notes}", ""]
    (OUT / "p1_topic_review.md").write_text("\n".join(L), encoding="utf-8")
    assert before == {k: sha256(p) for k, p in SOURCES.items()}, "a source file changed"
    print(f"wrote {len(df)} topics -> {(OUT / 'p1_topic_review.md').relative_to(ROOT)}, p1_topic_review.csv")
    print(cnt.to_dict(), suff.to_dict())


if __name__ == "__main__":
    main()
