#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
PREPARE = SKILL_ROOT / "scripts" / "prepare_cleanup.py"
CLEANUP = SKILL_ROOT / "scripts" / "cleanup_workspace.py"


def run(args: list[str], *, cwd: Path, check: bool = True):
    result = subprocess.run(args, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return result


def git(cwd: Path, *args: str, check: bool = True):
    return run(["git", *args], cwd=cwd, check=check)


def kv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


class TrackedBranchCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="git-workspace-cleanup-tracked-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.remote = self.root / "remote.git"
        self.worktree = self.root / "ui-dashboard-investment"
        self.branch = "feature/ui-dashboard-investment"

        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Test User")
        git(self.repo, "config", "user.email", "test@example.com")
        (self.repo / "README.md").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-m", "chore: base")
        git(self.root, "init", "--bare", str(self.remote))
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-u", "origin", "main")
        git(self.repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

        git(self.repo, "branch", self.branch)
        git(self.repo, "worktree", "add", str(self.worktree), self.branch)
        (self.worktree / "feature.txt").write_text("feature\n", encoding="utf-8")
        git(self.worktree, "add", "feature.txt")
        git(self.worktree, "commit", "-m", "feat: dashboard")
        git(self.worktree, "push", "-u", "origin", self.branch)
        self.feature_head = git(self.worktree, "rev-parse", "HEAD").stdout.strip()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def merge_and_switch_worktree_to_base(self) -> None:
        git(self.repo, "merge", "--no-ff", self.branch, "-m", "merge dashboard")
        git(self.repo, "push", "origin", "main")
        git(self.repo, "switch", "-c", "holding/main-worktree")
        git(self.worktree, "switch", "main")

    def prepare(self):
        return run(
            [
                "python3", str(PREPARE), "--workspace", str(self.worktree),
                "--remote", "origin", "--base-branch", "main",
            ],
            cwd=self.repo,
            check=False,
        )

    def cleanup(self, fingerprint: str, *extra: str):
        return run(
            [
                "python3", str(CLEANUP), "--workspace", str(self.worktree),
                "--remote", "origin", "--base-branch", "main",
                "--fingerprint", fingerprint, *extra,
            ],
            cwd=self.repo,
            check=False,
        )

    def test_preflight_tracks_previous_merged_branch_from_head_reflog(self) -> None:
        self.merge_and_switch_worktree_to_base()
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        values = kv(result.stdout)
        self.assertEqual(values["CLEANUP_SCOPE"], "worktree-and-tracked-branch")
        self.assertEqual(values["TRACKED_BRANCH_CLEANUP_ALLOWED"], "true")
        self.assertEqual(values["TRACKED_PREVIOUS_BRANCH"], self.branch)
        self.assertEqual(values["TRACKED_PREVIOUS_HEAD_SHA"], self.feature_head)
        self.assertEqual(values["TRACKED_PREVIOUS_MERGE_EVIDENCE"], "git-ancestor")
        self.assertIn(f"checkout: moving from {self.branch} to main", values["TRACKED_REFLOG_MESSAGE"])
        self.assertEqual(values["TRACKED_PREVIOUS_REMOTE_EXISTS"], "true")
        self.assertEqual(values["TRACKED_PREVIOUS_REMOTE_DELETE_AVAILABLE"], "true")

    def test_worktree_only_choice_preserves_tracked_branch(self) -> None:
        self.merge_and_switch_worktree_to_base()
        preview = self.prepare()
        fingerprint = kv(preview.stdout)["CLEANUP_FINGERPRINT"]
        result = self.cleanup(fingerprint)
        self.assertEqual(result.returncode, 0, result.stderr)
        values = kv(result.stdout)
        self.assertEqual(values["CLEANUP_SCOPE"], "worktree-only")
        self.assertEqual(values["TRACKED_LOCAL_BRANCH_REMOVED"], "skipped")
        self.assertEqual(git(self.repo, "show-ref", "--verify", f"refs/heads/{self.branch}", check=False).returncode, 0)

    def test_approved_tracked_local_branch_is_deleted_by_exact_sha(self) -> None:
        self.merge_and_switch_worktree_to_base()
        preview = self.prepare()
        fingerprint = kv(preview.stdout)["CLEANUP_FINGERPRINT"]
        result = self.cleanup(fingerprint, "--delete-tracked-branch")
        self.assertEqual(result.returncode, 0, result.stderr)
        values = kv(result.stdout)
        self.assertEqual(values["TRACKED_PREVIOUS_BRANCH"], self.branch)
        self.assertEqual(values["TRACKED_LOCAL_BRANCH_REMOVED"], "true")
        self.assertNotEqual(git(self.repo, "show-ref", "--verify", f"refs/heads/{self.branch}", check=False).returncode, 0)
        self.assertIn(self.branch, git(self.repo, "ls-remote", "--heads", "origin", f"refs/heads/{self.branch}").stdout)
        self.assertEqual(git(self.repo, "show-ref", "--verify", "refs/heads/main", check=False).returncode, 0)

    def test_approved_tracked_remote_branch_is_deleted_but_base_is_preserved(self) -> None:
        self.merge_and_switch_worktree_to_base()
        preview = self.prepare()
        fingerprint = kv(preview.stdout)["CLEANUP_FINGERPRINT"]
        result = self.cleanup(fingerprint, "--delete-tracked-branch", "--delete-remote")
        self.assertEqual(result.returncode, 0, result.stderr)
        values = kv(result.stdout)
        self.assertEqual(values["TRACKED_LOCAL_BRANCH_REMOVED"], "true")
        self.assertEqual(values["TRACKED_REMOTE_BRANCH_REMOVED"], "true")
        self.assertEqual(git(self.repo, "ls-remote", "--heads", "origin", f"refs/heads/{self.branch}").stdout.strip(), "")
        self.assertIn("refs/heads/main", git(self.repo, "ls-remote", "--heads", "origin", "refs/heads/main").stdout)

    def test_unmerged_previous_branch_is_not_offered_for_deletion(self) -> None:
        git(self.repo, "switch", "-c", "holding/main-worktree")
        git(self.worktree, "switch", "main")
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        values = kv(result.stdout)
        self.assertEqual(values["CLEANUP_SCOPE"], "worktree-only")
        self.assertEqual(values["TRACKED_BRANCH_CLEANUP_ALLOWED"], "false")
        self.assertEqual(values["TRACKED_PREVIOUS_BRANCH"], self.branch)
        self.assertIn("merge", values["TRACKED_PREVIOUS_REASON"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
