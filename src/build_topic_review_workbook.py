"""Build the Sprint 4 topic quality review workbook (read-only over existing outputs; no API calls).

    .venv/bin/python src/build_topic_review_workbook.py

Reads the assembled 374-topic naming result plus Sprint 4 feature / input snapshots and the
topic-validity screening, and writes an Excel workbook for human review of the flagged topics.
Every evidence value is copied from a source file; nothing is re-computed except joins,
the review-priority bucket (rules documented in the workbook) and the reference-link status
label (a threshold on the existing coverage_any value). Reviewer fields are left blank.
"""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
RUN = "hdbscan_10_umap10_ms1_2026-10-23"
NAMING = ROOT / f"data/processed/sprint4_naming_{RUN}"
ASSEMBLY = NAMING / "assembled_topic_naming_v1_20261104T003642Z"
FEAT = ROOT / f"data/processed/sprint4_features_{RUN}"
INP = ROOT / f"data/processed/sprint4_input_{RUN}"
VALID = NAMING / "validity_v1_topic_naming_v1_qwen_qwen3.8-27b_pilot_20261103T210409Z"
OUT_DIR = ROOT / f"reports/sprint4_naming/{RUN}/topic_quality_review_v1"
OUT = OUT_DIR / "sprint4_topic_quality_review.xlsx"

SOURCES = {
    "assembled_results": ASSEMBLY / "results.csv",
    "assembled_manifest": ASSEMBLY / "manifest.json",
    "topic_features": FEAT / "topic_features.csv",
    "representative_skills": FEAT / "representative_skills.csv",
    "similar_topic_pairs": FEAT / "similar_topic_pairs.csv",
    "topic_neighbors": FEAT / "topic_neighbors.csv",
    "reference_summary": FEAT / "reference_summary.csv",
    "topic_centroids": FEAT / "topic_centroids.npy",
    "features_manifest": FEAT / "manifest.json",
    "input_manifest": INP / "manifest.json",
    "topic_validity_all": VALID / "topic_validity_all.csv",
    "validity_summary": VALID / "validity_summary.json",
}
LOW_REF_COVERAGE = 0.30  # same constant as src/topic_naming.py (info flag low_reference_coverage)
DECISIONS = ["KEEP", "RENAME", "INVESTIGATE_CLUSTER", "POTENTIAL_MERGE", "UNSURE"]
PRIORITY_RULES = [
    (1, "P1 low_cohesion + near_duplicate_topic + llm_confidence low"),
    (2, "P2 other low_cohesion"),
    (3, "P3 near_duplicate_topic"),
    (4, "P4 generic_name / duplicate_name / near_duplicate_name"),
    (5, "P5 other flags (no_reference_link, weak_exceeds_assigned, llm_confidence_low, name checks)"),
]
REVIEW_COLS = ["Reviewer decision", "Proposed corrected name", "Reviewer notes", "Reviewer ID", "Review timestamp"]

FONT, BOLD = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
EVID_HEAD = PatternFill("solid", fgColor="D9E1F2")
REVIEW_HEAD = PatternFill("solid", fgColor="FFE699")
REVIEW_CELL = PatternFill("solid", fgColor="FFF9E5")
HIGH_ROW = PatternFill("solid", fgColor="F8CBAD")
WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def tokens(s):
    return [t for t in s.split(";") if t]


def priority(reason, conf):
    t = set(tokens(reason))
    names = any(x == "generic_name" or x.startswith(("duplicate_name:", "near_duplicate_name:")) for x in t)
    if "low_cohesion" in t and "near_duplicate_topic" in t and conf == "low":
        return PRIORITY_RULES[0][1]
    if "low_cohesion" in t:
        return PRIORITY_RULES[1][1]
    if "near_duplicate_topic" in t:
        return PRIORITY_RULES[2][1]
    if names:
        return PRIORITY_RULES[3][1]
    return PRIORITY_RULES[4][1]


def ref_status(cov, n_conf, n_assigned):
    c = float(cov)
    label = "no confident link" if c == 0 else f"low coverage (<{LOW_REF_COVERAGE:.0%})" if c < LOW_REF_COVERAGE else "linked"
    return f"{label}: {n_conf}/{n_assigned} assigned skills confidently linked ({c:.0%})"


