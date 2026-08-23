#!/usr/bin/env python3
from pathlib import Path
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

    def tearDown(self): self.tmp.cleanup()

    def run_helper(self, sha: str):
        return subprocess.run([sys.executable, str(SCRIPT), "--task-key", "TEST-1", "--expected-branch", "main", "--base-sha", sha, "--workspace", str(self.repo), "--expected-workspace", str(self.repo)], text=True, capture_output=True)

    def test_accepts_resolved_ancestor_base_sha(self):
        proc = self.run_helper(self.base)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"BASE_SHA={self.base}", proc.stdout)
        self.assertIn("STATUS=valid", proc.stdout)

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

if __name__ == "__main__": unittest.main(verbosity=2)
