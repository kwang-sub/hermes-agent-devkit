#!/usr/bin/env python3
"""Executable, network-free tests of managed Maven (real shell + real archives)."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent


def executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


class MavenLauncherTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="hermes-maven-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.workspace = self.base / "project"
        self.workspace.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("HERMES_", "GIT_", "MAVEN_"))}
        for key in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
            self.env.pop(key, None)
        self.home = self.base / "coder-home"
        self.home.mkdir()
        self.jdk = self.base / "jdk"
        for command in ("java", "javac"):
            executable(self.jdk / "bin" / command, "#!/bin/sh\nexit 0\n")
        self.cache = self.base / "maven-cache"
        self.log = self.base / "maven-args"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for name in ("hermes-java", "hermes-maven"):
            shutil.copy2(ROOT / name, self.bin / name)
            (self.bin / name).chmod(0o755)
        # Simulate a machine without a usable system Maven.
        executable(self.bin / "mvn", '#!/bin/sh\necho GLOBAL_MAVEN_MUST_NOT_RUN >&2\nexit 97\n')
        self.env.update(HOME=str(self.home), HERMES_MAVEN_ROOT=str(self.cache),
                        HERMES_GRADLE_ROOT=str(self.base / "unused-gradle"),
                        PATH=str(self.bin) + os.pathsep + self.env["PATH"],
                        MAVEN_TEST_LOG=str(self.log), MAVEN_TEST_EXIT="0")
        self.git("init", "-q")
        self.git("config", "user.name", "Regression Test")
        self.git("config", "user.email", "regression@example.invalid")
        (self.workspace / ".hermes").mkdir()
        (self.workspace / ".hermes/toolchain.env").write_text(f'JAVA_HOME="{self.jdk}"\n')
        self.props = self.workspace / ".mvn/wrapper/maven-wrapper.properties"
        self.props.parent.mkdir(parents=True)
        self.wrapper = self.workspace / "mvnw"
        self.wrapper.write_bytes(b"#!/bin/sh\r\necho WRAPPER_MUST_NOT_RUN\r\nexit 96\r\n")
        self.wrapper.chmod(0o644)
        self.archive = self.make_archive()
        self.properties()
        self.git("add", "mvnw", ".mvn")
        self.git("commit", "-qm", "fixture")

    def git(self, *args: str, cwd: Path | None = None) -> None:
        subprocess.run(["git", *args], cwd=cwd or self.workspace, env=self.env,
                       check=True, capture_output=True, text=True)

    def make_archive(self, suffix: str = "zip", broken: bool = False) -> Path:
        directory = self.base / "archive-source" / "apache-maven-3.6.3"
        executable(directory / "bin/mvn", '#!/bin/sh\nprintf "%s\\n" "$JAVA_HOME" "$@" > "$MAVEN_TEST_LOG"\nexit "$MAVEN_TEST_EXIT"\n')
        path = self.base / f"apache-maven-3.6.3-bin.{suffix}"
        if suffix == "zip":
            with zipfile.ZipFile(path, "w") as archive:
                archive.write(directory / "bin/mvn", "wrong/bin/mvn" if broken else "apache-maven-3.6.3/bin/mvn")
        else:
            with tarfile.open(path, "w:gz") as archive:
                archive.add(directory, arcname=directory.name)
        return path

    def properties(self, digest: str | None = None) -> None:
        digest = digest or hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.props.write_bytes((f"distributionUrl={self.archive.as_uri()}\r\ndistributionSha256Sum={digest}\r\n").encode())

    def launch(self, *args: str, java: bool = False, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(self.bin / ("hermes-java" if java else "hermes-maven")), *args],
                              cwd=cwd or self.workspace, env=self.env, text=True, capture_output=True, timeout=8)

    def assert_ok(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        content = self.log.read_text()
        self.assertIn(f"-Dmaven.repo.local={self.cache}/repository", content)
        self.assertIn(str(self.jdk), content)
        self.assertFalse((self.home / ".m2").exists())

    def test_zip_and_crlf_wrapper_without_home_m2(self) -> None:
        original = self.wrapper.read_bytes()
        self.assert_ok(self.launch("./mvnw", "-B", "compile"))
        self.assertEqual(original, self.wrapper.read_bytes())
        self.assertIn("apache-maven-3.6.3/bin/mvn", str(next((self.cache / "distributions").rglob("mvn"))))

    def test_tar_archive(self) -> None:
        self.archive = self.make_archive("tar.gz")
        self.properties()
        self.assert_ok(self.launch("./mvnw", "test"))

    def test_java_delegates_before_gradle_state(self) -> None:
        self.assert_ok(self.launch("./mvnw", "compile", java=True))
        self.assertFalse((self.base / "unused-gradle").exists())

    def test_java_missing_maven_launcher_does_not_run_wrapper(self) -> None:
        (self.bin / "hermes-maven").unlink()
        result = self.launch("./mvnw", java=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("MAVEN_LAUNCHER_MISSING", result.stderr)
        self.assertFalse(self.log.exists())

    def test_mvn_prefers_project_wrapper_over_global(self) -> None:
        self.assert_ok(self.launch("mvn", "compile", java=True))

    def test_warm_cache_reused_without_distribution_network(self) -> None:
        self.assert_ok(self.launch("./mvnw", "compile"))
        self.archive.unlink()
        self.assert_ok(self.launch("./mvnw", "test"))

    def test_diagnose_is_read_only_for_cold_and_warm_cache(self) -> None:
        result = self.launch("--diagnose", "./mvnw")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PREPARATION_REQUIRED", result.stdout)
        self.assertFalse(self.cache.exists())
        self.assertFalse(self.log.exists())
        self.assert_ok(self.launch("./mvnw", "compile"))
        self.assertIn("MAVEN_STATUS=READY", self.launch("--diagnose", "./mvnw").stdout)

    def test_help_works_without_project_and_no_cache_writes(self) -> None:
        for java in (True, False):
            self.assertEqual(self.launch("--help", java=java, cwd=self.home).returncode, 0)
        self.assertFalse(self.cache.exists())

    def test_missing_toolchain_is_classified(self) -> None:
        (self.workspace / ".hermes/toolchain.env").unlink()
        result = self.launch("./mvnw", "compile")
        self.assertEqual(result.returncode, 2)
        self.assertIn("MAVEN_TOOLCHAIN_MISSING", result.stderr)
        self.assertFalse(self.cache.exists())

    def test_missing_javac_is_classified(self) -> None:
        (self.jdk / "bin/javac").unlink()
        self.assertIn("MAVEN_JDK_INVALID", self.launch("./mvnw", "compile").stderr)

    def test_missing_wrapper_is_classified(self) -> None:
        self.props.unlink()
        self.assertIn("MAVEN_WRAPPER_MISSING", self.launch("./mvnw", "compile").stderr)

    def test_repo_override_before_download(self) -> None:
        for argument in ("-Dmaven.repo.local=/tmp/escape", "-Dmaven.repo.local"):
            result = self.launch("./mvnw", argument, "compile")
            self.assertEqual(result.returncode, 2)
            self.assertIn("MAVEN_REPOSITORY_OVERRIDE", result.stderr)
        self.assertFalse(self.cache.exists())

    def test_environment_repo_override_rejected(self) -> None:
        for key in ("MAVEN_ARGS", "MAVEN_OPTS", "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS"):
            self.env[key] = "-Dmaven.repo.local=/tmp/escape"
            self.assertIn("MAVEN_REPOSITORY_OVERRIDE", self.launch("./mvnw", "compile").stderr)
            self.env.pop(key)
        self.assertFalse(self.cache.exists())

    def test_project_repo_override_rejected(self) -> None:
        (self.workspace / ".mvn/maven.config").write_text("-Dmaven.repo.local=/tmp/escape\n")
        self.assertIn("MAVEN_REPOSITORY_OVERRIDE", self.launch("./mvnw", "compile").stderr)
        self.assertFalse(self.cache.exists())

    def test_checksum_mismatch_blocks_before_execution(self) -> None:
        self.properties("0" * 64)
        result = self.launch("./mvnw", "compile")
        self.assertEqual(result.returncode, 2)
        self.assertIn("MAVEN_DISTRIBUTION_CHECKSUM_MISMATCH", result.stderr)
        self.assertFalse(self.log.exists())

    def test_wrong_archive_layout_not_reported_as_missing_global_mvn(self) -> None:
        self.archive = self.make_archive(broken=True)
        self.properties()
        self.assertIn("MAVEN_DISTRIBUTION_LAYOUT_INVALID", self.launch("./mvnw", "compile").stderr)
        self.assertFalse(self.log.exists())

    def test_download_failure_has_explicit_reason_and_no_url(self) -> None:
        self.archive.unlink()
        result = self.launch("./mvnw", "compile")
        self.assertIn("MAVEN_DISTRIBUTION_DOWNLOAD_FAILED", result.stderr)
        self.assertNotIn("file://", result.stderr)
        self.assertFalse(self.log.exists())

    def test_maven_nonzero_exit_preserved_including_73(self) -> None:
        for code in (1, 73):
            self.env["MAVEN_TEST_EXIT"] = str(code)
            result = self.launch("./mvnw", "test")
            self.assertEqual(result.returncode, code, result.stderr)
            self.assertNotIn("LOCK_TIMEOUT", result.stderr)

    def test_linked_worktree_uses_primary_toolchain(self) -> None:
        linked = self.base / "linked"
        self.git("worktree", "add", "-qb", "feature/test", str(linked))
        (linked / ".hermes").mkdir()
        (linked / ".hermes/toolchain.env").write_text("JAVA_HOME=/stale/path\n")
        self.assert_ok(self.launch("./mvnw", "test", cwd=linked))

    def test_non_git_workspace(self) -> None:
        shutil.rmtree(self.workspace / ".git")
        self.assert_ok(self.launch("./mvnw", "test"))

    def test_explicit_nested_build_root(self) -> None:
        module = self.workspace / "backend"
        module.mkdir()
        shutil.move(str(self.workspace / ".mvn"), str(module / ".mvn"))
        shutil.move(str(self.wrapper), str(module / "mvnw"))
        self.assert_ok(self.launch("./mvnw", "-pl", "service", "-am", "compile", cwd=module))
        self.assertIn("\n-pl\nservice\n-am\n", self.log.read_text())

    def test_workspace_lock_is_bounded(self) -> None:
        import fcntl
        self.assert_ok(self.launch("./mvnw", "compile"))
        lock = next((self.cache / "locks").glob("workspace-*.lock"))
        with lock.open("w") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            self.env["HERMES_MAVEN_WORKSPACE_LOCK_TIMEOUT_SECONDS"] = "1"
            result = self.launch("./mvnw", "compile")
            self.assertEqual(result.returncode, 2)
            self.assertIn("MAVEN_WORKSPACE_LOCK_TIMEOUT", result.stderr)

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory write bits")
    def test_unwritable_cache_diagnostic(self) -> None:
        self.cache.mkdir(mode=0o500)
        try:
            self.assertIn("MAVEN_CACHE_NOT_WRITABLE", self.launch("--diagnose", "./mvnw").stderr)
        finally:
            self.cache.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
