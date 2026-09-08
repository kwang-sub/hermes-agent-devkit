#!/usr/bin/env python3
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_workspace.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True).stdout.strip()


class VerifyWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], capture_output=True, check=True)
        git(self.repo, "config", "user.name", "Hermes Test")
        git(self.repo, "config", "user.email", "hermes-test@example.invalid")
        (self.repo / "fixture.txt").write_text("base\n")
        git(self.repo, "add", "fixture.txt")
        git(self.repo, "commit", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def tearDown(self):
        self.tmp.cleanup()

    def kanban_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update({
            "HERMES_KANBAN_TASK": "t_demo",
            "HERMES_KANBAN_BOARD": "demo",
            "HERMES_KANBAN_DB": str(Path(self.tmp.name) / "kanban.db"),
            "HERMES_KANBAN_WORKSPACE": str(self.repo.resolve()),
            "HERMES_PROFILE": "coder",
            "HERMES_SESSION_SOURCE": "kanban",
            "HERMES_KANBAN_CONTEXT_VERSION": "1",
            "HERMES_KANBAN_SESSION_MODE": "NEW",
        })
        return env

    def run_helper(self, sha: str, *, env: dict[str, str] | None = None):
        return subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--task-key", "TEST-1",
                "--expected-branch", "main",
                "--base-sha", sha,
                "--workspace", str(self.repo),
                "--expected-workspace", str(self.repo),
            ],
            text=True,
            capture_output=True,
            env=env or self.kanban_env(),
        )

    def test_accepts_resolved_ancestor_base_sha(self):
        proc = self.run_helper(self.base)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"BASE_SHA={self.base}", proc.stdout)
        self.assertIn("KANBAN_CONTEXT=valid", proc.stdout)
        self.assertIn("KANBAN_TASK_ID=t_demo", proc.stdout)
        self.assertIn("KANBAN_BOARD=demo", proc.stdout)
        self.assertIn("KANBAN_SESSION_MODE=NEW", proc.stdout)
        self.assertIn("STATUS=valid", proc.stdout)
        for phase in (
            "PATH_RESOLVE",
            "KANBAN_CONTEXT",
            "SAFE_DIRECTORY_READ",
            "REPO_ROOT",
            "BRANCH",
            "WORKTREE_CHECK",
            "BASE_SHA_RESOLVE",
            "ANCESTOR_CHECK",
        ):
            self.assertRegex(proc.stdout, rf"WORKSPACE_VERIFY_PHASE_{phase}_SECONDS=\d+\.\d+")
        self.assertRegex(proc.stdout, r"WORKSPACE_VERIFY_TOTAL_SECONDS=\d+\.\d+")

    def test_allows_new_session_after_prior_session_loss(self):
        env = self.kanban_env()
        env["HERMES_KANBAN_SESSION_MODE"] = "NEW"
        env.pop("HERMES_KANBAN_AFFINITY_SESSION_ID", None)
        proc = self.run_helper(self.base, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("KANBAN_SESSION_MODE=NEW", proc.stdout)
        self.assertIn("KANBAN_AFFINITY_SESSION_ID=-", proc.stdout)

    def test_accepts_resume_session_when_dispatcher_rehydrates_context(self):
        env = self.kanban_env()
        env["HERMES_KANBAN_SESSION_MODE"] = "RESUME"
        env["HERMES_KANBAN_AFFINITY_SESSION_ID"] = "session-1"
        proc = self.run_helper(self.base, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("KANBAN_SESSION_MODE=RESUME", proc.stdout)
        self.assertIn("KANBAN_AFFINITY_SESSION_ID=session-1", proc.stdout)

    def test_rejects_manual_resume_without_kanban_context(self):
        env = os.environ.copy()
        for key in (
            "HERMES_KANBAN_TASK",
            "HERMES_KANBAN_BOARD",
            "HERMES_KANBAN_DB",
            "HERMES_KANBAN_WORKSPACE",
            "HERMES_PROFILE",
            "HERMES_SESSION_SOURCE",
            "HERMES_KANBAN_CONTEXT_VERSION",
            "HERMES_KANBAN_SESSION_MODE",
            "HERMES_KANBAN_AFFINITY_SESSION_ID",
        ):
            env.pop(key, None)
        proc = self.run_helper(self.base, env=env)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Kanban worker context is missing or mismatched", proc.stderr)
        self.assertIn("HERMES_KANBAN_TASK missing", proc.stderr)
        self.assertIn("manual `hermes --resume`", proc.stderr)

    def test_rejects_workspace_context_mismatch(self):
        env = self.kanban_env()
        env["HERMES_KANBAN_WORKSPACE"] = str(Path(self.tmp.name) / "other")
        proc = self.run_helper(self.base, env=env)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("HERMES_KANBAN_WORKSPACE mismatch", proc.stderr)

    def test_rejects_malformed_and_unresolvable_sha(self):
        malformed = self.run_helper("not-a-sha")
        self.assertNotEqual(malformed.returncode, 0)
        self.assertIn("full 40-character", malformed.stderr)
        missing = self.run_helper("0" * 40)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("does not resolve", missing.stderr)

    def test_rejects_non_ancestor_base_sha(self):
        git(self.repo, "switch", "-c", "side", self.base)
        (self.repo / "side.txt").write_text("side\n")
        git(self.repo, "add", "side.txt")
        git(self.repo, "commit", "-m", "side")
        side = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "switch", "main")
        (self.repo / "main.txt").write_text("main\n")
        git(self.repo, "add", "main.txt")
        git(self.repo, "commit", "-m", "main")
        proc = self.run_helper(side)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not an ancestor", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
