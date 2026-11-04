"""Sprint 4 P1 evidence reconciliation v2 (read-only).

    .venv/bin/python src/reconcile_p1_evidence.py

Joins the recovered Sprint 3 extraction records (data/interim/prepared_mentions.csv) to the 976 P1 membership
records through the frozen alias table (alias_key -> skill_key), and writes record / skill / topic evidence
tables plus a report and manifest to p1_review/p1_evidence_reconciliation_v2/.

Evidence classes are kept apart:
  extraction        statement rows from prepared_mentions.csv. AI-generated (model column), review_status as recorded.
  posting_context   whether the evidence quote is found verbatim in a locally available posting text
                    (noise-review JDs, sample2000, gold dev). Verification of the quote, not of the meaning.
  human_review      Sprint 3 noise-review decisions (weak members only), with the file's own provenance markers.
  candidate flags   deterministic rules -> "candidate for human review", never a confirmed error.
  ai_v1_*           AI flags from p1_remediation_proposals.json (v1), copied as-is and labelled AI.
Nothing is renamed, merged, split, reassigned or excluded. Fails loudly if any invariant differs.
"""
import hashlib
import json
import platform
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN = "hdbscan_10_umap10_ms1_2026-10-23"
INP = ROOT / f"data/processed/sprint4_input_{RUN}"
P1 = ROOT / f"reports/sprint4_naming/{RUN}/topic_quality_review_v1/p1_review"
OUT = P1 / "p1_evidence_reconciliation_v2"
S2K = Path("/Users/lochan/Downloads/sample2000_qwen_v3_2026-10-21_1545")
INPUTS = {
    "prepared_mentions": ROOT / "data/interim/prepared_mentions.csv",
    "aliases": INP / "aliases.csv",
    "memberships": INP / "memberships.csv",
    "p1_traceability_v1": P1 / "p1_evidence_traceability.csv",
    # supporting (read-only) evidence sources
    "input_manifest": INP / "manifest.json",
    "reference_links": INP / "reference_links.csv",
    "sprint3_noise_workbook": ROOT / "reports/sprint3_noise.xlsx",
    "p1_remediation_proposals_v1_ai": P1 / "p1_remediation_proposals.json",
    "noise_review_jd_Dhanush": ROOT / "reports/noise_review/noise_review_Dhanush.xlsx",
    "noise_review_jd_Lochan": ROOT / "reports/noise_review/noise_review_Lochan.xlsx",
    "noise_review_jd_Priyanka": ROOT / "reports/noise_review/noise_review_Priyanka.xlsx",
    "sample2000_postings": S2K / "extraction_sample_2000.csv",
    "gold_postings_dev": ROOT / "data/gold/gold_postings_dev.csv",
    "system_wordlist": Path("/usr/share/dict/words"),
}
PROTECTED = {  # must be byte-identical after the run (existing reports / frozen snapshots / review workbook)
    "review_workbook": ROOT / f"reports/sprint4_naming/{RUN}/topic_quality_review_v1/sprint4_topic_quality_review.xlsx",
    "p1_topic_review_csv": P1 / "p1_topic_review.csv",
    "p1_topic_review_md": P1 / "p1_topic_review.md",
    "p1_evidence_investigation_md": P1 / "p1_evidence_investigation.md",
    "p1_ai_recommendations_v1": P1 / "p1_ai_recommendations_v1.json",
    **{f"snapshot_{p.name}": p for p in sorted(INP.iterdir()) if p.is_file()},
    "noise_review_decisions_Lochan": ROOT / "reports/noise_review/reviewed_lochan.xlsx",
    "noise_review_decisions_Priyanka": ROOT / "reports/noise_review/noise_review_Priyanka_FINAL.xlsx",
}
EXPECT = {"p1_topics": 20, "p1_skills": 976, "membership_records": 976, "linked_records": 2013,
          "unmapped_aliases": 0, "missing_p1_members": 0, "duplicate_statement_ids": 0}
