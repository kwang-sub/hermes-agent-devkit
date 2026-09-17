#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "plan_transition.py"
spec = importlib.util.spec_from_file_location("plan_transition", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def state(app: str, db: str, platform: str, vendor: str) -> dict[str, str]:
    return {
        "application_runtime": app,
        "database_runtime": db,
        "database_platform": platform,
        "database_vendor": vendor,
    }


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
        state("CONTAINER", "NETWORK_HOST", "SUPABASE", "postgresql"),
    )
    assert result["transition_class"] == "COMBINED_CHANGE"
    assert "DATABASE_RUNTIME" in result["changes"]
    assert "PLATFORM" in result["changes"]
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
    test_container_to_local_preserves_volume()
    test_postgres_to_mysql_requires_data_migration()
    test_native_postgres_to_supabase_cloud_is_not_vendor_change()
    test_mysql_to_supabase_requires_vendor_migration()
    print("PASS")
