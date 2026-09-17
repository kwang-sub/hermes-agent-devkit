#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


RUNTIMES = {"LOCAL_HOST", "NETWORK_HOST", "CONTAINER", "UNKNOWN"}
PLATFORMS = {"NATIVE", "SUPABASE", "UNKNOWN"}
VENDORS = {"postgresql", "mysql", "mariadb", "mssql", "oracle", "UNKNOWN"}
COMPOSE_NAMES = ("compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml")
ENV_NAMES = (".env.example",)
MAX_DIRECTORY_DEPTH = 5
LOCAL_DATABASE_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "host.docker.internal",
    "gateway.docker.internal",
}
SUPABASE_DATABASE_HOST_SUFFIXES = (".supabase.co", ".supabase.com")


class InfrastructureDetectionError(RuntimeError):
    pass


def is_relevant_file(path: Path, repo: Path) -> bool:
    rel = path.relative_to(repo)
    name = path.name
    return (
        name == "Dockerfile"
        or name.endswith(".Dockerfile")
        or name in COMPOSE_NAMES
        or name in ENV_NAMES
        or (name == "config.toml" and "supabase" in rel.parts)
        or (name.startswith("application") and path.suffix in {".yml", ".yaml", ".properties"})
        or name in {"build.gradle", "build.gradle.kts", "pom.xml", "package.json", "schema.prisma"}
    )


def bounded_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    ignored = {".git", "node_modules", "build", "target", ".next", "dist", "vendor", ".gradle"}

    for root_text, dirs, names in os.walk(repo, topdown=True):
        root = Path(root_text)
        depth = len(root.relative_to(repo).parts)
        dirs[:] = [name for name in dirs if name not in ignored]
        if depth >= MAX_DIRECTORY_DEPTH:
            dirs[:] = []

        for name in names:
            path = root / name
            if is_relevant_file(path, repo):
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
    if any(token in lower for token in ("postgresql", "postgres:", "r2dbc:postgres", "jdbc:postgresql", "org.postgresql")):
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
    service_indent: int | None = None

    for line in text.splitlines():
        if re.match(r"^services:\s*(?:#.*)?$", line):
            in_services = True
            service_indent = None
            continue
        if not in_services or not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            break

        match = re.match(r"^(\s+)([A-Za-z0-9_.-]+):\s*(?:#.*)?$", line)
        if not match:
            continue
        indent = len(match.group(1).replace("\t", "    "))
        if service_indent is None:
            service_indent = indent
        if indent == service_indent:
            names.add(match.group(2))

    return names


def is_placeholder_host(host: str) -> bool:
    return any(token in host for token in ("$", "{", "}", "%"))


def database_endpoint_hosts(text: str) -> set[str]:
    lower = text.lower()
    patterns = (
        r"(?:jdbc|r2dbc):[a-z0-9]+://(?:(?:[^@/\s]+)@)?([^/:;?\s]+)",
        r"(?:postgres(?:ql)?|mysql|mariadb|mssql|sqlserver|oracle)(?:\+[a-z0-9]+)?://(?:(?:[^@/\s]+)@)?([^/:;?\s]+)",
    )
    hosts: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, lower):
            host = match.group(1).strip("[]")
            if host and not is_placeholder_host(host):
                hosts.add(host)
    return hosts


def is_supabase_database_host(host: str) -> bool:
    lowered = host.lower().rstrip(".")
    return lowered.endswith(SUPABASE_DATABASE_HOST_SUFFIXES)


def database_runtime_candidates(
    *,
    services: set[str],
    db_hosts: set[str],
    supabase_configs: list[Path],
) -> set[str]:
    candidates: set[str] = set()
    db_service_tokens = {"postgres", "postgresql", "db", "database", "mysql", "mariadb", "mssql", "sqlserver", "oracle"}

    if services.intersection(db_service_tokens):
        candidates.add("CONTAINER")
    if supabase_configs:
        candidates.add("CONTAINER")

    for host in db_hosts:
        if host in services:
            candidates.add("CONTAINER")
        elif host in LOCAL_DATABASE_HOSTS:
            candidates.add("LOCAL_HOST")
        else:
            candidates.add("NETWORK_HOST")

    return candidates


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
    supabase_db_hosts = {host for host in db_hosts if is_supabase_database_host(host)}
    supabase_database_evidence = bool(supabase_configs or supabase_db_hosts)

    application_runtime = "UNKNOWN"
    if dockerfiles or any(name in services for name in ("app", "application", "backend", "frontend", "api", "web")):
        application_runtime = "CONTAINER"

    if supabase_database_evidence:
        database_platform = "SUPABASE"
        vendors.add("postgresql")
    elif vendors or db_hosts:
        database_platform = "NATIVE"
    else:
        database_platform = "UNKNOWN"

    runtime_candidates = database_runtime_candidates(
        services=services,
        db_hosts=db_hosts,
        supabase_configs=supabase_configs,
    )
    database_runtime = next(iter(runtime_candidates)) if len(runtime_candidates) == 1 else "UNKNOWN"

    if len(vendors) == 1:
        database_vendor = next(iter(vendors))
    else:
        database_vendor = "UNKNOWN"

    confidence = "HIGH"
    if application_runtime == "UNKNOWN" or database_runtime == "UNKNOWN" or len(runtime_candidates) > 1:
        confidence = "PARTIAL"

    return {
        "application_runtime": application_runtime,
        "database_runtime": database_runtime,
        "database_runtime_candidates": sorted(runtime_candidates),
        "database_platform": database_platform,
        "database_vendor": database_vendor,
        "database_vendor_candidates": sorted(vendors),
        "database_endpoint_hosts": sorted(db_hosts),
        "supabase_database_hosts": sorted(supabase_db_hosts),
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
    print(f"DATABASE_RUNTIME_CANDIDATES={','.join(result['database_runtime_candidates'])}")
    print(f"DATABASE_PLATFORM={result['database_platform']}")
    print(f"DATABASE_VENDOR={result['database_vendor']}")
    print(f"DATABASE_VENDOR_CANDIDATES={','.join(result['database_vendor_candidates'])}")
    print(f"DATABASE_ENDPOINT_HOSTS={','.join(result['database_endpoint_hosts'])}")
    print(f"SUPABASE_DATABASE_HOSTS={','.join(result['supabase_database_hosts'])}")
    print(f"INFRA_INPUTS={','.join(result['inputs'])}")
    print(f"COMPOSE_SERVICES={','.join(result['compose_services'])}")
    print(f"CONFIDENCE={result['confidence']}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
