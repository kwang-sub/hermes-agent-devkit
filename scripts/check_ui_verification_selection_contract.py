#!/usr/bin/env python3
"""Fail CI if UI scope-selection decisions drift from the canonical contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "policy": "shared/references/ui-verification-selection-policy.md",
    "level": "shared/references/verification-level-policy.md",
    "breakdown": "custom-skills/orchestrator/dev-breakdown/SKILL.md",
    "direct": "custom-skills/orchestrator/dev-direct-flow/SKILL.md",
    "frontend": "custom-skills/shared/dev-frontend-feature/SKILL.md",
    "test": "custom-skills/shared/dev-frontend-test/SKILL.md",
    "browser": "custom-skills/shared/dev-frontend-test/references/browser-verification.md",
    "screen": "custom-skills/shared/dev-design-reference/references/screen-spec-contract.md",
}
REQUIRED = {
    "policy": ("UI_VERIFICATION_SELECTION_V1", "AC -> evidence", "REQUIRED", "OPTIONAL",
               "NOT_APPLICABLE", "beforeunload", "CODE_DRIVEN", "DRAFT", "Browser E2E",
               "P0/P1", "AC Evidence Map", "cannot be silently downgraded"),
    "level": ("UI_VERIFICATION_SELECTION_V1", "REQUIRED / OPTIONAL / NOT_APPLICABLE"),
    "breakdown": ("UI_VERIFICATION_SELECTION_V1", "AC Evidence Map", "Required Checks", "Optional Checks"),
    "direct": ("UI_VERIFICATION_SELECTION_V1", "Required Checks", "Optional Checks"),
    "frontend": ("UI_VERIFICATION_SELECTION_V1", "SPLIT_VIEW", "Design Conformance: NOT_REQUIRED"),
    "test": ("UI_VERIFICATION_SELECTION_V1", "AC Evidence Map", "REQUIRED | OPTIONAL | NOT_APPLICABLE"),
    "browser": ("UI_VERIFICATION_SELECTION_V1", "Browser-dependent", "REQUIRED/OPTIONAL"),
    "screen": ("UI_VERIFICATION_SELECTION_V1", "최소 실제 증적"),
}


def verify() -> None:
    for name, path in SOURCES.items():
        contents = (ROOT / path).read_text(encoding="utf-8")
        missing = [token for token in REQUIRED[name] if token not in contents]
        if missing:
            raise AssertionError(f"{path} missing contract terms: {missing}")
    policy = (ROOT / SOURCES["policy"]).read_text(encoding="utf-8")
    assert "completion is blocked" in policy
    assert "not permission to ignore evidence" in policy


if __name__ == "__main__":
    verify()
    print("PASS: risk-based UI verification selection contract")
