"""P1 evidence traceability: posting -> statement -> normalised skill -> membership -> topic (read-only).

    .venv/bin/python src/build_p1_traceability.py            # writes p1_evidence_traceability.csv
    (then, once p1_remediation_proposals.json exists, the same command also writes p1_evidence_investigation.md)

Uses only files already on disk (no API, no Supabase). Evidence sources, strongest first:
  extraction   the extractor's own evidence quote for this skill in a real posting
               (a) Sprint 3 noise-review workbooks: bold-red span in the full JD (weak members only)
               (b) sample2000 Qwen v3 statements export (87 extracted postings)
  text_match   the member string occurs in a locally available posting text, but there is NO extraction
               record linking that posting to the skill (string occurrence only)
Source evidence and AI output are kept apart: this script writes evidence + deterministic rule flags only;
AI diagnoses / remediation live in p1_remediation_proposals.json (hand-written, AI-generated).
"""
import hashlib
import json
import re
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN = "hdbscan_10_umap10_ms1_2026-10-23"
INP = ROOT / f"data/processed/sprint4_input_{RUN}"
OUT = ROOT / f"reports/sprint4_naming/{RUN}/topic_quality_review_v1/p1_review"
S2K = Path("/Users/lochan/Downloads/sample2000_qwen_v3_2026-10-21_1545")
NOISE_FILES = {  # reviewer -> file holding that reviewer's decisions (latest version on disk)
    "Dhanush": ROOT / "reports/noise_review/noise_review_Dhanush.xlsx",
    "Lochan": ROOT / "reports/noise_review/reviewed_lochan.xlsx",
    "Priyanka": ROOT / "reports/noise_review/noise_review_Priyanka_FINAL.xlsx",
}
JD_FILES = {  # original generated workbooks: the bold-red evidence spans survive here (re-saved copies lost them)
    "Dhanush": ROOT / "reports/noise_review/noise_review_Dhanush.xlsx",
    "Lochan": ROOT / "reports/noise_review/noise_review_Lochan.xlsx",
    "Priyanka": ROOT / "reports/noise_review/noise_review_Priyanka.xlsx",
}
SOURCES = {
    "p1_topic_review": OUT / "p1_topic_review.csv",
    "memberships": INP / "memberships.csv",
    "aliases": INP / "aliases.csv",
    "reference_links": INP / "reference_links.csv",
    "sprint3_noise_workbook": ROOT / "reports/sprint3_noise.xlsx",
    **{f"noise_review_{k}": v for k, v in NOISE_FILES.items()},
    **{f"noise_review_jd_{k}": v for k, v in JD_FILES.items()},
    "sample2000_statements": S2K / "statements_qwen_qwen3.8-27b_sample2000_v3.csv",
    "sample2000_postings": S2K / "extraction_sample_2000.csv",
    "gold_postings_dev": ROOT / "data/gold/gold_postings_dev.csv",
}
WORKBOOK = ROOT / f"reports/sprint4_naming/{RUN}/topic_quality_review_v1/sprint4_topic_quality_review.xlsx"
PROPOSALS = OUT / "p1_remediation_proposals.json"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
STOP = {"and", "the", "for", "with", "of", "to", "in", "on", "a", "an", "or", "use", "using", "types"}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def mask(s):
    return PHONE.sub("[phone]", EMAIL.sub("[email]", s))


def norm_key(s):  # same as normalize_aliases.rule1 + lower-casing used when skill_key was made
    s = re.sub(r"[‐-―-]+", " ", str(s).lower())
    return re.sub(r"\s+", " ", s).strip().rstrip(".,;").strip()


def snippet(text, start, end, pad=90):
    a, b = max(0, start - pad), min(len(text), end + pad)
    return mask(("…" if a else "") + text[a:start] + "[[" + text[start:end] + "]]" + text[end:b] + ("…" if b < len(text) else ""))


def stems(s):
    return {w[:4] for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) >= 3 and w not in STOP}


def compact(s):
    return re.sub(r"[^a-z0-9+#]", "", s.lower())


def lexical_match(k, label):
    """Rule: link shares a word stem with the label, or one compact string contains the other (c++ ~ C++)."""
    a, b = compact(k), compact(label)
    return bool(stems(k) & stems(label)) or (bool(a) and bool(b) and (a in b or b in a))


