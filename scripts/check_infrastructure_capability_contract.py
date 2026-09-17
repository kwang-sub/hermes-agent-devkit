#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "custom-skills/shared/dev-infrastructure/SKILL.md"
DETECTOR = ROOT / "custom-skills/shared/dev-infrastructure/scripts/detect_infrastructure.py"
PLANNER = ROOT / "custom-skills/shared/dev-infrastructure/scripts/plan_transition.py"
CACHE = ROOT / "custom-skills/orchestrator/dev-project-bootstrap/scripts/infrastructure_cache.py"
BREAKDOWN = ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md"
DISPATCH = ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md"
PERSIST = ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/scripts/persist_infrastructure_desired.py"
IMPLEMENT = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"


def require(path: Path, terms: tuple[str, ...]) -> None:
    if not path.is_file():
        raise SystemExit(f"missing required file: {path}")
    text = path.read_text(encoding="utf-8")
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{path} missing contract terms: {', '.join(missing)}")


def main() -> int:
    require(SKILL, (
        "LOCAL_HOST",
        "NETWORK_HOST",
        "CONTAINER",
        "SUPABASE",
        "Desired State",
        "Observed State",
        "HOST_CHANGE",
        "VENDOR_CHANGE",
        "Detach != Destroy",
        "dev-db-migration",
        "Existing Security Findings",
        "New Security Violations Introduced By Task",
    ))
    require(DETECTOR, (
        "is_dockerfile_name",
        "is_compose_name",
        "supabase:provider-env-contract",
        "supabase:database-endpoint",
        'database_platform = "UNKNOWN"',
        "database_host",
        "database_port",
    ))
    require(PLANNER, (
        "INITIAL_CONFIGURATION",
        "RUNTIME_CHANGE",
        "HOST_CHANGE",
        "PLATFORM_CHANGE",
        "VENDOR_CHANGE",
        "DATABASE_HOST",
        "DATABASE_PORT",
        "database-persistent-volume",
        "dev-data-feature",
        "destructive_operations",
    ))
    require(CACHE, (
        'application_runtime: "CONTAINER"',
        'database_runtime: "CONTAINER"',
        'database_platform: "NATIVE"',
        "application_host",
        "database_host",
        "INFRA_ENTRY_CANDIDATE=dev-infrastructure",
        'has_section(text, "infrastructure")',
    ))
    require(BREAKDOWN, (
        "Infrastructure Capability mapping",
        "Infrastructure Impact: YES",
        "dev-infrastructure: runtime/topology/configuration canonical entry",
        "기존 Repository의 하드코딩 설정",
        "dev-db-migration",
    ))
    require(PERSIST, (
        "Persist a user-approved Infrastructure Desired State",
        "atomic_write",
        "application_host",
        "database_host",
        "INFRASTRUCTURE_DESIRED_PERSISTENCE",
    ))
    require(DISPATCH, (
        "persist_infrastructure_desired.py",
        "Infrastructure Impact: YES",
        "Primary Repository",
        "Desired State",
    ))
    require(IMPLEMENT, (
        'skill_view("dev-infrastructure")',
        "첫 production patch 전에 반드시",
        "기존 파일은 preserve-first",
        'skill_view("dev-spring-feature")',
        'skill_view("dev-data-feature")',
        'skill_view("dev-db-migration")',
    ))
    print("PASS: infrastructure capability contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
