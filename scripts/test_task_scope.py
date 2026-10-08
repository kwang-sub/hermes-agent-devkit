#!/usr/bin/env python3
"""Shared Scope/EOL semantics and bulk diff regression tests."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom-skills" / "_lib"))
import task_scope

DIFF_CHECK = ROOT / "scripts" / "hermes-diff-check.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          text=True, capture_output=True).stdout.strip()


class TaskScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "DevKit Test")
        git(self.repo, "config", "core.autocrlf", "false")
        (self.repo / "eol.txt").write_bytes(b"unchanged\n")
        (self.repo / "changed file.txt").write_bytes(b"original\n")
        (self.repo / "clean.txt").write_bytes(b"original\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_semantic_detection_ignores_crlf_only(self) -> None:
        (self.repo / "eol.txt").write_bytes(b"unchanged\r\n")
        (self.repo / "changed file.txt").write_bytes(b"updated\r\n")
        paths = ["changed file.txt", "clean.txt", "eol.txt"]
        with patch.object(task_scope.subprocess, "run", wraps=subprocess.run) as call:
            semantic = task_scope.semantic_tracked_paths(self.repo, "HEAD", paths)
            self.assertEqual(call.call_count, 1)
        self.assertEqual(semantic, ["changed file.txt"])
        first = task_scope.scope_sha256(self.repo, ["eol.txt"])
        (self.repo / "eol.txt").write_bytes(b"unchanged\n")
        second = task_scope.scope_sha256(self.repo, ["eol.txt"])
        self.assertEqual(first, second)

    def test_bulk_whitespace_rejects_only_true_trailing_blanks(self) -> None:
        (self.repo / "eol.txt").write_bytes(b"unchanged\r\n")
        (self.repo / "changed file.txt").write_bytes(b"updated \r\n")
        command = [
            sys.executable, str(DIFF_CHECK), "--repo", str(self.repo),
            "--tracked", "changed file.txt", "--tracked", "eol.txt",
        ]
        proc = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("changed file.txt:1: trailing whitespace", proc.stdout)
        self.assertIn("WHITESPACE_ERROR_COUNT=1", proc.stdout)
        (self.repo / "changed file.txt").write_bytes(b"updated\r\n")
        proc = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_120_file_scope_has_identical_semantics(self) -> None:
        for index in range(120):
            (self.repo / f"file-{index:03}.txt").write_bytes(b"original\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "many")
        for index in range(120):
            data = b"original\r\n" if index % 2 else b"changed\r\n"
            (self.repo / f"file-{index:03}.txt").write_bytes(data)
        changed = task_scope.semantic_tracked_paths(
            self.repo, "HEAD", [f"file-{i:03}.txt" for i in range(120)],
        )
        self.assertEqual(len(changed), 60)
        self.assertEqual(changed[0], "file-000.txt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
