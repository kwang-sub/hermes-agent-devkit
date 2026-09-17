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


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_compose_postgres() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo, "backend/Dockerfile", "FROM eclipse-temurin:17-jre\n")
        write(repo, "compose.yml", """services:\n  backend:\n    build: ./backend\n  postgres:\n    image: postgres:17\n""")
        write(repo, "backend/src/application.yml", "spring:\n  datasource:\n    url: jdbc:postgresql://postgres:5432/app\n")
        state = module.infer_state(repo)
        assert state["application_runtime"] == "CONTAINER", state
        assert state["database_runtime"] == "CONTAINER", state
        assert state["database_platform"] == "NATIVE", state
        assert state["database_vendor"] == "postgresql", state


def test_nested_spring_resources_local_db() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(
            repo,
            "backend/src/main/resources/application.yml",
            "spring:\n  datasource:\n    url: jdbc:postgresql://localhost:5432/app\n",
        )
        state = module.infer_state(repo)
        assert "backend/src/main/resources/application.yml" in state["inputs"], state
        assert state["database_runtime"] == "LOCAL_HOST", state
        assert state["database_vendor"] == "postgresql", state


def test_placeholder_db_host_remains_unknown() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(
            repo,
            "application.properties",
            "spring.datasource.url=jdbc:postgresql://${DB_HOST}:${DB_PORT}/app\n",
        )
        state = module.infer_state(repo)
        assert state["database_runtime"] == "UNKNOWN", state
        assert state["database_endpoint_hosts"] == [], state
        assert state["database_vendor"] == "postgresql", state


def test_container_to_host_alias_is_local_db() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo, "Dockerfile", "FROM eclipse-temurin:17-jre\n")
        write(
            repo,
            "application.properties",
            "spring.datasource.url=jdbc:postgresql://host.docker.internal:5432/app\n",
        )
        state = module.infer_state(repo)
        assert state["application_runtime"] == "CONTAINER", state
        assert state["database_runtime"] == "LOCAL_HOST", state


def test_supabase_cloud_database_endpoint() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(
            repo,
            ".env.example",
            "DATABASE_URL=postgresql://postgres:placeholder@db.sample.supabase.co:5432/postgres\n",
        )
        state = module.infer_state(repo)
        assert state["database_runtime"] == "NETWORK_HOST", state
        assert state["database_platform"] == "SUPABASE", state
        assert state["database_vendor"] == "postgresql", state
        assert state["supabase_database_hosts"] == ["db.sample.supabase.co"], state


def test_supabase_auth_sdk_does_not_imply_supabase_database() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo, ".env.example", "SUPABASE_URL=https://sample.supabase.co\n")
        write(repo, "package.json", '{"dependencies":{"@supabase/supabase-js":"^2.0.0"}}')
        state = module.infer_state(repo)
        assert state["database_runtime"] == "UNKNOWN", state
        assert state["database_platform"] == "UNKNOWN", state
        assert state["database_vendor"] == "UNKNOWN", state
        assert state["supabase_database_hosts"] == [], state


def test_supabase_key_without_database_endpoint_keeps_database_unknown() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo, ".env.example", "SUPABASE_URL=\n")
        state = module.infer_state(repo)
        assert state["database_runtime"] == "UNKNOWN", state
        assert state["database_platform"] == "UNKNOWN", state
        assert state["database_vendor"] == "UNKNOWN", state


def test_supabase_local() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo, "supabase/config.toml", "project_id = \"demo\"\n")
        state = module.infer_state(repo)
        assert state["database_runtime"] == "CONTAINER", state
        assert state["database_platform"] == "SUPABASE", state
        assert state["database_vendor"] == "postgresql", state


def test_conflicting_runtime_evidence_is_unknown() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo, "compose.yml", """services:\n  postgres:\n    image: postgres:17\n""")
        write(
            repo,
            "application.properties",
            "spring.datasource.url=jdbc:postgresql://db.example.com:5432/app\n",
        )
        state = module.infer_state(repo)
        assert state["database_runtime"] == "UNKNOWN", state
        assert state["database_runtime_candidates"] == ["CONTAINER", "NETWORK_HOST"], state


def test_unknown_is_not_defaulted() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo, "build.gradle.kts", "plugins { java }\n")
        state = module.infer_state(repo)
        assert state["application_runtime"] == "UNKNOWN", state
        assert state["database_runtime"] == "UNKNOWN", state
        assert state["database_platform"] == "UNKNOWN", state


if __name__ == "__main__":
    test_compose_postgres()
    test_nested_spring_resources_local_db()
    test_placeholder_db_host_remains_unknown()
    test_container_to_host_alias_is_local_db()
    test_supabase_cloud_database_endpoint()
    test_supabase_auth_sdk_does_not_imply_supabase_database()
    test_supabase_key_without_database_endpoint_keeps_database_unknown()
    test_supabase_local()
    test_conflicting_runtime_evidence_is_unknown()
    test_unknown_is_not_defaulted()
    print("PASS")
