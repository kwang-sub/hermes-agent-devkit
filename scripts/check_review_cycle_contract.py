#!/usr/bin/env python3
"""Verify coder/reviewer risk-based review-cycle copies and transition invariants."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODER_CYCLE = ROOT / "custom-skills/coder/dev-review-cycle/SKILL.md"
REVIEWER_CYCLE = ROOT / "custom-skills/reviewer/dev-review-cycle/SKILL.md"
CODER_PROTOCOL = ROOT / "custom-skills/coder/dev-review-cycle/references/review-protocol.md"
REVIEWER_PROTOCOL = ROOT / "custom-skills/reviewer/dev-review-cycle/references/review-protocol.md"
IMPLEMENT = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"
REVIEW = ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md"
FAST = ROOT / "custom-skills/coder/dev-fast-flow/SKILL.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(path: Path, terms: tuple[str, ...], failures: list[str]) -> None:
    text = read(path)
    missing = [term for term in terms if term not in text]
    if missing:
        failures.append(f"{path.relative_to(ROOT)} missing: {', '.join(missing)}")


def main() -> int:
    failures: list[str] = []

    if read(CODER_CYCLE) != read(REVIEWER_CYCLE):
        failures.append("coder/reviewer dev-review-cycle/SKILL.md copies differ")
    if read(CODER_PROTOCOL) != read(REVIEWER_PROTOCOL):
        failures.append("coder/reviewer review-protocol.md copies differ")

    for path in (CODER_CYCLE, REVIEWER_CYCLE):
        require(path, (
            "Fast LOW", "REVIEW_REQUIRED", "kanban_complete", "kanban_request_review",
            "kanban_request_changes", "kanban_block", "CHANGES_REQUESTED", "original coder",
            "Standard Flow", "LOW 근거 없는", "source를 수정하지 않고", "no commit/push",
        ), failures)

    for path in (CODER_PROTOCOL, REVIEWER_PROTOCOL):
        require(path, (
            "Fast Flow", "Standard Flow", "Review Risk LOW", "review_skipped=true",
            "CHANGES_REQUESTED", "original coder", "동일 Workspace", "kanban_complete",
            "kanban_request_review", "kanban_request_changes", "kanban_block",
            "Standard Flow Coder self-complete", "publication = no commit/push/PR",
        ), failures)

    require(FAST, (
        "Review Policy: RISK_BASED", "LOW", "REVIEW_REQUIRED", "CHANGES_REQUESTED",
        "kanban_complete", "kanban_request_review",
    ), failures)

    require(IMPLEMENT, (
        "Flow: FAST", "Review Risk", "LOW", "REVIEW_REQUIRED", "kanban_complete",
        "kanban_request_review", "Standard Flow", "CHANGES_REQUESTED", "original coder",
        "동일 Workspace", "review 대용", "BLOCKED",
    ), failures)

    require(REVIEW, (
        "source를 수정하지 않는다", "kanban_request_changes", "kanban_complete",
        "kanban_block` 중 정확히 하나", "CHANGES_REQUESTED는 terminal 상태가 아니며",
        "original coder", "같은 Workspace", "needs_input", "Review Risk: LOW",
    ), failures)

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    print("[PASS] risk-based review-cycle copies and transition invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