def build_frames():
    res = read(SOURCES["assembled_results"])
    feat = read(SOURCES["topic_features"])
    refs = read(SOURCES["reference_summary"])
    reps = read(SOURCES["representative_skills"])
    pairs = read(SOURCES["similar_topic_pairs"])
    val = read(SOURCES["topic_validity_all"])

    reps = reps.assign(rank_i=reps["rank"].astype(int)).sort_values(["topic_id", "rank_i"])
    rep_txt = reps.groupby("topic_id").apply(
        lambda g: "; ".join(f"{k} ({float(c):.3f})" for k, c in zip(g.skill_key, g.cosine)), include_groups=False)
    dup = {}
    for a, b, c in zip(pairs.topic_a, pairs.topic_b, pairs.cosine):
        dup.setdefault(a, []).append((b, float(c)))
        dup.setdefault(b, []).append((a, float(c)))
    for r in res.itertuples():  # name-level duplicates recorded by the naming stage
        for f in tokens(r.name_flags):
            if f.startswith(("duplicate_name:", "near_duplicate_name:")):
                dup.setdefault(r.topic_id, []).append((f"{f.split(':')[1]} (name)", None))

    def dup_txt(t):
        out = []
        for o, c in sorted(dup.get(t, []), key=lambda x: -(x[1] or 0)):
            s = o if c is None else f"{o} ({c:.3f})"
            if s not in out:
                out.append(s)
        return "; ".join(out)

    m = res.merge(feat, on="topic_id", how="left", validate="1:1", suffixes=("", "_feat")) \
           .merge(refs, on="topic_id", how="left", validate="1:1", suffixes=("", "_ref")) \
           .merge(val[["topic_id", "validity_auto", "validity_auto_reason", "validity_review", "hierarchy_treatment"]],
                  on="topic_id", how="left", validate="1:1")
    assert len(m) == 374 and m.topic_id.is_unique and m.cos_mean.ne("").all() and m.coverage_any.ne("").all()

    rows = pd.DataFrame({
        "Topic ID": m.topic_id,
        "Provisional name": m.provisional_name,
        "Description": m.description,
        "Source provider and model": m.source_provider + " / " + m.source_model,
        "Model confidence": m.llm_confidence,
        "Model confidence reason": m.llm_confidence_reason,
        "Review flags": m.review_reason,
        "Topic quality flags": m.topic_quality_flags,
        "Name flags": m.name_flags,
        "Assigned member count": m.n_assigned.astype(int),
        "Weak member count": m.n_weak.astype(int),
        "Cohesion metric (cos_mean)": m.cos_mean.astype(float),
        "Cohesion min (cos_min)": m.cos_min.astype(float),
        "Transversal topic": m.is_transversal,
        "Representative skills (cosine to centroid)": m.topic_id.map(rep_txt).fillna(""),
        "LLM supporting skills": m.supporting_skills,
        "Reference-link status": [ref_status(c, n, a) for c, n, a in zip(m.coverage_any, m.n_confident, m.n_assigned)],
        "Reference link types": m.link_types,
        "Potential duplicate topic IDs": m.topic_id.map(dup_txt),
        "Validity screening (auto rules)": m.validity_auto,
        "Validity screening reason": m.validity_auto_reason,
        "Validity AI-proposed review (not human)": m.validity_review,
        "Hierarchy treatment (screening)": m.hierarchy_treatment,
        "Review required": m.review_required,
        "Review priority": [priority(r, c) if q == "true" else "" for r, c, q in
                            zip(m.review_reason, m.llm_confidence, m.review_required)],
        "Source run ID": m.source_run_id,
        "Human validated (source)": m.human_validated,
    })
    queue = rows[rows["Review required"] == "true"].copy()
    queue["_p"] = queue["Review priority"].str[1].astype(int)
    queue = queue.sort_values(["_p", "Cohesion metric (cos_mean)", "Topic ID"]).drop(columns="_p")

    name = dict(zip(res.topic_id, res.provisional_name))
    flags = dict(zip(res.topic_id, res.review_reason))
    dpairs = pd.DataFrame({
        "Topic A": pairs.topic_a, "Topic B": pairs.topic_b,
        "Centroid cosine similarity": pairs.cosine.astype(float),
        "Evidence type": "centroid cosine >= 0.90 (similar_topic_pairs.csv)",
        "Transversal involved": pairs.transversal_involved,
        "Name A": pairs.topic_a.map(name), "Name B": pairs.topic_b.map(name),
        "Review flags A": pairs.topic_a.map(flags), "Review flags B": pairs.topic_b.map(flags),
        "Representative skills A": pairs.topic_a.map(rep_txt), "Representative skills B": pairs.topic_b.map(rep_txt),
    })
    seen, extra = set(), []
    for r in res.itertuples():
        for f in tokens(r.name_flags):
            if f.startswith(("duplicate_name:", "near_duplicate_name:")):
                kind, other = f.split(":")
                key = tuple(sorted((r.topic_id, other)))
                if key in seen:
                    continue
                seen.add(key)
                a, b = key
                extra.append({"Topic A": a, "Topic B": b, "Centroid cosine similarity": None,
                              "Evidence type": f"{kind} (naming stage name match; no centroid pair >= 0.90)",
                              "Transversal involved": "", "Name A": name[a], "Name B": name[b],
                              "Review flags A": flags[a], "Review flags B": flags[b],
                              "Representative skills A": rep_txt.get(a, ""), "Representative skills B": rep_txt.get(b, "")})
    if extra:
        dpairs = pd.concat([dpairs, pd.DataFrame(extra)], ignore_index=True)
    return res, rows, queue, dpairs


