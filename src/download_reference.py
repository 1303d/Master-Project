"""Download the reference skill libraries used to link extracted skills (Sprint 3).

    py src/download_reference.py

ESCO v1.2 (CC BY 4.0) -> data/reference/esco_skills.csv, one row per skill, paged from the official API
  columns: uri, label, alt_labels (|-joined), skill_type (knowledge / skill), reuse_level
           (transversal / cross-sector / sector-specific / occupation-specific), broader (|-joined), description
              -> data/reference/esco_attitudes.csv, the "attitudes and values" group (traits)
O*NET 31.0 (CC BY 4.0) -> data/reference/onet/*.txt, only the files we use:
  Software Skills (tools, "Workplace Example" column), Work Styles (traits), Essential + Transferable Skills,
  Knowledge, GWAs to IWAs to DWAs (task statements). 31.0 renamed Technology Skills -> Software Skills.

Existing files are kept: delete one to download it again.
"""
import io
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "reference"
ESCO_API = "https://ec.europa.eu/esco/api/search"
ONET_ZIP = "https://www.onetcenter.org/dl_files/database/db_31_0_text.zip"
ONET_FILES = ["Software Skills.txt", "Work Styles.txt", "Essential Skills.txt", "Transferable Skills.txt",
              "Knowledge.txt", "GWAs to IWAs to DWAs.txt"]


def tail(uri):
    return uri.rstrip("/").rsplit("/", 1)[-1]


def fetch(limit, page):
    """One search page. Some pages return HTTP 500 (a bad record): split them so only that record is lost."""
    for _ in range(3):
        r = requests.get(ESCO_API, params={"type": "skill", "language": "en", "limit": limit, "offset": page,
                                           "full": "true"}, timeout=120)
        if r.status_code == 200:
            return r.json().get("_embedded", {}).get("results", [])
        time.sleep(2)
    if limit == 1:
        print(f"  skipped ESCO record #{page} (HTTP {r.status_code})")
        return [None]  # keeps the loop going past the bad record
    small = limit // 10 or 1
    return [h for i in range(limit // small) for h in fetch(small, page * (limit // small) + i)]


def esco():
    path = OUT / "esco_skills.csv"
    if path.exists():
        print(f"keep {path.relative_to(ROOT)}")
        return
    rows, page = [], 0
    while True:  # the API's offset is a page number
        hits = fetch(100, page)
        if not hits:
            break
        for h in filter(None, hits):
            links = h.get("_links", {})
            rows.append({
                "uri": h["uri"],
                "label": h["preferredLabel"].get("en") or h["title"],
                "alt_labels": "|".join((h.get("alternativeLabel") or {}).get("en", [])),
                "skill_type": "|".join(tail(x["uri"]) for x in links.get("hasSkillType", [])),
                "reuse_level": "|".join(tail(x["uri"]) for x in links.get("hasReuseLevel", [])),
                "broader": "|".join(x.get("title", "") for x in links.get("broaderHierarchyConcept", [])),
                "description": ((h.get("description") or {}).get("en") or {}).get("literal", ""),
            })
        page += 1
        print(f"  ESCO page {page}: {len(rows)} skills", flush=True)
        time.sleep(0.2)
    pd.DataFrame(rows).to_csv(path, index=False)
    print(f"{len(rows)} ESCO skills -> {path.relative_to(ROOT)}")


ATTITUDES = "http://data.europa.eu/esco/skill/81c66e05-0b64-4cc5-8707-432f59fb6528"  # "attitudes and values"


def esco_attitudes():
    """Walk ESCO's 'attitudes and values' group (traits) -> data/reference/esco_attitudes.csv (uri, label)."""
    path = OUT / "esco_attitudes.csv"
    if path.exists():
        print(f"keep {path.relative_to(ROOT)}")
        return
    seen, todo, rows = set(), [ATTITUDES], []
    while todo:
        uri = todo.pop()
        if uri in seen:
            continue
        seen.add(uri)
        r = requests.get("https://ec.europa.eu/esco/api/resource/skill", params={"uri": uri, "language": "en"},
                         timeout=60)
        if r.status_code != 200:
            continue
        d = r.json()
        rows.append({"uri": uri, "label": d.get("title", "")})
        links = d.get("_links", {})
        todo += [x["uri"] for k in ("narrowerConcept", "narrowerSkill") for x in links.get(k, [])]
        time.sleep(0.1)
    pd.DataFrame(rows[1:]).to_csv(path, index=False)  # rows[0] is the group itself
    print(f"{len(rows) - 1} ESCO attitudes -> {path.relative_to(ROOT)}")


def onet():
    folder = OUT / "onet"
    if all((folder / f).exists() for f in ONET_FILES):
        print(f"keep {folder.relative_to(ROOT)}")
        return
    folder.mkdir(parents=True, exist_ok=True)
    r = requests.get(ONET_ZIP, timeout=300)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for name in z.namelist():
            if Path(name).name in ONET_FILES:
                (folder / Path(name).name).write_bytes(z.read(name))  # flat copy, no paths from the zip
    print(f"O*NET files -> {folder.relative_to(ROOT)}: {sorted(p.name for p in folder.iterdir())}")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    onet()
    esco()
    esco_attitudes()
