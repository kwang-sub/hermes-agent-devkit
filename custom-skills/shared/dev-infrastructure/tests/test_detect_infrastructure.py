#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "detect_infrastructure.py"
spec = importlib.util.spec_from_file_location("detect_infrastructure", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def write(root: Path, path: str, text: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_defaults_unknown_observed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = module.detect(Path(tmp))
        assert result["application_runtime"] == "UNKNOWN"
        assert result["database_runtime"] == "UNKNOWN"
        assert result["application_status"] == "NOT_CONFIGURED"


def test_native_postgres_compose() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root, "backend/Dockerfile", "FROM eclipse-temurin:17-jre\n")
        write(root, "compose.yml", "services:\n  db:\n    image: postgres:17\n")
        result = module.detect(root)
        assert result["application_runtime"] == "CONTAINER"
        assert result["database_runtime"] == "CONTAINER"
        assert result["database_platform"] == "NATIVE"
        assert result["database_vendor"] == "postgresql"


def test_supabase_cloud_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root, ".env.example", "NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co\n")
        result = module.detect(root)
        assert result["database_runtime"] == "NETWORK_HOST"
        assert result["database_platform"] == "SUPABASE"
        assert result["database_vendor"] == "postgresql"


def test_supabase_local_wins_over_remote_env_hint() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root, "supabase/config.toml", "project_id = 'demo'\n")
        write(root, ".env.example", "SUPABASE_URL=http://127.0.0.1:54321\n")
        result = module.detect(root)
        assert result["database_runtime"] == "CONTAINER"
        assert result["database_platform"] == "SUPABASE"
        assert result["database_vendor"] == "postgresql"


if __name__ == "__main__":
    test_defaults_unknown_observed()
    test_native_postgres_compose()
    test_supabase_cloud_contract()
    test_supabase_local_wins_over_remote_env_hint()
    print("PASS")
