#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "shared/references/standard-work-unit-rules.md"
BREAKDOWN = ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md"
WORKFLOW = ROOT / "custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md"
DISPATCH = ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md"
IMPLEMENT = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"
REVIEW = ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md"
DATA = ROOT / "custom-skills/shared/dev-data-feature/SKILL.md"
MODELING = ROOT / "custom-skills/shared/dev-data-modeling/SKILL.md"
MIGRATION = ROOT / "custom-skills/shared/dev-db-migration/SKILL.md"


def require(path: Path, terms: tuple[str, ...]) -> None:
    if not path.is_file():
        raise SystemExit(f"missing standard work unit file: {path}")
    text = path.read_text(encoding="utf-8-sig")
    missing = [term for term in terms if term not in text]
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
        "DESIGN",
        "IMPLEMENTATION",
        "MIGRATION",
        "REFACTOR",
        "AUDIT",
        "여러 Skill 사용 != Task 분리",
        "Data `DESIGN_FIRST` logical model과 physical DB 구현은 항상 별도 Standard Task",
        "후속 Work Unit을 같은 Plan 승인으로 자동 dispatch하지 않는다",
    ))

    require(BREAKDOWN, common + (
        "Implementation Tasks를 만들기 전에 Work Unit Class/Boundary를 확정",
        "Data DESIGN → MIGRATION 강제 분리",
        "현재 DESIGN Plan의 Applicable Skills/Implementation Tasks에 `dev-db-migration`을 넣지 않는다",
        "후속 physical implementation 요청은 별도 Standard Flow",
        "API Spec Gate 자체는 별도 Work Unit을 자동 의미하지 않는다",
    ))

    require(WORKFLOW, common + (
        "WORK_UNIT_CLASSIFIED",
        "AUTO_DISPATCH_CURRENT_UNIT_ONLY",
        "현재 Task DONE",
        "사용자가 별도 Standard Flow로 후속 Work Unit 요청",
        "SAME_TASK_RESUME",
        "FOLLOW_UP_TASK",
    ))

    require(DISPATCH, common + (
        "Work Unit Contract 없는 Standard Task dispatch",
        "Follow-up Work Unit 자동 Kanban 생성/dispatch",
        "Follow-up capability를 현재 Applicable Skills에 자동 추가",
        "follow-up 전용 dev-db-migration",
    ))

    require(IMPLEMENT, common + (
        "Standard Work Unit Boundary Gate",
        "WORK_UNIT_BOUNDARY_EXCEEDED",
        "STOP at DESIGN boundary",
        "같은 Task에서 `dev-db-migration`",
        "AUDIT Task에서 application/test/config source",
        "Work Unit Boundary Respected: true",
    ))

    require(REVIEW, common + (
        "Standard Work Unit Review Gate",
        "Flyway/Liquibase migration",
        "AUDIT Task에서 application/test/config source mutation",
        "여러 Skill 사용 자체를 split finding으로 만들지 않는다",
        "Follow-up Work Unit을 현재 Task에 구현하도록 요구하지 않는다",
    ))

    require(DATA, common + (
        "Standard Work Unit Boundary",
        "Logical Design Task",
        "Physicalization Task",
        "DESIGN Task가 DONE되어도 후속 MIGRATION Task를 자동 생성하거나 dispatch하지 않는다",
        "별도 Standard Flow MIGRATION Task",
    ))

    require(MODELING, common + (
        "Work Unit Class: DESIGN",
        "별도 Standard MIGRATION Work Unit",
        "승인된 DBML materialization 후 DESIGN Task 종료",
    ))

    require(MIGRATION, (
        "Work Unit Class: MIGRATION",
        "Work Unit Boundary: SINGLE_UNIT",
        "DESIGN Work Unit에서 이 Skill을 실행",
        "새 `DESIGN` Work Unit",
        "APPROVED DBA Logical Model",
    ))

    print("PASS: Standard Flow single Work Unit boundary contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
