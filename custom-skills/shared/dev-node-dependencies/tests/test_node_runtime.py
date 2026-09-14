#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
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


def make_workspace(base: Path) -> tuple[Path, dict[str, str], Path]:
    workspace = base / "frontend"
    workspace.mkdir()
    log = base / "env.log"
    command = base / "fake-command"
    make_executable(
        command,
        "#!/usr/bin/env bash\n"
        'printf "NPM_CONFIG_CACHE=%s\\n" "$NPM_CONFIG_CACHE" > "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "npm_config_store_dir=%s\\n" "$npm_config_store_dir" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "YARN_CACHE_FOLDER=%s\\n" "$YARN_CACHE_FOLDER" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "BUN_INSTALL_CACHE_DIR=%s\\n" "$BUN_INSTALL_CACHE_DIR" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "XDG_CACHE_HOME=%s\\n" "$XDG_CACHE_HOME" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "TMPDIR=%s\\n" "$TMPDIR" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "ARGS=%s\\n" "$*" >> "$NODE_RUNTIME_TEST_LOG"\n',
    )
    env = os.environ.copy()
    env.update(
        {
            "HERMES_NODE_ROOT": str(base / "node-root"),
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


def test_internal_caches_and_tmp_are_outside_workspace() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, command = make_workspace(base)
        result = run_runtime(workspace, env, [str(command), "build", "--flag"])
        assert result.returncode == 0, result.stderr
        text = Path(env["NODE_RUNTIME_TEST_LOG"]).read_text(encoding="utf-8")
        root = Path(env["HERMES_NODE_ROOT"])
        key = workspace_key(workspace)
        assert f"NPM_CONFIG_CACHE={root / 'npm-cache'}" in text
        assert f"npm_config_store_dir={root / 'pnpm-store'}" in text
        assert f"YARN_CACHE_FOLDER={root / 'yarn-cache'}" in text
        assert f"BUN_INSTALL_CACHE_DIR={root / 'bun-cache'}" in text
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
        result = run_runtime(workspace, env, ["npm", "install", "react"])
        assert result.returncode == 2
        assert "must run as the exact package-manager command" in result.stderr


def test_package_script_is_allowed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, command = make_workspace(base)
        fake_npm = base / "npm"
        make_executable(fake_npm, command.read_text(encoding="utf-8"))
        result = run_runtime(workspace, env, [str(fake_npm), "run", "build"])
        assert result.returncode == 0, result.stderr


def main() -> int:
    tests = (
        test_internal_caches_and_tmp_are_outside_workspace,
        test_workspace_lock_blocks_concurrent_verification,
        test_dependency_mutation_is_rejected_to_preserve_tirith_guard,
        test_package_script_is_allowed,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
