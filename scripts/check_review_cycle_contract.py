#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODER_CYCLE = ROOT / "custom-skills/coder/dev-review-cycle/SKILL.md"
REVIEWER_CYCLE = ROOT / "custom-skills/reviewer/dev-review-cycle/SKILL.md"
CODER_PROTOCOL = ROOT / "custom-skills/coder/dev-review-cycle/references/review-protocol.md"
REVIEWER_PROTOCOL = ROOT / "custom-skills/reviewer/dev-review-cycle/references/review-protocol.md"
DIRECT = ROOT / "custom-skills/orchestrator/dev-direct-flow/SKILL.md"
IMPLEMENT = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"
REVIEW = ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md"
STANDARD = ROOT / "custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md"
DISPATCH = ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md"
MODEL_POLICY = ROOT / "custom-skills/shared/dev-flow-model-policy/SKILL.md"
MODEL_HELPER = ROOT / "shared/scripts/flow_model_policy.py"
APPROVAL_RULES = ROOT / "shared/references/approval-gate-rules.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(path: Path, terms: tuple[str, ...], failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"{path.relative_to(ROOT)} missing")
        return
    text = read(path)
    missing = [term for term in terms if term not in text]
    if missing:
        failures.append(f"{path.relative_to(ROOT)} missing: {', '.join(missing)}")


def forbid(path: Path, terms: tuple[str, ...], failures: list[str]) -> None:
    if not path.is_file():
        return
    text = read(path)
    present = [term for term in terms if term in text]
    if present:
        failures.append(f"{path.relative_to(ROOT)} contains removed terms: {', '.join(present)}")


