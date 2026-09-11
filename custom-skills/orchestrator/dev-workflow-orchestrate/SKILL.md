---
name: dev-workflow-orchestrate
description: Jira/text 개발 요청의 project·requirement delta·API spec·workspace·branch·Coder 모델·plan을 독립 clarify Gate로 승인한 뒤 자동 Kanban dispatch하는 orchestrator 전용 workflow.
version: 0.11.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, workflow, orchestrator, approval, clarify, gate, requirement-delta, api, spec, dispatch, kanban, model, performance]
    related_skills: [dev-work-intake, dev-project-resolve, dev-project-bootstrap, dev-breakdown, dev-api-spec, dev-skill-preflight, dev-workspace-dispatch, dev-flow-model-policy]
---

# dev-workflow-orchestrate

Orchestrator는 개발 요청의 상태 머신만 조정한다. application/test code, refactor, code review, commit, push, PR, merge, destructive cleanup은 직접 하지 않는다. 계획/진행 보고와 승인 질문은 **한국어**로 작성한다.

Standard Flow의 모든 사용자 승인 UI는 `/opt/data/shared/references/approval-gate-rules.md`를 canonical contract로 사용한다. **한 번의 사용자 확인에서는 하나의 의사결정만 요청한다.** 선택은 일반 텍스트 번호 목록이 아니라 Hermes 내장 `clarify` tool의 `choices`로 제공한다. TUI/CLI에서는 ↑/↓ + Enter 선택 UX를 사용한다.

핵심 불변식은 `Project Approval`, `Requirement Delta Approval`, 필요한 경우 `API Spec Approval`, `Plan Approval`, Workspace/Branch/Model 승인, 그리고 dispatch 시점의 `Base SHA` 보존이다.

## 상태 머신

신규 Standard Flow:

```text
START
→ WORK_ITEM_READY
→ PROJECT_APPROVED
→ dev-breakdown READY
→ API_SPEC_REQUIRED | API_SPEC_NOT_REQUIRED
→ API_SPEC_APPROVED | NOT_REQUIRED
→ WORKSPACE_APPROVED
→ BRANCH_APPROVED
→ EXISTING_CHANGES_APPROVED | NOT_REQUIRED
→ MODEL_APPROVED
→ PLAN_APPROVED
→ AUTO_DISPATCH
→ SKILL_PREFLIGHT
→ KANBAN_CREATED
→ REGISTRATION_NOTIFICATION_QUEUED
→ coder ↔ reviewer
→ DONE/BLOCKED
```

기존 카드/승인 이후 요구사항 변경:

```text
EXISTING_TASK
→ TASK_INSPECTED
→ REQUIREMENT_DELTA_READY
→ REQUIREMENT_DELTA_APPROVED
→ API_SPEC_REAPPROVED | REUSED | NOT_REQUIRED
→ REQUIRED Gate 각각 clarify 또는 REUSE
→ PLAN_REBUILT
→ PLAN_APPROVED
→ SAME_TASK_RESUMED | REPLACEMENT_TASK_AUTO_DISPATCH
→ coder ↔ reviewer
→ DONE/BLOCKED
```

## API Specification Mode

`dev-breakdown`이 API 관련 Task를 다음 중 하나로 판정한다.

```text
DESIGN_FIRST
SOURCE_SYNC
AUDIT
NOT_REQUIRED
```

- `DESIGN_FIRST`: 신규 endpoint 또는 method/path/request/response/error/auth 등 의미 계약 변경. `API_SPEC_REQUIRED`이며 구현 전에 Markdown DRAFT를 승인받는다.
- `SOURCE_SYNC`: 기존 Application Source를 Markdown DRAFT로 역문서화. API 의미를 바꾸지 않으므로 `API_SPEC_NOT_REQUIRED`다.
- `AUDIT`: Source ↔ Markdown ↔ OpenAPI 차이를 조사. 기본 read-only이며 `API_SPEC_NOT_REQUIRED`다.
- `NOT_REQUIRED`: API 계약 영향 없음.

`SOURCE_SYNC` 결과는 `Status: DRAFT`, `Documentation Source: APPLICATION_SOURCE`를 유지하며 자동 `APPROVED`로 승격하지 않는다.

## 신규 Standard Flow

