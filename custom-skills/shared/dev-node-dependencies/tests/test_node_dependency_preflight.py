from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT = SCRIPTS / "node_dependency_preflight.py"
WORKSPACE_HELPER = SCRIPTS / "node_workspace.py"


def make_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def output_value(stdout: str, key: str) -> str:
    prefix = key + "="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    raise AssertionError(f"missing {key}: {stdout}")


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
            "#!/usr/bin/env sh\n"
            'if [ "$1" = "config" ] && [ "$2" = "get" ]; then\n'
            '  key="$5"\n'
            '  case "$key" in\n'
            '    strictDepBuilds) printf "%s\\n" "${PNPM_TEST_STRICT_DEP_BUILDS:-true}" ;;\n'
            '    dangerouslyAllowAllBuilds) printf "%s\\n" "${PNPM_TEST_DANGEROUSLY_ALLOW_ALL_BUILDS:-false}" ;;\n'
            '    allowBuilds) if [ -n "${PNPM_TEST_ALLOW_BUILDS+x}" ]; then printf "%s\\n" "$PNPM_TEST_ALLOW_BUILDS"; else printf "{}\\n"; fi ;;\n'
            '    *) printf "null\\n" ;;\n'
            '  esac\n'
            'else\n'
            '  printf "12.5.1\\n"\n'
            'fi\n',
        )
        self.env = os.environ.copy()
        self.env["PATH"] = f"{self.fake_bin}:{self.env.get('PATH', '')}"
        self.env["HERMES_NODE_ROOT"] = str(self.base / "node-root")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_manifest(
        self,
        *,
        dependencies: dict[str, str] | None = None,
    ) -> None:
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

    def write_lock(self, marker: str = "one") -> None:
        (self.frontend / "pnpm-lock.yaml").write_text(
            f"lockfileVersion: '9.0'\n# {marker}\n",
            encoding="utf-8",
        )

    def run_preflight(
        self,
        *extra: str,
        package: str = "react",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workspace",
                str(self.workspace),
                "--package-root",
                "frontend",
                "--package",
                package,
                *extra,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=False,
        )

    def mark_restored(self, isolated: Path) -> subprocess.CompletedProcess[str]:
        installed = isolated / "node_modules" / "react"
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "package.json").write_text(
            '{"name":"react"}\n', encoding="utf-8"
        )
        return subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_HELPER),
                "--workspace",
                str(self.workspace),
                "--cwd",
                "frontend",
                "--mark-restored",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=False,
        )

    def test_absent_dependency_mutates_source_package_with_pnpm(self) -> None:
        self.write_manifest()

        proc = self.run_preflight()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PACKAGE_MANAGER=pnpm", proc.stdout)
        self.assertIn("PACKAGE_MANAGER_VERSION=12.5.1", proc.stdout)
        self.assertIn("NODE_REQUIREMENT=22.23.2", proc.stdout)
        self.assertIn("INSTALL_REQUIRED=true", proc.stdout)
        self.assertIn(
            "INSTALL_COMMAND=pnpm add --lockfile-only react",
            proc.stdout,
        )
        self.assertIn(f"INSTALL_WORKDIR={self.frontend}", proc.stdout)
        self.assertIn("RESTORE_COMMAND=NOT_REQUIRED", proc.stdout)
        self.assertIn("BUILD_REVIEW_MODE=SINGLE_REVIEW_BATCH", proc.stdout)
        self.assertIn("BUILD_REVIEW_COMMAND=NOT_REQUIRED", proc.stdout)
        self.assertIn("BUILD_REVIEW_WORKDIR=NOT_REQUIRED", proc.stdout)
        isolated = Path(
            output_value(proc.stdout, "VERIFICATION_PACKAGE_ROOT")
        )
        self.assertTrue(
            str(isolated).startswith(self.env["HERMES_NODE_ROOT"])
        )

    def test_dev_dependency_uses_pnpm_add_d(self) -> None:
        self.write_manifest()
        proc = self.run_preflight("--dependency-type", "dev")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(
            "INSTALL_COMMAND=pnpm add --lockfile-only -D react",
            proc.stdout,
        )

    def test_declared_dependency_restores_only_linux_workspace(self) -> None:
        self.write_manifest(dependencies={"react": "19.3.0"})
        self.write_lock()

        host_installed = self.frontend / "node_modules" / "react"
        host_installed.mkdir(parents=True)
        (host_installed / "package.json").write_text(
            '{"name":"react"}\n', encoding="utf-8"
        )

        proc = self.run_preflight()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("INSTALL_REQUIRED=false", proc.stdout)
        self.assertIn("DEPENDENCIES_READY=false", proc.stdout)
        self.assertIn("RESTORE_REQUIRED=true", proc.stdout)
        self.assertIn(
            "RESTORE_COMMAND=pnpm install --frozen-lockfile",
            proc.stdout,
        )
        isolated = Path(
            output_value(proc.stdout, "VERIFICATION_PACKAGE_ROOT")
        )
        self.assertIn(f"RESTORE_WORKDIR={isolated}", proc.stdout)
        self.assertIn("RESTORE_MARK_COMMAND=python3 ", proc.stdout)
        self.assertIn("BUILD_REVIEW_MODE=SINGLE_REVIEW_BATCH", proc.stdout)
        self.assertIn("BUILD_REVIEW_COMMAND=pnpm ignored-builds", proc.stdout)
        self.assertIn(f"BUILD_REVIEW_WORKDIR={isolated}", proc.stdout)
        self.assertNotEqual(isolated, self.frontend)
        self.assertFalse(
            (isolated / "node_modules" / "react" / "package.json").exists()
        )

    def test_linux_node_modules_are_reused_only_after_restore_mark(self) -> None:
        self.write_manifest(dependencies={"react": "19.3.0"})
        self.write_lock()
        first = self.run_preflight()
        self.assertEqual(first.returncode, 0, first.stderr)
        isolated = Path(
            output_value(first.stdout, "VERIFICATION_PACKAGE_ROOT")
        )

        marked = self.mark_restored(isolated)
        self.assertEqual(marked.returncode, 0, marked.stderr)
        self.assertIn("NODE_DEPENDENCIES_READY=true", marked.stdout)

        second = self.run_preflight()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn(
            "DEPENDENCY_1_NODE_MODULES_STATE=PRESENT_DECLARED",
            second.stdout,
        )
        self.assertIn("DEPENDENCIES_READY=true", second.stdout)
        self.assertIn("RESTORE_REQUIRED=false", second.stdout)
        self.assertTrue(
            (isolated / "node_modules" / "react" / "package.json").is_file()
        )

    def test_fingerprint_change_forces_restore_and_drops_stale_modules(self) -> None:
        self.write_manifest(dependencies={"react": "19.3.0"})
        self.write_lock()
        first = self.run_preflight()
        isolated = Path(
            output_value(first.stdout, "VERIFICATION_PACKAGE_ROOT")
        )
        marked = self.mark_restored(isolated)
        self.assertEqual(marked.returncode, 0, marked.stderr)

        self.write_lock(marker="changed")
        second = self.run_preflight()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("DEPENDENCIES_READY=false", second.stdout)
        self.assertIn("RESTORE_REQUIRED=true", second.stdout)
        self.assertFalse((isolated / "node_modules").exists())

    def test_build_policy_evidence_is_reported(self) -> None:
        self.write_manifest(dependencies={"react": "19.3.0"})
        self.write_lock()
        self.env["PNPM_TEST_ALLOW_BUILDS"] = json.dumps(
            {"unrs-resolver@1.12.2": True}
        )

        proc = self.run_preflight()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(
            "PNPM_APPROVED_BUILDS=unrs-resolver@1.12.2",
            proc.stdout,
        )
        self.assertIn("PNPM_STRICT_DEP_BUILDS=true", proc.stdout)
        self.assertIn(
            "PNPM_DANGEROUSLY_ALLOW_ALL_BUILDS=false",
            proc.stdout,
        )

    def test_unsafe_build_policy_blocks_dependency_preflight(self) -> None:
        self.write_manifest(dependencies={"react": "19.3.0"})
        self.write_lock()
        self.env["PNPM_TEST_DANGEROUSLY_ALLOW_ALL_BUILDS"] = "true"

        proc = self.run_preflight()

        self.assertEqual(proc.returncode, 2)
        self.assertIn("PNPM_BUILD_POLICY_UNSAFE", proc.stderr)
        self.assertIn("dangerouslyAllowAllBuilds=true", proc.stderr)

    def test_declared_dependency_without_pnpm_lock_blocks_restore(self) -> None:
        self.write_manifest(dependencies={"react": "19.3.0"})
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("pnpm-lock.yaml is required", proc.stderr)

    def test_legacy_package_lock_blocks_instead_of_falling_back(self) -> None:
        self.write_manifest()
        (self.frontend / "package-lock.json").write_text(
            "{}\n", encoding="utf-8"
        )
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 2)
        self.assertIn(
            "legacy package-manager lockfile detected", proc.stderr
        )

    def test_non_pnpm_manager_blocks(self) -> None:
        self.write_manifest()
        manifest = json.loads(
            (self.frontend / "package.json").read_text(encoding="utf-8")
        )
        manifest["devEngines"]["packageManager"]["name"] = "npm"
        (self.frontend / "package.json").write_text(
            json.dumps(manifest) + "\n", encoding="utf-8"
        )
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("packageManager.name must be 'pnpm'", proc.stderr)

    def test_missing_node_runtime_blocks(self) -> None:
        self.write_manifest()
        manifest = json.loads(
            (self.frontend / "package.json").read_text(encoding="utf-8")
        )
        manifest["devEngines"].pop("runtime")
        (self.frontend / "package.json").write_text(
            json.dumps(manifest) + "\n", encoding="utf-8"
        )
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 2)
        self.assertIn(
            "must declare exactly one Node runtime", proc.stderr
        )

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

    def test_package_discovery_ignores_generated_manifests(self) -> None:
        self.write_manifest()
        nested = self.frontend / "node_modules" / "some-package"
        nested.mkdir(parents=True)
        (nested / "package.json").write_text(
            '{"name":"some-package"}\n', encoding="utf-8"
        )
        generated = self.frontend / ".next" / "server"
        generated.mkdir(parents=True)
        (generated / "package.json").write_text(
            '{"name":"generated"}\n', encoding="utf-8"
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
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"PACKAGE_ROOT={self.frontend}", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
