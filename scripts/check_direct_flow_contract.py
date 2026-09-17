#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: Path, terms: tuple[str, ...], failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing: {path.relative_to(ROOT)}")
        return ""
    text = path.read_text(encoding="utf-8")
    missing = [term for term in terms if term not in text]
    if missing:
        failures.append(f"{path.relative_to(ROOT)} missing: {', '.join(missing)}")
    return text


def forbid(text: str, label: str, terms: tuple[str, ...], failures: list[str]) -> None:
    present = [term for term in terms if term in text]
    if present:
        failures.append(f"{label} contains removed Fast/interactive contract: {', '.join(present)}")


def main() -> int:
    failures: list[str] = []

    direct = ROOT / "custom-skills/orchestrator/dev-direct-flow/SKILL.md"
    implement = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"
    model_policy = ROOT / "custom-skills/shared/dev-flow-model-policy/SKILL.md"
    coder_cycle = ROOT / "custom-skills/coder/dev-review-cycle/SKILL.md"
    reviewer_cycle = ROOT / "custom-skills/reviewer/dev-review-cycle/SKILL.md"
    common = ROOT / "shared/AGENTS.common.md"
    root_agents = ROOT / "AGENTS.md"

    for removed in (
        ROOT / "custom-skills/coder/dev-fast-flow",
        ROOT / "custom-skills/coder/dev-direct-flow",
    ):
        if removed.exists():
            failures.append(f"removed Coder execution entry still exists: {removed.relative_to(ROOT)}")

    direct_text = require(
        direct,
        (
            "Orchestrator 소유의 compact dispatch 경로",
            "Direct에서 생략하는 것은 `dev-breakdown`의 광범위한 planning 단계",
            "Work Unit Class = IMPLEMENTATION | REFACTOR",
            "Work Unit Boundary = SINGLE_UNIT",
            "API Spec Gate = NOT_REQUIRED",
            "Infrastructure Impact = NO",
            "[실행 방식 선택]",
            "[Coder 모델 선택]",
            "[작업 계획 승인]",
            "Workspace Approval Source: DIRECT_FIXED_CURRENT",
            "Branch Approval Source: DIRECT_FIXED_CURRENT",
            'skill_view("dev-workspace-dispatch")',
            "Flow: DIRECT",
            "Review Policy: REQUIRED",
            "Coder self-complete를 허용하지 않는다",
            "DIRECT_SCOPE_EXCEEDED",
            "Requirement Delta/Standard Flow",
        ),
        failures,
    )
    forbid(direct_text, "dev-direct-flow", ("FAST Flow", "dev-fast-flow", "Interactive Coder가 직접 수행"), failures)

    implement_text = require(
        implement,
        (
            "Coder는 새 mutation request의 실행 방식을 선택하거나 self-dispatch하지 않고",
            "Direct/Standard Task",
            "## Flow: DIRECT",
            "DIRECT_SCOPE_EXCEEDED",
            "Review Policy: REQUIRED",
            "Direct Flow, Standard Flow, CHANGES_REQUESTED 재작업은 모두 항상 review",
            "Direct/Standard Flow 모두 Coder self-complete 금지",
        ),
        failures,
    )
    forbid(implement_text, "dev-implement-plan", ("## Flow: FAST", "Fast Flow는 LOW", "FAST_FLOW_ESCALATION_REQUIRED"), failures)

    model_text = require(
        model_policy,
        (
            "Direct/Standard Flow",
            "Reviewer Model: DEFAULT",
            "Model Escalation: REQUIRE_REAPPROVAL",
            "Direct와 Standard 모두 Reviewer를 필수",
            "migrate-existing",
            "MODEL_POLICY_SNAPSHOT_V1",
            "kanban_request_review",
            "kanban_request_changes",
        ),
        failures,
    )
    forbid(model_text, "dev-flow-model-policy", ("Fast LOW self-complete", "신규 Standard/Fast dispatch"), failures)

    coder_cycle_text = require(
        coder_cycle,
        (
            "Direct/Standard 모두 구현 완료 후 Reviewer를 반드시 거친다",
            "kanban_request_review",
            "kanban_request_changes",
            "Direct/Standard Coder self-complete",
            "review-enter",
            "changes-return",
        ),
        failures,
    )
    reviewer_cycle_text = require(
        reviewer_cycle,
        (
            "Direct/Standard 모두 구현 완료 후 Reviewer를 반드시 거친다",
            "kanban_request_review",
            "kanban_request_changes",
            "Direct/Standard Coder self-complete",
        ),
        failures,
    )
    if coder_cycle_text and reviewer_cycle_text and coder_cycle_text != reviewer_cycle_text:
        failures.append("coder/reviewer dev-review-cycle copies differ")

    for path in (common, root_agents):
        text = require(
            path,
            (
                "Orchestrator: 모든 새 mutation request의 실행 진입점",
                "요청을 `DIRECT | STANDARD`로 분류",
                "Coder: **Kanban에 할당된 Task만** 구현",
                "Direct도 Kanban Task를 생성하고 Coder→Reviewer를 반드시 거친다",
                "Fast Flow는 신규 실행 경로로 사용하지 않는다",
            ),
            failures,
        )
        forbid(text, str(path.relative_to(ROOT)), ("DIRECT | FAST | STANDARD_REQUIRED", "Fast worker는", "Fast Flow에는 `Flow: FAST`"), failures)

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    print("[PASS] Orchestrator Direct/Standard routing and mandatory review contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
