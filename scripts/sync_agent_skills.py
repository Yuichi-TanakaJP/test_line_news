#!/usr/bin/env python3
"""Check or synchronize generated agent skills from the canonical directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MANIFEST = Path(__file__).parents[1] / "skill-sync.json"


@dataclass(frozen=True)
class Finding:
    skill: str
    status: str
    detail: str


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_files(directory: Path) -> dict[Path, str]:
    if not directory.is_dir():
        return {}
    return {
        path.relative_to(directory): digest(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def load_manifest(path: Path) -> tuple[Path, Path, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    root = path.parent.resolve()
    canonical = (root / data["canonical"]).resolve()
    generated = (root / data["generated"]).resolve()
    skills = data["skills"]
    if not canonical.is_relative_to(root) or not generated.is_relative_to(root):
        raise ValueError("manifest directories must stay inside the repository")
    if not isinstance(skills, list) or not skills or not all(isinstance(item, str) for item in skills):
        raise ValueError("manifest 'skills' must be a non-empty string list")
    if len(skills) != len(set(skills)):
        raise ValueError("manifest 'skills' contains duplicates")
    if any(not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill) for skill in skills):
        raise ValueError("manifest skill names must use lowercase letters, digits, and hyphens")
    return canonical, generated, skills


def check(manifest: Path) -> list[Finding]:
    canonical, generated, skills = load_manifest(manifest)
    findings: list[Finding] = []
    for skill in skills:
        source = canonical / skill
        target = generated / skill
        if not (source / "SKILL.md").is_file():
            findings.append(Finding(skill, "invalid-source", "canonical SKILL.md is missing"))
            continue
        if not target.is_dir():
            findings.append(Finding(skill, "missing", "generated skill directory is missing"))
            continue
        source_files = relative_files(source)
        target_files = relative_files(target)
        if source_files != target_files:
            missing = sorted(str(path) for path in source_files.keys() - target_files.keys())
            extra = sorted(str(path) for path in target_files.keys() - source_files.keys())
            changed = sorted(
                str(path)
                for path in source_files.keys() & target_files.keys()
                if source_files[path] != target_files[path]
            )
            detail = f"missing={missing}, extra={extra}, changed={changed}"
            findings.append(Finding(skill, "drift", detail))
    return findings


def synchronize(manifest: Path) -> None:
    canonical, generated, skills = load_manifest(manifest)
    generated.mkdir(parents=True, exist_ok=True)
    for skill in skills:
        source = canonical / skill
        target = generated / skill
        if not (source / "SKILL.md").is_file():
            raise FileNotFoundError(f"canonical SKILL.md is missing: {source}")
        target.mkdir(parents=True, exist_ok=True)
        source_files = relative_files(source)
        target_files = relative_files(target)
        extra = target_files.keys() - source_files.keys()
        if extra:
            formatted = ", ".join(str(path) for path in sorted(extra))
            raise RuntimeError(f"refusing to delete generated-only files in {skill}: {formatted}")
        for relative in source_files:
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--write", action="store_true", help="Copy canonical files to generated directories.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    manifest = args.manifest.resolve()

    if args.write:
        synchronize(manifest)
    findings = check(manifest)

    if args.as_json:
        print(json.dumps([finding.__dict__ for finding in findings], ensure_ascii=False, indent=2))
    elif findings:
        for finding in findings:
            print(f"{finding.status.upper()} {finding.skill}: {finding.detail}")
    else:
        print("Skill sync check passed.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
