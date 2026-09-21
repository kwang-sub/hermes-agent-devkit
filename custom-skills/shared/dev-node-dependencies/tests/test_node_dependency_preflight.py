#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "node_dependency_preflight.py"


def write_package_json(path: Path, *, manager: str = "pnpm", include_dev_engines: bool = True) -> None:
    data: dict = {
        "name": "frontend",
        "private": True,
        "dependencies": {"react": "^19.0.0"},
    }
    if include_dev_engines:
        data["devEngines"] = {
            "runtime": {
                "name": "node",
                "version": "^24.11.0",
                "onFail": "download",
            },
            "packageManager": {
                "name": manager,
                "version": ">=12 <13",
                "onFail": "download",
            },
        }
    (path / "package.json").write_text(json.dumps(data), encoding="utf-8")


def make_fake_pnpm(root: Path) -> Path:
    binary = root / "bin" / "pnpm"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\necho 12.0.0\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary.parent


class NodeDependencyPreflightTest(unittest.TestCase):
    def run_preflight(
        self,
        workspace: Path,
        *,
        package: str = "react",
        package_root: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [
            "python3",
            str(SCRIPT),
            "--workspace",
            str(workspace),
            "--package",
            package,
        ]
        if package_root is not None:
            cmd += ["--package-root", package_root]
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=env,
        )

    def test_reads_node_and_pnpm_versions_from_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            frontend = workspace / "frontend"
            frontend.mkdir()
            write_package_json(frontend)
            (frontend / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
            fake_bin = make_fake_pnpm(workspace)
            result = self.run_preflight(
                workspace,
                package_root="frontend",
                extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH','')}"},
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("PACKAGE_MANAGER=pnpm", result.stdout)
            self.assertIn("PACKAGE_MANAGER_REQUIRED_VERSION=>=12 <13", result.stdout)
            self.assertIn("NODE_REQUIREMENT=^24.11.0", result.stdout)
            self.assertIn("NODE_VERSION=managed-by-pnpm", result.stdout)
            self.assertIn("CANONICAL_LOCKFILE=", result.stdout)
            self.assertIn("pnpm-lock.yaml", result.stdout)

    def test_missing_dev_engines_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            frontend = workspace / "frontend"
            frontend.mkdir()
            write_package_json(frontend, include_dev_engines=False)
            fake_bin = make_fake_pnpm(workspace)
            result = self.run_preflight(
                workspace,
                package_root="frontend",
                extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH','')}"},
            )
            self.assertEqual(2, result.returncode)
            self.assertIn("devEngines is required", result.stderr)

    def test_non_pnpm_manager_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            frontend = workspace / "frontend"
            frontend.mkdir()
            write_package_json(frontend, manager="npm")
            fake_bin = make_fake_pnpm(workspace)
            result = self.run_preflight(
                workspace,
                package_root="frontend",
                extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH','')}"},
            )
            self.assertEqual(2, result.returncode)
            self.assertIn("must declare pnpm", result.stderr)

    def test_install_command_is_always_pnpm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            frontend = workspace / "frontend"
            frontend.mkdir()
            write_package_json(frontend)
            fake_bin = make_fake_pnpm(workspace)
            result = self.run_preflight(
                workspace,
                package="zod",
                package_root="frontend",
                extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH','')}"},
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("INSTALL_REQUIRED=true", result.stdout)
            self.assertIn("INSTALL_COMMAND=pnpm add zod", result.stdout)

    def test_package_discovery_ignores_node_modules_and_next_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            frontend = workspace / "frontend"
            frontend.mkdir()
            write_package_json(frontend)
            nested = frontend / "node_modules" / "some-package"
            nested.mkdir(parents=True)
            (nested / "package.json").write_text('{"name":"some-package"}\n', encoding="utf-8")
            generated = frontend / ".next-hermes" / "server"
            generated.mkdir(parents=True)
            (generated / "package.json").write_text('{"name":"generated"}\n', encoding="utf-8")
            fake_bin = make_fake_pnpm(workspace)
            result = self.run_preflight(
                workspace,
                extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH','')}"},
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn(f"PACKAGE_ROOT={frontend}", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
