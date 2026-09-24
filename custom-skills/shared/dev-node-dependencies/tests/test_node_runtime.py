#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNTIME = SCRIPTS / "node_runtime.py"
ENVIRONMENT_GATE = SCRIPTS / "node_environment_gate.py"
WORKSPACE_HELPER = SCRIPTS / "node_workspace.py"


def make_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def workspace_key(workspace: Path) -> str:
    digest = hashlib.sha256(str(workspace.resolve()).encode("utf-8")).hexdigest()[:16]
    return f"{workspace.name}-{digest}"


def write_manifest(workspace: Path, *, react_version: str = "19.3.0") -> None:
    (workspace / "package.json").write_text(
        json.dumps(
            {
                "name": "frontend",
                "private": True,
                "devEngines": {
                    "runtime": {
                        "name": "node",
                        "version": "22.23.2",
                        "onFail": "download",
                    },
                    "packageManager": {
                        "name": "pnpm",
                        "version": ">=12.0.0 <13.0.0",
                        "onFail": "download",
                    },
                },
                "dependencies": {"react": react_version},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def write_lock(workspace: Path, marker: str = "one") -> None:
    (workspace / "pnpm-lock.yaml").write_text(
        f"lockfileVersion: '9.0'\n# {marker}\n",
        encoding="utf-8",
    )


def make_workspace(base: Path) -> tuple[Path, dict[str, str], Path]:
    workspace = base / "frontend"
    workspace.mkdir()
    write_manifest(workspace)
    write_lock(workspace)
    (workspace / "src").mkdir()
    (workspace / "src" / "index.ts").write_text(
        "export const value = 1;\n", encoding="utf-8"
    )

    host_next = workspace / ".next" / "dev" / "types"
    host_next.mkdir(parents=True)
    (host_next / "stale.d.ts").write_text(
        "declare const stale: true;\n", encoding="utf-8"
    )
    host_modules = workspace / "node_modules"
    host_modules.mkdir()
    (host_modules / "windows-host-marker.txt").write_text(
        "host\n", encoding="utf-8"
    )
    (workspace / "tsconfig.tsbuildinfo").write_text(
        "host-cache\n", encoding="utf-8"
    )

    log = base / "env.log"
    fake_pnpm = base / "pnpm"
    make_executable(
        fake_pnpm,
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "config" ] && [ "$2" = "get" ]; then\n'
        '  key="${!#}"\n'
        '  case "$key" in\n'
        '    strictDepBuilds) printf "%s\\n" "${PNPM_TEST_STRICT_DEP_BUILDS:-true}" ;;\n'
        '    dangerouslyAllowAllBuilds) printf "%s\\n" "${PNPM_TEST_DANGEROUSLY_ALLOW_ALL_BUILDS:-false}" ;;\n'
        '    allowBuilds) if [ -n "${PNPM_TEST_ALLOW_BUILDS+x}" ]; then printf "%s\\n" "$PNPM_TEST_ALLOW_BUILDS"; else printf "{}\\n"; fi ;;\n'
        '    *) printf "null\\n" ;;\n'
        '  esac\n'
        '  exit 0\n'
        'fi\n'
        'printf "PWD=%s\\n" "$PWD" > "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "PNPM_HOME=%s\\n" "$PNPM_HOME" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "PNPM_STORE_DIR=%s\\n" "$PNPM_STORE_DIR" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "npm_config_store_dir=%s\\n" "$npm_config_store_dir" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "XDG_CACHE_HOME=%s\\n" "$XDG_CACHE_HOME" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "TMPDIR=%s\\n" "$TMPDIR" >> "$NODE_RUNTIME_TEST_LOG"\n'
        'printf "ARGS=%s\\n" "$*" >> "$NODE_RUNTIME_TEST_LOG"\n',
    )
    env = os.environ.copy()
    env.update(
        {
            "HERMES_NODE_ROOT": str(base / "node-root"),
            "NODE_RUNTIME_TEST_LOG": str(log),
            "PATH": f"{base}:{os.environ.get('PATH', '')}",
        }
    )
    return workspace, env, fake_pnpm


def run_runtime(
    workspace: Path,
    env: dict[str, str],
    command: list[str],
    timeout: int = 3,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(RUNTIME),
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


def run_environment_gate(
    workspace: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(ENVIRONMENT_GATE),
            "--workspace",
            str(workspace),
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def run_workspace_helper(
    workspace: Path,
    env: dict[str, str],
    *,
    mark: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        "python3",
        str(WORKSPACE_HELPER),
        "--workspace",
        str(workspace),
    ]
    if mark:
        command.append("--mark-restored")
    return subprocess.run(
        command,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def output_value(stdout: str, key: str) -> str:
    prefix = key + "="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    raise AssertionError(f"missing {key} in output: {stdout}")


def prepare_restored_workspace(
    workspace: Path,
    env: dict[str, str],
) -> Path:
    prepared = run_workspace_helper(workspace, env)
    assert prepared.returncode == 0, prepared.stderr
    isolated = Path(output_value(prepared.stdout, "NODE_ISOLATED_PACKAGE_ROOT"))
    installed = isolated / "node_modules" / "react"
    installed.mkdir(parents=True)
    (installed / "package.json").write_text(
        '{"name":"react"}\n', encoding="utf-8"
    )
    marked = run_workspace_helper(workspace, env, mark=True)
    assert marked.returncode == 0, marked.stderr
    assert "NODE_DEPENDENCIES_READY=true" in marked.stdout
    return isolated


def test_verification_runs_in_linux_isolated_workspace() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, fake_pnpm = make_workspace(base)
        isolated = prepare_restored_workspace(workspace, env)

        result = run_runtime(workspace, env, [str(fake_pnpm), "run", "build"])
        assert result.returncode == 0, result.stderr
        assert Path(output_value(result.stdout, "NODE_RUNTIME_CWD")) == isolated
        assert isolated != workspace
        assert str(isolated).startswith(str(Path(env["HERMES_NODE_ROOT"])))
        assert (isolated / "src" / "index.ts").read_text(
            encoding="utf-8"
        ) == "export const value = 1;\n"
        assert not (isolated / ".next").exists()
        assert not (
            isolated / "node_modules" / "windows-host-marker.txt"
        ).exists()
        assert not (isolated / "tsconfig.tsbuildinfo").exists()

        assert (
            workspace / ".next" / "dev" / "types" / "stale.d.ts"
        ).is_file()
        assert (
            workspace / "node_modules" / "windows-host-marker.txt"
        ).is_file()

        text = Path(env["NODE_RUNTIME_TEST_LOG"]).read_text(encoding="utf-8")
        root = Path(env["HERMES_NODE_ROOT"])
        assert f"PWD={isolated}" in text
        assert f"PNPM_HOME={root / 'pnpm-home'}" in text
        assert f"PNPM_STORE_DIR={root / 'pnpm-store'}" in text
        assert f"npm_config_store_dir={root / 'pnpm-store'}" in text
        assert f"XDG_CACHE_HOME={root / 'cache'}" in text
        assert "ARGS=run build" in text
        assert "NODE_RUNTIME_NODE_REQUIREMENT=22.23.2" in result.stdout
        assert (
            "NODE_RUNTIME_PNPM_REQUIREMENT=>=12.0.0 <13.0.0"
            in result.stdout
        )
        assert (
            "NODE_RUNTIME_OUTPUT_POLICY=linux-isolated-workspace;workspace-serialized"
            in result.stdout
        )


def test_internal_node_modules_survive_sync_but_generated_output_is_reset() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, fake_pnpm = make_workspace(base)
        isolated = prepare_restored_workspace(workspace, env)

        internal_marker = isolated / "node_modules" / "linux-marker.txt"
        internal_marker.write_text("linux\n", encoding="utf-8")
        internal_next = isolated / ".next" / "dev" / "types"
        internal_next.mkdir(parents=True)
        (internal_next / "old.d.ts").write_text(
            "declare const old: true;\n", encoding="utf-8"
        )
        (isolated / "old.tsbuildinfo").write_text(
            "old\n", encoding="utf-8"
        )
        (workspace / "src" / "index.ts").write_text(
            "export const value = 2;\n", encoding="utf-8"
        )

        result = run_runtime(workspace, env, [str(fake_pnpm), "run", "build"])
        assert result.returncode == 0, result.stderr
        assert internal_marker.is_file()
        assert not (isolated / ".next").exists()
        assert not (isolated / "old.tsbuildinfo").exists()
        assert (isolated / "src" / "index.ts").read_text(
            encoding="utf-8"
        ) == "export const value = 2;\n"


def test_dependency_fingerprint_change_invalidates_linux_node_modules() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, fake_pnpm = make_workspace(base)
        isolated = prepare_restored_workspace(workspace, env)
        assert (isolated / "node_modules" / "react").is_dir()

        write_manifest(workspace, react_version="19.3.1")
        write_lock(workspace, marker="two")
        result = run_runtime(workspace, env, [str(fake_pnpm), "run", "build"])

        assert result.returncode == 2
        assert "current package.json/pnpm-lock.yaml/pnpm-workspace.yaml fingerprint" in result.stderr
        assert not (isolated / "node_modules").exists()


def test_pnpm_workspace_policy_change_invalidates_linux_node_modules() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, fake_pnpm = make_workspace(base)
        isolated = prepare_restored_workspace(workspace, env)
        assert (isolated / "node_modules" / "react").is_dir()

        (workspace / "pnpm-workspace.yaml").write_text(
            "strictDepBuilds: true\n"
            "dangerouslyAllowAllBuilds: false\n"
            "allowBuilds:\n"
            "  'unrs-resolver@1.12.2': true\n",
            encoding="utf-8",
        )
        env["PNPM_TEST_ALLOW_BUILDS"] = '{"unrs-resolver@1.12.2":true}'
        result = run_runtime(workspace, env, [str(fake_pnpm), "run", "build"])

        assert result.returncode == 2
        assert "current package.json/pnpm-lock.yaml/pnpm-workspace.yaml fingerprint" in result.stderr
        assert not (isolated / "node_modules").exists()


def test_environment_gate_blocks_dangerous_global_build_allow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, _fake_pnpm = make_workspace(base)
        env["PNPM_TEST_DANGEROUSLY_ALLOW_ALL_BUILDS"] = "true"

        result = run_environment_gate(workspace, env)
        assert result.returncode == 2
        assert "BLOCKER_CLASS=PNPM_BUILD_POLICY_UNSAFE" in result.stderr
        assert "dangerouslyAllowAllBuilds=true" in result.stderr


def test_environment_gate_blocks_broad_build_approval() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, _fake_pnpm = make_workspace(base)
        env["PNPM_TEST_ALLOW_BUILDS"] = '{"unrs-resolver":true}'

        result = run_environment_gate(workspace, env)
        assert result.returncode == 2
        assert "BLOCKER_CLASS=PNPM_BUILD_POLICY_SCOPE_TOO_BROAD" in result.stderr


def test_environment_gate_accepts_exact_build_approval() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, _fake_pnpm = make_workspace(base)
        env["PNPM_TEST_ALLOW_BUILDS"] = '{"unrs-resolver@1.12.2":true}'

        result = run_environment_gate(workspace, env)
        assert result.returncode == 0, result.stderr
        assert "PNPM_APPROVED_BUILDS=unrs-resolver@1.12.2" in result.stdout


def test_restore_mark_rejects_source_change_after_install() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, _fake_pnpm = make_workspace(base)
        prepared = run_workspace_helper(workspace, env)
        assert prepared.returncode == 0, prepared.stderr
        isolated = Path(
            output_value(prepared.stdout, "NODE_ISOLATED_PACKAGE_ROOT")
        )
        installed = isolated / "node_modules" / "react"
        installed.mkdir(parents=True)
        (installed / "package.json").write_text(
            '{"name":"react"}\n', encoding="utf-8"
        )

        write_lock(workspace, marker="changed-after-restore")
        marked = run_workspace_helper(workspace, env, mark=True)
        assert marked.returncode == 2
        assert "changed after isolated restore" in marked.stderr


def test_workspace_lock_blocks_concurrent_verification() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, fake_pnpm = make_workspace(base)
        root = Path(env["HERMES_NODE_ROOT"])
        lock_path = (
            root / "locks" / f"workspace-{workspace_key(workspace)}.lock"
        )
        lock_path.parent.mkdir(parents=True)
        with lock_path.open("a+") as handle:
            fcntl.flock(
                handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
            )
            result = run_runtime(
                workspace,
                env,
                [str(fake_pnpm), "run", "test"],
                timeout=1,
            )
        assert result.returncode == 2
        assert "timed out waiting for Node workspace lock" in result.stderr


def test_dependency_mutation_is_rejected_to_preserve_tirith_guard() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, fake_pnpm = make_workspace(base)
        result = run_runtime(
            workspace, env, [str(fake_pnpm), "add", "react"]
        )
        assert result.returncode == 2
        assert "must run through dev-node-dependencies/Tirith" in result.stderr


def test_non_pnpm_command_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, _fake_pnpm = make_workspace(base)
        result = run_runtime(workspace, env, ["npm", "run", "build"])
        assert result.returncode == 2
        assert "only pnpm verification commands are supported" in result.stderr


def test_missing_dev_engines_runtime_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, fake_pnpm = make_workspace(base)
        (workspace / "package.json").write_text(
            '{"name":"frontend","devEngines":{"packageManager":{"name":"pnpm","version":"12.5.1","onFail":"download"}}}\n',
            encoding="utf-8",
        )
        result = run_runtime(
            workspace, env, [str(fake_pnpm), "run", "build"]
        )
        assert result.returncode == 2
        assert "must declare exactly one Node runtime" in result.stderr


def test_non_pnpm_project_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, fake_pnpm = make_workspace(base)
        manifest = json.loads(
            (workspace / "package.json").read_text(encoding="utf-8")
        )
        manifest["devEngines"]["packageManager"]["name"] = "npm"
        (workspace / "package.json").write_text(
            json.dumps(manifest) + "\n", encoding="utf-8"
        )
        result = run_runtime(
            workspace, env, [str(fake_pnpm), "run", "build"]
        )
        assert result.returncode == 2
        assert "packageManager.name must be 'pnpm'" in result.stderr


def test_environment_gate_passes_for_canonical_pnpm_project() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, _fake_pnpm = make_workspace(base)
        result = run_environment_gate(workspace, env)
        assert result.returncode == 0, result.stderr
        assert "FRONTEND_ENVIRONMENT_GATE=PASS" in result.stdout
        assert "BLOCKER_CLASS=NONE" in result.stdout
        assert "PACKAGE_MANAGER=pnpm" in result.stdout
        assert "SOURCE_VERIFICATION_POLICY=FORBIDDEN" in result.stdout
        assert "VERIFICATION_RUNTIME=node_runtime.py" in result.stdout


def test_environment_gate_blocks_legacy_npm_project_before_verification() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, fake_pnpm = make_workspace(base)
        manifest = json.loads(
            (workspace / "package.json").read_text(encoding="utf-8")
        )
        manifest["packageManager"] = "npm@11.17.0"
        (workspace / "package.json").write_text(
            json.dumps(manifest) + "\n", encoding="utf-8"
        )
        (workspace / "package-lock.json").write_text(
            '{"lockfileVersion":3}\n', encoding="utf-8"
        )

        gate = run_environment_gate(workspace, env)
        assert gate.returncode == 2
        assert "FRONTEND_ENVIRONMENT_GATE=BLOCKED" in gate.stderr
        assert "BLOCKER_CLASS=PROJECT_TOOLCHAIN_MIGRATION_REQUIRED" in gate.stderr
        assert "SOURCE_VERIFICATION_POLICY=FORBIDDEN" in gate.stderr

        runtime = run_runtime(
            workspace, env, [str(fake_pnpm), "run", "build"]
        )
        assert runtime.returncode == 2
        assert (
            "NODE_RUNTIME_BLOCKER_CLASS=PROJECT_TOOLCHAIN_MIGRATION_REQUIRED"
            in runtime.stderr
        )
        assert not Path(env["NODE_RUNTIME_TEST_LOG"]).exists()


def test_environment_gate_blocks_missing_pnpm_lock() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace, env, fake_pnpm = make_workspace(base)
        (workspace / "pnpm-lock.yaml").unlink()

        gate = run_environment_gate(workspace, env)
        assert gate.returncode == 2
        assert "BLOCKER_CLASS=PROJECT_TOOLCHAIN_MIGRATION_REQUIRED" in gate.stderr
        assert "pnpm-lock.yaml is required" in gate.stderr

        runtime = run_runtime(
            workspace, env, [str(fake_pnpm), "run", "typecheck"]
        )
        assert runtime.returncode == 2
        assert "pnpm-lock.yaml is required" in runtime.stderr
        assert not Path(env["NODE_RUNTIME_TEST_LOG"]).exists()


def main() -> int:
    tests = (
        test_environment_gate_passes_for_canonical_pnpm_project,
        test_environment_gate_blocks_legacy_npm_project_before_verification,
        test_environment_gate_blocks_missing_pnpm_lock,
        test_verification_runs_in_linux_isolated_workspace,
        test_internal_node_modules_survive_sync_but_generated_output_is_reset,
        test_dependency_fingerprint_change_invalidates_linux_node_modules,
        test_pnpm_workspace_policy_change_invalidates_linux_node_modules,
        test_environment_gate_blocks_dangerous_global_build_allow,
        test_environment_gate_blocks_broad_build_approval,
        test_environment_gate_accepts_exact_build_approval,
        test_restore_mark_rejects_source_change_after_install,
        test_workspace_lock_blocks_concurrent_verification,
        test_dependency_mutation_is_rejected_to_preserve_tirith_guard,
        test_non_pnpm_command_is_rejected,
        test_missing_dev_engines_runtime_is_blocked,
        test_non_pnpm_project_is_blocked,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