def short_code(k):
    """Rule: candidate acronym / code = one token (allowing / & . +) of <= 5 chars, or a token with digits."""
    toks = k.split()
    return (len(toks) == 1 and len(re.sub(r"[^a-z0-9]", "", k)) <= 5) or any(re.search(r"\d", t) and re.search(r"[a-z]", t) for t in toks)


def load_noise_reviews():
    """Per weak skill: reviewer decisions and the example posting with the extractor's evidence span."""
    dec, ev, docs = {}, {}, {}
    for who, f in NOISE_FILES.items():
        r = pd.read_excel(f, "Review", dtype=str, keep_default_na=False)
        for s, d, a, n in zip(r["skill"], r["DECISION"], r["alias of (if alias)"], r["note"]):
            dec[s] = {"reviewer": who, "decision": d, "alias_of": a, "note": n, "file": str(f.relative_to(ROOT))}
        f = JD_FILES[who]
        ws = openpyxl.load_workbook(f, rich_text=True)["Job descriptions"]
        for row in ws.iter_rows(min_row=2):
            skill, title, comp, link, jd = (row[i].value for i in (1, 2, 3, 4, 5))
            if not skill or jd is None:
                continue
            url = row[4].hyperlink.target if row[4].hyperlink else ""
            pid = "li_" + url.rstrip("/").split("/")[-1] if "linkedin.com/jobs/view/" in url else ""
            text = str(jd)
            spans = []
            if not isinstance(jd, str):
                pos = 0
                for blk in jd:
                    t = blk if isinstance(blk, str) else blk.text
                    if not isinstance(blk, str) and blk.font is not None and blk.font.b:
                        spans.append((pos, pos + len(t)))
                    pos += len(t)
            ev[str(skill)] = {"posting_id": pid, "title": title, "company": comp, "url": url,
                              "snippets": [snippet(text, a, b) for a, b in spans[:3]],
                              "evidence_quotes": [text[a:b] for a, b in spans[:3]], "file": str(f.relative_to(ROOT))}
            if pid:
                docs[pid] = (text, f"{f.relative_to(ROOT)} [Job descriptions]", title, comp)
    return dec, ev, docs


