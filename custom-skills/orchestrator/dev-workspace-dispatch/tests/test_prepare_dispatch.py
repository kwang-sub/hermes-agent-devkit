#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_dispatch.py"


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def write_metadata(repo: Path) -> None:
    metadata = repo / ".hermes" / "project.yaml"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        f"""# managed-by: dev-project-bootstrap
version: 2

project:
  id: test-project
  name: test-project
  repository: {repo}

kanban:
  board: test-project

git:
  default_base_branch: main
  worktree_root: {repo.parent / '.worktrees'}

profiles:
  orchestrator: orchestrator
  coder: coder
  reviewer: reviewer
""",
        encoding="utf-8",
    )


class PrepareDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name) / "repo"
        self.repo.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(self.repo)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        git(self.repo, "config", "user.name", "Hermes Test")
        git(self.repo, "config", "user.email", "hermes-test@example.invalid")
        git(self.repo, "config", "core.autocrlf", "false")
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-m", "fixture")
        write_metadata(self.repo)
        git(self.repo, "add", ".hermes/project.yaml")
        git(self.repo, "commit", "-m", "metadata")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_helper(self, task_key: str, mode: str, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--task-key",
                task_key,
                "--workspace",
                str(self.repo),
                "--branch-mode",
                mode,
                *extra,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_current_branch_mode(self) -> None:
        proc = self.run_helper("CALC-001", "current")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("BRANCH_MODE=current", proc.stdout)
        self.assertIn("BRANCH=main", proc.stdout)
        self.assertIn("CREATED_BRANCH=false", proc.stdout)
        self.assertIn("WORKSPACE_EFFECTIVE_DIRTY=false", proc.stdout)
        self.assertIn("STATUS=prepared", proc.stdout)
        self.assertEqual(git(self.repo, "branch", "--show-current").stdout.strip(), "main")

    def test_create_branch_mode(self) -> None:
        proc = self.run_helper("CALC-002", "create")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("BRANCH_MODE=create", proc.stdout)
        self.assertIn("BRANCH=feature/CALC-002", proc.stdout)
        self.assertIn("CREATED_BRANCH=true", proc.stdout)
        self.assertEqual(
            git(self.repo, "branch", "--show-current").stdout.strip(),
            "feature/CALC-002",
        )

    def test_effective_dirty_workspace_requires_confirmation(self) -> None:
        (self.repo / "README.md").write_text("dirty\n", encoding="utf-8")
        refused = self.run_helper("CALC-003", "current")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("--confirmed-dirty", refused.stderr)
        self.assertIn("EFFECTIVE_CHANGED_COUNT=1", refused.stderr)
        self.assertIn("EFFECTIVE_CHANGED_1=README.md", refused.stderr)

        confirmed = self.run_helper("CALC-003", "current", "--confirmed-dirty")
        self.assertEqual(confirmed.returncode, 0, confirmed.stderr)
        self.assertIn("WORKSPACE_DIRTY=true", confirmed.stdout)
        self.assertIn("WORKSPACE_EFFECTIVE_DIRTY=true", confirmed.stdout)
        self.assertIn("EFFECTIVE_CHANGED_COUNT=1", confirmed.stdout)

    def test_hermes_managed_files_do_not_require_dirty_confirmation(self) -> None:
        (self.repo / ".hermes" / "toolchain.env").write_text("JAVA_HOME=/tmp/jdk\n", encoding="utf-8")
        (self.repo / ".hermes" / "LOCAL-001-body.txt").write_text("body\n", encoding="utf-8")

        proc = self.run_helper("CALC-004", "current")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("WORKSPACE_DIRTY=true", proc.stdout)
        self.assertIn("WORKSPACE_EFFECTIVE_DIRTY=false", proc.stdout)
        self.assertIn("EFFECTIVE_CHANGED_COUNT=0", proc.stdout)
        self.assertIn("HERMES_MANAGED_COUNT=2", proc.stdout)

    def test_crlf_only_change_is_classified_separately(self) -> None:
        (self.repo / "README.md").write_bytes(b"fixture\r\n")

        proc = self.run_helper("CALC-005", "current")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("WORKSPACE_DIRTY=true", proc.stdout)
        self.assertIn("WORKSPACE_EFFECTIVE_DIRTY=false", proc.stdout)
        self.assertIn("EFFECTIVE_CHANGED_COUNT=0", proc.stdout)
        self.assertIn("EOL_ONLY_COUNT=1", proc.stdout)
        self.assertIn("EOL_ONLY_1=README.md", proc.stdout)

    def test_effective_and_managed_changes_are_reported_separately(self) -> None:
        (self.repo / "README.md").write_text("dirty\n", encoding="utf-8")
        (self.repo / "CLAUDE.md").write_text("instructions\n", encoding="utf-8")
        (self.repo / ".hermes" / "toolchain.env").write_text("JAVA_HOME=/tmp/jdk\n", encoding="utf-8")

        proc = self.run_helper("CALC-006", "current", "--confirmed-dirty")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("EFFECTIVE_CHANGED_COUNT=2", proc.stdout)
        self.assertIn("HERMES_MANAGED_COUNT=1", proc.stdout)
        self.assertIn("EFFECTIVE_CHANGED_1=CLAUDE.md", proc.stdout)
        self.assertIn("EFFECTIVE_CHANGED_2=README.md", proc.stdout)
        self.assertIn("HERMES_MANAGED_1=.hermes/toolchain.env", proc.stdout)

    def test_unsafe_task_key_is_rejected(self) -> None:
        proc = self.run_helper("unsafe/key", "current")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("task key", proc.stderr)
        self.assertEqual(git(self.repo, "branch", "--show-current").stdout.strip(), "main")


if __name__ == "__main__":
    unittest.main(verbosity=2)
