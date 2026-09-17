#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "persist_infrastructure_desired.py"
spec = importlib.util.spec_from_file_location("persist_infrastructure_desired", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def metadata() -> str:
    return """# managed-by: dev-project-bootstrap
project:
  id: demo
  repository: /workspace/demo

infrastructure:
  version: \"1\"
  defaults:
    application_runtime: \"CONTAINER\"
    database_runtime: \"CONTAINER\"
  desired:
    application_runtime: \"LOCAL_HOST\"
    database_runtime: \"LOCAL_HOST\"
    database_platform: \"NATIVE\"
    database_vendor: \"postgresql\"

kanban:
  board: demo
"""


def args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "application_runtime": "CONTAINER",
        "application_host": None,
        "database_runtime": "NETWORK_HOST",
        "database_host": "db.internal",
        "database_port": "5544",
        "database_platform": "NATIVE",
        "database_vendor": "postgresql",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_persist_replaces_only_desired_block() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        target = repo / ".hermes" / "project.yaml"
        target.parent.mkdir(parents=True)
        target.write_text(metadata(), encoding="utf-8")
        desired = module.normalize(args())
        status = module.persist(repo, desired)
        text = target.read_text(encoding="utf-8")
        assert status == "updated"
        assert 'application_runtime: "CONTAINER"' in text
        assert 'database_runtime: "NETWORK_HOST"' in text
        assert 'database_host: "db.internal"' in text
        assert 'database_port: "5544"' in text
        assert "kanban:\n  board: demo" in text
        assert "defaults:\n    application_runtime" in text


def test_persist_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        target = repo / ".hermes" / "project.yaml"
        target.parent.mkdir(parents=True)
        target.write_text(metadata(), encoding="utf-8")
        desired = {
            "application_runtime": "LOCAL_HOST",
            "database_runtime": "LOCAL_HOST",
            "database_platform": "NATIVE",
            "database_vendor": "postgresql",
        }
        assert module.persist(repo, desired) == "unchanged"


def test_supabase_normalizes_vendor_to_postgresql() -> None:
    desired = module.normalize(
        args(
            database_host="db.example.supabase.co",
            database_port="5432",
            database_platform="SUPABASE",
            database_vendor="mysql",
        )
    )
    assert desired["database_vendor"] == "postgresql"


def test_host_rejects_url_or_credential_shape() -> None:
    for value in ("https://db.internal", "user@db.internal"):
        try:
            module.normalize(args(database_host=value))
        except module.PersistError as exc:
            assert "host/service name only" in str(exc)
        else:
            raise AssertionError(f"invalid host must be rejected: {value}")


def test_port_must_be_valid_tcp_port() -> None:
    for value in ("abc", "0", "65536"):
        try:
            module.normalize(args(database_port=value))
        except module.PersistError as exc:
            assert "between 1 and 65535" in str(exc)
        else:
            raise AssertionError(f"invalid port must be rejected: {value}")


if __name__ == "__main__":
    test_persist_replaces_only_desired_block()
    test_persist_is_idempotent()
    test_supabase_normalizes_vendor_to_postgresql()
    test_host_rejects_url_or_credential_shape()
    test_port_must_be_valid_tcp_port()
    print("PASS")
