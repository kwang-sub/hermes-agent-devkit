#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


BOARD_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
DEFAULT_TIMEOUT_SECONDS = 15


class InventoryError(RuntimeError):
    pass


def _int_or_zero(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def parse_board_payload(raw: str) -> tuple[list[dict[str, Any]], str | None]:
    text = raw.strip()
    if not text:
        raise InventoryError("board inventory command returned empty output")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InventoryError(f"board inventory command returned invalid JSON: {exc}") from exc

    if isinstance(payload, list):
        boards = payload
        current = None
    elif isinstance(payload, dict):
        raw_boards = payload.get("boards")
        if not isinstance(raw_boards, list):
            raise InventoryError("board inventory JSON must contain a boards array")
        boards = raw_boards
        raw_current = payload.get("current")
        current = str(raw_current).strip().lower() if raw_current else None
    else:
        raise InventoryError("board inventory JSON root must be an object or array")

    typed = [item for item in boards if isinstance(item, dict)]
    return typed, current


def normalize_boards(
    raw_boards: list[dict[str, Any]],
    current: str | None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in raw_boards:
        if bool(item.get("archived")):
            continue

        slug = str(item.get("slug") or "").strip().lower()
        if not slug or not BOARD_SLUG_RE.fullmatch(slug) or slug in seen:
            continue

        seen.add(slug)
        name = str(item.get("name") or slug).strip() or slug
        counts = item.get("counts") if isinstance(item.get("counts"), dict) else {}
        blocked_count = _int_or_zero(counts.get("blocked"))
        if item.get("total") is None:
            total = sum(
                _int_or_zero(value)
                for status, value in counts.items()
                if str(status) != "archived"
            )
        else:
            total = _int_or_zero(item.get("total"))

        is_current = bool(item.get("is_current")) or (current is not None and slug == current)
        normalized.append(
            {
                "slug": slug,
                "name": name,
                "is_current": is_current,
                "blocked_count": blocked_count,
                "total": total,
            }
        )

    normalized.sort(
        key=lambda row: (
            0 if row["is_current"] else 1,
            str(row["name"]).casefold(),
            str(row["slug"]),
        )
    )
    return normalized


def resolve_hermes_binary(explicit: str | None) -> str:
    if explicit:
        return str(Path(explicit).expanduser())

    configured = os.getenv("HERMES_CLI", "").strip()
    if configured:
        return configured

    found = shutil.which("hermes")
    if found:
        return found

    fallback = Path("/opt/hermes/.venv/bin/hermes")
    if fallback.is_file():
        return str(fallback)

    raise InventoryError("Hermes CLI executable is unavailable")


def collect_inventory(hermes_binary: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [hermes_binary, "kanban", "boards", "list", "--json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InventoryError(f"failed to read Hermes board inventory: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise InventoryError(
            "Hermes board inventory command failed"
            + (f": {detail}" if detail else "")
        )

    raw_boards, current = parse_board_payload(result.stdout)
    boards = normalize_boards(raw_boards, current)
    return {
        "status": "pass",
        "source": "hermes kanban boards list --json",
        "current": current,
        "count": len(boards),
        "boards": boards,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read live Hermes Kanban boards for the Task Recovery Gate 1."
    )
    parser.add_argument(
        "--hermes-bin",
        help="Hermes executable override; intended mainly for bounded runtime tests.",
    )
    args = parser.parse_args()

    try:
        binary = resolve_hermes_binary(args.hermes_bin)
        inventory = collect_inventory(binary)
        print(json.dumps(inventory, ensure_ascii=False, sort_keys=True))
        return 0
    except InventoryError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blocker": "BOARD_INVENTORY_UNAVAILABLE",
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
