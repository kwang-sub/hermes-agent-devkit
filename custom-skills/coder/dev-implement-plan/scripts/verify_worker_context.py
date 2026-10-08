#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


class GuardError(RuntimeError):
    pass


class WrongVerificationPath(GuardError):
    """The current shell cannot prove dispatcher ownership by design."""
    pass


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-workspace", required=True)
    parser.add_argument("--expected-profile", default="coder")
    parser.add_argument(
        "--worker-provider",
        default=None,
        help="Approved active worker provider. Codex must use kanban_show instead.",
    )
    args = parser.parse_args()

    task_id = _clean(os.environ.get("HERMES_KANBAN_TASK"))
    board = _clean(os.environ.get("HERMES_KANBAN_BOARD"))
    kanban_db = _clean(os.environ.get("HERMES_KANBAN_DB"))
    actual_workspace = _clean(os.environ.get("HERMES_KANBAN_WORKSPACE"))
    profile = _clean(os.environ.get("HERMES_PROFILE"))
    source = _clean(os.environ.get("HERMES_SESSION_SOURCE"))
    context_version = _clean(os.environ.get("HERMES_KANBAN_CONTEXT_VERSION"))
    session_mode = _clean(os.environ.get("HERMES_KANBAN_SESSION_MODE")) or "NEW"
    affinity_session_id = _clean(os.environ.get("HERMES_KANBAN_AFFINITY_SESSION_ID")) or "-"
    delegated = _clean(os.environ.get("HERMES_DELEGATED_CHILD_CONTEXT"))
    provider = _clean(args.worker_provider).lower()

    # Codex app-server and delegated shell descendants are deliberately stripped
    # of Kanban ownership. Do not treat their missing HERMES_KANBAN_TASK as a
    # transient dispatcher failure, and never try to restore the sensitive env.
    # Explicit provider rejects this helper even when the caller supplies env.
    if provider == "openai-codex" or (delegated and not task_id):
        raise WrongVerificationPath(
            "WRONG_VERIFICATION_PATH: Codex native shell or an unowned "
            "delegated subprocess cannot run the env-based Worker Context Gate. "
            "For an openai-codex worker, verify the INITIAL kanban_show Task ID, "
            "running status, current_run_id and worker_context via the managed "
            "Kanban MCP tool. Never re-inject HERMES_KANBAN_TASK or retry this "
            "helper from the same shell."
        )

    problems: list[str] = []
    if delegated:
        problems.append("HERMES_DELEGATED_CHILD_CONTEXT must be unset")
    if not task_id:
        problems.append("HERMES_KANBAN_TASK missing")
    if not board:
        problems.append("HERMES_KANBAN_BOARD missing")
    if not kanban_db:
        problems.append("HERMES_KANBAN_DB missing")
    if not actual_workspace:
        problems.append("HERMES_KANBAN_WORKSPACE missing")
    else:
        try:
            if Path(actual_workspace).resolve() != Path(args.expected_workspace).resolve():
                problems.append(
                    "HERMES_KANBAN_WORKSPACE mismatch: "
                    f"expected={Path(args.expected_workspace).resolve()}, actual={Path(actual_workspace).resolve()}"
                )
        except OSError:
            problems.append(f"HERMES_KANBAN_WORKSPACE invalid: {actual_workspace}")
    if profile != args.expected_profile:
        problems.append(f"HERMES_PROFILE mismatch: expected={args.expected_profile!r}, actual={profile!r}")
    if source != "kanban":
        problems.append(f"HERMES_SESSION_SOURCE mismatch: expected='kanban', actual={source!r}")
    if context_version != "1":
        problems.append(
            f"HERMES_KANBAN_CONTEXT_VERSION mismatch: expected='1', actual={context_version!r}"
        )

    if problems:
        raise GuardError(
            "Kanban worker context is missing or mismatched. "
            "Do not continue from a manual `hermes --resume`/direct chat process and do not inject "
            "Kanban environment variables manually. Requeue/unblock the same card so the dispatcher "
            "creates a fresh worker context. " + " | ".join(problems)
        )

    print("WORKER_CONTEXT_STATUS=valid")
    print(f"KANBAN_TASK_ID={task_id}")
    print(f"KANBAN_BOARD={board}")
    print(f"KANBAN_PROFILE={profile}")
    print(f"KANBAN_SESSION_MODE={session_mode}")
    print(f"KANBAN_AFFINITY_SESSION_ID={affinity_session_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WrongVerificationPath as exc:
        print("WORKER_CONTEXT_STATUS=BLOCKED", file=sys.stderr)
        print("WORKER_CONTEXT_BLOCKER=WRONG_VERIFICATION_PATH", file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except GuardError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
