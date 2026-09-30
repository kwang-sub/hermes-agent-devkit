---
name: dev-workflow-orchestrate
description: Jira/text 개발 요청의 project·work unit·requirement delta·API spec·workspace·branch·Coder 모델·plan을 독립 clarify Gate로 승인한 뒤 단일 Work Unit만 Kanban dispatch하는 orchestrator 전용 workflow.
version: 0.17.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, workflow, orchestrator, approval, clarify, gate, work-unit, requirement-delta, api, spec, dispatch, kanban, model, performance]
    related_skills: [dev-work-intake, dev-project-resolve, dev-project-bootstrap, dev-breakdown, dev-api-spec, dev-skill-preflight, dev-workspace-dispatch, dev-flow-model-policy, dev-task-recovery]
---

# dev-workflow-orchestrate

Orchestrator는 요청의 상태 머신과 승인 Gate만 조정한다. application/test code, code review, commit, push, PR, merge, cleanup은 직접 하지 않는다. 사용자 가시 계획/승인 문구는 한국어다.

Standard Flow 승인 UI는 `/opt/data/shared/references/approval-gate-rules.md`, Work Unit 경계는 `/opt/data/shared/references/standard-work-unit-rules.md`, 연속 작업 Parent 추적은 `/opt/data/shared/references/parent-tracking-rules.md`가 source of truth다. **한 번의 사용자 확인에서는 하나의 의사결정만 요청한다.** 선택지는 질문 본문에 번호로 쓰지 않고 `clarify`의 `choices`를 사용한다.

## Blocked Task Recovery 진입

사용자가 다음처럼 **기존 blocked Kanban Task 복구 자체**를 요청하면 일반 신규 Standard Flow보다 먼저 `skill_view("dev-task-recovery")`를 사용한다.

```text
리커버 플로우
차단 Task 복구
blocked 카드 원인 분석 후 재개
기존 카드 번호를 유지해 복구
```

Recovery Flow는:

```text
[보드 선택]
→ [차단 카드 선택]
→ read-only 원인 분석
→ [복구 계획 승인]
→ durable Recovery Revision
→ SAME_TASK_RESUME
```

의 정확히 3-Gate 계약을 소유한다.

`RETRY_SAME_CONTRACT | SAME_TASK_RESUME`이고 Project/Workspace/Branch/Model/API/Work Unit 독립 재승인이 필요하지 않으면 Recovery Gate 3 승인이 bounded Requirement Delta + Recovery Plan 승인을 대표한다. 이 경우 일반 `[추가 요구사항 확인]` / `[작업 계획 승인]` Gate를 뒤에 중복 추가하지 않는다.

독립 승인 경계를 넘으면 Recovery Skill이 `REPLACEMENT_REQUIRED`로 종료하고 현재 카드를 blocked로 보존한 뒤 이 Standard Flow로 돌아온다. 이때부터는 일반 승인 Gate를 그대로 적용한다.

## 상태 머신

```text
START
→ PROJECT_APPROVED
→ dev-breakdown READY
→ WORK_UNIT_CLASSIFIED
→ PARENT_TRACKING_CLASSIFIED
→ PARENT_TRACKING_APPROVED | NOT_REQUIRED
→ API_SPEC_APPROVED | NOT_REQUIRED
→ WORKSPACE_APPROVED
→ BRANCH_APPROVED | BRANCH_NOT_REQUIRED
→ MODEL_APPROVED
→ PLAN_APPROVED  # Execution + Verification Contract approved
→ AUTO_DISPATCH_CURRENT_UNIT_ONLY
→ SKILL_PREFLIGHT
→ KANBAN_CREATED
→ coder ↔ reviewer
→ DONE | BLOCKED
```

`Work Unit Boundary: SPLIT_REQUIRED`이면 현재 Task는 첫 Current Deliverable만 dispatch한다. 후속 Work Unit은 metadata로만 보존한다.

