#!/usr/bin/env python3
"""Smoke-test the Hermes-native Kanban notification runtime.

The DevKit intentionally does not patch Discord formatting, add a custom
`registered` event, or inject session-affinity fields into notifications.
"""
from __future__ import annotations

from pathlib import Path


REQUIRED_EVENTS = {
    "completed",
    "blocked",
    "gave_up",
    "crashed",
    "timed_out",
    "review_requested",
    "changes_requested",
    "block_loop_detected",
}


def main() -> int:
    from gateway import kanban_watchers_notifier as notifier

    terminal = set(getattr(notifier, "TERMINAL_KINDS", ()))
    formatters = set(getattr(notifier, "_EVENT_FORMATTERS", {}).keys())
    missing_terminal = sorted(REQUIRED_EVENTS - terminal)
    missing_formatters = sorted(REQUIRED_EVENTS - formatters)
    if missing_terminal:
        raise SystemExit(f"native notifier missing terminal kinds: {missing_terminal}")
    if missing_formatters:
        raise SystemExit(f"native notifier missing event formatters: {missing_formatters}")

    source = Path(notifier.__file__).read_text(encoding="utf-8")
    forbidden = (
        "_devkit_discord_kanban_message(",
        "notification_session_context(",
    )
    found = [marker for marker in forbidden if marker in source]
    if found:
        raise SystemExit(f"DevKit notification patch markers remain in Hermes runtime: {found}")

    print("[PASS] Hermes native Kanban notification runtime contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
