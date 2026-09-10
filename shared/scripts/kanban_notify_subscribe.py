#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

TRUE_VALUES = {"1", "true", "yes", "on"}
ALLOWED_DELIVERY_MODES = {"notify", "wake", "notify+wake"}
DEFAULT_REGISTRATION_HELPER = Path(__file__).resolve().with_name("kanban_registration_event.py")
DEFAULT_HERMES_PYTHON = Path("/opt/hermes/.venv/bin/python")
REGISTRATION_ACK_TIMEOUT_ENV = "HERMES_KANBAN_NOTIFY_REGISTRATION_ACK_TIMEOUT_SECONDS"
REGISTRATION_ACK_POLL_ENV = "HERMES_KANBAN_NOTIFY_REGISTRATION_ACK_POLL_SECONDS"
DEFAULT_REGISTRATION_ACK_TIMEOUT_SECONDS = 20.0
DEFAULT_REGISTRATION_ACK_POLL_SECONDS = 0.5


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


def hermes_python() -> str:
    override = (os.getenv("HERMES_PYTHON") or "").strip()
    if override:
        return str(Path(override).expanduser())
    if DEFAULT_HERMES_PYTHON.is_file():
        return str(DEFAULT_HERMES_PYTHON)
    return sys.executable


def registration_helper() -> Path:
    override = (os.getenv("HERMES_KANBAN_REGISTRATION_EVENT_HELPER") or "").strip()
    return Path(override).expanduser() if override else DEFAULT_REGISTRATION_HELPER


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