```text
현재 Task DONE
→ STOP
→ 사용자가 별도 Standard Flow로 후속 Work Unit 요청
```

Follow-up Task를 같은 승인으로 자동 생성하지 않는다. 다만 여러 Standard Task를 하나의 큰 목표로 추적해야 하면 실행되지 않는 `[부모]` tracking card를 사용할 수 있다. Parent는 후속 Task 자동 생성 권한을 갖지 않는다.

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
→ Parent Tracking Mode 판정
→ [작업 관리 방식 승인] (Parent 생성/연결/승격 시)
→ [API 규격 승인] (필요 시)
→ [Workspace 선택]
→ [Branch 선택] (Git Workspace만)
→ 기존 변경 보존 승인 (Git Workspace에서 필요 시)
→ [Coder 모델 선택]
→ [실행·검증 계획 승인]
→ NO_EXTRA_KANBAN_CONFIRMATION
→ AUTO_DISPATCH_CURRENT_UNIT_ONLY
```

Coder Tier는 `DEFAULT | PREMIUM`만 허용하고 Reviewer Model은 항상 DEFAULT다. 승인 Tier는 `flow_model_policy.py resolve --tier`로 해석하고 Task에 `model=<MODEL>`, `provider=<PROVIDER>`, `dev-flow-model-policy`, `Model Escalation: REQUIRE_REAPPROVAL` snapshot을 보존한다.

## Parent Tracking Gate

`dev-breakdown` 뒤 현재 요청이 단건인지 연속 작업 추적이 필요한지 판정한다.

```text
Parent Tracking Mode: NONE | NEW_PARENT | LINK_EXISTING_PARENT | PROMOTE_TO_PARENT
```

- `NONE`: 명백한 단건 작업이면 Gate 없이 진행한다.
- `NEW_PARENT`: 새 `[부모]` tracking card를 생성하고 현재 Task를 `[자식]`로 연결한다.
- `LINK_EXISTING_PARENT`: 기존 `[부모]` 카드에 새 `[자식]` Task를 추가하거나 연결된 Task를 수정한다.
- `PROMOTE_TO_PARENT`: Parent 없이 시작한 기존 Task를 새 `[부모]` tracking card의 첫 이력으로 연결한다.

Parent tracking 구조를 바꾸는 경우 다음 독립 Gate를 사용한다.

```text
[작업 관리 방식 승인]
이번 작업의 연속 작업 관리 방식을 승인할까요?
```

이 Gate는 tracking 관계만 승인하며 API/Workspace/Branch/Model/Plan 승인을 대신하지 않는다. Parent/Child 관계의 authoritative key는 제목이 아니라 Parent Task ID다. 표시는 `[부모]` / `[자식]` 제목 접두어를 사용한다.

Parent는 `Execution: NON_DISPATCH`이며 Coder/Reviewer로 dispatch하지 않는다. 전체 Child 카드를 미리 만들지 않고 현재 Standard Task만 생성한다. Child 완료 후 다음 Child를 자동 실행하지 않으며, 다음 작업은 새 Standard Flow에서 기존 Parent를 선택해 진행한다.

## API 규격 승인 Gate

DESIGN_FIRST에서만 사용한다.

```text
[API 규격 승인]
choices: [규격 승인, 규격 보류]
```

`규격 승인`만 승인이다. `규격 보류`면 이후 Gate/dispatch를 중단한다. 수정 요구는 DRAFT를 갱신하고 같은 Gate를 다시 출력한다. SOURCE_SYNC/AUDIT/NOT_REQUIRED는 Gate를 생략한다.

## clarify Gate 계약

서로 다른 승인 Gate를 한 질문으로 합치지 않는다.

**Gate 전이 불변식:** Project/API Spec/Workspace/Branch/Existing Changes/Coder Model/Plan/Requirement Delta 중 현재 단계가 승인을 요구하고 Gate 입력이 준비되면, Orchestrator는 필요한 설명을 일반 메시지로 보여준 **같은 turn에서 즉시 해당 `clarify`를 호출한다.** 설명만 출력하고 사용자의 `네`, `진행해주세요`, `계속해주세요`를 기다린 뒤 다음 turn에서 Gate를 띄우는 흐름은 금지한다. 이미 승인 evidence가 있어 `REUSE`/`NOT_REQUIRED`인 Gate만 생략할 수 있다.

```text
GATE_REQUIRED + GATE_INPUT_READY
→ 일반 메시지로 판단 근거/후보/계획 표시 (필요한 경우)
→ IMMEDIATE_CLARIFY
→ APPROVED | REVISE | BLOCKED
```

`IMMEDIATE_CLARIFY` 전에는 동일 계획을 다시 출력하거나 별도 진행 의사를 묻지 않는다.

```text
[Project 선택]
[작업 관리 방식 승인]
[API 규격 승인]
[Workspace 선택]
[Branch 선택]
[기존 변경 보존 확인]
[Coder 모델 선택]
[실행·검증 계획 승인]
[추가 요구사항 확인]
```

Git Workspace에서는 Workspace와 Branch가 별도 Gate다. Non-Git Workspace는 Project 등록 시 Version Control 승인이 이미 기록되어 있으므로 `BRANCH_NOT_REQUIRED`, `Existing Changes: NOT_REQUIRED`로 진행한다. `Other` 또는 수정 요구는 승인으로 간주하지 않고 값을 갱신한 뒤 **같은 Gate를 다시 출력**한다.

## 실행·검증 계획 승인 Gate

Plan Approval은 Implementation만 승인하지 않고 **Execution Contract + Verification Contract**를 함께 승인한다. 일반 메시지에서 반드시 다음 canonical heading을 사용한다.

```text
## 🛠️ **실행 계획**
<현재 Work Unit의 구현 계획>

