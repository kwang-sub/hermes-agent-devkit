#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "plan_transition.py"
spec = importlib.util.spec_from_file_location("plan_transition", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def state(
    app: str,
    db: str,
    platform: str,
    vendor: str,
    *,
    application_host: str = "unknown",
    application_port: str = "unknown",
    database_host: str = "unknown",
    database_port: str = "unknown",
) -> dict[str, str]:
    return {
        "application_runtime": app,
        "application_host": application_host,
        "application_port": application_port,
        "database_runtime": db,
        "database_host": database_host,
        "database_port": database_port,
        "database_platform": platform,
        "database_vendor": vendor,
    }


def test_empty_repository_is_initial_configuration() -> None:
    result = module.plan(
        state("UNKNOWN", "UNKNOWN", "UNKNOWN", "unknown"),
        state("CONTAINER", "CONTAINER", "NATIVE", "postgresql"),
    )
    assert result["transition_class"] == "INITIAL_CONFIGURATION"
    assert result["initial_configuration"] is True


def test_container_to_local_preserves_volume() -> None:
    result = module.plan(
        state("CONTAINER", "CONTAINER", "NATIVE", "postgresql"),
        state("CONTAINER", "LOCAL_HOST", "NATIVE", "postgresql"),
    )
    assert result["transition_class"] == "RUNTIME_CHANGE"
    assert result["data_migration"] == "NOT_REQUIRED"
    assert "database-container-service" in result["detached"]
    assert "database-persistent-volume" in result["preserved"]
    assert result["removed"] == []
    assert result["destructive_operations"] == "NONE"


def test_database_host_only_change_is_host_change() -> None:
    result = module.plan(
        state(
            "CONTAINER",
            "NETWORK_HOST",
            "NATIVE",
            "postgresql",
            database_host="db-old.internal",
            database_port="5432",
        ),
        state(
            "CONTAINER",
            "NETWORK_HOST",
            "NATIVE",
            "postgresql",
            database_host="db-new.internal",
            database_port="5432",
        ),
    )
    assert result["transition_class"] == "HOST_CHANGE"
    assert result["changes"] == ["DATABASE_HOST"]
    assert result["host_changed"] is True
    assert result["data_migration"] == "NOT_REQUIRED"


def test_database_port_only_change_is_host_change() -> None:
    result = module.plan(
        state(
            "CONTAINER",
            "NETWORK_HOST",
            "NATIVE",
            "postgresql",
            database_host="db.internal",
            database_port="5432",
        ),
        state(
            "CONTAINER",
            "NETWORK_HOST",
            "NATIVE",
            "postgresql",
            database_host="db.internal",
            database_port="5544",
        ),
    )
    assert result["transition_class"] == "HOST_CHANGE"
    assert result["changes"] == ["DATABASE_PORT"]


def test_runtime_and_host_change_is_combined() -> None:
    result = module.plan(
        state(
            "CONTAINER",
            "LOCAL_HOST",
            "NATIVE",
            "postgresql",
            database_host="localhost",
            database_port="5432",
        ),
        state(
            "CONTAINER",
            "NETWORK_HOST",
            "NATIVE",
            "postgresql",
            database_host="db.internal",
            database_port="5432",
        ),
    )
    assert result["transition_class"] == "COMBINED_CHANGE"
    assert "DATABASE_RUNTIME" in result["changes"]
    assert "DATABASE_HOST" in result["changes"]


def test_postgres_to_mysql_requires_data_migration() -> None:
    result = module.plan(
        state("CONTAINER", "CONTAINER", "NATIVE", "postgresql"),
        state("CONTAINER", "CONTAINER", "NATIVE", "mysql"),
    )
    assert result["transition_class"] == "VENDOR_CHANGE"
    assert result["data_migration"] == "REQUIRED"
    assert result["required_capabilities"] == ["dev-data-feature", "dev-db-migration"]


def test_native_postgres_to_supabase_cloud_is_not_vendor_change() -> None:
    result = module.plan(
        state("CONTAINER", "CONTAINER", "NATIVE", "postgresql"),
        state(
            "CONTAINER",
            "NETWORK_HOST",
            "SUPABASE",
            "postgresql",
            database_host="db.project.supabase.co",
            database_port="5432",
        ),
    )
    assert result["transition_class"] == "COMBINED_CHANGE"
    assert "DATABASE_RUNTIME" in result["changes"]
    assert "PLATFORM" in result["changes"]
    assert "VENDOR" not in result["changes"]
    assert result["data_migration"] == "NOT_REQUIRED"


def test_supabase_unknown_vendor_is_normalized_to_postgres() -> None:
    result = module.plan(
        state("CONTAINER", "CONTAINER", "NATIVE", "postgresql"),
        state("CONTAINER", "NETWORK_HOST", "SUPABASE", "unknown"),
    )
    assert result["desired"]["database_vendor"] == "postgresql"
    assert "VENDOR" not in result["changes"]
    assert result["data_migration"] == "NOT_REQUIRED"


def test_mysql_to_supabase_requires_vendor_migration() -> None:
    result = module.plan(
        state("CONTAINER", "NETWORK_HOST", "NATIVE", "mysql"),
        state("CONTAINER", "NETWORK_HOST", "SUPABASE", "postgresql"),
    )
    assert "PLATFORM" in result["changes"]
    assert "VENDOR" in result["changes"]
    assert result["data_migration"] == "REQUIRED"


if __name__ == "__main__":
    test_empty_repository_is_initial_configuration()
    test_container_to_local_preserves_volume()
    test_database_host_only_change_is_host_change()
    test_database_port_only_change_is_host_change()
    test_runtime_and_host_change_is_combined()
    test_postgres_to_mysql_requires_data_migration()
    test_native_postgres_to_supabase_cloud_is_not_vendor_change()
    test_supabase_unknown_vendor_is_normalized_to_postgres()
    test_mysql_to_supabase_requires_vendor_migration()
    print("PASS")
