#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


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


def main() -> int:
    if not UPDATER.is_file():
        raise SystemExit("update-devkit.ps1 is missing")

    text = UPDATER.read_text(encoding="utf-8-sig")

    require(
        text,
        (
            '#requires -Version 5.1',
            '[string]$Branch = "dev"',
            'git" -Arguments @("status", "--porcelain=v1"',
            'git" -Arguments @("fetch", "--prune", $Remote)',
            'git" -Arguments @("merge", "--ff-only", $RemoteRef)',
            '$ImageBuildInputs = @(',
            '"Dockerfile"',
            '"scripts/hermes-java"',
            '$ChangedFiles -contains "compose.yml"',
            'docker" -Arguments @("compose", "build")',
            'docker" -Arguments @("compose", "up", "-d", "--force-recreate")',
            'scripts\\verify-container-runtime.ps1',
            'Runtime verification failed. Performing one cached rebuild + force-recreate repair.',
            'sample.env changed. Existing .env is intentionally not overwritten',
            'init-profiles.ps1 changed. Profile initialization is intentionally not run automatically',
            'IMAGE_REBUILT=',
            'CONTAINER_RECREATED=',
            'AUTOMATIC_REPAIR_USED=',
        ),
        "update-devkit.ps1",
    )

    # Persistent auth/profile/session/Kanban state must never be destroyed by an
    # ordinary update. Local source must also never be rewritten automatically.
    forbid(
        text.lower(),
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

    if text.count('docker" -Arguments @("compose", "build")') < 2:
        raise SystemExit(
            "update-devkit.ps1 must keep both planned build and one repair build paths"
        )

    print("[PASS] DevKit updater contract verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
