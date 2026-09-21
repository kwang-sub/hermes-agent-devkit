from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "node_dependency_preflight.py"


def make_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


class NodeDependencyPreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.workspace = self.base / "workspace"
        self.frontend = self.workspace / "frontend"
        self.frontend.mkdir(parents=True)
        self.fake_bin = self.base / "bin"
        self.fake_bin.mkdir()
        make_executable(
            self.fake_bin / "pnpm",
            "#!/usr/bin/env sh\nprintf '12.5.1\\n'\n",
        )
        self.env = os.environ.copy()
        self.env["PATH"] = f"{self.fake_bin}:{self.env.get('PATH', '')}"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_manifest(self, *, dependencies: dict[str, str] | None = None) -> None:
        manifest = {
            "name": "frontend",
            "private": True,
            "devEngines": {
                "runtime": {
                    "name": "node",
                    "version": "22.23.2",
                    "onFail": "download",
                },
                "packageManager": {
                    "name": "pnpm",
                    "version": ">=12.0.0 <13.0.0",
                    "onFail": "download",
                },
            },
            "dependencies": dependencies or {},
        }
        (self.frontend / "package.json").write_text(
            json.dumps(manifest) + "\n",
            encoding="utf-8",
        )

    def run_preflight(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workspace",
                str(self.workspace),
                "--package-root",
                "frontend",
                "--package",
                "react",
                *extra,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=False,
        )

    def test_pnpm_project_uses_dev_engines_as_toolchain_source(self) -> None:
        self.write_manifest()
        (self.frontend / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")

        proc = self.run_preflight()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PACKAGE_MANAGER=pnpm", proc.stdout)
        self.assertIn("PACKAGE_MANAGER_SOURCE=package.json devEngines.packageManager", proc.stdout)
        self.assertIn("PACKAGE_MANAGER_VERSION=12.5.1", proc.stdout)
        self.assertIn("PACKAGE_MANAGER_REQUIRED_VERSION=>=12.0.0 <13.0.0", proc.stdout)
        self.assertIn("NODE_VERSION=managed-by-pnpm", proc.stdout)
        self.assertIn("NODE_REQUIREMENT=22.23.2", proc.stdout)
        self.assertIn("NODE_REQUIREMENT_CHECK=pnpm-managed", proc.stdout)
        self.assertIn("CANONICAL_LOCKFILE=", proc.stdout)
        self.assertIn("pnpm-lock.yaml", proc.stdout)
        self.assertIn("INSTALL_COMMAND=pnpm add react", proc.stdout)
        self.assertIn("STATUS=pass", proc.stdout)

    def test_dev_dependency_uses_pnpm_add_d(self) -> None:
        self.write_manifest()
        proc = self.run_preflight("--dependency-type", "dev")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("INSTALL_COMMAND=pnpm add -D react", proc.stdout)

    def test_legacy_package_lock_blocks_instead_of_falling_back(self) -> None:
        self.write_manifest()
        (self.frontend / "package-lock.json").write_text("{}\n", encoding="utf-8")
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("legacy package-manager lockfile detected", proc.stderr)

    def test_non_pnpm_manager_blocks(self) -> None:
        self.write_manifest()
        manifest = json.loads((self.frontend / "package.json").read_text(encoding="utf-8"))
        manifest["devEngines"]["packageManager"]["name"] = "npm"
        (self.frontend / "package.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("packageManager.name must be 'pnpm'", proc.stderr)

    def test_missing_node_runtime_blocks(self) -> None:
        self.write_manifest()
        manifest = json.loads((self.frontend / "package.json").read_text(encoding="utf-8"))
        manifest["devEngines"].pop("runtime")
        (self.frontend / "package.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("must declare exactly one Node runtime", proc.stderr)

    def test_declared_dependency_missing_from_node_modules_requests_restore(self) -> None:
        self.write_manifest(dependencies={"react": "19.3.0"})
        (self.frontend / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("INSTALL_REQUIRED=false", proc.stdout)
        self.assertIn("RESTORE_REQUIRED=true", proc.stdout)
        self.assertIn("RESTORE_COMMAND=pnpm install --frozen-lockfile", proc.stdout)

    def test_extraneous_node_modules_does_not_replace_manifest_evidence(self) -> None:
        self.write_manifest()
        installed = self.frontend / "node_modules" / "react"
        installed.mkdir(parents=True)
        (installed / "package.json").write_text('{"name":"react"}\n', encoding="utf-8")
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("DEPENDENCY_1_MANIFEST_STATE=ABSENT", proc.stdout)
        self.assertIn("DEPENDENCY_1_NODE_MODULES_STATE=EXTRANEOUS_PRESENT", proc.stdout)
        self.assertIn("INSTALL_REQUIRED=true", proc.stdout)

    def test_package_root_is_ambiguous_without_explicit_root(self) -> None:
        self.write_manifest()
        other = self.workspace / "other"
        other.mkdir()
        (other / "package.json").write_text(
            (self.frontend / "package.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workspace",
                str(self.workspace),
                "--package",
                "react",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("package root is ambiguous", proc.stderr)

    def test_package_discovery_ignores_node_modules_manifests(self) -> None:
        self.write_manifest()
        nested = self.frontend / "node_modules" / "some-package"
        nested.mkdir(parents=True)
        (nested / "package.json").write_text('{"name":"some-package"}\n', encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workspace",
                str(self.workspace),
                "--package",
                "react",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"PACKAGE_ROOT={self.frontend}", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
