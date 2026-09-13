#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "node_dependency_preflight.py"


class NodeDependencyPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name) / "repo"
        self.frontend = self.workspace / "frontend"
        self.frontend.mkdir(parents=True)
        self.write_manifest({"name": "fixture", "private": True})
        (self.frontend / "package-lock.json").write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_manifest(self, data: dict) -> None:
        (self.frontend / "package.json").write_text(json.dumps(data), encoding="utf-8")

    def run_helper(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(self.workspace), "--package-root", "frontend", *extra],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_absent_dependency_with_extraneous_node_modules_requires_install(self) -> None:
        installed = self.frontend / "node_modules" / "@supabase" / "ssr"
        installed.mkdir(parents=True)
        (installed / "package.json").write_text('{"name":"@supabase/ssr"}\n', encoding="utf-8")

        proc = self.run_helper("--package", "@supabase/ssr", "--dependency-type", "prod")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PACKAGE_MANAGER=npm", proc.stdout)
        self.assertIn(f"PACKAGE_MANAGER_ROOT={self.frontend}", proc.stdout)
        self.assertIn(f"CANONICAL_LOCKFILE={self.frontend / 'package-lock.json'}", proc.stdout)
        self.assertIn("LOCKFILE_PRESENT=true", proc.stdout)
        self.assertIn("DEPENDENCY_1_MANIFEST_STATE=ABSENT", proc.stdout)
        self.assertIn("DEPENDENCY_1_NODE_MODULES_STATE=EXTRANEOUS_PRESENT", proc.stdout)
        self.assertIn("INSTALL_REQUIRED=true", proc.stdout)
        self.assertIn("INSTALL_COMMAND=npm install @supabase/ssr", proc.stdout)
        self.assertIn("STATUS=pass", proc.stdout)

    def test_declared_dependency_does_not_request_add(self) -> None:
        self.write_manifest({"name": "fixture", "dependencies": {"react": "19.1.0"}})
        proc = self.run_helper("--package", "react")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("DEPENDENCY_1_MANIFEST_STATE=DECLARED_PROD", proc.stdout)
        self.assertIn("INSTALL_REQUIRED=false", proc.stdout)
        self.assertIn("INSTALL_COMMAND=NOT_REQUIRED", proc.stdout)

    def test_dev_dependency_command_uses_save_dev(self) -> None:
        proc = self.run_helper("--package", "vitest", "--dependency-type", "dev")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("INSTALL_COMMAND=npm install --save-dev vitest", proc.stdout)

    def test_conflicting_lockfiles_block(self) -> None:
        (self.frontend / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
        proc = self.run_helper("--package", "react")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("conflicting package manager lockfiles", proc.stderr)
        self.assertIn("STATUS=blocked", proc.stderr)

    def test_package_manager_field_lockfile_mismatch_blocks(self) -> None:
        self.write_manifest({"name": "fixture", "packageManager": "pnpm@9.0.0"})
        proc = self.run_helper("--package", "react")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("packageManager/lockfile mismatch", proc.stderr)

    def test_obvious_node_major_mismatch_blocks(self) -> None:
        (self.frontend / ".nvmrc").write_text("999\n", encoding="utf-8")
        proc = self.run_helper("--package", "react")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("node version mismatch", proc.stderr)

    def test_nested_package_inherits_workspace_manager_and_lockfile(self) -> None:
        (self.frontend / "package-lock.json").unlink()
        (self.workspace / "package.json").write_text(
            json.dumps({"name": "root", "private": True, "workspaces": ["frontend"]}),
            encoding="utf-8",
        )
        (self.workspace / "package-lock.json").write_text("{}\n", encoding="utf-8")

        proc = self.run_helper("--package", "@supabase/ssr")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PACKAGE_MANAGER=npm", proc.stdout)
        self.assertIn(f"PACKAGE_MANAGER_ROOT={self.workspace}", proc.stdout)
        self.assertIn(f"CANONICAL_LOCKFILE={self.workspace / 'package-lock.json'}", proc.stdout)
        self.assertIn("LOCKFILE_PRESENT=true", proc.stdout)
        self.assertIn("INSTALL_COMMAND=npm install @supabase/ssr", proc.stdout)

    def test_package_manager_without_lockfile_reports_expected_canonical_lock(self) -> None:
        (self.frontend / "package-lock.json").unlink()
        npm_version = subprocess.run(
            ["npm", "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        ).stdout.strip()
        self.write_manifest({"name": "fixture", "packageManager": f"npm@{npm_version}"})

        proc = self.run_helper("--package", "react")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"CANONICAL_LOCKFILE={self.frontend / 'package-lock.json'}", proc.stdout)
        self.assertIn("LOCKFILE_PRESENT=false", proc.stdout)

    def test_ambiguous_package_roots_require_explicit_root(self) -> None:
        other = self.workspace / "admin"
        other.mkdir()
        (other / "package.json").write_text('{"name":"admin"}\n', encoding="utf-8")
        (other / "package-lock.json").write_text("{}\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(self.workspace), "--package", "react"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("package root is ambiguous", proc.stderr)

    def test_package_discovery_ignores_node_modules_manifests(self) -> None:
        nested = self.frontend / "node_modules" / "some-package"
        nested.mkdir(parents=True)
        (nested / "package.json").write_text('{"name":"some-package"}\n', encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(self.workspace), "--package", "react"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"PACKAGE_ROOT={self.frontend}", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
