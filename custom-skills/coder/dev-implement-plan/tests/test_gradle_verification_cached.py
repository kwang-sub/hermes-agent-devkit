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
                import os
                from pathlib import Path
                Path(os.environ["CACHE_TEST_CALLS"]).open("a", encoding="utf-8").write("run\\n")
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

    def run_helper(self, *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["CACHE_TEST_CALLS"] = str(self.calls)
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workspace",
                str(self.repo),
                "--mode",
                "TARGETED_TEST",
                "--test",
                "com.example.TargetTest",
                "--scope-path",
                str(self.source.relative_to(self.repo)),
                "--verification-timeout",
                str(timeout),
                "--engine",
                str(self.engine),
                "--evidence-root",
                str(self.evidence),
            ],
            text=True,
            capture_output=True,
            env=env,
        )

    def call_count(self) -> int:
        if not self.calls.exists():
            return 0
        return len(self.calls.read_text(encoding="utf-8").splitlines())

    def test_pass_is_reused_only_for_unchanged_scope(self) -> None:
        first = self.run_helper()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("VERIFICATION_EVIDENCE=EXECUTED", first.stdout)
        self.assertIn("PRIMARY_REUSED=false", first.stdout)
        self.assertIn("VERIFICATION_TIMEOUT_SECONDS=600", first.stdout)
        self.assertEqual(self.call_count(), 1)

        second = self.run_helper()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("VERIFICATION_EVIDENCE=REUSED", second.stdout)
        self.assertIn("PRIMARY_REUSED=true", second.stdout)
        self.assertEqual(self.call_count(), 1, "unchanged scope must not rerun Gradle")

        self.source.write_text("class TargetTest { int changed; }\n", encoding="utf-8")
        third = self.run_helper()
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertIn("VERIFICATION_EVIDENCE=EXECUTED", third.stdout)
        self.assertIn("PRIMARY_REUSED=false", third.stdout)
        self.assertEqual(self.call_count(), 2, "source/test modification must force fresh verification")

    def test_timeout_is_capped_at_ten_minutes(self) -> None:
        proc = self.run_helper(timeout=601)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("between 1 and 600 seconds", proc.stderr)
        self.assertEqual(self.call_count(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
