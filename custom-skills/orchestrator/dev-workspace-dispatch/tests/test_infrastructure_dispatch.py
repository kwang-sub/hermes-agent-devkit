from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import tempfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_dispatch.py"
SPEC = importlib.util.spec_from_file_location("prepare_dispatch", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def args(**overrides: str | None) -> argparse.Namespace:
    values = {
        "desired_application_runtime": None,
        "desired_database_runtime": None,
        "desired_database_platform": None,
        "desired_database_vendor": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def metadata() -> str:
    return """# managed-by: dev-project-bootstrap
version: 3

project:
  id: "demo"
  repository: "/workspace/demo"

kanban:
  board: "demo"

infrastructure:
  version: "1"
  application_runtime: "CONTAINER"
  database_runtime: "CONTAINER"
  database_platform: "NATIVE"
  database_vendor: "postgresql"

resolver:
  aliases: []
"""


def test_infrastructure_args_are_atomic() -> None:
    try:
        module.infrastructure_args(
            args(desired_application_runtime="CONTAINER")
        )
    except module.DispatchError:
        pass
    else:
        raise AssertionError("partial desired infrastructure state must fail")


def test_supabase_normalizes_vendor_to_postgresql() -> None:
    state = module.infrastructure_args(
        args(
            desired_application_runtime="CONTAINER",
            desired_database_runtime="NETWORK_HOST",
            desired_database_platform="SUPABASE",
            desired_database_vendor="UNKNOWN",
        )
    )
    assert state is not None
    assert state["database_vendor"] == "postgresql", state


def test_persist_updates_only_infrastructure_section() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "project.yaml"
        path.write_text(metadata(), encoding="utf-8")
        state = {
            "application_runtime": "LOCAL_HOST",
            "database_runtime": "NETWORK_HOST",
            "database_platform": "SUPABASE",
            "database_vendor": "postgresql",
        }
        status = module.persist_infrastructure_state(path, state)
        text = path.read_text(encoding="utf-8")
        assert status == "updated"
        assert 'application_runtime: "LOCAL_HOST"' in text
        assert 'database_runtime: "NETWORK_HOST"' in text
        assert 'database_platform: "SUPABASE"' in text
        assert 'database_vendor: "postgresql"' in text
        assert 'board: "demo"' in text
        assert "resolver:" in text


def test_persist_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "project.yaml"
        path.write_text(metadata(), encoding="utf-8")
        state = {
            "application_runtime": "CONTAINER",
            "database_runtime": "CONTAINER",
            "database_platform": "NATIVE",
            "database_vendor": "postgresql",
        }
        assert module.persist_infrastructure_state(path, state) == "unchanged"


if __name__ == "__main__":
    test_infrastructure_args_are_atomic()
    test_supabase_normalizes_vendor_to_postgresql()
    test_persist_updates_only_infrastructure_section()
    test_persist_is_idempotent()
    print("PASS")
