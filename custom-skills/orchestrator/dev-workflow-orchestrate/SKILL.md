---
name: dev-workflow-orchestrate
description: Jira/text 개발 요청의 project·work unit·requirement delta·API spec·workspace·branch·Coder 모델·plan을 독립 clarify Gate로 승인한 뒤 단일 Work Unit만 Kanban dispatch하는 orchestrator 전용 workflow.
version: 0.13.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, workflow, orchestrator, approval, clarify, gate, work-unit, requirement-delta, api, spec, dispatch, kanban, model, performance]
    related_skills: [dev-work-intake, dev-project-resolve, dev-project-bootstrap, dev-breakdown, dev-api-spec, dev-skill-preflight, dev-workspace-dispatch, dev-flow-model-policy]
---

# dev-workflow-orchestrate

Orchestrator는 요청의 상태 머신과 승인 Gate만 조정한다. application/test code, code review, commit, push, PR, merge, cleanup은 직접 하지 않는다. 사용자 가시 계획/승인 문구는 한국어다.

Standard Flow 승인 UI는 `/opt/data/shared/references/approval-gate-rules.md`, Work Unit 경계는 `/opt/data/shared/references/standard-work-unit-rules.md`가 source of truth다. **한 번의 사용자 확인에서는 하나의 의사결정만 요청한다.** 선택지는 질문 본문에 번호로 쓰지 않고 `clarify`의 `choices`를 사용한다.

## 상태 머신

```text
START
→ PROJECT_APPROVED
→ dev-breakdown READY
→ WORK_UNIT_CLASSIFIED
→ API_SPEC_APPROVED | NOT_REQUIRED
→ WORKSPACE_APPROVED
→ BRANCH_APPROVED | BRANCH_NOT_REQUIRED
→ MODEL_APPROVED
→ PLAN_APPROVED
→ AUTO_DISPATCH_CURRENT_UNIT_ONLY
→ SKILL_PREFLIGHT
→ KANBAN_CREATED
→ NOTIFY_REGISTRATION_EVENT=queued
→ coder ↔ reviewer
→ DONE | BLOCKED
```

`Work Unit Boundary: SPLIT_REQUIRED`이면 현재 Task는 첫 Current Deliverable만 dispatch한다. 후속 Work Unit은 metadata로만 보존한다.

```text
현재 Task DONE
→ STOP
→ 사용자가 별도 Standard Flow로 후속 Work Unit 요청
```

Follow-up Task를 같은 승인으로 자동 생성하지 않는다.

## Work Unit Boundary

필수 handoff:

```text
Work Unit Class: DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT
Work Unit Boundary: SINGLE_UNIT | SPLIT_REQUIRED
Current Deliverable: ...
Follow-up Required: YES | NO
Follow-up Work Unit: ... | NONE
Follow-up Input: ... | NONE
Excluded Follow-up Scope: ... | NONE
```

여러 capability가 하나의 deliverable을 완성하는 것은 split 사유가 아니다. 독립 승인 artifact가 다음 mutation phase의 authoritative input이 되면 split한다. Data DESIGN + physicalization은 DESIGN 완료 후 별도 MIGRATION이다.

## API Specification Mode

`dev-breakdown` 결과는 `DESIGN_FIRST | SOURCE_SYNC | AUDIT | NOT_REQUIRED` 중 하나다.

- DESIGN_FIRST: `API_SPEC_REQUIRED`; 구현 전 Markdown DRAFT 승인.
- SOURCE_SYNC: existing source 역문서화; 의미 변경 없음.
- AUDIT: Source ↔ Markdown ↔ OpenAPI 조사.
- NOT_REQUIRED: API 의미 영향 없음.

DESIGN_FIRST 승인 후에만 `API_SPEC_APPROVED`다. API Spec 승인과 Plan 승인을 한 질문으로 합치지 않는다.

## 신규 Standard Flow

```text
dev-work-intake
→ [Project 선택]
→ dev-breakdown
→ Work Unit Class/Boundary 확정
→ [API 규격 승인] (필요 시)
→ [Workspace 선택]
→ [Branch 선택] (Git Workspace만)
→ 기존 변경 보존 승인 (Git Workspace에서 필요 시)
→ [Coder 모델 선택]
→ [작업 계획 승인]
→ NO_EXTRA_KANBAN_CONFIRMATION
→ AUTO_DISPATCH_CURRENT_UNIT_ONLY
```

Coder Tier는 `DEFAULT | PREMIUM`만 허용하고 Reviewer Model은 항상 DEFAULT다. 승인 Tier는 `flow_model_policy.py resolve --tier`로 해석하고 Task에 `model=<MODEL>`, `provider=<PROVIDER>`, `dev-flow-model-policy`, `Model Escalation: REQUIRE_REAPPROVAL` snapshot을 보존한다.

## API 규격 승인 Gate

DESIGN_FIRST에서만 사용한다.

```text
[API 규격 승인]
choices: [규격 승인, 규격 보류]
```

