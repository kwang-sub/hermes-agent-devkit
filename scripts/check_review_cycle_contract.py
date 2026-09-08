#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CODER_CYCLE=ROOT/"custom-skills/coder/dev-review-cycle/SKILL.md"; REVIEWER_CYCLE=ROOT/"custom-skills/reviewer/dev-review-cycle/SKILL.md"
CODER_PROTOCOL=ROOT/"custom-skills/coder/dev-review-cycle/references/review-protocol.md"; REVIEWER_PROTOCOL=ROOT/"custom-skills/reviewer/dev-review-cycle/references/review-protocol.md"
IMPLEMENT=ROOT/"custom-skills/coder/dev-implement-plan/SKILL.md"; REVIEW=ROOT/"custom-skills/reviewer/dev-code-review/SKILL.md"; FAST=ROOT/"custom-skills/coder/dev-fast-flow/SKILL.md"
STANDARD=ROOT/"custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md"; DISPATCH=ROOT/"custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md"
MODEL_POLICY=ROOT/"custom-skills/shared/dev-flow-model-policy/SKILL.md"; MODEL_HELPER=ROOT/"shared/scripts/flow_model_policy.py"; APPROVAL_RULES=ROOT/"shared/references/approval-gate-rules.md"
def read(p): return p.read_text(encoding="utf-8")
def require(path,terms,failures):
    if not path.is_file(): failures.append(f"{path.relative_to(ROOT)} missing"); return
    t=read(path); missing=[x for x in terms if x not in t]
    if missing: failures.append(f"{path.relative_to(ROOT)} missing: {', '.join(missing)}")
def main():
    f=[]
    if read(CODER_CYCLE)!=read(REVIEWER_CYCLE): f.append("coder/reviewer dev-review-cycle/SKILL.md copies differ")
    if read(CODER_PROTOCOL)!=read(REVIEWER_PROTOCOL): f.append("coder/reviewer review-protocol.md copies differ")
    for p in (CODER_CYCLE,REVIEWER_CYCLE): require(p,("Fast LOW","REVIEW_REQUIRED","kanban_complete","kanban_request_review","kanban_request_changes","kanban_block","CHANGES_REQUESTED","original coder","Standard Flow","LOW 근거 없는","source를 수정하지 않고","no commit/push"),f)
    for p in (CODER_PROTOCOL,REVIEWER_PROTOCOL): require(p,("Fast Flow","Standard Flow","Review Risk LOW","review_skipped=true","CHANGES_REQUESTED","original coder","동일 Workspace","kanban_complete","kanban_request_review","kanban_request_changes","kanban_block","Standard Flow Coder self-complete","publication = no commit/push/PR"),f)
    require(FAST,("Review Policy: RISK_BASED","LOW","REVIEW_REQUIRED","CHANGES_REQUESTED","kanban_complete","kanban_request_review","dev-flow-model-policy","FAST Flow · DEFAULT","FAST Flow · PREMIUM","Reviewer는 DEFAULT 고정","Model Escalation: REQUIRE_REAPPROVAL"),f)
    require(STANDARD,("/opt/data/shared/references/approval-gate-rules.md","WORKSPACE_APPROVED","BRANCH_APPROVED","MODEL_APPROVED","PLAN_APPROVED","clarify","choices","[Project 선택]","[Workspace 선택]","[Branch 선택]","[Coder 모델 선택]","[작업 계획 승인]","DEFAULT | PREMIUM","Reviewer Model은 항상 DEFAULT","flow_model_policy.py resolve","model=<MODEL>","provider=<PROVIDER>","dev-flow-model-policy","Model Escalation: REQUIRE_REAPPROVAL","기존 카드 재작업 계약","Requirement Delta:","Approval Reuse:","migrate-existing","STATUS=legacy-task-migrated","SNAPSHOT_SOURCE=durable-comment","신규/대체 Task 승인 불변식","대체 카드 생성 승인","서로 다른 승인 Gate를 한 질문으로 합치지 않는다","NO_EXTRA_KANBAN_CONFIRMATION"),f)
    require(APPROVAL_RULES,("한 번의 사용자 확인에서는 하나의 의사결정만 요청한다","clarify","choices","↑/↓ 이동 + Enter 선택","Other (type your answer)","Workspace와 Branch는 서로 다른 Gate다","AUTO_DISPATCH","NO_EXTRA_KANBAN_CONFIRMATION"),f)
    require(DISPATCH,("Coder Model Tier(DEFAULT|PREMIUM) 승인 완료","model=MODEL","provider=PROVIDER","dev-flow-model-policy","model_override == MODEL","provider_override == PROVIDER","review-enter","changes-return","Reviewer profile DEFAULT"),f)
    require(MODEL_POLICY,("HERMES_FLOW_MODEL_DEFAULT_PROVIDER","HERMES_FLOW_MODEL_DEFAULT","HERMES_FLOW_MODEL_PREMIUM_PROVIDER","HERMES_FLOW_MODEL_PREMIUM","Reviewer Model: DEFAULT","Model Escalation: REQUIRE_REAPPROVAL","flow_model_policy.py review-enter","flow_model_policy.py changes-return","자동 escalation은 금지","MODEL_POLICY_SNAPSHOT_V1","migrate-existing","durable Kanban comment","pre-policy Task라는 이유만으로 새 카드 생성을 강제"),f)
    require(MODEL_HELPER,("HERMES_FLOW_MODEL_","review-enter","changes-return","set-model","selection_from_task_payload","Reviewer Model","REQUIRE_REAPPROVAL","migrate-existing","MODEL_POLICY_SNAPSHOT_V1","legacy-task-migrated","durable-comment"),f)
    require(IMPLEMENT,("Flow: FAST","Review Risk","LOW","REVIEW_REQUIRED","kanban_complete","kanban_request_review","Standard Flow","CHANGES_REQUESTED","original coder","동일 Workspace","Standard Flow 또는 CHANGES_REQUESTED 재작업은 항상 review","BLOCKED"),f)
    require(REVIEW,("source를 수정하지 않는다","kanban_request_changes","kanban_complete","kanban_block` 중 정확히 하나","같은 Workspace","needs_input","Review Risk: LOW"),f)
    if f:
        [print(f"[FAIL] {x}") for x in f]; return 1
    print("[PASS] risk-based review-cycle, model-transition, clarify approval, and auto-dispatch invariants"); return 0
if __name__=="__main__": raise SystemExit(main())
