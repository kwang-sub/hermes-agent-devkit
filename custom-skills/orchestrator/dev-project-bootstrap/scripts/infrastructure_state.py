#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


MANAGED_MARKER = "# managed-by: dev-project-bootstrap"
INFRASTRUCTURE_VERSION = "1"
SUPPORTED_VENDORS = {"postgresql", "mysql", "mariadb", "mssql", "oracle"}


class InfrastructureStateError(RuntimeError):
    pass


def split_top_level_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.splitlines(keepends=True)
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if line.startswith((" ", "\t")):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+):(?:\s.*)?(?:\r?\n)?$", line)
        if match:
            starts.append((index, match.group(1)))
    if not starts:
        return text, []
    header = "".join(lines[: starts[0][0]])
    sections: list[tuple[str, str]] = []
    for pos, (start, key) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        sections.append((key, "".join(lines[start:end])))
    return header, sections


def metadata_path(repo: Path) -> Path:
    return repo / ".hermes" / "project.yaml"


def technology_vendors(sections: list[tuple[str, str]]) -> list[str]:
    body = next((body for key, body in sections if key == "technology"), "")
    if not body:
        return []
    lines = body.splitlines()
    inside = False
    values: list[str] = []
    for line in lines:
        if re.fullmatch(r"\s{2}database_vendors:\s*(?:\[\])?\s*", line):
            if line.rstrip().endswith("[]"):
                return []
            inside = True
            continue
        if not inside:
            continue
        if re.match(r"^\s{2}\S", line):
            break
        match = re.match(r"^\s{4}-\s+(.+?)\s*$", line)
        if not match:
            continue
        raw = match.group(1).strip()
        try:
            decoded = json.loads(raw)
            value = str(decoded)
        except Exception:
            value = raw.strip("'\"")
        if value in SUPPORTED_VENDORS:
            values.append(value)
    return list(dict.fromkeys(values))


def infrastructure_section(vendor: str) -> str:
    return "\n".join([
        "infrastructure:",
        f"  version: {json.dumps(INFRASTRUCTURE_VERSION)}",
        '  application_runtime: "CONTAINER"',
        '  database_runtime: "CONTAINER"',
        '  database_platform: "NATIVE"',
        f"  database_vendor: {json.dumps(vendor)}",
    ]) + "\n"


def ensure(repo: Path) -> tuple[str, str]:
    path = metadata_path(repo)
    if not path.is_file():
        raise InfrastructureStateError(
            f"bootstrap-managed metadata is missing; run bootstrap_project first: {path}"
        )
    text = path.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise InfrastructureStateError(f"metadata is not managed by dev-project-bootstrap: {path}")

    header, sections = split_top_level_sections(text)
    existing = next((body for key, body in sections if key == "infrastructure"), None)
    if existing is not None:
        return "preserved", "existing"

    vendors = technology_vendors(sections)
    vendor = vendors[0] if len(vendors) == 1 else "UNKNOWN"
    parts = [body.rstrip() for _, body in sections if body.strip()]
    parts.append(infrastructure_section(vendor).rstrip())
    updated = header.rstrip("\r\n")
    if updated:
        updated += "\n"
    updated += "\n\n".join(parts) + "\n"
    path.write_text(updated, encoding="utf-8")
    return "created", vendor


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ensure bootstrap-managed infrastructure desired-state defaults without overwriting existing choices"
    )
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"ERROR=repository not found: {repo}", file=sys.stderr)
        return 2
    try:
        status, vendor = ensure(repo)
    except InfrastructureStateError as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 2

    print(f"INFRASTRUCTURE_STATE={status}")
    print("APPLICATION_RUNTIME_DEFAULT=CONTAINER")
    print("DATABASE_RUNTIME_DEFAULT=CONTAINER")
    print("DATABASE_PLATFORM_DEFAULT=NATIVE")
    print(f"DATABASE_VENDOR_DEFAULT={vendor}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
