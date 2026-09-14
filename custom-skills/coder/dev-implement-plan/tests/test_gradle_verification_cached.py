#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gradle_verification_cached.py"


class GradleVerificationCachedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        (self.repo / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
        (self.repo / "build.gradle").write_text("plugins {}\n", encoding="utf-8")
        self.main_source = self.repo / "src/main/java/com/example/Target.java"
        self.main_source.parent.mkdir(parents=True)
        self.main_source.write_text("class Target {}\n", encoding="utf-8")
        self.source = self.repo / "src/test/java/com/example/TargetTest.java"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("class TargetTest {}\n", encoding="utf-8")
        self.evidence = self.base / "evidence"
        self.calls = self.base / "engine-calls.log"
        self.engine = self.base / "engine.py"
        self.engine.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import os, sys
                from pathlib import Path
                args = sys.argv[1:]
                Path(os.environ["CACHE_TEST_CALLS"]).open("a", encoding="utf-8").write(" ".join(args) + "\\n")
                is_preflight = "compileTestJava" in args or "compileJava" in args
                if is_preflight and os.environ.get("CACHE_PREFLIGHT_FAIL") == "1":
                    task = ":compileJava" if "compileJava" in args else ":compileTestJava"
                    print(f"> Task {task} FAILED")
                    print("PRIMARY_RESULT=FAIL")
                    print("PRIMARY_DURATION_SECONDS=2.0")
                    print("GRADLE_STATUS=FAIL")
                    print("GRADLE_BLOCKER=BUILD_FAILURE")
                    raise SystemExit(1)
                print("PRIMARY_RESULT=PASS")
                print("PRIMARY_DURATION_SECONDS=321.0")
                print("PRIMARY_COMMAND=hermes-java ./gradlew test --tests com.example.TargetTest")
                print("GRADLE_STATUS=PASS")
                print("GRADLE_BLOCKER=NONE")
                """
            ),
            encoding="utf-8",
        )
        self.engine.chmod(0o755)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_helper(
        self,
        *,
        timeout: int = 600,
        preflight_fail: bool = False,
        scope_paths: list[Path] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["CACHE_TEST_CALLS"] = str(self.calls)
        if preflight_fail:
            env["CACHE_PREFLIGHT_FAIL"] = "1"
        selected_scope = scope_paths or [self.source]
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--workspace",
            str(self.repo),
            "--mode",
            "TARGETED_TEST",
            "--test",
            "com.example.TargetTest",
        ]
        for path in selected_scope:
            cmd.extend(["--scope-path", str(path.relative_to(self.repo))])
        cmd.extend(
            [
                "--verification-timeout",
                str(timeout),
                "--compile-preflight-timeout",
                "60",
                "--engine",
                str(self.engine),
                "--evidence-root",
                str(self.evidence),
            ]
        )
        return subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            env=env,
        )

    def calls_list(self) -> list[str]:
        if not self.calls.exists():
            return []
        return self.calls.read_text(encoding="utf-8").splitlines()

    def call_count(self) -> int:
        return len(self.calls_list())

    def test_pass_is_reused_only_for_unchanged_scope(self) -> None:
        first = self.run_helper()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("VERIFICATION_PHASE_START=COMPILE_TEST", first.stdout)
        self.assertIn("VERIFICATION_PHASE_RESULT=PASS", first.stdout)
        self.assertIn("VERIFICATION_PHASE_START=TARGETED_TEST", first.stdout)
        self.assertIn("VERIFICATION_EVIDENCE=EXECUTED", first.stdout)
        self.assertIn("PRIMARY_REUSED=false", first.stdout)
        self.assertIn("VERIFICATION_TIMEOUT_SECONDS=600", first.stdout)
        self.assertRegex(first.stdout, r"VERIFICATION_TOTAL_DURATION_SECONDS=\d+\.\d+")
        self.assertEqual(self.call_count(), 2)

        second = self.run_helper()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("VERIFICATION_PHASE_START=CACHE_REUSE", second.stdout)
        self.assertIn("VERIFICATION_EVIDENCE=REUSED", second.stdout)
        self.assertIn("PRIMARY_REUSED=true", second.stdout)
        self.assertEqual(self.call_count(), 2, "unchanged scope must not rerun Gradle")

        self.source.write_text("class TargetTest { int changed; }\n", encoding="utf-8")
        third = self.run_helper()
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertIn("VERIFICATION_EVIDENCE=EXECUTED", third.stdout)
        self.assertIn("PRIMARY_REUSED=false", third.stdout)
        self.assertEqual(self.call_count(), 4, "source/test modification must force fresh verification")

    def test_compile_preflight_failure_skips_expensive_targeted_test(self) -> None:
        proc = self.run_helper(preflight_fail=True)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("VERIFICATION_PHASE_START=COMPILE_TEST", proc.stdout)
        self.assertIn("GRADLE_FAILURE_PHASE=COMPILE_TEST", proc.stdout)
        self.assertIn("FAIL_FAST_STOP=true", proc.stdout)
        self.assertIn("TARGETED_TEST_SKIPPED=true", proc.stdout)
        calls = self.calls_list()
        self.assertEqual(len(calls), 1)
        self.assertIn("compileTestJava", calls[0])
        self.assertFalse(any("--test com.example.TargetTest" in call or "--tests com.example.TargetTest" in call for call in calls))

    def test_test_only_scope_preflight_uses_compile_test_java(self) -> None:
        proc = self.run_helper(scope_paths=[self.source])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("VERIFICATION_PHASE_START=COMPILE_TEST", proc.stdout)
        self.assertIn("VERIFICATION_PHASE_TASK=compileTestJava", proc.stdout)
        calls = self.calls_list()
        self.assertIn("--task compileTestJava", calls[0])
        self.assertNotIn("--task compileJava", calls[0])

    def test_main_only_scope_preflight_uses_compile_java(self) -> None:
        proc = self.run_helper(scope_paths=[self.main_source])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("VERIFICATION_PHASE_START=COMPILE_PRODUCTION", proc.stdout)
        self.assertIn("VERIFICATION_PHASE_TASK=compileJava", proc.stdout)
        calls = self.calls_list()
        self.assertIn("--task compileJava", calls[0])
        self.assertNotIn("--task compileTestJava", calls[0])

    def test_mixed_main_and_test_scope_preflight_prefers_compile_java(self) -> None:
        proc = self.run_helper(scope_paths=[self.main_source, self.source])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("VERIFICATION_PHASE_START=COMPILE_PRODUCTION", proc.stdout)
        self.assertIn("VERIFICATION_PHASE_TASK=compileJava", proc.stdout)
        calls = self.calls_list()
        self.assertIn("--task compileJava", calls[0])
        self.assertNotIn("--task compileTestJava", calls[0])
        self.assertIn("--mode TARGETED_TEST", calls[1])

    def test_timeout_is_capped_at_ten_minutes(self) -> None:
        proc = self.run_helper(timeout=601)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("between 1 and 600 seconds", proc.stderr)
        self.assertEqual(self.call_count(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
