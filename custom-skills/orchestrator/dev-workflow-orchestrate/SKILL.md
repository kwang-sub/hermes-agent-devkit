---
name: dev-workflow-orchestrate
description: Jira/text 개발 요청의 project·workspace·branch·Coder 모델·plan을 독립 clarify Gate로 승인한 뒤 자동 Kanban dispatch하는 orchestrator 전용 workflow.
version: 0.9.2
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, workflow, orchestrator, approval, clarify, gate, dispatch, kanban, model, performance]
    related_skills: [dev-work-intake, dev-project-resolve, dev-project-bootstrap, dev-breakdown, dev-skill-preflight, dev-workspace-dispatch, dev-flow-model-policy]
---

# dev-workflow-orchestrate

Orchestrator는 개발 요청의 상태 머신만 조정한다. application/test code, refactor, code review, commit, push, PR, merge, destructive cleanup은 직접 하지 않는다. 계획/진행 보고와 승인 질문은 **한국어**로 작성한다.

Standard Flow의 모든 사용자 승인 UI는 `/opt/data/shared/references/approval-gate-rules.md`를 canonical contract로 사용한다. **한 번의 사용자 확인에서는 하나의 의사결정만 요청한다.** 선택은 일반 텍스트 번호 목록이 아니라 Hermes 내장 `clarify` tool의 `choices`로 제공한다. TUI/CLI에서는 ↑/↓ + Enter 선택 UX를 사용한다.

핵심 불변식은 `Project Approval`, `Plan Approval`, Workspace/Branch/Model 승인, 그리고 dispatch 시점의 `Base SHA` 보존이다.

## 상태 머신

```text
START
→ WORK_ITEM_READY
→ PROJECT_APPROVED
→ dev-breakdown READY
→ WORKSPACE_APPROVED
→ BRANCH_APPROVED
→ EXISTING_CHANGES_APPROVED | NOT_REQUIRED
→ MODEL_APPROVED
→ PLAN_APPROVED
→ AUTO_DISPATCH
→ SKILL_PREFLIGHT
→ KANBAN_CREATED
→ coder ↔ reviewer
→ DONE/BLOCKED
```

기존 카드 재작업:

```text
EXISTING_TASK
→ TASK_INSPECTED
→ REQUIREMENT_DELTA_READY
→ REQUIRED Gate 각각 clarify 또는 REUSE
→ MODEL_APPROVED_OR_MIGRATED
→ SAME_TASK_RESUMED
→ coder ↔ reviewer
→ DONE/BLOCKED
```

## 신규 Standard Flow

1. `dev-work-intake`로 요구사항을 정규화한다.
2. `dev-project-resolve` 결과를 `[Project 선택]` clarify Gate로 승인받는다. 이것이 Project Approval이다.
3. `dev-breakdown`으로 READY 계획을 만든다.
4. `[Workspace 선택]` → `[Branch 선택]` → `[기존 변경 보존 확인]`(필요 시) → `[Coder 모델 선택]`을 각각 독립 clarify Gate로 승인받는다.
5. 승인된 Tier를 `flow_model_policy.py resolve --tier <DEFAULT|PREMIUM>`으로 정확히 한 번 해석한다.
6. Implementation Plan 본문을 보여준 뒤 `[작업 계획 승인]` clarify Gate를 수행한다. 이것이 Plan Approval이다.
7. Plan까지 승인되면 **추가 Kanban 생성 확인 없이 즉시 AUTO_DISPATCH**한다.
8. `prepare_dispatch.py`가 승인 workspace/branch의 `Base SHA`를 확정하고 Task body에 보존한다.

## clarify Gate 계약

선택지는 질문 본문에 번호로 쓰지 않고 `clarify.questions[].choices`에 넣는다. 첫 번째 choice는 Hermes가 Recommended로 표시하므로 현재 권장값을 첫 번째에 둔다. `Other (type your answer)`는 추가 요구사항 입력 경로다.

Project:

```text
question: [Project 선택] <project/repository/base branch 요약>
choices: [제안된 프로젝트 사용, 다른 프로젝트 지정]
```

Workspace:

```text
question: [Workspace 선택] 현재 제안: <workspace>
choices: [제안된 Workspace 사용, 다른 Workspace 지정]
```

Branch:

```text
question: [Branch 선택] mode=<current|create>, branch=<branch>, base=<base>
choices: [제안된 Branch 사용, 다른 Branch 지정]
```

기존 변경:

```text
question: [기존 변경 보존 확인] reset/restore/stash/clean 금지, 기존 변경 전체 보존
choices: [기존 변경을 모두 보존하고 진행, 상태 확인 후 다시 결정]
```

Coder Model:

```text
question: [Coder 모델 선택] 이번 작업의 Coder 모델 등급
choices: [<권장 Tier>, <나머지 Tier>]
```

