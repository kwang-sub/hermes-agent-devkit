#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
import re
import subprocess
import sys
from typing import Any

DEFAULT_HERMES_CLI = "/opt/hermes/.venv/bin/hermes"
MODEL_TIERS = ("DEFAULT", "PREMIUM")
SNAPSHOT_MARKER = "MODEL_POLICY_SNAPSHOT_V1"
TERMINAL_STATUSES = {"done", "archived"}


class ModelPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelSelection:
    tier: str
    model: str
    provider: str


def _clean_value(value: str | None, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ModelPolicyError(f"{name} is not configured")
    if any(ch in text for ch in ("\r", "\n", "\x00")):
        raise ModelPolicyError(f"{name} contains an invalid control character")
    return text


def resolve_model_selection(tier: str, environ: dict[str, str] | None = None) -> ModelSelection:
    env = os.environ if environ is None else environ
    normalized = str(tier or "").strip().upper()
    if normalized not in MODEL_TIERS:
        raise ModelPolicyError(f"model tier must be one of {', '.join(MODEL_TIERS)}")
    model_key = f"HERMES_FLOW_MODEL_{normalized}"
    provider_key = f"HERMES_FLOW_MODEL_{normalized}_PROVIDER"
    return ModelSelection(
        tier=normalized,
        model=_clean_value(env.get(model_key), model_key),
        provider=_clean_value(env.get(provider_key), provider_key),
    )


def model_contract_lines(selection: ModelSelection, *, marker: bool = False) -> str:
    lines = []
    if marker:
        lines.append(SNAPSHOT_MARKER)
    lines.extend(
        (
            "Model Policy:",
            f"- Coder Model Tier: {selection.tier}",
            f"- Coder Model: {selection.model}",
            f"- Coder Provider: {selection.provider}",
            "- Reviewer Model: DEFAULT",
            "- Model Escalation: REQUIRE_REAPPROVAL",
        )
    )
    return "\n".join(lines)


def selection_from_contract_text(text: str) -> ModelSelection:
    source = str(text or "")

    def field(label: str) -> str:
        match = re.search(
            rf"(?mi)^\s*-?\s*{re.escape(label)}\s*:\s*(.+?)\s*$",
            source,
        )
        if not match:
            raise ModelPolicyError(f"model contract is missing field: {label}")
        return _clean_value(match.group(1), label)

    tier = field("Coder Model Tier").upper()
    if tier not in MODEL_TIERS:
        raise ModelPolicyError(f"model contract has unsupported Coder Model Tier: {tier}")
    reviewer = field("Reviewer Model").upper()
    if reviewer != "DEFAULT":
        raise ModelPolicyError(f"Reviewer Model must be DEFAULT, got: {reviewer}")
    escalation = field("Model Escalation").upper()
    if escalation != "REQUIRE_REAPPROVAL":
        raise ModelPolicyError(f"Model Escalation must be REQUIRE_REAPPROVAL, got: {escalation}")
    return ModelSelection(
        tier=tier,
        model=field("Coder Model"),
        provider=field("Coder Provider"),
    )


def selection_from_task_payload(payload: dict[str, Any]) -> ModelSelection:
    task = payload.get("task", payload)
    if not isinstance(task, dict):
        raise ModelPolicyError("Kanban show payload has no task object")

    comments = payload.get("comments") or []
    if isinstance(comments, list):
        for comment in reversed(comments):
            if not isinstance(comment, dict):
                continue
            body = str(comment.get("body") or "")
            if SNAPSHOT_MARKER in body:
                return selection_from_contract_text(body)

    body = str(task.get("body") or "")
    if "Coder Model Tier:" in body:
        return selection_from_contract_text(body)

    raise ModelPolicyError(
        "task has no model policy snapshot in body or durable migration comment"
    )


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ModelPolicyError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}")
    return result


def _hermes_cli() -> str:
    return _clean_value(os.environ.get("HERMES_CLI", DEFAULT_HERMES_CLI), "HERMES_CLI")


def _board(value: str | None) -> str:
    return _clean_value(value or os.environ.get("HERMES_KANBAN_BOARD"), "HERMES_KANBAN_BOARD")


def _task_id(value: str | None) -> str:
    return _clean_value(value or os.environ.get("HERMES_KANBAN_TASK"), "HERMES_KANBAN_TASK")


def _base_command(board: str) -> list[str]:
    return [_hermes_cli(), "kanban", "--board", board]


