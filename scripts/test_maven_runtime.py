#!/usr/bin/env python3
"""Regression tests for role-independent bounded Maven verification."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("maven_verification", ROOT / "scripts/verification/maven_verification.py")
verification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification)


class VerificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="maven-verifier-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.launcher = self.root / "launcher"
        self.write_launcher("exit 0\n")

    def write_launcher(self, text: str) -> None:
        self.launcher.write_text("#!/bin/sh\n" + text)
        self.launcher.chmod(0o755)

    def run_verification(self, seconds: int = 4):
        return verification.verify(self.root, "./mvnw", ["-B", "test"], self.launcher,
                                   self.root / "evidence", seconds)

    def test_success_evidence_has_real_exit_not_only_toolchain_ready(self) -> None:
        result = self.run_verification()
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["executed"])
        receipt = json.loads(Path(result["evidence"]).read_text())
        self.assertEqual(receipt["exit_code"], 0)
        self.assertNotIn("command", receipt)
        self.assertEqual(Path(result["log"]).stat().st_mode & 0o777, 0o600)

    def test_nonzero_is_not_success(self) -> None:
        self.write_launcher("exit 7\n")
        result = self.run_verification()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["exit_code"], 7)
        self.assertEqual(result["blocker"], "MAVEN_BUILD_OR_TEST_FAILED")

    def test_launcher_reason_is_preserved(self) -> None:
        self.write_launcher("echo MAVEN_BLOCKER=MAVEN_CACHE_NOT_WRITABLE\nexit 2\n")
        self.assertEqual(self.run_verification()["blocker"], "MAVEN_CACHE_NOT_WRITABLE")

    def test_missing_launcher_not_misreported_as_missing_cache(self) -> None:
        self.launcher.unlink()
        result = self.run_verification()
        self.assertEqual(result["blocker"], "MAVEN_LAUNCHER_MISSING")
        self.assertFalse(result["executed"])
        self.assertFalse((self.root / "evidence").exists())

    def test_timeout_reaps_descendants_and_releases_locks(self) -> None:
        import fcntl
        lock = self.root / "test.lock"
        self.write_launcher(f'exec 8>"{lock}"\nflock 8\ntrap "" TERM\nsleep 60 &\nwait\n')
        result = self.run_verification(seconds=1)
        self.assertEqual(result["blocker"], "MAVEN_COMMAND_TIMEOUT")
        self.assertLess(result["elapsed_seconds"], 5)
        with lock.open("w") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_dependency_and_offline_failures(self) -> None:
        self.assertEqual(verification.classify("Cannot access central in offline mode; has not been downloaded"), "MAVEN_OFFLINE_DEPENDENCY_MISSING")
        self.assertEqual(verification.classify("Could not resolve dependencies for project"), "MAVEN_DEPENDENCY_RESOLUTION_FAILED")

    def test_relative_evidence_root_rejected(self) -> None:
        with self.assertRaises(ValueError):
            verification.verify(self.root, "./mvnw", ["compile"], self.launcher, Path("relative"), 1)

    def test_invalid_timeouts(self) -> None:
        import argparse
        for value in ("0", "-1", "nan", "abc"):
            with self.assertRaises(argparse.ArgumentTypeError):
                verification.positive_seconds(value)


if __name__ == "__main__":
    unittest.main()
