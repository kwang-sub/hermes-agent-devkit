#!/usr/bin/env python3
"""Verify coder/reviewer review-cycle copies and transition invariants."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODER_CYCLE = ROOT / "custom-skills/coder/dev-review-cycle/SKILL.md"
REVIEWER_CYCLE = ROOT / "custom-skills/reviewer/dev-review-cycle/SKILL.md"
CODER_PROTOCOL = ROOT / "custom-skills/coder/dev-review-cycle/references/review-protocol.md"
REVIEWER_PROTOCOL = ROOT / "custom-skills/reviewer/dev-review-cycle/references/review-protocol.md"
IMPLEMENT = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"
REVIEW = ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md"

COMMON_TERMS = (
    "kanban_request_review",
    "kanban_request_changes",
    "kanban_complete",
    "kanban_block",
    "CHANGES_REQUESTED",
    "original coder",
    "동일 Workspace",
    "needs_input",
    "no commit/push",
)
CYCLE_TERMS = COMMON_TERMS + (
    "허용 전이",
    "금지 전이",
    "source를 수정하지 않고",
    "정확히 하나",
    "terminal 상태가 아니다",
    "구현 완료 후 `kanban_block`",
    "Orchestrator",
)
PROTOCOL_TERMS = COMMON_TERMS + (
    "Coder가 구현 또는 수정 후 `kanban_complete`",
    "Reviewer가 application, test, config 또는 workflow source를 직접 수정",
    "동일한 중요한 blocker가 3 review cycle",
    "Workspace = remains",
    "CHANGES_REQUESTED는 original coder ready로 이어지는 비-terminal",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(path: Path, terms: tuple[str, ...], failures: list[str]) -> None:
    text = read(path)
    missing = [term for term in terms if term not in text]
    if missing:
        failures.append(f"{path.relative_to(ROOT)} missing: {", ".join(missing)}")


def main() -> int:
    failures: list[str] = []
    if read(CODER_CYCLE) != read(REVIEWER_CYCLE):
        failures.append("coder/reviewer dev-review-cycle/SKILL.md copies differ")
    if read(CODER_PROTOCOL) != read(REVIEWER_PROTOCOL):
        failures.append("coder/reviewer review-protocol.md copies differ")

    for path in (CODER_CYCLE, REVIEWER_CYCLE):
        require(path, CYCLE_TERMS, failures)
    for path in (CODER_PROTOCOL, REVIEWER_PROTOCOL):
        require(path, PROTOCOL_TERMS, failures)
    require(
        IMPLEMENT,
        (
            "kanban_request_review`만 호출한 뒤 멈춘다",
            "구현 완료 상태에서 `kanban_complete`",
            "review 대용 `kanban_block`",
            "CHANGES_REQUESTED",
            "original coder",
            "동일 Workspace",
        ),
        failures,
    )
    require(
        REVIEW,
        (
            "source를 수정하지 않는다",
            "kanban_request_changes",
            "kanban_complete",
            "kanban_block` 중 정확히 하나만 실행",
            "CHANGES_REQUESTED는 terminal 상태가 아니며",
            "original coder",
            "같은 Workspace",
            "needs_input",
        ),
        failures,
    )

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[PASS] dev-review-cycle copies and transition invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
