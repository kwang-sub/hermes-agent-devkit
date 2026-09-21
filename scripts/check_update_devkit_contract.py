#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "update-devkit.ps1"
RUNTIME_VERIFIER = ROOT / "scripts/verify-container-runtime.ps1"
DOCKERFILE = ROOT / "Dockerfile"
TIRITH_PATCH = ROOT / "scripts/patch_hermes_tirith_profile_guard.py"
LATEST_COMPAT_SCRIPT = ROOT / "scripts/verify_latest_hermes_compat.sh"
LATEST_COMPAT_WORKFLOW = ROOT / ".github/workflows/latest-hermes-compat.yml"


def require(text: str, terms: tuple[str, ...], label: str) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{label} missing required contract terms: {', '.join(missing)}")


def forbid(text: str, terms: tuple[str, ...], label: str) -> None:
    present = [term for term in terms if term in text]
    if present:
        raise SystemExit(f"{label} contains forbidden destructive terms: {', '.join(present)}")


def executable_text(text: str) -> str:
    without_help = re.sub(r"<#.*?#>", "", text, flags=re.DOTALL)
    lines = [
        line
        for line in without_help.splitlines()
        if not line.lstrip().startswith("#")
    ]
    return "\n".join(lines)


def read_required(path: Path, label: str) -> str:
    if not path.is_file():
        raise SystemExit(f"{label} is missing: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8-sig")


