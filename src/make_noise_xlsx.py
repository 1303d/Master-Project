"""Noise workbook for the active HDBSCAN run (canonical_v2) -> C:/master/reports/sprint3_noise.xlsx"""
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(r"C:\master")
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402

V = ROOT / "data/processed/sprint3_full_2026-10-22/canonical_v2"
RUN = "hdbscan_10_umap10_ms1"
a = pd.read_csv(V / f"clusters/{RUN}/assignments.csv", keep_default_na=False)
u = pd.read_csv(V / "unique_skills.csv", keep_default_na=False)[["skill_key", "posting_count"]]
types = pd.read_csv(V / "skill_types.csv", keep_default_na=False)[["skill_key", "skill_type"]]
lib = set(pd.read_csv(V / "library_hdbscan_v2/library.csv", keep_default_na=False)["skill_key"])
con = db.connect()
mem = pd.DataFrame(con.execute("""select st.skill_key, st.topic_id, t.label, st.state, st.score, st.margin
    from skill_topics st join cluster_runs r on r.run_id = st.run_id and r.is_active join topics t using (topic_id)""").fetchall(),
    columns=["skill_key", "topic_id", "topic_label", "state", "score", "margin"])
run_id = con.execute("select run_id from cluster_runs where is_active").fetchone()[0]

df = (a[["skill_key", "mention_count", "cluster"]].merge(u, on="skill_key", how="left").merge(mem, on="skill_key", how="left")
      .merge(types, on="skill_key", how="left"))
df["noise"] = df["cluster"] < 0
df["library"] = df["skill_key"].isin(lib)
df = df.sort_values(["mention_count", "skill_key"], ascending=[False, True])
noise = df[df["noise"]]
sweep = pd.read_csv(V / "clusters/sweep.csv")

wb = Workbook()
H = Font(name="Arial", bold=True, color="FFFFFF"); F = Font(name="Arial"); B = Font(name="Arial", bold=True)
FILL = PatternFill("solid", fgColor="0F6E78"); KEY = PatternFill("solid", fgColor="E1F0F1")


def table(ws, cols, rows, widths):
    ws.append(cols)
    for c in ws[1]:
        c.font, c.fill, c.alignment = H, FILL, Alignment(vertical="center")
    for r in rows:
        ws.append(list(r))
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = F
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


# --- Skills: every canonical skill of the run (the formulas on Summary count this sheet) ---
ws = wb.active; ws.title = "Skills"
cols = ["skill", "mentions", "postings", "hdbscan_cluster", "is_noise", "topic_id", "topic_label", "membership",
        "score (cosine)", "margin", "library_skill", "skill_type"]
table(ws, cols, (( r.skill_key, int(r.mention_count), int(r.posting_count) if pd.notna(r.posting_count) else None, int(r.cluster),
                   bool(r.noise), r.topic_id, r.topic_label, r.state, r.score, r.margin, bool(r.library), r.skill_type)
                 for r in df.itertuples()), [32, 10, 10, 15, 9, 10, 28, 12, 13, 9, 12, 12])
n_rows = len(df) + 1
for r in range(2, n_rows + 1):
    ws.cell(r, 9).number_format = "0.000"; ws.cell(r, 10).number_format = "0.000"

# --- Noise skills: only the HDBSCAN noise, most-mentioned first ---
wn = wb.create_sheet("Noise skills")
table(wn, ["skill", "mentions", "postings", "weak member of topic", "topic_label", "score (cosine)", "margin", "library_skill", "skill_type"],
      ((r.skill_key, int(r.mention_count), int(r.posting_count) if pd.notna(r.posting_count) else None, r.topic_id, r.topic_label,
        r.score, r.margin, bool(r.library), r.skill_type) for r in noise.itertuples()), [32, 10, 10, 20, 28, 13, 9, 12, 12])
for r in range(2, len(noise) + 2):
    wn.cell(r, 6).number_format = "0.000"; wn.cell(r, 7).number_format = "0.000"

