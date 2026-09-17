#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


RUNTIMES = {"LOCAL_HOST", "NETWORK_HOST", "CONTAINER", "UNKNOWN"}
PLATFORMS = {"NATIVE", "SUPABASE", "UNKNOWN"}
VENDORS = {"postgresql", "mysql", "mariadb", "mssql", "oracle", "UNKNOWN"}
COMPOSE_NAMES = ("compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml")
ENV_NAMES = (".env.example",)
MAX_DEPTH = 3


class InfrastructureDetectionError(RuntimeError):
    pass


def relative_depth(root: Path, path: Path) -> int:
    return len(path.relative_to(root).parts)


def bounded_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    ignored = {".git", "node_modules", "build", "target", ".next", "dist", "vendor"}
    for path in repo.rglob("*"):
        try:
            rel = path.relative_to(repo)
        except ValueError:
            continue
        if any(part in ignored for part in rel.parts):
            continue
        if path.is_dir():
            continue
        if relative_depth(repo, path) > MAX_DEPTH + 1:
            continue
        name = path.name
        if (
            name == "Dockerfile"
            or name.endswith(".Dockerfile")
            or name in COMPOSE_NAMES
            or name in ENV_NAMES
            or (name == "config.toml" and "supabase" in rel.parts)
            or (name.startswith("application") and path.suffix in {".yml", ".yaml", ".properties"})
            or name in {"build.gradle", "build.gradle.kts", "pom.xml", "package.json", "schema.prisma"}
        ):
            files.append(path)
    return sorted(files)


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def detect_vendor(text: str) -> set[str]:
    lower = text.lower()
    found: set[str] = set()
    if any(token in lower for token in ("postgresql", "postgres:", "r2dbc:postgres", "jdbc:postgresql", "org.postgresql", "@supabase/")):
        found.add("postgresql")
    if any(token in lower for token in ("mariadb", "jdbc:mariadb", "org.mariadb")):
        found.add("mariadb")
    if any(token in lower for token in ("mysql", "jdbc:mysql", "com.mysql")):
        found.add("mysql")
    if any(token in lower for token in ("sqlserver", "mssql", "jdbc:sqlserver", "r2dbc:mssql")):
        found.add("mssql")
    if any(token in lower for token in ("oracle", "jdbc:oracle", "ojdbc")):
        found.add("oracle")
    return found


def compose_service_names(text: str) -> set[str]:
    names: set[str] = set()
    in_services = False
    for line in text.splitlines():
        if re.match(r"^services:\s*$", line):
            in_services = True
            continue
        if in_services and re.match(r"^[A-Za-z0-9_.-]+:\s*$", line):
            break
        match = re.match(r"^\s{2}([A-Za-z0-9_.-]+):\s*$", line) if in_services else None
        if match:
            names.add(match.group(1))
    return names


def database_endpoint_hosts(text: str) -> set[str]:
    lower = text.lower()
    patterns = (
        r"(?:jdbc|r2dbc):[a-z0-9]+://([^/:;?\s]+)",
        r"(?:postgres(?:ql)?|mysql|mariadb|mssql|sqlserver|oracle)(?:\+[a-z0-9]+)?://([^/:;?\s]+)",
    )
    hosts: set[str] = set()
    for pattern in patterns:
        hosts.update(match.group(1) for match in re.finditer(pattern, lower))
    return hosts


def has_supabase_remote(text: str) -> bool:
    lower = text.lower()
    return "supabase.co" in lower or "supabase.com" in lower or bool(
        re.search(r"(?m)^\s*(?:next_public_)?supabase_url\s*[=:]", lower)
    )


def infer_state(repo: Path) -> dict[str, Any]:
    files = bounded_files(repo)
    inputs = [str(path.relative_to(repo)).replace("\\", "/") for path in files]

    compose_files = [p for p in files if p.name in COMPOSE_NAMES]
    dockerfiles = [p for p in files if p.name == "Dockerfile" or p.name.endswith(".Dockerfile")]
    supabase_configs = [p for p in files if p.name == "config.toml" and "supabase" in p.relative_to(repo).parts]

    compose_text = "\n".join(safe_read(p) for p in compose_files)
    all_text = "\n".join(safe_read(p) for p in files)
    services = compose_service_names(compose_text)
    vendors = detect_vendor(all_text)
    db_hosts = database_endpoint_hosts(all_text)
    supabase_remote = has_supabase_remote(all_text)

    application_runtime = "UNKNOWN"
    if dockerfiles or any(name in services for name in ("app", "application", "backend", "frontend", "api", "web")):
        application_runtime = "CONTAINER"

    if supabase_configs or supabase_remote:
        database_platform = "SUPABASE"
        vendors.add("postgresql")
    elif vendors or db_hosts:
        database_platform = "NATIVE"
    else:
        database_platform = "UNKNOWN"

    database_runtime = "UNKNOWN"
    db_service_tokens = {"postgres", "postgresql", "db", "database", "mysql", "mariadb", "mssql", "sqlserver", "oracle"}
    if services.intersection(db_service_tokens) or db_hosts.intersection(services):
        database_runtime = "CONTAINER"
    elif database_platform == "SUPABASE" and supabase_configs:
        database_runtime = "CONTAINER"
    elif supabase_remote:
        database_runtime = "NETWORK_HOST"
    elif db_hosts.intersection({"localhost", "127.0.0.1", "::1"}):
        database_runtime = "LOCAL_HOST"
    elif db_hosts:
        database_runtime = "NETWORK_HOST"

    if len(vendors) == 1:
        database_vendor = next(iter(vendors))
    else:
        database_vendor = "UNKNOWN"

    confidence = "HIGH"
    if application_runtime == "UNKNOWN" or database_runtime == "UNKNOWN":
        confidence = "PARTIAL"

    return {
        "application_runtime": application_runtime,
        "database_runtime": database_runtime,
        "database_platform": database_platform,
        "database_vendor": database_vendor,
        "database_vendor_candidates": sorted(vendors),
        "database_endpoint_hosts": sorted(db_hosts),
        "inputs": inputs,
        "compose_services": sorted(services),
        "confidence": confidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect bounded application/database infrastructure runtime evidence")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"ERROR=repository not found: {repo}", file=sys.stderr)
        return 2

    result = infer_state(repo)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"APPLICATION_RUNTIME={result['application_runtime']}")
    print(f"DATABASE_RUNTIME={result['database_runtime']}")
    print(f"DATABASE_PLATFORM={result['database_platform']}")
    print(f"DATABASE_VENDOR={result['database_vendor']}")
    print(f"DATABASE_VENDOR_CANDIDATES={','.join(result['database_vendor_candidates'])}")
    print(f"DATABASE_ENDPOINT_HOSTS={','.join(result['database_endpoint_hosts'])}")
    print(f"INFRA_INPUTS={','.join(result['inputs'])}")
    print(f"COMPOSE_SERVICES={','.join(result['compose_services'])}")
    print(f"CONFIDENCE={result['confidence']}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