def main():
    before = {k: sha256(p) for k, p in SOURCES.items()}
    wb_before = sha256(WORKBOOK)
    p1 = pd.read_csv(SOURCES["p1_topic_review"], dtype=str, keep_default_na=False)
    topics = dict(zip(p1.topic_id, p1.provisional_name))
    mem = pd.read_csv(SOURCES["memberships"], dtype=str, keep_default_na=False)
    mem = mem[mem.topic_id.isin(topics)].copy()
    ali = pd.read_csv(SOURCES["aliases"], dtype=str, keep_default_na=False)
    alias_of = ali.groupby("skill_key").apply(lambda g: [(a, r) for a, r in zip(g.alias_key, g.rule)], include_groups=False).to_dict()
    akey2skill = dict(zip(ali.alias_key, ali.skill_key))
    ref = pd.read_csv(SOURCES["reference_links"], dtype=str, keep_default_na=False).set_index("skill_key")
    cnt = pd.read_excel(SOURCES["sprint3_noise_workbook"], "Skills", dtype=str, keep_default_na=False).set_index("skill")
    dec, nev, docs = load_noise_reviews()

    st = pd.read_csv(SOURCES["sample2000_statements"], dtype=str, keep_default_na=False)
    st["skill_key"] = st.skill.map(norm_key).map(lambda k: akey2skill.get(k, k))
    posts = pd.read_csv(SOURCES["sample2000_postings"], dtype=str, keep_default_na=False)
    for pid, t, ti, co in zip(posts.posting_id, posts.description, posts.title, posts.company_name):
        docs.setdefault(pid, (t, str(SOURCES["sample2000_postings"]), ti, co))
    gold = pd.read_csv(SOURCES["gold_postings_dev"], dtype=str, keep_default_na=False)
    for pid, t, ti, co in zip(gold.posting_id, gold.description, gold.title, gold.company_name):
        docs.setdefault(pid, (t, str(SOURCES["gold_postings_dev"].relative_to(ROOT)), ti, co))
    low = {pid: v[0].lower() for pid, v in docs.items()}
    s2k_titles = dict(zip(posts.posting_id, posts.title))

    rows = []
    for r in mem.sort_values(["topic_id", "state", "score"], ascending=[True, True, False]).itertuples():
        k = r.skill_key
        ev = []  # (evidence_type, posting_id, title, snippet, source_file)
        if k in nev and nev[k]["snippets"]:
            e = nev[k]
            ev += [("extraction", e["posting_id"], e["title"], s, e["file"] + " [Job descriptions, bold-red span]") for s in e["snippets"][:1]]
        for x in st[st.skill_key == k].head(3).itertuples():
            ev.append(("extraction", x.posting_id, s2k_titles.get(x.posting_id, ""),
                       mask(f"skill='{x.skill}' evidence='{x.evidence}' (evidence_in_text={x.evidence_in_text})"),
                       str(SOURCES["sample2000_statements"])))
        n_text = 0
        terms = sorted({k} | {a for a, _ in alias_of.get(k, [])}, key=len, reverse=True)
        pats = [re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])") for t in terms]
        have = {e[1] for e in ev}
        for pid, t in low.items():
            if not any(term in t for term in terms):
                continue
            m = next((m for p in pats for m in [p.search(t)] if m), None)
            if not m:
                continue
            n_text += 1
            if pid not in have and sum(e[0] == "text_match" for e in ev) < 3 and len(ev) < 3:
                text, src, ti, _ = docs[pid]
                ev.append(("text_match", pid, ti, snippet(text, m.start(), m.end()), src))
        n_ext = sum(e[0] == "extraction" for e in ev)
        ev_level = "extraction_snippet" if n_ext else ("text_match_only" if ev else "unavailable")
        rf = ref.loc[k] if k in ref.index else None
        lexical = lexical_match(k, rf["ref_label"]) if rf is not None and rf["ref_label"] else None
        c = cnt.loc[k] if k in cnt.index else None
        d = dec.get(k, {})
        row = {
            "topic_id": r.topic_id, "provisional_name": topics[r.topic_id],
            "skill_key": k, "membership_state": r.state, "membership_score": r.score, "membership_margin": r.margin,
            "original_strings_normalised_into_this_key": "; ".join(f"{a}" + (f" [{ru}]" if ru else "") for a, ru in alias_of.get(k, [])) or "unavailable",
            "original_surface_form_casing": "; ".join(sorted(set(st[st.skill_key == k].skill))[:5]) or "unavailable (statements not on disk)",
            "posting_count": c["postings"] if c is not None else "unavailable",
            "mention_count": c["mentions"] if c is not None else "unavailable",
            "library_skill": c["library_skill"] if c is not None else "unavailable",
            "skill_type_sprint3": c["skill_type"] if c is not None else "unavailable",
            "evidence_level": ev_level,
            "n_postings_with_string_occurrence_local": n_text,
        }
        for i in range(3):
            e = ev[i] if i < len(ev) else ("", "", "", "", "")
            row.update({f"ev{i+1}_type": e[0], f"ev{i+1}_posting_id": e[1], f"ev{i+1}_title": e[2],
                        f"ev{i+1}_snippet": e[3], f"ev{i+1}_source_file": e[4]})
        row.update({
            "ref_verdict": rf["verdict"] if rf is not None else "unavailable",
            "ref_source": rf["source"] if rf is not None else "", "ref_label": rf["ref_label"] if rf is not None else "",
            "ref_id": rf["ref_id"] if rf is not None else "", "ref_score": rf["score"] if rf is not None else "",
            "ref_match_type": rf["match"] if rf is not None else "", "ref_review_status": rf["review_status"] if rf is not None else "",
            "noise_review_reviewer": d.get("reviewer", ""), "noise_review_decision": d.get("decision", ""),
            "noise_review_alias_of": d.get("alias_of", ""), "noise_review_note": d.get("note", ""),
            "noise_review_file": d.get("file", ""),
            # deterministic rule flags (not AI judgments)
            "rule_short_code_candidate": short_code(k),
            "rule_ambiguous_acronym": short_code(k) and not (rf is not None and rf["verdict"] == "known_skill" and lexical),
            "rule_ref_link_no_shared_word": (rf is not None and rf["verdict"] == "known_skill" and lexical is False),
            "rule_reviewer_not_a_skill": d.get("decision") == "not_a_skill",
            "evidence_sufficient_to_disambiguate": ("unavailable - no posting evidence on disk" if ev_level == "unavailable"
                                                    else "insufficient - string occurrence only, no extraction record" if ev_level == "text_match_only"
                                                    else "extraction snippet available - human must read it"),
        })
        rows.append(row)
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "p1_evidence_traceability.csv", index=False)
    stats = {
        "skills_traced": len(df), "unique_skills": df.skill_key.nunique(),
        "assigned": int((df.membership_state == "assigned").sum()), "weak": int((df.membership_state == "weak").sum()),
        "traced_to_count_ref_alias": int(((df.posting_count != "unavailable") & (df.ref_verdict != "unavailable")).sum()),
        "with_extraction_evidence": int((df.evidence_level == "extraction_snippet").sum()),
        "with_text_match_only": int((df.evidence_level == "text_match_only").sum()),
        "missing_source_evidence": int((df.evidence_level == "unavailable").sum()),
        "rule_ambiguous_acronym": int(df.rule_ambiguous_acronym.sum()),
        "rule_reviewer_not_a_skill": int(df.rule_reviewer_not_a_skill.sum()),
        "rule_ref_link_no_shared_word": int(df.rule_ref_link_no_shared_word.sum()),
        "known_skill_links": int((df.ref_verdict == "known_skill").sum()),
        "weak_with_noise_review_decision": int((df.noise_review_decision != "").sum()),
    }
    print(json.dumps(stats, indent=1))
    assert before == {k: sha256(p) for k, p in SOURCES.items()} and wb_before == sha256(WORKBOOK), "a source changed"
    if PROPOSALS.exists():
        write_md(df, stats, json.loads(PROPOSALS.read_text()), before)


