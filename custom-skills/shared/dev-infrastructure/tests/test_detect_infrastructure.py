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
        assert result["database_platform"] == "UNKNOWN"
        assert result["database_vendor"] == "unknown"
        assert result["database_host"] == "unknown"
        assert result["application_status"] == "NOT_CONFIGURED"
        assert result["database_status"] == "NOT_CONFIGURED"


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


def test_dockerfile_and_compose_variants_are_detected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root, "backend/Dockerfile.dev", "FROM eclipse-temurin:21-jre\n")
        write(root, "infra/compose.local.yml", "services:\n  db:\n    image: mariadb:11\n")
        result = module.detect(root)
        assert result["application_runtime"] == "CONTAINER"
        assert result["database_runtime"] == "CONTAINER"
        assert result["database_vendor"] == "mariadb"
        assert "dockerfile:backend/Dockerfile.dev" in result["evidence"]
        assert "compose:infra/compose.local.yml" in result["evidence"]


def test_invalid_compose_named_file_is_not_runtime_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root, "compose.dev.yml", "metadata:\n  name: not-compose\n")
        result = module.detect(root)
        assert result["application_runtime"] == "UNKNOWN"
        assert result["database_runtime"] == "UNKNOWN"


def test_supabase_auth_contract_does_not_imply_supabase_database() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(
            root,
            ".env.example",
            "NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co\n"
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=\n",
        )
        result = module.detect(root)
        assert result["database_runtime"] == "UNKNOWN"
        assert result["database_platform"] == "UNKNOWN"
        assert result["database_vendor"] == "unknown"
        assert "supabase:provider-env-contract" in result["evidence"]


def test_supabase_database_endpoint_is_strong_database_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(
            root,
            ".env.local",
            "SUPABASE_DB_URL=postgresql://postgres:secret@db.project.supabase.co:5432/postgres\n",
        )
        result = module.detect(root)
        assert result["database_runtime"] == "NETWORK_HOST"
        assert result["database_platform"] == "SUPABASE"
        assert result["database_vendor"] == "postgresql"
        assert result["database_host"] == "db.project.supabase.co"
        assert result["database_port"] == "5432"


def test_supabase_local_wins_over_provider_env_hint() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(root, "supabase/config.toml", "project_id = 'demo'\n")
        write(root, ".env.example", "SUPABASE_URL=http://127.0.0.1:54321\n")
        result = module.detect(root)
        assert result["database_runtime"] == "CONTAINER"
        assert result["database_platform"] == "SUPABASE"
        assert result["database_vendor"] == "postgresql"


def test_spring_properties_database_endpoint_is_detected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write(
            root,
            "backend/src/main/resources/application.properties",
            "spring.datasource.url=jdbc:postgresql://db.internal:5544/app\n",
        )
        result = module.detect(root)
        assert result["database_runtime"] == "NETWORK_HOST"
        assert result["database_platform"] == "NATIVE"
        assert result["database_vendor"] == "postgresql"
        assert result["database_host"] == "db.internal"
        assert result["database_port"] == "5544"


if __name__ == "__main__":
    test_defaults_unknown_observed()
    test_native_postgres_compose()
    test_dockerfile_and_compose_variants_are_detected()
    test_invalid_compose_named_file_is_not_runtime_evidence()
    test_supabase_auth_contract_does_not_imply_supabase_database()
    test_supabase_database_endpoint_is_strong_database_evidence()
    test_supabase_local_wins_over_provider_env_hint()
    test_spring_properties_database_endpoint_is_detected()
    print("PASS")