## 🧪 **검증 계획**
- Target: ...
- Method: ...
- Provider: ...
- Required Environment: ...
- Lifecycle: ...

### ⚠️ **환경 의존 검증**
<별도 환경 검증 상세 또는 NONE>

구현 요약:
<실제 변경 대상 + 핵심 변경 + 보존 범위/중요 예외를 1~2줄, 최대 2문장으로 요약>
```

환경 의존 검증은 Docker/실제 DB/Testcontainers/외부 서비스/browser 등 구현환경 외 capability를 요구하는 검증이다. Provider와 lifecycle은 Plan Approval의 일부다. 승인 뒤 Coder가 provider를 임의 변경하거나 fallback하지 않는다. 변경이 필요하면 Requirement Delta/Recovery의 bounded verification delta로 재승인한다.

### Plan Gate TUI 길이 계약

전체 Implementation Plan은 clarify 직전 일반 메시지로 먼저 보여준다. Plan의 마지막에는 반드시 `구현 요약:`을 1~2줄(최대 2문장)로 출력하며, 실제 변경 대상 + 핵심 변경 + 보존 범위 또는 중요 예외를 포함한다. 제목/목표의 단순 반복은 금지한다. **`구현 요약:`이 누락되면 `PLAN_READY`가 아니므로 `clarify`를 호출할 수 없다. 요약 출력 직후 같은 turn에서 즉시 Plan `clarify`를 호출한다.** `clarify.questions[0].question`은 아래 문자열을 그대로 사용한다.

```text
[실행·검증 계획 승인]
위 실행 계획과 검증 계획을 승인할까요?
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

일반 기존-card 재작업과 `dev-task-recovery`를 구분한다.

```text
사용자가 blocked/triage Task Recovery를 명시
→ dev-task-recovery 3-Gate 경로 우선

일반 추가 요구사항/완료 Task 변경/비-blocked 재작업
→ 아래 Generic Requirement Delta 경로
```

Recovery 정상 경로는 같은 Task ID에 durable Revision을 남기고 `kanban_unblock`한다. `kanban_create`를 사용하지 않는다.

