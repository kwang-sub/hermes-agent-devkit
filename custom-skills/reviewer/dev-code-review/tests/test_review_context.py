#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "review_context.py"

def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True).stdout.strip()

class ReviewContextTests(unittest.TestCase):
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
        git(self.repo, "branch", "dispatch-base", self.base)
        git(self.repo, "switch", "-c", "review")
        (self.repo / "change.txt").write_text("change\n")
        git(self.repo, "add", "change.txt")
        git(self.repo, "commit", "-m", "change")

    def tearDown(self): self.tmp.cleanup()

    def run_helper(self, sha: str, branch: str = "dispatch-base"):
        return subprocess.run([sys.executable, str(SCRIPT), "--base-branch", branch, "--base-sha", sha, "--expected-branch", "review", "--workspace", str(self.repo), "--expected-workspace", str(self.repo)], text=True, capture_output=True)

    def test_uses_dispatch_sha_without_drift(self):
        proc = self.run_helper(self.base)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("BASE_BRANCH_DRIFTED=false", proc.stdout)
        self.assertIn("TRACKED_CHANGED_COUNT=1", proc.stdout)

    def test_reports_branch_drift_but_keeps_dispatch_sha_diff(self):
        git(self.repo, "branch", "-f", "dispatch-base", "HEAD")
        proc = self.run_helper(self.base)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("BASE_BRANCH_DRIFTED=true", proc.stdout)
        self.assertIn(f"BASE_SHA={self.base}", proc.stdout)
        self.assertIn("TRACKED_CHANGED_COUNT=1", proc.stdout)
        self.assertIn("TRACKED_1=change.txt", proc.stdout)

    def test_rejects_malformed_and_unresolvable_sha(self):
        malformed = self.run_helper("bad")
        self.assertNotEqual(malformed.returncode, 0)
        self.assertIn("full 40-character", malformed.stderr)
        missing = self.run_helper("0" * 40)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("does not resolve", missing.stderr)

    def test_rejects_non_ancestor_sha(self):
        git(self.repo, "switch", "--orphan", "unrelated")
        (self.repo / "unrelated.txt").write_text("unrelated\n")
        git(self.repo, "add", "unrelated.txt")
        git(self.repo, "commit", "-m", "unrelated")
        unrelated = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "switch", "review")
        proc = self.run_helper(unrelated)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not an ancestor", proc.stderr)

if __name__ == "__main__": unittest.main(verbosity=2)
