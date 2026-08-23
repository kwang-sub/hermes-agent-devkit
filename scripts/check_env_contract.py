#!/usr/bin/env python3
"""Verify the public environment contract without reading the real .env file."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample.env"
COMPOSE = ROOT / "compose.yml"
INIT = ROOT / "init-profiles.ps1"

DEFAULTS = {
    "HERMES_COMPOSE_PROJECT_NAME": "hermes-dev",
    "HERMES_CONTAINER_NAME": "hermes-dev",
    "HERMES_IMAGE_NAME": "hermes-dev",
    "HERMES_IMAGE_TAG": "0.1.0",
    "HERMES_DATA_VOLUME_NAME": "hermes-dev-data",
    "HERMES_HOST_WORKSPACE_PATH": "D:/workspace",
    "HERMES_CONTAINER_WORKSPACE_PATH": "/workspace",
    "HERMES_HOST_CUSTOM_SKILLS_PATH": "./custom-skills",
    "HERMES_CONTAINER_CUSTOM_SKILLS_PATH": "/opt/custom-skills",
    "HERMES_HOST_SHARED_PATH": "./shared",
    "HERMES_CONTAINER_SHARED_PATH": "/opt/data/shared",
    "HERMES_PORT_BIND_ADDRESS": "127.0.0.1",
    "HERMES_DASHBOARD_HOST_PORT": "9119",
    "HERMES_DASHBOARD_CONTAINER_PORT": "9119",
    "HERMES_GATEWAY_HOST_PORT": "8642",
    "HERMES_GATEWAY_CONTAINER_PORT": "8642",
    "HERMES_TIMEZONE": "Asia/Seoul",
    "JIRA_API_VERSION": "3",
    "JIRA_ACCEPTANCE_CRITERIA_FIELDS": "Acceptance Criteria",
    "JIRA_INCLUDE_FIELD_NAMES": "",
    "JIRA_VERIFY_SSL": "true",
    "HERMES_WORK_ITEM_DIR": "/opt/data/work-items",
}

SENSITIVE_SAMPLE_KEYS = {
    "HERMES_DASHBOARD_USERNAME",
    "HERMES_DASHBOARD_PASSWORD",
    "HERMES_DASHBOARD_SECRET",
    "JIRA_BASE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
}
REQUIRED_SAMPLE_KEYS = set(DEFAULTS) | SENSITIVE_SAMPLE_KEYS

INIT_DEFAULTS = {
    key: value
    for key, value in DEFAULTS.items()
    if key
    in {
        "HERMES_CONTAINER_NAME",
        "HERMES_CONTAINER_WORKSPACE_PATH",
        "HERMES_CONTAINER_CUSTOM_SKILLS_PATH",
        "HERMES_CONTAINER_SHARED_PATH",
    }
}


def parse_sample() -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw_line in enumerate(SAMPLE.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        if not match:
            raise SystemExit(f"sample.env:{number}: expected KEY=VALUE")
        key, value = match.groups()
        if key in values:
            raise SystemExit(f"sample.env:{number}: duplicate key {key}")
        values[key] = value
    return values


def render_compose_vars(text: str, overrides: dict[str, str]) -> str:
    """Render defaulted Compose variables for a secret-free contract fixture."""

    def replace(match: re.Match[str]) -> str:
        key, default = match.groups()
        return overrides.get(key, default)

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*):-([^}]*)}", replace, text)


def main() -> int:
    if not SAMPLE.is_file():
        raise SystemExit("missing canonical sample.env")
    if (ROOT / "smaple.env").exists():
        raise SystemExit("deprecated typo file smaple.env must not exist")

    sample = parse_sample()
    missing = sorted(REQUIRED_SAMPLE_KEYS - sample.keys())
    if missing:
        raise SystemExit(f"sample.env missing keys: {', '.join(missing)}")
    populated_credentials = sorted(key for key in SENSITIVE_SAMPLE_KEYS if sample[key])
    if populated_credentials:
        raise SystemExit(
            "sample.env credential fields must stay blank: "
            + ", ".join(populated_credentials)
        )

    compose = COMPOSE.read_text(encoding="utf-8")
    for key, default in DEFAULTS.items():
        reference = "${" + key + ":-" + default + "}"
        if reference not in compose:
            raise SystemExit(f"compose.yml missing defaulted reference: {reference}")
    if re.search(r"^\s*source:\s*D:/workspace\s*$", compose, re.MULTILINE):
        raise SystemExit("compose.yml still hardcodes D:/workspace as a volume source")
    if "HERMES_CONTAINER_DATA_PATH" in compose or "HERMES_CONTAINER_DATA_PATH" in sample:
        raise SystemExit("unsupported container data path must not be public configuration")
    if not re.search(r"^\s*target:\s*/opt/data\s*$", compose, re.MULTILINE):
        raise SystemExit("compose.yml must keep the official image data target /opt/data")

    port_fixture = render_compose_vars(
        compose,
        {
            "HERMES_DASHBOARD_CONTAINER_PORT": "19119",
            "HERMES_GATEWAY_CONTAINER_PORT": "18642",
        },
    )
    for expected in (
        "HERMES_DASHBOARD_PORT: 19119",
        "API_SERVER_PORT: 18642",
        '"127.0.0.1:9119:19119"',
        '"127.0.0.1:8642:18642"',
        "('127.0.0.1', 18642)",
    ):
        if expected not in port_fixture:
            raise SystemExit(
                "compose.yml does not connect non-default container ports to "
                f"listener/publish/healthcheck contract: {expected}"
            )

    init = INIT.read_text(encoding="utf-8-sig")
    if 'Get-EnvOrDefault -Name "HERMES_CONTAINER_DATA_PATH"' in init:
        raise SystemExit("init-profiles.ps1 must keep the official /opt/data runtime path")
    for key, default in INIT_DEFAULTS.items():
        pattern = (
            r'Get-EnvOrDefault\s+-Name\s+"'
            + re.escape(key)
            + r'"\s+-Default\s+"'
            + re.escape(default)
            + r'"'
        )
        if not re.search(pattern, init):
            raise SystemExit(f"init-profiles.ps1 missing env/default contract for {key}")
    for required_term in ("Import-DotEnv", "Get-EnvOrDefault", "EnvSelfTest"):
        if required_term not in init:
            raise SystemExit(f"init-profiles.ps1 missing helper: {required_term}")

    print(f"[PASS] env contract verified ({len(REQUIRED_SAMPLE_KEYS)} public keys)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
