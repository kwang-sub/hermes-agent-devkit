#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

HERMES_JAVA = Path(__file__).resolve().parent / "hermes-java"


def make_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def make_repo(base: Path, *, wrapper_jar: bool) -> tuple[Path, dict[str, str], Path]:
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
        'printf "WRAPPER\\n" > "$HERMES_JAVA_TEST_LOG"\n'
        'printf "%s\\n" "$@" >> "$HERMES_JAVA_TEST_LOG"\n',
    )

    wrapper_dir = repo / "gradle/wrapper"
    wrapper_dir.mkdir(parents=True)
    (wrapper_dir / "gradle-wrapper.properties").write_text(
        "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.7-bin.zip\n",
        encoding="utf-8",
    )
    if wrapper_jar:
        (wrapper_dir / "gradle-wrapper.jar").write_bytes(b"placeholder")

    log = base / "execution.log"
    env = os.environ.copy()
    env.update(
        {
            "GRADLE_USER_HOME": str(base / "gradle-user-home"),
            "HERMES_GRADLE_PROJECT_CACHE_ROOT": str(base / "project-cache"),
            "HERMES_JAVA_TEST_LOG": str(log),
        }
    )
    return repo, env, log


def install_cached_gradle(
    base: Path,
    *,
    version: str = "8.7",
    distribution: str = "bin",
) -> Path:
    gradle = (
        base
        / "gradle-user-home/wrapper/dists"
        / f"gradle-{version}-{distribution}"
        / "cache-key"
        / f"gradle-{version}"
        / "bin/gradle"
    )
    make_executable(
        gradle,
        "#!/usr/bin/env bash\n"
        'printf "CACHED\\n" > "$HERMES_JAVA_TEST_LOG"\n'
        'printf "%s\\n" "$@" >> "$HERMES_JAVA_TEST_LOG"\n',
    )
    return gradle


def run_gradle(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HERMES_JAVA), "./gradlew", "test", "--tests", "*SmfpLog*"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def assert_common_arguments(log: str) -> None:
    assert "--project-cache-dir" in log, log
    assert "test" in log, log
    assert "--tests" in log, log
    assert "*SmfpLog*" in log, log


def test_wrapper_is_preferred() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo, env, log = make_repo(base, wrapper_jar=True)
        install_cached_gradle(base)

        result = run_gradle(repo, env)

        assert result.returncode == 0, result.stderr
        text = log.read_text(encoding="utf-8")
        assert text.startswith("WRAPPER\n"), text
        assert_common_arguments(text)


def test_missing_wrapper_uses_exact_cached_distribution() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo, env, log = make_repo(base, wrapper_jar=False)
        cached_gradle = install_cached_gradle(base)

        result = run_gradle(repo, env)

        assert result.returncode == 0, result.stderr
        text = log.read_text(encoding="utf-8")
        assert text.startswith("CACHED\n"), text
        assert str(cached_gradle) in result.stderr, result.stderr
        assert_common_arguments(text)


def test_wrong_cached_version_is_not_used() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo, env, _log = make_repo(base, wrapper_jar=False)
        install_cached_gradle(base, version="8.6")

        result = run_gradle(repo, env)

        assert result.returncode == 2
        assert "cached distribution was not found" in result.stderr, result.stderr
        assert "gradle-8.7-bin" in result.stderr, result.stderr


def main() -> int:
    tests = (
        test_wrapper_is_preferred,
        test_missing_wrapper_uses_exact_cached_distribution,
        test_wrong_cached_version_is_not_used,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
