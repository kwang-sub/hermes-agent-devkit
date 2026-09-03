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

    def assert_timing_output(self, text: str) -> None:
        self.assertIn("GIT_TRACKED_SCAN_SECONDS=", text)
        self.assertIn("GIT_EFFECTIVE_SCAN_SECONDS=", text)
        self.assertIn("GIT_UNTRACKED_SCAN_SECONDS=", text)
        self.assertIn("CLASSIFICATION_SECONDS=", text)
        self.assertIn("WORKSPACE_CLASSIFICATION_TOTAL_SECONDS=", text)

    def test_current_branch_mode(self) -> None:
        proc = self.run_helper("CALC-001", "current")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("BOARD=test-project", proc.stdout)
        self.assertIn("BRANCH_MODE=current", proc.stdout)
        self.assertIn("BRANCH=main", proc.stdout)
        self.assertIn("CREATED_BRANCH=false", proc.stdout)
        self.assertIn("WORKSPACE_CHANGE_SCAN_MODE=full", proc.stdout)
        self.assertIn("WORKSPACE_EFFECTIVE_DIRTY=false", proc.stdout)
        self.assert_timing_output(proc.stdout)
        self.assertIn("STATUS=prepared", proc.stdout)
        self.assertEqual(git(self.repo, "branch", "--show-current").stdout.strip(), "main")

    def test_board_comes_from_managed_metadata(self) -> None:
        proc = self.run_helper("CALC-BOARD", "current")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("BOARD=test-project", proc.stdout)

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
        self.assert_timing_output(refused.stderr)

    def test_confirmed_dirty_uses_preservation_fast_path(self) -> None:
        (self.repo / "README.md").write_text("dirty\n", encoding="utf-8")
        (self.repo / "new.bin").write_bytes(b"x" * 1024)

        confirmed = self.run_helper("CALC-003", "current", "--confirmed-dirty")
        self.assertEqual(confirmed.returncode, 0, confirmed.stderr)
        self.assertIn("WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation", confirmed.stdout)
        self.assertIn("EXISTING_CHANGES_PRESERVATION_APPROVED=true", confirmed.stdout)
        self.assertIn("WORKSPACE_DIRTY=unknown", confirmed.stdout)
        self.assertIn("WORKSPACE_EFFECTIVE_DIRTY=unknown", confirmed.stdout)
        self.assertIn("EFFECTIVE_CHANGED_COUNT=-1", confirmed.stdout)
        self.assertIn("EOL_ONLY_COUNT=-1", confirmed.stdout)
        self.assertIn("HERMES_MANAGED_COUNT=-1", confirmed.stdout)
        self.assertIn("WORKSPACE_CLASSIFICATION_TOTAL_SECONDS=-1.000", confirmed.stdout)
        self.assertNotIn("EFFECTIVE_CHANGED_1=", confirmed.stdout)

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

    def test_effective_and_managed_changes_can_be_diagnosed_without_fast_path(self) -> None:
        (self.repo / "README.md").write_text("dirty\n", encoding="utf-8")
        (self.repo / "CLAUDE.md").write_text("instructions\n", encoding="utf-8")
        (self.repo / ".hermes" / "toolchain.env").write_text("JAVA_HOME=/tmp/jdk\n", encoding="utf-8")

        proc = self.run_helper("CALC-006", "current")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("EFFECTIVE_CHANGED_COUNT=2", proc.stderr)
        self.assertIn("HERMES_MANAGED_COUNT=1", proc.stderr)
        self.assertIn("EFFECTIVE_CHANGED_1=CLAUDE.md", proc.stderr)
        self.assertIn("EFFECTIVE_CHANGED_2=README.md", proc.stderr)
        self.assertIn("HERMES_MANAGED_1=.hermes/toolchain.env", proc.stderr)

    def test_batch_scan_contract_avoids_per_file_diff_quiet(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('["diff", "--name-only", "-z", "HEAD"]', source)
        self.assertIn('["diff", "--name-only", "-z", "--ignore-cr-at-eol", "HEAD"]', source)
        self.assertIn('["ls-files", "-z", "--others", "--exclude-standard"]', source)
        self.assertNotIn('"diff", "--quiet", "--ignore-cr-at-eol"', source)
        self.assertIn('if args.confirmed_dirty:', source)
        self.assertIn('scan_mode = "skipped-approved-preservation"', source)

    def test_unsafe_task_key_is_rejected(self) -> None:
        proc = self.run_helper("unsafe/key", "current")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("task key", proc.stderr)
        self.assertEqual(git(self.repo, "branch", "--show-current").stdout.strip(), "main")


if __name__ == "__main__":
    unittest.main(verbosity=2)
