#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migration_guard.py"
SPEC = importlib.util.spec_from_file_location("migration_guard", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def root() -> Path:
    return Path(tempfile.mkdtemp(prefix="migration-guard-"))


def test_default_flyway_when_no_framework_exists() -> None:
    project = root()
    result = MODULE.analyze(project)
    assert result["status"] == "pass"
    assert result["migration_tool"] == "default_flyway"
    assert result["flyway_version_policy"] == "timestamp_utc_default"


def test_existing_flyway_detection() -> None:
    project = root()
    migration = project / "src/main/resources/db/migration"
    migration.mkdir(parents=True)
    (migration / "V20260916140000__create_account.sql").write_text("select 1;", encoding="utf-8")
    result = MODULE.analyze(project)
    assert result["migration_tool"] == "existing_flyway"
    assert result["flyway_version_policy"] == "timestamp_utc"


def test_existing_liquibase_detection() -> None:
    project = root()
    changelog = project / "src/main/resources/db/changelog"
    changelog.mkdir(parents=True)
    (changelog / "db.changelog-master.yaml").write_text("databaseChangeLog: []", encoding="utf-8")
    result = MODULE.analyze(project)
    assert result["migration_tool"] == "existing_liquibase"


def test_mixed_tool_detection_is_blocked() -> None:
    project = root()
    (project / "src/main/resources/db/migration").mkdir(parents=True)
    (project / "src/main/resources/db/changelog").mkdir(parents=True)
    result = MODULE.analyze(project)
    assert result["status"] == "blocked"
    assert result["migration_tool"] == "conflict"


def test_physical_name_uses_subject_area_once() -> None:
    assert MODULE.build_physical_table_name("investment", "account") == "tbl_investment_account"
    assert MODULE.build_physical_table_name("investment", "investment_account") == "tbl_investment_account"


def test_invalid_subject_area_is_rejected() -> None:
    try:
        MODULE.build_physical_table_name("Investment-Core", "account")
    except ValueError as exc:
        assert "lowercase snake_case" in str(exc)
    else:
        raise AssertionError("invalid subject area should fail")


def test_timestamp_version_validation() -> None:
    errors, _ = MODULE.validate_new_flyway_file(
        "V20260916142351__add_account_type.sql",
        "timestamp_utc_default",
    )
    assert errors == []
    errors, _ = MODULE.validate_new_flyway_file("V1__add_account_type.sql", "timestamp_utc_default")
    assert errors


def test_deployed_version_ordering_blocks_out_of_order_workaround() -> None:
    errors, _ = MODULE.validate_new_flyway_file(
        "V20260916142351__add_account_type.sql",
        "timestamp_utc",
        deployed_version="20260917100000",
    )
    assert any("outOfOrder" in item for item in errors)


def test_duplicate_flyway_versions_are_blocked() -> None:
    project = root()
    migration = project / "src/main/resources/db/migration"
    migration.mkdir(parents=True)
    (migration / "V20260916140000__create_account.sql").write_text("select 1;", encoding="utf-8")
    (migration / "V20260916140000__create_holding.sql").write_text("select 1;", encoding="utf-8")
    result = MODULE.analyze(project)
    assert result["status"] == "blocked"
    assert any("duplicate Flyway version" in item for item in result["errors"])


def test_new_file_version_collision_is_blocked_before_creation() -> None:
    project = root()
    migration = project / "src/main/resources/db/migration"
    migration.mkdir(parents=True)
    (migration / "V20260916140000__existing.sql").write_text("select 1;", encoding="utf-8")
    result = MODULE.analyze(project, new_file="V20260916140000__new_change.sql")
    assert result["status"] == "blocked"
    assert any("already exists" in item for item in result["errors"])


def test_existing_numeric_version_policy_is_preserved() -> None:
    project = root()
    migration = project / "src/main/resources/db/migration"
    migration.mkdir(parents=True)
    (migration / "V1__baseline.sql").write_text("select 1;", encoding="utf-8")
    result = MODULE.analyze(project, new_file="V2__next_change.sql")
    assert result["status"] == "pass"
    assert result["flyway_version_policy"] == "project_existing"


def test_timestamp_allocator_skips_existing_second() -> None:
    project = root()
    migration = project / "src/main/resources/db/migration"
    migration.mkdir(parents=True)
    (migration / "V20260916140000__existing.sql").write_text("select 1;", encoding="utf-8")
    value = MODULE.allocate_timestamp_version(
        project,
        now=datetime(2026, 9, 16, 14, 0, 0, tzinfo=timezone.utc),
    )
    assert value == "20260916140001"


if __name__ == "__main__":
    test_default_flyway_when_no_framework_exists()
    test_existing_flyway_detection()
    test_existing_liquibase_detection()
    test_mixed_tool_detection_is_blocked()
    test_physical_name_uses_subject_area_once()
    test_invalid_subject_area_is_rejected()
    test_timestamp_version_validation()
    test_deployed_version_ordering_blocks_out_of_order_workaround()
    test_duplicate_flyway_versions_are_blocked()
    test_new_file_version_collision_is_blocked_before_creation()
    test_existing_numeric_version_policy_is_preserved()
    test_timestamp_allocator_skips_existing_second()
    print("[PASS] Coder DB migration guard tests")
