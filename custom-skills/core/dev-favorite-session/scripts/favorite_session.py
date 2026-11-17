#!/usr/bin/env python3
"""Hermes session bookmarks using native `hermes sessions pin|pinned|unpin|rename`.

No private session database, transcript mutation, or process-relaunch hooks.
All output is one JSON object; writes require an explicit operation and identity.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

SESSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
MAX_TITLE_CHARS = 100
MAX_OUTPUT_CHARS = 240
DEFAULT_LIMIT = 2
MAX_LIMIT = 4


class FavoriteError(Exception):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def validate_session_id(value: str) -> str:
    value = str(value or "").strip()
    if not SESSION_ID_RE.fullmatch(value):
        raise FavoriteError("invalid_session_id", "유효하지 않은 세션 ID입니다.")
    return value


def validate_title(value: str) -> str:
    value = str(value or "")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise FavoriteError("invalid_title", "타이틀에 제어 문자나 개행을 사용할 수 없습니다.")
    # Match Hermes SessionDB's whitespace-collapse behavior for exact read-back.
    value = re.sub(r" +", " ", value.strip())
    if any(char in value for char in ("\u200b", "\u200c", "\u200d", "\ufeff", "\u202e")):
        raise FavoriteError("invalid_title", "보이지 않는 제어 문자가 포함된 타이틀은 사용할 수 없습니다.")
    if not value or len(value) > MAX_TITLE_CHARS:
        raise FavoriteError("invalid_title", f"타이틀은 1~{MAX_TITLE_CHARS}자로 입력해야 합니다.")
    return value


def error_text(output: str) -> str:
    """Bound operational error text; never echo the entire process environment."""
    cleaned = " ".join(str(output or "").split())[:MAX_OUTPUT_CHARS]
    # Never print obvious credential assignments from an upstream CLI diagnostic.
    return re.sub(r"(?i)(\b(?:token|password|api[-_]?key|secret)\s*[:=]\s*)\S+", r"\1[REDACTED]", cleaned)


@dataclass(frozen=True)
class PinnedSession:
    id: str
    title: str
    source: str
    last_active: Any
    message_count: Any

    @classmethod
    def from_json(cls, row: dict) -> "PinnedSession":
        if not isinstance(row, dict):
            raise FavoriteError("invalid_hermes_response", "즐겨찾기 항목 형식이 잘못되었습니다.")
        session_id = validate_session_id(row.get("id", ""))
        title = row.get("title")
        if title is not None and not isinstance(title, str):
            raise FavoriteError("invalid_hermes_response", "Hermes의 세션 제목 형식이 잘못되었습니다.")
        return cls(
            id=session_id,
            title=title or "",
            source=str(row.get("source") or ""),
            last_active=row.get("last_active"),
            message_count=row.get("message_count"),
        )

    def as_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "last_active": self.last_active,
            "message_count": self.message_count,
        }


class HermesCli:
    """Thin native CLI adapter; avoid shell invocation and direct state.db writes."""

    def __init__(self, binary: str | None = None):
        self.binary = binary or os.environ.get("HERMES_CLI_BIN") or (
            "/opt/hermes/.venv/bin/hermes" if Path("/opt/hermes/.venv/bin/hermes").is_file()
            else shutil.which("hermes")
        )
        if not self.binary:
            raise FavoriteError("hermes_not_found", "Hermes CLI 실행 파일을 찾을 수 없습니다.")

    def _run(self, *parts: str) -> str:
        cmd = [self.binary, "sessions", *parts]
        try:
            p = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise FavoriteError("hermes_command_failed", f"Hermes CLI 호출 실패: {type(exc).__name__}") from exc
        if p.returncode != 0:
            detail = error_text(p.stderr or p.stdout)
            raise FavoriteError("hermes_command_failed", f"Hermes 명령 실패: {detail or 'exit ' + str(p.returncode)}")
        return p.stdout

    def pinned(self) -> list[PinnedSession]:
        raw = self._run("pinned", "--json")
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FavoriteError("invalid_hermes_response", "Hermes pinned --json 결과가 JSON이 아닙니다.") from exc
        if not isinstance(rows, list):
            raise FavoriteError("invalid_hermes_response", "Hermes pinned --json 결과는 배열이어야 합니다.")
        parsed = [PinnedSession.from_json(row) for row in rows]
        if len({row.id for row in parsed}) != len(parsed):
            raise FavoriteError("invalid_hermes_response", "중복된 세션 ID가 반환되었습니다.")
        return parsed

    def pin(self, session_id: str) -> None:
        self._run("pin", validate_session_id(session_id))

    def unpin(self, session_id: str) -> None:
        self._run("unpin", validate_session_id(session_id))

    def rename(self, session_id: str, title: str) -> None:
        # `--` terminates argparse option processing when a title begins with '-' .
        self._run("rename", validate_session_id(session_id), "--", validate_title(title))


def _by_id(rows: list[PinnedSession], session_id: str) -> PinnedSession | None:
    return next((row for row in rows if row.id == session_id), None)


def _safe_unpin_rollback(cli: HermesCli, session_id: str) -> str | None:
    try:
        cli.unpin(session_id)
        # Validate the pin really is absent, rather than claiming rollback when it failed silently.
        if _by_id(cli.pinned(), session_id):
            return "Pin 해제 검증 실패"
        return None
    except FavoriteError as exc:
        return f"Pin 해제 실패: {exc}"


def register(cli: HermesCli, session_id: str, title: str) -> dict[str, Any]:
    """Pin before optional rename so an already-identical title is a valid no-op.

    If rename fails for a newly pinned row, restore the previous unpinned state.
    Existing pins are never removed on a title conflict.
    """
    session_id, title = validate_session_id(session_id), validate_title(title)
    before = cli.pinned()
    original = _by_id(before, session_id)
    newly_pinned = original is None
    if newly_pinned:
        cli.pin(session_id)
    renamed_committed = False
    try:
        pinned = _by_id(cli.pinned(), session_id)
        if not pinned:
            raise FavoriteError(
                "pin_not_visible", "Pin 이후 세션 ID가 목록에 나타나지 않았습니다. "
                "압축으로 세션 ID가 바뀐 경우 현재 세션 ID로 다시 실행하세요.")
        renamed = pinned.title != title
        if renamed:
            cli.rename(session_id, title)
            renamed_committed = True
        updated = _by_id(cli.pinned(), session_id)
        if not updated or updated.title != title:
            raise FavoriteError("pin_verify_failed", "Pin 또는 제목 변경 결과를 확인하지 못했습니다.")
        return {"ok": True, "action": "register", "session": updated.as_json(),
                "pin_added": newly_pinned, "title_updated": renamed}
    except FavoriteError as exc:
        rollback_error = _safe_unpin_rollback(cli, session_id) if newly_pinned else None
        if rollback_error or renamed_committed:
            reason = f" — 기존 Pin 상태 복구 실패: {rollback_error}" if rollback_error else ""
            raise FavoriteError(
                "partial_failure", f"{exc}{reason} — 제목/Pin 상태 재확인이 필요합니다.",
                details={"session_id": session_id, "verify_manually": True}) from exc
        raise


def list_pins(cli: HermesCli, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    if offset < 0 or not (1 <= limit <= MAX_LIMIT):
        raise FavoriteError("invalid_pagination", f"offset은 0 이상, limit는 1~{MAX_LIMIT}여야 합니다.")
    rows = cli.pinned()
    page = rows[offset:offset + limit]
    return {"ok": True, "action": "list", "total": len(rows), "offset": offset,
            "limit": limit, "has_previous": offset > 0,
            "has_more": offset + len(page) < len(rows),
            "sessions": [row.as_json() for row in page]}


def prepare_resume(cli: HermesCli, *, session_id: str | None, title: str | None) -> dict[str, Any]:
    rows = cli.pinned()
    if bool(session_id) == bool(title):
        raise FavoriteError("invalid_input", "session-id 또는 title 중 하나만 지정해야 합니다.")
    if session_id:
        candidate = _by_id(rows, validate_session_id(session_id))
        if not candidate:
            raise FavoriteError("not_pinned", "해당 세션이 즐겨찾기 목록에 없습니다.")
    else:
        query = validate_title(title or "")
        exact = [row for row in rows if row.title == query]
        folded = [row for row in rows if row.title.casefold() == query.casefold()]
        prefix = [row for row in rows if row.title.casefold().startswith(query.casefold())]
        matches = exact or folded or prefix
        if not matches:
            raise FavoriteError("not_found", f"타이틀 '{query}'에 일치하는 즐겨찾기가 없습니다.")
        if len(matches) != 1:
            raise FavoriteError("ambiguous_title", "일치하는 즐겨찾기가 여러 개입니다. 정확한 제목을 입력하세요.",
                                details={"candidates": [row.as_json() for row in matches[:10]]})
        candidate = matches[0]
    return {"ok": True, "action": "prepare-resume", "session": candidate.as_json(),
            "resume_slash": "/resume " + candidate.id,
            "note": "스킬 응답이 끝난 뒤 Hermes 입력창에 resume_slash를 입력하세요. "
                    "스킬 도구 호출만으로 실행 중인 대화를 전환할 수는 없습니다."}


def remove_pin(cli: HermesCli, session_id: str, *, expected_title: str, confirmed: bool) -> dict[str, Any]:
    if not confirmed:
        raise FavoriteError("confirmation_required", "즐겨찾기 해제는 확인 UI에서 승인한 뒤 실행해야 합니다.")
    session_id = validate_session_id(session_id)
    if expected_title:
        expected_title = validate_title(expected_title)
    current = _by_id(cli.pinned(), session_id)
    if current is None:
        raise FavoriteError("not_pinned", "이미 즐겨찾기에서 해제됐거나 세션을 찾을 수 없습니다.")
    if current.title != expected_title:
        raise FavoriteError("session_changed", "선택 이후 제목이 바뀌었습니다. 목록을 갱신하고 다시 확인하세요.")
    cli.unpin(session_id)
    if _by_id(cli.pinned(), session_id):
        raise FavoriteError("unpin_verify_failed", "즐겨찾기 해제 여부를 검증하지 못했습니다.")
    return {"ok": True, "action": "remove", "session": current.as_json(),
            "conversation_deleted": False}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hermes-native session bookmarks")
    parser.add_argument("--hermes-bin", default=None,
                        help="Hermes CLI path, default: /opt/hermes/.venv/bin/hermes or PATH")
    sub = parser.add_subparsers(dest="action", required=True)
    register_parser = sub.add_parser("register", help="Title and pin the current session")
    register_parser.add_argument("--session-id", required=True)
    register_parser.add_argument("--title", required=True)
    list_parser = sub.add_parser("list", help="List only pinned sessions")
    list_parser.add_argument("--offset", type=int, default=0)
    list_parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    resume_parser = sub.add_parser("prepare-resume", help="Resolve a pinned ID/title to /resume")
    resume_target = resume_parser.add_mutually_exclusive_group(required=True)
    resume_target.add_argument("--session-id")
    resume_target.add_argument("--title")
    remove_parser = sub.add_parser("remove", help="Unpin, never delete, an explicitly confirmed session")
    remove_parser.add_argument("--session-id", required=True)
    remove_parser.add_argument("--expected-title", required=True)
    remove_parser.add_argument("--confirmed", action="store_true")
    return parser


def dispatch(args: argparse.Namespace, cli: HermesCli) -> dict[str, Any]:
    if args.action == "register":
        return register(cli, args.session_id, args.title)
    if args.action == "list":
        return list_pins(cli, offset=args.offset, limit=args.limit)
    if args.action == "prepare-resume":
        return prepare_resume(cli, session_id=args.session_id, title=args.title)
    if args.action == "remove":
        return remove_pin(cli, args.session_id, expected_title=args.expected_title,
                          confirmed=args.confirmed)
    raise FavoriteError("invalid_action", "지원하지 않는 동작입니다.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = dispatch(args, HermesCli(args.hermes_bin))
    except FavoriteError as exc:
        result = {"ok": False, "code": exc.code, "message": str(exc), **exc.details}
        print(json.dumps(result, ensure_ascii=False))
        return 1
    except Exception as exc:
        # Do not leak stack traces/session content on an unexpected failure.
        print(json.dumps({"ok": False, "code": "unexpected_error",
                          "message": f"예상치 못한 오류: {type(exc).__name__}"}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
