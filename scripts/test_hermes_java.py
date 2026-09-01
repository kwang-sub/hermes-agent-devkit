#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


HERMES_JAVA = Path(__file__).resolve().parent / "hermes-java"


def make_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def make_gradle_zip(base: Path, version: str = "8.7") -> tuple[Path, str]:
    source = base / f"gradle-{version}"
    gradle = source / "bin/gradle"
    make_executable(
        gradle,
        "#!/usr/bin/env bash\n"
        'printf "MANAGED\\n" > "$HERMES_JAVA_TEST_LOG"\n'
        'printf "GRADLE_USER_HOME=%s\\n" "$GRADLE_USER_HOME" >> "$HERMES_JAVA_TEST_LOG"\n'
        'printf "%s\\n" "$@" >> "$HERMES_JAVA_TEST_LOG"\n',
    )
    archive = base / f"gradle-{version}-bin.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            arcname = path.relative_to(base).as_posix()
            info = zipfile.ZipInfo.from_file(path, arcname)
            if os.access(path, os.X_OK):
                info.external_attr = (0o100755 << 16)
            zf.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, digest


def make_repo(
    base: Path,
    *,
    properties_newline: str = "\n",
    checksum: bool = True,
) -> tuple[Path, dict[str, str], Path, Path]:
    repo = base / "project"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    java_home = base / "jdk"
    make_executable(java_home / "bin/java", "#!/usr/bin/env bash\nexit 0\n")

    (repo / ".hermes").mkdir()
    (repo / ".hermes/toolchain.env").write_text(
        f"JAVA_HOME={java_home}\n",
        encoding="utf-8",
    )

    make_executable(
        repo / "gradlew",
        "#!/usr/bin/env bash\n"
        'echo "WRAPPER_SHOULD_NOT_RUN" >&2\n'
        "exit 99\n",
    )

    archive, digest = make_gradle_zip(base)
    wrapper_dir = repo / "gradle/wrapper"
    wrapper_dir.mkdir(parents=True)
    lines = [f"distributionUrl={archive.as_uri()}"]
    if checksum:
        lines.append(f"distributionSha256Sum={digest}")
    (wrapper_dir / "gradle-wrapper.properties").write_text(
        properties_newline.join(lines) + properties_newline,
        encoding="utf-8",
        newline="",
    )

    log = base / "execution.log"
    gradle_root = base / "gradle-root"
    env = os.environ.copy()
    env.update(
        {
            "HERMES_GRADLE_ROOT": str(gradle_root),
            "GRADLE_USER_HOME": str(repo / ".gradle-home"),
            "HERMES_JAVA_TEST_LOG": str(log),
        }
    )
    return repo, env, log, archive


def run_gradle(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HERMES_JAVA), "./gradlew", "test", "--tests", "*SmfpLog*"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def assert_common_arguments(log: str, gradle_root: Path) -> None:
    assert log.startswith("MANAGED\n"), log
    assert f"GRADLE_USER_HOME={gradle_root / 'user-home'}" in log, log
    assert "--project-cache-dir" in log, log
    assert str(gradle_root / "project-cache") in log, log
    assert "test" in log, log
    assert "--tests" in log, log
    assert "*SmfpLog*" in log, log


def test_cache_miss_downloads_and_runs_exact_distribution() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo, env, log, _archive = make_repo(base)
        result = run_gradle(repo, env)
        assert result.returncode == 0, result.stderr
        assert "Gradle cache miss; downloading" in result.stderr, result.stderr
        gradle_root = Path(env["HERMES_GRADLE_ROOT"])
        managed = gradle_root / "distributions/gradle-8.7-bin/gradle-8.7/bin/gradle"
        assert managed.is_file(), managed
        assert_common_arguments(log.read_text(encoding="utf-8"), gradle_root)
        assert not (repo / ".gradle-home").exists()


def test_cache_hit_runs_without_source_archive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo, env, log, archive = make_repo(base)
        first = run_gradle(repo, env)
        assert first.returncode == 0, first.stderr
        archive.unlink()
        log.unlink()
        second = run_gradle(repo, env)
        assert second.returncode == 0, second.stderr
        assert "Gradle cache miss; downloading" not in second.stderr
        assert_common_arguments(log.read_text(encoding="utf-8"), Path(env["HERMES_GRADLE_ROOT"]))


def test_crlf_wrapper_properties_are_supported() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo, env, log, _archive = make_repo(base, properties_newline="\r\n")
        result = run_gradle(repo, env)
        assert result.returncode == 0, result.stderr
        assert_common_arguments(log.read_text(encoding="utf-8"), Path(env["HERMES_GRADLE_ROOT"]))


def test_checksum_mismatch_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo, env, _log, _archive = make_repo(base)
        properties = repo / "gradle/wrapper/gradle-wrapper.properties"
        text = properties.read_text(encoding="utf-8")
        text = "\n".join(
            "distributionSha256Sum=" + ("0" * 64)
            if line.startswith("distributionSha256Sum=") else line
            for line in text.splitlines()
        ) + "\n"
        properties.write_text(text, encoding="utf-8")
        result = run_gradle(repo, env)
        assert result.returncode == 2
        assert "checksum mismatch" in result.stderr, result.stderr


def test_missing_checksum_warns_but_runs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo, env, log, _archive = make_repo(base, checksum=False)
        result = run_gradle(repo, env)
        assert result.returncode == 0, result.stderr
        assert "distributionSha256Sum is not set" in result.stderr
        assert_common_arguments(log.read_text(encoding="utf-8"), Path(env["HERMES_GRADLE_ROOT"]))


def main() -> int:
    tests = (
        test_cache_miss_downloads_and_runs_exact_distribution,
        test_cache_hit_runs_without_source_archive,
        test_crlf_wrapper_properties_are_supported,
        test_checksum_mismatch_fails_closed,
        test_missing_checksum_warns_but_runs,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
