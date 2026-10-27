#!/usr/bin/env python3
"""UpdateKit regression: default-only Lite boot while retaining Git/Docker data safety."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def read(path):
    f = ROOT / path
    if not f.is_file():
        raise SystemExit(f"missing required file: {path}")
    return f.read_text(encoding="utf-8-sig")


def require(text, terms, label):
    missing = [s for s in terms if s not in text]
    if missing:
        raise SystemExit(f"{label}: missing {missing}")


def main():
    upd = read("update-devkit.ps1")
    init = read("init-lite.ps1")
    compose = read("compose.yml")
    verifier = read("scripts/verify-container-runtime.ps1")
    gateway = read("scripts/devkit_gateway_readiness.py")
    require(upd, (
        "#requires -Version 5.1",
        '[string]$Branch = "dev"',
        '$HermesBaseImage = "nousresearch/hermes-agent:latest"',
        'git" -Arguments @("status", "--porcelain=v1"',
        'git" -Arguments @("fetch", "--prune", $Remote)',
        'git" -Arguments @("merge", "--ff-only", $RemoteRef)',
        '"compose", "build", "--pull"',
        '"compose", "up", "-d", "--force-recreate"',
        'function Restart-UpdatedUpdater',
        'function Invoke-LiteInitialization',
        '"init-lite.ps1"',
        'Invoke-LiteInitialization -Initializer $ProfileInitializer -ContainerName $Container',
        "LITE_DEFAULT_RECONCILED=",
        'Initialize-GitPublishing',
        "AUTOMATIC_REPAIR_USED=",
    ), "Lite updater")
    if "init-profiles.ps1" in upd:
        raise SystemExit("updater still references deprecated role profile initializer")
    if upd.count("Invoke-LiteInitialization -Initializer $ProfileInitializer -ContainerName $Container") != 2:
        raise SystemExit("Lite reconciliation must run on normal and repair paths")
    if upd.count('"compose", "build", "--pull"') != 1:
        raise SystemExit("repair must not pull latest again")
    require(init, (
        "ArchiveLegacyProfiles", "DryRun", "scripts/lite_default_profile.py",
        "scripts/lite_mode.py", "ConvertFrom-Json", '"/opt/data"',
        '"/tmp/devkit-lite-default-profile.py"',
        '"exec", "--user", "hermes"',
    ), "Lite initialization")
    for forbidden in ("git reset", "git clean", "git stash",
                      "docker volume rm", "docker compose down -v"):
        if forbidden in upd or forbidden in init:
            raise SystemExit("Unsafe updater action: " + forbidden)
    require(compose, (
        "nousresearch/hermes-agent:latest",
        'HERMES_KANBAN_BOOT_RECOVERY_ENABLED: "false"',
        'source: hermes-data', 'target: /opt/data',
        'GATEWAY_MULTIPLEX_PROFILES: "true"',
    ), "Persistent runtime")
    require(gateway, (
        'REQUIRED = frozenset(("default",))',
        'NO_VERIFIED_LIVE_GATEWAY',
    ), "Live default gateway")
    require(verifier, (
        "Default Lite Gateway served-profile contract",
        "Default Lite skill/profile contract",
        "/opt/data/config.yaml", "/opt/custom-skills/lite",
        "dev-lite-session",
    ), "Lite runtime verification")
    if 'Profile skill/toolset contract: $Profile' in verifier:
        raise SystemExit("Legacy role profile contract still required by runtime verifier")
    print("[PASS] DevKit Lite-only update, Gateway, and persistent Docker safety contract")


if __name__ == "__main__":
    main()