일반 재작업은 먼저 `kanban_show`로 기존 상태와 Work Unit/모델 snapshot을 읽는다.

```text
Approval Reuse:
- Project: REUSE | REQUIRED
- Requirement Delta: REQUIRED
- Work Unit Boundary: REUSE | RECLASSIFY
- API Spec: REUSE | REQUIRED | NOT_REQUIRED
- Workspace: REUSE | REQUIRED
- Branch: REUSE | REQUIRED
- Coder Model: REUSE | REQUIRED | MIGRATE
- Plan + Verification: REUSE | REQUIRED
```

pre-policy Task는 필요하면 `migrate-existing`을 사용하며 성공 계약은 `STATUS=legacy-task-migrated`, `SNAPSHOT_SOURCE=durable-comment`다. 대체 카드 생성 승인 자체는 각 Gate 승인을 대신하지 않는다.

## 신규/대체 Task 승인 불변식

범위가 바뀐 신규/대체 Task는 Requirement Delta Approval, Work Unit 재분류, 필요한 API Spec Approval, Execution + Verification Plan Approval을 가진다. 모든 필수 Gate 완료 후에는 Kanban 생성 자체를 다시 승인받지 않는다.

## 자동 Dispatch / 성능

필수 승인 완료 후:

```text
NO_EXTRA_KANBAN_CONFIRMATION
→ prepare_dispatch.py 정확히 한 번
→ dev-skill-preflight
→ kanban_create tool 1회
→ kanban_show tool 1회
→ unblock / dispatch
→ DevKit Notification Bridge는 task_events를 비동기로 관찰
```

승인 Gate 중 working-tree 전체 scan을 하지 않는다. 기존 변경 보존 승인 시 `skipped-approved-preservation`을 사용한다. Coder는 `change_summary.py --include`, Reviewer는 `review_context.py --include`로 bounded scope만 본다. 세부 성능 규칙은 `references/dispatch-efficiency.md`를 따른다.

## 불변식

- Project Approval / Execution+Verification Plan Approval / Requirement Delta Approval을 추측하지 않는다.
- 승인 필요 단계에서 설명만 출력하고 자연어 재확인을 기다리지 않는다. Gate 입력 준비 즉시 canonical `clarify`를 같은 turn에서 호출한다.
- Standard Plan Gate는 상세 실행·검증 계획의 마지막 `구현 요약:` 1~2줄이 필수이며, 누락 시 `PLAN_READY`로 전이하지 않는다.
- Workspace/Branch/Existing Changes/Model도 Gate가 REQUIRED이면 명시적 `clarify` 승인 없이는 다음 상태로 전이하지 않는다.
- blocked Task 복구 요청은 `dev-task-recovery`의 정확히 3-Gate 계약을 우선하며, 정상 SAME_TASK_RESUME 뒤에 일반 Plan/Requirement Delta Gate를 중복 추가하지 않는다.
- Git Workspace의 Base SHA는 dispatch 시점 계약으로 보존한다. Non-Git Workspace는 `Base SHA: NONE`이며 snapshot을 생성하지 않는다.
- 현재 Work Unit만 dispatch한다.
- Parent tracking이 승인된 Task는 제목에 `[자식]`를 사용하고 Task body에 Parent Task ID를 기록한다. Parent 제목은 `[부모]`를 사용하되 관계 판정에 제목 문자열을 사용하지 않는다.
- Parent는 실행하지 않으며 전체 하위 카드를 선생성하거나 Child 완료 뒤 다음 Child를 자동 dispatch하지 않는다.
- Parent 없이 시작한 Task도 별도 `[작업 관리 방식 승인]` 후 `PROMOTE_TO_PARENT`로 전환할 수 있다.
- 추가 Kanban 생성 확인 질문을 만들지 않는다.
- 상세 API/재작업/dispatch edge case는 `references/workflow-details.md`를 필요할 때만 읽는다.
