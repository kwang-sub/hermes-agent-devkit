---
name: dev-direct-flow
description: Orchestrator가 작고 명확한 단일 Work Unit 요청을 짧은 승인 절차로 현재 workspace/current branch에 Kanban dispatch하고 Coder→Reviewer 실행 계약을 재사용하는 Direct Flow.
version: 1.0.2
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, direct, workflow, approval, kanban, model, work-unit]
    related_skills: [dev-workflow-orchestrate, dev-project-resolve, dev-skill-preflight, dev-workspace-dispatch, dev-flow-model-policy, dev-implement-plan, dev-code-review]
    requires_tools: [terminal, clarify, skill_view, kanban_create, kanban_show, kanban_unblock]
---

# dev-direct-flow

Direct Flow는 **Orchestrator 소유의 compact dispatch 경로**다. Orchestrator가 application/test/config source를 직접 수정하는 모드가 아니며 Interactive Coder 직접 수정 모드도 아니다.

```text
User request
→ Orchestrator Direct eligibility
→ 필요한 Project Approval
→ [실행 방식 선택] DIRECT
→ [Coder 모델 선택]
→ compact Plan Approval
→ dev-workspace-dispatch
→ Kanban (Flow: DIRECT)
→ Coder
→ Reviewer DEFAULT
→ DONE | CHANGES_REQUESTED | BLOCKED
```

Direct에서 생략하는 것은 `dev-breakdown`의 광범위한 planning 단계와 Standard의 선택형 Workspace/Branch 설계다. 구현·검증·Capability Preflight·모델 pin·등록 알림·Reviewer는 생략하지 않는다.

## 1. 진입 불변식

- mutation request의 실행 진입점은 Orchestrator다. Coder가 새 요청을 self-route/self-dispatch하지 않는다.
- 실제 Kanban Worker는 이미 할당된 Task 계약을 수행하며 Direct/Standard 선택 Gate를 다시 묻지 않는다.
- read-only 분석/설명 요청은 Direct/Standard 실행 Gate 대상이 아니다.
- Direct 여부 판정 때문에 source read/grep/build/test가 필요하면 Direct로 추측하지 않고 Standard로 보낸다.
- Direct eligibility/원인 진단 단계에서 Orchestrator는 project build/test를 실행하지 않는다. Gradle 재현이 필요하면 Direct 판정을 멈추고 Standard로 전환하거나 승인/dispatch 후 Coder에게 위임한다.
- 승인 이후 bounded 진단 예외에서도 raw `./gradlew ...` 또는 `gradle ...`을 직접 호출하지 않고 `hermes-java ./gradlew ...`를 사용한다. COMPILE/TARGETED_TEST 검증은 Coder의 canonical cached verification helper가 소유한다.
- `/dev-direct-flow`를 명시해도 eligibility를 우회하지 않는다.

## 2. Direct eligibility

다음을 **모두** 만족해야 Direct 후보가 될 수 있다.

```text
- managed 단일 Project가 명확함
- current workspace/current branch를 그대로 사용
- 요구사항 해석이 하나이며 Open Question 없음
- 하나의 Work Unit만 필요
- Work Unit Class = IMPLEMENTATION | REFACTOR
- Work Unit Boundary = SINGLE_UNIT
- 작은 기존 패턴 기반 변경
- 대상 파일/심볼/영역을 사용자 요청 또는 이미 승인된 evidence로 좁힐 수 있음
- API Spec Gate = NOT_REQUIRED
- Infrastructure Impact = NO
- 별도 설계 artifact가 선행 input으로 필요하지 않음
- bounded compile/targeted test로 검증 가능
```

다음 중 하나면 **Standard Flow**다.

```text
DESIGN 또는 MIGRATION Work Unit
DB schema/data migration/DBML 설계
public API method/path/request/response/error/auth 의미 변경
dependency 추가/upgrade
Infrastructure runtime/host/network/container/env delivery 변경
security/authz/transaction/concurrency 정책 변경
architecture/common abstraction/shared contract 결정
cross-repository 또는 의미 있는 multi-module 변경
Non-Git Managed Project 또는 Non-Git Workspace
여러 독립 Work Unit
요구사항 복수 해석
실제 source를 넓게 분석해야 scope를 알 수 있음
현재 branch/workspace 외 선택이 필요
기존 변경을 보존할 수 있는지 별도 판단이 필요
```

애매하면 Direct가 아니라 Standard다.

## 3. 실행 방식 Gate

Direct 후보가 확인되면 일반 메시지에 근거를 짧게 보여준 뒤 하나의 `clarify`로 실행 방식만 선택한다.

```text
question:
  [실행 방식 선택]
  이 요청을 Direct Flow로 진행할까요?
choices:
  - Direct Flow
  - Standard Flow
  - 취소
```

- `Direct Flow`만 Direct 승인이다.
- `Standard Flow`면 `dev-workflow-orchestrate` Standard 경로로 전환하고 Direct Gate 상태를 실행 승인으로 재사용하지 않는다.
- `Other`로 scope가 바뀌면 eligibility부터 다시 평가한다.
- `수정해주세요`, `적용해주세요`, `바로 해주세요` 같은 일반 mutation 표현은 Direct Flow 승인 자체로 간주하지 않는다.

## 4. Project / Workspace / Branch 계약

사용자가 현재 요청에서 정확한 managed Project를 지정하지 않았다면 기존 `[Project 선택]` Gate를 먼저 수행한다.

Direct는 Git managed project의 다음 fixed context에서만 허용한다. Non-Git/Composite Project는 Standard Flow로 처리한다.

