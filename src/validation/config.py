"""Validation config (data/validation/config/validation_config.yaml) and repo-relative paths."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_REL = "data/validation/config/validation_config.yaml"
PARTS = (1, 2, 3)


class Config:
    def __init__(self, root=ROOT, data=None):
        self.root = Path(root)
        self.data = data if data is not None else yaml.safe_load((self.root / CONFIG_REL).read_text(encoding="utf-8"))
        self.reviewers = [r.strip().lower() for r in self.data["reviewers"]]
        self.protected_n = {str(n) for n in self.data.get("protected_postings_n", [])}
        self.allowed_split = self.data.get("allowed_split", "dev")
        self.rule_choices = list(self.data.get("rule_choices", []))

    def path(self, rel):
        return self.root / rel

    def rel(self, p):
        """Repo-relative POSIX path, so tracked manifests never hold machine-specific paths."""
        return Path(p).resolve().relative_to(self.root.resolve()).as_posix()

    def shown(self, p):
        """Repo-relative path for messages when possible (never fails)."""
        try:
            return self.rel(p)
        except (TypeError, ValueError):
            return str(p)

    def p(self, key):
        return self.path(self.data["paths"][key])

    def postings_file(self):
        """First posting-text file that exists (they are shared via Drive, not Git), else None."""
        for rel in self.data["paths"]["postings"]:
            if self.path(rel).is_file():
                return self.path(rel)
        return None

    def run(self, run_id):
        r = self.data["runs"][run_id]
        return {"id": run_id, "errors": self.path(r["errors"]), "report": self.path(r["report"]) if r.get("report") else None}

    def part(self, n):
        return self.data[f"part{n}"]

    # folders written by the validation workflow. Tracked by Git: manifests, adjudication, approved_versions,
    # reports. Ignored (.gitignore, blind reviews): manifests/*_key.json and reviews/<reviewer>/events.jsonl.
    @property
    def vdir(self):
        return self.root / "data" / "validation"

    @property
    def manifests_dir(self):
        return self.vdir / "manifests"

    def reviews_file(self, reviewer):
        return self.vdir / "reviews" / reviewer / "events.jsonl"

    def adjudication_file(self, reviewer):
        return self.vdir / "adjudication" / f"{reviewer}.jsonl"

    @property
    def approved_dir(self):
        return self.vdir / "approved_versions"

    @property
    def reports_dir(self):
        return self.root / "reports" / "validation"

    def check_reviewer(self, reviewer):
        r = str(reviewer or "").strip().lower()
        if r not in self.reviewers:
            raise ValueError(f"unknown reviewer {reviewer!r}; choose one of {', '.join(self.reviewers)}")
        return r