def parse_key_values(raw: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip()
    return values


def env_seconds(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, value)


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


def matching_subscription(
    subscriptions: list[dict],
    *,
    task_id: str,
    platform: str,
    target: str,
    notifier_profile: str,
    delivery_mode: str,
) -> dict | None:
    return next(
        (
            sub
            for sub in subscriptions
            if subscription_matches(
                sub,
                task_id=task_id,
                platform=platform,
                target=target,
                notifier_profile=notifier_profile,
                delivery_mode=delivery_mode,
            )
        ),
        None,
    )


def enqueue_registration_event(board: str, task_id: str) -> tuple[str | None, int | None, str]:
    helper = registration_helper()
    if not helper.is_file():
        return None, None, f"registration event helper missing: {helper}"
    result = run_command(
        [hermes_python(), str(helper), "--board", board, "--task-id", task_id],
        timeout=20,
    )
    if result is None or result.returncode != 0:
        return None, None, command_detail(result)
    output = (result.stdout or "").strip()
    values = parse_key_values(output)
    status = values.get("REGISTRATION_EVENT_STATUS")
    raw_event_id = values.get("REGISTRATION_EVENT_ID")
    if status not in {"queued", "existing"}:
        return None, None, f"unexpected registration event result: {output[:300]}"
    try:
        event_id = int(raw_event_id or "")
    except ValueError:
        return None, None, f"registration event id missing or invalid: {output[:300]}"
    if event_id <= 0:
        return None, None, f"registration event id must be positive: {event_id}"
    return status, event_id, output


def read_subscriptions(prefix: list[str], task_id: str) -> tuple[list[dict] | None, str | None]:
    verify = run_command([*prefix, "notify-list", task_id, "--json"])
    if verify is None or verify.returncode != 0:
        return None, f"subscription verification command failed: {command_detail(verify)}"
    try:
        return load_subscriptions(verify.stdout), None
    except (json.JSONDecodeError, ValueError) as exc:
        return None, f"subscription verification JSON invalid: {type(exc).__name__}"


def wait_for_registration_delivery(
    prefix: list[str],
    *,
    task_id: str,
    platform: str,
    target: str,
    notifier_profile: str,
    delivery_mode: str,
    event_id: int,
) -> tuple[bool, str]:
    timeout = env_seconds(
        REGISTRATION_ACK_TIMEOUT_ENV,
        DEFAULT_REGISTRATION_ACK_TIMEOUT_SECONDS,
        minimum=0.0,
    )
    poll = env_seconds(
        REGISTRATION_ACK_POLL_ENV,
        DEFAULT_REGISTRATION_ACK_POLL_SECONDS,
        minimum=0.01,
    )
    deadline = time.monotonic() + timeout
    wake_stable_reads = 0
    last_observed = "subscription not observed"

    while True:
        subscriptions, error = read_subscriptions(prefix, task_id)
        if error:
            last_observed = error
        else:
            assert subscriptions is not None
            sub = matching_subscription(
                subscriptions,
                task_id=task_id,
                platform=platform,
                target=target,
                notifier_profile=notifier_profile,
                delivery_mode=delivery_mode,
            )
            if sub is None:
                last_observed = "expected subscription disappeared while awaiting registration delivery"
            else:
                try:
                    last_event_id = int(sub.get("last_event_id") or 0)
                    last_ping_event_id = int(sub.get("last_ping_event_id") or 0)
                except (TypeError, ValueError):
                    return False, "subscription delivery cursors are not integers"

                last_observed = (
                    f"last_event_id={last_event_id}, last_ping_event_id={last_ping_event_id}, "
                    f"registration_event_id={event_id}"
                )

                if delivery_mode == "wake":
                    # wake-only has no passive ping checkpoint. The claim cursor is
                    # rewound on wake failure, so require two stable observations of
                    # the exact registration event before accepting the gate.
                    if last_event_id == event_id:
                        wake_stable_reads += 1
                        if wake_stable_reads >= 2:
                            return True, f"wake cursor settled at registration event {event_id}"
                    else:
                        wake_stable_reads = 0
                        if last_event_id > event_id:
                            return False, (
                                "registration wake event was bypassed before gate acknowledgement: "
                                f"{last_observed}"
                            )
                else:
                    # The Standard Flow keeps the task blocked until this gate passes,
                    # so no later ping is valid here. Exact equality proves the
                    # registration event itself reached adapter.send successfully;
                    # a greater value would mask a skipped registration behind a later
                    # terminal event (the failure mode this gate is designed to catch).
                    if last_ping_event_id == event_id:
                        return True, f"last_ping_event_id={last_ping_event_id}"
                    if last_ping_event_id > event_id or last_event_id > event_id:
                        return False, (
                            "registration notification was bypassed before gate acknowledgement: "
                            f"{last_observed}"
                        )

        if time.monotonic() >= deadline:
            return False, f"registration delivery acknowledgement timed out: {last_observed}"
        time.sleep(poll)


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

    subscriptions, verify_error = read_subscriptions(prefix, args.task_id)
    if verify_error:
        return fail(verify_error)
    assert subscriptions is not None
    matched = matching_subscription(
        subscriptions,
        task_id=args.task_id,
        platform=platform,
        target=target,
        notifier_profile=notifier_profile,
        delivery_mode=delivery_mode,
    )
    if matched is None:
        return fail("subscription verification did not find the expected board/task target")

    # Hermes notification subscriptions start their cursor at the latest event.
    # Therefore the registration event MUST be enqueued only after the verified
    # subscription exists, otherwise the first-card notification is considered history.
    registration_status, registration_event_id, registration_detail = enqueue_registration_event(
        board, args.task_id
    )
    if registration_status is None or registration_event_id is None:
        return fail(f"registration notification enqueue failed: {registration_detail}")

    delivered, delivery_detail = wait_for_registration_delivery(
        prefix,
        task_id=args.task_id,
        platform=platform,
        target=target,
        notifier_profile=notifier_profile,
        delivery_mode=delivery_mode,
        event_id=registration_event_id,
    )
    if not delivered:
        return fail(f"registration notification delivery failed: {delivery_detail}")

    print("NOTIFY_STATUS=subscribed")
    print("NOTIFY_VERIFIED=true")
    # Preserve the existing Standard Flow output contract: EVENT=queued means
    # the logical registration event is durably present. STATE distinguishes a
    # newly inserted event from an idempotent retry without breaking older
    # orchestrator skill contracts that key on EVENT=queued.
    print("NOTIFY_REGISTRATION_EVENT=queued")
    print(f"NOTIFY_REGISTRATION_EVENT_STATE={registration_status}")
    print(f"NOTIFY_REGISTRATION_EVENT_ID={registration_event_id}")
    print("NOTIFY_REGISTRATION_DELIVERED=true")
    print(f"NOTIFY_REGISTRATION_DELIVERY={delivery_detail}")
    print(f"NOTIFY_BOARD={board}")
    print(f"NOTIFY_PLATFORM={platform}")
    print(f"NOTIFY_TARGET={target}")
    print(f"NOTIFY_DELIVERY_MODE={delivery_mode}")
    print(f"NOTIFY_PROFILE={notifier_profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
