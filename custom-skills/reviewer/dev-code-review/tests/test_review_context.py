#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "review_context.py"
DIFF_CHECK = Path(__file__).resolve().parents[4] / "scripts" / "hermes-diff-check.py"
CHANGE_SUMMARY = (
    Path(__file__).resolve().parents[3]
    / "coder"
    / "dev-implement-plan"
    / "scripts"
    / "change_summary.py"
)


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

    def run_helper(self, *includes: str, allow_full_scan: bool = False):
        cmd = [
            sys.executable, str(SCRIPT),
            "--base-branch", "dispatch-base",
            "--base-sha", self.base,
            "--expected-branch", "review",
            "--workspace", str(self.repo),
            "--expected-workspace", str(self.repo),
        ]
        if allow_full_scan:
            cmd.append("--allow-full-scan")
        for include in includes:
            cmd.extend(["--include", include])
        env = os.environ.copy()
        env["HERMES_DIFF_CHECK"] = str(DIFF_CHECK)
        return subprocess.run(cmd, text=True, capture_output=True, env=env)

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

    def create_secondary_handoff(self) -> tuple[Path, str]:
        secondary = Path(self.tmp.name) / "docs"
        subprocess.run(["git", "init", "-b", "main", str(secondary)], capture_output=True, check=True)
        git(secondary, "config", "user.name", "Hermes Test")
        git(secondary, "config", "user.email", "hermes-test@example.invalid")
        git(secondary, "config", "core.autocrlf", "false")
        (secondary / "doc.md").write_text("# base\n", encoding="utf-8")
        git(secondary, "add", ".")
        git(secondary, "commit", "-m", "base")
        (secondary / "doc.md").write_text("# changed\n", encoding="utf-8")
        env = os.environ.copy()
        env["HERMES_DIFF_CHECK"] = str(DIFF_CHECK)
        proc = subprocess.run(
            [
                sys.executable,
                str(CHANGE_SUMMARY),
                "--workspace",
                str(secondary),
                "--include",
                "doc.md",
            ],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        relative = os.path.relpath(secondary / "doc.md", self.repo)
        return secondary, relative

    def test_matching_gate_reuses_verification(self):
        first = self.run_helper("change.txt")
        self.assertEqual(first.returncode, 0, first.stderr)
        current = field(first.stdout, "CURRENT_SCOPE_SHA256")
        self.write_gate(["change.txt"], current)
        second = self.run_helper("change.txt")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("SCAN_MODE=scoped", second.stdout)
        self.assertIn("CODER_HANDOFF_GATE=PASS", second.stdout)
        self.assertIn("REVIEWER_TEST_RERUN_REQUIRED=false", second.stdout)

    def test_standard_flow_requires_scoped_include(self):
        proc = self.run_helper()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("scoped --include paths", proc.stderr)
        self.assertIn("--allow-full-scan", proc.stderr)

    def test_explicit_full_diagnostic_remains_available(self):
        proc = self.run_helper(allow_full_scan=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SCAN_MODE=full-diagnostic", proc.stdout)

    def test_crlf_only_change_is_noise(self):
        (self.repo / "fixture.txt").write_bytes(b"base\r\n")
        proc = self.run_helper("fixture.txt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TRACKED_CHANGED_COUNT=0", proc.stdout)
        self.assertIn("EOL_ONLY_COUNT=1", proc.stdout)

    def test_crlf_file_with_real_change_passes_whitespace_check(self):
        (self.repo / "fixture.txt").write_bytes(b"changed\r\n")
        proc = self.run_helper("fixture.txt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TRACKED_CHANGED_COUNT=1", proc.stdout)
        self.assertIn("DIFF_CHECK=PASS", proc.stdout)

    def test_real_trailing_whitespace_in_crlf_file_is_rejected(self):
        (self.repo / "fixture.txt").write_bytes(b"changed \r\n")
        proc = self.run_helper("fixture.txt")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("trailing whitespace", proc.stderr)

    def test_untracked_lookup_uses_pathspec_when_scoped(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('return git_paths(root, ["ls-files", "--others", "--exclude-standard"], includes)', source)
        self.assertNotIn("all_paths = git_paths", source)

    def test_relative_sibling_repo_include_uses_secondary_handoff(self):
        secondary, relative = self.create_secondary_handoff()
        first = self.run_helper("change.txt")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.write_gate(["change.txt"], field(first.stdout, "CURRENT_SCOPE_SHA256"))

        proc = self.run_helper("change.txt", relative)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SECONDARY_WORKSPACE_COUNT=1", proc.stdout)
        self.assertIn(f"SECONDARY_1_WORKSPACE={secondary.resolve()}", proc.stdout)
        self.assertIn("SECONDARY_1_BRANCH=main", proc.stdout)
        self.assertIn("SECONDARY_1_CODER_HANDOFF_GATE=PASS", proc.stdout)
        self.assertIn("SECONDARY_1_CODER_HANDOFF_GATE_REASON=matched", proc.stdout)
        self.assertIn("ALL_REVIEW_SCOPE_HANDOFFS_MATCH=true", proc.stdout)
        self.assertIn("VERIFICATION_REUSE_ELIGIBLE=true", proc.stdout)

    def test_secondary_handoff_detects_content_changed_after_coder_summary(self):
        secondary, relative = self.create_secondary_handoff()
        (secondary / "doc.md").write_text("# changed again\n", encoding="utf-8")

        proc = self.run_helper("change.txt", relative)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SECONDARY_1_CODER_HANDOFF_GATE=FAIL", proc.stdout)
        self.assertIn("SECONDARY_1_CODER_HANDOFF_GATE_REASON=stale", proc.stdout)
        self.assertIn("ALL_REVIEW_SCOPE_HANDOFFS_MATCH=false", proc.stdout)

    def test_secondary_handoff_detects_branch_change(self):
        secondary, relative = self.create_secondary_handoff()
        git(secondary, "switch", "-c", "other")

        proc = self.run_helper("change.txt", relative)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SECONDARY_1_CODER_HANDOFF_GATE=FAIL", proc.stdout)
        self.assertIn("SECONDARY_1_CODER_HANDOFF_GATE_REASON=branch_mismatch", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
