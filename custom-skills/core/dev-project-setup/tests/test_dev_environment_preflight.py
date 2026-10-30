from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dev_environment_preflight.py"
SPEC = importlib.util.spec_from_file_location("dev_environment_preflight", SCRIPT)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def git(cmd: list[str], repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *cmd], cwd=repo, text=True, capture_output=True)


class GitAttributesPreflightTest(unittest.TestCase):
    def test_creates_rules_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            self.assertEqual("created", preflight.ensure_gitattributes(repo))
            first = (repo / ".gitattributes").read_text(encoding="utf-8")
            self.assertIn("gradlew text eol=lf", first)
            self.assertIn("mvnw text eol=lf", first)
            self.assertIn("*.sh text eol=lf", first)
            self.assertIn("*.bat text eol=crlf", first)
            self.assertIn("*.cmd text eol=crlf", first)

            self.assertEqual("unchanged", preflight.ensure_gitattributes(repo))
            second = (repo / ".gitattributes").read_text(encoding="utf-8")
            self.assertEqual(first, second)

    def test_preserves_existing_non_conflicting_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            path = repo / ".gitattributes"
            path.write_text("* text=auto\n*.png binary\n", encoding="utf-8")

            self.assertEqual("updated", preflight.ensure_gitattributes(repo))
            updated = path.read_text(encoding="utf-8")
            self.assertTrue(updated.startswith("* text=auto\n*.png binary\n"))
            self.assertIn("# Hermes development defaults", updated)

    def test_blocks_conflicting_eol_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            path = repo / ".gitattributes"
            path.write_text("*.sh text eol=crlf\n", encoding="utf-8")

            with self.assertRaises(preflight.PreflightError):
                preflight.ensure_gitattributes(repo)

            self.assertEqual("*.sh text eol=crlf\n", path.read_text(encoding="utf-8"))

    def test_reports_existing_wrapper_crlf_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            wrapper = repo / "gradlew"
            wrapper.write_bytes(b"#!/bin/sh\r\necho ok\r\n")

            warnings = preflight.inspect_wrapper_eol(repo, "gradle")

            self.assertEqual(1, len(warnings))
            self.assertIn("CRLF", warnings[0])
            self.assertEqual(b"#!/bin/sh\r\necho ok\r\n", wrapper.read_bytes())


class GitChangeClassificationTest(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        git(["init", "-b", "dev"], repo)
        git(["config", "user.email", "test@example.invalid"], repo)
        git(["config", "user.name", "Preflight Test"], repo)
        git(["config", "core.autocrlf", "false"], repo)
        (repo / "app.txt").write_text("baseline\n", encoding="utf-8")
        git(["add", "app.txt"], repo)
        result = git(["commit", "-m", "baseline"], repo)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
        return repo

    def test_ignores_crlf_only_tracked_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            (repo / "app.txt").write_bytes(b"baseline\r\n")

            effective, eol_only = preflight.inspect_git_changes(repo)

            self.assertEqual([], effective)
            self.assertEqual(["app.txt"], eol_only)

    def test_keeps_real_and_untracked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            (repo / "app.txt").write_text("real change\n", encoding="utf-8")
            (repo / "new.txt").write_text("new\n", encoding="utf-8")

            effective, eol_only = preflight.inspect_git_changes(repo)

            self.assertEqual(["app.txt", "new.txt"], effective)
            self.assertEqual([], eol_only)


class JavaToolchainDetectionTest(unittest.TestCase):
    def test_detects_gradle_java_8_legacy_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "build.gradle").write_text(
                "sourceCompatibility = '1.8'\ntargetCompatibility = '1.8'\n",
                encoding="utf-8",
            )

            version, warnings = preflight.detect_java_target(repo, "gradle")

            self.assertEqual(8, version)
            self.assertEqual([], warnings)

    def test_detects_gradle_java_17_toolchain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "build.gradle.kts").write_text(
                "java { toolchain { languageVersion.set(JavaLanguageVersion.of(17)) } }\n",
                encoding="utf-8",
            )

            version, warnings = preflight.detect_java_target(repo, "gradle")

            self.assertEqual(17, version)
            self.assertEqual([], warnings)

    def test_detects_maven_java_21_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "pom.xml").write_text(
                "<project><properties><maven.compiler.release>21</maven.compiler.release>"
                "</properties></project>",
                encoding="utf-8",
            )

            version, warnings = preflight.detect_java_target(repo, "maven")

            self.assertEqual(21, version)
            self.assertEqual([], warnings)

    def test_defaults_to_java_17_when_target_is_not_declared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "build.gradle").write_text("plugins { id 'java' }\n", encoding="utf-8")

            version, warnings = preflight.detect_java_target(repo, "gradle")

            self.assertEqual(17, version)
            self.assertEqual(1, len(warnings))

    def test_blocks_conflicting_java_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "build.gradle").write_text(
                "sourceCompatibility = '1.8'\ntargetCompatibility = '17'\n",
                encoding="utf-8",
            )

            with self.assertRaises(preflight.PreflightError):
                preflight.detect_java_target(repo, "gradle")

    def test_gradle_9_uses_java_17_runtime_for_java_8_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            wrapper = repo / "gradle" / "wrapper"
            wrapper.mkdir(parents=True)
            (wrapper / "gradle-wrapper.properties").write_text(
                "distributionUrl=https\\://services.gradle.org/distributions/gradle-9.0.0-bin.zip\n",
                encoding="utf-8",
            )

            runtime, warnings = preflight.select_runtime_java(repo, "gradle", 8)

            self.assertEqual(17, runtime)
            self.assertEqual(1, len(warnings))

    def test_writes_managed_toolchain_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            path = preflight.write_toolchain_env(repo, 8, 8, Path("/opt/jdks/temurin-8"))
            text = path.read_text(encoding="utf-8")

            self.assertIn("HERMES_PROJECT_JAVA_TARGET=8", text)
            self.assertIn("HERMES_PROJECT_JAVA_RUNTIME=8", text)
            self.assertIn("JAVA_HOME=/opt/jdks/temurin-8", text)


if __name__ == "__main__":
    unittest.main()
