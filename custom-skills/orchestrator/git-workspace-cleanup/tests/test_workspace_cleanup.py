#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
LIST = SCRIPTS / "list_worktrees.py"
PREPARE = SCRIPTS / "prepare_cleanup.py"
CLEANUP = SCRIPTS / "cleanup_workspace.py"


def run(args: list[str], *, cwd: Path, env: dict[str, str] | None = None, check: bool = True):
    completed = subprocess.run(args, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if check and completed.returncode != 0:
        raise AssertionError(f"command failed ({completed.returncode}): {' '.join(args)}\n{completed.stdout}\n{completed.stderr}")
    return completed


def git(cwd: Path, *args: str, check: bool = True):
    return run(["git", *args], cwd=cwd, check=check)


def values(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


class Fixture:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="git-workspace-cleanup-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.remote = self.root / "remote.git"
        self.worktree = self.root / "feature-wt"
        self.branch = "feature/test-cleanup"
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
        git(self.worktree, "commit", "-m", "feat: feature")
        git(self.worktree, "push", "-u", "origin", self.branch)
        self.head = git(self.worktree, "rev-parse", "HEAD").stdout.strip()

    def close(self):
        self.temp.cleanup()

    def merge(self):
        git(self.repo, "merge", "--no-ff", self.branch, "-m", "merge feature")
        git(self.repo, "push", "origin", "main")

    def switch_worktree_to_base_without_merge(self):
        git(self.repo, "switch", "-c", "holding/main-worktree")
        git(self.worktree, "switch", "main")

    def fake_github(self, mode: str) -> dict[str, str]:
        raw = "https://github.com/example/demo.git"
        git(self.repo, "remote", "set-url", "origin", raw)
        git(self.repo, "config", f"url.{self.remote.as_uri()}.insteadOf", raw)
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        gh = fake_bin / "gh"
        gh.write_text(
            """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[:2] == ['auth', 'status']:
    raise SystemExit(0)
if args and args[0] == 'api':
    path = next((a for a in args if a.startswith('repos/')), '')
    if path.endswith('/pulls'):
        print(json.dumps([{'number': 7}]))
        raise SystemExit(0)
    if path.endswith('/pulls/7'):
        merged = os.environ['FAKE_GH_MODE'] == 'merged'
        print(json.dumps({
            'number': 7,
            'html_url': 'https://github.com/example/demo/pull/7',
            'state': 'closed' if merged else 'open',
            'merged_at': '2026-09-15T00:00:00Z' if merged else None,
            'base': {'ref': 'main'},
            'head': {'ref': os.environ['FAKE_GH_BRANCH'], 'sha': os.environ['FAKE_GH_HEAD']},
        }))
        raise SystemExit(0)
raise SystemExit(2)
""", encoding="utf-8")
        gh.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
        env["FAKE_GH_MODE"] = mode
        env["FAKE_GH_BRANCH"] = self.branch
        env["FAKE_GH_HEAD"] = self.head
        env["GH_CONFIG_DIR"] = str(self.root / "gh-config")
        return env


class WorkspaceCleanupTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.close()

    def prepare(self, *, env=None, workspace=None):
        return run([
            "python3", str(PREPARE), "--workspace", str(workspace or self.f.worktree),
            "--remote", "origin", "--base-branch", "main",
        ], cwd=self.f.repo, env=env, check=False)

    def test_lists_linked_worktree_with_branch_and_remote(self):
        result = run(["python3", str(LIST), "--repo", str(self.f.repo), "--remote", "origin"], cwd=self.f.repo, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = values(result.stdout)
        self.assertEqual(data["LINKED_WORKTREES"], "1")
        self.assertEqual(data["WORKTREE_1_BRANCH"], self.f.branch)
        self.assertEqual(data["WORKTREE_1_STATUS"], "CLEAN")
        self.assertEqual(data["WORKTREE_1_REMOTE_EXISTS"], "true")

    def test_lists_eol_only_worktree_separately_from_dirty(self):
        (self.f.worktree / "feature.txt").write_bytes(b"feature\r\n")
        result = run(
            ["python3", str(LIST), "--repo", str(self.f.repo), "--remote", "origin"],
            cwd=self.f.repo,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = values(result.stdout)
        self.assertEqual(data["WORKTREE_1_STATUS"], "EOL_ONLY")

    def test_eol_only_worktree_is_ready_for_cleanup_with_scoped_force_evidence(self):
        self.f.merge()
        (self.f.worktree / "feature.txt").write_bytes(b"feature\r\n")
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = values(result.stdout)
        self.assertEqual(data["WORKTREE_SEMANTIC_DIRTY"], "false")
        self.assertEqual(data["WORKTREE_EOL_NOISE_ONLY"], "true")
        self.assertEqual(data["EOL_ONLY_COUNT"], "1")
        self.assertEqual(data["EOL_ONLY_FORCE_REMOVE_ALLOWED"], "true")
        self.assertEqual(data["EOL_ONLY_FILE"], "feature.txt")

    def test_eol_only_worktree_cleanup_removes_without_reset_restore_or_clean(self):
        self.f.merge()
        (self.f.worktree / "feature.txt").write_bytes(b"feature\r\n")
        preview = self.prepare()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        fingerprint = values(preview.stdout)["CLEANUP_FINGERPRINT"]

        result = run([
            "python3", str(CLEANUP), "--workspace", str(self.f.worktree), "--remote", "origin",
            "--base-branch", "main", "--fingerprint", fingerprint,
        ], cwd=self.f.repo, check=False)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.f.worktree.exists())
        self.assertEqual(values(result.stdout)["WORKTREE_REMOVED"], "true")

    def test_semantic_tracked_change_is_still_blocked(self):
        (self.f.worktree / "feature.txt").write_text("semantic change\n", encoding="utf-8")
        result = self.prepare()
        self.assertEqual(result.returncode, 2)
        self.assertIn("semantic modified/staged/untracked files", result.stderr)

    def test_base_branch_linked_worktree_is_ready_for_worktree_only_cleanup(self):
        self.f.switch_worktree_to_base_without_merge()
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = values(result.stdout)
        self.assertEqual(data["CLEANUP_SCOPE"], "worktree-only")
        self.assertEqual(data["TRACKED_BRANCH_CLEANUP_ALLOWED"], "false")
        self.assertEqual(data["BRANCH"], "main")
        self.assertEqual(data["MERGE_EVIDENCE"], "base-branch-worktree")

    def test_ready_when_branch_is_ancestor_of_base(self):
        self.f.merge()
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = values(result.stdout)
        self.assertEqual(data["CLEANUP_SCOPE"], "worktree-and-branch")
        self.assertEqual(data["MERGE_EVIDENCE"], "git-ancestor")

    def test_primary_worktree_is_blocked(self):
        result = self.prepare(workspace=self.f.repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn("primary worktree", result.stderr)

    def test_dirty_worktree_is_blocked(self):
        (self.f.worktree / "untracked.txt").write_text("keep\n", encoding="utf-8")
        result = self.prepare()
        self.assertEqual(result.returncode, 2)
        self.assertIn("modified or untracked files", result.stderr)

    def test_open_pr_is_blocked(self):
        result = self.prepare(env=self.f.fake_github("open"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("open pull request", result.stderr)

    def test_merged_pr_allows_squash_style_cleanup_evidence(self):
        result = self.prepare(env=self.f.fake_github("merged"))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = values(result.stdout)
        self.assertEqual(data["MERGE_EVIDENCE"], "github-pr-merged")
        self.assertEqual(data["PR_NUMBER"], "7")

    def test_cleanup_can_delete_matching_remote_branch_after_approval(self):
        self.f.merge()
        preview = self.prepare()
        fingerprint = values(preview.stdout)["CLEANUP_FINGERPRINT"]
        result = run([
            "python3", str(CLEANUP), "--workspace", str(self.f.worktree), "--remote", "origin",
            "--base-branch", "main", "--fingerprint", fingerprint, "--delete-remote",
        ], cwd=self.f.repo, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values(result.stdout)["REMOTE_BRANCH_REMOVED"], "true")
        self.assertEqual(git(self.f.repo, "ls-remote", "--heads", "origin", f"refs/heads/{self.f.branch}").stdout.strip(), "")

    def test_fingerprint_change_blocks_cleanup_before_mutation(self):
        self.f.merge()
        preview = self.prepare()
        fingerprint = values(preview.stdout)["CLEANUP_FINGERPRINT"]
        git(self.f.worktree, "push", "origin", "--delete", self.f.branch)
        result = run([
            "python3", str(CLEANUP), "--workspace", str(self.f.worktree), "--remote", "origin",
            "--base-branch", "main", "--fingerprint", fingerprint,
        ], cwd=self.f.repo, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("fingerprint changed", result.stderr)
        self.assertTrue(self.f.worktree.exists())

    def test_mutation_script_uses_exact_ref_delete_and_no_force_cleanup(self):
        text = CLEANUP.read_text(encoding="utf-8")
        self.assertIn('"update-ref", "-d"', text)
        self.assertIn('"worktree", "remove"', text)
        self.assertIn('allow_eol_only_force', text)
        self.assertIn('command.append("--force")', text)
        for forbidden in ("--force-with-lease", '"branch", "-D"', "git reset", "git restore", "git clean", "git stash"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