OUTPUTS = ["p1_extraction_evidence_v2.csv", "p1_skill_evidence_summary_v2.csv", "p1_topic_evidence_summary_v2.csv",
           "p1_evidence_reconciliation_v2.md", "manifest.json"]
STOP = {"and", "the", "for", "with", "of", "to", "in", "on", "a", "an", "or", "as", "is", "are", "be", "by", "at",
        "experience", "knowledge", "skills", "skill", "ability", "strong", "using", "use", "working", "work", "including"}
EXTRACTION_LABEL = "extraction (AI-generated statement; not manually reviewed)"


class InvariantError(SystemExit):
    pass


def check(name, got, want):
    if got != want:
        raise InvariantError(f"INVARIANT FAILED: {name} = {got}, expected {want}")
    return got


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def squash(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def words(s):
    return {w for w in re.findall(r"[a-z0-9+#]+", s.lower()) if w not in STOP and len(w) > 1}


def compact(s):
    return re.sub(r"[^a-z0-9+#]", "", s.lower())


def lexical_match(a, b):
    ca, cb = compact(a), compact(b)
    stems = lambda s: {w[:4] for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) >= 3 and w not in STOP}
    return bool(stems(a) & stems(b)) or (bool(ca) and bool(cb) and (ca in cb or cb in ca))


def short_code(k):
    toks = k.split()
    return (len(toks) == 1 and len(re.sub(r"[^a-z0-9]", "", k)) <= 5) or any(re.search(r"\d", t) and re.search(r"[a-z]", t) for t in toks)


def local_postings():
    """posting_id -> (text, source, title). Texts are contact-masked copies; used only to verify evidence quotes."""
    docs = {}
    for who in ("Dhanush", "Lochan", "Priyanka"):
        f = INPUTS[f"noise_review_jd_{who}"]
        wb = openpyxl.load_workbook(f)
        for row in wb["Job descriptions"].iter_rows(min_row=2):
            url = row[4].hyperlink.target if row[4].hyperlink else ""
            if "linkedin.com/jobs/view/" in url and row[5].value:
                docs.setdefault("li_" + url.rstrip("/").split("/")[-1], (str(row[5].value), str(f.relative_to(ROOT)), row[2].value or ""))
    s = read(INPUTS["sample2000_postings"])
    for pid, t, ti in zip(s.posting_id, s.description, s.title):
        docs.setdefault(pid, (t, str(INPUTS["sample2000_postings"]), ti))
    g = read(INPUTS["gold_postings_dev"])
    for pid, t, ti in zip(g.posting_id, g.description, g.title):
        docs.setdefault(pid, (t, str(INPUTS["gold_postings_dev"].relative_to(ROOT)), ti))
    return docs


def dhanush_markers():
    r = pd.read_excel(INPUTS["noise_review_jd_Dhanush"], "Review", dtype=str, keep_default_na=False)
    return dict(zip(r["skill"], r["suggested by"]))