# --- Sweep: noise share of every setting tried (values from clusters/sweep.csv) ---
wsw = wb.create_sheet("Sweep noise")
table(wsw, ["setting", "method", "topics", "noise share (skills)", "noise share (mentions)"],
      ((x.run_id, x.method, int(x.n_clusters), float(x.noise_share), float(x.noise_mention_share)) for x in sweep.itertuples()),
      [26, 15, 9, 20, 22])
for r in range(2, len(sweep) + 2):
    wsw.cell(r, 4).number_format = "0.0%"; wsw.cell(r, 5).number_format = "0.0%"
wsw.cell(len(sweep) + 3, 1, "Source: data/processed/sprint3_full_2026-10-22/canonical_v2/clusters/sweep.csv (cluster_skills.py). "
         "Leiden and agglomerative assign every skill, so their noise is 0%.").font = Font(name="Arial", italic=True)

# --- Summary: formulas over the Skills sheet ---
s = wb.create_sheet("Summary", 0)
s.column_dimensions["A"].width = 46; s.column_dimensions["B"].width = 16; s.column_dimensions["C"].width = 70
s["A1"] = "HDBSCAN noise — Section B, Sprint 3"; s["A1"].font = Font(name="Arial", bold=True, size=14)
s["A2"] = f"Active run {run_id} · min_cluster_size 10 · min_samples 1 · UMAP 10 dims · 11,093 clean skills"; s["A2"].font = F
rng = f"Skills!$E$2:$E${n_rows}"; men = f"Skills!$B$2:$B${n_rows}"; libr = f"Skills!$K$2:$K${n_rows}"
rows = [
    ("Skills (canonical)", f"=COUNTA(Skills!$A$2:$A${n_rows})", "0", "every skill of the run"),
    ("Noise skills (HDBSCAN cluster = -1)", f'=COUNTIF({rng},TRUE)', "#,##0", "skills HDBSCAN did not put in any topic"),
    ("Noise share of skills", "=B5/B4", "0.0%", "the headline number"),
    ("Mentions (all skills)", f"=SUM({men})", "#,##0", "a skill counts once per statement"),
    ("Mentions of noise skills", f'=SUMIF({rng},TRUE,{men})', "#,##0", ""),
    ("Noise share of mentions", "=B8/B7", "0.0%", "higher than by skills: big merged skills (e.g. microsoft excel) are noise"),
    ("Noise skills that are library skills", f'=COUNTIFS({rng},TRUE,{libr},TRUE)', "#,##0", "generic cross-sector skills, handled by the library"),
    ("Clustered skills", "=B4-B5", "#,##0", ""),
]
s["A3"], s["B3"], s["C3"] = "Measure", "Value", "Note"
for c in (s["A3"], s["B3"], s["C3"]):
    c.font, c.fill = H, FILL
for i, (k, f, fmt, note) in enumerate(rows, 4):
    s.cell(i, 1, k).font = F
    c = s.cell(i, 2, f); c.font = B if "share" in k else F; c.number_format = fmt
    if "share" in k:
        c.fill = KEY
    s.cell(i, 3, note).font = Font(name="Arial", color="5B6673")
s.cell(13, 1, "How noise is handled: every noise skill becomes a weak member of its nearest topic centroid "
              "(Skills sheet: membership = weak, with score and margin), so no skill is lost.").font = Font(name="Arial", italic=True)
s.cell(14, 1, "Sources: canonical_v2/clusters/hdbscan_10_umap10_ms1/assignments.csv, Supabase skill_topics / topics, "
              "library_hdbscan_v2/library.csv, skill_types.csv (built 2026-10-27).").font = Font(name="Arial", italic=True, color="5B6673")

out = ROOT / "reports/sprint3_noise.xlsx"
wb.save(out)
print("saved", out, "| skills", len(df), "| noise", len(noise), round(len(noise) / len(df) * 100, 2), "%",
      "| mention share", round(noise.mention_count.sum() / df.mention_count.sum() * 100, 2), "%")
