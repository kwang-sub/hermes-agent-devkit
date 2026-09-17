from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "infrastructure_cache.py"
SPEC = importlib.util.spec_from_file_location("infrastructure_cache", SCRIPT)
assert SPEC and SPEC.loader
cache = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cache)


def project_yaml(root: Path, extra: str = "") -> Path:
    path = root / ".hermes" / "project.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# managed-by: dev-project-bootstrap\n"
        "version: 3\n\n"
        "project:\n"
        "  id: \"demo\"\n"
        "  name: \"demo\"\n"
        "  repository: \"/tmp/demo\"\n\n"
        "technology:\n"
        "  database_vendors:\n"
        "    - \"postgresql\"\n"
        + extra,
        encoding="utf-8",
    )
    return path


def test_missing_infrastructure_defaults_to_container() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = project_yaml(root)
        status, desired = cache.initialize(root)
        text = path.read_text(encoding="utf-8")
        assert status == "created"
        assert desired["application_runtime"] == "CONTAINER"
        assert desired["database_runtime"] == "CONTAINER"
        assert desired["database_vendor"] == "postgresql"
        assert 'application_runtime: "CONTAINER"' in text
        assert 'database_runtime: "CONTAINER"' in text


def test_existing_infrastructure_is_not_overwritten() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        existing = (
            "\ninfrastructure:\n"
            "  version: \"1\"\n"
            "  desired:\n"
            "    application_runtime: \"LOCAL_HOST\"\n"
            "    database_runtime: \"NETWORK_HOST\"\n"
            "    database_platform: \"SUPABASE\"\n"
            "    database_vendor: \"postgresql\"\n"
        )
        path = project_yaml(root, existing)
        before = path.read_text(encoding="utf-8")
        status, desired = cache.initialize(root)
        after = path.read_text(encoding="utf-8")
        assert status == "reused"
        assert before == after
        assert desired == {
            "application_runtime": "LOCAL_HOST",
            "database_runtime": "NETWORK_HOST",
            "database_platform": "SUPABASE",
            "database_vendor": "postgresql",
        }


def test_incomplete_existing_infrastructure_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        existing = (
            "\ninfrastructure:\n"
            "  version: \"1\"\n"
            "  desired:\n"
            "    application_runtime: \"LOCAL_HOST\"\n"
        )
        project_yaml(root, existing)
        try:
            cache.initialize(root)
        except cache.InfrastructureCacheError as exc:
            assert "incomplete" in str(exc)
        else:
            raise AssertionError("incomplete explicit infrastructure state must not be inferred over")


if __name__ == "__main__":
    test_missing_infrastructure_defaults_to_container()
    test_existing_infrastructure_is_not_overwritten()
    test_incomplete_existing_infrastructure_is_rejected()
    print("PASS")
