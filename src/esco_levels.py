"""ESCO v1.2.1 skills-hierarchy levels and topic purity (corrected definition, esco_purity/2).

Levels come ONLY from `skillsHierarchy_en.csv` (Level 0 = pillar, e.g. "skills" / "knowledge" / "transversal
skills and competences"; Level 1 = top groups such as "communication, collaboration and creativity" or
"information and communication technologies (icts)"; Level 2 / Level 3 = narrower groups). Parent links come from
`broaderRelationsSkillPillar_en.csv`; every broader parent is followed (ESCO concepts can have several).

Correction. The Phase 2/3 audit column `esco_purity_level2` took `path[-2]` of the FIRST-parent chain, which for the
usual chain [L3, L2, L1, L0] is the Level 1 group. It is therefore a Level 1 metric with a first-parent simplification.
`purity()` below names the level explicitly and is multi-parent aware.
"""
from collections import defaultdict
from pathlib import Path

import pandas as pd

LEVELS = (0, 1, 2, 3)


def read(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def load(esco_dir):
    """Return (level_of: uri -> level, parents: uri -> sorted list of broader uris, labels: uri -> label, skills: set)."""
    d = Path(esco_dir)
    h = read(d / "skillsHierarchy_en.csv")
    level_of, labels = {}, {}
    for lv in LEVELS:
        for u, lab in zip(h[f"Level {lv} URI"], h[f"Level {lv} preferred term"]):
            if u:
                prev = level_of.setdefault(u, lv)
                assert prev == lv, f"{u} appears at levels {prev} and {lv}"
                labels.setdefault(u, lab)
    br = read(d / "broaderRelationsSkillPillar_en.csv")
    parents = defaultdict(set)
    for c, b in zip(br.conceptUri, br.broaderUri):
        parents[c].add(b)
    skills = set(read(d / "skills_en.csv").conceptUri)
    return level_of, {k: sorted(v) for k, v in parents.items()}, labels, skills


def ancestors_at_level(uri, level, level_of, parents):
    """All ancestors of `uri` whose hierarchy level is `level` (multi-parent BFS, cycle-safe)."""
    out, seen, todo = set(), {uri}, list(parents.get(uri, []))
    while todo:
        u = todo.pop()
        if u in seen:
            continue
        seen.add(u)
        if level_of.get(u) == level:
            out.add(u)
            continue                      # groups above a level-L group are not level L
        todo.extend(parents.get(u, []))
    return out


def legacy_first_parent_group(uri, parents):
    """Reproduces the audit's old rule: first-parent chain, take path[-2] (or path[-1] if the chain has length 1)."""
    path, seen, u = [], set(), uri
    while u in parents and u not in seen:
        seen.add(u)
        u = parents[u][0]
        path.append(u)
    return (path[-2] if len(path) >= 2 else path[-1]) if path else None


def purity(uris_by_topic, level, level_of, parents, skills, min_links=3):
    """Per topic: share of the largest level-L group, each linked member spreading weight 1/|groups| over its
    level-L ancestors. Members whose URI is not in v1.2.1 or that have no level-L ancestor are counted, not used."""
    rows = []
    for t, uris in uris_by_topic.items():
        w = defaultdict(float)
        n_used = n_missing = n_nolevel = 0
        for u in uris:
            if u not in skills:
                n_missing += 1
                continue
            g = ancestors_at_level(u, level, level_of, parents)
            if not g:
                n_nolevel += 1
                continue
            n_used += 1
            for x in g:
                w[x] += 1 / len(g)
        top = max(w, key=lambda k: (w[k], k)) if w else ""
        rows.append({"topic_id": t, "level": level, "n_links": len(uris), "n_used": n_used,
                     "n_uri_not_in_v121": n_missing, "n_no_level_ancestor": n_nolevel,
                     "purity": round(w[top] / n_used, 4) if n_used >= min_links else None, "top_group_uri": top})
    return pd.DataFrame(rows)
