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


def test_persist_replaces_only_desired_block() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        target = repo / ".hermes" / "project.yaml"
        target.parent.mkdir(parents=True)
        target.write_text(metadata(), encoding="utf-8")
        desired = {
            "application_runtime": "CONTAINER",
            "database_runtime": "NETWORK_HOST",
            "database_platform": "NATIVE",
            "database_vendor": "postgresql",
            "database_host": "db.internal",
            "database_port": "5544",
        }
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
    args = argparse.Namespace(
        application_runtime="CONTAINER",
        application_host=None,
        database_runtime="NETWORK_HOST",
        database_host="db.example.supabase.co",
        database_port="5432",
        database_platform="SUPABASE",
        database_vendor="mysql",
    )
    desired = module.normalize(args)
    assert desired["database_vendor"] == "postgresql"


if __name__ == "__main__":
    test_persist_replaces_only_desired_block()
    test_persist_is_idempotent()
    test_supabase_normalizes_vendor_to_postgresql()
    print("PASS")
