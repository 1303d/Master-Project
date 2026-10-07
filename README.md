# Skill Taxonomy (Section B)

Taxonomy of Work capstone. We build a skill taxonomy from public job postings.

## Folders

| Folder | What goes here |
|---|---|
| `data/raw/` | Downloaded data, never edited |
| `data/interim/` | Cleaned data |
| `data/processed/` | Final tables (postings, statements) |
| `data/gold/` | Hand-labeled gold set (100 postings) |
| `src/` | Python scripts |
| `notebooks/` | Exploration notebooks |
| `reports/` | Sprint reports |
| `cache/` | Saved LLM responses (re-runs are free) |
| `docs/` | Plans and shared docs |
| `learn/` | Study pages |

## Setup

1. Install packages: `py -m pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and add your API key.
3. Download data: `py src/download_data.py`
4. Clean data: `py src/clean_postings.py` (or put the shared `postings_clean.parquet` in `data/interim/`)

## Gold-set annotation in the dashboard

We reuse Lochan's review dashboard (repo `taxonomy-skill-project`) with no code changes.
Rules: `data/gold/LABELING_RULES.md`.

1. Build the dashboard data for the 100 gold postings: `py src/make_dashboard_data.py`
2. Start the dashboard (path to Lochan's repo):
   `py ../taxonomy-skill-project/src/dashboard.py --root dashboard_kaggle --db dashboard_kaggle/data/kaggle_gold.sqlite`
3. Open http://127.0.0.1:8765/ → **Annotation review** → **Evaluation annotation (independent)**.
4. Type your own reviewer ID, then click **Use this ID**.
5. When done, click **Export…** → **Write export folder**. Exports go to `dashboard_kaggle/data/annotation/sprint2_v1/reviewed/<your-id>/`.

Split: Lochan = IT + Engineering; Dhanush = all other sectors.
