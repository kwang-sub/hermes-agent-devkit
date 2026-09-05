#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess

TRUE_VALUES = {"1", "true", "yes", "on"}
ALLOWED_DELIVERY_MODES = {"notify", "wake", "notify+wake"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Subscribe a Kanban task to optional gateway notifications.")
    parser.add_argument("--board", required=True, help="Explicit Kanban board slug. Default-board fallback is forbidden.")
    parser.add_argument("--task-id", required=True)
    return parser.parse_args()


def enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUE_VALUES


def hermes_cli() -> str:
    override = os.getenv("HERMES_CLI")
    if override:
        return override
    return shutil.which("hermes") or "/usr/local/bin/hermes"


def run_command(cmd: list[str], *, timeout: int = 20) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def command_detail(result: subprocess.CompletedProcess[str] | None) -> str:
    if result is None:
        return "command execution failed"
    return (result.stderr or result.stdout).strip().replace("\n", " | ")[:300]


def fail(reason: str) -> int:
    print("NOTIFY_STATUS=failed")
    print(f"NOTIFY_ERROR={reason}")
    return 1


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


def main() -> int:
    args = parse_args()
    board = args.board.strip()
    if not board:
        return fail("board must not be empty")

    if not enabled(os.getenv("HERMES_KANBAN_NOTIFY_ENABLED")):
        print("NOTIFY_STATUS=disabled")
        print(f"NOTIFY_BOARD={board}")
        return 0

    platform = (os.getenv("HERMES_KANBAN_NOTIFY_PLATFORM") or "").strip()
    target = (os.getenv("HERMES_KANBAN_NOTIFY_TARGET") or "").strip()
    delivery_mode = (os.getenv("HERMES_KANBAN_NOTIFY_DELIVERY_MODE") or "notify").strip()
    chat_type = (os.getenv("HERMES_KANBAN_NOTIFY_CHAT_TYPE") or "").strip()
    notifier_profile = (os.getenv("HERMES_KANBAN_NOTIFY_PROFILE") or "default").strip()

    missing = [
        name
        for name, value in (
            ("HERMES_KANBAN_NOTIFY_PLATFORM", platform),
            ("HERMES_KANBAN_NOTIFY_TARGET", target),
            ("HERMES_KANBAN_NOTIFY_PROFILE", notifier_profile),
        )
        if not value
    ]
    if missing:
        return fail(f"missing configuration: {','.join(missing)}")
    if delivery_mode not in ALLOWED_DELIVERY_MODES:
        return fail(f"unsupported delivery mode: {delivery_mode}")

    cli = hermes_cli()
    prefix = [cli, "kanban", "--board", board]

    show = run_command([*prefix, "show", args.task_id, "--json"])
    if show is None or show.returncode != 0:
        return fail(f"task read-back failed on board '{board}': {command_detail(show)}")
    print("TASK_READBACK_VERIFIED=true")

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
        return fail(f"subscription command failed: {command_detail(subscribed)}")

    verify = run_command([*prefix, "notify-list", args.task_id, "--json"])
    if verify is None or verify.returncode != 0:
        return fail(f"subscription verification command failed: {command_detail(verify)}")

    try:
        subscriptions = load_subscriptions(verify.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        return fail(f"subscription verification JSON invalid: {type(exc).__name__}")

    matched = any(
        str(sub.get("task_id") or args.task_id) == args.task_id
        and str(sub.get("platform") or "") == platform
        and str(sub.get("chat_id") or "") == target
        and str(sub.get("notifier_profile") or "") == notifier_profile
        and str(sub.get("delivery_mode") or "notify") == delivery_mode
        for sub in subscriptions
    )
    if not matched:
        return fail("subscription verification did not find the expected board/task target")

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
