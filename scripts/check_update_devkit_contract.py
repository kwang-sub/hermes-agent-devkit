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
INIT_PROFILES = ROOT / "init-profiles.ps1"
NOTIFIER_POLICY = ROOT / "docker/cont-init.d/019-devkit-kanban-notifier-policy"


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
            '$HermesBaseImage = "nousresearch/hermes-agent:latest"',
            '[switch]$SkipProfileInit',
            'git" -Arguments @("status", "--porcelain=v1"',
            'git" -Arguments @("fetch", "--prune", $Remote)',
            'git" -Arguments @("merge", "--ff-only", $RemoteRef)',
            '$ImageBuildInputs = @(',
            '"Dockerfile"',
            '"scripts/hermes-java"',
            'docker" -Arguments @("compose", "build", "--pull")',
            'docker" -Arguments @("compose", "up", "-d", "--force-recreate")',
            'function Invoke-ProfileInitialization',
            'init-profiles.ps1',
            'Profile/skill reconciliation',
            'PROFILES_RECONCILED=',
            'function Ensure-S6GatewayRuntimePermissions',
            'function Ensure-DefaultMultiplexGateway',
            'Ensure-S6GatewayRuntimePermissions -ContainerName $ContainerName',
            'Ensure-DefaultMultiplexGateway -ContainerName $Container',
            'chown hermes:hermes /run/service',
            'chown hermes:hermes "/run/service/.s6-svscan/$entry"',
            '".devkit-hermes-write-check"',
            '"exec", "--user", "root", $ContainerName',
            '"exec", "--user", "hermes", $ContainerName',
            '"/opt/hermes/.venv/bin/hermes", "gateway", "start"',
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

    if text.count("        Restart-UpdatedUpdater `") != 1:
        raise SystemExit(
            "update-devkit.ps1 must re-exec exactly once when its own file changes"
        )

    if text.count("Ensure-DefaultMultiplexGateway -ContainerName $Container") < 2:
        raise SystemExit(
            "update-devkit.ps1 must reconcile the default Gateway on both normal and repair paths"
        )

    if 'manager.register_profile_gateway("default", start_now=False)' in text:
        raise SystemExit(
            "update-devkit.ps1 must repair the upstream /run/service ownership contract "
            "instead of registering the default Gateway slot as root"
        )

    root_gateway_start = (
        '"exec", "--user", "root", $ContainerName,\n'
        '        "/opt/hermes/.venv/bin/hermes", "gateway", "start"'
    )
    if root_gateway_start in text:
        raise SystemExit(
            "update-devkit.ps1 may use root only for ephemeral s6 permission repair; "
            "the Hermes Gateway itself must start as user hermes"
        )

    require(
        text,
        (
            'function Restart-UpdatedUpdater',
            '[RESTART] update-devkit.ps1 changed during fast-forward',
            '-NoPull',
            '$ChangedFiles -contains "update-devkit.ps1"',
            '-ForceRebuildRequested:$ForceRebuild',
            '-NoRepairRequested:$NoRepair',
            '-SkipVerifyRequested:$SkipVerify',
            '-SkipProfileInitRequested:$SkipProfileInit',
            '-SkipGitHubAuthRequested:$SkipGitHubAuth',
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

    forbid(
        text,
        (
            '[string]$HermesBaseImage',
            '$env:HERMES_BASE_IMAGE =',
            '$PreviousHermesBaseImage',
        ),
        "update-devkit.ps1 fixed latest base-image contract",
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
            's6 dynamic Gateway scandir hermes-write contract',
            '".devkit-runtime-write-check"',
            'DevKit Kanban notifier service is running',
            'DevKit Kanban notifier ownership contract',
            'GATEWAY_MULTIPLEX_PROFILES=true',
            'Default multiplex Gateway service is running',
            '/run/service/gateway-default',
            'default_gateway_multiplexes',
            'recorded_served_profiles',
            '{"default", "coder", "orchestrator", "reviewer"}',
        ),
        "update-devkit runtime Git/Tirith/multiplex verification",
    )

    forbid(
        runtime_verifier,
        (
            '$(/usr/local/bin/git --version)',
            '$(/usr/local/bin/git config --system --bool --get worktree.useRelativePaths)',
            'HERMES_KANBAN_NOTIFY_PROFILE=orchestrator',
            '/run/service/gateway-orchestrator',
            'Orchestrator notification Gateway is running',
        ),
        "Windows PowerShell-safe runtime Git and fixed multiplex verification",
    )

    init_profiles = read_required(INIT_PROFILES, "init-profiles.ps1")
    require(
        init_profiles,
        (
            "function Ensure-KanbanNotificationOwnership",
            '"config", "set", "kanban.notify_in_gateway", "false"',
            '"config", "set", "kanban.auto_subscribe_on_create", "false"',
            "Ensure-KanbanNotificationOwnership",
        ),
        "DevKit Notification Bridge profile ownership",
    )

    notifier_policy = read_required(NOTIFIER_POLICY, "DevKit notifier boot policy")
    require(
        notifier_policy,
        (
            "kanban.notify_in_gateway false",
            "kanban.auto_subscribe_on_create false",
            'for profile_dir in /opt/data/profiles/*',
            'HERMES_KANBAN_NOTIFY_ENABLED controls only the bridge delivery loop',
            'devkit_kanban_notifier.py --initialize-state',
        ),
        "DevKit Notification Bridge boot ownership",
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
            'ARG HERMES_BASE_IMAGE=nousresearch/hermes-agent:latest',
            'FROM ${HERMES_BASE_IMAGE} AS hermes-upstream-patched',
            'FROM hermes-upstream-patched AS hermes-devkit-runtime',
            'ARG GIT_VERSION=2.55.0',
            'ARG PNPM_VERSION=12.5.1',
            'ENV PNPM_HOME=/opt/pnpm',
            'https://get.pnpm.io/install.sh',
            'PNPM_VERSION="$PNPM_VERSION"',
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
            'scripts/devkit_kanban_notifier.py /opt/devkit/bin/devkit_kanban_notifier.py',
            'docker/cont-init.d/019-devkit-kanban-notifier-policy',
            'docker/devkit-s6-rc.d/',
            '/opt/devkit/bin/devkit_kanban_notifier.py --self-test',
            '/opt/hermes/.venv/bin/hermes send --help',
            'patch_hermes_kanban_model_transition.py --self-test',
            "grep -q 'def _devkit_run_flow_model_transition' /opt/hermes/tools/kanban_tools.py",
            '/opt/hermes/.venv/bin/python -m py_compile',
        ),
        "Dockerfile latest-Hermes/Git compatibility stage",
    )

    forbid(
        dockerfile,
        (
            "patch_hermes_discord_kanban_notify.py",
            "patch_hermes_discord_kanban_session.py",
        ),
        "Dockerfile native Kanban notification contract",
    )

    for removed_notification_runtime in (
        ROOT / "scripts/patch_hermes_discord_kanban_notify.py",
        ROOT / "scripts/patch_hermes_discord_kanban_session.py",
        ROOT / "scripts/test_kanban_registered_runtime.py",
        ROOT / "shared/scripts/kanban_registration_event.py",
        ROOT / "shared/scripts/test_kanban_registration_event.py",
        ROOT / "shared/scripts/kanban_notify_subscribe.py",
        ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/scripts/subscribe_notification.py",
        ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py",
        ROOT / "scripts/test_native_kanban_notification_runtime.py",
    ):
        if removed_notification_runtime.exists():
            raise SystemExit(
                "obsolete DevKit notification runtime patch/test must be removed: "
                + str(removed_notification_runtime.relative_to(ROOT))
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
            '/opt/devkit/bin/devkit_kanban_notifier.py --self-test',
            '/opt/hermes/.venv/bin/hermes send --help',
            '/etc/s6-overlay/s6-rc.d/devkit-notifier/run',
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

    print("[PASS] DevKit updater + runtime verifier + Notification Bridge + latest Hermes CI + pinned Git/pnpm runtime + Tirith routed-profile compatibility contract verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