선택 가능한 Tier는 `DEFAULT | PREMIUM`뿐이다. Reviewer Model은 항상 DEFAULT이며 선택 Gate를 만들지 않는다. Agent가 PREMIUM을 추천할 수는 있지만 자동 escalation은 금지한다.

Plan:

```text
question: [작업 계획 승인] 위 Implementation Plan을 어떻게 처리할까요?
choices: [승인, 차단]
```

`Other` 또는 다른 후보 지정/수정 요구는 승인으로 간주하지 않는다. 요구사항을 갱신한 뒤 **같은 Gate를 다시 출력**한다. Workspace와 Branch는 같은 질문에 합치지 않는다.

## 자동 Kanban Dispatch 불변식

승인 상태:

```text
project_approved = false
workspace_approved = false
branch_approved = false
existing_changes_approved = false | not_required
model_approved = false
plan_approved = false
```

모두 승인된 순간:

```text
NO_EXTRA_KANBAN_CONFIRMATION
→ prepare_dispatch.py 정확히 한 번
→ dev-skill-preflight
→ approved model snapshot 확인
→ kanban_create tool 1회
→ kanban_show tool 1회
→ notification subscribe
→ kanban_unblock
→ worker dispatch
```

다음 질문은 금지한다.

```text
Kanban 작업 카드를 등록할까요?
Coder/Reviewer 흐름으로 배정해도 될까요?
이제 실제 작업을 시작할까요?
```

Plan 승인 전에는 `prepare_dispatch.py`, `kanban_create`, `kanban_unblock`을 실행하지 않는다.

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

## 기존 카드 재작업 계약

먼저 `kanban_show`로 Task id/status, Project/Workspace/Branch, 기존 Plan/승인 증거, assignee/lane, model_override/provider_override, Model Policy snapshot을 확인한다.

```text
Requirement Delta:
- 변경 요구사항
- 유지 요구사항
- 금지 작업
- 재검토 범위

Approval Reuse:
- Project: REUSE | REQUIRED
- Workspace: REUSE | REQUIRED
- Branch: REUSE | REQUIRED
- Existing Changes: REUSE | REQUIRED | NOT_REQUIRED
- Coder Model: REUSE | REQUIRED | MIGRATE
- Plan: REUSE | REQUIRED
```

`REQUIRED`가 여러 개여도 서로 다른 승인 Gate를 한 질문으로 합치지 않는다. canonical 순서로 하나씩 clarify한다.

pre-policy 활성 Task는 새 카드를 만들지 않고 모델 승인 후:

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py migrate-existing \
  --tier <DEFAULT|PREMIUM> \
  --lane <coder|reviewer> \
  --board <board> \
  --task-id <task>
```

성공 조건은 `STATUS=legacy-task-migrated`, `SNAPSHOT_SOURCE=durable-comment`다. `done`/`archived` terminal Task에 후속 작업이 필요한 경우에만 새 Task를 고려한다.

## 신규/대체 Task 승인 불변식

`대체 카드 생성 승인` 자체는 각 Gate 승인을 대신하지 않는다. 새 Task가 필요하면 Project/Workspace/Branch/Existing Changes/Model/Plan Gate를 각각 승인 또는 명시적 REUSE한 뒤 자동 생성한다. 모든 Gate 승인 후에는 **Kanban 생성 자체를 다시 승인받지 않는다.**

## Workspace / Branch 성능 계약

승인 Gate 중에는 working-tree 전체 scan을 하지 않는다. repository/workspace/current branch/base branch identity 조회만 허용한다.

기존 변경 전체 보존이 승인되면:

```text
prepare_dispatch.py --confirmed-dirty
WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation
```

이후 exact count를 복구하려고 `git status`, `git diff`, `git ls-files`를 다시 실행하지 않는다. 정상 dispatch에서 `prepare_dispatch.py`는 정확히 한 번만 수행한다.

Coder/Reviewer도 전체 저장소를 재스캔하지 않는다.

```text
Coder → change_summary.py --include <changed-path>...
Reviewer → review_context.py --include <changed-path>...
```

## Kanban 생성 단일 경로

```text
prepare_dispatch PASS
→ skill preflight PASS
→ kanban_create tool 1회
→ kanban_show tool 1회
→ notification subscribe
→ unblock
→ dispatch
```

Board는 `.hermes/project.yaml`의 managed board만 사용한다. `hermes project list`, `hermes project --help`, Kanban body 임시 파일, CLI body-file capability probing은 금지한다. 알림 실패 시 기존 `dev-workspace-dispatch`의 차단 계약을 따른다.

Coder/Reviewer 모델 전이는 `dev-flow-model-policy`의 `review-enter` / `changes-return` 계약을 사용하며 Reviewer profile DEFAULT를 유지한다.

세부 성능 규칙은 `references/dispatch-efficiency.md`를 따른다.
