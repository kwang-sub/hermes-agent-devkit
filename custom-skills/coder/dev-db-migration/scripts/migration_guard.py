#!/usr/bin/env python3
"""Bounded migration-policy helper for Coder DB physicalization.

It detects existing Flyway/Liquibase evidence, validates Flyway version naming,
allocates a collision-free UTC timestamp version inside the current worktree,
and derives the DevKit default physical table name from approved subject-area
metadata. It does not connect to or mutate a database.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

SKIP_DIRS = {".git", ".gradle", ".idea", "build", "target", "node_modules", "out", "dist"}
TEXT_MARKERS = {
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "application.yml",
    "application.yaml",
    "application.properties",
    "application-dev.yml",
    "application-dev.yaml",
    "application-dev.properties",
    "application-test.yml",
    "application-test.yaml",
    "application-test.properties",
}
FLYWAY_DIR_SUFFIXES = (
    ("src", "main", "resources", "db", "migration"),
    ("db", "migration"),
)
LIQUIBASE_DIR_SUFFIXES = (
    ("src", "main", "resources", "db", "changelog"),
    ("db", "changelog"),
)
GENERIC_VERSIONED_RE = re.compile(r"^V(?P<version>[0-9][0-9._]*)__.+\.sql$", re.IGNORECASE)
TIMESTAMP_VERSIONED_RE = re.compile(
    r"^V(?P<version>\d{14})__(?P<description>[a-z0-9]+(?:_[a-z0-9]+)*)\.sql$"
)
REPEATABLE_RE = re.compile(r"^R__(?P<description>[a-z0-9]+(?:_[a-z0-9]+)*)\.sql$", re.IGNORECASE)
SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


def _path_endswith(path: Path, suffix: tuple[str, ...]) -> bool:
    parts = path.parts
    return len(parts) >= len(suffix) and tuple(parts[-len(suffix):]) == suffix


def _walk_bounded(root: Path, max_depth: int = 7) -> Iterable[tuple[Path, list[str], list[str]]]:
    root = root.resolve()
    base_depth = len(root.parts)
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        depth = len(current_path.parts) - base_depth
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".worktrees")]
        if depth >= max_depth:
            dirs[:] = []
        yield current_path, dirs, files


def collect_evidence(root: Path) -> dict[str, Any]:
    flyway: set[str] = set()
    liquibase: set[str] = set()
    flyway_dirs: set[Path] = set()
    out_of_order: list[str] = []

    for current, _, files in _walk_bounded(root):
        rel = current.relative_to(root.resolve()) if current != root.resolve() else Path(".")
        if any(_path_endswith(current, suffix) for suffix in FLYWAY_DIR_SUFFIXES):
            flyway.add(f"dir:{rel.as_posix()}")
            flyway_dirs.add(current)
        if any(_path_endswith(current, suffix) for suffix in LIQUIBASE_DIR_SUFFIXES):
            liquibase.add(f"dir:{rel.as_posix()}")

        for filename in files:
            if filename not in TEXT_MARKERS:
                continue
            path = current / filename
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            lowered = text.lower()
            rel_file = path.relative_to(root.resolve()).as_posix()
            if "flyway-core" in lowered or "org.flywaydb.flyway" in lowered or "spring.flyway" in lowered:
                flyway.add(f"file:{rel_file}")
            if "liquibase-core" in lowered or "org.liquibase" in lowered or "spring.liquibase" in lowered:
                liquibase.add(f"file:{rel_file}")
            if re.search(r"(?im)^\s*(?:spring\.flyway\.out-of-order|out-of-order|outoforder)\s*[:=]\s*true\s*$", text):
                out_of_order.append(rel_file)

    if flyway and liquibase:
        tool = "conflict"
    elif flyway:
        tool = "existing_flyway"
    elif liquibase:
        tool = "existing_liquibase"
    else:
        tool = "default_flyway"

    return {
        "migration_tool": tool,
        "flyway_evidence": sorted(flyway),
        "liquibase_evidence": sorted(liquibase),
        "flyway_dirs": sorted(str(path) for path in flyway_dirs),
        "out_of_order_files": sorted(set(out_of_order)),
    }


def _canonical_version(version: str) -> tuple[int, ...] | None:
    parts = re.split(r"[._]", version)
    if not parts or any(not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _flyway_files(root: Path, evidence: dict[str, Any]) -> list[Path]:
    files: list[Path] = []
    for raw_dir in evidence.get("flyway_dirs", []):
        directory = Path(raw_dir)
        if directory.is_dir():
            files.extend(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".sql")
    return sorted(set(files))


def analyze_flyway(root: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    versions: dict[tuple[int, ...], list[str]] = {}
    timestamp_count = 0
    versioned_count = 0
    repeatable_count = 0
    invalid_filenames: list[str] = []

    for path in _flyway_files(root, evidence):
        name = path.name
        generic = GENERIC_VERSIONED_RE.match(name)
        if generic:
            versioned_count += 1
            version = generic.group("version")
            canonical = _canonical_version(version)
            if canonical is not None:
                versions.setdefault(canonical, []).append(name)
            if TIMESTAMP_VERSIONED_RE.match(name):
                timestamp_count += 1
            continue
        if REPEATABLE_RE.match(name):
            repeatable_count += 1
            continue
        if name[:1].upper() in {"V", "R"}:
            invalid_filenames.append(name)

    duplicates = [sorted(names) for names in versions.values() if len(names) > 1]
    if versioned_count == 0:
        policy = "timestamp_utc_default"
    elif timestamp_count == versioned_count:
        policy = "timestamp_utc"
    else:
        policy = "project_existing"

    return {
        "flyway_version_policy": policy,
        "versioned_count": versioned_count,
        "repeatable_count": repeatable_count,
        "existing_version_keys": [".".join(str(part) for part in key) for key in sorted(versions)],
        "duplicate_versions": duplicates,
        "invalid_filenames": sorted(invalid_filenames),
    }


def allocate_timestamp_version(root: Path, now: datetime | None = None) -> str:
    evidence = collect_evidence(root)
    used = {
        match.group("version")
        for path in _flyway_files(root, evidence)
        for match in [TIMESTAMP_VERSIONED_RE.match(path.name)]
        if match
    }
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc).replace(microsecond=0)
    for _ in range(120):
        candidate = current.strftime("%Y%m%d%H%M%S")
        if candidate not in used:
            return candidate
        current += timedelta(seconds=1)
    raise ValueError("unable to allocate unique Flyway timestamp version within 120 seconds")


def build_physical_table_name(subject_area: str, logical_table: str) -> str:
    subject = subject_area.strip().lower()
    logical = logical_table.strip().replace('"', '').lower().rsplit(".", 1)[-1]
    if not SNAKE_RE.fullmatch(subject):
        raise ValueError(f"subject area must be lowercase snake_case: {subject_area}")
    if not SNAKE_RE.fullmatch(logical):
        raise ValueError(f"logical table must be lowercase snake_case: {logical_table}")
    if logical.startswith("tbl_"):
        raise ValueError(f"logical table must not contain physical tbl_ prefix: {logical_table}")
    prefix = f"{subject}_"
    entity = logical[len(prefix):] if logical.startswith(prefix) else logical
    if not entity:
        raise ValueError("logical table must contain an entity name after subject-area normalization")
    return f"tbl_{subject}_{entity}"


def validate_new_flyway_file(
    new_file: str,
    policy: str,
    deployed_version: str | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    name = Path(new_file).name
    generic = GENERIC_VERSIONED_RE.match(name)
    repeatable = REPEATABLE_RE.match(name)
    if repeatable:
        return errors, warnings
    if not generic:
        errors.append(f"invalid Flyway migration filename: {name}")
        return errors, warnings

    version = generic.group("version")
    if policy in {"timestamp_utc_default", "timestamp_utc"} and not TIMESTAMP_VERSIONED_RE.match(name):
        errors.append(
            "new Flyway versioned migration must use V<yyyyMMddHHmmss>__<lowercase_snake_case>.sql"
        )

    if deployed_version:
        current = _canonical_version(version)
        deployed = _canonical_version(deployed_version)
        if current is None or deployed is None:
            warnings.append("deployed version ordering could not be compared numerically")
        elif current <= deployed:
            errors.append(
                f"new migration version {version} is not greater than deployed version {deployed_version}; do not auto-enable outOfOrder"
            )
    return errors, warnings


def analyze(
    root: Path,
    new_file: str | None = None,
    deployed_version: str | None = None,
    subject_area: str | None = None,
    logical_table: str | None = None,
    allocate_version: bool = False,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if not root.is_dir():
        return {"status": "blocked", "errors": [f"project root not found: {root}"], "warnings": []}

    evidence = collect_evidence(root)
    if evidence["migration_tool"] == "conflict":
        errors.append("Flyway and Liquibase are both detected; resolve migration ownership before implementation")
    if evidence["out_of_order_files"]:
        warnings.append("Flyway outOfOrder=true detected; preserve only with explicit project evidence/approval")

    flyway = analyze_flyway(root, evidence)
    for names in flyway["duplicate_versions"]:
        errors.append(f"duplicate Flyway version: {', '.join(names)}")
    if flyway["invalid_filenames"]:
        warnings.append("existing Flyway-like filenames do not match the lightweight guard convention")

    if new_file:
        file_errors, file_warnings = validate_new_flyway_file(
            new_file,
            flyway["flyway_version_policy"],
            deployed_version=deployed_version,
        )
        generic = GENERIC_VERSIONED_RE.match(Path(new_file).name)
        if generic:
            canonical = _canonical_version(generic.group("version"))
            key = ".".join(str(part) for part in canonical) if canonical is not None else None
            if key and key in set(flyway["existing_version_keys"]):
                file_errors.append(f"new Flyway version already exists in project: {generic.group('version')}")
        errors.extend(file_errors)
        warnings.extend(file_warnings)

    physical_table = None
    if subject_area is not None or logical_table is not None:
        if not subject_area or not logical_table:
            errors.append("subject-area and logical-table must be supplied together")
        else:
            try:
                physical_table = build_physical_table_name(subject_area, logical_table)
            except ValueError as exc:
                errors.append(str(exc))

    allocated = None
    if allocate_version:
        if evidence["migration_tool"] == "existing_liquibase":
            errors.append("cannot allocate Flyway version for a Liquibase project")
        elif evidence["migration_tool"] != "conflict":
            try:
                allocated = allocate_timestamp_version(root)
            except ValueError as exc:
                errors.append(str(exc))

    return {
        "status": "blocked" if errors else "pass",
        "root": str(root),
        **evidence,
        **flyway,
        "physical_table": physical_table,
        "allocated_flyway_version": allocated,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Coder migration policy guard")
    parser.add_argument("--root", required=True)
    parser.add_argument("--new-file")
    parser.add_argument("--deployed-version")
    parser.add_argument("--subject-area")
    parser.add_argument("--logical-table")
    parser.add_argument("--allocate-flyway-version", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    result = analyze(
        Path(args.root),
        new_file=args.new_file,
        deployed_version=args.deployed_version,
        subject_area=args.subject_area,
        logical_table=args.logical_table,
        allocate_version=args.allocate_flyway_version,
    )
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"STATUS={result['status']}")
        print(f"MIGRATION_TOOL={result.get('migration_tool', 'unknown')}")
        print(f"FLYWAY_VERSION_POLICY={result.get('flyway_version_policy', 'unknown')}")
        if result.get("physical_table"):
            print(f"PHYSICAL_TABLE={result['physical_table']}")
        if result.get("allocated_flyway_version"):
            print(f"ALLOCATED_FLYWAY_VERSION={result['allocated_flyway_version']}")
        for item in result.get("warnings", []):
            print(f"WARNING={item}")
        for item in result.get("errors", []):
            print(f"ERROR={item}")
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
