#!/usr/bin/env python3
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "review_context.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True).stdout.strip()


def field(output: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}=(.+)$", output, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"{name} missing from output:\n{output}")
    return match.group(1)


def handoff_state(repo: Path) -> Path:
    raw = git(repo, "rev-parse", "--git-path", "hermes/review-handoff.json")
    path = Path(raw)
    return path if path.is_absolute() else (repo / path).resolve()


class ReviewContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], capture_output=True, check=True)
        git(self.repo, "config", "user.name", "Hermes Test")
        git(self.repo, "config", "user.email", "hermes-test@example.invalid")
        git(self.repo, "config", "core.autocrlf", "false")
        (self.repo / "fixture.txt").write_text("base\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "branch", "dispatch-base", self.base)
        git(self.repo, "switch", "-c", "review")
        (self.repo / "change.txt").write_text("change\n")
        git(self.repo, "add", "change.txt")
        git(self.repo, "commit", "-m", "change")

    def tearDown(self):
        self.tmp.cleanup()

    def run_helper(self, *includes: str):
        cmd = [
            sys.executable, str(SCRIPT),
            "--base-branch", "dispatch-base",
            "--base-sha", self.base,
            "--expected-branch", "review",
            "--workspace", str(self.repo),
            "--expected-workspace", str(self.repo),
        ]
        for include in includes:
            cmd.extend(["--include", include])
        return subprocess.run(cmd, text=True, capture_output=True)

    def write_gate(self, paths: list[str], fingerprint: str) -> None:
        path = handoff_state(self.repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "workspace": str(self.repo.resolve()),
            "scope": paths,
            "effective_paths": paths,
            "effective_scope_sha256": fingerprint,
            "status": "valid",
        }) + "\n", encoding="utf-8")

    def test_missing_gate_requires_minimal_rerun(self):
        proc = self.run_helper()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("CODER_HANDOFF_GATE=FAIL", proc.stdout)
        self.assertIn("VERIFICATION_REUSE_ELIGIBLE=false", proc.stdout)
        self.assertIn("REVIEWER_TEST_RERUN_REQUIRED=true", proc.stdout)
        self.assertIn("RERUN_POLICY=minimal-once;no-rerun-tasks-for-confidence", proc.stdout)

    def test_matching_gate_reuses_verification(self):
        first = self.run_helper()
        current = field(first.stdout, "CURRENT_SCOPE_SHA256")
        self.write_gate(["change.txt"], current)
        second = self.run_helper()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("CODER_HANDOFF_GATE=PASS", second.stdout)
        self.assertIn("CODER_HANDOFF_GATE_REASON=matched", second.stdout)
        self.assertIn("VERIFICATION_REUSE_ELIGIBLE=true", second.stdout)
        self.assertIn("REVIEWER_TEST_RERUN_REQUIRED=false", second.stdout)
        self.assertIn(f"EFFECTIVE_SCOPE_SHA256={current}", second.stdout)

    def test_stale_gate_disables_reuse(self):
        first = self.run_helper()
        current = field(first.stdout, "CURRENT_SCOPE_SHA256")
        self.write_gate(["change.txt"], current)
        (self.repo / "change.txt").write_text("changed after summary\n")
        second = self.run_helper()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("CODER_HANDOFF_GATE=FAIL", second.stdout)
        self.assertIn("VERIFICATION_REUSE_ELIGIBLE=false", second.stdout)
        self.assertIn("REVIEWER_TEST_RERUN_REQUIRED=true", second.stdout)

    def test_external_include_is_secondary_scope(self):
        external = Path(self.tmp.name) / "docs" / "design.md"
        external.parent.mkdir()
        external.write_text("# design\n", encoding="utf-8")
        proc = self.run_helper("change.txt", str(external))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PRIMARY_SCOPE=change.txt", proc.stdout)
        self.assertIn("EXTERNAL_INCLUDE_COUNT=1", proc.stdout)
        self.assertRegex(proc.stdout, r"EXTERNAL_SCOPE_SHA256=[0-9a-f]{64}")
        self.assertIn("EXTERNAL_SCOPE_POLICY=docs-or-secondary-workspace;do-not-invalidate-primary-executable-verification", proc.stdout)

    def test_crlf_only_change_is_noise(self):
        (self.repo / "fixture.txt").write_bytes(b"base\r\n")
        proc = self.run_helper("fixture.txt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TRACKED_CHANGED_COUNT=0", proc.stdout)
        self.assertIn("EOL_ONLY_COUNT=1", proc.stdout)
        self.assertIn("DIFF_CHECK=PASS", proc.stdout)

    def test_rejects_malformed_sha(self):
        cmd = [
            sys.executable, str(SCRIPT),
            "--base-branch", "dispatch-base",
            "--base-sha", "bad",
            "--expected-branch", "review",
            "--workspace", str(self.repo),
            "--expected-workspace", str(self.repo),
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("full 40-character", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
