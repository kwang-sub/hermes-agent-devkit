#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import re
from typing import Iterable

IGNORED_DIRS = {".git", "node_modules", "build", "target", ".next", "dist", "vendor", ".gradle"}
ENV_HINT_NAMES = {".env.example", ".env.sample", "sample.env"}
DOCKERFILE_PATTERNS = ("Dockerfile", "Dockerfile.*", "dockerfile", "dockerfile.*")
COMPOSE_PATTERNS = (
    "compose.yml",
    "compose.yaml",
    "compose.*.yml",
    "compose.*.yaml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "docker-compose.*.yml",
    "docker-compose.*.yaml",
)
SPRING_CONFIG_PATTERNS = ("application*.yml", "application*.yaml", "application*.properties")
SUPABASE_PROVIDER_KEYS = {"SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"}
SUPABASE_DATABASE_KEYS = {"SUPABASE_DB_URL", "SUPABASE_DATABASE_URL"}
DB_IMAGES = {
    "postgres": "postgresql",
    "postgis": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "mcr.microsoft.com/mssql": "mssql",
    "oracle": "oracle",
}
JDBC_URL_RE = re.compile(
    r"jdbc:(?P<vendor>postgresql|mysql|mariadb|sqlserver|oracle):(?://)?(?P<host>[^:/;\s]+)?(?::(?P<port>\d+))?",
    flags=re.IGNORECASE,
)


def bounded_files(repo: Path, *, names: set[str] | None = None, patterns: tuple[str, ...] = (), max_depth: int = 3) -> Iterable[Path]:
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo)
        if len(rel.parts) > max_depth + 1:
            continue
        if any(part in IGNORED_DIRS for part in rel.parts[:-1]):
            continue
        if names and path.name in names:
            yield path
            continue
        if patterns and any(fnmatch.fnmatchcase(path.name, pattern) for pattern in patterns):
            yield path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def infer_vendor(text: str) -> str:
    lowered = text.lower()
    for marker, vendor in DB_IMAGES.items():
        if marker in lowered:
            return vendor
    return "unknown"


def valid_compose(path: Path) -> bool:
    text = read_text(path)
    return bool(re.search(r"(?m)^\s*services\s*:\s*(?:#.*)?$", text))


def env_keys(text: str) -> set[str]:
    result: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match:
            result.add(match.group(1).upper())
    return result


def infer_jdbc_endpoint(text: str) -> tuple[str, str, str]:
    match = JDBC_URL_RE.search(text)
    if not match:
        return "unknown", "unknown", "unknown"
    vendor = match.group("vendor").lower()
    vendor = "mssql" if vendor == "sqlserver" else vendor
    host = (match.group("host") or "unknown").strip()
    port = (match.group("port") or "unknown").strip()
    return vendor, host, port


def detect(repo: Path) -> dict[str, object]:
    compose_candidates = list(bounded_files(repo, patterns=COMPOSE_PATTERNS))
    compose_files = [path for path in compose_candidates if valid_compose(path)]
    dockerfiles = list(bounded_files(repo, patterns=DOCKERFILE_PATTERNS))
    env_files = list(bounded_files(repo, names=ENV_HINT_NAMES))
    spring_configs = list(bounded_files(repo, patterns=SPRING_CONFIG_PATTERNS, max_depth=5))
    supabase_config = repo / "supabase" / "config.toml"

    evidence: list[str] = []
    application_runtime = "UNKNOWN"
    application_host = "unknown"
    database_runtime = "UNKNOWN"
    database_platform = "UNKNOWN"
    database_vendor = "unknown"
    database_host = "unknown"
    database_port = "unknown"
    application_status = "UNKNOWN"
    database_status = "UNKNOWN"

    compose_text = "\n".join(read_text(path) for path in compose_files)
    env_text = "\n".join(read_text(path) for path in env_files)
    spring_text = "\n".join(read_text(path) for path in spring_configs)
    contract_keys = env_keys(env_text)

    if dockerfiles or compose_files:
        application_runtime = "CONTAINER"
        application_status = "READY" if dockerfiles and compose_files else "PARTIAL"
        for path in dockerfiles:
            evidence.append(f"dockerfile:{path.relative_to(repo)}")
        for path in compose_files:
            evidence.append(f"compose:{path.relative_to(repo)}")

    for path in compose_candidates:
        if path not in compose_files:
            evidence.append(f"compose-invalid:{path.relative_to(repo)}")

    compose_vendor = infer_vendor(compose_text)
    if compose_vendor != "unknown":
        database_runtime = "CONTAINER"
        database_platform = "NATIVE"
        database_vendor = compose_vendor
        database_status = "READY"
        evidence.append(f"compose-db-vendor:{compose_vendor}")

    jdbc_vendor, jdbc_host, jdbc_port = infer_jdbc_endpoint(spring_text)
    if jdbc_vendor != "unknown":
        if database_vendor == "unknown":
            database_vendor = jdbc_vendor
        if database_platform == "UNKNOWN":
            database_platform = "NATIVE"
        if database_runtime == "UNKNOWN":
            database_runtime = "NETWORK_HOST" if jdbc_host not in {"unknown", "localhost", "127.0.0.1"} else "LOCAL_HOST"
            database_status = "PARTIAL"
        database_host = jdbc_host
        database_port = jdbc_port
        evidence.append(f"jdbc-db-vendor:{jdbc_vendor}")
        if jdbc_host != "unknown":
            evidence.append(f"jdbc-db-host:{jdbc_host}")

    if supabase_config.is_file():
        database_runtime = "CONTAINER"
        database_platform = "SUPABASE"
        database_vendor = "postgresql"
        database_status = "READY"
        evidence.append("supabase:config.toml")
    elif contract_keys & SUPABASE_DATABASE_KEYS:
        database_runtime = "NETWORK_HOST"
        database_platform = "SUPABASE"
        database_vendor = "postgresql"
        database_status = "PARTIAL"
        evidence.append("supabase:remote-db-contract")
    elif contract_keys & SUPABASE_PROVIDER_KEYS:
        evidence.append("supabase:provider-env-contract")

    if application_runtime == "UNKNOWN":
        application_status = "NOT_CONFIGURED"
    if database_runtime == "UNKNOWN":
        database_status = "NOT_CONFIGURED"

    return {
        "application_runtime": application_runtime,
        "application_host": application_host,
        "application_status": application_status,
        "database_runtime": database_runtime,
        "database_host": database_host,
        "database_port": database_port,
        "database_platform": database_platform,
        "database_vendor": database_vendor,
        "database_status": database_status,
        "evidence": sorted(evidence),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect bounded infrastructure runtime evidence")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        raise SystemExit(f"repository not found: {repo}")
    result = detect(repo)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key, value in result.items():
            if isinstance(value, list):
                value = ",".join(value)
            print(f"{key.upper()}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