```text
Project: <approved managed project>
Workspace: <primary/current approved repository workspace>
Branch mode: current
Expected branch: <current branch>
Workspace Approval Source: DIRECT_FIXED_CURRENT
Branch Approval Source: DIRECT_FIXED_CURRENT
```

Direct에서 별도 Workspace/Branch 후보 선택 UI를 만들지 않는다. 다른 workspace/새 branch가 필요하면 Standard로 전환한다.

`DIRECT_FIXED_CURRENT`는 Direct Plan Approval이 위 fixed context를 포함해 승인됐다는 의미다. Standard Flow의 독립 Workspace/Branch Gate를 일반화하거나 약화하지 않는다.

## 5. Coder 모델 Gate

Flow 선택 뒤 `[Coder 모델 선택]`을 독립 Gate로 수행한다.

```text
choices:
- DEFAULT
- PREMIUM
```

실제 model/provider는 승인 Tier를 기준으로 `flow_model_policy.py resolve --tier <DEFAULT|PREMIUM>`으로 한 번 해석한다. Reviewer는 항상 DEFAULT다. 자동 PREMIUM escalation은 금지한다.

## 6. Compact Plan

Direct Plan은 source 분석 보고서가 아니라 **작고 명확한 실행 snapshot**이다. 일반 메시지에 최소 다음을 보여준다.

```text
Flow: DIRECT
Project: <project>
Workspace: <current workspace>
Branch: <current branch>
Coder Model Tier: <DEFAULT|PREMIUM>
Work Unit Class: IMPLEMENTATION | REFACTOR
Work Unit Boundary: SINGLE_UNIT
Current Deliverable: <이번 작업 산출물>
Follow-up Required: NO
Follow-up Work Unit: NONE
Follow-up Input: NONE
Excluded Follow-up Scope: <Direct 금지 범위>
목표: <goal>
Acceptance Criteria:
- ...
구현 작업:
- ...
테스트 계획:
- ...
위험:
- ... | none
Applicable Skills:
- <explicit/stack-cache evidence로 확정 가능한 skill>
API Spec Mode: NOT_REQUIRED
API Spec Gate: NOT_REQUIRED
API Spec Status: NOT_REQUIRED
Infrastructure Impact: NO
Review Policy: REQUIRED
```

Applicable Skills를 확정하려고 broad source 분석이 필요하면 Standard로 전환한다.

Plan은 기존 `[작업 계획 승인]` Gate를 사용한다. Plan 승인 전 source mutation/Kanban 생성/build/test 실행은 금지한다.

## 7. Dispatch

Plan 승인 후 추가 Kanban 생성 확인 없이 `skill_view("dev-workspace-dispatch")`를 적용한다.

Direct Task body에는 반드시 다음 provenance를 추가한다.

```text
Flow: DIRECT
Entry Flow: DIRECT
Review Policy: REQUIRED
Workspace Approval Source: DIRECT_FIXED_CURRENT
Branch Approval Source: DIRECT_FIXED_CURRENT
```

나머지는 Standard의 canonical dispatch 계약을 그대로 사용한다.

```text
Primary Repository metadata
Base SHA
Existing changes preservation
Capability Preflight
Coder model/provider pin
Reviewer profile DEFAULT
initial_status=blocked
kanban_show read-back
registration notification
unblock
```

Direct 전용 Kanban 생성 helper, 별도 board 탐색, global safe.directory 변경을 만들지 않는다.

## 8. Coder / Reviewer 계약

Direct Task는 작은 작업이어도 Coder self-complete를 허용하지 않는다.

```text
Coder
→ dev-implement-plan
→ verification
→ kanban_request_review
→ Reviewer DEFAULT
→ kanban_complete | kanban_request_changes | kanban_block
```

Coder가 실제 source에서 Direct eligibility를 벗어나는 요구를 발견하면 scope를 확대하지 않는다.

```text
DIRECT_SCOPE_EXCEEDED
- Evidence: <why>
- Required Flow: STANDARD
```

를 남기고 BLOCK한다. Orchestrator가 Requirement Delta/Standard Flow로 재계획한다.

## 9. Follow-up

Direct 승인은 **한 Task에 대한 one-shot approval**이다. 이미 dispatch된 Direct Task에 새 요구사항이 들어오면 Direct 전용 follow-up helper를 사용하지 않는다.

- 같은 Work Unit 안의 requirement delta인지 기존 `dev-workflow-orchestrate` 계약으로 평가한다.
- 다른 Work Unit/API/schema/dependency/Infrastructure/architecture 범위면 Standard Flow로 분리한다.
- terminal Task에 새 요구가 생기면 새 Direct/Standard 요청으로 다시 분류한다.

## 10. 금지

- Orchestrator가 Direct라는 이유로 source 직접 수정
- Orchestrator가 raw `./gradlew ...` 또는 `gradle ...`을 직접 실행해 `/workspace`의 project-local `.gradle`/`build`를 오염시키는 행위
- canonical cached verification helper 또는 `hermes-java`를 우회하는 ad-hoc Gradle build/test 실행
- Interactive Coder가 새 mutation request를 self-route/self-dispatch
- Direct/Standard canonical dispatch를 우회하는 별도 실행 경로 또는 Task 생성
- Reviewer 생략 / risk-based self-complete
- current workspace/current branch 외 Direct 실행
- Direct에서 API/DB/Infrastructure/architecture 정책 결정
- 기존 사용자 변경 reset/restore/clean/stash
- 승인 없는 model 변경
- Direct 전용 duplicate dispatch/notification implementation
