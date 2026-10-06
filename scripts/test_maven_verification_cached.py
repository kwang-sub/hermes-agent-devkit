#!/usr/bin/env python3
"""Regression tests for Maven fingerprint/evidence reuse."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "custom-skills/coder/dev-implement-plan/scripts/maven_verification_cached.py"


class CachedMavenVerificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="maven-cached-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        source = self.workspace / "src" / "Main.java"
        source.parent.mkdir()
        source.write_text("class Main {}\n", encoding="utf-8")
        self.source = source
        self.evidence = self.root / "evidence"
        self.counter = self.root / "counter"
        self.engine = self.root / "engine.py"
        self.write_engine(pass_result=True)

    def write_engine(self, *, pass_result: bool) -> None:
        status = "PASS" if pass_result else "BLOCKED"
        blocker = "NONE" if pass_result else "MAVEN_BUILD_OR_TEST_FAILED"
        exit_code = 0 if pass_result else 2
        self.engine.write_text(
            "from pathlib import Path\n"
            "import os\n"
            "counter = Path(os.environ['FAKE_MAVEN_COUNTER'])\n"
            "count = int(counter.read_text()) if counter.exists() else 0\n"
            "counter.write_text(str(count + 1))\n"
            f"print('MAVEN_STATUS={status}')\n"
            f"print('MAVEN_BLOCKER={blocker}')\n"
            "print('MAVEN_ELAPSED_SECONDS=1.0')\n"
            "print('MAVEN_EVIDENCE=/tmp/primary-result.json')\n"
            f"raise SystemExit({exit_code})\n",
            encoding="utf-8",
        )

    def run_helper(self, *maven_args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["FAKE_MAVEN_COUNTER"] = str(self.counter)
        env["HERMES_KANBAN_TASK"] = "t_cached_maven"
        return subprocess.run(
            [
                sys.executable,
                str(HELPER),
                "--workspace",
                str(self.workspace),
                "--engine",
                str(self.engine),
                "--evidence-root",
                str(self.evidence),
                "--mode",
                "COMPILE",
                "--scope-path",
                "src/Main.java",
                "--",
                *(maven_args or ("-B", "compile")),
            ],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def counter_value(self) -> int:
        return int(self.counter.read_text()) if self.counter.exists() else 0

    def test_unchanged_scope_reuses_pass_without_primary_execution(self) -> None:
        first = self.run_helper()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("VERIFICATION_EVIDENCE=EXECUTED", first.stdout)
        self.assertIn("PRIMARY_REUSED=false", first.stdout)
        fresh_evidence = [line for line in first.stdout.splitlines() if line.startswith("MAVEN_EVIDENCE=")][-1]
        self.assertIn(str(self.evidence), fresh_evidence)
        self.assertEqual(self.counter_value(), 1)

        second = self.run_helper()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("VERIFICATION_EVIDENCE=REUSED", second.stdout)
        self.assertIn("PRIMARY_REUSED=true", second.stdout)
        self.assertEqual(self.counter_value(), 1)

    def test_source_change_invalidates_cached_pass(self) -> None:
        self.assertEqual(self.run_helper().returncode, 0)
        self.source.write_text("class Main { int value; }\n", encoding="utf-8")
        rerun = self.run_helper()
        self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
        self.assertIn("VERIFICATION_EVIDENCE=EXECUTED", rerun.stdout)
        self.assertEqual(self.counter_value(), 2)

    def test_command_change_invalidates_cached_pass_without_storing_raw_args(self) -> None:
        first = self.run_helper("-B", "-Dtoken=secret-value", "compile")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.run_helper("-B", "compile")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(self.counter_value(), 2)
        receipts = list(self.evidence.rglob("*.json"))
        self.assertGreaterEqual(len(receipts), 2)
        for receipt in receipts:
            raw = receipt.read_text(encoding="utf-8")
            self.assertNotIn("secret-value", raw)
            data = json.loads(raw)
            self.assertIn("arguments_sha256", data)

    def test_blocked_result_is_never_reused(self) -> None:
        self.write_engine(pass_result=False)
        first = self.run_helper()
        second = self.run_helper()
        self.assertNotEqual(first.returncode, 0)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("VERIFICATION_EVIDENCE=NOT_REUSABLE", second.stdout)
        self.assertEqual(self.counter_value(), 2)

    def test_build_configuration_is_auto_fingerprinted(self) -> None:
        self.assertEqual(self.run_helper().returncode, 0)
        (self.workspace / "pom.xml").write_text("<project><version>2</version></project>\n", encoding="utf-8")
        rerun = self.run_helper()
        self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
        self.assertEqual(self.counter_value(), 2)


if __name__ == "__main__":
    unittest.main()
