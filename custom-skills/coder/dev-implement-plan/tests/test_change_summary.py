#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "change_summary.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True).stdout.strip()


def fingerprint(output: str) -> str:
    match = re.search(r"^EFFECTIVE_SCOPE_SHA256=([0-9a-f]{64})$", output, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"fingerprint missing from output:\n{output}")
    return match.group(1)


def handoff_state(repo: Path) -> Path:
    raw = git(repo, "rev-parse", "--git-path", "hermes/review-handoff.json")
    path = Path(raw)
    return path if path.is_absolute() else (repo / path).resolve()


class ChangeSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], capture_output=True, check=True)
        git(self.repo, "config", "user.name", "Hermes Test")
        git(self.repo, "config", "user.email", "hermes-test@example.invalid")
        git(self.repo, "config", "core.autocrlf", "false")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        (self.repo / "unrelated.txt").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_helper(self, *includes: str, compact: bool = False) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(SCRIPT), "--workspace", str(self.repo)]
        if compact:
            cmd.append("--compact")
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
        self.assertIn("UNTRACKED_1=new.md", proc.stdout)
        self.assertNotIn("unrelated.txt", proc.stdout)
        self.assertIn("HANDOFF_GATE=PASS", proc.stdout)
        state = json.loads(handoff_state(self.repo).read_text(encoding="utf-8"))
        self.assertEqual(state["effective_scope_sha256"], fingerprint(proc.stdout))
        self.assertEqual(state["effective_paths"], ["new.md", "tracked.txt"])

    def test_fingerprint_changes_with_effective_content(self) -> None:
        (self.repo / "tracked.txt").write_text("first\n", encoding="utf-8")
        first = self.run_helper("tracked.txt")
        self.assertEqual(first.returncode, 0, first.stderr)
        (self.repo / "tracked.txt").write_text("second\n", encoding="utf-8")
        second = self.run_helper("tracked.txt")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(fingerprint(first.stdout), fingerprint(second.stdout))

    def test_crlf_only_tracked_change_is_reported_as_noise(self) -> None:
        (self.repo / "tracked.txt").write_bytes(b"base\r\n")
        quiet = subprocess.run([
            "git", "-C", str(self.repo), "diff", "--quiet", "--ignore-cr-at-eol", "HEAD", "--", "tracked.txt"
        ], capture_output=True)
        self.assertEqual(quiet.returncode, 0)
        proc = self.run_helper("tracked.txt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TRACKED_CHANGED_COUNT=0", proc.stdout)
        self.assertIn("EOL_ONLY_COUNT=1", proc.stdout)
        self.assertIn("WHITESPACE_ERROR_COUNT=0", proc.stdout)
        self.assertIn("HANDOFF_GATE=PASS", proc.stdout)

    def test_untracked_difference_exit_one_is_not_an_error(self) -> None:
        (self.repo / "new.md").write_text("# valid\n", encoding="utf-8")
        proc = self.run_helper("new.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("UNTRACKED_COUNT=1", proc.stdout)
        self.assertIn("WHITESPACE_ERROR_COUNT=0", proc.stdout)

    def test_invalid_summary_clears_handoff_gate(self) -> None:
        (self.repo / "tracked.txt").write_text("valid change\n", encoding="utf-8")
        valid = self.run_helper("tracked.txt")
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertTrue(handoff_state(self.repo).is_file())
        (self.repo / "bad.md").write_text("bad trailing space \n", encoding="utf-8")
        proc = self.run_helper("bad.md")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("HANDOFF_GATE=FAIL", proc.stdout)
        self.assertIn("STATUS=invalid", proc.stdout)
        self.assertFalse(handoff_state(self.repo).exists())

    def test_compact_output_keeps_failure_exit_code(self) -> None:
        (self.repo / "bad.md").write_text("bad trailing space \n", encoding="utf-8")
        proc = self.run_helper("bad.md", compact=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("HANDOFF_GATE=FAIL", proc.stdout)
        self.assertIn("STATUS=invalid", proc.stdout)
        self.assertNotIn("WHITESPACE_ERROR_1=", proc.stdout)

    def test_rejects_external_include(self) -> None:
        external = Path(self.tmp.name) / "external.md"
        external.write_text("# docs\n", encoding="utf-8")
        proc = self.run_helper(str(external))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("summarize each Git workspace separately", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
