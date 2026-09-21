#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/node_runtime.py"


def make_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def workspace_key(workspace: Path) -> str:
    digest = hashlib.sha256(str(workspace.resolve()).encode("utf-8")).hexdigest()[:16]
    return f"{workspace.name}-{digest}"


def package_json() -> dict:
    return {
        "name": "frontend",
        "private": True,
        "devEngines": {
            "runtime": {
                "name": "node",
                "version": "^24.11.0",
                "onFail": "download",
            },
            "packageManager": {
                "name": "pnpm",
                "version": ">=12 <13",
                "onFail": "download",
            },
        },
    }


def make_workspace(base: Path) -> tuple[Path, dict[str, str], Path]:
    workspace = base / "frontend"
    workspace.mkdir()
    (workspace / "package.json").write_text(
        json.dumps(package_json()), encoding="utf-8"
    )
    log = base / "env.log"
    command = base / "fake-command"
    make_executable(
        command,
        "#!/usr/bin/env bash\n"
        'printf "PNPM_HOME=%s\\n" "$PNPM_HOME" > "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "PNPM_STORE_DIR=%s\\n" "$PNPM_STORE_DIR" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "npm_config_store_dir=%s\\n" "$npm_config_store_dir" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "NEXT_DIST_DIR=%s\\n" "$NEXT_DIST_DIR" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "XDG_CACHE_HOME=%s\\n" "$XDG_CACHE_HOME" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "TMPDIR=%s\\n" "$TMPDIR" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "ARGS=%s\\n" "$*" >> "$NODE_RUNTIME_TEST_LOG"\n',
    )
    env = os.environ.copy()
    env.update(
        {
            "HERMES_NODE_ROOT": str(base / "node-root"),
            "PNPM_HOME": str(base / "bootstrap-pnpm"),
            "NODE_RUNTIME_TEST_LOG": str(log),
        }
    )
    return workspace, env, command


def run_runtime(workspace: Path, env: dict[str, str], command: list[str], timeout: int = 3):
    return subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--workspace",
            str(workspace),
            "--lock-timeout",
            str(timeout),
            "--",
            *command,
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_pnpm_state_is_outside_workspace_and_next_output_is_separate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, command = make_workspace(base)
        result = run_runtime(workspace, env, [str(command), "build", "--flag"])
        assert result.returncode == 0, result.stderr
        text = Path(env["NODE_RUNTIME_TEST_LOG"]).read_text(encoding="utf-8")
        root = Path(env["HERMES_NODE_ROOT"])
        key = workspace_key(workspace)
        assert f"PNPM_HOME={root / 'pnpm-home'}" in text
        assert f"PNPM_STORE_DIR={root / 'pnpm-store'}" in text
        assert f"npm_config_store_dir={root / 'pnpm-store'}" in text
        assert "NEXT_DIST_DIR=.next-hermes" in text
        assert f"XDG_CACHE_HOME={root / 'xdg-cache'}" in text
        assert f"TMPDIR={root / 'workspaces' / key / 'tmp'}" in text
        assert "ARGS=build --flag" in text


def test_workspace_lock_blocks_concurrent_verification() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, command = make_workspace(base)
        root = Path(env["HERMES_NODE_ROOT"])
        lock_path = root / "locks" / f"workspace-{workspace_key(workspace)}.lock"
        lock_path.parent.mkdir(parents=True)
        with lock_path.open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = run_runtime(workspace, env, [str(command), "test"], timeout=1)
        assert result.returncode == 2
        assert "timed out waiting for Node workspace lock" in result.stderr


def test_dependency_mutation_is_rejected_to_preserve_tirith_guard() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, _command = make_workspace(base)
        result = run_runtime(workspace, env, ["pnpm", "install"])
        assert result.returncode == 2
        assert "must run through dev-node-dependencies/Tirith" in result.stderr


def test_missing_dev_engines_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, command = make_workspace(base)
        (workspace / "package.json").write_text('{"name":"frontend"}', encoding="utf-8")
        result = run_runtime(workspace, env, [str(command), "test"])
        assert result.returncode == 2
        assert "devEngines is required" in result.stderr


def test_non_pnpm_package_manager_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, command = make_workspace(base)
        manifest = package_json()
        manifest["devEngines"]["packageManager"]["name"] = "npm"
        (workspace / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = run_runtime(workspace, env, [str(command), "test"])
        assert result.returncode == 2
        assert "must declare pnpm" in result.stderr


def main() -> int:
    tests = (
        test_pnpm_state_is_outside_workspace_and_next_output_is_separate,
        test_workspace_lock_blocks_concurrent_verification,
        test_dependency_mutation_is_rejected_to_preserve_tirith_guard,
        test_missing_dev_engines_is_blocked,
        test_non_pnpm_package_manager_is_blocked,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
