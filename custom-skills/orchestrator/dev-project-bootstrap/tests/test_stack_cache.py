#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stack_cache.py"
SPEC = importlib.util.spec_from_file_location("stack_cache", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def metadata(repo: Path) -> Path:
    path = repo / ".hermes" / "project.yaml"
    write(path, """# managed-by: dev-project-bootstrap
version: 2

project:
  id: "sample"
  name: "sample"
  repository: "/workspace/sample"

kanban:
  board: "sample"

git:
  default_base_branch: "dev"
  worktree_root: "/workspace/.worktrees/sample"

profiles:
  orchestrator: "orchestrator"
  coder: "coder"
  reviewer: "reviewer"

resolver:
  aliases:
    - legacy
  modules: []
  files: []
  paths: []

custom_policy:
  keep: true
""")
    return path


def test_create_reuse_and_refresh() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        meta = metadata(repo)
        write(repo / "backend" / "build.gradle", 'plugins { id "org.springframework.boot" }')
        write(repo / "frontend" / "package.json", '{"dependencies":{"react":"19","next":"16"},"devDependencies":{"typescript":"5"}}')
        write(repo / "frontend" / "tsconfig.json", "{}")

        status1, result1 = MODULE.resolve(repo)
        text1 = meta.read_text(encoding="utf-8")
        assert status1 == "created"
        assert "version: 3" in text1
        assert "technology:" in text1
        assert '    - "java"' in text1
        assert '    - "spring"' in text1
        assert '    - "typescript"' in text1
        assert '    - "react"' in text1
        assert '    - "nextjs"' in text1
        assert "custom_policy:\n  keep: true" in text1
        assert "resolver:\n  aliases:\n    - legacy" in text1

        status2, result2 = MODULE.resolve(repo)
        assert status2 == "reused"
        assert result2["fingerprint"] == result1["fingerprint"]
        assert meta.read_text(encoding="utf-8") == text1

        write(repo / "frontend" / "package.json", '{"dependencies":{"react":"19"},"devDependencies":{"typescript":"5"}}')
        status3, result3 = MODULE.resolve(repo)
        assert status3 == "updated"
        assert result3["fingerprint"] != result1["fingerprint"]
        assert "nextjs" not in result3["stacks"]


def test_kotlin_stack_is_cached_and_reused() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        meta = metadata(repo)
        write(repo / "build.gradle.kts", '''
plugins {
    kotlin("jvm") version "2.4.20"
    id("org.springframework.boot") version "4.0.0"
}
''')

        status1, result1 = MODULE.resolve(repo)
        text1 = meta.read_text(encoding="utf-8")
        assert status1 == "created"
        assert result1["detector_version"] == "3"
        assert result1["stacks"] == ["kotlin", "spring"]
        assert result1["backend_skills"] == ["dev-kotlin-guidelines", "dev-spring-guidelines"]
        assert '  detector_version: "3"' in text1
        assert '    - "kotlin"' in text1
        assert '    - "dev-kotlin-guidelines"' in text1
        assert '    - "java"' not in text1

        status2, result2 = MODULE.resolve(repo)
        assert status2 == "reused"
        assert result2["stacks"] == ["kotlin", "spring"]
        assert result2["fingerprint"] == result1["fingerprint"]
        assert meta.read_text(encoding="utf-8") == text1


def test_source_change_keeps_cache_hit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        meta = metadata(repo)
        write(repo / "package.json", '{"dependencies":{"react":"19"}}')
        status1, _ = MODULE.resolve(repo)
        assert status1 == "created"
        before = meta.read_text(encoding="utf-8")
        write(repo / "src" / "App.tsx", "export const App = () => null")
        status2, _ = MODULE.resolve(repo)
        assert status2 == "reused"
        assert meta.read_text(encoding="utf-8") == before


def test_unmanaged_metadata_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / ".hermes" / "project.yaml", "version: 2\n")
        write(repo / "package.json", '{}')
        try:
            MODULE.resolve(repo)
        except MODULE.StackCacheError:
            pass
        else:
            raise AssertionError("unmanaged metadata must be rejected")


if __name__ == "__main__":
    test_create_reuse_and_refresh()
    test_kotlin_stack_is_cached_and_reused()
    test_source_change_keeps_cache_hit()
    test_unmanaged_metadata_is_blocked()
    print("TEST_STATUS=PASS")
