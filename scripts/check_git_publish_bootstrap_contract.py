#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "update-devkit.ps1"
COMPOSE = ROOT / "compose.yml"
SAMPLE_ENV = ROOT / "sample.env"
PR_PUBLISH_LIB = ROOT / "custom-skills/orchestrator/dev-pr-publish/scripts/pr_publish_lib.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"[FAIL] missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8-sig")


def require(text: str, terms: tuple[str, ...], label: str) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"[FAIL] {label} missing: {', '.join(missing)}")


def forbid(text: str, terms: tuple[str, ...], label: str) -> None:
    present = [term for term in terms if term in text]
    if present:
        raise SystemExit(f"[FAIL] {label} contains forbidden terms: {', '.join(present)}")


def run_git(args: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"[FAIL] git {' '.join(args)} failed ({result.returncode})\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout.strip()


def verify_profile_home_independent_global_config() -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-git-config-") as temp_dir:
        root = Path(temp_dir)
        global_config = root / "gitconfig"
        home_a = root / "profile-a"
        home_b = root / "profile-b"
        home_a.mkdir()
        home_b.mkdir()

        base_env = os.environ.copy()
        base_env["GIT_CONFIG_GLOBAL"] = str(global_config)

        env_a = dict(base_env)
        env_a["HOME"] = str(home_a)
        run_git(["config", "--global", "user.name", "DevKit Test"], env_a)
        run_git(["config", "--global", "user.email", "devkit@example.invalid"], env_a)

        env_b = dict(base_env)
        env_b["HOME"] = str(home_b)
        name = run_git(["config", "--global", "--get", "user.name"], env_b)
        email = run_git(["config", "--global", "--get", "user.email"], env_b)

        if name != "DevKit Test" or email != "devkit@example.invalid":
            raise SystemExit(
                "[FAIL] GIT_CONFIG_GLOBAL did not survive routed-profile HOME isolation: "
                f"name={name!r}, email={email!r}"
            )


def main() -> int:
    updater = read(UPDATER)
    compose = read(COMPOSE)
    sample = read(SAMPLE_ENV)
    library = read(PR_PUBLISH_LIB)

    require(
        updater,
        (
            '[switch]$SkipGitHubAuth',
            'function Get-ContainerEnvValue',
            'function Test-GitHubAuthentication',
            'function Initialize-GitPublishing',
            'HERMES_GIT_USER_NAME',
            'HERMES_GIT_USER_EMAIL',
            'GH_CONFIG_DIR',
            '"config", "--global", "user.name"',
            '"config", "--global", "user.email"',
            'gh auth status --hostname github.com',
            '"auth", "login"',
            '"--git-protocol", "https"',
            '"--web"',
            'Git publish identity/auth bootstrap',
            'GIT_IDENTITY_CONFIGURED=',
            'GITHUB_AUTH_READY=',
        ),
        "update-devkit Git publish bootstrap",
    )

    require(
        compose,
        (
            'HERMES_GIT_USER_NAME: ${HERMES_GIT_USER_NAME:-}',
            'HERMES_GIT_USER_EMAIL: ${HERMES_GIT_USER_EMAIL:-}',
            'HERMES_GIT_CONFIG_GLOBAL: ${HERMES_GIT_CONFIG_GLOBAL:-/opt/data/gitconfig}',
            'GIT_CONFIG_GLOBAL: ${HERMES_GIT_CONFIG_GLOBAL:-/opt/data/gitconfig}',
            'HERMES_GH_CONFIG_DIR: ${HERMES_GH_CONFIG_DIR:-/opt/data/gh}',
            'GH_CONFIG_DIR: ${HERMES_GH_CONFIG_DIR:-/opt/data/gh}',
        ),
        "compose Git publish environment",
    )

    require(
        sample,
        (
            'HERMES_GIT_USER_NAME=',
            'HERMES_GIT_USER_EMAIL=',
            'HERMES_GIT_CONFIG_GLOBAL=/opt/data/gitconfig',
            'HERMES_GH_CONFIG_DIR=/opt/data/gh',
            'GitHub 인증 토큰은 .env에 넣지 않습니다.',
        ),
        "sample.env Git publish configuration",
    )

    require(
        library,
        (
            'HERMES_GH_CONFIG_DIR',
            '"/opt/data/gh"',
            'gh authentication is not ready',
        ),
        "dev-pr-publish persistent gh auth contract",
    )

    forbid(
        sample,
        (
            'GH_TOKEN=',
            'GITHUB_TOKEN=',
            'GITHUB_PAT=',
        ),
        "sample.env secret policy",
    )
    forbid(
        updater,
        (
            'gh auth login --with-token',
            'GH_TOKEN=',
            'GITHUB_TOKEN=',
        ),
        "update-devkit GitHub auth policy",
    )

    verify_profile_home_independent_global_config()

    print(
        "[PASS] Git publish bootstrap: persistent profile-independent global Git config + "
        ".env identity + persistent gh auth contract verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
