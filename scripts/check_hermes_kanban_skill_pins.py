#!/usr/bin/env python3
"""CI-only Hermes Kanban pinned-skill contract: isolated board, no worker dispatch.

Run inside the built DevKit image with /opt/hermes/.venv/bin/python.
--self-test runs pure fixtures in a regular Python CI job without Hermes.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace


class ContractFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def check_create_schema(schema: object, label: str) -> None:
    """Verify the caller-visible array-of-skill-names contract, not just source text."""
    require(isinstance(schema, dict), f"{label}: missing kanban_create schema")
    parameters = schema.get("parameters") or {}
    properties = parameters.get("properties") or {}
    skills = properties.get("skills") or {}
    require(parameters.get("type") == "object", f"{label}: invalid parameters object")
    require(
        skills.get("type") == "array" and (skills.get("items") or {}).get("type") == "string",
        f"{label}: kanban_create.skills must be an array of strings",
    )


def check_persisted_skills(task: object, events: list, expected: list[str]) -> None:
    """A show-tool response is not authoritative for skills: inspect task and created event."""
    require(task is not None, "kanban_create did not persist the task")
    actual = getattr(task, "skills", None)
    require(actual == expected, f"task.skills mismatch: expected {expected!r}, got {actual!r}")
    created = [event for event in events if getattr(event, "kind", None) == "created"]
    require(len(created) == 1, f"expected one created event, got {len(created)}")
    payload = getattr(created[0], "payload", None)
    require(isinstance(payload, dict), "created event has no structured payload")
    require(
        payload.get("skills") == expected,
        f"created event skills mismatch: expected {expected!r}, got {payload.get('skills')!r}",
    )


def self_test() -> None:
    good = {
        "name": "kanban_create",
        "parameters": {
            "type": "object",
            "properties": {"skills": {"type": "array", "items": {"type": "string"}}},
        },
    }
    check_create_schema(good, "fixture")
    for field in ("type", "items"):
        broken = copy.deepcopy(good)
        pin = broken["parameters"]["properties"]["skills"]
        pin[field] = "string" if field == "type" else {"type": "number"}
        try:
            check_create_schema(broken, "negative fixture")
        except ContractFailure:
            pass
        else:
            raise AssertionError(f"invalid schema {field} was accepted")
    broken = copy.deepcopy(good)
    del broken["parameters"]["properties"]["skills"]
    try:
        check_create_schema(broken, "missing fixture")
    except ContractFailure:
        pass
    else:
        raise AssertionError("missing skills field was accepted")

    expected = ["dev-java-guidelines", "dev-flow-model-policy"]
    task = SimpleNamespace(skills=expected)
    event = SimpleNamespace(kind="created", payload={"skills": expected})
    check_persisted_skills(task, [event], expected)
    for bad_task, bad_event in (
        (SimpleNamespace(skills=None), event),
        (task, SimpleNamespace(kind="created", payload={"skills": None})),
    ):
        try:
            check_persisted_skills(bad_task, [bad_event], expected)
        except ContractFailure:
            pass
        else:
            raise AssertionError("missing persisted skill pin was accepted")
    print("PASS: CI Kanban skill pin schema and persistence negative fixtures")


def runtime_smoke() -> None:
    # This subprocess is a standalone Docker --entrypoint Python process. Redirect
    # every state root BEFORE importing Hermes; never touch a user's real board.
    with tempfile.TemporaryDirectory(prefix="devkit-kanban-pin-ci-") as directory:
        root = Path(directory).resolve()
        profile = root / "profile"
        home = root / "home"
        profile.mkdir()
        home.mkdir()
        (profile / "config.yaml").write_text("toolsets:\n  - kanban\n", encoding="utf-8")
        db_path = root / "isolated" / "kanban.db"
        os.environ.update({
            "HERMES_HOME": str(profile),
            "HOME": str(home),
            "HERMES_PROFILE": "orchestrator",
            "HERMES_KANBAN_DB": str(db_path),
            "HERMES_KANBAN_BOARD": "default",
            "HERMES_KANBAN_WORKSPACES_ROOT": str(root / "workspaces"),
            "HERMES_KANBAN_NOTIFY_ENABLED": "false",
        })
        for key in (
            "HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID",
            "HERMES_KANBAN_CLAIM_LOCK", "HERMES_SESSION_ID",
            "HERMES_TENANT",
        ):
            os.environ.pop(key, None)

        from tools.kanban_tools_schemas import KANBAN_CREATE_SCHEMA
        import tools.kanban_tools  # noqa: F401 -- registers the live tool handler
        from tools.registry import registry
        from hermes_cli import kanban_db as kb
        from hermes_cli import kanban_db_connect as kbc

        require(
            kb.kanban_db_path().resolve() == db_path,
            "CI isolation failed: Kanban DB does not resolve to the temporary board",
        )
        require(not db_path.exists(), "CI fixture board unexpectedly exists")
        check_create_schema(KANBAN_CREATE_SCHEMA, "upstream source")
        check_create_schema(registry.get_schema("kanban_create"), "registered tool")

        definitions = registry.get_definitions({"kanban_create"}, quiet=True)
        exposed = [
            item.get("function") for item in definitions
            if item.get("type") == "function"
            and (item.get("function") or {}).get("name") == "kanban_create"
        ]
        require(len(exposed) == 1, "kanban_create missing from model-facing tool definitions")
        check_create_schema(exposed[0], "model-facing tool")

        expected = [
            "dev-java-guidelines",
            "dev-spring-guidelines",
            "dev-spring-test",
            "dev-official-docs-context",
            "dev-flow-model-policy",
        ]
        create_args = {
            "title": "CI isolated pinned skill persistence smoke",
            "body": "CI-only fixture. No product scope, no worker dispatch.",
            "assignee": "coder",
            "workspace_kind": "scratch",
            "initial_status": "blocked",
            "skills": expected,
        }
        response = registry.dispatch("kanban_create", create_args)
        require(isinstance(response, str), f"kanban_create returned nontext: {type(response).__name__}")
        created = json.loads(response)
        require(created.get("ok") is True, f"kanban_create failed: {created}")
        task_id = created.get("task_id")
        require(isinstance(task_id, str) and task_id.startswith("t_"), "kanban_create returned no task ID")
        require(created.get("status") == "blocked", "CI fixture escaped the blocked dispatch barrier")
        require(db_path.is_file(), "kanban_create did not use the isolated board")

        shown_raw = registry.dispatch("kanban_show", {"task_id": task_id})
        require(isinstance(shown_raw, str), "kanban_show did not return JSON")
        shown = json.loads(shown_raw)
        shown_task = shown.get("task") or {}
        require(
            shown_task.get("id") == task_id and shown_task.get("status") == "blocked",
            "kanban_show failed to read the newly created blocked task",
        )
        # Upstream kanban_show's compact _TASK_FIELDS omits skills; do not mistake
        # that omission for a failed DB write.
        with kbc.connect_closing(db_path=db_path) as conn:
            task = kb.get_task(conn, task_id)
            events = kb.list_events(conn, task_id)
            check_persisted_skills(task, events, expected)
            require(task.status == "blocked", "pinned task is no longer blocked")
            require(not kb.list_runs(conn, task_id), "CI task unexpectedly acquired a worker run")

    require(not root.exists(), "temporary Kanban board was not cleaned up")
    print("PASS: model-facing kanban_create.skills + isolated blocked task DB/event read-back; no worker dispatched")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Pure contract fixtures; no Hermes runtime needed")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
        else:
            runtime_smoke()
    except (ContractFailure, Exception) as exc:
        print(f"FAIL: Hermes Kanban skill pin compatibility: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
