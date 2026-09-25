#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "custom-skills/orchestrator/dev-task-recovery/SKILL.md"
DETAILS = ROOT / "custom-skills/orchestrator/dev-task-recovery/references/recovery-details.md"
INVENTORY = ROOT / "custom-skills/orchestrator/dev-task-recovery/scripts/recovery_board_inventory.py"
INVENTORY_TEST = ROOT / "custom-skills/orchestrator/dev-task-recovery/tests/test_recovery_board_inventory.py"
WORKFLOW = ROOT / "custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md"
WORKFLOW_DETAILS = ROOT / "custom-skills/orchestrator/dev-workflow-orchestrate/references/workflow-details.md"
APPROVAL = ROOT / "shared/references/approval-gate-rules.md"
README = ROOT / "README.md"


def read_required(path: Path, label: str) -> str:
    if not path.is_file():
        raise SystemExit(f"missing {label}: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise SystemExit(f"empty {label}: {path.relative_to(ROOT)}")
    return text


def require(text: str, terms: tuple[str, ...], label: str) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{label} missing terms: {', '.join(missing)}")


def main() -> int:
    skill = read_required(SKILL, "dev-task-recovery skill")
    details = read_required(DETAILS, "dev-task-recovery details")
    inventory = read_required(INVENTORY, "recovery board inventory helper")
    read_required(INVENTORY_TEST, "recovery board inventory tests")
    workflow = read_required(WORKFLOW, "dev-workflow-orchestrate skill")
    workflow_details = read_required(WORKFLOW_DETAILS, "dev-workflow-orchestrate details")
    approval = read_required(APPROVAL, "approval gate rules")
    readme = read_required(README, "README")

    require(
        skill,
        (
            "name: dev-task-recovery",
            "RECOVERY_GATE_COUNT=3",
            "[보드 선택]",
            "[차단 카드 선택]",
            "[복구 계획 승인]",
            'status="blocked"',
            "kanban_list(",
            "kanban_show(",
            "kanban_comment(",
            "kanban_unblock(",
            "RETRY_SAME_CONTRACT",
            "SAME_TASK_RESUME",
            "REPLACEMENT_REQUIRED",
            "TASK_RECOVERY_RETRY_V1",
            "TASK_RECOVERY_REVISION_V1",
            "TASK_RECOVERY_ESCALATION_V1",
            "Revision Authority: LATEST_APPROVED_RECOVERY_REVISION",
            "Original Contract: PRESERVED",
            "kanban_create 금지",
            "새 Task ID 생성 금지",
            "triage",
            "references/recovery-details.md",
            "requires_tools: [terminal, skill_view, clarify, kanban_list, kanban_show, kanban_comment, kanban_unblock]",
        ),
        "dev-task-recovery skill",
    )

    gate_order = [
        skill.index("## 2. Gate 1"),
        skill.index("## 3. Gate 2"),
        skill.index("## 6. Gate 3"),
        skill.index("## 7. Gate 3 승인 후"),
        skill.index("## 8. Revision Read-back Gate"),
        skill.index("## 9. 같은 Task 재개"),
    ]
    if gate_order != sorted(gate_order):
        raise SystemExit("dev-task-recovery gate/read-back/unblock sections are out of order")

    require(
        details,
        (
            "BOARD_INVENTORY_READY",
            "BLOCKED_TASK_INVENTORY_READY",
            "RECOVERY_PLAN_APPROVED",
            "RECOVERY_STATUS=STALE_TASK_SELECTION",
            "RECOVERY_REVISION_NOT_PERSISTED",
            "KANBAN_UNBLOCK_FAILED",
            "task.status == blocked",
            "same Task ID 유지",
            "latest Recovery Revision",
            "raw status mutation",
        ),
        "dev-task-recovery details",
    )

    require(
        inventory,
        (
            '"kanban", "boards", "list", "--json"',
            "BOARD_INVENTORY_UNAVAILABLE",
            "parse_board_payload",
            "normalize_boards",
            "blocked_count",
            "archived",
            "DEFAULT_TIMEOUT_SECONDS = 15",
        ),
        "recovery board inventory helper",
    )
    if '"switch"' in inventory or "boards switch" in inventory:
        raise SystemExit("recovery board inventory helper must not mutate the active board")

    require(
        workflow,
        (
            "dev-task-recovery",
            "Blocked Task Recovery 진입",
            'skill_view("dev-task-recovery")',
            "[보드 선택]",
            "[차단 카드 선택]",
            "[복구 계획 승인]",
            "정확히 3-Gate",
            "SAME_TASK_RESUME",
            "REPLACEMENT_REQUIRED",
        ),
        "dev-workflow-orchestrate recovery routing",
    )

    require(
        workflow_details,
        (
            "Blocked Task Recovery 전용 진입",
            "RECOVERY_ENTRY",
            "durable Recovery Revision",
            "Recovery-specific 승인 예외",
            "task.status == blocked",
            "same Task ID 유지",
            "REPLACEMENT_REQUIRED",
        ),
        "dev-workflow-orchestrate recovery details",
    )

    require(
        approval,
        (
            "Blocked Task Recovery Flow — 정확히 3 Gate",
            "RECOVERY_GATE_COUNT=3",
            "Gate 1 BOARD_APPROVAL",
            "Gate 2 BLOCKED_TASK_APPROVAL",
            "Gate 3 RECOVERY_PLAN_APPROVAL",
            "Recovery Mode == RETRY_SAME_CONTRACT | SAME_TASK_RESUME",
            "REPLACEMENT_REQUIRED",
            "같은 Task ID",
        ),
        "approval gate recovery contract",
    )

    require(
        readme,
        (
            "## 9.3 Task Recovery Flow",
            "dev-task-recovery",
            "[보드 선택]",
            "[차단 카드 선택]",
            "[복구 계획 승인]",
            "SAME_TASK_RESUME",
        ),
        "README recovery guide",
    )

    print("[PASS] blocked Task Recovery 3-gate / durable revision / same-task resume contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