def main():
    existing = [f for f in OUTPUTS if (OUT / f).exists()]
    if existing:
        raise SystemExit(f"refusing to overwrite {existing} in {OUT}")
    in_hash = {k: sha256(p) for k, p in INPUTS.items()}
    prot_hash = {k: sha256(p) for k, p in PROTECTED.items()}
    snap = json.loads(INPUTS["input_manifest"].read_text())["files_sha256"]
    for f in ("aliases.csv", "memberships.csv", "reference_links.csv"):
        check(f"frozen snapshot {f} sha256 matches its manifest", sha256(INP / f), snap[f])

    pm = read(INPUTS["prepared_mentions"])
    ali = read(INPUTS["aliases"])
    mem = read(INPUTS["memberships"])
    v1 = read(INPUTS["p1_traceability_v1"])
    ref = read(INPUTS["reference_links"]).rename(columns={"score": "ref_score"}).set_index("skill_key")
    ai_v1 = json.loads(INPUTS["p1_remediation_proposals_v1_ai"].read_text())["topics"]
    dict_words = {w.strip().lower() for w in INPUTS["system_wordlist"].read_text(errors="ignore").split()}

    # --- key mapping ---------------------------------------------------------------------------------------
    check("alias_key unique in aliases.csv", int(ali.alias_key.duplicated().sum()), 0)
    check("duplicate_statement_ids", int(pm.statement_id.duplicated().sum()), EXPECT["duplicate_statement_ids"])
    a2s = dict(zip(ali.alias_key, ali.skill_key))
    rule = dict(zip(ali.alias_key, ali.rule))
    unmapped = sorted(set(pm.skill_key) - set(a2s))
    check("unmapped_aliases", len(unmapped), EXPECT["unmapped_aliases"])
    pm["canonical_skill_key"] = pm.skill_key.map(a2s)
    pm["alias_rule"] = pm.skill_key.map(rule)

    p1_topics = sorted(v1.topic_id.unique())
    check("p1_topics", len(p1_topics), EXPECT["p1_topics"])
    p1_skills = set(v1.skill_key)
    check("p1_skills (distinct canonical)", len(p1_skills), EXPECT["p1_skills"])
    m1 = mem[mem.skill_key.isin(p1_skills)]
    check("membership_records matched", len(m1), EXPECT["membership_records"])
    check("membership skill_key unique (one topic per skill)", int(m1.skill_key.duplicated().sum()), 0)
    check("membership topic == v1 topic", int((m1.set_index("skill_key").topic_id != v1.set_index("skill_key").topic_id.reindex(m1.skill_key).values).sum()), 0)
    check("membership topics are the P1 topics", sorted(m1.topic_id.unique()), p1_topics)

    rec = pm[pm.canonical_skill_key.isin(p1_skills)].merge(
        m1.rename(columns={"skill_key": "canonical_skill_key", "state": "membership_state", "score": "membership_score",
                           "margin": "membership_margin"})[["canonical_skill_key", "topic_id", "membership_state", "membership_score", "membership_margin"]],
        on="canonical_skill_key", how="left", validate="m:1")
    check("linked_records", len(rec), EXPECT["linked_records"])
    check("missing_p1_members (no extraction record)", len(p1_skills - set(rec.canonical_skill_key)), EXPECT["missing_p1_members"])
    check("linked statement_id unique", int(rec.statement_id.duplicated().sum()), 0)
    check("linked records without topic", int(rec.topic_id.isna().sum()), 0)

    # Sprint 3 counts cross-check (sprint3_noise.xlsx was built from the same mentions)
    s3 = pd.read_excel(INPUTS["sprint3_noise_workbook"], "Skills", dtype=str, keep_default_na=False).set_index("skill")
    g = rec.groupby("canonical_skill_key").agg(n=("statement_id", "size"), p=("posting_id", "nunique"))
    check("mention counts equal sprint3_noise.xlsx", int((g.n != s3.mentions.reindex(g.index).astype(int)).sum()), 0)
    check("posting counts equal sprint3_noise.xlsx", int((g.p != s3.postings.reindex(g.index).astype(int)).sum()), 0)

    # --- posting-context verification of the evidence quote ----------------------------------------------
    docs = local_postings()
    sq = {pid: squash(t) for pid, (t, _, _) in docs.items()}
    names = dict(zip(v1.topic_id, v1.provisional_name))

    def verify(pid, ev):
        if pid not in docs:
            return "posting_text_unavailable"
        if ev and ev in docs[pid][0]:
            return "verified_exact"
        if ev and squash(ev) in sq[pid]:
            return "verified_normalised_whitespace_case"
        return "not_found_in_local_text"
    rec["evidence_class"] = EXTRACTION_LABEL
    rec["posting_context_check"] = [verify(p, e) for p, e in zip(rec.posting_id, rec.evidence)]
    rec["posting_text_source"] = rec.posting_id.map(lambda p: docs[p][1] if p in docs else "")
    rec["posting_title"] = rec.posting_id.map(lambda p: docs[p][2] if p in docs else "")
    rec["provisional_topic_name"] = rec.topic_id.map(names)
    rec_cols = ["statement_id", "posting_id", "topic_id", "provisional_topic_name", "canonical_skill_key", "membership_state",
                "membership_score", "membership_margin", "skill_key", "alias_rule", "skill", "original_skill", "evidence",
                "original_evidence", "model", "prompt_version", "review_status", "evidence_class", "posting_context_check",
                "posting_text_source", "posting_title"]
    rec = rec[rec_cols].rename(columns={"skill_key": "extraction_skill_key"})
    rec = rec.sort_values(["topic_id", "canonical_skill_key", "posting_id", "statement_id"]).reset_index(drop=True)

    # --- skill level ---------------------------------------------------------------------------------------
    dmark = dhanush_markers()
    v1i = v1.set_index("skill_key")
    ai_sets = {k: {x.split(" ~ ")[0] for t in ai_v1.values() for x in t.get(k, [])}
               for k in ("suspected_extraction_errors", "suspected_clustering_errors", "questionable_reference_links", "normalisation_issues")}
    rows = []
    for k, gr in rec.groupby("canonical_skill_key", sort=False):
        m = m1.set_index("skill_key").loc[k]
        rf = ref.loc[k] if k in ref.index else None
        quotes = list(dict.fromkeys(gr.evidence))
        exp_seen = any(re.search(r"\(\s*" + re.escape(k) + r"s?\s*\)", q, re.I) or re.search(re.escape(k) + r"\s*\(", q, re.I) for q in quotes) if short_code(k) else False
        ctx = [words(q) - words(k) for q in quotes]
        diverge = len(gr.posting_id.unique()) >= 2 and all(not (a & b) for a, b in combinations(ctx, 2)) and all(ctx)
        single = len(k.split()) == 1 and k.isalpha() and k in dict_words
        known_lex = rf is not None and rf["verdict"] == "known_skill" and lexical_match(k, rf["ref_label"])
        ref_flag = rf is not None and rf["verdict"] == "known_skill" and not lexical_match(k, rf["ref_label"])
        reviewer = v1i.at[k, "noise_review_reviewer"]
        prov = ("" if not reviewer else
                f"Sprint 3 noise review by {reviewer}; file marks the decision as suggested by '{dmark.get(k, '')}' (please check)" if reviewer == "Dhanush"
                else f"Sprint 3 noise review by {reviewer}; no AI-suggestion marker in the file")
        pc = Counter(gr.posting_context_check)
        rows.append({
            "topic_id": m.topic_id, "provisional_topic_name": names[m.topic_id], "canonical_skill_key": k,
            "membership_state": m.state, "membership_score": m.score, "membership_margin": m.margin,
            "n_extraction_records": len(gr), "n_postings": gr.posting_id.nunique(),
            "extraction_skill_keys": "; ".join(sorted(gr.extraction_skill_key.unique())),
            "original_skill_forms": "; ".join(sorted(gr.original_skill.unique())[:8]),
            "models": "; ".join(f"{a}={b}" for a, b in Counter(gr.model).most_common()),
            "prompt_versions": "; ".join(sorted(gr.prompt_version.unique())),
            "review_status": "; ".join(sorted(gr.review_status.unique())),
            "evidence_examples": " || ".join(f"{p}: {e}" for p, e in list(dict.fromkeys(zip(gr.posting_id, gr.evidence)))[:3]),
            "n_context_verified": pc["verified_exact"] + pc["verified_normalised_whitespace_case"],
            "n_context_not_found": pc["not_found_in_local_text"], "n_context_text_unavailable": pc["posting_text_unavailable"],
            "ref_verdict": rf["verdict"] if rf is not None else "no_link_row", "ref_source": rf["source"] if rf is not None else "",
            "ref_label": rf["ref_label"] if rf is not None else "", "ref_id": rf["ref_id"] if rf is not None else "",
            "ref_score": rf["ref_score"] if rf is not None else "", "ref_match_type": rf["match"] if rf is not None else "",
            "ref_review_status": rf["review_status"] if rf is not None else "",
            "human_review_decision": v1i.at[k, "noise_review_decision"], "human_review_alias_of": v1i.at[k, "noise_review_alias_of"],
            "human_review_note": v1i.at[k, "noise_review_note"], "human_review_provenance": prov,
            "cand_ambiguous_acronym": short_code(k) and not known_lex and not exp_seen,
            "cand_generic_noun": single and not known_lex,
            "cand_reference_mapping": ref_flag,
            "cand_conflicting_meaning": diverge,
            "ai_v1_suspected_extraction_error": k in ai_sets["suspected_extraction_errors"],
            "ai_v1_suspected_clustering_error": k in ai_sets["suspected_clustering_errors"],
            "ai_v1_questionable_reference": k in ai_sets["questionable_reference_links"],
            "ai_v1_normalisation_issue": k in ai_sets["normalisation_issues"],
        })
    sk = pd.DataFrame(rows)
    flags = ["cand_ambiguous_acronym", "cand_generic_noun", "cand_reference_mapping", "cand_conflicting_meaning"]
    sk["candidate_for_human_review"] = sk[flags].any(axis=1)
    sk["candidate_reasons"] = sk[flags].apply(lambda r: "; ".join(f[5:] for f in flags if r[f]), axis=1)
    sk = sk.sort_values(["topic_id", "membership_state", "canonical_skill_key"]).reset_index(drop=True)
    check("skill summary rows", len(sk), EXPECT["p1_skills"])
    check("skill summary records sum", int(sk.n_extraction_records.sum()), EXPECT["linked_records"])

    # --- topic level ---------------------------------------------------------------------------------------
    tp = []
    for t, gs in sk.groupby("topic_id"):
        gr = rec[rec.topic_id == t]
        tp.append({"topic_id": t, "provisional_topic_name": names[t],
                   "n_skills": len(gs), "n_assigned": int((gs.membership_state == "assigned").sum()), "n_weak": int((gs.membership_state == "weak").sum()),
                   "n_extraction_records": len(gr), "n_postings": gr.posting_id.nunique(),
                   "n_single_posting_skills": int((gs.n_postings == 1).sum()),
                   "n_records_context_verified": int(gr.posting_context_check.str.startswith("verified").sum()),
                   "n_records_context_not_found": int((gr.posting_context_check == "not_found_in_local_text").sum()),
                   "n_records_text_unavailable": int((gr.posting_context_check == "posting_text_unavailable").sum()),
                   "n_human_review_decisions": int((gs.human_review_decision != "").sum()),
                   "n_human_not_a_skill": int((gs.human_review_decision == "not_a_skill").sum()),
                   **{f"n_{f}": int(gs[f].sum()) for f in flags},
                   "n_candidates_for_human_review": int(gs.candidate_for_human_review.sum()),
                   "models": "; ".join(f"{a}={b}" for a, b in Counter(gr.model).most_common())})
    tp = pd.DataFrame(tp)
    check("topic summary rows", len(tp), EXPECT["p1_topics"])
    check("topic summary skills sum", int(tp.n_skills.sum()), EXPECT["p1_skills"])

    # --- write -----------------------------------------------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    rec.to_csv(OUT / OUTPUTS[0], index=False)
    sk.to_csv(OUT / OUTPUTS[1], index=False)
    tp.to_csv(OUT / OUTPUTS[2], index=False)
    ctx = Counter(rec.posting_context_check)
    counts = {
        "p1_topics": len(tp), "p1_skills": len(sk), "membership_records": len(m1), "linked_records": len(rec),
        "unmapped_aliases": len(unmapped), "missing_p1_members": len(p1_skills - set(rec.canonical_skill_key)),
        "duplicate_statement_ids": int(pm.statement_id.duplicated().sum()),
        "prepared_mentions_rows": len(pm), "prepared_mentions_postings": pm.posting_id.nunique(),
        "linked_postings": rec.posting_id.nunique(), "linked_models": dict(Counter(rec.model)),
        "linked_review_status": dict(Counter(rec.review_status)),
        "records_where_evidence_differs_from_original": int((rec.evidence != rec.original_evidence).sum()),
        "records_where_skill_differs_from_original": int((rec.skill != rec.original_skill).sum()),
        "records_via_alias_rule": int((rec.alias_rule != "").sum()),
        "posting_context_check": dict(ctx),
        "skills_with_human_review_decision": int((sk.human_review_decision != "").sum()),
        **{f"skills_{f}": int(sk[f].sum()) for f in flags},
        "skills_candidate_for_human_review": int(sk.candidate_for_human_review.sum()),
        "skills_single_posting": int((sk.n_postings == 1).sum()),
    }
    for k, v in EXPECT.items():
        check(f"final {k}", counts[k], v)
    write_md(rec, sk, tp, counts)
    out_hash = {f: sha256(OUT / f) for f in OUTPUTS[:4]}
    check("inputs unchanged", {k: sha256(p) for k, p in INPUTS.items()}, in_hash)
    check("protected files unchanged", {k: sha256(p) for k, p in PROTECTED.items()}, prot_hash)
    manifest = {
        "schema": "p1_evidence_reconciliation/2", "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": "src/reconcile_p1_evidence.py", "script_sha256": sha256(__file__),
        "python": sys.version.split()[0], "pandas": pd.__version__, "platform": platform.platform(),
        "clustering_run_id": RUN, "read_only": True, "api_calls": "none", "database": "not accessed",
        "inputs": {k: {"path": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p), "sha256": in_hash[k]} for k, p in INPUTS.items()},
        "protected_unchanged": {k: {"path": str(p.relative_to(ROOT)), "sha256": prot_hash[k]} for k, p in PROTECTED.items()},
        "expected": EXPECT, "counts": counts, "outputs": {f: {"sha256": h} for f, h in out_hash.items()},
        "candidate_rules": {
            "cand_ambiguous_acronym": "one token of <=5 alphanumerics or a token mixing letters and digits; no confident lexically matching reference link; no '(KEY)' / 'KEY (' expansion pattern in any evidence quote",
            "cand_generic_noun": "single alphabetic token found in /usr/share/dict/words, without a confident lexically matching reference link",
            "cand_reference_mapping": "known_skill reference link whose label shares no 4-letter word stem with the skill and neither compact string contains the other",
            "cand_conflicting_meaning": ">=2 postings and no two evidence quotes share a content word besides the skill's own words",
        },
        "labels": {"extraction": EXTRACTION_LABEL, "posting_context": "verbatim quote check against contact-masked local posting text; confirms the quote exists, not its meaning",
                   "human_review": "Sprint 3 noise-review decisions (weak members only), provenance as marked in each file",
                   "ai_v1": "copied from p1_remediation_proposals.json (AI-generated, not human-validated)"},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: counts[k] for k in list(EXPECT) + ["posting_context_check", "skills_candidate_for_human_review"]}, indent=1))
    print(f"wrote {len(OUTPUTS)} files to {OUT.relative_to(ROOT)}")