def show_task_payload(*, board: str, task_id: str) -> dict[str, Any]:
    result = _run([*_base_command(board), "show", task_id, "--json"])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ModelPolicyError(f"invalid Kanban show JSON for {task_id}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ModelPolicyError(f"unexpected Kanban show payload for {task_id}")
    task = payload.get("task", payload)
    if not isinstance(task, dict):
        raise ModelPolicyError(f"Kanban show payload has no task object for {task_id}")
    return payload


def set_task_model(*, board: str, task_id: str, selection: ModelSelection | None) -> None:
    command = [*_base_command(board), "set-model", task_id]
    if selection is None:
        command.append("none")
    else:
        command.extend([selection.model, "--provider", selection.provider])
    _run(command)


def restore_raw_override(*, board: str, task_id: str, model: str | None, provider: str | None) -> None:
    clean_model = str(model or "").strip()
    clean_provider = str(provider or "").strip()
    command = [*_base_command(board), "set-model", task_id]
    if not clean_model:
        command.append("none")
    else:
        command.append(clean_model)
        if clean_provider:
            command.extend(["--provider", clean_provider])
    _run(command)


def append_snapshot_comment(*, board: str, task_id: str, selection: ModelSelection) -> None:
    _run(
        [
            *_base_command(board),
            "comment",
            task_id,
            model_contract_lines(selection, marker=True),
            "--author",
            "flow-model-policy",
        ]
    )


def print_selection(selection: ModelSelection) -> None:
    print(f"MODEL_TIER={selection.tier}")
    print(f"MODEL={selection.model}")
    print(f"PROVIDER={selection.provider}")
    print("REVIEWER_MODEL=DEFAULT")
    print("MODEL_ESCALATION=REQUIRE_REAPPROVAL")


def migrate_existing_task(*, board: str, task_id: str, tier: str, lane: str) -> ModelSelection:
    payload = show_task_payload(board=board, task_id=task_id)
    task = payload.get("task", payload)
    assert isinstance(task, dict)
    status = str(task.get("status") or "").strip().lower()
    if status in TERMINAL_STATUSES:
        raise ModelPolicyError(
            f"cannot migrate terminal task {task_id} ({status}); create a follow-up task through the normal approval gates"
        )

    selection = resolve_model_selection(tier)
    previous_model = task.get("model_override")
    previous_provider = task.get("provider_override")

    if lane == "coder":
        set_task_model(board=board, task_id=task_id, selection=selection)
    elif lane == "reviewer":
        set_task_model(board=board, task_id=task_id, selection=None)
    else:
        raise ModelPolicyError(f"unsupported lane: {lane}")

    try:
        append_snapshot_comment(board=board, task_id=task_id, selection=selection)
    except Exception:
        restore_raw_override(
            board=board,
            task_id=task_id,
            model=str(previous_model or "") or None,
            provider=str(previous_provider or "") or None,
        )
        raise

    return selection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve and enforce the DevKit Coder/Reviewer Kanban model policy."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="Resolve an approved Coder model tier from environment variables.")
    resolve.add_argument("--tier", required=True, choices=MODEL_TIERS)

    apply = sub.add_parser("apply", help="Apply an approved Coder model tier to a Kanban task.")
    apply.add_argument("--tier", required=True, choices=MODEL_TIERS)
    apply.add_argument("--task-id")
    apply.add_argument("--board")

    migrate = sub.add_parser(
        "migrate-existing",
        help="Add a durable model snapshot to an active pre-policy task and keep the same card.",
    )
    migrate.add_argument("--tier", required=True, choices=MODEL_TIERS)
    migrate.add_argument("--lane", required=True, choices=("coder", "reviewer"))
    migrate.add_argument("--task-id")
    migrate.add_argument("--board")

    review = sub.add_parser("review-enter", help="Clear the task override before handing the task to Reviewer DEFAULT.")
    review.add_argument("--task-id")
    review.add_argument("--board")

    changes = sub.add_parser("changes-return", help="Restore the originally approved Coder model before CHANGES_REQUESTED returns to Coder.")
    changes.add_argument("--task-id")
    changes.add_argument("--board")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "resolve":
        selection = resolve_model_selection(args.tier)
        print_selection(selection)
        print("STATUS=resolved")
        return 0

    board = _board(args.board)
    task_id = _task_id(args.task_id)

    if args.command == "apply":
        selection = resolve_model_selection(args.tier)
        set_task_model(board=board, task_id=task_id, selection=selection)
        print_selection(selection)
        print("STATUS=applied")
        return 0

    if args.command == "migrate-existing":
        selection = migrate_existing_task(
            board=board,
            task_id=task_id,
            tier=args.tier,
            lane=args.lane,
        )
        print_selection(selection)
        print(f"CURRENT_LANE={args.lane.upper()}")
        print("SNAPSHOT_SOURCE=durable-comment")
        print("STATUS=legacy-task-migrated")
        return 0

    if args.command == "review-enter":
        set_task_model(board=board, task_id=task_id, selection=None)
        print("MODEL_TIER=REVIEWER_DEFAULT")
        print("MODEL=DEFAULT")
        print("STATUS=review-default-ready")
        return 0

    if args.command == "changes-return":
        payload = show_task_payload(board=board, task_id=task_id)
        selection = selection_from_task_payload(payload)
        set_task_model(board=board, task_id=task_id, selection=selection)
        print_selection(selection)
        print("STATUS=coder-model-restored")
        return 0

    raise ModelPolicyError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ModelPolicyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