1. `dev-work-intake`로 요구사항을 정규화한다.
2. `dev-project-resolve` 결과를 `[Project 선택]` clarify Gate로 승인받는다. 이것이 Project Approval이다.
3. `dev-breakdown`으로 READY 계획을 만들고 API Spec Mode/Gate/Status/Path를 확정한다.
4. `DESIGN_FIRST + API Spec Gate: REQUIRED`이면 `skill_view("dev-api-spec")`로 Markdown API Spec DRAFT를 구성하고 일반 메시지로 보여준 뒤 `[API 규격 승인]` clarify Gate를 수행한다.
5. `[Workspace 선택]` → `[Branch 선택]` → `[기존 변경 보존 확인]`(필요 시) → `[Coder 모델 선택]`을 각각 독립 clarify Gate로 승인받는다.
6. 승인된 Tier를 `flow_model_policy.py resolve --tier <DEFAULT|PREMIUM>`으로 정확히 한 번 해석한다.
7. Implementation Plan 본문을 보여준 뒤 `[작업 계획 승인]` clarify Gate를 수행한다. 이것이 Plan Approval이다.
8. Plan까지 승인되면 **추가 Kanban 생성 확인 없이 즉시 AUTO_DISPATCH**한다.
9. `prepare_dispatch.py`가 승인 workspace/branch의 `Base SHA`를 확정하고 Task body에 보존한다.

## API 규격 승인 Gate

DESIGN_FIRST에서만 사용한다.

Orchestrator는 source/config를 수정하지 않고 다음 metadata를 포함한 Markdown DRAFT를 먼저 보여준다.

```text
API Spec Mode: DESIGN_FIRST
API Spec Gate: REQUIRED
API Spec Status: DRAFT
API Spec Path: <planned docs/api/<domain>.md or existing path>
API Spec Source: DESIGN
```

그 다음 독립 `clarify` Gate를 수행한다.

```text
question: [API 규격 승인] 위 Markdown API Specification을 구현 기준으로 확정할까요?
choices: [규격 승인, 규격 보류]
```

규칙:
- `규격 승인`만 `API_SPEC_APPROVED`다.
- 승인 후 `API Spec Status: APPROVED`와 승인된 Markdown snapshot을 Implementation Plan/Task body에 보존한다.
- `규격 보류`면 이후 Gate/dispatch를 진행하지 않는다.
- `Other`는 API 규격 수정으로 처리하고 DRAFT를 갱신한 뒤 같은 Gate를 다시 출력한다.
- API Spec 승인과 Plan 승인을 한 질문으로 합치지 않는다.
- `SOURCE_SYNC | AUDIT | NOT_REQUIRED`는 `API Spec Gate: NOT_REQUIRED`로 이 Gate를 생략한다.

## clarify Gate 계약

선택지는 질문 본문에 번호로 쓰지 않고 `clarify.questions[].choices`에 넣는다. 첫 번째 choice는 Hermes가 Recommended로 표시하므로 현재 권장값을 첫 번째에 둔다. `Other (type your answer)`는 추가 요구사항 입력 경로다.

```text
[Project 선택]            choices: [제안된 프로젝트 사용, 다른 프로젝트 지정]
[API 규격 승인]           choices: [규격 승인, 규격 보류] (DESIGN_FIRST일 때만)
[Workspace 선택]          choices: [제안된 Workspace 사용, 다른 Workspace 지정]
[Branch 선택]             choices: [제안된 Branch 사용, 다른 Branch 지정]
[기존 변경 보존 확인]     choices: [기존 변경을 모두 보존하고 진행, 상태 확인 후 다시 결정]
[Coder 모델 선택]         choices: [<권장 Tier>, <나머지 Tier>]
[작업 계획 승인]          choices: [승인, 차단]
```

선택 가능한 Coder Tier는 `DEFAULT | PREMIUM`뿐이다. Reviewer Model은 항상 DEFAULT이며 선택 Gate를 만들지 않는다. Agent가 PREMIUM을 추천할 수는 있지만 자동 escalation은 금지한다.

`Other` 또는 다른 후보 지정/수정 요구는 승인으로 간주하지 않는다. 요구사항을 갱신한 뒤 **같은 Gate를 다시 출력**한다. Workspace와 Branch는 같은 질문에 합치지 않는다.

