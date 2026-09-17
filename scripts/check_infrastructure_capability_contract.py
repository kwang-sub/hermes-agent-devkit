#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(path: Path, terms: tuple[str, ...]) -> None:
    if not path.is_file():
        raise SystemExit(f"missing file: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(
            f"{path.relative_to(ROOT)} missing infrastructure contract terms: "
            + ", ".join(missing)
        )


def main() -> int:
    require(
        ROOT / "custom-skills/shared/dev-infrastructure/SKILL.md",
        (
            "Application Runtime",
            "Database Runtime",
            "CONTAINER        # 신규/미설정 프로젝트 기본값",
            "Database Platform",
            "SUPABASE",
            "Desired State reconciliation",
            "Project / Workspace ownership",
            "VENDOR_CHANGE",
            "Detach != Destroy",
            "dev-db-migration",
        ),
    )
    require(
        ROOT / "custom-skills/shared/dev-infrastructure/scripts/detect_infrastructure.py",
        (
            "LOCAL_HOST",
            "NETWORK_HOST",
            "CONTAINER",
            "SUPABASE",
            "UNKNOWN",
            "SUPABASE_DATABASE_HOST_SUFFIXES",
            "supabase_database_hosts",
            "database_runtime_candidates",
        ),
    )
    require(
        ROOT / "custom-skills/shared/dev-infrastructure/scripts/plan_transition.py",
        (
            "DEFAULT_APPLICATION_RUNTIME = \"CONTAINER\"",
            "DEFAULT_DATABASE_RUNTIME = \"CONTAINER\"",
            "resolve_project_repo",
            "--project-repo",
            "requires_observed_verification",
            "safe_to_auto_destroy",
            "dev-data-feature",
            "dev-db-migration",
        ),
    )
    require(
        ROOT / "custom-skills/orchestrator/dev-project-bootstrap/scripts/infrastructure_state.py",
        (
            "load_infrastructure_detector",
            "DEFAULT_APPLICATION_RUNTIME = \"CONTAINER\"",
            "DEFAULT_DATABASE_RUNTIME = \"CONTAINER\"",
            "conflicting database runtime evidence",
            "database_platform",
        ),
    )
    require(
        ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/scripts/prepare_dispatch.py",
        (
            "--desired-application-runtime",
            "--desired-database-runtime",
            "--desired-database-platform",
            "--desired-database-vendor",
            "infrastructure desired state is atomic",
            "persist_infrastructure_state",
            "INFRASTRUCTURE_STATE_STATUS",
        ),
    )
    require(
        ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md",
        (
            "Infrastructure Desired State persistence",
            "Primary Repository `.hermes/project.yaml infrastructure:`",
            "4축은 atomic contract",
            "INFRASTRUCTURE_STATE_STATUS",
        ),
    )
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