def write_md(df, stats, prop, hashes):
    from datetime import datetime, timezone
    T = prop["topics"]
    keys = {"ai_suspected_extraction_errors": "suspected_extraction_errors", "ai_suspected_clustering_errors": "suspected_clustering_errors",
            "ai_wrong_reference_links": "questionable_reference_links", "ai_normalisation_issues": "normalisation_issues"}
    prop["counts"] = {k: sum(len(t.get(v, [])) for t in T.values()) for k, v in keys.items()}
    known = set(df.skill_key)
    bad = [x for t in T.values() for v in keys.values() for x in t.get(v, []) if x.split(" ~ ")[0] not in known]
    assert not bad, f"AI lists name skills that are not P1 members: {bad}"
    L = ["# Sprint 4 — P1 evidence investigation (20 topics)", "",
         "> Read-only investigation. Source evidence comes from files on disk (`p1_evidence_traceability.csv`). "
         "**Diagnoses and remediation proposals are AI-generated (Claude Code) and NOT human-validated** — they live in "
         "`p1_remediation_proposals.json`. Nothing was deleted, split, merged, renamed or reassigned.", "",
         f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `src/build_p1_traceability.py`.", "",
         "## 1. Data lineage found", "",
         "| Step | Where it lives | Available here? |", "|---|---|---|"]
    L += [f"| {a} | {b} | {c} |" for a, b, c in prop["lineage"]]
    L += ["", "## 2. Headline counts", "", "| Measure | Count | Basis |", "|---|---|---|",
          f"| Member skills traced (P1 memberships) | {stats['skills_traced']} ({stats['assigned']} assigned, {stats['weak']} weak) | memberships.csv |",
          f"| Traced to posting count + reference link + alias rows | {stats['traced_to_count_ref_alias']} | sprint3_noise.xlsx, reference_links.csv, aliases.csv |",
          f"| With original posting evidence (extractor quote) | {stats['with_extraction_evidence']} | noise-review JDs / sample2000 statements |",
          f"| String occurrence in a local posting only (no extraction record) | {stats['with_text_match_only']} | text search; NOT extraction evidence |",
          f"| Missing source evidence | {stats['missing_source_evidence']} | — |",
          f"| Ambiguous acronyms / codes (rule) | {stats['rule_ambiguous_acronym']} | short code and no lexically matching confident link |",
          f"| Suspected extraction errors — confirmed by a Sprint 3 noise reviewer (`not_a_skill`) | {stats['rule_reviewer_not_a_skill']} | noise-review decision |",
          f"| Suspected extraction errors — AI-flagged (assigned + weak) | {prop['counts']['ai_suspected_extraction_errors']} | AI reading, see JSON |",
          f"| Suspected clustering errors — AI-flagged members | {prop['counts']['ai_suspected_clustering_errors']} | AI reading, see JSON |",
          f"| Questionable ESCO/O*NET matches (rule: confident link shares no word with label) | {stats['rule_ref_link_no_shared_word']} of {stats['known_skill_links']} confident links | rule |",
          f"| Questionable ESCO/O*NET matches — AI-confirmed wrong after reading | {prop['counts']['ai_wrong_reference_links']} | AI reading, see JSON |",
          f"| Normalisation issues — AI-flagged (variants not merged) | {prop['counts']['ai_normalisation_issues']} | AI reading, see JSON |",
          "", "Remediation proposals (AI-generated, not human-validated):", "", "| Proposal | Topics |", "|---|---|"]
    rc = pd.Series([t["remediation"] for t in T.values()]).value_counts()
    L += [f"| {k} | {int(rc.get(k, 0))} |" for k in ["RETAIN_PENDING_REVIEW", "RENAME_PENDING_REVIEW", "INVESTIGATE_MEMBER_REASSIGNMENT",
                                                     "INVESTIGATE_TOPIC_SPLIT", "INVESTIGATE_TOPIC_EXCLUSION", "NEEDS_SOURCE_EVIDENCE"]]
    L += ["", "| Topic | Name | Members (a/w) | Extraction evidence | Text only | None | Ambig. codes (rule) | Reviewer not_a_skill | Diagnosis (AI) | Remediation (AI) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for t, g in df.groupby("topic_id", sort=False):
        p = T[t]
        L.append(f"| {t} | {g.provisional_name.iat[0]} | {(g.membership_state=='assigned').sum()}/{(g.membership_state=='weak').sum()} | "
                 f"{(g.evidence_level=='extraction_snippet').sum()} | {(g.evidence_level=='text_match_only').sum()} | {(g.evidence_level=='unavailable').sum()} | "
                 f"{g.rule_ambiguous_acronym.sum()} | {g.rule_reviewer_not_a_skill.sum()} | {', '.join(p['diagnosis'])} | {p['remediation']} |")
    L += ["", "Diagnosis codes: A extraction error · B normalisation error · C ambiguous, needs context · D clustering error · "
          "E incorrect reference link · F insufficient evidence.", "", "## 3. Evidence gaps", ""] + [f"- {x}" for x in prop["evidence_gaps"]]
    L += ["", "## 4. Per-topic findings", ""]
    for t, g in df.groupby("topic_id", sort=False):
        p = T[t]
        a = g[g.membership_state == "assigned"]
        L += [f"### {t} — {g.provisional_name.iat[0]}", "",
              f"Members {len(a)} assigned / {len(g)-len(a)} weak · extraction evidence {(g.evidence_level=='extraction_snippet').sum()} · "
              f"string-only {(g.evidence_level=='text_match_only').sum()} · none {(g.evidence_level=='unavailable').sum()} · "
              f"rule-ambiguous codes {g.rule_ambiguous_acronym.sum()} · reviewer not_a_skill {g.rule_reviewer_not_a_skill.sum()} · "
              f"confident links with no shared word {g.rule_ref_link_no_shared_word.sum()}", "",
              "**Confirmed observations (from source files):**", ""] + [f"- {x}" for x in p["confirmed_observations"]]
        L += ["", "**AI interpretation (not human-validated):**", ""] + [f"- {x}" for x in p["ai_interpretation"]]
        for lab, key in (("Suspected extraction errors", "suspected_extraction_errors"), ("Suspected clustering errors (member does not fit topic)", "suspected_clustering_errors"),
                         ("Questionable reference links", "questionable_reference_links"), ("Normalisation issues", "normalisation_issues")):
            if p.get(key):
                L.append(f"- *{lab} (AI):* {', '.join(p[key])}")
        L += ["", f"**Diagnosis (AI):** {', '.join(p['diagnosis'])} · **Remediation (AI):** `{p['remediation']}`", "",
              f"*Why:* {p['remediation_reason']}", ""]
        top = g.sort_values("posting_count", key=lambda s: pd.to_numeric(s, errors="coerce"), ascending=False).head(8)
        L += ["Highest-posting members:", "", "| Skill | State | Postings | Evidence | Reference (verdict → label) | Reviewer |", "|---|---|---|---|---|---|"]
        L += [f"| {r.skill_key} | {r.membership_state} | {r.posting_count} | {r.evidence_level} | {r.ref_verdict} → {r.ref_label} | {r.noise_review_decision or '—'} |"
              for r in top.itertuples()]
        L.append("")
    L += ["## 5. Verification", ""] + [f"- {x}" for x in prop.get("verification", [])]
    L += ["", "Source sha256 (unchanged before/after this run):", ""] + [f"- `{k}` {v}" for k, v in hashes.items()]
    (OUT / "p1_evidence_investigation.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote p1_evidence_investigation.md")


if __name__ == "__main__":
    main()
