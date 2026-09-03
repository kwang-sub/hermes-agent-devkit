from __future__ import annotations

import os
from typing import Any, Dict, Optional

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult

from .client import NaverWorksClient


def _configured() -> bool:
    required = (
        "NAVER_WORKS_CLIENT_ID",
        "NAVER_WORKS_CLIENT_SECRET",
        "NAVER_WORKS_SERVICE_ACCOUNT",
        "NAVER_WORKS_PRIVATE_KEY",
        "NAVER_WORKS_BOT_ID",
    )
    return all((os.getenv(name) or "").strip() for name in required)


def check_requirements() -> bool:
    return _configured()


def validate_config(config) -> bool:
    return _configured()


def _env_enablement() -> dict | None:
    if not _configured():
        return None
    seed: dict[str, Any] = {}
    home = (os.getenv("NAVER_WORKS_HOME_CHANNEL") or "").strip()
    if home:
        seed["home_channel"] = {"chat_id": home, "name": "NAVER WORKS"}
    return seed


class NaverWorksAdapter(BasePlatformAdapter):
    """Outbound-only NAVER WORKS platform adapter."""

    def __init__(self, config: PlatformConfig):
        super().__init__(config=config, platform=Platform("naverworks"))
        self._client: NaverWorksClient | None = None

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if not _configured():
            return False
        self._client = NaverWorksClient()
        self._mark_connected()
        return True

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
        self._mark_disconnected()

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        if self._client is None:
            return SendResult(success=False, error="NAVER WORKS adapter not connected")
        try:
            message_id = await self._client.send_text(chat_id, content)
            return SendResult(success=True, message_id=message_id or "sent")
        except Exception as exc:
            return SendResult(success=False, error=f"NAVER WORKS send failed: {type(exc).__name__}: {exc}")

    async def get_chat_info(self, chat_id: str):
        return {"name": chat_id, "type": "channel"}


async def _standalone_send(
    pconfig,
    chat_id: str,
    message: str,
    *,
    thread_id=None,
    media_files=None,
    force_document=False,
):
    client = NaverWorksClient()
    try:
        message_id = await client.send_text(chat_id, message)
        return {"success": True, "message_id": message_id or "sent"}
    except Exception as exc:
        return {"error": f"NAVER WORKS send failed: {type(exc).__name__}: {exc}"}
    finally:
        await client.close()


def register(ctx) -> None:
    ctx.register_platform(
        name="naverworks",
        label="NAVER WORKS",
        adapter_factory=lambda cfg: NaverWorksAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        required_env=[
            "NAVER_WORKS_CLIENT_ID",
            "NAVER_WORKS_CLIENT_SECRET",
            "NAVER_WORKS_SERVICE_ACCOUNT",
            "NAVER_WORKS_PRIVATE_KEY",
            "NAVER_WORKS_BOT_ID",
        ],
        env_enablement_fn=_env_enablement,
        cron_deliver_env_var="NAVER_WORKS_HOME_CHANNEL",
        standalone_sender_fn=_standalone_send,
        max_message_length=1800,
        platform_hint="NAVER WORKS outbound notification channel. Keep messages concise and text-only.",
        emoji="🟢",
    )
