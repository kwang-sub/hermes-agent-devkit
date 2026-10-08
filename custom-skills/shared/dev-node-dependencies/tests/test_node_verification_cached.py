#!/usr/bin/env python3
"""Canonical Node PASS reuse and invalidation regression."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import node_verification_cached as cached


class PnpmEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()
        self.evidence = Path(self.temp.name) / "evidence"
        (self.workspace / "package.json").write_text(
            json.dumps({"name": "test", "scripts": {"typecheck": "tsc -p ."}}),
            encoding="utf-8",
        )
        (self.workspace / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
        (self.workspace / "app.ts").write_text("export const number = 1;\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cached(self, command: list[str] | None = None) -> int:
        return cached.run(
            workspace=self.workspace, cwd=self.workspace,
            mode="STATIC_COMPILE", command=command or ["pnpm", "run", "typecheck"],
            scope_paths=["app.ts"], evidence_root=self.evidence,
        )

    def test_reuses_identical_scope_but_invalidates_mutation(self):
        with patch.object(cached, "validate_project_environment"), patch.object(
            cached, "isolated_workspace_ready", return_value=True,
        ), patch.object(
            cached, "execute_runtime", return_value=0,
        ) as runner:
            self.assertEqual(self.run_cached(), 0)
            self.assertEqual(self.run_cached(), 0)
            self.assertEqual(runner.call_count, 1)
            (self.workspace / "app.ts").write_text("export const number = 2;\n")
            self.assertEqual(self.run_cached(), 0)
            self.assertEqual(runner.call_count, 2)
            (self.workspace / "package.json").write_text(
                json.dumps({"name": "test", "scripts": {"typecheck": "tsc --noEmit"}})
            )
            self.assertEqual(self.run_cached(), 0)
            self.assertEqual(runner.call_count, 3)

    def test_failure_is_never_reused(self):
        with patch.object(cached, "validate_project_environment"), patch.object(
            cached, "isolated_workspace_ready", return_value=True,
        ), patch.object(
            cached, "execute_runtime", side_effect=[1, 0],
        ) as runner:
            self.assertEqual(self.run_cached(), 1)
            self.assertEqual(self.run_cached(), 0)
            self.assertEqual(self.run_cached(), 0)
            self.assertEqual(runner.call_count, 2)

    def test_source_modified_during_verification_blocks_receipt(self):
        def modify(*args, **kwargs):
            (self.workspace / "app.ts").write_text("changed during compile\n")
            return 0
        with patch.object(cached, "validate_project_environment"), patch.object(
            cached, "isolated_workspace_ready", return_value=True,
        ), patch.object(
            cached, "execute_runtime", side_effect=modify,
        ):
            self.assertEqual(self.run_cached(), 2)

    def test_cannot_skip_gate_on_cache_reuse(self):
        with patch.object(cached, "validate_project_environment", side_effect=[
            None, cached.EnvironmentGateError("policy invalid"),
        ]), patch.object(cached, "isolated_workspace_ready", return_value=True), patch.object(cached, "execute_runtime", return_value=0):
            self.assertEqual(self.run_cached(), 0)
            with self.assertRaises(cached.EnvironmentGateError):
                self.run_cached()

    def test_cache_hit_requires_ready_isolated_dependencies(self):
        with patch.object(cached, "validate_project_environment"), patch.object(
            cached, "isolated_workspace_ready", side_effect=[False, False],
        ), patch.object(cached, "execute_runtime", return_value=0) as runner:
            self.assertEqual(self.run_cached(), 0)
            self.assertEqual(self.run_cached(), 0)
            self.assertEqual(runner.call_count, 2)

    def test_package_build_produces_fresh_artifact_not_reused(self):
        with patch.object(cached, "validate_project_environment"), patch.object(
            cached, "isolated_workspace_ready", return_value=True,
        ), patch.object(cached, "execute_runtime", return_value=0) as runner:
            for _ in range(2):
                self.assertEqual(cached.run(
                    workspace=self.workspace, cwd=self.workspace,
                    mode="PACKAGE_BUILD", command=["pnpm", "run", "build"],
                    scope_paths=["app.ts"], evidence_root=self.evidence,
                ), 0)
            self.assertEqual(runner.call_count, 2)

    def test_explicit_no_reuse_for_environment_dependent_test(self):
        with patch.object(cached, "validate_project_environment"), patch.object(
            cached, "isolated_workspace_ready", return_value=True,
        ), patch.object(cached, "execute_runtime", return_value=0) as runner:
            for _ in range(2):
                self.assertEqual(cached.run(
                    workspace=self.workspace, cwd=self.workspace,
                    mode="TARGETED_TEST", command=["pnpm", "run", "test"],
                    scope_paths=["app.ts"], evidence_root=self.evidence,
                    no_reuse=True,
                ), 0)
            self.assertEqual(runner.call_count, 2)

    def test_env_and_secondary_config_mutations_invalidate_cache(self):
        with patch.object(cached, "validate_project_environment"), patch.object(
            cached, "isolated_workspace_ready", return_value=True,
        ), patch.object(cached, "execute_runtime", return_value=0) as runner:
            self.assertEqual(self.run_cached(), 0)
            (self.workspace / ".env.local").write_text("FEATURE_ENABLED=true\\n")
            self.assertEqual(self.run_cached(), 0)
            (self.workspace / "tsconfig.paths.json").write_text('{"compilerOptions": {}}')
            self.assertEqual(self.run_cached(), 0)
            self.assertEqual(runner.call_count, 3)

    def test_reject_mutation_command_or_invalid_scope(self):
        with self.assertRaises(cached.RuntimeErrorPolicy):
            self.run_cached(["pnpm", "install"])
        with patch.object(cached, "validate_project_environment"):
            with self.assertRaises(cached.VerificationError):
                cached.run(
                    workspace=self.workspace, cwd=self.workspace,
                    mode="TARGETED_TEST", command=["pnpm", "test"],
                    scope_paths=["../../outside"], evidence_root=self.evidence,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
