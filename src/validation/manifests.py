"""Versioned sample manifests: part<N>_v<K>.json (+ part2_v<K>_key.json). A manifest is never replaced.

`ensure` builds v1 once. Rebuilding with the same sources is a no-op; changed sources are refused unless
new_version=True, which writes v<K+1> and leaves older manifests (and the reviews tied to them) untouched.
"""
import json
import re

from validation import agreements, disagreements, full_posting
from validation.config import PARTS
from validation.storage import git_head, read_json, sha256_file, sha256_text, utc_now, write_json_atomic

BUILDERS = {1: disagreements.build, 2: agreements.build, 3: full_posting.build}


class StaleSources(Exception):
    pass


def source_files(cfg, part):
    files = [cfg.p("gold"), cfg.p("split")]
    for run_id in cfg.part(part).get("runs", []):
        r = cfg.run(run_id)
        files += [r["errors"]] + ([r["report"]] if r["report"] else [])
    return files


def fingerprint(cfg, part):
    """Hashes of everything the sample depends on: source files + this part's settings.
    Posting text is Drive-only, so it is checked per item (description_sha256) instead."""
    settings = {"part": cfg.part(part), "protected": sorted(cfg.protected_n), "split": cfg.allowed_split,
                "gold_version": cfg.data.get("gold_version"),
                "runs": {r: cfg.data["runs"][r] for r in cfg.part(part).get("runs", [])}}
    out = {cfg.rel(f): sha256_file(f) for f in source_files(cfg, part)}
    out["settings"] = sha256_text(json.dumps(settings, sort_keys=True))
    return out


def versions(cfg, part):
    pat = re.compile(rf"part{part}_v(\d+)\.json$")
    found = [(int(m.group(1)), f) for f in cfg.manifests_dir.glob(f"part{part}_v*.json") if (m := pat.match(f.name))]
    return sorted(found)


def active(cfg, part):
    v = versions(cfg, part)
    return read_json(v[-1][1]) if v else None


def stale_sources(cfg, manifest):
    """Source files whose hash changed since the manifest was built ([] = still valid). The labelling rules
    count too: every manifest records their hash, and reviewers judge items against them."""
    now = fingerprint(cfg, manifest["part"])
    changed = {k for k in set(now) | set(manifest["sources"]) if now.get(k) != manifest["sources"].get(k)}
    rules = manifest.get("rules")
    if rules and (cfg.rel(cfg.p("rules")) != rules["file"] or sha256_file(cfg.p("rules")) != rules["sha256"]):
        changed.add(rules["file"])
    return sorted(changed)


def ensure(cfg, part, new_version=False):
    """Return (manifest, status) with status 'created', 'unchanged' or 'new_version'."""
    current = active(cfg, part)
    if current is not None:
        changed = stale_sources(cfg, current)
        if not changed:
            return current, "unchanged"
        if not new_version:
            raise StaleSources(f"part {part}: sources changed since {current['manifest_id']} ({', '.join(changed)}); "
                               "rebuild with --new-version (existing reviews stay tied to the old manifest)")
    k = (versions(cfg, part)[-1][0] + 1) if current else 1
    built = BUILDERS[part](cfg)
    items, population = built[0], built[1]
    rules = cfg.p("rules")
    manifest = {"manifest_id": f"part{part}_v{k}", "part": part, "version": k, "created_utc": utc_now(),
                "implementation_commit": git_head(cfg.root), "gold_version": cfg.data.get("gold_version"),
                "rules": {"file": cfg.rel(rules), "sha256": sha256_file(rules)},
                "settings": cfg.part(part), "protected_postings_n": sorted(cfg.protected_n, key=int),
                "sources": fingerprint(cfg, part), "population": population, "items": items}
    write_json_atomic(cfg.manifests_dir / f"part{part}_v{k}.json", manifest)
    if part == 2:
        write_json_atomic(cfg.manifests_dir / f"part2_v{k}_key.json", {"manifest_id": manifest["manifest_id"], "key": built[2]})
    return manifest, ("new_version" if current else "created")


def ensure_all(cfg, new_version=False):
    return {p: ensure(cfg, p, new_version) for p in PARTS}


def part2_key(cfg, manifest_id):
    f = cfg.manifests_dir / f"{manifest_id}_key.json"
    return read_json(f)["key"] if f.is_file() else {}
