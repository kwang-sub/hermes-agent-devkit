#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Iterable
from urllib.parse import urlparse

IGNORED_DIRS = {".git", "node_modules", "build", "target", ".next", "dist", "vendor", ".gradle"}
DB_IMAGES = {
    "postgres": "postgresql",
    "postgis": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "mcr.microsoft.com/mssql": "mssql",
    "oracle": "oracle",
}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
SUPABASE_PROVIDER_KEYS = {"SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"}
SUPABASE_DB_KEYS = {"SUPABASE_DB_URL", "SUPABASE_DATABASE_URL"}
DB_URL_KEYS = {"DATABASE_URL", "DB_URL", "SPRING_DATASOURCE_URL"}
DB_HOST_KEYS = {"DATABASE_HOST", "DB_HOST"}
DB_PORT_KEYS = {"DATABASE_PORT", "DB_PORT"}
APP_HOST_KEYS = {"APPLICATION_HOST", "APP_HOST", "SERVER_ADDRESS"}
APP_PORT_KEYS = {"APPLICATION_PORT", "APP_PORT", "SERVER_PORT"}


def bounded_files(repo: Path, predicate, max_depth: int = 6) -> Iterable[Path]:
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo)
        if len(rel.parts) > max_depth + 1:
            continue
        if any(part in IGNORED_DIRS for part in rel.parts[:-1]):
            continue
        if predicate(path.name):
            yield path


def is_dockerfile_name(name: str) -> bool:
    return re.fullmatch(r"dockerfile(?:[._-].+)?", name, flags=re.IGNORECASE) is not None


def is_compose_name(name: str) -> bool:
    lowered = name.lower()
    return (
        re.fullmatch(r"compose(?:[._-].+)?\.ya?ml", lowered) is not None
        or re.fullmatch(r"docker-compose(?:[._-].+)?\.ya?ml", lowered) is not None
    )


def is_env_name(name: str) -> bool:
    if name == "sample.env":
        return True
    return re.fullmatch(r"\.env(?:\.[A-Za-z0-9_-]+)*(?:\.local)?", name) is not None


def is_spring_config_name(name: str) -> bool:
    return re.fullmatch(r"application(?:-[A-Za-z0-9_.-]+)?\.(?:ya?ml|properties)", name) is not None


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def meaningful_dockerfile(path: Path) -> bool:
    return re.search(r"(?im)^\s*FROM\s+\S+", read_text(path)) is not None


def meaningful_compose(path: Path) -> bool:
    return re.search(r"(?m)^services:\s*(?:#.*)?$", read_text(path)) is not None


def infer_vendor(text: str) -> str:
    lowered = text.lower()
    jdbc_markers = {
        "jdbc:postgresql:": "postgresql",
        "jdbc:mysql:": "mysql",
        "jdbc:mariadb:": "mariadb",
        "jdbc:sqlserver:": "mssql",
        "jdbc:oracle:": "oracle",
    }
    for marker, vendor in jdbc_markers.items():
        if marker in lowered:
            return vendor
    for marker, vendor in DB_IMAGES.items():
        if marker in lowered:
            return vendor
    return "unknown"


def normalized_value(value: str) -> str | None:
    candidate = value.strip().strip("'\"")
    if not candidate:
        return None
    if candidate.startswith("${") or candidate.startswith("#{"):
        return None
    lowered = candidate.lower()
    if lowered in {"null", "none", "changeme", "example", "placeholder"}:
        return None
    return candidate


