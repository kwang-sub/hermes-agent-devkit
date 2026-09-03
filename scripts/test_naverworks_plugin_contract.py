#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "platforms" / "naverworks"


def require(text: str, terms: tuple[str, ...], label: str) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"[FAIL] {label}: missing {', '.join(missing)}")


def main() -> int:
    manifest = (PLUGIN / "plugin.yaml").read_text(encoding="utf-8")
    adapter = (PLUGIN / "adapter.py").read_text(encoding="utf-8")
    client = (PLUGIN / "client.py").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
    sample = (ROOT / "sample.env").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "kanban-notifications.md").read_text(encoding="utf-8")

    ast.parse(adapter)
    ast.parse(client)

    require(manifest, (
        "kind: platform", "NAVER_WORKS_CLIENT_ID", "NAVER_WORKS_PRIVATE_KEY",
        "NAVER_WORKS_BOT_ID", "NAVER_WORKS_HOME_CHANNEL",
    ), "plugin.yaml")
    require(adapter, (
        'name="naverworks"', "adapter_factory", "env_enablement_fn=_env_enablement",
        'cron_deliver_env_var="NAVER_WORKS_HOME_CHANNEL"',
        "standalone_sender_fn=_standalone_send", "NaverWorksAdapter",
    ), "adapter.py")
    require(client, (
        "https://auth.worksmobile.com/oauth2/v2.0/token",
        "https://www.worksapis.com/v1.0",
        "urn:ietf:params:oauth:grant-type:jwt-bearer",
        '"iss": client_id', '"sub": service_account',
        "serialization.load_pem_private_key", "padding.PKCS1v15()", "hashes.SHA256()",
        '"content": {"type": "text", "text": message}',
    ), "client.py")
    require(dockerfile, (
        "COPY plugins/platforms/naverworks /opt/hermes/plugins/platforms/naverworks",
    ), "Dockerfile")
    require(compose, (
        "NAVER_WORKS_CLIENT_ID:", "NAVER_WORKS_CLIENT_SECRET:",
        "NAVER_WORKS_SERVICE_ACCOUNT:", "NAVER_WORKS_PRIVATE_KEY:",
        "NAVER_WORKS_BOT_ID:", "NAVER_WORKS_HOME_CHANNEL: ${HERMES_KANBAN_NOTIFY_TARGET:-}",
    ), "compose.yml")
    require(sample, (
        "HERMES_KANBAN_NOTIFY_PLATFORM=discord", "NAVER_WORKS_CLIENT_ID=",
        "NAVER_WORKS_PRIVATE_KEY=", "NAVER_WORKS_SCOPE=bot.message",
    ), "sample.env")
    require(docs, (
        "HERMES_KANBAN_NOTIFY_PLATFORM=naverworks", "NAVER_WORKS_PRIVATE_KEY",
        "NOTIFY_STATUS=subscribed",
    ), "kanban notification docs")

    print("[PASS] NAVER WORKS platform plugin contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
