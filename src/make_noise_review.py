"""Three noise-review workbooks (one per team member) -> C:/master/reports/noise_review/"""
import re
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.hyperlink import Hyperlink

ROOT = Path(r"C:\master")
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402
from gold_tool import hide_contacts  # noqa: E402

D = ROOT / "data/processed/sprint3_full_2026-10-22"
REVIEWERS = ["Dhanush", "Lochan", "Priyanka"]
OUT = ROOT / "reports/noise_review"
OUT.mkdir(parents=True, exist_ok=True)

noise = pd.read_excel(ROOT / "reports/sprint3_noise.xlsx", sheet_name="Noise skills")
alias = pd.read_csv(D / "canonical_v2/aliases.csv", keep_default_na=False).set_index("skill_key")["canonical_key"]
m = pd.read_csv(D / "prepared_mentions.csv", keep_default_na=False, usecols=["posting_id", "skill", "evidence", "skill_key"])
m["canonical"] = m["skill_key"].map(alias).fillna(m["skill_key"])
m = m[m["canonical"].isin(set(noise["skill"]))]
posts = pd.DataFrame(db.connect().execute(
    "select posting_id, title, company, url, description from postings where posting_id = any(%s)", (list(m["posting_id"].unique()),)).fetchall(),
    columns=["posting_id", "title", "company", "url", "description"]).set_index("posting_id")
m = m.join(posts, on="posting_id")
m["link"] = m.apply(lambda r: r["url"] or (f"https://www.linkedin.com/jobs/view/{r['posting_id'][3:]}" if r["posting_id"].startswith("li_") else ""), axis=1)
ex = m.drop_duplicates(["canonical", "posting_id"]).groupby("canonical").head(1)  # one JD per skill: less to read
ex["n"] = ex.groupby("canonical").cumcount() + 1
wide = ex.pivot(index="canonical", columns="n", values=["posting_id", "title", "company", "evidence", "link"])

rows = noise.sort_values(["postings", "skill"], ascending=[False, True]).reset_index(drop=True)
rows["reviewer"] = [REVIEWERS[i % 3] for i in range(len(rows))]  # round-robin: same mix of frequent and rare skills

H = Font(name="Arial", bold=True, color="FFFFFF"); F = Font(name="Arial", size=10)
FILL = PatternFill("solid", fgColor="0F6E78"); INPUT = PatternFill("solid", fgColor="FFF2CC")
COLS = [("#", 6), ("skill", 28), ("postings", 9), ("nearest topic (weak member)", 26), ("library skill", 9), ("type (ESCO / O*NET)", 13),
        ("job description", 14),
        ("DECISION", 13), ("alias of (if alias)", 22), ("note", 30)]


def get(skill, field, n):
    try:
        v = wide.loc[skill, (field, n)]
        return "" if pd.isna(v) else v
    except KeyError:
        return ""


RED_BOLD = InlineFont(rFont="Arial", sz=10, b=True, color="C00000"); PLAIN = InlineFont(rFont="Arial", sz=10)


def marked(text, quotes):
    """Full JD as rich text with every evidence quote in bold red."""
    spans = sorted((x.start(), x.end()) for q in quotes if len(q) > 2 for x in re.finditer(re.escape(q), text, re.I))
    parts, pos = [], 0
    for a, b in spans:
        if a < pos:
            a = pos
        if a >= b:
            continue
        if a > pos:
            parts.append(TextBlock(PLAIN, text[pos:a]))
        parts.append(TextBlock(RED_BOLD, text[a:b])); pos = b
    if pos < len(text):
        parts.append(TextBlock(PLAIN, text[pos:]))
    return CellRichText(parts) if parts else ""


