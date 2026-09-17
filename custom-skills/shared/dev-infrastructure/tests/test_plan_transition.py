#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "plan_transition.py"
spec = importlib.util.spec_from_file_location("plan_transition", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def metadata(database_runtime: str, platform: str = "NATIVE", vendor: str = "postgresql") -> str:
    return f"""# managed-by: dev-project-bootstrap\nversion: 4\n\ninfrastructure:\n  version: \"1\"\n  application_runtime: \"CONTAINER\"\n  database_runtime: \"{database_runtime}\"\n  database_platform: \"{platform}\"\n  database_vendor: \"{vendor}\"\n"""


def test_container_to_local_preserves_data() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo, ".hermes/project.yaml", metadata("LOCAL_HOST"))
        write(repo, "backend/Dockerfile", "FROM eclipse-temurin:17-jre\n")
        write(repo, "compose.yml", """services:\n  backend:\n    build: ./backend\n  postgres:\n    image: postgres:17\n""")
        write(repo, "application.properties", "spring.datasource.url=jdbc:postgresql://postgres:5432/app\n")
        result = module.plan(repo)
        assert result["transition"] == "RUNTIME_CHANGE", result
        assert result["data_migration"] == "NOT_REQUIRED", result
        assert "database persistent volume/data" in result["resources_preserved"], result
        assert result["safe_to_auto_destroy"] is False, result


def test_linked_worktree_reads_desired_state_from_primary_repository() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        primary = root / "primary"
        workspace = root / "linked"
        primary.mkdir()
        workspace.mkdir()
        (primary / ".git" / "worktrees" / "linked").mkdir(parents=True)
        write(primary, ".hermes/project.yaml", metadata("NETWORK_HOST", "SUPABASE", "postgresql"))
        write(
            workspace,
            ".git",
            f"gitdir: {primary / '.git' / 'worktrees' / 'linked'}\n",
        )
        write(workspace, "Dockerfile", "FROM eclipse-temurin:17-jre\n")
        write(workspace, ".env.example", "SUPABASE_URL=https://demo.supabase.co\n")

        result = module.plan(workspace)
        assert result["project_repository"] == str(primary.resolve()), result
        assert result["desired"]["database_runtime"] == "NETWORK_HOST", result
        assert result["desired"]["database_platform"] == "SUPABASE", result


def test_vendor_change_opens_data_gate() -> None:
    observed = {
        "application_runtime": "CONTAINER",
        "database_runtime": "CONTAINER",
        "database_platform": "NATIVE",
        "database_vendor": "postgresql",
    }
    desired = {
        "application_runtime": "CONTAINER",
        "database_runtime": "CONTAINER",
        "database_platform": "NATIVE",
        "database_vendor": "mysql",
    }
    result = module.compare(observed, desired)
    assert result["transition"] == "VENDOR_CHANGE", result
    assert result["data_migration"] == "REQUIRED", result
    assert "dev-data-feature" in result["required_skills"], result
    assert "dev-db-migration" in result["required_skills"], result


def test_native_postgres_to_supabase_is_not_vendor_change() -> None:
    observed = {
        "application_runtime": "CONTAINER",
        "database_runtime": "CONTAINER",
        "database_platform": "NATIVE",
        "database_vendor": "postgresql",
    }
    desired = {
        "application_runtime": "CONTAINER",
        "database_runtime": "NETWORK_HOST",
        "database_platform": "SUPABASE",
        "database_vendor": "postgresql",
    }
    result = module.compare(observed, desired)
    assert result["transition"] == "COMBINED_CHANGE", result
    assert result["vendor_change"] is False, result
    assert result["data_migration"] == "NOT_REQUIRED", result


def test_supabase_rejects_non_postgresql_desired_vendor() -> None:
    desired = {
        "application_runtime": "CONTAINER",
        "database_runtime": "NETWORK_HOST",
        "database_platform": "SUPABASE",
        "database_vendor": "mysql",
    }
    try:
        module.validate_desired(desired)
    except module.TransitionPlanError:
        pass
    else:
        raise AssertionError("SUPABASE + mysql must be rejected")


def test_unknown_observed_reports_unknown_drift() -> None:
    observed = {
        "application_runtime": "UNKNOWN",
        "database_runtime": "UNKNOWN",
        "database_platform": "NATIVE",
        "database_vendor": "UNKNOWN",
    }
    desired = {
        "application_runtime": "CONTAINER",
        "database_runtime": "CONTAINER",
        "database_platform": "NATIVE",
        "database_vendor": "UNKNOWN",
    }
    result = module.compare(observed, desired)
    assert result["drift"] == "UNKNOWN", result
    assert result["transition"] == "UNKNOWN", result
    assert result["requires_observed_verification"] is True, result


if __name__ == "__main__":
    test_container_to_local_preserves_data()
    test_linked_worktree_reads_desired_state_from_primary_repository()
    test_vendor_change_opens_data_gate()
    test_native_postgres_to_supabase_is_not_vendor_change()
    test_supabase_rejects_non_postgresql_desired_vendor()
    test_unknown_observed_reports_unknown_drift()
    print("PASS")