## Requirement Delta Approval — 승인 이후 추가 요구사항

이미 승인된 Plan, 생성된 Task, 완료/리뷰 완료 Task에 대해 사용자가 새 요구사항·롤백·범위 교체·목표 변경을 제시하면 **그 자연어 요청 자체를 실행 승인으로 간주하지 않는다.**

먼저 `kanban_show`와 필요한 최소 read-only evidence로 기존 상태를 확인하고 다음을 정규화한다.

```text
Requirement Delta:
- 변경 요구사항
- 유지 요구사항
- 롤백/제거 범위
- 금지 작업
- 재검토 범위
- 기존 Task 처리: SAME_TASK_RESUME | REPLACEMENT_TASK | FOLLOW_UP_TASK
```

그 다음 반드시 독립 clarify Gate를 수행한다.

```text
question: [추가 요구사항 확인] 위 Requirement Delta를 새 작업 범위로 확정할까요?
choices: [요구사항 확정, 보류]
```

규칙:
- `요구사항 확정`만 `REQUIREMENT_DELTA_APPROVED`다.
- `보류`는 dispatch/재개/대체 카드 생성 금지다.
- `Other`는 Requirement Delta를 수정한 뒤 같은 Gate를 다시 출력한다.
- 사용자가 `/dev-workflow-orchestrate 롤백하고 X만 적용해주세요`, `네 진행해주세요`처럼 말한 것은 **요구사항 전달**이지 Requirement Delta Approval 증거가 아니다.
- Requirement Delta 승인 후 `Approval Reuse:`를 판정한다.
- API 의미 계약이 바뀌면 기존 `API_SPEC_APPROVED`를 무효화하고 DESIGN_FIRST DRAFT를 갱신해 `[API 규격 승인]`을 다시 수행한다.
- Goal/Acceptance Criteria/주요 구현 방식이 바뀐 경우 `Plan: REQUIRED`이며, `dev-breakdown`으로 갱신된 Plan을 만든 뒤 `[작업 계획 승인]`을 별도로 다시 수행한다.
- 필요한 Requirement Delta/API Spec/Plan 승인이 없으면 `prepare_dispatch.py`, `kanban_create`, `kanban_unblock`, model migration, same-task resume를 실행하지 않는다.

## 기존 카드 재작업 계약

먼저 `kanban_show`로 Task id/status, Project/Workspace/Branch, 기존 Plan/승인 증거, API Spec Mode/Status/Path, assignee/lane, model_override/provider_override, Model Policy snapshot을 확인한다.

```text
Approval Reuse:
- Project: REUSE | REQUIRED
- Requirement Delta: REQUIRED
- API Spec: REUSE | REQUIRED | NOT_REQUIRED
- Workspace: REUSE | REQUIRED
- Branch: REUSE | REQUIRED
- Existing Changes: REUSE | REQUIRED | NOT_REQUIRED
- Coder Model: REUSE | REQUIRED | MIGRATE
- Plan: REUSE | REQUIRED
```

`REQUIRED`가 여러 개여도 서로 다른 승인 Gate를 한 질문으로 합치지 않는다. canonical 순서로 하나씩 clarify한다.

pre-policy 활성 Task는 새 카드를 만들지 않고 필요한 Requirement Delta/API Spec/Model/Plan 승인 뒤 `flow_model_policy.py migrate-existing`를 사용한다. 성공 조건은 `STATUS=legacy-task-migrated`, `SNAPSHOT_SOURCE=durable-comment`다. `done`/`archived` terminal Task에 후속 작업이 필요한 경우에만 새 Task를 고려한다.

## 자동 Kanban Dispatch 불변식

승인 상태:

```text
project_approved = false
requirement_delta_approved = true | false | not_required
api_spec_approved = true | false | not_required
workspace_approved = false
branch_approved = false
existing_changes_approved = false | not_required
model_approved = false
plan_approved = false
```

신규 요청은 `requirement_delta_approved=not_required`다. DESIGN_FIRST면 `api_spec_approved=true`가 필요하고 SOURCE_SYNC/AUDIT/NOT_REQUIRED는 `not_required`다.

모두 승인된 순간:

