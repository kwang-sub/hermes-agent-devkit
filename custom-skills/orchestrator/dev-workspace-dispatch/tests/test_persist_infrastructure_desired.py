from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "persist_infrastructure_desired.py"
SPEC = importlib.util.spec_from_file_location("persist_infrastructure_desired", SCRIPT)
assert SPEC and SPEC.loader
persist = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(persist)


def project_yaml(root: Path, infrastructure: str) -> Path:
    path = root / ".hermes" / "project.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# managed-by: dev-project-bootstrap\n"
        "version: 3\n\n"
        "project:\n"
        "  id: \"demo\"\n"
        "  name: \"demo\"\n"
        f"  repository: \"{root}\"\n\n"
        "technology:\n"
        "  stacks:\n"
        "    - \"spring\"\n\n"
        + infrastructure,
        encoding="utf-8",
    )
    return path


def desired(**overrides: str) -> dict[str, str]:
    values = {
        "application_runtime": "CONTAINER",
        "application_host": "unknown",
        "application_port": "unknown",
        "database_runtime": "NETWORK_HOST",
        "database_host": "db-new.internal",
        "database_port": "5544",
        "database_platform": "NATIVE",
        "database_vendor": "postgresql",
    }
    values.update(overrides)
    return values


def test_approved_desired_state_replaces_existing_section_and_preserves_other_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        path = project_yaml(
            root,
            "infrastructure:\n"
            "  version: \"1\"\n"
            "  desired:\n"
            "    application_runtime: \"LOCAL_HOST\"\n"
            "    database_runtime: \"LOCAL_HOST\"\n"
            "    database_platform: \"NATIVE\"\n"
            "    database_vendor: \"postgresql\"\n",
        )
        status, normalized = persist.persist(root, desired())
        text = path.read_text(encoding="utf-8")

        assert status == "updated"
        assert normalized["database_host"] == "db-new.internal"
        assert 'version: "2"' in text
        assert 'database_runtime: "NETWORK_HOST"' in text
        assert 'database_host: "db-new.internal"' in text
        assert 'database_port: "5544"' in text
        assert "technology:" in text
        assert '    - "spring"' in text


def test_persistence_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        project_yaml(root, "")
        first_status, first = persist.persist(root, desired())
        before = (root / ".hermes" / "project.yaml").read_text(encoding="utf-8")
        second_status, second = persist.persist(root, desired())
        after = (root / ".hermes" / "project.yaml").read_text(encoding="utf-8")

        assert first_status == "updated"
        assert second_status == "reused"
        assert first == second
        assert before == after


def test_supabase_desired_state_normalizes_vendor_to_postgresql() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        project_yaml(root, "")
        status, normalized = persist.persist(
            root,
            desired(database_platform="SUPABASE", database_vendor="unknown"),
        )
        assert status == "updated"
        assert normalized["database_vendor"] == "postgresql"


def test_url_or_credential_is_rejected_as_host() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        project_yaml(root, "")
        try:
            persist.persist(root, desired(database_host="postgres://user:secret@db.internal"))
        except persist.DesiredStateError as exc:
            assert "hostname/address only" in str(exc)
        else:
            raise AssertionError("credential-bearing host must be rejected")


if __name__ == "__main__":
    test_approved_desired_state_replaces_existing_section_and_preserves_other_metadata()
    test_persistence_is_idempotent()
    test_supabase_desired_state_normalizes_vendor_to_postgresql()
    test_url_or_credential_is_rejected_as_host()
    print("PASS")