`규격 승인`만 승인이다. `규격 보류`면 이후 Gate/dispatch를 중단한다. 수정 요구는 DRAFT를 갱신하고 같은 Gate를 다시 출력한다. SOURCE_SYNC/AUDIT/NOT_REQUIRED는 Gate를 생략한다.

## clarify Gate 계약

서로 다른 승인 Gate를 한 질문으로 합치지 않는다.

```text
[Project 선택]
[API 규격 승인]
[Workspace 선택]
[Branch 선택]
[기존 변경 보존 확인]
[Coder 모델 선택]
[작업 계획 승인]
[추가 요구사항 확인]
```

Git Workspace에서는 Workspace와 Branch가 별도 Gate다. Non-Git Workspace는 Project 등록 시 Version Control 승인이 이미 기록되어 있으므로 `BRANCH_NOT_REQUIRED`, `Existing Changes: NOT_REQUIRED`로 진행한다. `Other` 또는 수정 요구는 승인으로 간주하지 않고 값을 갱신한 뒤 **같은 Gate를 다시 출력**한다.

### Plan Gate TUI 길이 계약

전체 Implementation Plan은 clarify 직전 일반 메시지로 먼저 보여준다. `clarify.questions[0].question`은 아래 문자열을 그대로 사용한다.

```text
[작업 계획 승인]
위 Implementation Plan을 승인할까요?
```

Task, Project / Workspace / Branch, Coder Model, Goal, Design Evidence, Implementation Tasks, Acceptance Criteria 등 동적 상세는 질문에 다시 넣지 않는다. **정보는 일반 메시지에 유지하고 결정 UI만 짧게 유지**한다.

## Requirement Delta Approval — 승인 이후 추가 요구사항

승인 이후 요구사항 변경은 자연어 요청 자체를 실행 승인으로 취급하지 않는다.

```text
Requirement Delta:
- 변경 요구사항
- 유지 요구사항
- 롤백/제거 범위
- 금지 작업
- 재검토 범위
- 기존 Task 처리: SAME_TASK_RESUME | REPLACEMENT_TASK | FOLLOW_UP_TASK
```

독립 `[추가 요구사항 확인]` Gate에서 `요구사항 확정`된 경우에만 `REQUIREMENT_DELTA_APPROVED`다. Work Unit/API Spec/Plan을 다시 판정한다. 다른 Work Unit이면 SAME_TASK_RESUME하지 않고 FOLLOW_UP_TASK 또는 새 Standard Flow로 분리한다.

## 기존 카드 재작업 계약

먼저 `kanban_show`로 기존 상태와 Work Unit/모델 snapshot을 읽는다.

```text
Approval Reuse:
- Project: REUSE | REQUIRED
- Requirement Delta: REQUIRED
- Work Unit Boundary: REUSE | RECLASSIFY
- API Spec: REUSE | REQUIRED | NOT_REQUIRED
- Workspace: REUSE | REQUIRED
- Branch: REUSE | REQUIRED
- Coder Model: REUSE | REQUIRED | MIGRATE
- Plan: REUSE | REQUIRED
```

pre-policy Task는 필요하면 `migrate-existing`을 사용하며 성공 계약은 `STATUS=legacy-task-migrated`, `SNAPSHOT_SOURCE=durable-comment`다. 대체 카드 생성 승인 자체는 각 Gate 승인을 대신하지 않는다.

## 신규/대체 Task 승인 불변식

범위가 바뀐 신규/대체 Task는 Requirement Delta Approval, Work Unit 재분류, 필요한 API Spec Approval, Plan Approval을 각각 가진다. 모든 필수 Gate 완료 후에는 Kanban 생성 자체를 다시 승인받지 않는다.

## 자동 Dispatch / 성능

필수 승인 완료 후:

```text
NO_EXTRA_KANBAN_CONFIRMATION
→ prepare_dispatch.py 정확히 한 번
→ dev-skill-preflight
→ kanban_create tool 1회
→ kanban_show tool 1회
→ notification subscribe
→ NOTIFY_REGISTRATION_EVENT=queued
→ unblock / dispatch
```

승인 Gate 중 working-tree 전체 scan을 하지 않는다. 기존 변경 보존 승인 시 `skipped-approved-preservation`을 사용한다. Coder는 `change_summary.py --include`, Reviewer는 `review_context.py --include`로 bounded scope만 본다. 세부 성능 규칙은 `references/dispatch-efficiency.md`를 따른다.

## 불변식

- Project Approval / Plan Approval / Requirement Delta Approval을 추측하지 않는다.
- Git Workspace의 Base SHA는 dispatch 시점 계약으로 보존한다. Non-Git Workspace는 `Base SHA: NONE`이며 snapshot을 생성하지 않는다.
- 현재 Work Unit만 dispatch한다.
- 추가 Kanban 생성 확인 질문을 만들지 않는다.
- 상세 API/재작업/dispatch edge case는 `references/workflow-details.md`를 필요할 때만 읽는다.