WIDTHS = {"Topic ID": 9, "Provisional name": 28, "Description": 50, "Model confidence reason": 45,
          "Representative skills (cosine to centroid)": 55, "LLM supporting skills": 35,
          "Reference-link status": 32, "Potential duplicate topic IDs": 24, "Review priority": 30,
          "Validity screening reason": 35, "Review flags": 30, "Reviewer notes": 40, "Proposed corrected name": 28,
          "Representative skills A": 55, "Representative skills B": 55, "Name A": 28, "Name B": 28,
          "Evidence type": 34, "Review flags A": 28, "Review flags B": 28}
WRAP_COLS = {"Description", "Model confidence reason", "Representative skills (cosine to centroid)", "LLM supporting skills",
             "Validity screening reason", "Representative skills A", "Representative skills B", "Review flags",
             "Reference-link status", "Reviewer notes", "Evidence type", "Potential duplicate topic IDs"}


def write_table(ws, df, review_cols=(), high_col=None):
    cols = list(df.columns) + list(review_cols)
    for j, c in enumerate(cols, 1):
        cell = ws.cell(1, j, c)
        cell.font, cell.alignment = BOLD, Alignment(wrap_text=True, vertical="center")
        cell.fill = REVIEW_HEAD if c in review_cols else EVID_HEAD
        ws.column_dimensions[get_column_letter(j)].width = WIDTHS.get(c, 14)
    for i, row in enumerate(df.itertuples(index=False), 2):
        for j, v in enumerate(row, 1):
            v = None if (v is None or (isinstance(v, float) and pd.isna(v))) else v
            cell = ws.cell(i, j, v)
            cell.font = FONT
            cell.alignment = WRAP if cols[j - 1] in WRAP_COLS else TOP
            if isinstance(v, float):
                cell.number_format = "0.000"
        for j in range(len(df.columns) + 1, len(cols) + 1):
            cell = ws.cell(i, j)
            cell.font, cell.fill = FONT, REVIEW_CELL
            cell.alignment = WRAP if cols[j - 1] in WRAP_COLS else TOP
    last = get_column_letter(len(cols))
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{last}{len(df) + 1}"
    ws.row_dimensions[1].height = 42
    if high_col is not None:
        L = get_column_letter(cols.index(high_col) + 1)
        ws.conditional_formatting.add(f"A2:{last}{len(df) + 1}", FormulaRule(
            formula=[f'OR(LEFT(${L}2,2)="P1",LEFT(${L}2,2)="P2")'], fill=HIGH_ROW))
    return cols


