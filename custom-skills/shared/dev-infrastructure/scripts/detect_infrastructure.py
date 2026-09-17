#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

IGNORED_DIRS = {".git", "node_modules", "build", "target", ".next", "dist", "vendor", ".gradle"}
COMPOSE_NAMES = {"compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"}
ENV_HINT_NAMES = {".env.example", ".env.sample", "sample.env"}
DB_IMAGES = {
    "postgres": "postgresql",
    "postgis": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "mcr.microsoft.com/mssql": "mssql",
    "oracle": "oracle",
}


def bounded_files(repo: Path, names: set[str], max_depth: int = 3) -> Iterable[Path]:
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo)
        if len(rel.parts) > max_depth + 1:
            continue
        if any(part in IGNORED_DIRS for part in rel.parts[:-1]):
            continue
        if path.name in names:
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


def detect(repo: Path) -> dict[str, object]:
    compose_files = list(bounded_files(repo, COMPOSE_NAMES))
    dockerfiles = list(bounded_files(repo, {"Dockerfile", "dockerfile"}))
    env_files = list(bounded_files(repo, ENV_HINT_NAMES))
    supabase_config = repo / "supabase" / "config.toml"

    evidence: list[str] = []
    application_runtime = "UNKNOWN"
    database_runtime = "UNKNOWN"
    database_platform = "NATIVE"
    database_vendor = "unknown"
    application_status = "UNKNOWN"
    database_status = "UNKNOWN"

    compose_text = "\n".join(read_text(path) for path in compose_files)
    env_text = "\n".join(read_text(path) for path in env_files)

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
        database_vendor = compose_vendor
        database_status = "READY"
        evidence.append(f"compose-db-vendor:{compose_vendor}")

    if supabase_config.is_file():
        database_runtime = "CONTAINER"
        database_platform = "SUPABASE"
        database_vendor = "postgresql"
        database_status = "READY"
        evidence.append("supabase:config.toml")
    elif "SUPABASE_URL" in env_text.upper() or "NEXT_PUBLIC_SUPABASE_URL" in env_text.upper():
        database_runtime = "NETWORK_HOST"
        database_platform = "SUPABASE"
        database_vendor = "postgresql"
        database_status = "PARTIAL"
        evidence.append("supabase:remote-env-contract")

    if application_runtime == "UNKNOWN":
        application_status = "NOT_CONFIGURED"
    if database_runtime == "UNKNOWN":
        database_status = "NOT_CONFIGURED"

    return {
        "application_runtime": application_runtime,
        "application_status": application_status,
        "database_runtime": database_runtime,
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
