#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
PREPARE = SCRIPTS / "prepare_cleanup.py"
CLEANUP = SCRIPTS / "cleanup_worktree.py"


def run(args: list[str], *, cwd: Path, env: dict[str, str] | None = None, check: bool = True):
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if check and completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def git(cwd: Path, *args: str, check: bool = True):
    return run(["git", *args], cwd=cwd, check=check)


def parse_output(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result


class RepoFixture:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.remote = self.root / "remote.git"
        self.worktree = self.root / "feature-wt"
        self.branch = "feature/test-cleanup"
        self._init()

    def close(self) -> None:
        self.temp.cleanup()

    def _init(self) -> None:
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

    def merge_feature(self) -> None:
        git(self.repo, "merge", "--no-ff", self.branch, "-m", "merge feature")
        git(self.repo, "push", "origin", "main")

    def fake_github_remote(self, gh_dir: Path, mode: str) -> dict[str, str]:
        raw_url = "https://github.com/example/demo.git"
        git(self.repo, "remote", "set-url", "origin", raw_url)
        replacement = self.remote.as_uri()
        git(self.repo, "config", f"url.{replacement}.insteadOf", raw_url)

        gh_dir.mkdir(parents=True, exist_ok=True)
        gh = gh_dir / "gh"
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
        mode = os.environ['FAKE_GH_MODE']
        merged = mode == 'merged'
        state = 'closed' if merged else 'open'
        print(json.dumps({
            'number': 7,
            'html_url': 'https://github.com/example/demo/pull/7',
            'state': state,
            'merged_at': '2026-09-15T00:00:00Z' if merged else None,
            'base': {'ref': 'main'},
            'head': {'ref': os.environ['FAKE_GH_BRANCH'], 'sha': os.environ['FAKE_GH_HEAD']},
        }))
        raise SystemExit(0)
print('unsupported fake gh invocation: ' + ' '.join(args), file=sys.stderr)
raise SystemExit(2)
""",
            encoding="utf-8",
        )
        gh.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(gh_dir) + os.pathsep + env.get("PATH", "")
        env["FAKE_GH_MODE"] = mode
        env["FAKE_GH_BRANCH"] = self.branch
        env["FAKE_GH_HEAD"] = self.head
        env["GH_CONFIG_DIR"] = str(self.root / "gh-config")
        return env


class WorktreeCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = RepoFixture()

    def tearDown(self) -> None:
        self.fixture.close()

    def prepare(self, *, env: dict[str, str] | None = None, workspace: Path | None = None):
        target = workspace or self.fixture.worktree
        return run(
            [
                "python3",
                str(PREPARE),
                "--workspace",
                str(target),
                "--remote",
                "origin",
                "--base-branch",
                "main",
            ],
            cwd=self.fixture.repo,
            env=env,
            check=False,
        )

    def test_ready_when_branch_is_ancestor_of_base(self) -> None:
        self.fixture.merge_feature()
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        values = parse_output(result.stdout)
        self.assertEqual(values["STATUS"], "ready")
        self.assertEqual(values["MERGE_EVIDENCE"], "git-ancestor")
        self.assertEqual(values["BRANCH"], self.fixture.branch)
        self.assertEqual(values["REMOTE_BRANCH_EXISTS"], "true")

    def test_main_worktree_is_blocked(self) -> None:
        result = self.prepare(workspace=self.fixture.repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn("primary worktree", result.stderr)

    def test_dirty_worktree_is_blocked(self) -> None:
        (self.fixture.worktree / "untracked.txt").write_text("keep me\n", encoding="utf-8")
        result = self.prepare()
        self.assertEqual(result.returncode, 2)
        self.assertIn("modified or untracked files", result.stderr)

    def test_open_pr_is_blocked(self) -> None:
        env = self.fixture.fake_github_remote(self.fixture.root / "fake-bin", "open")
        result = self.prepare(env=env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("open pull request", result.stderr)

    def test_merged_pr_allows_squash_style_cleanup_evidence(self) -> None:
        env = self.fixture.fake_github_remote(self.fixture.root / "fake-bin", "merged")
        result = self.prepare(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        values = parse_output(result.stdout)
        self.assertEqual(values["MERGE_EVIDENCE"], "github-pr-merged")
        self.assertEqual(values["PR_NUMBER"], "7")
        self.assertEqual(values["PR_URL"], "https://github.com/example/demo/pull/7")

    def test_cleanup_removes_worktree_and_local_branch_but_keeps_remote_by_default(self) -> None:
        self.fixture.merge_feature()
        preview = self.prepare()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        fingerprint = parse_output(preview.stdout)["CLEANUP_FINGERPRINT"]

        cleaned = run(
            [
                "python3",
                str(CLEANUP),
                "--workspace",
                str(self.fixture.worktree),
                "--remote",
                "origin",
                "--base-branch",
                "main",
                "--fingerprint",
                fingerprint,
            ],
            cwd=self.fixture.repo,
            check=False,
        )
        self.assertEqual(cleaned.returncode, 0, cleaned.stderr)
        values = parse_output(cleaned.stdout)
        self.assertEqual(values["STATUS"], "cleaned")
        self.assertEqual(values["WORKTREE_REMOVED"], "true")
        self.assertEqual(values["LOCAL_BRANCH_REMOVED"], "true")
        self.assertEqual(values["REMOTE_BRANCH_REMOVED"], "skipped")
        self.assertFalse(self.fixture.worktree.exists())
        local = git(self.fixture.repo, "show-ref", "--verify", f"refs/heads/{self.fixture.branch}", check=False)
        self.assertNotEqual(local.returncode, 0)
        remote = git(self.fixture.repo, "ls-remote", "--heads", "origin", f"refs/heads/{self.fixture.branch}")
        self.assertIn(self.fixture.branch, remote.stdout)

    def test_cleanup_can_delete_remote_branch_after_approval(self) -> None:
        self.fixture.merge_feature()
        preview = self.prepare()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        fingerprint = parse_output(preview.stdout)["CLEANUP_FINGERPRINT"]

        cleaned = run(
            [
                "python3",
                str(CLEANUP),
                "--workspace",
                str(self.fixture.worktree),
                "--remote",
                "origin",
                "--base-branch",
                "main",
                "--fingerprint",
                fingerprint,
                "--delete-remote",
            ],
            cwd=self.fixture.repo,
            check=False,
        )
        self.assertEqual(cleaned.returncode, 0, cleaned.stderr)
        values = parse_output(cleaned.stdout)
        self.assertEqual(values["REMOTE_BRANCH_REMOVED"], "true")
        remote = git(self.fixture.repo, "ls-remote", "--heads", "origin", f"refs/heads/{self.fixture.branch}")
        self.assertEqual(remote.stdout.strip(), "")

    def test_fingerprint_change_blocks_cleanup_before_mutation(self) -> None:
        self.fixture.merge_feature()
        preview = self.prepare()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        fingerprint = parse_output(preview.stdout)["CLEANUP_FINGERPRINT"]
        git(self.fixture.worktree, "push", "origin", "--delete", self.fixture.branch)

        cleaned = run(
            [
                "python3",
                str(CLEANUP),
                "--workspace",
                str(self.fixture.worktree),
                "--remote",
                "origin",
                "--base-branch",
                "main",
                "--fingerprint",
                fingerprint,
            ],
            cwd=self.fixture.repo,
            check=False,
        )
        self.assertEqual(cleaned.returncode, 2)
        self.assertIn("fingerprint changed", cleaned.stderr)
        self.assertTrue(self.fixture.worktree.exists())
        local = git(self.fixture.repo, "show-ref", "--verify", f"refs/heads/{self.fixture.branch}", check=False)
        self.assertEqual(local.returncode, 0)

    def test_mutation_script_uses_exact_ref_delete_and_no_force_cleanup(self) -> None:
        text = CLEANUP.read_text(encoding="utf-8")
        self.assertIn('"update-ref", "-d"', text)
        self.assertIn('"worktree", "remove"', text)
        for forbidden in ("--force", "force-with-lease", '"branch", "-D"', "git reset", "git stash"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
