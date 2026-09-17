#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "custom-skills/shared/dev-infrastructure/SKILL.md"
DETECTOR = ROOT / "custom-skills/shared/dev-infrastructure/scripts/detect_infrastructure.py"
PLANNER = ROOT / "custom-skills/shared/dev-infrastructure/scripts/plan_transition.py"
CACHE = ROOT / "custom-skills/orchestrator/dev-project-bootstrap/scripts/infrastructure_cache.py"


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
        "VENDOR_CHANGE",
        "Detach != Destroy",
        "dev-db-migration",
    ))
    require(DETECTOR, (
        "compose.yml",
        "supabase",
        "NETWORK_HOST",
        "CONTAINER",
        "database_vendor",
    ))
    require(PLANNER, (
        "RUNTIME_CHANGE",
        "PLATFORM_CHANGE",
        "VENDOR_CHANGE",
        "database-persistent-volume",
        "dev-data-feature",
        "destructive_operations",
    ))
    require(CACHE, (
        'application_runtime: "CONTAINER"',
        'database_runtime: "CONTAINER"',
        "INFRA_ENTRY_CANDIDATE=dev-infrastructure",
        'has_section(text, "infrastructure")',
    ))
    print("PASS: infrastructure capability contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
