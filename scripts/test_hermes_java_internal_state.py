#!/usr/bin/env python3
from __future__ import annotations

import fcntl
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
        'printf "HERMES_GRADLE_BUILD_DIR=%s\\n" "$HERMES_GRADLE_BUILD_DIR" > "$HERMES_JAVA_TEST_LOG"\n'
        'printf "GRADLE_USER_HOME=%s\\n" "$GRADLE_USER_HOME" >> "$HERMES_JAVA_TEST_LOG"\n'
        'printf "ARGS=%s\\n" "$*" >> "$HERMES_JAVA_TEST_LOG"\n',
    )
    archive = base / f"gradle-{version}-bin.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in source.rglob("*"):
            if path.is_file():
                arcname = path.relative_to(base).as_posix()
                info = zipfile.ZipInfo.from_file(path, arcname)
                if os.access(path, os.X_OK):
                    info.external_attr = 0o100755 << 16
                zf.writestr(info, path.read_bytes())
    return archive, hashlib.sha256(archive.read_bytes()).hexdigest()


def make_repo(base: Path) -> tuple[Path, dict[str, str], Path]:
    repo = base / "project"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    java_home = base / "jdk"
    make_executable(java_home / "bin/java", "#!/usr/bin/env bash\nexit 0\n")
    (repo / ".hermes").mkdir()
    (repo / ".hermes/toolchain.env").write_text(f"JAVA_HOME={java_home}\n", encoding="utf-8")
    make_executable(repo / "gradlew", "#!/usr/bin/env bash\nexit 99\n")
    archive, digest = make_gradle_zip(base)
    props = repo / "gradle/wrapper/gradle-wrapper.properties"
    props.parent.mkdir(parents=True)
    props.write_text(
        f"distributionUrl={archive.as_uri()}\n"
        f"distributionSha256Sum={digest}\n",
        encoding="utf-8",
    )
    log = base / "execution.log"
    env = os.environ.copy()
    env.update({
        "HERMES_GRADLE_ROOT": str(base / "gradle-root"),
        "HERMES_JAVA_TEST_LOG": str(log),
    })
    return repo, env, log


def workspace_key(repo: Path) -> str:
    digest = subprocess.run(
        ["git", "hash-object", "--stdin"], cwd=repo, input=str(repo),
        text=True, capture_output=True, check=True,
    ).stdout.strip()[:12]
    return f"{repo.name}-{digest}"


def run_gradle(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HERMES_JAVA), "./gradlew", "test"],
        cwd=repo, env=env, text=True, capture_output=True, check=False,
    )


def test_build_output_and_project_cache_are_internal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo, env, log = make_repo(base)
        result = run_gradle(repo, env)
        assert result.returncode == 0, result.stderr
        root = Path(env["HERMES_GRADLE_ROOT"])
        key = workspace_key(repo)
        text = log.read_text(encoding="utf-8")
        assert f"HERMES_GRADLE_BUILD_DIR={root / 'builds' / key}" in text
        assert f"GRADLE_USER_HOME={root / 'user-home'}" in text
        assert f"--project-cache-dir {root / 'project-cache' / key}" in text
        assert f"--init-script {root / 'init' / 'hermes-build-output.gradle'}" in text
        init_text = (root / "init/hermes-build-output.gradle").read_text(encoding="utf-8")
        assert "HERMES_GRADLE_BUILD_DIR" in init_text
        assert "project.buildDir" in init_text
        assert not (repo / "build").exists()


def test_workspace_lock_blocks_concurrent_gradle() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo, env, _log = make_repo(base)
        first = run_gradle(repo, env)
        assert first.returncode == 0, first.stderr
        root = Path(env["HERMES_GRADLE_ROOT"])
        lock_path = root / "locks" / f"workspace-{workspace_key(repo)}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("w") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            env["HERMES_GRADLE_WORKSPACE_LOCK_TIMEOUT_SECONDS"] = "1"
            result = run_gradle(repo, env)
        assert result.returncode == 2
        assert "timed out waiting for Gradle workspace lock" in result.stderr


def main() -> int:
    tests = (
        test_build_output_and_project_cache_are_internal,
        test_workspace_lock_blocks_concurrent_gradle,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
