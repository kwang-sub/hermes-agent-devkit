#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "update-devkit.ps1"


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


def main() -> int:
    if not UPDATER.is_file():
        raise SystemExit("update-devkit.ps1 is missing")

    text = UPDATER.read_text(encoding="utf-8-sig")

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

    print("[PASS] DevKit updater contract verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
