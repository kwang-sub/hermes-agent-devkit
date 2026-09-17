#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile

MANAGED_MARKER = "# managed-by: dev-project-bootstrap"
RUNTIMES = {"LOCAL_HOST", "NETWORK_HOST", "CONTAINER"}
PLATFORMS = {"NATIVE", "SUPABASE"}
VENDORS = {"postgresql", "mysql", "mariadb", "mssql", "oracle", "unknown"}
DESIRED_KEYS = (
    "application_runtime",
    "application_host",
    "application_port",
    "database_runtime",
    "database_host",
    "database_port",
    "database_platform",
    "database_vendor",
)


class DesiredStateError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persist a user-approved Infrastructure Desired State in primary project metadata."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--application-runtime", required=True, choices=sorted(RUNTIMES))
    parser.add_argument("--application-host", default="unknown")
    parser.add_argument("--application-port", default="unknown")
    parser.add_argument("--database-runtime", required=True, choices=sorted(RUNTIMES))
    parser.add_argument("--database-host", default="unknown")
    parser.add_argument("--database-port", default="unknown")
    parser.add_argument("--database-platform", required=True, choices=sorted(PLATFORMS))
    parser.add_argument("--database-vendor", required=True, choices=sorted(VENDORS))
    return parser.parse_args()


def normalize_host(value: str) -> str:
    raw = str(value or "unknown").strip()
    if not raw or raw.lower() == "unknown":
        return "unknown"
    if any(char.isspace() for char in raw) or "://" in raw or "/" in raw or "@" in raw:
        raise DesiredStateError(f"host must be a hostname/address only, not a URL or credential: {raw}")
    return raw.lower()


def normalize_port(value: str) -> str:
    raw = str(value or "unknown").strip()
    if not raw or raw.lower() == "unknown":
        return "unknown"
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise DesiredStateError(f"invalid port: {raw}")
    return raw


def normalize_desired(values: dict[str, str]) -> dict[str, str]:
    app_runtime = values["application_runtime"].upper()
    db_runtime = values["database_runtime"].upper()
    platform = values["database_platform"].upper()
    vendor = values["database_vendor"].lower()
    if app_runtime not in RUNTIMES:
        raise DesiredStateError(f"invalid application runtime: {app_runtime}")
    if db_runtime not in RUNTIMES:
        raise DesiredStateError(f"invalid database runtime: {db_runtime}")
    if platform not in PLATFORMS:
        raise DesiredStateError(f"invalid database platform: {platform}")
    if vendor not in VENDORS:
        raise DesiredStateError(f"invalid database vendor: {vendor}")
    if platform == "SUPABASE":
        vendor = "postgresql"
    return {
        "application_runtime": app_runtime,
        "application_host": normalize_host(values.get("application_host", "unknown")),
        "application_port": normalize_port(values.get("application_port", "unknown")),
        "database_runtime": db_runtime,
        "database_host": normalize_host(values.get("database_host", "unknown")),
        "database_port": normalize_port(values.get("database_port", "unknown")),
        "database_platform": platform,
        "database_vendor": vendor,
    }


def render_infrastructure(desired: dict[str, str]) -> str:
    lines = [
        "infrastructure:",
        '  version: "2"',
        "  defaults:",
        '    application_runtime: "CONTAINER"',
        '    database_runtime: "CONTAINER"',
        '    database_platform: "NATIVE"',
        "  desired:",
    ]
    for key in DESIRED_KEYS:
        lines.append(f"    {key}: {json.dumps(desired[key], ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def replace_infrastructure_section(text: str, rendered: str) -> str:
    pattern = re.compile(
        r"(?ms)^infrastructure:\s*(?:#.*)?\n.*?(?=^[A-Za-z0-9_.-]+:\s*(?:#.*)?$|\Z)"
    )
    match = pattern.search(text)
    if match:
        before = text[: match.start()].rstrip()
        after = text[match.end() :].lstrip("\n")
        updated = before + "\n\n" + rendered
        if after:
            updated += "\n" + after
        return updated.rstrip() + "\n"
    return text.rstrip() + "\n\n" + rendered


def atomic_write(path: Path, text: str) -> None:
    mode = path.stat().st_mode
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(mode)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def persist(repo: Path, desired: dict[str, str]) -> tuple[str, dict[str, str]]:
    repo = repo.expanduser().resolve()
    metadata = repo / ".hermes" / "project.yaml"
    if not metadata.is_file():
        raise DesiredStateError(f"project metadata is missing from primary repository: {metadata}")
    text = metadata.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise DesiredStateError(f"project metadata is not managed by dev-project-bootstrap: {metadata}")

    repository_match = re.search(r"(?m)^\s{2}repository:\s*(.+?)\s*$", text)
    if not repository_match:
        raise DesiredStateError("project.repository is missing from metadata")
    configured_repo = Path(repository_match.group(1).strip().strip("'\"")).expanduser().resolve()
    if configured_repo != repo:
        raise DesiredStateError(
            f"project metadata repository mismatch: metadata={configured_repo}, primary={repo}"
        )

    normalized = normalize_desired(desired)
    updated = replace_infrastructure_section(text, render_infrastructure(normalized))
    if updated == text:
        return "reused", normalized
    atomic_write(metadata, updated)
    return "updated", normalized


def main() -> int:
    args = parse_args()
    desired = {
        "application_runtime": args.application_runtime,
        "application_host": args.application_host,
        "application_port": args.application_port,
        "database_runtime": args.database_runtime,
        "database_host": args.database_host,
        "database_port": args.database_port,
        "database_platform": args.database_platform,
        "database_vendor": args.database_vendor,
    }
    try:
        status, normalized = persist(Path(args.repo), desired)
    except DesiredStateError as exc:
        print(f"ERROR={exc}")
        return 2

    print(f"INFRASTRUCTURE_DESIRED_PERSISTENCE={status}")
    print(f"INFRASTRUCTURE_DESIRED_PERSISTED={'true' if status == 'updated' else 'false'}")
    for key in DESIRED_KEYS:
        print(f"DESIRED_{key.upper()}={normalized[key]}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