def main() -> int:
    text = read_required(UPDATER, "update-devkit.ps1")

    require(
        text,
        (
            '#requires -Version 5.1',
            '[string]$Branch = "dev"',
            '[string]$HermesBaseImage = "nousresearch/hermes-agent:latest"',
            '[switch]$SkipProfileInit',
            'git" -Arguments @("status", "--porcelain=v1"',
            'git" -Arguments @("fetch", "--prune", $Remote)',
            'git" -Arguments @("merge", "--ff-only", $RemoteRef)',
            '$ImageBuildInputs = @(',
            '"Dockerfile"',
            '"scripts/hermes-java"',
            '$env:HERMES_BASE_IMAGE = $HermesBaseImage',
            'docker" -Arguments @("compose", "build", "--pull")',
            'docker" -Arguments @("compose", "up", "-d", "--force-recreate")',
            'function Invoke-ProfileInitialization',
            'init-profiles.ps1',
            'Profile/skill reconciliation',
            'PROFILES_RECONCILED=',
            'scripts\\verify-container-runtime.ps1',
            'Runtime verification failed. Performing one cached rebuild + force-recreate repair.',
            'sample.env changed. Existing .env is intentionally not overwritten',
            'HERMES_BASE_IMAGE=$HermesBaseImage',
            'IMAGE_REBUILT=',
            'CONTAINER_RECREATED=',
            'AUTOMATIC_REPAIR_USED=',
        ),
        "update-devkit.ps1",
    )

    if "Profile initialization is intentionally not run automatically" in text:
        raise SystemExit("update-devkit.ps1 still documents manual-only profile initialization")

    require(
        text,
        (
            'function Get-CapturedText',
            '[AllowNull()]',
            'if ($null -eq $Output)',
            'return ""',
        ),
        "update-devkit.ps1 empty-output contract",
    )

    require(
        text,
        (
            'function Test-AnyPathMatch',
            '[AllowEmptyCollection()]',
            '[string[]]$Paths',
            '$ChangedFiles = @()',
        ),
        "update-devkit.ps1 empty-change contract",
    )

    require(
        text,
        (
            '$PreviousHermesBaseImageExists = Test-Path Env:HERMES_BASE_IMAGE',
            '$PreviousHermesBaseImage = if ($PreviousHermesBaseImageExists)',
            'if ($PreviousHermesBaseImageExists)',
            'Remove-Item Env:HERMES_BASE_IMAGE -ErrorAction SilentlyContinue',
        ),
        "update-devkit.ps1 process-local base-image override contract",
    )

    executable = executable_text(text).lower()
    forbid(
        executable,
        (
            "compose down -v",
            '"down", "-v"',
            "git reset",
            '"reset"',
            "git clean",
            '"clean"',
            "git stash",
            '"stash"',
            "--no-cache",
        ),
        "update-devkit.ps1",
    )

    if text.count('docker" -Arguments @("compose", "build", "--pull")') != 1:
        raise SystemExit(
            "update-devkit.ps1 must have exactly one planned pull-build path"
        )

    if text.count('docker" -Arguments @("compose", "build")') < 1:
        raise SystemExit(
            "update-devkit.ps1 must keep one cached repair build path"
        )

    runtime_verifier = read_required(RUNTIME_VERIFIER, "runtime verifier")
    require(
        runtime_verifier,
        (
            'function Invoke-DockerExactOutputCheck',
            'Pinned Git 2.55.0 runtime',
            '"/usr/local/bin/git", "--version"',
            '-Expected "git version 2.55.0"',
            'Relative Git worktree paths',
            '"/usr/local/bin/git", "config", "--system", "--bool", "--get", "worktree.useRelativePaths"',
            '-Expected "true"',
            'Standalone pnpm 12.5.1 runtime',
            '"/usr/local/bin/pnpm", "--version"',
            '-Expected "12.5.1"',
            'Tirith routed-profile guard patch',
            'DEVKIT_TIRITH_PROFILE_GUARD_V1',
            '_devkit_tirith_subprocess_env',
            '_devkit_only_analysis_incomplete',
            'process-global environment',
            'Shared Node dependency capability',
        ),
        "update-devkit runtime Git/Tirith verification",
    )

    forbid(
        runtime_verifier,
        (
            '$(/usr/local/bin/git --version)',
            '$(/usr/local/bin/git config --system --bool --get worktree.useRelativePaths)',
        ),
        "Windows PowerShell-safe runtime Git verification",
    )

    tirith_patch = read_required(TIRITH_PATCH, "Hermes Tirith routed-profile patch")
    require(
        tirith_patch,
        (
            'DEVKIT_TIRITH_PROFILE_GUARD_V1',
            '_devkit_tirith_subprocess_env',
            'get_hermes_home_override',
            'apply_subprocess_home_env',
            '_devkit_only_analysis_incomplete',
            '_devkit_tirith_daemon_recheck',
            'Positive findings are never retried/bypassed',
            'profile_isolation',
        ),
        "Hermes Tirith routed-profile patch",
    )

    dockerfile = read_required(DOCKERFILE, "Dockerfile")
    require(
        dockerfile,
        (
            'FROM ${HERMES_BASE_IMAGE} AS hermes-upstream-patched',
            'FROM hermes-upstream-patched AS hermes-devkit-runtime',
            'ARG GIT_VERSION=2.55.0',
            'ARG PNPM_VERSION=12.5.1',
            'ENV PNPM_HOME=/opt/pnpm',
            'https://get.pnpm.io/install.sh',
            'PNPM_VERSION="${PNPM_VERSION}"',
            '/usr/local/bin/pnpm --version',
            'mkdir -p /tmp/git-worktree-check',
            'git -C /tmp/git-worktree-check init -q',
            'git -C /tmp/git-worktree-check worktree repair --relative-paths',
            'git config --system worktree.useRelativePaths true',
            'git config --system --bool --get worktree.useRelativePaths',
            'patch_hermes_tirith_profile_guard.py --self-test',
            'patch_hermes_tirith_profile_guard.py /opt/hermes/tools/tirith_security.py',
            "grep -q 'DEVKIT_TIRITH_PROFILE_GUARD_V1' /opt/hermes/tools/tirith_security.py",
            '/opt/hermes/tools/tirith_security.py',
            'patch_hermes_kanban_model_transition.py --self-test',
            "grep -q 'def _devkit_run_flow_model_transition' /opt/hermes/tools/kanban_tools.py",
            '/opt/hermes/.venv/bin/python -m py_compile',
        ),
        "Dockerfile latest-Hermes/Git compatibility stage",
    )

    if "git worktree repair -h 2>&1 | grep -q -- '--relative-paths'" in dockerfile:
        raise SystemExit(
            "Dockerfile must verify relative-worktree support by executing repair --relative-paths, not by grepping short help"
        )

    compat_script = read_required(LATEST_COMPAT_SCRIPT, "latest Hermes compatibility script")
    require(
        compat_script,
        (
            'nousresearch/hermes-agent:latest',
            '--target hermes-upstream-patched',
            '--target hermes-devkit-runtime',
            '--pull',
            '/usr/local/bin/git --version',
            'worktree.useRelativePaths',
            '/usr/local/bin/pnpm --version',
            'runtime-smoke',
            '22.23.2',
            'pnpm install --lockfile-only',
            'def _devkit_run_flow_model_transition',
            'MODEL_POLICY_SNAPSHOT_V1',
            'DEVKIT_TIRITH_PROFILE_GUARD_V1',
            '_devkit_tirith_subprocess_env',
            '_devkit_only_analysis_incomplete',
            '/opt/hermes/.venv/bin/hermes --help',
            '/opt/custom-skills/shared/dev-api-spec/SKILL.md',
            '/opt/custom-skills/shared/dev-node-dependencies/SKILL.md',
            '/opt/data/shared/scripts/flow_model_policy.py',
        ),
        "latest Hermes compatibility smoke",
    )

    compat_workflow = read_required(LATEST_COMPAT_WORKFLOW, "latest Hermes compatibility workflow")
    require(
        compat_workflow,
        (
            'name: Verify Latest Hermes Compatibility',
            '- dev',
            '- "fix/**"',
            '- "feat/**"',
            '- "feature/**"',
            '- "perf/**"',
            'latest Hermes update-devkit compatibility',
            'HERMES_BASE_IMAGE=nousresearch/hermes-agent:latest',
            'bash scripts/verify_latest_hermes_compat.sh',
        ),
        "latest Hermes compatibility workflow",
    )

    print("[PASS] DevKit updater + runtime verifier + latest Hermes CI + pinned Git/pnpm runtime + Tirith routed-profile compatibility contract verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
