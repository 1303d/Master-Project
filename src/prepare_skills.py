"""Prepare extracted skill mentions for embedding (Sprint 3): apply approved evidence corrections, add a
normalised skill key, count mentions and postings per key.

    py src/prepare_skills.py --statements S.csv --approved A.csv --postings P.csv --out-dir OUT [--scope "..."]

Example (the 2026-10-21 pilot bundle):
    py src/prepare_skills.py \
        --statements data/interim/sprint3_pilot_2026-10-21/statements_qwen_qwen3.8-27b_sample2000_v3.csv \
        --approved data/interim/sprint3_pilot_2026-10-21/evidence_review_approved.csv \
        --postings data/interim/sprint3_pilot_2026-10-21/extraction_sample_2000.csv \
        --out-dir data/processed/sprint3_pilot_2026-10-21 \
        --scope "Partial Kaggle Qwen v3 pilot: 87 completed postings"

Corrections are applied by statement_id and only when the row checks out: posting link, original label and
evidence equal the statement, the reviewer approved it, and the corrected evidence is the exact text at
[evidence_start:evidence_end] of the posting description. Any failed check stops the run (nothing written).
Original label/evidence and the review status are kept as columns. The key is lowercase + outer-whitespace
trim only: no synonym merging, no trait filtering. Refuses to overwrite existing outputs.
Output: <out-dir>/prepared_mentions.csv, unique_skills.csv, manifest.json (sha256 of inputs and outputs)
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

STATEMENT_COLS = ["statement_id", "posting_id", "skill", "evidence"]
APPROVED_COLS = ["statement_id", "posting_id", "original_skill", "proposed_skill", "original_evidence",
                 "proposed_evidence", "evidence_start", "evidence_end", "decision", "reviewer_confirmation"]
OUTPUTS = ["prepared_mentions.csv", "unique_skills.csv", "manifest.json"]
REVIEWED, UNREVIEWED = "approved_flagged_entry", "not_manually_reviewed"


def skill_key(label):
    """Lowercase + trim outer whitespace. Nothing else (inner spaces, punctuation, plurals stay)."""
    return label.strip().lower()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need_cols(df, cols, name):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")


def validate_inputs(statements, approved, postings):
    """Raise ValueError listing every problem found; return nothing when all checks pass."""
    need_cols(statements, STATEMENT_COLS, "statements")
    need_cols(approved, APPROVED_COLS, "approved")
    need_cols(postings, ["posting_id", "description"], "postings")
    errors = []
    for name, df, col in [("statements", statements, "statement_id"), ("approved", approved, "statement_id"),
                          ("postings", postings, "posting_id")]:
        dups = df[col][df[col].duplicated()].tolist()
        if dups:
            errors.append(f"{name}: duplicate {col} {dups}")
    if statements["skill"].isna().any() or (statements["skill"].fillna("").str.strip() == "").any():
        errors.append("statements: empty skill label")
    unknown = sorted(set(statements["posting_id"]) - set(postings["posting_id"]))
    if unknown:
        errors.append(f"statements: posting_id not in postings {unknown}")
    if errors:  # the per-row checks below assume unique ids
        raise ValueError("\n".join(errors))

    st = statements.set_index("statement_id")
    desc = postings.set_index("posting_id")["description"]
    for r in approved.itertuples(index=False):
        sid = r.statement_id
        if sid not in st.index:
            errors.append(f"{sid}: not in statements")
            continue
        s = st.loc[sid]
        if r.posting_id != s["posting_id"]:
            errors.append(f"{sid}: posting_id {r.posting_id} != statement's {s['posting_id']}")
        if r.original_skill != s["skill"]:
            errors.append(f"{sid}: original_skill {r.original_skill!r} != statement's {s['skill']!r}")
        if r.original_evidence != s["evidence"]:
            errors.append(f"{sid}: original_evidence differs from the statement's evidence")
        if r.reviewer_confirmation != "approved":
            errors.append(f"{sid}: reviewer_confirmation is {r.reviewer_confirmation!r}, not 'approved'")
        if r.decision != "keep":
            errors.append(f"{sid}: decision {r.decision!r} not supported (only 'keep')")
        if not isinstance(r.proposed_skill, str) or not r.proposed_skill.strip():
            errors.append(f"{sid}: empty proposed_skill")
        if r.posting_id not in desc.index:
            errors.append(f"{sid}: posting {r.posting_id} not in postings")
        elif desc[r.posting_id][int(r.evidence_start):int(r.evidence_end)] != r.proposed_evidence:
            errors.append(f"{sid}: proposed_evidence is not the exact text at "
                          f"[{r.evidence_start}:{r.evidence_end}] of the description")
    if errors:
        raise ValueError("\n".join(errors))


def prepare(statements, approved):
    """Return (prepared_mentions, unique_skills). Inputs must already pass validate_inputs."""
    m = statements.copy()
    m["original_skill"] = m["skill"]
    m["original_evidence"] = m["evidence"]
    m["review_status"] = UNREVIEWED
    fix = approved.set_index("statement_id")
    hit = m["statement_id"].isin(fix.index)
    m.loc[hit, "skill"] = m.loc[hit, "statement_id"].map(fix["proposed_skill"])
    m.loc[hit, "evidence"] = m.loc[hit, "statement_id"].map(fix["proposed_evidence"])
    m.loc[hit, "review_status"] = REVIEWED
    m["skill_key"] = m["skill"].map(skill_key)

    rows = []
    for key, g in m.groupby("skill_key", sort=True):
        # display label = most common original spelling; ties go to the first one seen
        display = max(Counter(g["skill"]).items(), key=lambda kv: kv[1])[0]
        rows.append({"skill_key": key, "display_label": display, "mention_count": len(g),
                     "posting_count": g["posting_id"].nunique()})
    return m, pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--statements", required=True, help="statements CSV (one row per extracted skill)")
    ap.add_argument("--approved", required=True, help="approved evidence-review CSV")
    ap.add_argument("--postings", required=True, help="postings CSV with posting_id, description")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--scope", default="", help="free-text description saved in the manifest")
    args = ap.parse_args()

    out = Path(args.out_dir)
    exists = [f for f in OUTPUTS if (out / f).exists()]
    if exists:
        raise SystemExit(f"Refusing to overwrite {exists} in {out}")

    statements = pd.read_csv(args.statements, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    approved = pd.read_csv(args.approved, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    postings = pd.read_csv(args.postings, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    validate_inputs(statements, approved, postings)
    mentions, unique = prepare(statements, approved)
    assert unique["mention_count"].sum() == len(mentions) == len(statements)

    out.mkdir(parents=True, exist_ok=True)
    mentions.to_csv(out / "prepared_mentions.csv", index=False, encoding="utf-8")
    unique.to_csv(out / "unique_skills.csv", index=False, encoding="utf-8")
    files = [args.statements, args.approved, args.postings, out / "prepared_mentions.csv", out / "unique_skills.csv"]
    manifest = {
        "scope": args.scope,
        "mentions": len(mentions),
        "unique_skills": len(unique),
        "approved_flagged_entries": int((mentions["review_status"] == REVIEWED).sum()),
        "normalization": "Trim outer whitespace and lowercase",
        "synonyms_merged": False,
        "traits_filtered": False,
        "fully_manually_reviewed": bool((mentions["review_status"] == REVIEWED).all()),
        "sha256": {Path(f).as_posix(): sha256(f) for f in files},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"{len(mentions)} mentions, {len(unique)} unique skills, "
          f"{manifest['approved_flagged_entries']} approved corrections -> {out}")


if __name__ == "__main__":
    main()
