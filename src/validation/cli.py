"""Gold validation command line (the dashboard page uses the same code).

    python src/validation/cli.py build                 # create the three sample manifests (no-op if unchanged)
    python src/validation/cli.py build --new-version   # sources changed: write v<K+1>; old reviews are kept
    python src/validation/cli.py status                # artifacts, manifests, progress (counts only)
    python src/validation/cli.py report                # write reports/validation/validation_progress_<time>.md/.json
    python src/validation/cli.py approve-version --name gold_v1_validation_1
                                                       # APPROVED changes -> data/validation/approved_versions/<name>/

No command edits a gold file, calls an API or touches the database. Labels are never printed.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validation import adjudication, manifests, reporting  # noqa: E402
from validation.config import PARTS, Config  # noqa: E402
from validation.sources import MissingArtifact  # noqa: E402


def artifacts(cfg):
    """Which inputs exist on this machine (posting text is shared via Drive, not Git)."""
    rows = [("gold", cfg.p("gold"), "Git"), ("split", cfg.p("split"), "Git"), ("rules", cfg.p("rules"), "Git"),
            ("historical audit", cfg.p("historical_audit"), "Git")]
    for run_id in cfg.data["runs"]:
        r = cfg.run(run_id)
        rows += [(f"{run_id} errors", r["errors"], "Git"), (f"{run_id} report", r["report"], "Git")]
    found = cfg.postings_file()
    rows.append(("posting text", found or cfg.path(cfg.data["paths"]["postings"][0]),
                 "Google Drive (gitignored): copy gold_postings_dev.csv into data/gold/"))
    return [{"name": n, "path": cfg.shown(p), "exists": bool(p and Path(p).is_file()), "source": s} for n, p, s in rows]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--new-version", action="store_true")
    sub.add_parser("status")
    sub.add_parser("report")
    a = sub.add_parser("approve-version")
    a.add_argument("--name", required=True)
    args = ap.parse_args()
    cfg = Config()
    try:
        if args.cmd == "build":
            for part in PARTS:
                m, st = manifests.ensure(cfg, part, args.new_version)
                print(f"part {part}: {m['manifest_id']} {st} · {len(m['items'])} items")
                print("  population:", json.dumps(m["population"], default=str))
        elif args.cmd == "status":
            for a_ in artifacts(cfg):
                print(f"{'ok     ' if a_['exists'] else 'MISSING'} {a_['name']}: {a_['path']} ({a_['source']})")
            print(json.dumps(reporting.summary(cfg)["parts"], indent=1, default=str))
        elif args.cmd == "report":
            print("\n".join(reporting.export(cfg)))
        elif args.cmd == "approve-version":
            out, n = adjudication.approve_version(cfg, args.name)
            print(f"{n} approved changes -> {cfg.rel(out)} (gold files unchanged)")
    except (MissingArtifact, manifests.StaleSources, FileExistsError, ValueError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
