#!/usr/bin/env python3
"""Report entrypoint context budgets and verify compact policy invariants."""
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
        "FAST_FLOW_ESCALATION_REQUIRED", "secret", "commit", "push", "한국어",
    ],
    "shared/AGENTS.common.md": [
        "Orchestrator", "Coder", "Reviewer", "Fast Flow", "Standard Flow",
        "FAST_FLOW_ESCALATION_REQUIRED", "secret", "commit", "push", "한국어",
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
    ],
    "custom-skills/coder/dev-implement-plan/SKILL.md": [
        "Workspace", "Reviewer Profile", "Flow: FAST", "FAST_FLOW_ESCALATION_REQUIRED",
        "secret", "commit", "push", "BLOCKED",
    ],
    "custom-skills/reviewer/dev-code-review/SKILL.md": [
        "Reviewer", "source를 수정하지", "secret", "commit", "push", "BLOCKED",
    ],
}

def chars(rel: str) -> int:
    return len((ROOT / rel).read_text(encoding="utf-8"))

def main() -> int:
    failed = False
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
        print("[FAIL] AGENTS.md common block differs from shared/AGENTS.common.md")
        failed = True
    for rel, terms in REQUIRED.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        missing = [term for term in terms if term not in text]
        if missing:
            print(f"[FAIL] {rel}: missing invariants: {', '.join(missing)}")
            failed = True
    refs = [
        "shared/references/common-agent-rules.md",
        "custom-skills/orchestrator/dev-workflow-orchestrate/references/workflow-details.md",
        "custom-skills/orchestrator/dev-breakdown/references/planning-details.md",
        "custom-skills/coder/dev-implement-plan/references/implementation-details.md",
        "custom-skills/reviewer/dev-code-review/references/review-details.md",
        "custom-skills/coder/dev-review-cycle/references/review-protocol.md",
        "custom-skills/reviewer/dev-review-cycle/references/review-protocol.md",
    ]
    missing_refs = [rel for rel in refs if not (ROOT / rel).is_file()]
    if missing_refs:
        print(f"[FAIL] Missing detail references: {', '.join(missing_refs)}")
        failed = True
    else:
        preserved = {
            "shared/references/common-agent-rules.md": BASELINES["shared/AGENTS.common.md"],
            "custom-skills/orchestrator/dev-workflow-orchestrate/references/workflow-details.md": BASELINES["custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md"],
            "custom-skills/orchestrator/dev-breakdown/references/planning-details.md": BASELINES["custom-skills/orchestrator/dev-breakdown/SKILL.md"],
            "custom-skills/coder/dev-implement-plan/references/implementation-details.md": BASELINES["custom-skills/coder/dev-implement-plan/SKILL.md"],
            "custom-skills/reviewer/dev-code-review/references/review-details.md": BASELINES["custom-skills/reviewer/dev-code-review/SKILL.md"],
            "custom-skills/coder/dev-review-cycle/references/review-protocol.md": BASELINES["custom-skills/coder/dev-review-cycle/SKILL.md"],
            "custom-skills/reviewer/dev-review-cycle/references/review-protocol.md": BASELINES["custom-skills/reviewer/dev-review-cycle/SKILL.md"],
        }
        for rel, minimum in preserved.items():
            size = chars(rel)
            if size < minimum:
                print(f"[FAIL] {rel}: detailed policy is smaller than preserved baseline ({size} < {minimum})")
                failed = True
    if len(agents) > 20_000:
        print(f"[WARN] AGENTS.md exceeds Hermes 20,000-character context cap: {len(agents)}")
    if failed:
        return 1
    print("[PASS] Context budget and compact policy invariants")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())