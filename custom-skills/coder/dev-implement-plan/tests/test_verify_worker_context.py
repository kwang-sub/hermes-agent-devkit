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

    def run_helper(self, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--expected-workspace",
                str(self.workspace),
                "--expected-profile",
                "coder",
            ],
            text=True,
            capture_output=True,
            env=env,
        )

    def test_accepts_dispatcher_worker_context(self) -> None:
        proc = self.run_helper(self.base_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("WORKER_CONTEXT_STATUS=valid", proc.stdout)
        self.assertIn("KANBAN_TASK_ID=t_demo", proc.stdout)
        self.assertIn("KANBAN_BOARD=demo", proc.stdout)
        self.assertIn("KANBAN_PROFILE=coder", proc.stdout)
        self.assertIn("KANBAN_SESSION_MODE=NEW", proc.stdout)

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