def env_values(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        candidate = normalized_value(value)
        if key.strip() and candidate is not None:
            result[key.strip().upper()] = candidate
    return result


def spring_values(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    property_patterns = {
        "SPRING_DATASOURCE_URL": r"(?mi)^\s*spring\.datasource\.url\s*[:=]\s*(.+?)\s*$",
        "SERVER_ADDRESS": r"(?mi)^\s*server\.address\s*[:=]\s*(.+?)\s*$",
        "SERVER_PORT": r"(?mi)^\s*server\.port\s*[:=]\s*(.+?)\s*$",
    }
    for key, pattern in property_patterns.items():
        match = re.search(pattern, text)
        if match:
            candidate = normalized_value(match.group(1))
            if candidate is not None:
                result[key] = candidate

    jdbc = re.search(r"(?i)jdbc:(?:postgresql|mysql|mariadb|sqlserver|oracle)[^\s'\"]+", text)
    if jdbc and "SPRING_DATASOURCE_URL" not in result:
        result["SPRING_DATASOURCE_URL"] = jdbc.group(0).rstrip(",")
    return result


def first_value(values: dict[str, str], keys: set[str]) -> str | None:
    for key in sorted(keys):
        value = values.get(key)
        if value:
            return value
    return None


def parse_endpoint(value: str) -> tuple[str | None, str | None]:
    raw = value.strip().strip("'\"")
    if not raw:
        return None, None

    lowered = raw.lower()
    if lowered.startswith("jdbc:oracle:thin:@//"):
        raw = "//" + raw.split("@//", 1)[1]
    elif lowered.startswith("jdbc:oracle:thin:@"):
        tail = raw.split("@", 1)[1]
        match = re.match(r"([^:/;]+):(\d+)", tail)
        return (match.group(1), match.group(2)) if match else (None, None)
    elif lowered.startswith("jdbc:"):
        raw = raw[len("jdbc:"):]
        scheme_end = raw.find(":")
        if scheme_end >= 0:
            raw = raw[scheme_end + 1 :]

    if raw.startswith("//"):
        parsed = urlparse("scheme:" + raw)
    elif "://" in raw:
        parsed = urlparse(raw)
    else:
        match = re.match(r"([^:/;]+)(?::(\d+))?", raw)
        return (match.group(1), match.group(2)) if match else (None, None)

    try:
        port = str(parsed.port) if parsed.port is not None else None
    except ValueError:
        port = None
    return parsed.hostname, port


def runtime_for_database_host(host: str) -> str:
    return "LOCAL_HOST" if host.lower() in LOCAL_HOSTS else "NETWORK_HOST"


def detect(repo: Path) -> dict[str, object]:
    dockerfiles = [path for path in bounded_files(repo, is_dockerfile_name, max_depth=4) if meaningful_dockerfile(path)]
    compose_files = [path for path in bounded_files(repo, is_compose_name, max_depth=4) if meaningful_compose(path)]
    env_files = list(bounded_files(repo, is_env_name, max_depth=4))
    spring_files = list(bounded_files(repo, is_spring_config_name, max_depth=6))
    supabase_config = repo / "supabase" / "config.toml"

    evidence: list[str] = []
    application_runtime = "UNKNOWN"
    database_runtime = "UNKNOWN"
    database_platform = "UNKNOWN"
    database_vendor = "unknown"
    application_status = "UNKNOWN"
    database_status = "UNKNOWN"
    application_host = "unknown"
    application_port = "unknown"
    database_host = "unknown"
    database_port = "unknown"

    compose_text = "\n".join(read_text(path) for path in compose_files)
    env_data: dict[str, str] = {}
    for path in env_files:
        env_data.update(env_values(read_text(path)))
    spring_data: dict[str, str] = {}
    for path in spring_files:
        spring_data.update(spring_values(read_text(path)))
    config_data = {**env_data, **spring_data}

    if dockerfiles or compose_files:
        application_runtime = "CONTAINER"
        application_status = "READY" if dockerfiles and compose_files else "PARTIAL"
        for path in dockerfiles:
            evidence.append(f"dockerfile:{path.relative_to(repo)}")
        for path in compose_files:
            evidence.append(f"compose:{path.relative_to(repo)}")

    compose_vendor = infer_vendor(compose_text)
    if compose_vendor != "unknown":
        database_runtime = "CONTAINER"
        database_platform = "NATIVE"
        database_vendor = compose_vendor
        database_status = "READY"
        evidence.append(f"compose-db-vendor:{compose_vendor}")

    app_host_value = first_value(config_data, APP_HOST_KEYS)
    app_port_value = first_value(config_data, APP_PORT_KEYS)
    if app_host_value:
        application_host = app_host_value
        evidence.append("application-host:config")
    if app_port_value and app_port_value.isdigit():
        application_port = app_port_value
        evidence.append("application-port:config")

    db_url = first_value(config_data, DB_URL_KEYS | SUPABASE_DB_KEYS)
    db_host_value = first_value(config_data, DB_HOST_KEYS)
    db_port_value = first_value(config_data, DB_PORT_KEYS)
    if db_url:
        host, port = parse_endpoint(db_url)
        if host:
            database_host = host
        if port:
            database_port = port
        url_vendor = infer_vendor(db_url)
        if url_vendor != "unknown" and database_vendor == "unknown":
            database_vendor = url_vendor
        if host and database_runtime == "UNKNOWN":
            database_runtime = runtime_for_database_host(host)
            database_status = "PARTIAL"
        if host and "supabase.co" in host.lower():
            database_platform = "SUPABASE"
            database_vendor = "postgresql"
            evidence.append("supabase:database-endpoint")
        elif database_vendor != "unknown" and database_platform == "UNKNOWN":
            database_platform = "NATIVE"
        evidence.append("database-url:config")
    else:
        if db_host_value:
            database_host = db_host_value
            if database_runtime == "UNKNOWN":
                database_runtime = runtime_for_database_host(db_host_value)
                database_status = "PARTIAL"
            evidence.append("database-host:config")
        if db_port_value and db_port_value.isdigit():
            database_port = db_port_value
            evidence.append("database-port:config")

    if supabase_config.is_file():
        database_runtime = "CONTAINER"
        database_platform = "SUPABASE"
        database_vendor = "postgresql"
        database_status = "READY"
        evidence.append("supabase:config.toml")
    elif any(key in env_data for key in SUPABASE_PROVIDER_KEYS):
        # Supabase Auth/API usage alone is not evidence that the application database
        # itself is hosted by Supabase. Keep it as provider evidence only.
        evidence.append("supabase:provider-env-contract")

    if database_platform == "UNKNOWN" and database_vendor != "unknown":
        database_platform = "NATIVE"

    if application_runtime == "UNKNOWN":
        application_status = "NOT_CONFIGURED"
    if database_runtime == "UNKNOWN":
        database_status = "NOT_CONFIGURED"

    return {
        "application_runtime": application_runtime,
        "application_host": application_host,
        "application_port": application_port,
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
