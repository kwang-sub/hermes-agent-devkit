#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().with_name("flow_model_policy.py")

MODEL_ENV = {
    "HERMES_FLOW_MODEL_DEFAULT_PROVIDER": "openai-codex",
    "HERMES_FLOW_MODEL_DEFAULT": "gpt-5.6-terra",
    "HERMES_FLOW_MODEL_PREMIUM_PROVIDER": "openai-codex",
    "HERMES_FLOW_MODEL_PREMIUM": "gpt-6-astra",
}

TASK_BODY = """Flow: FAST
Model Policy:
- Coder Model Tier: PREMIUM
- Coder Model: gpt-6-astra
- Coder Provider: openai-codex
- Reviewer Model: DEFAULT
- Model Escalation: REQUIRE_REAPPROVAL
"""

LEGACY_COMMENT = """MODEL_POLICY_SNAPSHOT_V1
Model Policy:
- Coder Model Tier: DEFAULT
- Coder Model: gpt-5.6-terra
- Coder Provider: openai-codex
- Reviewer Model: DEFAULT
- Model Escalation: REQUIRE_REAPPROVAL
"""


def invoke(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(["python3", str(SCRIPT), *args], text=True, capture_output=True, env=merged)


def test_resolve_uses_environment_snapshot() -> None:
    result = invoke(["resolve", "--tier", "PREMIUM"], MODEL_ENV)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    for term in (
        "MODEL_TIER=PREMIUM",
        "MODEL=gpt-6-astra",
        "PROVIDER=openai-codex",
        "REVIEWER_MODEL=DEFAULT",
        "MODEL_ESCALATION=REQUIRE_REAPPROVAL",
        "STATUS=resolved",
    ):
        if term not in result.stdout:
            raise AssertionError(result.stdout)


def write_fake_hermes(root: Path) -> tuple[Path, Path]:
    log = root / "calls.log"
    fake = root / "hermes"
    fake.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$*\" >> \"$HERMES_TEST_CALL_LOG\"\n"
        "case \" $* \" in\n"
        "  *' show '*' --json '*) printf '%s\\n' \"$HERMES_TEST_SHOW_JSON\" ;;\n"
        "  *' comment '*) [ \"${HERMES_TEST_FAIL_COMMENT:-0}\" = 1 ] && exit 9 || : ;;\n"
        "  *) : ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake, log


def transition_env(fake: Path, log: Path, payload: dict) -> dict[str, str]:
    env = dict(MODEL_ENV)
    env.update(
        {
            "HERMES_CLI": str(fake),
            "HERMES_KANBAN_BOARD": "demo",
            "HERMES_KANBAN_TASK": "t_demo",
            "HERMES_TEST_CALL_LOG": str(log),
            "HERMES_TEST_SHOW_JSON": json.dumps(payload),
        }
    )
    return env


def test_review_enter_clears_override() -> None:
    with tempfile.TemporaryDirectory(prefix="flow-model-policy-review-") as temp_dir:
        root = Path(temp_dir)
        fake, log = write_fake_hermes(root)
        env = transition_env(fake, log, {"task": {"id": "t_demo", "body": TASK_BODY}})
        result = invoke(["review-enter"], env)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        if "STATUS=review-default-ready" not in result.stdout:
            raise AssertionError(result.stdout)
        calls = log.read_text(encoding="utf-8")
        if "kanban --board demo set-model t_demo none" not in calls:
            raise AssertionError(calls)


def test_changes_return_restores_task_body_snapshot_not_current_env() -> None:
    with tempfile.TemporaryDirectory(prefix="flow-model-policy-changes-") as temp_dir:
        root = Path(temp_dir)
        fake, log = write_fake_hermes(root)
        env = transition_env(fake, log, {"task": {"id": "t_demo", "body": TASK_BODY}, "comments": []})
        env["HERMES_FLOW_MODEL_PREMIUM"] = "gpt-future-model"
        result = invoke(["changes-return"], env)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        if "STATUS=coder-model-restored" not in result.stdout:
            raise AssertionError(result.stdout)
        calls = log.read_text(encoding="utf-8")
        expected = "kanban --board demo set-model t_demo gpt-6-astra --provider openai-codex"
        if expected not in calls:
            raise AssertionError(calls)
        if "gpt-future-model" in calls:
            raise AssertionError("changes-return re-resolved current ENV instead of task snapshot")


def test_changes_return_prefers_legacy_comment_snapshot() -> None:
    with tempfile.TemporaryDirectory(prefix="flow-model-policy-comment-") as temp_dir:
        root = Path(temp_dir)
        fake, log = write_fake_hermes(root)
        payload = {
            "task": {"id": "t_demo", "body": TASK_BODY},
            "comments": [{"author": "flow-model-policy", "body": LEGACY_COMMENT}],
        }
        env = transition_env(fake, log, payload)
        result = invoke(["changes-return"], env)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        calls = log.read_text(encoding="utf-8")
        expected = "kanban --board demo set-model t_demo gpt-5.6-terra --provider openai-codex"
        if expected not in calls:
            raise AssertionError(calls)


def test_migrate_existing_coder_applies_model_and_writes_snapshot_comment() -> None:
    with tempfile.TemporaryDirectory(prefix="flow-model-policy-migrate-") as temp_dir:
        root = Path(temp_dir)
        fake, log = write_fake_hermes(root)
        payload = {
            "task": {
                "id": "t_demo",
                "status": "blocked",
                "body": "legacy task without model policy",
                "model_override": None,
                "provider_override": None,
            },
            "comments": [],
        }
        env = transition_env(fake, log, payload)
        result = invoke(["migrate-existing", "--tier", "DEFAULT", "--lane", "coder"], env)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        for term in (
            "STATUS=legacy-task-migrated",
            "SNAPSHOT_SOURCE=durable-comment",
            "MODEL_TIER=DEFAULT",
        ):
            if term not in result.stdout:
                raise AssertionError(result.stdout)
        calls = log.read_text(encoding="utf-8")
        if "kanban --board demo set-model t_demo gpt-5.6-terra --provider openai-codex" not in calls:
            raise AssertionError(calls)
        if "kanban --board demo comment t_demo MODEL_POLICY_SNAPSHOT_V1" not in calls:
            raise AssertionError(calls)


def test_migrate_existing_terminal_task_fails_without_mutation() -> None:
    with tempfile.TemporaryDirectory(prefix="flow-model-policy-terminal-") as temp_dir:
        root = Path(temp_dir)
        fake, log = write_fake_hermes(root)
        payload = {
            "task": {
                "id": "t_demo",
                "status": "done",
                "body": "legacy task",
                "model_override": None,
                "provider_override": None,
            },
            "comments": [],
        }
        env = transition_env(fake, log, payload)
        result = invoke(["migrate-existing", "--tier", "DEFAULT", "--lane", "coder"], env)
        if result.returncode == 0:
            raise AssertionError("terminal task migration must fail")
        calls = log.read_text(encoding="utf-8")
        if "set-model" in calls or " comment " in calls:
            raise AssertionError(calls)


def test_migrate_existing_comment_failure_rolls_back_override() -> None:
    with tempfile.TemporaryDirectory(prefix="flow-model-policy-rollback-") as temp_dir:
        root = Path(temp_dir)
        fake, log = write_fake_hermes(root)
        payload = {
            "task": {
                "id": "t_demo",
                "status": "blocked",
                "body": "legacy task",
                "model_override": "old-model",
                "provider_override": "old-provider",
            },
            "comments": [],
        }
        env = transition_env(fake, log, payload)
        env["HERMES_TEST_FAIL_COMMENT"] = "1"
        result = invoke(["migrate-existing", "--tier", "DEFAULT", "--lane", "coder"], env)
        if result.returncode == 0:
            raise AssertionError("comment failure must fail migration")
        calls = log.read_text(encoding="utf-8")
        if "kanban --board demo set-model t_demo old-model --provider old-provider" not in calls:
            raise AssertionError(calls)


def test_invalid_reviewer_contract_fails_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="flow-model-policy-invalid-") as temp_dir:
        root = Path(temp_dir)
        bad_body = TASK_BODY.replace("Reviewer Model: DEFAULT", "Reviewer Model: PREMIUM")
        fake, log = write_fake_hermes(root)
        env = transition_env(fake, log, {"task": {"id": "t_demo", "body": bad_body}, "comments": []})
        result = invoke(["changes-return"], env)
        if result.returncode == 0:
            raise AssertionError("invalid reviewer model contract must fail")
        if "Reviewer Model must be DEFAULT" not in result.stderr:
            raise AssertionError(result.stderr)


def main() -> int:
    test_resolve_uses_environment_snapshot()
    test_review_enter_clears_override()
    test_changes_return_restores_task_body_snapshot_not_current_env()
    test_changes_return_prefers_legacy_comment_snapshot()
    test_migrate_existing_coder_applies_model_and_writes_snapshot_comment()
    test_migrate_existing_terminal_task_fails_without_mutation()
    test_migrate_existing_comment_failure_rolls_back_override()
    test_invalid_reviewer_contract_fails_closed()
    print("[PASS] flow model policy tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