def main() -> int:
    failures: list[str] = []

    if read(CODER_CYCLE) != read(REVIEWER_CYCLE):
        failures.append("coder/reviewer dev-review-cycle/SKILL.md copies differ")
    if read(CODER_PROTOCOL) != read(REVIEWER_PROTOCOL):
        failures.append("coder/reviewer review-protocol.md copies differ")

    for path in (CODER_CYCLE, REVIEWER_CYCLE):
        require(
            path,
            (
                "Direct/Standard 모두 구현 완료 후 Reviewer를 반드시 거친다",
                "kanban_complete",
                "kanban_request_review",
                "kanban_request_changes",
                "kanban_block",
                "CHANGES_REQUESTED",
                "original coder",
                "Direct/Standard Coder self-complete",
                "source 수정",
                "no commit/push",
            ),
            failures,
        )

    for path in (CODER_PROTOCOL, REVIEWER_PROTOCOL):
        require(
            path,
            (
                "Direct와 Standard Flow는 모두 Reviewer 필수",
                "kanban_complete",
                "kanban_request_review",
                "kanban_request_changes",
                "kanban_block",
                "CHANGES_REQUESTED",
                "original coder",
                "동일 Workspace",
                "Direct/Standard Coder self-complete",
                "publication = no commit/push/PR",
            ),
            failures,
        )

    require(
        DIRECT,
        (
            "Orchestrator 소유의 compact dispatch 경로",
            "[실행 방식 선택]",
            "[Coder 모델 선택]",
            "Flow: DIRECT",
            "Review Policy: REQUIRED",
            "dev-flow-model-policy",
            "Reviewer는 항상 DEFAULT",
            'skill_view("dev-workspace-dispatch")',
        ),
        failures,
    )

    require(
        STANDARD,
        (
            "/opt/data/shared/references/approval-gate-rules.md",
            "WORKSPACE_APPROVED",
            "BRANCH_APPROVED",
            "MODEL_APPROVED",
            "PLAN_APPROVED",
            "REQUIREMENT_DELTA_APPROVED",
            "Requirement Delta Approval",
            "[추가 요구사항 확인]",
            "clarify",
            "choices",
            "[Project 선택]",
            "[Workspace 선택]",
            "[Branch 선택]",
            "[Coder 모델 선택]",
            "[작업 계획 승인]",
            "DEFAULT | PREMIUM",
            "Reviewer Model은 항상 DEFAULT",
            "flow_model_policy.py resolve",
            "model=<MODEL>",
            "provider=<PROVIDER>",
            "dev-flow-model-policy",
            "Model Escalation: REQUIRE_REAPPROVAL",
            "기존 카드 재작업 계약",
            "Requirement Delta:",
            "Approval Reuse:",
            "migrate-existing",
            "STATUS=legacy-task-migrated",
            "SNAPSHOT_SOURCE=durable-comment",
            "신규/대체 Task 승인 불변식",
            "대체 카드 생성 승인",
            "서로 다른 승인 Gate를 한 질문으로 합치지 않는다",
            "NO_EXTRA_KANBAN_CONFIRMATION",
            "NOTIFICATION_SUBSCRIPTION_ATTEMPTED",
        ),
        failures,
    )

    require(
        APPROVAL_RULES,
        (
            "한 번의 사용자 확인에서는 하나의 의사결정만 요청한다",
            "clarify",
            "choices",
            "↑/↓ 이동 + Enter 선택",
            "Other (type your answer)",
            "Workspace와 Branch는 서로 다른 Gate다",
            "[추가 요구사항 확인]",
            "requirement_delta_approved",
            "Requirement Delta",
            "AUTO_DISPATCH",
            "NO_EXTRA_KANBAN_CONFIRMATION",
        ),
        failures,
    )

    require(
        DISPATCH,
        (
            "Coder Model Tier(DEFAULT|PREMIUM) 승인 완료",
            "model=MODEL",
            "provider=PROVIDER",
            "dev-flow-model-policy",
            "model_override == MODEL",
            "provider_override == PROVIDER",
            "review-enter",
            "changes-return",
            "Reviewer profile DEFAULT",
            "NOTIFY_STATUS=subscribed | disabled | warning",
            "Hermes native",
            "kanban_unblock tool 정확히 1회",
        ),
        failures,
    )

    forbid(
        DISPATCH,
        (
            "NOTIFY_REGISTRATION_EVENT",
            "registered task_event",
            "전달 ACK timeout",
            "최초 등록 알림",
        ),
        failures,
    )

    require(
        MODEL_POLICY,
        (
            "Direct/Standard Flow",
            "HERMES_FLOW_MODEL_DEFAULT_PROVIDER",
            "HERMES_FLOW_MODEL_DEFAULT",
            "HERMES_FLOW_MODEL_PREMIUM_PROVIDER",
            "HERMES_FLOW_MODEL_PREMIUM",
            "Reviewer Model: DEFAULT",
            "Model Escalation: REQUIRE_REAPPROVAL",
            "flow_model_policy.py review-enter",
            "flow_model_policy.py changes-return",
            "PREMIUM 자동 escalation은 금지",
            "MODEL_POLICY_SNAPSHOT_V1",
            "migrate-existing",
            "durable Kanban comment",
            "pre-policy Task라는 이유만으로 새 카드 생성을 강제하지 않는다",
        ),
        failures,
    )

    require(
        MODEL_HELPER,
        (
            "HERMES_FLOW_MODEL_",
            "review-enter",
            "changes-return",
            "set-model",
            "selection_from_task_payload",
            "Reviewer Model",
            "REQUIRE_REAPPROVAL",
            "migrate-existing",
            "MODEL_POLICY_SNAPSHOT_V1",
            "legacy-task-migrated",
            "durable-comment",
        ),
        failures,
    )

    require(
        IMPLEMENT,
        (
            "Flow: DIRECT",
            "Review Policy: REQUIRED",
            "DIRECT_SCOPE_EXCEEDED",
            "kanban_request_review",
            "Direct Flow, Standard Flow, CHANGES_REQUESTED 재작업은 모두 항상 review",
            "Direct/Standard Flow 모두 Coder self-complete 금지",
            "CHANGES_REQUESTED",
            "original coder",
            "동일 Workspace",
            "BLOCKED",
        ),
        failures,
    )

    require(
        REVIEW,
        (
            "source를 수정하지 않는다",
            "kanban_request_changes",
            "kanban_complete",
            "kanban_block` 중 정확히 하나",
            "같은 Workspace",
            "needs_input",
        ),
        failures,
    )

    for removed in (
        ROOT / "custom-skills/coder/dev-fast-flow",
        ROOT / "custom-skills/coder/dev-direct-flow",
    ):
        if removed.exists():
            failures.append(f"removed Coder flow still exists: {removed.relative_to(ROOT)}")

    forbid(CODER_CYCLE, ("Fast LOW", "Review Risk LOW"), failures)
    forbid(IMPLEMENT, ("## Flow: FAST", "Fast Flow는 LOW"), failures)

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    print("[PASS] Direct/Standard mandatory review, model-transition, requirement-delta approval, native notification, and auto-dispatch invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