def write_md(rec, sk, tp, c):
    flags = ["cand_ambiguous_acronym", "cand_generic_noun", "cand_reference_mapping", "cand_conflicting_meaning"]
    ctx = c["posting_context_check"]
    L = ["# Sprint 4 — P1 evidence reconciliation v2", "",
         "> Read-only. Every extraction record is **AI-generated** (model column) and **not manually reviewed** "
         f"(review_status = {', '.join(c['linked_review_status'])}). Flags below are **candidates for human review**, not confirmed errors. "
         "Nothing was renamed, merged, split, reassigned or excluded.", "",
         "## Validation", "", "| Check | Expected | Observed |", "|---|---|---|"]
    L += [f"| {k} | {v} | {c[k]} |" for k, v in EXPECT.items()]
    L += ["", "Also checked: alias_key unique; frozen snapshot hashes equal its manifest; one topic per P1 skill and it equals the v1 topic; "
          "per-skill mention and posting counts equal `reports/sprint3_noise.xlsx`; inputs and protected files byte-identical after the run.", "",
          "## Evidence classes", "", "| Class | What it proves | Records / skills |", "|---|---|---|",
          f"| Extraction | an AI extractor ({', '.join(f'{k} {v}' for k, v in c['linked_models'].items())}) produced this skill with this quote | {c['linked_records']} records, {c['linked_postings']} postings |",
          f"| Posting context, verified | the quote occurs in a local copy of that posting (contact-masked) | {ctx.get('verified_exact', 0) + ctx.get('verified_normalised_whitespace_case', 0)} records ({ctx.get('verified_normalised_whitespace_case', 0)} after whitespace/case normalisation) |",
          f"| Posting context, not found | local text exists but the quote is not in it (masking or paraphrase) | {ctx.get('not_found_in_local_text', 0)} records |",
          f"| Posting text unavailable | no local copy of that posting | {ctx.get('posting_text_unavailable', 0)} records |",
          f"| Human review | Sprint 3 noise-review decision (weak members only) | {c['skills_with_human_review_decision']} skills |",
          "", f"Evidence corrections: {c['records_where_evidence_differs_from_original']} records differ from original_evidence and "
          f"{c['records_where_skill_differs_from_original']} from original_skill. Records reached through a normalisation rule: {c['records_via_alias_rule']}. "
          f"{c['skills_single_posting']} of {c['p1_skills']} P1 skills occur in exactly one posting.", "",
          "## Candidates for human review (rule-based)", "", "| Flag | Skills | Rule |", "|---|---|---|"]
    rules = {"cand_ambiguous_acronym": "short code, no matching confident link, no expansion in any quote",
             "cand_generic_noun": "single dictionary word, no matching confident link",
             "cand_reference_mapping": "confident link label shares no word with the skill",
             "cand_conflicting_meaning": "≥2 postings whose quotes share no content word"}
    L += [f"| {f[5:]} | {c['skills_' + f]} | {rules[f]} |" for f in flags]
    L += [f"| any of the above | {c['skills_candidate_for_human_review']} | — |", "",
          "## Topics", "", "| Topic | Name | Skills (a/w) | Records | Postings | Context verified | Human decisions | Acronym | Generic | Ref map | Conflict | Any |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    L += [f"| {r.topic_id} | {r.provisional_topic_name} | {r.n_skills} ({r.n_assigned}/{r.n_weak}) | {r.n_extraction_records} | {r.n_postings} | "
          f"{r.n_records_context_verified} | {r.n_human_review_decisions} | {r.n_cand_ambiguous_acronym} | {r.n_cand_generic_noun} | "
          f"{r.n_cand_reference_mapping} | {r.n_cand_conflicting_meaning} | {r.n_candidates_for_human_review} |" for r in tp.itertuples()]
    L += ["", "## Examples per flag (first 12 by postings)", ""]
    for f in flags:
        x = sk[sk[f]].sort_values("n_postings", ascending=False).head(12)
        L.append(f"- **{f[5:]}:** " + "; ".join(f"{r.canonical_skill_key} ({r.topic_id}, {r.n_postings}p)" for r in x.itertuples()))
    L += ["", "## Files", "", "- `p1_extraction_evidence_v2.csv` — one row per linked extraction record (statement_id unique).",
          "- `p1_skill_evidence_summary_v2.csv` — one row per P1 skill: evidence, reference link, human review, candidate flags, AI v1 flags (separate columns).",
          "- `p1_topic_evidence_summary_v2.csv` — one row per P1 topic.", "- `manifest.json` — input / output / protected-file hashes, counts, rules."]
    (OUT / "p1_evidence_reconciliation_v2.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
