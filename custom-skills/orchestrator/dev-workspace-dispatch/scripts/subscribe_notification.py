#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

TRUE_VALUES = {"1", "true", "yes", "on"}
ALLOWED_DELIVERY_MODES = {"notify", "wake", "notify+wake"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Subscribe a Kanban task to optional gateway notifications.")
    parser.add_argument("--task-id", required=True)
    return parser.parse_args()


def enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUE_VALUES


def hermes_cli() -> str:
    override = os.getenv("HERMES_CLI")
    if override:
        return override
    return shutil.which("hermes") or "/usr/local/bin/hermes"


def main() -> int:
    args = parse_args()
    if not enabled(os.getenv("HERMES_KANBAN_NOTIFY_ENABLED")):
        print("NOTIFY_STATUS=disabled")
        return 0

    platform = (os.getenv("HERMES_KANBAN_NOTIFY_PLATFORM") or "").strip()
    target = (os.getenv("HERMES_KANBAN_NOTIFY_TARGET") or "").strip()
    delivery_mode = (os.getenv("HERMES_KANBAN_NOTIFY_DELIVERY_MODE") or "notify").strip()
    chat_type = (os.getenv("HERMES_KANBAN_NOTIFY_CHAT_TYPE") or "").strip()

    missing = [name for name, value in (("HERMES_KANBAN_NOTIFY_PLATFORM", platform), ("HERMES_KANBAN_NOTIFY_TARGET", target)) if not value]
    if missing:
        print(f"NOTIFY_STATUS=warning")
        print(f"NOTIFY_WARNING=missing configuration: {','.join(missing)}")
        return 0
    if delivery_mode not in ALLOWED_DELIVERY_MODES:
        print("NOTIFY_STATUS=warning")
        print(f"NOTIFY_WARNING=unsupported delivery mode: {delivery_mode}")
        return 0

    cmd = [
        hermes_cli(), "kanban", "notify-subscribe", args.task_id,
        "--platform", platform,
        "--chat-id", target,
        "--delivery-mode", delivery_mode,
    ]
    if chat_type:
        cmd.extend(["--chat-type", chat_type])

    try:
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print("NOTIFY_STATUS=warning")
        print(f"NOTIFY_WARNING=subscription failed: {type(exc).__name__}")
        return 0

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", " | ")
        print("NOTIFY_STATUS=warning")
        print(f"NOTIFY_WARNING=subscription command failed: {detail[:300]}")
        return 0

    print("NOTIFY_STATUS=subscribed")
    print(f"NOTIFY_PLATFORM={platform}")
    print(f"NOTIFY_TARGET={target}")
    print(f"NOTIFY_DELIVERY_MODE={delivery_mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
