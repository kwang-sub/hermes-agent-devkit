#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "custom-skills/shared/dev-infrastructure/SKILL.md"
DETECTOR = ROOT / "custom-skills/shared/dev-infrastructure/scripts/detect_infrastructure.py"
PLANNER = ROOT / "custom-skills/shared/dev-infrastructure/scripts/plan_transition.py"
CACHE = ROOT / "custom-skills/orchestrator/dev-project-bootstrap/scripts/infrastructure_cache.py"
BREAKDOWN = ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md"
IMPLEMENT = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"
DISPATCH = ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md"
PERSIST = ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/scripts/persist_infrastructure_desired.py"


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
        "INITIAL_CONFIGURATION",
        "HOST_CHANGE",
        "VENDOR_CHANGE",
        "Supabase provider 사용 evidence",
        "Existing Security Findings",
        "New Security Violations Introduced By Task",
        "Detach != Destroy",
        "dev-db-migration",
    ))
    require(DETECTOR, (
        "Dockerfile.*",
        "compose.*.yml",
        "valid_compose",
        "supabase:provider-env-contract",
        "SUPABASE_DB_URL",
        "database_host",
        "database_port",
        'database_platform = "UNKNOWN"',
    ))
    require(PLANNER, (
        "INITIAL_CONFIGURATION",
        "RUNTIME_CHANGE",
        "HOST_CHANGE",
        "PLATFORM_CHANGE",
        "VENDOR_CHANGE",
        "database_host",
        "database_port",
        "database-persistent-volume",
        "dev-data-feature",
        "destructive_operations",
    ))
    require(CACHE, (
        'application_runtime: "CONTAINER"',
        'database_runtime: "CONTAINER"',
        "OPTIONAL_DESIRED_KEYS",
        "database_host",
        "database_port",
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
    require(IMPLEMENT, (
        'skill_view("dev-infrastructure")',
        "첫 production patch 전에 반드시",
        "기존 파일은 preserve-first",
        'skill_view("dev-spring-feature")',
        'skill_view("dev-data-feature")',
        'skill_view("dev-db-migration")',
    ))
    require(DISPATCH, (
        "Infrastructure Desired State Persistence",
        "persist_infrastructure_desired.py",
        "PROJECT_REPOSITORY",
        "infrastructure.desired 블록만 atomic replace",
        "Infrastructure Impact: YES",
        "Desired Persist: UPDATED | UNCHANGED | NOT_REQUIRED",
    ))
    require(PERSIST, (
        "application_runtime",
        "application_host",
        "database_runtime",
        "database_host",
        "database_port",
        "database_platform",
        "database_vendor",
        "atomic_write",
        "os.replace",
    ))
    print("PASS: infrastructure capability contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
