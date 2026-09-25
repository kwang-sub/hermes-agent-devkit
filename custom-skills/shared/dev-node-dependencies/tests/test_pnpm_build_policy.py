#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
POLICY = SCRIPTS / "pnpm_build_policy.py"


def make_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def make_workspace(base: Path) -> tuple[Path, dict[str, str]]:
    workspace = base / "frontend"
    workspace.mkdir()
    (workspace / "package.json").write_text(
        json.dumps({"name": "frontend", "private": True}) + "\n",
        encoding="utf-8",
    )
    fake_pnpm = base / "pnpm"
    make_executable(
        fake_pnpm,
        "#!/usr/bin/env bash\n"
        'if [ "$1" != "config" ] || [ "$2" != "get" ]; then exit 9; fi\n'
        'key="${!#}"\n'
        'case "$key" in\n'
        '  strictDepBuilds) printf "%s\\n" "${PNPM_TEST_STRICT_DEP_BUILDS:-true}" ;;\n'
        '  dangerouslyAllowAllBuilds) printf "%s\\n" "${PNPM_TEST_DANGEROUSLY_ALLOW_ALL_BUILDS:-false}" ;;\n'
        '  allowBuilds) if [ -n "${PNPM_TEST_ALLOW_BUILDS+x}" ]; then printf "%s\\n" "$PNPM_TEST_ALLOW_BUILDS"; else printf "{}\\n"; fi ;;\n'
        '  *) printf "null\\n" ;;\n'
        'esac\n',
    )
    env = os.environ.copy()
    env["PATH"] = f"{base}:{env.get('PATH', '')}"
    return workspace, env


def run_policy(
    workspace: Path,
    env: dict[str, str],
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(POLICY),
            "--workspace",
            str(workspace),
            *extra,
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_default_policy_is_safe_without_workspace_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace, env = make_workspace(Path(tmp))
        result = run_policy(workspace, env)
        assert result.returncode == 0, result.stderr
        assert "PNPM_BUILD_POLICY=PASS" in result.stdout
        assert "PNPM_BUILD_POLICY_FILE=NOT_PRESENT" in result.stdout
        assert "PNPM_STRICT_DEP_BUILDS=true" in result.stdout
        assert "PNPM_DANGEROUSLY_ALLOW_ALL_BUILDS=false" in result.stdout


def test_unreviewed_placeholder_requires_one_time_review() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace, env = make_workspace(Path(tmp))
        env["PNPM_TEST_ALLOW_BUILDS"] = json.dumps(
            {"unrs-resolver@1.12.2": "set this to true or false"}
        )
        result = run_policy(workspace, env)
        assert result.returncode == 2
        assert "BLOCKER_CLASS=PNPM_BUILD_POLICY_REVIEW_REQUIRED" in result.stderr
        assert "unrs-resolver@1.12.2" in result.stderr


def test_pending_exact_matcher_can_be_resolved_by_decision_plan() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace, env = make_workspace(Path(tmp))
        env["PNPM_TEST_ALLOW_BUILDS"] = json.dumps(
            {"unrs-resolver@1.12.2": "set this to true or false"}
        )
        result = run_policy(
            workspace,
            env,
            "--approve",
            "unrs-resolver@1.12.2",
        )
        assert result.returncode == 0, result.stderr
        assert "PNPM_PENDING_BUILDS=unrs-resolver@1.12.2" in result.stdout
        assert '"unrs-resolver@1.12.2":true' in result.stdout
        assert "PNPM_BUILD_POLICY_DECISION=READY" in result.stdout


def test_exact_approval_passes_and_new_version_is_not_implicitly_approved() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace, env = make_workspace(Path(tmp))
        env["PNPM_TEST_ALLOW_BUILDS"] = json.dumps(
            {"unrs-resolver@1.12.2": True}
        )
        result = run_policy(workspace, env)
        assert result.returncode == 0, result.stderr
        assert "PNPM_APPROVED_BUILDS=unrs-resolver@1.12.2" in result.stdout
        assert "unrs-resolver@1.12.3" not in result.stdout


def test_broad_true_approval_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace, env = make_workspace(Path(tmp))
        env["PNPM_TEST_ALLOW_BUILDS"] = json.dumps({"unrs-resolver": True})
        result = run_policy(workspace, env)
        assert result.returncode == 2
        assert "BLOCKER_CLASS=PNPM_BUILD_POLICY_SCOPE_TOO_BROAD" in result.stderr


def test_decision_plan_merges_existing_policy_and_uses_pnpm_config_set() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace, env = make_workspace(Path(tmp))
        env["PNPM_TEST_ALLOW_BUILDS"] = json.dumps(
            {
                "esbuild@0.25.9": True,
                "telemetry-package@1.0.0": False,
            }
        )
        result = run_policy(
            workspace,
            env,
            "--approve",
            "unrs-resolver@1.12.2",
        )
        assert result.returncode == 0, result.stderr
        assert "PNPM_BUILD_POLICY_DECISION=READY" in result.stdout
        assert '"esbuild@0.25.9":true' in result.stdout
        assert '"telemetry-package@1.0.0":false' in result.stdout
        assert '"unrs-resolver@1.12.2":true' in result.stdout
        assert "pnpm config set --location=project --json strictDepBuilds true" in result.stdout
        assert "pnpm config set --location=project --json dangerouslyAllowAllBuilds false" in result.stdout
        assert "pnpm config set --location=project --json allowBuilds" in result.stdout


def test_batch_decision_reports_all_approvals_and_denials_once() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace, env = make_workspace(Path(tmp))
        result = run_policy(
            workspace,
            env,
            "--approve",
            "unrs-resolver@1.12.2",
            "--approve",
            "esbuild@0.25.9",
            "--deny",
            "telemetry-package@1.0.0",
        )
        assert result.returncode == 0, result.stderr
        assert "PNPM_BUILD_POLICY_DECISION_MODE=BATCH" in result.stdout
        assert "PNPM_BUILD_POLICY_DECISION_COUNT=3" in result.stdout
        assert "PNPM_BUILD_POLICY_APPROVAL_COUNT=2" in result.stdout
        assert "PNPM_BUILD_POLICY_DENIAL_COUNT=1" in result.stdout
        assert (
            "PNPM_BUILD_POLICY_BATCH_APPROVALS=esbuild@0.25.9,unrs-resolver@1.12.2"
            in result.stdout
        )
        assert (
            "PNPM_BUILD_POLICY_BATCH_DENIALS=telemetry-package@1.0.0"
            in result.stdout
        )
        assert '"esbuild@0.25.9":true' in result.stdout
        assert '"unrs-resolver@1.12.2":true' in result.stdout
        assert '"telemetry-package@1.0.0":false' in result.stdout


def test_decision_plan_requires_exact_version() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace, env = make_workspace(Path(tmp))
        result = run_policy(workspace, env, "--approve", "unrs-resolver")
        assert result.returncode == 2
        assert "BLOCKER_CLASS=PNPM_BUILD_POLICY_MATCHER_NOT_EXACT" in result.stderr


def main() -> int:
    tests = (
        test_default_policy_is_safe_without_workspace_file,
        test_unreviewed_placeholder_requires_one_time_review,
        test_pending_exact_matcher_can_be_resolved_by_decision_plan,
        test_exact_approval_passes_and_new_version_is_not_implicitly_approved,
        test_broad_true_approval_is_blocked,
        test_decision_plan_merges_existing_policy_and_uses_pnpm_config_set,
        test_batch_decision_reports_all_approvals_and_denials_once,
        test_decision_plan_requires_exact_version,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
