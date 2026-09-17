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


def write_metadata(repo: Path, text: str) -> Path:
    path = repo / ".hermes" / "project.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_creates_container_defaults() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        path = write_metadata(repo, metadata())
        status, vendor = module.ensure(repo)
        text = path.read_text(encoding="utf-8")
        assert status == "created"
        assert vendor == "UNKNOWN"
        assert 'application_runtime: "CONTAINER"' in text
        assert 'database_runtime: "CONTAINER"' in text
        assert 'database_platform: "NATIVE"' in text
        assert 'database_vendor: "UNKNOWN"' in text


def test_uses_single_detected_vendor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        tech = """\ntechnology:\n  database_vendors:\n    - \"postgresql\"\n  data_entry_candidate: \"dev-data-feature\"\n"""
        path = write_metadata(repo, metadata(tech))
        status, vendor = module.ensure(repo)
        text = path.read_text(encoding="utf-8")
        assert status == "created"
        assert vendor == "postgresql"
        assert 'database_vendor: "postgresql"' in text


def test_preserves_existing_desired_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        existing = metadata() + """\ninfrastructure:\n  version: \"1\"\n  application_runtime: \"LOCAL_HOST\"\n  database_runtime: \"NETWORK_HOST\"\n  database_platform: \"SUPABASE\"\n  database_vendor: \"postgresql\"\n"""
        path = write_metadata(repo, existing)
        before = path.read_text(encoding="utf-8")
        status, vendor = module.ensure(repo)
        after = path.read_text(encoding="utf-8")
        assert status == "preserved"
        assert vendor == "existing"
        assert before == after


if __name__ == "__main__":
    test_creates_container_defaults()
    test_uses_single_detected_vendor()
    test_preserves_existing_desired_state()
    print("PASS")
