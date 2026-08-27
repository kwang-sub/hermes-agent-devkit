#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "change_summary.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True).stdout.strip()


class ChangeSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], capture_output=True, check=True)
        git(self.repo, "config", "user.name", "Hermes Test")
        git(self.repo, "config", "user.email", "hermes-test@example.invalid")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        (self.repo / "unrelated.txt").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_helper(self, *includes: str) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(SCRIPT), "--workspace", str(self.repo)]
        for include in includes:
            cmd.extend(["--include", include])
        return subprocess.run(cmd, text=True, capture_output=True)

    def test_scopes_tracked_and_untracked_changes(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "new.md").write_text("# new\n", encoding="utf-8")
        (self.repo / "unrelated.txt").write_text("unrelated change\n", encoding="utf-8")

        proc = self.run_helper("tracked.txt", "new.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TRACKED_CHANGED_COUNT=1", proc.stdout)
        self.assertIn("TRACKED_1=tracked.txt", proc.stdout)
        self.assertIn("UNTRACKED_COUNT=1", proc.stdout)
        self.assertIn("UNTRACKED_1=new.md", proc.stdout)
        self.assertNotIn("unrelated.txt", proc.stdout)
        self.assertIn("STATUS=valid", proc.stdout)

    def test_untracked_difference_exit_one_is_not_an_error(self) -> None:
        (self.repo / "new.md").write_text("# valid\n", encoding="utf-8")
        proc = self.run_helper("new.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("UNTRACKED_COUNT=1", proc.stdout)
        self.assertIn("WHITESPACE_ERROR_COUNT=0", proc.stdout)
        self.assertIn("STATUS=valid", proc.stdout)

    def test_reports_untracked_whitespace_error(self) -> None:
        (self.repo / "bad.md").write_text("bad trailing space \n", encoding="utf-8")
        proc = self.run_helper("bad.md")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("WHITESPACE_ERROR_COUNT=1", proc.stdout)
        self.assertIn("STATUS=invalid", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
