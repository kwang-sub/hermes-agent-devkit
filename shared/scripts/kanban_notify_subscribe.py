#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess

TRUE_VALUES = {"1", "true", "yes", "on"}
ALLOWED_DELIVERY_MODES = {"notify", "wake", "notify+wake"}
NOTIFIER_PROFILE = "default"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Subscribe a Kanban task to optional Hermes-native gateway notifications."
    )
    parser.add_argument(
        "--board",
        required=True,
        help="Explicit Kanban board slug. Default-board fallback is forbidden.",
    )
    parser.add_argument("--task-id", required=True)
    return parser.parse_args()


def enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUE_VALUES


def hermes_cli() -> str:
    override = (os.getenv("HERMES_CLI") or "").strip()
    return override or shutil.which("hermes") or "/usr/local/bin/hermes"


def run_command(cmd: list[str], *, timeout: int = 20) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def command_detail(result: subprocess.CompletedProcess[str] | None) -> str:
    if result is None:
        return "command execution failed"
    return (result.stderr or result.stdout).strip().replace("\n", " | ")[:300]


def warning(reason: str, *, board: str) -> int:
    print("NOTIFY_STATUS=warning")
    print("NOTIFY_VERIFIED=false")
    print(f"NOTIFY_ERROR={reason}")
    print(f"NOTIFY_BOARD={board}")
    return 0


def load_subscriptions(raw: str) -> list[dict]:
    payload = json.loads(raw or "[]")
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("subscriptions", "items", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("unexpected notify-list JSON shape")


def subscription_matches(
    sub: dict,
    *,
    task_id: str,
    platform: str,
    target: str,
    notifier_profile: str,
    delivery_mode: str,
) -> bool:
    return (
        str(sub.get("task_id") or task_id) == task_id
        and str(sub.get("platform") or "") == platform
        and str(sub.get("chat_id") or "") == target
        and str(sub.get("notifier_profile") or "") == notifier_profile
        and str(sub.get("delivery_mode") or "notify") == delivery_mode
    )


def main() -> int:
    args = parse_args()
    board = args.board.strip()
    if not board:
        print("NOTIFY_STATUS=failed")
        print("NOTIFY_ERROR=board must not be empty")
        return 1

    if not enabled(os.getenv("HERMES_KANBAN_NOTIFY_ENABLED")):
        print("NOTIFY_STATUS=disabled")
        print(f"NOTIFY_BOARD={board}")
        return 0

    platform = (os.getenv("HERMES_KANBAN_NOTIFY_PLATFORM") or "").strip()
    target = (os.getenv("HERMES_KANBAN_NOTIFY_TARGET") or "").strip()
    delivery_mode = (os.getenv("HERMES_KANBAN_NOTIFY_DELIVERY_MODE") or "notify").strip()
    chat_type = (os.getenv("HERMES_KANBAN_NOTIFY_CHAT_TYPE") or "").strip()
    notifier_profile = NOTIFIER_PROFILE

    missing = [
        name
        for name, value in (
            ("HERMES_KANBAN_NOTIFY_PLATFORM", platform),
            ("HERMES_KANBAN_NOTIFY_TARGET", target),
        )
        if not value
    ]
    if missing:
        return warning(f"missing configuration: {','.join(missing)}", board=board)
    if delivery_mode not in ALLOWED_DELIVERY_MODES:
        return warning(f"unsupported delivery mode: {delivery_mode}", board=board)

    prefix = [hermes_cli(), "kanban", "--board", board]
    subscribe_cmd = [
        *prefix,
        "notify-subscribe",
        args.task_id,
        "--platform",
        platform,
        "--chat-id",
        target,
        "--delivery-mode",
        delivery_mode,
        "--notifier-profile",
        notifier_profile,
    ]
    if chat_type:
        subscribe_cmd.extend(["--chat-type", chat_type])

    subscribed = run_command(subscribe_cmd)
    if subscribed is None or subscribed.returncode != 0:
        return warning(
            f"native subscription command failed: {command_detail(subscribed)}",
            board=board,
        )

    verify = run_command([*prefix, "notify-list", args.task_id, "--json"])
    if verify is None or verify.returncode != 0:
        return warning(
            f"native subscription read-back failed: {command_detail(verify)}",
            board=board,
        )
    try:
        subscriptions = load_subscriptions(verify.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        return warning(
            f"native subscription read-back JSON invalid: {type(exc).__name__}",
            board=board,
        )

    matched = next(
        (
            sub
            for sub in subscriptions
            if subscription_matches(
                sub,
                task_id=args.task_id,
                platform=platform,
                target=target,
                notifier_profile=notifier_profile,
                delivery_mode=delivery_mode,
            )
        ),
        None,
    )
    if matched is None:
        return warning(
            "native subscription read-back did not find the expected board/task target",
            board=board,
        )

    print("NOTIFY_STATUS=subscribed")
    print("NOTIFY_VERIFIED=true")
    print(f"NOTIFY_BOARD={board}")
    print(f"NOTIFY_PLATFORM={platform}")
    print(f"NOTIFY_TARGET={target}")
    print(f"NOTIFY_DELIVERY_MODE={delivery_mode}")
    print(f"NOTIFY_PROFILE={notifier_profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
