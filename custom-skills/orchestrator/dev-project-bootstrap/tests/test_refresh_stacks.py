#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "refresh_stacks.py"
SPEC = importlib.util.spec_from_file_location("refresh_stacks", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def make_managed_repo(path: Path) -> None:
    (path / ".git").mkdir(parents=True)
    metadata = path / ".hermes" / "project.yaml"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        "# managed-by: dev-project-bootstrap\nversion: 3\n",
        encoding="utf-8",
    )


def test_discover_only_managed_repositories() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        managed = root / "product" / "managed"
        make_managed_repo(managed)

        unmanaged = root / "product" / "unmanaged"
        (unmanaged / ".git").mkdir(parents=True)
        (unmanaged / ".hermes").mkdir()
        (unmanaged / ".hermes" / "project.yaml").write_text("version: 3\n", encoding="utf-8")

        vendor = root / "node_modules" / "nested"
        make_managed_repo(vendor)

        discovered = MODULE.discover(root, 5)
        assert discovered == [managed.resolve()]


def test_discover_respects_depth() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shallow = root / "a" / "b"
        deep = root / "a" / "b" / "c" / "d"
        make_managed_repo(shallow)
        make_managed_repo(deep)

        discovered = MODULE.discover(root, 2)
        assert discovered == [shallow.resolve()]


if __name__ == "__main__":
    test_discover_only_managed_repositories()
    test_discover_respects_depth()
    print("TEST_STATUS=PASS")
