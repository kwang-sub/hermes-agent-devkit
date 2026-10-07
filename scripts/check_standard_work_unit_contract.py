#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "shared/references/standard-work-unit-rules.md"
BREAKDOWN = ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md"
WORKFLOW = ROOT / "custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md"
DISPATCH = ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md"
IMPLEMENT = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"
IMPLEMENT_DETAILS = ROOT / "custom-skills/coder/dev-implement-plan/references/implementation-details.md"
REVIEW = ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md"
DATA = ROOT / "custom-skills/shared/dev-data-feature/SKILL.md"
MODELING = ROOT / "custom-skills/shared/dev-data-modeling/SKILL.md"
MIGRATION = ROOT / "custom-skills/shared/dev-db-migration/SKILL.md"
PARENT = ROOT / "shared/references/parent-tracking-rules.md"
SESSION = ROOT / "shared/references/session-history-rules.md"
RELATION_PREVIEW = ROOT / "scripts/patch_hermes_kanban_relation_preview.py"


def text(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"missing standard work unit file: {path}")
    return path.read_text(encoding="utf-8-sig")


def require(path: Path, terms: tuple[str, ...]) -> None:
    body = text(path)
    missing = [term for term in terms if term not in body]
    if missing:
        raise SystemExit(f"{path.relative_to(ROOT)} missing work-unit terms: {', '.join(missing)}")


