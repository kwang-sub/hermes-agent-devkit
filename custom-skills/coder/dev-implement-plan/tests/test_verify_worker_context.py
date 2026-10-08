#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_worker_context.py"


class VerifyWorkerContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "repo"
        self.workspace.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def base_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update({
            "HERMES_KANBAN_TASK": "t_demo",
            "HERMES_KANBAN_BOARD": "demo",
            "HERMES_KANBAN_DB": str(Path(self.tmp.name) / "kanban.db"),
            "HERMES_KANBAN_WORKSPACE": str(self.workspace.resolve()),
            "HERMES_PROFILE": "coder",
            "HERMES_SESSION_SOURCE": "kanban",
            "HERMES_KANBAN_CONTEXT_VERSION": "1",
            "HERMES_KANBAN_SESSION_MODE": "NEW",
        })
        env.pop("HERMES_DELEGATED_CHILD_CONTEXT", None)
        return env

    def run_helper(
        self, env: dict[str, str], provider: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        arguments = [
            sys.executable, str(SCRIPT),
            "--expected-workspace", str(self.workspace),
            "--expected-profile", "coder",
        ]
        if provider is not None:
            arguments.extend(["--worker-provider", provider])
        return subprocess.run(
            arguments, text=True, capture_output=True, env=env,
        )

    def test_accepts_dispatcher_worker_context(self) -> None:
        proc = self.run_helper(self.base_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("WORKER_CONTEXT_STATUS=valid", proc.stdout)
        self.assertIn("KANBAN_TASK_ID=t_demo", proc.stdout)
        self.assertIn("KANBAN_BOARD=demo", proc.stdout)
        self.assertIn("KANBAN_PROFILE=coder", proc.stdout)
        self.assertIn("KANBAN_SESSION_MODE=NEW", proc.stdout)

    def test_owned_non_codex_worker_still_passes_all_run_modes(self) -> None:
        for session_mode in ("NEW", "RESUME"):
            for flow in ("DIRECT", "STANDARD", "RECOVERY", "CHANGES_REQUESTED"):
                with self.subTest(session_mode=session_mode, flow=flow):
                    env = self.base_env()
                    env["HERMES_KANBAN_SESSION_MODE"] = session_mode
                    env["HERMES_KANBAN_FLOW"] = flow
                    result = self.run_helper(env, provider="anthropic")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("WORKER_CONTEXT_STATUS=valid", result.stdout)
                    self.assertIn(f"KANBAN_SESSION_MODE={session_mode}", result.stdout)

    def test_codex_declared_provider_cannot_use_shell_gate_even_with_ownership(self) -> None:
        proc = self.run_helper(self.base_env(), provider="openai-codex")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("WORKER_CONTEXT_BLOCKER=WRONG_VERIFICATION_PATH", proc.stderr)
        self.assertIn("INITIAL kanban_show", proc.stderr)
        self.assertNotIn("WORKER_CONTEXT_STATUS=valid", proc.stdout)

    def test_realistic_codex_scrubbed_shell_is_not_misreported_as_lost_worker(self) -> None:
        for mode in ("NEW", "RESUME"):
            with self.subTest(mode=mode):
                env = self.base_env()
                env["HERMES_KANBAN_SESSION_MODE"] = mode
                for key in (
                    "HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID",
                    "HERMES_KANBAN_CLAIM_LOCK",
                ):
                    env.pop(key, None)
                # Mirrors upstream scrub_kanban_env: worker identity is stripped
                # and the delegated-child fence survives native subprocesses.
                env["HERMES_DELEGATED_CHILD_CONTEXT"] = "/opt/data/kanban"
                prior = dict(env)
                proc = self.run_helper(env)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("WORKER_CONTEXT_BLOCKER=WRONG_VERIFICATION_PATH", proc.stderr)
                self.assertNotIn("WORKER_CONTEXT_STATUS=valid", proc.stdout)
                self.assertEqual(env, prior, "the gate must never re-inject ownership variables")

    def test_delegated_shell_cannot_gain_ownership_through_provider_switch(self) -> None:
        env = self.base_env()
        env["HERMES_DELEGATED_CHILD_CONTEXT"] = "/opt/data/kanban"
        env.pop("HERMES_KANBAN_TASK")
        proc = self.run_helper(env, provider="anthropic")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("WRONG_VERIFICATION_PATH", proc.stderr)

    def test_rejects_manual_resume_without_task_context(self) -> None:
        env = self.base_env()
        env.pop("HERMES_KANBAN_TASK")
        proc = self.run_helper(env)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("HERMES_KANBAN_TASK missing", proc.stderr)
        self.assertIn("do not inject Kanban environment variables manually", proc.stderr)

    def test_rejects_workspace_mismatch(self) -> None:
        env = self.base_env()
        env["HERMES_KANBAN_WORKSPACE"] = str(Path(self.tmp.name) / "other")
        proc = self.run_helper(env)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("HERMES_KANBAN_WORKSPACE mismatch", proc.stderr)

    def test_rejects_delegated_child_context(self) -> None:
        env = self.base_env()
        env["HERMES_DELEGATED_CHILD_CONTEXT"] = "1"
        proc = self.run_helper(env)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("HERMES_DELEGATED_CHILD_CONTEXT must be unset", proc.stderr)

    def test_rejects_context_version_mismatch(self) -> None:
        env = self.base_env()
        env["HERMES_KANBAN_CONTEXT_VERSION"] = "0"
        proc = self.run_helper(env)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("HERMES_KANBAN_CONTEXT_VERSION mismatch", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
