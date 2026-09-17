#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "infrastructure_state.py"
spec = importlib.util.spec_from_file_location("infrastructure_state", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def metadata(technology: str = "") -> str:
    return f"""# managed-by: dev-project-bootstrap\nversion: 3\n\nproject:\n  id: \"demo\"\n\nresolver:\n  aliases: []\n{technology}"""


def write(repo: Path, rel: str, text: str) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_metadata(repo: Path, text: str) -> Path:
    return write(repo, ".hermes/project.yaml", text)


def test_creates_container_defaults_without_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        path = write_metadata(repo, metadata())
        status, state, observed = module.ensure(repo)
        text = path.read_text(encoding="utf-8")
        assert status == "created"
        assert state == {
            "application_runtime": "CONTAINER",
            "database_runtime": "CONTAINER",
            "database_platform": "NATIVE",
            "database_vendor": "UNKNOWN",
        }, state
        assert observed is not None
        assert observed["database_runtime"] == "UNKNOWN", observed
        assert 'application_runtime: "CONTAINER"' in text
        assert 'database_runtime: "CONTAINER"' in text
        assert 'database_platform: "NATIVE"' in text
        assert 'database_vendor: "UNKNOWN"' in text


def test_uses_single_detected_technology_vendor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        tech = """\ntechnology:\n  database_vendors:\n    - \"postgresql\"\n  data_entry_candidate: \"dev-data-feature\"\n"""
        path = write_metadata(repo, metadata(tech))
        status, state, _ = module.ensure(repo)
        text = path.read_text(encoding="utf-8")
        assert status == "created"
        assert state["database_vendor"] == "postgresql", state
        assert 'database_vendor: "postgresql"' in text


def test_existing_local_database_evidence_beats_container_default() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        path = write_metadata(repo, metadata())
        write(
            repo,
            "backend/src/main/resources/application.yml",
            "spring:\n  datasource:\n    url: jdbc:postgresql://localhost:5432/app\n",
        )
        status, state, observed = module.ensure(repo)
        text = path.read_text(encoding="utf-8")
        assert status == "created"
        assert observed is not None
        assert observed["database_runtime"] == "LOCAL_HOST", observed
        assert state["database_runtime"] == "LOCAL_HOST", state
        assert state["database_platform"] == "NATIVE", state
        assert state["database_vendor"] == "postgresql", state
        assert 'database_runtime: "LOCAL_HOST"' in text


def test_existing_supabase_database_evidence_beats_native_default() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        path = write_metadata(repo, metadata())
        write(
            repo,
            ".env.example",
            "DATABASE_URL=postgresql://postgres:placeholder@db.sample.supabase.co:5432/postgres\n",
        )
        status, state, observed = module.ensure(repo)
        text = path.read_text(encoding="utf-8")
        assert status == "created"
        assert observed is not None
        assert state["database_runtime"] == "NETWORK_HOST", state
        assert state["database_platform"] == "SUPABASE", state
        assert state["database_vendor"] == "postgresql", state
        assert 'database_runtime: "NETWORK_HOST"' in text
        assert 'database_platform: "SUPABASE"' in text


def test_conflicting_runtime_evidence_blocks_default_initialization() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write_metadata(repo, metadata())
        write(repo, "compose.yml", "services:\n  postgres:\n    image: postgres:17\n")
        write(
            repo,
            "application.properties",
            "spring.datasource.url=jdbc:postgresql://db.example.com:5432/app\n",
        )
        try:
            module.ensure(repo)
        except module.InfrastructureStateError:
            pass
        else:
            raise AssertionError("conflicting runtime evidence must block bootstrap default")


def test_preserves_existing_desired_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        existing = metadata() + """\ninfrastructure:\n  version: \"1\"\n  application_runtime: \"LOCAL_HOST\"\n  database_runtime: \"NETWORK_HOST\"\n  database_platform: \"SUPABASE\"\n  database_vendor: \"postgresql\"\n"""
        path = write_metadata(repo, existing)
        before = path.read_text(encoding="utf-8")
        status, state, observed = module.ensure(repo)
        after = path.read_text(encoding="utf-8")
        assert status == "preserved"
        assert state == {}
        assert observed is None
        assert before == after


if __name__ == "__main__":
    test_creates_container_defaults_without_evidence()
    test_uses_single_detected_technology_vendor()
    test_existing_local_database_evidence_beats_container_default()
    test_existing_supabase_database_evidence_beats_native_default()
    test_conflicting_runtime_evidence_blocks_default_initialization()
    test_preserves_existing_desired_state()
    print("PASS")
