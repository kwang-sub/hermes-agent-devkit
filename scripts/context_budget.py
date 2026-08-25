#!/usr/bin/env python3
"""Report entrypoint budgets and verify compact policy invariants."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINES = {
    "AGENTS.md": 17676,
    "shared/AGENTS.common.md": 17016,
    "custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md": 9611,
    "custom-skills/orchestrator/dev-breakdown/SKILL.md": 12170,
    "custom-skills/coder/dev-implement-plan/SKILL.md": 5434,
    "custom-skills/reviewer/dev-code-review/SKILL.md": 4836,
    "custom-skills/coder/dev-review-cycle/SKILL.md": 3300,
    "custom-skills/reviewer/dev-review-cycle/SKILL.md": 3300,
}

REQUIRED = {
    "AGENTS.md": [
        "Orchestrator", "Coder", "Reviewer", "Fast Flow", "Standard Flow",
        "FAST_FLOW_ESCALATION_REQUIRED", "공통 코드 품질", "2-depth",
        "Stack/Capability Skill", "secret", "commit", "push", "한국어",
        "Review Policy: RISK_BASED", "REVIEW_REQUIRED",
    ],
    "shared/AGENTS.common.md": [
        "Orchestrator", "Coder", "Reviewer", "Fast Flow", "Standard Flow",
        "FAST_FLOW_ESCALATION_REQUIRED", "공통 코드 품질", "2-depth",
        "Stack/Capability Skill", "secret", "commit", "push", "한국어",
        "Review Policy: RISK_BASED", "REVIEW_REQUIRED",
    ],
    "custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md": [
        "Project Approval", "Plan Approval", "Workspace / Branch", "dev-workspace-dispatch",
        "Base SHA", "coder", "reviewer", "READY", "BLOCKED", "commit", "push", "한국어",
    ],
    "custom-skills/orchestrator/dev-breakdown/SKILL.md": [
        "Plan Approval", "Workspace / Branch", "READY", "BLOCKED", "coder", "한국어", "commit", "push",
    ],
    "custom-skills/coder/dev-fast-flow/SKILL.md": [
        "Fast Flow", "Kanban", "coder", "reviewer", "clean", "current branch",
        "FAST_FLOW_ESCALATION_REQUIRED", "Standard Flow", "commit", "push",
        "Review Policy: RISK_BASED", "LOW", "REVIEW_REQUIRED",
    ],
    "custom-skills/coder/dev-implement-plan/SKILL.md": [
        "Workspace", "Reviewer Profile", "Flow: FAST", "FAST_FLOW_ESCALATION_REQUIRED",
        "공통 Coding Rules 핵심", "2-depth", "Stack / Capability Skill", "coding-rules.md",
        "secret", "commit", "push", "BLOCKED", "Review Risk", "LOW", "REVIEW_REQUIRED",
    ],
    "custom-skills/reviewer/dev-code-review/SKILL.md": [
        "Reviewer", "source를 수정하지", "Common Coding Review Gate", "2-depth",
        "Stack / Capability Review Gate", "coding-rules.md", "secret", "commit", "push", "BLOCKED",
    ],
}

DETAIL_REQUIRED = {
    "custom-skills/coder/dev-implement-plan/references/implementation-details.md": [
        "Risk-based Review", "Review Risk: LOW", "REVIEW_REQUIRED", "review_skipped", "targeted",
        "Standard Flow", "CHANGES_REQUESTED", "kanban_request_review", "kanban_complete",
    ],
    "custom-skills/coder/dev-review-cycle/references/review-protocol.md": [
        "Fast Flow", "Standard Flow", "Review Risk LOW", "review_skipped=true",
        "CHANGES_REQUESTED", "kanban_request_review", "kanban_complete", "no commit/push/PR",
    ],
    "custom-skills/reviewer/dev-review-cycle/references/review-protocol.md": [
        "Fast Flow", "Standard Flow", "Review Risk LOW", "review_skipped=true",
        "CHANGES_REQUESTED", "kanban_request_review", "kanban_complete", "no commit/push/PR",
    ],
}

REFERENCES = [
    "shared/references/common-agent-rules.md",
    "shared/references/coding-rules.md",
    "shared/references/stack-capability-skill-guide.md",
    "custom-skills/orchestrator/dev-workflow-orchestrate/references/workflow-details.md",
    "custom-skills/orchestrator/dev-breakdown/references/planning-details.md",
    "custom-skills/coder/dev-implement-plan/references/implementation-details.md",
    "custom-skills/reviewer/dev-code-review/references/review-details.md",
    "custom-skills/coder/dev-review-cycle/references/review-protocol.md",
    "custom-skills/reviewer/dev-review-cycle/references/review-protocol.md",
]


def chars(rel: str) -> int:
    return len((ROOT / rel).read_text(encoding="utf-8"))


def require_terms(rel: str, terms: list[str], failures: list[str]) -> None:
    text = (ROOT / rel).read_text(encoding="utf-8")
    missing = [term for term in terms if term not in text]
    if missing:
        failures.append(f"{rel}: missing invariants: {', '.join(missing)}")


def main() -> int:
    failures: list[str] = []
    print("[INFO] Context/skill entrypoint character budget")
    for rel, before in BASELINES.items():
        now = chars(rel)
        delta = now - before
        pct = now / before * 100
        print(f"[SIZE] {rel}: {before} -> {now} ({delta:+d}, {pct:.1f}% of baseline)")
        if now >= before:
            print(f"[WARN] {rel}: entrypoint did not shrink")

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    common = (ROOT / "shared/AGENTS.common.md").read_text(encoding="utf-8").rstrip()
    start = agents.index("<!-- HERMES-COMMON:START -->")
    end = agents.index("<!-- HERMES-COMMON:END -->") + len("<!-- HERMES-COMMON:END -->")
    if agents[start:end].rstrip() != common:
        failures.append("AGENTS.md common block differs from shared/AGENTS.common.md")

    for rel, terms in REQUIRED.items():
        require_terms(rel, terms, failures)

    missing_refs = [rel for rel in REFERENCES if not (ROOT / rel).is_file()]
    if missing_refs:
        failures.append("Missing detail references: " + ", ".join(missing_refs))

    for rel, terms in DETAIL_REQUIRED.items():
        if (ROOT / rel).is_file():
            require_terms(rel, terms, failures)

    if len(agents) > 20_000:
        print(f"[WARN] AGENTS.md exceeds Hermes 20,000-character context cap: {len(agents)}")

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    print("[PASS] Context budget and compact policy invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
