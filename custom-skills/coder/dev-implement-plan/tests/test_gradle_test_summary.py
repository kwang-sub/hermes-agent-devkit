#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gradle_test_summary.py"


class GradleTestSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.workspace = self.base / "repo"
        self.workspace.mkdir()
        self.results = self.base / "results"
        self.results.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_helper(self, *, as_json: bool = False, results_root: Path | None = None):
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--workspace",
            str(self.workspace),
            "--results-root",
            str(results_root or self.results),
        ]
        if as_json:
            cmd.append("--json")
        return subprocess.run(cmd, text=True, capture_output=True)

    def write_suite(
        self,
        relative: str,
        *,
        tests: int,
        failures: int = 0,
        errors: int = 0,
        skipped: int = 0,
        failing_case: bool = False,
    ) -> None:
        path = self.results / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        case = (
            '<testcase classname="com.example.SampleTest" name="fails">'
            '<failure message="expected 1 but was 2">trace</failure></testcase>'
            if failing_case
            else '<testcase classname="com.example.SampleTest" name="passes"/>'
        )
        path.write_text(
            f'<testsuite name="sample" tests="{tests}" failures="{failures}" '
            f'errors="{errors}" skipped="{skipped}">{case}</testsuite>',
            encoding="utf-8",
        )

    def test_aggregates_junit_xml_across_projects(self) -> None:
        self.write_suite(
            "root/test-results/test/TEST-one.xml",
            tests=7,
            failures=1,
            skipped=1,
            failing_case=True,
        )
        self.write_suite(
            "module-a/test-results/test/TEST-two.xml",
            tests=5,
            errors=1,
        )
        proc = self.run_helper()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TEST_SUMMARY_STATUS=AVAILABLE", proc.stdout)
        self.assertIn("TEST_RESULT_FILE_COUNT=2", proc.stdout)
        self.assertIn("TEST_SUITE_COUNT=2", proc.stdout)
        self.assertIn("TESTS_TOTAL=12", proc.stdout)
        self.assertIn("TESTS_FAILURES=1", proc.stdout)
        self.assertIn("TESTS_ERRORS=1", proc.stdout)
        self.assertIn("TESTS_SKIPPED=1", proc.stdout)
        self.assertIn("TESTS_PASSED=9", proc.stdout)
        self.assertIn("TEST_FAILURE_DETAIL_COUNT=1", proc.stdout)
        self.assertIn("com.example.SampleTest.fails: expected 1 but was 2", proc.stdout)

    def test_missing_results_are_explicit_not_error(self) -> None:
        proc = self.run_helper()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TEST_SUMMARY_STATUS=MISSING", proc.stdout)
        self.assertIn("TEST_RESULT_FILE_COUNT=0", proc.stdout)
        self.assertIn("TESTS_TOTAL=0", proc.stdout)

    def test_json_mode_contains_same_contract(self) -> None:
        self.write_suite("root/test-results/test/TEST-one.xml", tests=3, skipped=1)
        proc = self.run_helper(as_json=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "AVAILABLE")
        self.assertEqual(payload["tests_total"], 3)
        self.assertEqual(payload["tests_skipped"], 1)
        self.assertEqual(payload["tests_passed"], 2)

    def test_invalid_xml_fails_without_guessing_counts(self) -> None:
        path = self.results / "root/test-results/test/TEST-bad.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<testsuite", encoding="utf-8")
        proc = self.run_helper()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("cannot parse JUnit XML", proc.stderr)
        self.assertNotIn("TESTS_TOTAL=", proc.stdout)

    def test_default_root_matches_hermes_build_key_contract(self) -> None:
        build_root = self.base / "builds"
        repo_hash = subprocess.run(
            ["git", "hash-object", "--stdin"],
            input=str(self.workspace.resolve()),
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()[:12]
        managed = build_root / f"repo-{repo_hash}"
        path = managed / "root/test-results/test/TEST-one.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '<testsuite name="sample" tests="2" failures="0" errors="0" skipped="0"/>',
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["HERMES_GRADLE_BUILD_ROOT"] = str(build_root)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(self.workspace)],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"TEST_RESULTS_ROOT={managed}", proc.stdout)
        self.assertIn("TESTS_TOTAL=2", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