def build(out=OUT):
    if out.exists():
        sys.exit(f"refusing to overwrite existing workbook {out} (it may hold reviewer decisions)")
    before = {k: sha256(p) for k, p in SOURCES.items()}
    res, rows, queue, dpairs = build_frames()
    wb = Workbook()

    ws = wb.active
    ws.title = "Review_Queue"
    qcols = write_table(ws, queue.drop(columns=["Review required"]), REVIEW_COLS, "Review priority")
    dcol = get_column_letter(qcols.index("Reviewer decision") + 1)
    dv = DataValidation(type="list", formula1='"' + ",".join(DECISIONS) + '"', allow_blank=True,
                        showErrorMessage=True, errorTitle="Invalid decision", error="Pick a decision from the list")
    ws.add_data_validation(dv)
    dv.add(f"{dcol}2:{dcol}{len(queue) + 1}")
    tcol = get_column_letter(qcols.index("Review timestamp") + 1)
    for i in range(2, len(queue) + 2):
        ws[f"{tcol}{i}"].number_format = "yyyy-mm-dd hh:mm"

    ws = wb.create_sheet("All_Topics")
    write_table(ws, rows, (), "Review priority")
    ws = wb.create_sheet("Duplicate_Candidates")
    write_table(ws, dpairs)
    ws.freeze_panes = "C2"

    ws = wb.create_sheet("Review_Guidelines")
    guide = [
        ("Decision", "Meaning"),
        ("KEEP", "Topic is coherent and the name accurately describes its members."),
        ("RENAME", "Topic is coherent, but the name is misleading, generic or too long. Put the new name in 'Proposed corrected name'."),
        ("INVESTIGATE_CLUSTER", "Topic members are semantically inconsistent or the cluster may require splitting or reassignment."),
        ("POTENTIAL_MERGE", "Two topics appear semantically redundant; requires further evaluation. Name the other topic ID in 'Reviewer notes'."),
        ("UNSURE", "Evidence is insufficient."),
        ("", ""),
        ("Important", "These decisions are review recommendations, not automatic modifications. Nothing in clustering, names, Supabase or the hierarchy changes because of this sheet."),
        ("Which cells to edit", "Only the yellow columns on Review_Queue: Reviewer decision (dropdown), Proposed corrected name, Reviewer notes, Reviewer ID, Review timestamp. Blue columns are source evidence — do not edit."),
        ("Example row (format only)", "Reviewer decision = RENAME | Proposed corrected name = Regulatory Coding Compliance | Reviewer notes = members mix medical coding and DOT rules | Reviewer ID = LE | Review timestamp = 2026-11-05 14:30"),
        ("Human only", "Reviewer fields must be filled by a human. Do not paste AI / LLM judgments into them."),
        ("", ""),
        ("Review priority", "Buckets (first rule that matches wins; within a bucket, rows are sorted by lowest cohesion):"),
    ] + [("", t) for _, t in PRIORITY_RULES] + [
        ("Highlight", "P1 and P2 rows are shaded orange on Review_Queue and All_Topics."),
        ("", ""),
        ("Evidence definitions", ""),
        ("Review flags", "review_reason from the assembled naming result (topic-quality flags + name flags + llm_confidence_low). Copied verbatim."),
        ("low_cohesion", "cos_mean <= 25th percentile of all 374 topics (topic_naming.py)."),
        ("near_duplicate_topic", "some neighbour topic centroid has cosine >= 0.90 (sprint4_features similar_topic_pairs.csv)."),
        ("weak_exceeds_assigned", "more weak members than assigned members."),
        ("no_reference_link", "coverage_any == 0: no assigned skill has a confident ESCO / O*NET link."),
        ("Cohesion metric (cos_mean)", "mean cosine of assigned members to the topic centroid (topic_features.csv). Higher = tighter."),
        ("Representative skills", "top-10 assigned members by cosine to the centroid (representative_skills.csv)."),
        ("Reference-link status", f"label from coverage_any: 0 = no confident link; < {LOW_REF_COVERAGE:.0%} = low coverage (same threshold as topic_naming.py); otherwise linked. Purity is unavailable (no broader-group data in the snapshot)."),
        ("Potential duplicate topic IDs", "partner topics from similar_topic_pairs.csv with centroid cosine, plus '(name)' partners from duplicate_name flags."),
        ("Validity screening", "deterministic surface-form rules from topic_validity.py. 'Validity AI-proposed review' = Claude Code proposal in config/topic_validity/pilot_review_v1.json, status 'awaiting human confirmation' — NOT a human decision."),
        ("Names", "All names are provisional LLM output (Qwen or Claude Sonnet 5.5); none are human-validated."),
    ]
    for i, (a, b) in enumerate(guide, 1):
        ws.cell(i, 1, a).font = BOLD
        ws.cell(i, 2, b).font = BOLD if i == 1 else FONT
        ws.cell(i, 2).alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 30, 110

    ws = wb.create_sheet("Summary")
    nq = len(queue) + 1
    na = len(rows) + 1
    qL = lambda c: get_column_letter(qcols.index(c) + 1)
    acols = list(rows.columns)
    aL = lambda c: get_column_letter(acols.index(c) + 1)
    D = f"Review_Queue!${qL('Reviewer decision')}$2:${qL('Reviewer decision')}${nq}"
    FL = f"All_Topics!${aL('Review flags')}$2:${aL('Review flags')}${na}"
    PR = f"All_Topics!${aL('Source provider and model')}$2:${aL('Source provider and model')}${na}"
    RQ = f"All_Topics!${aL('Review required')}$2:${aL('Review required')}${na}"
    QP = f"Review_Queue!${qL('Review priority')}$2:${qL('Review priority')}${nq}"
    lines = [("Metric", "Count", "Formula basis"),
             ("Total topics", f"=COUNTA(All_Topics!$A$2:$A${na})", "rows in All_Topics"),
             ("Flagged topics", f"=COUNTA(Review_Queue!$A$2:$A${nq})", "rows in Review_Queue"),
             ("Reviewed topics", f"=COUNTA({D})", "non-blank Reviewer decision"),
             ("Pending reviews", "=B3-B4", "flagged - reviewed"),
             ("", None, ""), ("By reviewer decision", None, "")]
    lines += [(d, f'=COUNTIF({D},"{d}")', "") for d in DECISIONS]
    lines += [("", None, ""), ("By review priority (flagged)", None, "")]
    lines += [(t, f'=COUNTIF({QP},"{t}")', "") for _, t in PRIORITY_RULES]
    flag_names = sorted({f.split(":")[0] for r in res.review_reason for f in tokens(r)})
    lines += [("", None, ""), ("By review flag (all topics; one topic can have several)", None, "")]
    for f in flag_names:
        pat = f";{f}:" if f in ("duplicate_name", "near_duplicate_name") else f";{f};"
        lines.append((f, f'=SUMPRODUCT(--ISNUMBER(SEARCH("{pat}",";"&{FL}&";")))', "token match in Review flags"))
    lines += [("", None, ""), ("By model provider", None, "all topics / flagged")]
    for p in sorted(rows["Source provider and model"].unique()):
        lines.append((p, f'=COUNTIF({PR},"{p}")', f'=COUNTIFS({PR},"{p}",{RQ},"true")'))
    for i, (a, b, c) in enumerate(lines, 1):
        ws.cell(i, 1, a).font = BOLD if (b is None or i == 1) else FONT
        ws.cell(i, 2, b).font = BOLD if i == 1 else FONT
        ws.cell(i, 3, c).font = BOLD if i == 1 else FONT
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width, ws.column_dimensions["C"].width = 60, 12, 30
    ws.freeze_panes = "A2"

    after = {k: sha256(p) for k, p in SOURCES.items()}
    assert before == after, "a source file changed while building"
    ws = wb.create_sheet("Metadata")
    meta = [("Key", "Value"),
            ("generated_utc", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")),
            ("script", "src/build_topic_review_workbook.py"),
            ("script_sha256", sha256(__file__)),
            ("clustering_run_id", RUN),
            ("assembly_id", json.loads(SOURCES["assembled_manifest"].read_text())["assembly_id"]),
            ("llm_api_calls", "none (built only from files on disk)"),
            ("names", "provisional; human_validated = false for all 374 in source"),
            ("missing evidence", "ESCO/O*NET broader-group purity unavailable in snapshot (reference_summary.purity_status)"),
            ("", ""), ("Source file", "sha256 (relative path)")]
    meta += [(k, f"{before[k]}  ({p.relative_to(ROOT)})") for k, p in SOURCES.items()]
    for i, (a, b) in enumerate(meta, 1):
        ws.cell(i, 1, a).font = BOLD
        ws.cell(i, 2, b).font = FONT
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 26, 150

    wb.calculation.fullCalcOnLoad = True  # formulas have no cached values until Excel opens the file
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"wrote {out.relative_to(ROOT)}: {len(rows)} topics, {len(queue)} queued, {len(dpairs)} duplicate pairs")


if __name__ == "__main__":
    build()