```text
NO_EXTRA_KANBAN_CONFIRMATION
→ prepare_dispatch.py 정확히 한 번
→ dev-skill-preflight
→ approved model snapshot 확인
→ kanban_create tool 1회 (initial_status=blocked)
→ kanban_show tool 1회
→ notification subscribe
→ registration notification enqueue
→ kanban_unblock
→ worker dispatch
```

다음 질문은 금지한다.

```text
Kanban 작업 카드를 등록할까요?
Coder/Reviewer 흐름으로 배정해도 될까요?
이제 실제 작업을 시작할까요?
```

단, **추가 요구사항 자체를 정식 승인받는 `[추가 요구사항 확인]` Gate와 필요한 `[API 규격 승인]` Gate는 생략하면 안 된다.**

## 모델 snapshot

Tier 승인 직후:

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py resolve --tier "<DEFAULT|PREMIUM>"
```

성공 계약:

```text
MODEL_TIER=<DEFAULT|PREMIUM>
MODEL=<resolved model>
PROVIDER=<resolved provider>
REVIEWER_MODEL=DEFAULT
MODEL_ESCALATION=REQUIRE_REAPPROVAL
STATUS=resolved
```

Task body에도 `Model Escalation: REQUIRE_REAPPROVAL`을 기록한다. Task 생성 시 `model=<MODEL>`, `provider=<PROVIDER>`로 snapshot을 고정하고 `dev-flow-model-policy`를 runtime pin한다. 동일 승인 모델 retry는 재승인하지 않는다. Tier/Provider/Model 변경은 재승인 대상이다.

## 신규/대체 Task 승인 불변식

`대체 카드 생성 승인` 자체는 각 Gate 승인을 대신하지 않는다. 기존 승인 뒤 범위가 바뀐 대체 Task는 **Requirement Delta Approval + 필요한 API Spec Approval + 갱신된 Plan Approval**을 반드시 가진다. Project/Workspace/Branch/Existing Changes/Model은 delta에 따라 각각 REUSE 또는 REQUIRED다. 모든 필요한 Gate 승인 후에는 Kanban 생성 자체를 다시 승인받지 않는다.

## Workspace / Branch 성능 계약

승인 Gate 중에는 working-tree 전체 scan을 하지 않는다. repository/workspace/current branch/base branch identity 조회만 허용한다.

기존 변경 전체 보존이 승인되면:

```text
prepare_dispatch.py --confirmed-dirty
WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation
```

이후 exact count를 복구하려고 `git status`, `git diff`, `git ls-files`를 다시 실행하지 않는다.

Coder/Reviewer도 전체 저장소를 재스캔하지 않는다.

```text
Coder → change_summary.py --include <changed-path>...
Reviewer → review_context.py --include <changed-path>...
```

API `SOURCE_SYNC`/`AUDIT`도 Task/도메인 범위의 bounded scan을 기본으로 하며, 전체 API 감사가 명시된 경우에만 범위를 넓힌다.

## Kanban 생성·최초 알림 단일 경로

```text
prepare_dispatch PASS
→ skill preflight PASS
→ kanban_create(initial_status=blocked)
→ kanban_show read-back PASS
→ subscribe_notification.py
→ NOTIFY_STATUS=subscribed + NOTIFY_VERIFIED=true
→ NOTIFY_REGISTRATION_EVENT=queued
→ unblock
→ dispatch
```

알림 구독은 task 생성 이후에 이루어지므로, 구독 완료 후 `registered` event를 enqueue해야 최초 등록 알림이 history cursor에 묻히지 않는다. 등록 이벤트 enqueue 실패는 알림 Gate 실패로 보고 unblock하지 않는다. 알림이 명시적으로 disabled인 경우 기존 정책대로 최초 등록 알림도 생략한다.

Board는 `.hermes/project.yaml`의 managed board만 사용한다. `hermes project list`, `hermes project --help`, Kanban body 임시 파일, CLI body-file capability probing은 금지한다. 알림 실패 시 기존 `dev-workspace-dispatch`의 차단 계약을 따른다.

Coder/Reviewer 모델 전이는 `dev-flow-model-policy`의 `review-enter` / `changes-return` 계약을 사용하며 Reviewer profile DEFAULT를 유지한다.

세부 성능 규칙은 `references/dispatch-efficiency.md`를 따른다.
