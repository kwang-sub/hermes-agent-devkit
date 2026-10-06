#!/usr/bin/env python3
"""Prevent Standard/Direct/Recovery session-capture policy divergence."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = "SESSION_HISTORY_BEST_EFFORT_V1"
FINALIZE = "SESSION_HISTORY_FINALIZE"
REFERENCE = "shared/references/session-history-rules.md"
CODER = "custom-skills/coder/dev-implement-plan/SKILL.md"
REVIEWER = "custom-skills/reviewer/dev-code-review/SKILL.md"
CYCLE = "custom-skills/{role}/dev-review-cycle/SKILL.md"


def require(root: Path, path: str, terms: tuple[str, ...]) -> str:
    source = (root / path).read_text(encoding="utf-8")
    missing = [term for term in terms if term not in source]
    if missing:
        raise AssertionError(f"{path}: missing {missing}")
    return source


def check_workers(root: Path) -> None:
    require(root, REFERENCE, (
        POLICY, FINALIZE, "Standard / Direct / Recovery / CHANGES_REQUESTED",
        "unavailable", "TASK_SESSION_HISTORY_WARNING", "STATE_DB_MISSING", "SESSION_MATCH_NOT_FOUND",
        "SESSION_HISTORY_COMMENT_PENDING", "ack-comment", "0.5초", "최대 3회", "1회 조회",
        "VERIFICATION_PROVIDER_UNAVAILABLE", "terminal transition 후", "백그라운드",
        "devkit-task-session-history.db", "task_session_history_comments",
        "error` (exit 0)", "SESSION_HISTORY_RECHECK_REQUIRED=true",
        "시작 capture의 `unavailable/error`에서는 durable warning comment를 만들지 않는다",
        "finalize에서도 `unavailable/error`이거나 marker/receipt 보완이 실패하면 그때만",
    ))
    common = (POLICY, FINALIZE, "session-history-rules.md", "--phase start", "--phase finalize",
              "SESSION_HISTORY_COMMENT_PENDING", "TASK_SESSION_HISTORY_WARNING", "ack-comment",
              "--session-id", "unavailable", "error", "invalid")
    coder = require(root, CODER, common + ("--profile coder", "--profile-home /opt/data/profiles/coder",
                                          "kanban_request_review", "VERIFICATION_PROVIDER_UNAVAILABLE"))
    reviewer = require(root, REVIEWER, common + ("--profile reviewer", "--profile-home /opt/data/profiles/reviewer",
                                                "kanban_complete", "kanban_request_changes", "kanban_block"))
    old_rules = (
        "Session ID를 추측하지 않고 mutation 전에 capability blocker로 종료한다",
        "Session ID를 확인할 수 없거나 comment 기록이 실패하면 review mutation 전에 capability blocker로 종료한다",
        "Session History가 enabled된 DevKit에서 기록 없이 구현을 진행하지 않는다",
        "captured marker 기록/receipt가 실패하면 기존 capability 오류 처리로 mutation 전에 중단한다",
        "captured marker·receipt 기록 오류는 기존 capability 오류로 source mutation 전에 중단한다",
        "captured marker·receipt 기록 오류는 기존 capability 오류로 review mutation 전에 중단한다",
        "`error` (exit 3)",
        "`unavailable`: `TASK_SESSION_HISTORY_WARNING`을 한 번 남기고 review를 계속한다",
        "`SESSION_HISTORY_STATUS=unavailable`: `TASK_SESSION_HISTORY_WARNING`을 한 번 기록하고 계속한다",
    )
    reference = (root / REFERENCE).read_text(encoding="utf-8")
    for rule in old_rules:
        if rule in coder + reviewer + reference:
            raise AssertionError(f"obsolete hard-block rule: {rule}")
    execution = coder.split("## 실행 순서", 1)[1].split("```", 2)[1]
    if execution.index(FINALIZE) > execution.index("kanban_request_review"):
        raise AssertionError("coder must finalize before transferring ownership")
    review_execution = reviewer.split("## 실행 계약", 1)[1].split("## Session History", 1)[0]
    if FINALIZE not in review_execution:
        raise AssertionError("review verdict must finalize pending traceability")
    cycles = [require(root, CYCLE.format(role=role), (POLICY, FINALIZE, "kanban_comment", "ack-comment",
               "kanban_request_review", "kanban_complete", "kanban_request_changes", "kanban_block"))
              for role in ("coder", "reviewer")]
    if cycles[0] != cycles[1]:
        raise AssertionError("coder/reviewer review-cycle copies differ")


def main() -> int:
    check_workers(ROOT)
    # These entrypoints must continue using the canonical workers, not a
    # private Direct or Recovery session policy.
    require(ROOT, "custom-skills/orchestrator/dev-direct-flow/SKILL.md", (
        'skill_view("dev-workspace-dispatch")', "Flow: DIRECT", "canonical dispatch", "dev-implement-plan", "dev-code-review",
    ))
    require(ROOT, "custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md", (
        "dev-workspace-dispatch", "coder ↔ reviewer", "SAME_TASK_RESUME",
    ))
    require(ROOT, "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md", (
        "session-history-rules.md", "task_session_history.py capture", "TASK_SESSION_HISTORY",
    ))
    require(ROOT, "custom-skills/orchestrator/dev-task-recovery/SKILL.md", (
        "SAME_TASK_RESUME", "RECOVERY_GATE_COUNT=3", "새 Task ID 생성 금지",
    ))
    print("PASS: Standard/Direct/Recovery bounded session capture and pre-transition finalization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
