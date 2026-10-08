#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "change_summary.py"
DIFF_CHECK = Path(__file__).resolve().parents[4] / "scripts" / "hermes-diff-check.py"


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

    def run_helper(self, *includes: str, compact: bool = False, allow_full_scan: bool = False, check_only: bool = False, task_id: str | None = None) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(SCRIPT), "--workspace", str(self.repo)]
        if check_only:
            cmd.append("--check-only")
        if task_id:
            cmd.extend(["--task-id", task_id])
        if compact:
            cmd.append("--compact")
        if allow_full_scan:
            cmd.append("--allow-full-scan")
        for include in includes:
            cmd.extend(["--include", include])
        env = os.environ.copy()
        env["HERMES_DIFF_CHECK"] = str(DIFF_CHECK)
        return subprocess.run(cmd, text=True, capture_output=True, env=env)

    def test_scopes_tracked_and_untracked_changes(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "new.md").write_text("# new\n", encoding="utf-8")
        (self.repo / "unrelated.txt").write_text("unrelated change\n", encoding="utf-8")
        proc = self.run_helper("tracked.txt", "new.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SCAN_MODE=scoped", proc.stdout)
        self.assertIn("TRACKED_CHANGED_COUNT=1", proc.stdout)
        self.assertIn("TRACKED_1=tracked.txt", proc.stdout)
        self.assertIn("UNTRACKED_1=new.md", proc.stdout)
        self.assertNotIn("unrelated.txt", proc.stdout)
        self.assertIn("HANDOFF_GATE=PASS", proc.stdout)
        state = json.loads(handoff_state(self.repo).read_text(encoding="utf-8"))
        self.assertEqual(state["effective_scope_sha256"], fingerprint(proc.stdout))
        self.assertEqual(state["effective_paths"], ["new.md", "tracked.txt"])

    def test_check_only_never_modifies_existing_task_handoff(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        original = self.run_helper("tracked.txt", task_id="t_scope")
        self.assertEqual(original.returncode, 0, original.stderr)
        task_handoff = Path(git(
            self.repo, "rev-parse", "--git-path",
            "hermes/task-handoffs/t_scope/current.json",
        ))
        if not task_handoff.is_absolute():
            task_handoff = self.repo / task_handoff
        original_bytes = task_handoff.read_bytes()
        # Changing a source after final verification must not erase the old
        # handoff during cheap preflight; final write replaces it later.
        (self.repo / "tracked.txt").write_text("new changes\n", encoding="utf-8")
        check = self.run_helper("tracked.txt", check_only=True, task_id="t_scope")
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("PREFLIGHT_SCOPE_ONLY=true", check.stdout)
        self.assertEqual(task_handoff.read_bytes(), original_bytes)
        bad_path = self.repo / "bad.md"
        bad_path.write_text("bad trailing space \n", encoding="utf-8")
        invalid = self.run_helper("bad.md", check_only=True, task_id="t_scope")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual(task_handoff.read_bytes(), original_bytes)

    def test_check_only_does_not_create_handoff(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        check = self.run_helper("tracked.txt", check_only=True, task_id="t_new")
        self.assertEqual(check.returncode, 0, check.stderr)
        raw = git(
            self.repo, "rev-parse", "--git-path",
            "hermes/task-handoffs/t_new/current.json",
        )
        path = Path(raw)
        if not path.is_absolute():
            path = self.repo / path
        self.assertFalse(path.exists())

    def test_standard_flow_requires_scoped_include(self) -> None:
        proc = self.run_helper()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("scoped --include paths are required", proc.stderr)
        self.assertIn("--allow-full-scan", proc.stderr)

    def test_explicit_full_diagnostic_remains_available(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        proc = self.run_helper(allow_full_scan=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TRACKED_CHANGED_COUNT=1", proc.stdout)

    def test_untracked_discovery_uses_pathspec_when_scoped(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('return git_paths(root, ["ls-files", "--others", "--exclude-standard"], includes)', source)
        self.assertNotIn("all_untracked = git_paths", source)

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
        proc = self.run_helper("tracked.txt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TRACKED_CHANGED_COUNT=0", proc.stdout)
        self.assertIn("EOL_ONLY_COUNT=1", proc.stdout)
        self.assertIn("WHITESPACE_ERROR_COUNT=0", proc.stdout)
        self.assertIn("HANDOFF_GATE=PASS", proc.stdout)

    def test_crlf_file_with_real_change_passes_without_false_trailing_whitespace(self) -> None:
        (self.repo / "tracked.txt").write_bytes(b"changed\r\n")
        proc = self.run_helper("tracked.txt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TRACKED_CHANGED_COUNT=1", proc.stdout)
        self.assertIn("EOL_ONLY_COUNT=0", proc.stdout)
        self.assertIn("WHITESPACE_ERROR_COUNT=0", proc.stdout)
        self.assertIn("HANDOFF_GATE=PASS", proc.stdout)

    def test_real_trailing_whitespace_in_crlf_file_fails(self) -> None:
        (self.repo / "tracked.txt").write_bytes(b"changed \r\n")
        proc = self.run_helper("tracked.txt")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("WHITESPACE_ERROR_COUNT=1", proc.stdout)
        self.assertIn("HANDOFF_GATE=FAIL", proc.stdout)

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


    def test_non_git_summary_uses_declared_paths_without_snapshot(self) -> None:
        workspace = Path(self.tmp.name) / "non-git"
        workspace.mkdir()
        (workspace / "app.txt").write_text("changed\n", encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workspace", str(workspace),
                "--version-control", "none",
                "--include", "app.txt",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("VERSION_CONTROL=none", proc.stdout)
        self.assertIn("SCAN_MODE=unsupported-non-git", proc.stdout)
        self.assertIn("CHANGE_TRACKING=unsupported", proc.stdout)
        self.assertIn("DECLARED_CHANGED_COUNT=1", proc.stdout)
        self.assertIn("DECLARED_CHANGED_1=app.txt", proc.stdout)
        self.assertIn("HANDOFF_GATE=NOT_APPLICABLE", proc.stdout)
        self.assertNotIn("EFFECTIVE_SCOPE_SHA256=", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
