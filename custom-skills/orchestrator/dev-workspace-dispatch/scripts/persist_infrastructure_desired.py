#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile

MANAGED_MARKER = "# managed-by: dev-project-bootstrap"
REQUIRED_KEYS = (
    "application_runtime",
    "database_runtime",
    "database_platform",
    "database_vendor",
)
OPTIONAL_KEYS = (
    "application_host",
    "database_host",
    "database_port",
)
RUNTIMES = {"LOCAL_HOST", "NETWORK_HOST", "CONTAINER"}
PLATFORMS = {"NATIVE", "SUPABASE"}
VENDORS = {"postgresql", "mysql", "mariadb", "mssql", "oracle", "unknown"}


class PersistError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Persist an approved Infrastructure Desired State into primary project metadata.")
    p.add_argument("--repo", required=True, help="Primary managed repository root")
    p.add_argument("--application-runtime", required=True, choices=sorted(RUNTIMES))
    p.add_argument("--application-host")
    p.add_argument("--database-runtime", required=True, choices=sorted(RUNTIMES))
    p.add_argument("--database-host")
    p.add_argument("--database-port")
    p.add_argument("--database-platform", required=True, choices=sorted(PLATFORMS))
    p.add_argument("--database-vendor", required=True, choices=sorted(VENDORS))
    return p.parse_args()


def normalize_host(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    host = value.strip()
    if not host or host.lower() == "unknown":
        return None
    if any(char.isspace() for char in host) or "/" in host or "@" in host:
        raise PersistError(f"{label} must be a host/service name only, not a URL or credential-bearing value")
    return host


def normalize_port(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw or raw.lower() == "unknown":
        return None
    if not raw.isdigit():
        raise PersistError("database_port must be an integer between 1 and 65535")
    port = int(raw)
    if not 1 <= port <= 65535:
        raise PersistError("database_port must be an integer between 1 and 65535")
    return str(port)


def normalize(args: argparse.Namespace) -> dict[str, str]:
    result = {
        "application_runtime": args.application_runtime,
        "database_runtime": args.database_runtime,
        "database_platform": args.database_platform,
        "database_vendor": args.database_vendor.strip().lower(),
    }
    application_host = normalize_host(args.application_host, "application_host")
    database_host = normalize_host(args.database_host, "database_host")
    database_port = normalize_port(args.database_port)
    if application_host is not None:
        result["application_host"] = application_host
    if database_host is not None:
        result["database_host"] = database_host
    if database_port is not None:
        result["database_port"] = database_port
    if result["database_platform"] == "SUPABASE":
        result["database_vendor"] = "postgresql"
    return result


def metadata_file(repo: Path) -> Path:
    return repo / ".hermes" / "project.yaml"


def validate_metadata(path: Path) -> str:
    if not path.is_file():
        raise PersistError(f"project metadata is missing: {path}")
    text = path.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise PersistError(f"project metadata is not managed by dev-project-bootstrap: {path}")
    if not re.search(r"(?m)^infrastructure:\s*$", text):
        raise PersistError("infrastructure section is missing; run dev-project-bootstrap --refresh-stack first")
    return text


def desired_block(desired: dict[str, str]) -> str:
    lines = ["  desired:"]
    for key in (*REQUIRED_KEYS, *OPTIONAL_KEYS):
        if key in desired:
            lines.append(f"    {key}: {json.dumps(desired[key], ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def replace_desired(text: str, desired: dict[str, str]) -> str:
    pattern = re.compile(r"(?ms)^  desired:\s*\n(?:    [^\n]*\n?)*")
    match = pattern.search(text)
    if not match:
        raise PersistError("infrastructure.desired block is missing or malformed")
    return text[: match.start()] + desired_block(desired) + text[match.end() :]


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def persist(repo: Path, desired: dict[str, str]) -> str:
    path = metadata_file(repo)
    original = validate_metadata(path)
    updated = replace_desired(original, desired)
    if updated == original:
        return "unchanged"
    atomic_write(path, updated)
    return "updated"


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"ERROR=repository not found: {repo}")
        return 2
    try:
        desired = normalize(args)
        status = persist(repo, desired)
    except PersistError as exc:
        print(f"ERROR={exc}")
        return 2

    print(f"INFRASTRUCTURE_DESIRED_PERSIST={status}")
    for key in (*REQUIRED_KEYS, *OPTIONAL_KEYS):
        if key in desired:
            print(f"{key.upper()}={desired[key]}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
