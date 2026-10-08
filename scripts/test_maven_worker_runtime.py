#!/usr/bin/env python3
"""Regression tests for worker startup responsibility and bounded Maven verification."""
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
from devkit_worker_startup import MARKER, LEGACY_REVIEW_PIN, LEGACY_SKIP_MARKER, with_worker_startup
import patch_hermes_kanban_session_affinity as patch

spec = importlib.util.spec_from_file_location("maven_verification", ROOT / "custom-skills/coder/dev-implement-plan/scripts/maven_verification.py")
verification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification)


class StartupTest(unittest.TestCase):
    def test_new_and_resumed_roles(self) -> None:
        for profile in ("coder", "reviewer"):
            for prefix in ([], ["--resume", "existing-session"]):
                argv = ["hermes", "-p", profile, *prefix, "chat", "-q", "work kanban task t_demo"]
                result = with_worker_startup(argv, profile)
                self.assertEqual(argv[-1], "work kanban task t_demo")
                self.assertEqual(result[:-1], argv[:-1])
                self.assertEqual(result[-1].count(MARKER), 1)
                self.assertIn("KANBAN_EXECUTION_BOUNDARY_V1", result[-1])
                self.assertIn("Provider별 Worker Context", result[-1])
                self.assertIn("kanban_show", result[-1])
                self.assertIn("ownership ENV가 scrub되므로", result[-1])
                self.assertNotIn("verify_worker_context.py", result[-1])
                expected_skill = "dev-implement-plan" if profile == "coder" else "dev-code-review"
                self.assertIn(f'skill_view("{expected_skill}")', result[-1])
                self.assertNotIn("hermes-maven", result[-1])
                self.assertNotIn("maven_verification.py", result[-1])
                self.assertEqual(result, with_worker_startup(result, profile))

    def test_coder_context_route_reminder_is_consistent_across_restarts(self) -> None:
        for prefix in ([], ["--resume", "old-coder-session"]):
            for flow in ("DIRECT", "STANDARD", "RECOVERY", "CHANGES_REQUESTED"):
                query = f"work kanban task t_demo ({flow})"
                argv = ["hermes", "-p", "coder", *prefix, "chat", "-q", query]
                actual = with_worker_startup(argv, "coder")
                self.assertIn("kanban_show를 Worker Context 근거로 사용", actual[-1])
                self.assertIn("Shell 환경변수 검사기를 호출하지 않는다", actual[-1])
                self.assertEqual(actual, with_worker_startup(actual, "coder"))
                self.assertEqual(argv[-1], query, "do not mutate Task source input")

    def test_legacy_review_pin_skipped_for_coder_without_changing_task(self) -> None:
        for prefix in ([], ["--resume", "existing-session"]):
            argv = [
                "hermes", "-p", "coder", *prefix, "--cli",
                "--skills", LEGACY_REVIEW_PIN,
                "--skills", "dev-java-guidelines",
                "--skills", LEGACY_REVIEW_PIN,
                "--skills", "unknown-other-skill",
                "chat", "-q", "work kanban task t_old",
            ]
            original = list(argv)
            actual = with_worker_startup(argv, "coder")
            self.assertEqual(argv, original, "startup must not mutate Kanban-derived argv")
            prefix_args = actual[:actual.index("-q")]
            self.assertNotIn(LEGACY_REVIEW_PIN, prefix_args)
            self.assertEqual(prefix_args.count("--skills"), 2)
            self.assertIn("dev-java-guidelines", prefix_args)
            self.assertIn("unknown-other-skill", prefix_args, "unknown skills must fail closed upstream")
            self.assertIn('skill_view("dev-implement-plan")', actual[-1])
            self.assertEqual(actual[-1].count(LEGACY_SKIP_MARKER), 1)
            self.assertEqual(with_worker_startup(actual, "coder"), actual)

    def test_reviewer_preloads_legacy_shim_without_role_leakage(self) -> None:
        argv = [
            "hermes", "-p", "reviewer", "--skills", LEGACY_REVIEW_PIN,
            "--skills", "dev-java-guidelines",
            "chat", "--query", "work kanban task t_old",
        ]
        actual = with_worker_startup(argv, "reviewer")
        self.assertEqual(actual[:-1], argv[:-1])
        self.assertEqual(actual[:-1].count(LEGACY_REVIEW_PIN), 1)
        self.assertIn('skill_view("dev-code-review")', actual[-1])
        self.assertNotIn(LEGACY_SKIP_MARKER, actual[-1])
        reviewer_shim = ROOT / "custom-skills/reviewer/sdlc-review/SKILL.md"
        self.assertTrue(reviewer_shim.is_file())
        self.assertIn("dev-code-review", reviewer_shim.read_text(encoding="utf-8"))
        self.assertFalse((ROOT / "custom-skills/coder/sdlc-review/SKILL.md").exists())

    def test_only_exact_known_legacy_flag_is_affected(self) -> None:
        argv = [
            "hermes", "-p", "coder",
            "--skills=sdlc-review", "--skills=other-old-review",
            "--skills", "sdlc-review-other",
            "chat", "-q", "work kanban task t_demo",
        ]
        actual = with_worker_startup(argv, "coder")
        self.assertNotIn("--skills=sdlc-review", actual[:actual.index("-q")])
        self.assertIn("--skills=other-old-review", actual[:actual.index("-q")])
        self.assertIn("sdlc-review-other", actual[:actual.index("-q")])
        self.assertIn(LEGACY_SKIP_MARKER, actual[-1])

    def test_dispatcher_current_sample_skips_legacy_pin_in_coder(self) -> None:
        from unittest.mock import patch as mock_patch
        fake_package = types.ModuleType("hermes_cli")
        affinity = types.ModuleType("hermes_cli.devkit_session_affinity")
        affinity.choose_worker_session = lambda **kwargs: types.SimpleNamespace(mode="NEW", session_id=None)
        startup = types.ModuleType("hermes_cli.devkit_worker_startup")
        startup.with_worker_startup = with_worker_startup
        original = 'return ["hermes", "-p", profile_arg, "chat", "-q", f"work kanban task {task.id}"]'
        replacement = 'return ["hermes", "-p", profile_arg, "--skills", "sdlc-review", "--skills", "dev-java-guidelines", "chat", "-q", f"work kanban task {task.id}"]'
        source = patch._current_sample()
        self.assertIn(original, source)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "kanban_db_dispatch.py"
            target.write_text(source.replace(original, replacement))
            self.assertEqual(patch.patch_source(target), "patched")
            with mock_patch.dict(sys.modules, {
                "hermes_cli": fake_package,
                "hermes_cli.devkit_session_affinity": affinity,
                "hermes_cli.devkit_worker_startup": startup,
            }):
                namespace = {}
                exec(compile(target.read_text(), str(target), "exec"), namespace)
                for role in ("coder", "reviewer"):
                    argv = namespace["_default_spawn"](
                        types.SimpleNamespace(id="t_old", assignee=role), "/workspace/project"
                    )
                    pins = argv[:argv.index("-q")]
                    self.assertEqual(LEGACY_REVIEW_PIN in pins, role == "reviewer")
                    self.assertIn("dev-java-guidelines", pins)
                    self.assertIn(MARKER, argv[-1])

    def test_unknown_role_is_unchanged(self) -> None:
        argv = ["hermes", "chat", "-q", "hello"]
        self.assertIs(with_worker_startup(argv, "orchestrator"), argv)

    def test_malformed_argv_fails_closed(self) -> None:
        for argv in (["hermes", "chat"], ["hermes", "-q"], ["hermes", "-q", "one", "-q", "two"]):
            with self.assertRaises(RuntimeError):
                with_worker_startup(argv, "coder")

    def test_prompt_remains_bounded_and_policy_only(self) -> None:
        prompt = with_worker_startup(["hermes", "-q", "work kanban task t_demo"], "coder")[-1]
        self.assertLess(len(prompt), 1600)
        for term in (
            "skill_view",
            "KANBAN_EXECUTION_BOUNDARY_V1",
        ):
            self.assertIn(term, prompt)
        for runtime_detail in (
            "verify_workspace.py",
            "hermes-maven",
            "maven_verification.py",
            "gradle_verification.py",
            "/opt/data/maven",
            "/opt/data/gradle",
        ):
            self.assertNotIn(runtime_detail, prompt)

    def test_patched_current_and_legacy_spawn_deliver_actual_prompt(self) -> None:
        fake_package = types.ModuleType("hermes_cli")
        fake_affinity = types.ModuleType("hermes_cli.devkit_session_affinity")
        fake_startup = types.ModuleType("hermes_cli.devkit_worker_startup")
        fake_startup.with_worker_startup = with_worker_startup
        # No shell ownership variables are injected by this adapter.
        from unittest.mock import patch as mock_patch
        for sample, function in ((patch._current_sample(), "_default_spawn"),
                                  (patch._legacy_sample().replace("\n\nclass _KB:", "\n    return cmd\n\nclass _KB:"), "spawn_worker")):
            for session_id in (None, "saved-session"):
                fake_affinity.choose_worker_session = lambda **kwargs: types.SimpleNamespace(mode="RESUME" if session_id else "NEW", session_id=session_id)
                modules = {"hermes_cli": fake_package, "hermes_cli.devkit_session_affinity": fake_affinity,
                           "hermes_cli.devkit_worker_startup": fake_startup}
                with tempfile.TemporaryDirectory() as tmp, mock_patch.dict(sys.modules, modules):
                    source = Path(tmp) / "worker.py"
                    source.write_text(sample)
                    self.assertEqual(patch.patch_source(source), "patched")
                    self.assertEqual(patch.patch_source(source), "already-patched")
                    namespace = {}
                    exec(compile(source.read_text(), str(source), "exec"), namespace)
                    argv = namespace[function](types.SimpleNamespace(id="t_demo", assignee="coder"), "/workspace/project")
                    self.assertIn(MARKER, argv[-1])
                    self.assertEqual("--resume" in argv, session_id is not None)


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
