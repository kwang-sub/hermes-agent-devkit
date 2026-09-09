#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

DELEGATED_CHILD_ENV_MARKER = "HERMES_DELEGATED_CHILD_CONTEXT"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _validate_context(
    env: Mapping[str, str],
    task: Any | None,
    *,
    ownership_ok: bool,
    lookup_error: str | None = None,
) -> dict[str, Any]:
    task_id = _clean(env.get("HERMES_KANBAN_TASK"))
    board = _clean(env.get("HERMES_KANBAN_BOARD"))
    db_path = _clean(env.get("HERMES_KANBAN_DB"))
    run_id = _clean(env.get("HERMES_KANBAN_RUN_ID"))
    claim_lock = _clean(env.get("HERMES_KANBAN_CLAIM_LOCK"))

    errors: list[str] = []
    if _clean(env.get(DELEGATED_CHILD_ENV_MARKER)):
        errors.append("delegated child marker is set")
    if not ownership_ok:
        errors.append("context is not dispatcher-owned")
    if not task_id:
        errors.append("HERMES_KANBAN_TASK missing")
    if not board:
        errors.append("HERMES_KANBAN_BOARD missing")
    if not db_path:
        errors.append("HERMES_KANBAN_DB missing")
    if not run_id:
        errors.append("HERMES_KANBAN_RUN_ID missing")
    if not claim_lock:
        errors.append("HERMES_KANBAN_CLAIM_LOCK missing")
    if lookup_error:
        errors.append(lookup_error)
    elif task_id and task is None:
        errors.append("task not found on pinned board")

    if task is not None:
        task_status = _clean(getattr(task, "status", ""))
        actual_run_id = _clean(getattr(task, "current_run_id", ""))
        actual_claim_lock = _clean(getattr(task, "claim_lock", ""))
        workspace = _clean(getattr(task, "workspace_path", ""))
        assignee = _clean(getattr(task, "assignee", ""))

        if task_status != "running":
            errors.append(f"task status is not running: {task_status or '-'}")
        if run_id and actual_run_id != run_id:
            errors.append("task current_run_id does not match worker run")
        if claim_lock and actual_claim_lock != claim_lock:
            errors.append("task claim_lock does not match worker claim")
        if not workspace:
            errors.append("task workspace is missing")
        if not assignee:
            errors.append("task assignee is missing")

    payload = {
        "status": "valid" if not errors else "invalid",
        "context_source": "hermes-mcp",
        "task_id": task_id or None,
        "board": board or None,
        "run_id": run_id or None,
        "workspace": ((_clean(getattr(task, "workspace_path", "")) or None) if task is not None else None),
        "profile": ((_clean(getattr(task, "assignee", "")) or None) if task is not None else None),
        "task_status": ((_clean(getattr(task, "status", "")) or None) if task is not None else None),
        "model": ((_clean(getattr(task, "model_override", "")) or None) if task is not None else None),
        "provider": ((_clean(getattr(task, "provider_override", "")) or None) if task is not None else None),
        "claim_bound": bool(claim_lock),
        "errors": errors,
    }
    return payload


def _load_task(db_path: str, task_id: str) -> Any | None:
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc

    pinned = Path(db_path).expanduser()
    if not pinned.is_file():
        raise FileNotFoundError(f"pinned Kanban DB does not exist: {pinned}")
    conn = kbc.connect(db_path=pinned)
    try:
        return kb.get_task(conn, task_id)
    finally:
        conn.close()


def kanban_worker_context() -> str:
    """Verify the active dispatcher-owned Kanban worker context inside Hermes MCP.

    The Codex executor intentionally does not receive Kanban ownership environment
    variables in its native shell. This read-only MCP tool validates the pinned
    Task/Board/Run/Claim against the live Kanban row without exposing the claim
    token to Codex shell commands.
    """
    from agent.delegation_context import is_dispatcher_owned_worker_context

    env = dict(os.environ)
    task_id = _clean(env.get("HERMES_KANBAN_TASK"))
    board = _clean(env.get("HERMES_KANBAN_BOARD"))
    db_path = _clean(env.get("HERMES_KANBAN_DB"))
    task = None
    lookup_error = None
    if task_id and board and db_path:
        try:
            task = _load_task(db_path, task_id)
        except Exception as exc:
            lookup_error = f"task lookup failed: {type(exc).__name__}"

    payload = _validate_context(
        env,
        task,
        ownership_ok=is_dispatcher_owned_worker_context(),
        lookup_error=lookup_error,
    )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def self_test() -> None:
    env = {
        "HERMES_KANBAN_TASK": "t_test",
        "HERMES_KANBAN_BOARD": "demo",
        "HERMES_KANBAN_DB": "/tmp/demo.db",
        "HERMES_KANBAN_RUN_ID": "7",
        "HERMES_KANBAN_CLAIM_LOCK": "claim-token",
    }
    task = SimpleNamespace(
        status="running",
        current_run_id=7,
        claim_lock="claim-token",
        workspace_path="/workspace/demo",
        assignee="coder",
        model_override="gpt-test",
        provider_override="openai-codex",
    )

    valid = _validate_context(env, task, ownership_ok=True)
    assert valid["status"] == "valid"
    assert valid["task_id"] == "t_test"
    assert valid["workspace"] == "/workspace/demo"
    assert valid["profile"] == "coder"
    assert valid["claim_bound"] is True

    missing = dict(env)
    missing.pop("HERMES_KANBAN_TASK")
    invalid = _validate_context(missing, None, ownership_ok=True)
    assert invalid["status"] == "invalid"
    assert "HERMES_KANBAN_TASK missing" in invalid["errors"]

    mismatched = SimpleNamespace(**{**task.__dict__, "current_run_id": 8})
    invalid = _validate_context(env, mismatched, ownership_ok=True)
    assert "task current_run_id does not match worker run" in invalid["errors"]

    delegated = dict(env)
    delegated[DELEGATED_CHILD_ENV_MARKER] = "1"
    invalid = _validate_context(delegated, task, ownership_ok=False)
    assert invalid["status"] == "invalid"
    assert "delegated child marker is set" in invalid["errors"]

    print("DevKit Kanban worker context self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    print(kanban_worker_context())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
