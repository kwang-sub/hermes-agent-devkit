from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"
API_BASE_URL = "https://www.worksapis.com/v1.0"
DEFAULT_SCOPE = "bot.message"
TOKEN_REFRESH_MARGIN_SECONDS = 60


def _required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ValueError(f"missing environment variable: {name}")
    return value


def normalize_private_key(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    return value.replace("\\n", "\n")


def build_service_account_jwt(
    *, client_id: str, service_account: str, private_key: str, now: int | None = None
) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = {
        "iss": client_id,
        "sub": service_account,
        "iat": issued_at,
        "exp": issued_at + 3600,
    }
    return jwt.encode(payload, normalize_private_key(private_key), algorithm="RS256")


@dataclass
class AccessToken:
    value: str
    expires_at: float


class NaverWorksClient:
    def __init__(self, *, http_client: httpx.AsyncClient | None = None) -> None:
        self.client_id = _required("NAVER_WORKS_CLIENT_ID")
        self.client_secret = _required("NAVER_WORKS_CLIENT_SECRET")
        self.service_account = _required("NAVER_WORKS_SERVICE_ACCOUNT")
        self.private_key = _required("NAVER_WORKS_PRIVATE_KEY")
        self.bot_id = _required("NAVER_WORKS_BOT_ID")
        self.scope = (os.getenv("NAVER_WORKS_SCOPE") or DEFAULT_SCOPE).strip()
        self._http = http_client or httpx.AsyncClient(timeout=20.0)
        self._owns_http = http_client is None
        self._token: AccessToken | None = None

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def _access_token(self) -> str:
        now = time.time()
        if self._token and now < self._token.expires_at - TOKEN_REFRESH_MARGIN_SECONDS:
            return self._token.value

        assertion = build_service_account_jwt(
            client_id=self.client_id,
            service_account=self.service_account,
            private_key=self.private_key,
            now=int(now),
        )
        response = await self._http.post(
            TOKEN_URL,
            data={
                "assertion": assertion,
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": self.scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        token = str(data.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("NAVER WORKS token response did not contain access_token")
        expires_in = int(data.get("expires_in") or 3600)
        self._token = AccessToken(token, now + expires_in)
        return token

    async def send_text(self, channel_id: str, message: str) -> str | None:
        channel_id = channel_id.strip()
        if not channel_id:
            raise ValueError("NAVER WORKS channel id is empty")
        token = await self._access_token()
        response = await self._http.post(
            f"{API_BASE_URL}/bots/{self.bot_id}/channels/{channel_id}/messages",
            json={"content": {"type": "text", "text": message}},
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json() if response.content else {}
        return data.get("messageId") or data.get("message_id")