for name in REVIEWERS:
    part = rows[rows["reviewer"] == name]
    wb = Workbook()
    info = wb.active; info.title = "How to review"
    lines = [
        (f"Noise skill review — {name}", Font(name="Arial", bold=True, size=14)),
        (f"{len(part)} skills that HDBSCAN left as noise (run hdbscan_10_umap10_ms1_2026-10-23). Sorted by postings: start at the top.", F),
        ("Fill only the yellow columns on the 'Review' sheet: DECISION (dropdown), 'alias of' and note.", F),
        ("", F),
        ("DECISION values (rule E: ESCO + O*NET are the rule book):", Font(name="Arial", bold=True)),
        ("skill        = a real, checkable ability (e.g. vba, payroll processing, venipuncture)", F),
        ("trait        = a personal quality, O*NET Work Style / ESCO attitude (e.g. judgment, patience, empathy)", F),
        ("not_a_skill  = a task, duty, degree, licence, tool brand with no skill meaning, or junk (e.g. 'zoom' as a word, '278')", F),
        ("alias        = the same skill as another name; write that name in 'alias of' (e.g. 'ms outlook' -> microsoft outlook)", F),
        ("unsure       = cannot decide; add a note so the team discusses it", F),
        ("", F),
        ("Example row (format only):  skill = vba · DECISION = skill · alias of = (empty) · note = Excel macro language", Font(name="Arial", italic=True)),
        ("Click 'read JD' to see the full job description (sheet 'Job descriptions'); the evidence is in bold red. Ctrl+F also works there.", F),
        ("When done, save the file and send it back; Claude will load the decisions into Supabase (review_decisions).", F),
    ]
    for i, (t, f) in enumerate(lines, 1):
        info.cell(i, 1, t).font = f
    info.column_dimensions["A"].width = 120

    ws = wb.create_sheet("Review")
    jd = wb.create_sheet("Job descriptions")
    jd.append(["#", "skill to judge", "job title", "company", "link", "full job description (evidence for this skill in bold red)", "back"])
    for c in jd[1]:
        c.font, c.fill, c.alignment = H, FILL, Alignment(wrap_text=True, vertical="center")
    one = ex.set_index("canonical")
    LINK = Font(name="Arial", size=10, color="0F6E78", underline="single")
    for i, s in enumerate(part.skill, 1):  # row i+1 here = row i+1 on Review, same skill
        n = i + 1
        if s not in one.index:
            jd.append([i, s, "", "", "", "(no posting found)", ""]); continue
        r0 = one.loc[s]
        text = ILLEGAL_CHARACTERS_RE.sub("", hide_contacts(r0["description"] or ""))
        jd.append([i, s, r0["title"], r0["company"], "", "", ""])
        jd.cell(n, 6).value = marked(text, {r0["evidence"]})
        if r0["link"]:
            c = jd.cell(n, 5, "open posting"); c.hyperlink = r0["link"]
        c = jd.cell(n, 7, "back to Review"); c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'Review'!H{n}")
        for c in jd[n]:
            c.font = LINK if c.hyperlink else (Font(name="Arial", size=10, bold=True) if c.column == 2 else F)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        jd.row_dimensions[n].height = min(409, 13 * (len(text) // 140 + text.count("\n") + 1))
    for col, w in zip("ABCDEFG", (6, 24, 26, 18, 13, 140, 14)):
        jd.column_dimensions[col].width = w
    jd.freeze_panes = "C2"; jd.auto_filter.ref = jd.dimensions
    ws.append([c for c, _ in COLS])
    for c in ws[1]:
        c.font, c.fill, c.alignment = H, FILL, Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 32
    for i, r in enumerate(part.itertuples(), 1):
        s = r.skill
        ws.append([i, s, int(r.postings), f"{r._4} {r.topic_label}" if isinstance(r._4, str) else "", "yes" if r.library_skill else "",
                   r.skill_type if isinstance(r.skill_type, str) else "",
                   "", "", "", ""])
        if get(s, "posting_id", 1):
            c = ws.cell(i + 1, 7, "read JD")
            c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'Job descriptions'!A{i + 1}")
            c.font = Font(name="Arial", size=10, color="0F6E78", underline="single")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if c.hyperlink is None:
                c.font = F
            c.alignment = Alignment(wrap_text=False, vertical="top")
        for c in row[7:10]:
            c.fill = INPUT
    for i, (_, w) in enumerate(COLS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    dv = DataValidation(type="list", formula1='"skill,trait,not_a_skill,alias,unsure"', allow_blank=True,
                        error="Pick one: skill, trait, not_a_skill, alias, unsure", errorTitle="Decision")
    ws.add_data_validation(dv); dv.add(f"H2:H{len(part) + 1}")
    ws.freeze_panes = "C2"; ws.auto_filter.ref = ws.dimensions
    wb.active = 1
    path = OUT / f"noise_review_{name}.xlsx"
    wb.save(path)
    print(name, len(part), "skills ->", path, "| with JD:", sum(1 for s in part.skill if get(s, "posting_id", 1)))
