#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: Path, terms: tuple[str, ...], failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"{path.relative_to(ROOT)} missing")
        return
    text = path.read_text(encoding="utf-8")
    missing = [term for term in terms if term not in text]
    if missing:
        failures.append(f"{path.relative_to(ROOT)} missing: {', '.join(missing)}")


def main() -> int:
    failures: list[str] = []

    spec = ROOT / "custom-skills/shared/dev-api-spec/SKILL.md"
    template = ROOT / "custom-skills/shared/dev-api-spec/references/api-spec-template.md"
    breakdown = ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md"
    workflow = ROOT / "custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md"
    approval = ROOT / "shared/references/approval-gate-rules.md"
    dispatch = ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md"
    implement = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"
    contract = ROOT / "custom-skills/shared/dev-api-contract/SKILL.md"
    docs = ROOT / "custom-skills/shared/dev-api-docs/SKILL.md"
    review = ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md"

    require(spec, (
        "DESIGN_FIRST", "SOURCE_SYNC", "AUDIT", "docs/api/<domain>.md",
        "Status: DRAFT", "Documentation Source: APPLICATION_SOURCE",
        "SOURCE_ONLY", "SPEC_ONLY", "CONTRACT_MISMATCH", "API_SPEC_MISMATCH",
        "API_SPEC_GATE=REQUIRED", "API_SPEC_APPROVED=true",
        "SOURCE_SYNC 결과 자동 `APPROVED`", "Repository 전체를 자동으로 훑지 않는다",
    ), failures)
    require(template, (
        "Status", "Documentation Source", "Method", "Path", "Request",
        "Success Response", "Error", "Money / Decimal", "Date / Time / Timezone",
        "Source Evidence", "Unknown / Review Required",
    ), failures)
    require(breakdown, (
        "dev-api-spec", "API Spec Mode", "DESIGN_FIRST", "SOURCE_SYNC", "AUDIT",
        "API Spec Gate", "API Spec Path",
    ), failures)
    require(workflow, (
        "API_SPEC_REQUIRED", "API_SPEC_APPROVED", "[API 규격 승인]",
        "규격 승인", "규격 보류", "DESIGN_FIRST", "SOURCE_SYNC",
        "API Spec 승인과 Plan 승인을 한 질문으로 합치지 않는다",
    ), failures)
    require(approval, (
        "API Spec", "[API 규격 승인]", "규격 승인", "규격 보류",
        "API_SPEC_APPROVAL", "API_SPEC_APPROVED",
    ), failures)
    require(dispatch, (
        "API Spec Gate: REQUIRED | NOT_REQUIRED", "API Spec Status: APPROVED | DRAFT | NOT_REQUIRED",
        "API Spec Path:", "API Spec Mode:",
    ), failures)
    require(implement, (
        "dev-api-spec", "APPROVED Markdown API Specification", "SOURCE_SYNC",
        "API_SPEC_MISMATCH", "Markdown Added / Updated",
    ), failures)
    require(contract, (
        "APPROVED Markdown API Specification", "DESIGN_FIRST", "SOURCE_SYNC",
        "API_SPEC_MISMATCH", "SOURCE_ONLY",
    ), failures)
    require(docs, (
        "APPROVED Markdown API Specification", "API_SPEC_MISMATCH",
        "Documentation Source: APPLICATION_SOURCE", "SOURCE_SYNC",
    ), failures)
    require(review, (
        "dev-api-spec", "API Spec Review Gate", "API Spec Status: APPROVED",
        "API_SPEC_MISMATCH", "SOURCE_SYNC",
    ), failures)

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    print("[PASS] Markdown API specification design-first/source-sync/audit contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