def main() -> int:
    common = (
        "Work Unit Class",
        "Work Unit Boundary",
        "Current Deliverable",
        "Follow-up Required",
        "Follow-up Work Unit",
        "Follow-up Input",
        "Excluded Follow-up Scope",
    )

    require(REFERENCE, common + (
        "DESIGN", "IMPLEMENTATION", "MIGRATION", "REFACTOR", "AUDIT",
        "여러 Skill 사용 != Task 분리",
        "logical model과 physical DB 구현은 항상 별도 Standard Task",
        "후속 Work Unit을 같은 Plan 승인으로 자동 dispatch하지 않는다",
        "Verification Contract", "Verification Provider", "환경 의존 검증",
    ))

    require(PARENT, (
        "Parent Tracking Mode", "NEW_PARENT", "LINK_EXISTING_PARENT", "PROMOTE_TO_PARENT",
        "[부모]", "[자식]", "Parent Task ID", "Execution: NON_DISPATCH",
        "Job ID", "Implementation Summary", "Session IDs", "Parent Session 추적", "전체 하위 카드를 미리 생성하지 않는다",
        "다음 Child를 자동 dispatch하지 않는다",
        "kanban_create.parents", "Execution Ordering", "Depends On Task IDs",
        "Parent Task ID", "Relation: CHILD_WORK_UNIT",
        "PARENT_TRACKING_METADATA_MISMATCH", "NATIVE_PARENT_LINK_PRESENT",
        "LEGACY_NATIVE_PARENT_LINK", "구조적 Parent Tracking에 사용하지 않는다",
        "native task_links: NONE",
    ))

    require(SESSION, (
        "TASK_SESSION_HISTORY", "append-only", "일반 단일 카드", "[자식]", "[부모]",
        "devkit-task-session-history.db", "UNAVAILABLE", "Session ID를 추측하지 않는다",
    ))

    require(RELATION_PREVIEW, (
        "DEVKIT_KANBAN_RELATION_PREVIEW_API_V2",
        "_devkit_tracking_parent_id",
        "Parent Task ID",
        "CHILD_WORK_UNIT",
        "Native task_links are Hermes execution dependencies",
        "SELECT id, title, status, body FROM tasks ORDER BY id",
        "t.relation_preview.progress",
    ))
    if "Native task_links stays authoritative" in text(RELATION_PREVIEW):
        raise SystemExit("Kanban relation preview must not treat native task_links as DevKit tracking hierarchy")

    require(BREAKDOWN, common + (
        "Implementation Tasks를 만들기 전에 Work Unit Class/Boundary를 확정",
        "Data DESIGN → MIGRATION 강제 분리",
        "dev-db-migration",
        "별도 Standard Flow",
        "API Spec Gate",
        "별도 Work Unit",
        "🛠️ **실행 계획**", "🧪 **검증 계획**", "환경 의존 검증",
        "Verification Provider", "Fallback Policy",
        "Parent Tracking Recommendation", "Parent Tracking Reason", "[부모]", "[자식]",
    ))

    require(WORKFLOW, common + (
        "WORK_UNIT_CLASSIFIED",
        "AUTO_DISPATCH_CURRENT_UNIT_ONLY",
        "현재 Task DONE",
        "별도 Standard Flow",
        "SAME_TASK_RESUME",
        "FOLLOW_UP_TASK",
        "PLAN_APPROVED", "Execution + Verification Contract approved", "실행·검증 계획 승인",
        "환경 의존 검증", "provider를 임의 변경하거나 fallback하지 않는다",
        "Gate 전이 불변식", "IMMEDIATE_CLARIFY",
        "Project/API Spec/Workspace/Branch/Existing Changes/Coder Model/Plan/Requirement Delta",
        "설명만 출력하고 사용자의 `네`, `진행해주세요`, `계속해주세요`를 기다린 뒤 다음 turn에서 Gate를 띄우는 흐름은 금지",
        "구현 요약:", "PLAN_READY", "최대 2문장",
        "repository-wide/exhaustive impact analysis", "Bounded Pre-Mutation Impact Scan",
        "PARENT_TRACKING_CLASSIFIED", "작업 관리 방식 승인", "NEW_PARENT", "LINK_EXISTING_PARENT", "PROMOTE_TO_PARENT", "[부모]", "[자식]",
        "kanban_create.parents", "Execution Ordering", "Depends On Task IDs",
        "Parent Task ID", "Relation: CHILD_WORK_UNIT", "native `parents`는 실행 dependency",
    ))

    require(DISPATCH, common + (
        "Work Unit Contract 없는 Standard Task dispatch",
        "Follow-up Work Unit 자동 Kanban 생성/dispatch",
        "Follow-up capability를 현재 Applicable Skills에 자동 추가",
        "dev-db-migration",
        "Verification Contract", "Verification Provider", "Verification Approval: APPROVED",
        "Parent Tracking Dispatch 계약", "Execution: NON_DISPATCH", "Parent Task ID", "[부모]", "[자식]", "Job ID", "Implementation Summary",
        "kanban_create.parents", "Execution Ordering", "Depends On Task IDs",
        "parents=[]", "PARENT_TRACKING_METADATA_MISMATCH", "NATIVE_PARENT_LINK_PRESENT",
        "EXECUTION_DEPENDENCY_PENDING", "legacy `kanban_create.parents` 카드",
        "Session History 계약", "TASK_SESSION_HISTORY", "UNAVAILABLE",
    ))

    require(IMPLEMENT, common + (
        "Work Unit Boundary Gate",
        "WORK_UNIT_BOUNDARY_EXCEEDED",
        "STOP at DESIGN boundary",
        "dev-db-migration",
        "### AUDIT",
        "application/test/config source를 수정하지 않는다",
        "Work Unit Boundary Respected: true",
        "Standard Flow Verification Contract Gate", "VERIFICATION_PROVIDER_UNAVAILABLE",
        "Session History Gate", "task_session_history.py capture", "TASK_SESSION_HISTORY", "kanban_comment",
        "Bounded Pre-Mutation Impact Scan", "최대 2-hop", "Impact Summary", "Reference Lazy-Load",
    ))

    require(IMPLEMENT_DETAILS, (
        "Bounded Pre-Mutation Impact Scan",
        "Task Snapshot",
        "1-hop",
        "2-hop",
        "IMPACT_SUMMARY",
        "inline `python3 -c`",
        "discovery 목적으로 `kanban_show`를 반복하지 않는다",
    ))

    require(REVIEW, common + (
        "Standard Work Unit Review Gate",
        "Flyway/Liquibase migration",
        "AUDIT Task",
        "application/test/config source mutation",
        "여러 Skill 사용 자체를 split finding으로 만들지 않는다",
        "Follow-up Work Unit을 현재 Task에 구현하도록 요구하지 않는다",
        "Session History Review Gate", "TASK_SESSION_HISTORY", "kanban_comment", "IMPACT_SUMMARY",
    ))

    require(DATA, common + (
        "Standard Work Unit Boundary",
        "Logical Design Task",
        "Physicalization Task",
        "DESIGN Task가 DONE되어도 후속 MIGRATION Task를 자동 생성하거나 dispatch하지 않는다",
        "별도 Standard Flow",
        "MIGRATION",
    ))

    require(MODELING, common + (
        "Work Unit Class: DESIGN",
        "별도 Standard MIGRATION Work Unit",
        "DBML materialization",
        "DESIGN Task 종료",
    ))

    require(MIGRATION, (
        "Work Unit Class: MIGRATION",
        "Work Unit Boundary: SINGLE_UNIT",
        "`DESIGN` Work Unit",
        "새 `DESIGN` Work Unit",
        "APPROVED DBA Logical Model",
    ))

    print("PASS: Standard Flow single Work Unit + parent tracking + session history contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
