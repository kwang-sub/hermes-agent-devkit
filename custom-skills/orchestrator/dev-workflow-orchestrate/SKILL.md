---
name: dev-workflow-orchestrate
description: Jira/text 개발 요청의 project·workspace·branch·Coder 모델·plan을 독립 승인 Gate로 확인한 뒤 coder/reviewer로 dispatch하는 orchestrator 전용 workflow.
version: 0.8.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, workflow, orchestrator, approval, gate, breakdown, dispatch, kanban, model, performance]
    related_skills: [dev-work-intake, dev-project-resolve, dev-project-bootstrap, dev-breakdown, dev-skill-preflight, dev-workspace-dispatch, dev-flow-model-policy]
---

# dev-workflow-orchestrate

개발 요청의 상태 머신만 조정한다. Orchestrator는 application/test code, refactor, code review를 직접 하지 않고 commit, push, PR, merge, destructive cleanup도 하지 않는다.

Standard Flow의 모든 사용자 승인 UI는 `/opt/data/shared/references/approval-gate-rules.md`를 canonical contract로 사용한다. Gate 문구를 자유형으로 만들거나 서로 다른 의사결정을 한 질문에 합치지 않는다.

## 상태 머신

신규 Standard Flow:

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
→ dev-workspace-dispatch
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
→ REQUIRED Gate를 각각 독립 수행 또는 승인 REUSE
→ MODEL_APPROVED_OR_MIGRATED
→ SAME_TASK_RESUMED
→ coder ↔ reviewer
→ DONE/BLOCKED
```

흐름:

1. 요구사항을 Common Work Item으로 정규화한다.
2. managed project를 확정하고 Project Approval Gate를 통과한다.
3. `dev-breakdown`으로 READY 계획을 생성한다. 이 시점의 계획은 기술적 초안이며 아직 사용자 승인 상태가 아니다.
4. `/opt/data/shared/references/approval-gate-rules.md` 순서대로 Workspace → Branch → Existing Changes(필요 시) → Coder Model을 **각각 별도 turn의 Gate**로 승인받는다.
5. 승인된 Coder Model Tier를 `/opt/data/shared/scripts/flow_model_policy.py resolve --tier <DEFAULT|PREMIUM>`으로 실제 provider/model에 해석한다.
6. 마지막으로 한국어 Implementation Plan을 정형화된 Plan Approval Gate로 제시하고 승인받는다.
7. 모든 독립 Gate가 승인된 뒤에만 `dev-workspace-dispatch`를 실행해 workspace/branch, Base SHA와 모델 snapshot을 확정한다.
8. Skill preflight 후 `kanban_create` / `kanban_show`로 Task를 생성·검증한다.
9. 이후 Coder/Reviewer 흐름에 맡긴다. Reviewer는 별도 모델 승인 없이 항상 Reviewer profile DEFAULT를 사용한다.

## 공통 승인 Gate 불변식

한 번의 사용자 확인에서는 **하나의 의사결정만** 요청한다.

금지 예:

```text
Workspace <x>, Branch <y>, PREMIUM 모델을 사용하겠습니다?
이 Workspace와 브랜치, 모델로 계획까지 승인하시겠습니까?
```

허용 순서:

```text
[Workspace 선택] → 사용자 응답 → STOP
[Branch 선택] → 사용자 응답 → STOP
[기존 변경 보존 확인] → 사용자 응답 → STOP (필요한 경우)
[Coder 모델 선택] → 사용자 응답 → STOP
[작업 계획 승인] → 사용자 응답 → STOP
```

각 Gate에서 `추가 요구사항`, 수정 요청, 다른 후보 지정 등 승인 이외 응답이 들어오면 요구사항/후보를 갱신하고 **같은 Gate를 다시 출력**한다. 해당 응답을 승인으로 해석하거나 다음 Gate로 넘어가지 않는다.

승인 상태는 독립적으로 취급한다.

```text
workspace_approved = false
branch_approved = false
existing_changes_approved = false | not_required
model_approved = false
plan_approved = false
```

Dispatch는 다음이 모두 참일 때만 허용한다.

```text
workspace_approved
AND branch_approved
AND (existing_changes_approved OR existing_changes_not_required)
AND model_approved
AND plan_approved
```

## Workspace Approval Gate

`dev-breakdown READY` 후 첫 실행 Gate다.

```text
[Workspace 선택]

작업에 사용할 Workspace를 확인해주세요.

현재 제안:
- Workspace: <workspace>

1. 제안된 Workspace 사용
2. 다른 Workspace 지정
3. 추가 요구사항 입력

번호 또는 요구사항을 입력해주세요.
```

`1`만 현재 후보 승인이다. `2`, `3`, 자연어 요구사항은 후보/요구사항을 반영하고 같은 Gate를 다시 출력한다.

Workspace 승인 전 working-tree 전체 scan을 하지 않는다. repository/workspace identity 확인만 허용한다.

## Branch Approval Gate

Workspace 승인 다음에 별도로 수행한다.

```text
[Branch 선택]

작업에 사용할 Branch를 확인해주세요.

현재 제안:
- Branch mode: <current | create>
- Branch: <branch>
- Base Branch: <base-branch>

1. 제안된 Branch 사용
2. 다른 Branch 지정
3. 추가 요구사항 입력

번호 또는 요구사항을 입력해주세요.
```

Workspace와 Branch는 같은 질문에 합치지 않는다. Branch mode/name 변경 요청 후에는 같은 Branch Gate를 다시 승인받는다.

## Existing Changes Approval Gate

기존 변경 보존 승인이 아직 없을 때만 별도로 수행한다.

```text
[기존 변경 보존 확인]

현재 Workspace의 기존 변경 처리 방식을 확인해주세요.

기본 정책:
- reset/restore/stash/clean 금지
- 기존 변경 전체 보존

1. 기존 변경을 모두 보존하고 진행
2. 상태 확인 후 다시 결정
3. 추가 요구사항 입력

번호 또는 요구사항을 입력해주세요.
```

사용자가 기존 변경 전체 보존을 승인하면 이후 `prepare_dispatch.py --confirmed-dirty`를 사용하고 repository-wide dirty/EOL/untracked 분류를 생략한다.

`2`를 선택한 경우에만 helper의 full classification 결과를 확인할 수 있으며, 결과 제시 후 같은 Gate를 다시 출력한다.

## Coder Model Approval Gate

Workspace/Branch/기존 변경 정책과 합치지 않고 별도로 수행한다.

```text
[Coder 모델 선택]

이번 작업에서 Coder가 사용할 모델 등급을 선택해주세요.

1. PREMIUM
2. DEFAULT
3. 추가 요구사항 입력

번호 또는 요구사항을 입력해주세요.
```

규칙:
- `1` → PREMIUM 승인.
- `2` → DEFAULT 승인.
- `3` 또는 자연어 요구사항 → 요구사항만 반영하고 같은 Gate 재출력.
- `PREMIUM 모델을 사용하겠습니다?`, `<실제 모델명>을 사용하시겠습니까?` 같은 자유형 질문만 출력하지 않는다.
- Reviewer는 선택지에 넣지 않는다. Reviewer Model은 항상 DEFAULT다.

실제 모델은 ENV에 의해 결정되므로 Gate에서 실제 모델명을 정책으로 하드코딩하지 않는다. Tier 승인 직후 정확히 한 번 다음 helper로 해석한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py resolve --tier "<DEFAULT|PREMIUM>"
```

최소 성공 출력:

```text
MODEL_TIER=<DEFAULT|PREMIUM>
MODEL=<resolved model>
PROVIDER=<resolved provider>
REVIEWER_MODEL=DEFAULT
MODEL_ESCALATION=REQUIRE_REAPPROVAL
STATUS=resolved
```

이 해석 결과는 승인 snapshot이다. 이후 ENV가 바뀌어도 현재 Task에는 다시 resolve하지 않는다. Coder Model Tier/Provider/Model 변경은 사용자 재승인 없이는 금지한다.

## Plan Approval Gate

모든 실행 후보가 확정된 뒤 마지막 승인으로 수행한다.

```text
[작업 계획 승인]

다음 작업 계획을 확인해주세요.

<Implementation Plan>

1. 승인
2. 차단
3. 수정 또는 추가 요구사항 입력

번호 또는 요구사항을 입력해주세요.
```

규칙:
- `1` → 현재 Plan 승인.
- `2` → BLOCKED 유지. 자동 dispatch 금지.
- `3` 또는 자연어 수정 요청 → `dev-breakdown` 계획을 갱신하고 **동일 Plan Gate를 다시 출력**한다.
- 계획 수정/추가 요구사항을 Plan 승인으로 해석하지 않는다.
- Plan 승인 전 `prepare_dispatch.py`, `kanban_create`, `kanban_unblock`을 실행하지 않는다.

## 기존 카드 재작업 계약

사용자가 `t_xxxxxxxx`처럼 기존 Kanban Task를 명시하고 수정/재검토를 요청하면 새 Task 생성보다 같은 Task 재개를 우선한다.

먼저 `kanban_show`로 다음을 확인한다.

```text
Task id/status
Project / Workspace / Branch
기존 요구사항/계획/승인 관련 Task body와 comments
현재 assignee/lane
model_override/provider_override
Model Policy snapshot 존재 여부
```

### 승인 재사용 원칙

기존 승인 증거가 Task body/comment/history에 명시적으로 남아 있고 새 요청이 그 승인 범위를 바꾸지 않으면 해당 Gate만 REUSE할 수 있다.

```text
Project Approval
- 같은 managed project면 기존 승인 재사용 가능

Workspace Approval
- 동일 workspace이며 승인 증거가 있으면 REUSE
- workspace가 바뀌거나 증거가 없으면 REQUIRED

Branch Approval
- 동일 branch mode/name이며 승인 증거가 있으면 REUSE
- branch 전략/이름이 바뀌거나 증거가 없으면 REQUIRED

Existing Changes Approval
- 기존 변경 보존 정책이 그대로면 REUSE
- 처리 정책이 바뀌면 REQUIRED

Coder Model Approval
- 기존 Model Policy snapshot이 있으면 동일 모델 재시도는 재승인 없음
- snapshot이 없는 pre-policy 활성 Task면 Coder Model Tier만 승인받고 same-card migration

Plan Approval
- 기존 구현 계획의 목표/범위를 실질적으로 바꾸지 않는 보정이면 REUSE 가능
- acceptance criteria, 주요 구현 방식, 파괴적 작업 여부가 바뀌면 REQUIRED
```

**승인 증거가 없다는 이유만으로 승인됐다고 추정하지 않는다.** `새 카드 생성 승인`, `재개 승인`, `수정 진행 승인` 같은 문구는 다른 Gate 승인을 대신하지 않는다.

### 요구사항 변경 시 Gate 판정

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

`REQUIRED`가 여러 개여도 한 질문에 합치지 않는다. canonical Gate 순서에 따라 하나씩 수행한다.

다음은 Plan 재승인 대상이다.

```text
대상 DB를 명시적으로 변경/고정
DROP/cleanup 금지처럼 파괴적 작업 정책 변경
새로운 acceptance criteria 추가
기존 구현을 다시 검토하여 결함 수정 요구
```

### pre-policy 활성 Task 모델 migration

기존 Task에 Model Policy snapshot이 없지만 Task가 활성 상태라면 새 카드를 만들지 않는다. Coder Model Tier Gate 승인 후 현재 lane에 맞춰 실행한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py migrate-existing \
  --tier <DEFAULT|PREMIUM> \
  --lane <coder|reviewer> \
  --board <board> \
  --task-id <task>
```

성공 조건:

```text
STATUS=legacy-task-migrated
SNAPSHOT_SOURCE=durable-comment
```

`done`/`archived` terminal Task에 후속 작업이 필요한 경우에만 새 Task를 고려한다.

## 신규/대체 Task 승인 불변식

새 Task가 필요해도 다음을 생략하지 않는다.

```text
WORKSPACE_APPROVED
→ BRANCH_APPROVED
→ EXISTING_CHANGES_APPROVED | NOT_REQUIRED
→ MODEL_APPROVED
→ PLAN_APPROVED
→ model snapshot 확인
→ dev-workspace-dispatch
→ skill preflight
→ kanban_create
```

`새 카드 생성 승인`, `대체 카드 생성 승인`, `다시 카드 만들어 진행`, `재작업 카드 생성 승인`은 Task 생성 의도만 의미하며 Workspace/Branch/Existing Changes/Model/Plan 승인을 대신하지 않는다.

## Workspace / Branch 상태 검사 단일화 계약

승인 Gate 진행 중에는 working-tree 전체 scan을 하지 않는다. 허용되는 것은 repository/workspace/current branch/base branch 같은 identity 조회뿐이다.

금지:

```text
git status
git diff --name-only
git diff --ignore-cr-at-eol
git ls-files --others
inline Python tracked/effective/EOL 분류
```

### Existing changes preservation fast path

기존 변경 전체 보존 승인 후 반드시:

```text
prepare_dispatch.py --confirmed-dirty
```

를 사용한다. 이 경우 repository-wide dirty/EOL/untracked 분류를 생략하며 다음이 정상이다.

```text
WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation
WORKSPACE_DIRTY=unknown
WORKSPACE_EFFECTIVE_DIRTY=unknown
EFFECTIVE_CHANGED_COUNT=-1
EOL_ONLY_COUNT=-1
HERMES_MANAGED_COUNT=-1
```

이후 exact count 복구를 위해 `git status`, `git diff`, `git ls-files`, 별도 helper를 실행하지 않는다.

**정상 dispatch에서 `prepare_dispatch.py`는 정확히 한 번 실행한다.**

## Kanban 생성 단일 경로 계약

```text
prepare_dispatch PASS
→ dev-skill-preflight PASS
→ approved model snapshot 확인
→ kanban_create tool 1회
→ kanban_show tool 1회
→ notification subscribe helper 1회
→ worker dispatch
```

`kanban_create`에는 승인 snapshot을 직접 전달한다.

```text
model=<MODEL>
provider=<PROVIDER>
skills에 dev-flow-model-policy 포함
```

Task body에는 반드시 다음을 기록한다.

```text
Model Policy:
- Coder Model Tier: <MODEL_TIER>
- Coder Model: <MODEL>
- Coder Provider: <PROVIDER>
- Reviewer Model: DEFAULT
- Model Escalation: REQUIRE_REAPPROVAL
```

다음 capability probing/fallback은 금지한다.

```text
hermes kanban ... create --help
hermes project list
hermes project --help
Kanban body 임시 파일
CLI body-file capability probing
```

Board는 `.hermes/project.yaml`의 managed board를 명시적으로 사용한다.

`kanban_show` read-back에서 다음도 검증한다.

```text
model_override == MODEL
provider_override == PROVIDER
Task body Coder Model Tier/Model/Provider == 승인 snapshot
Reviewer Model == DEFAULT
Model Escalation == REQUIRE_REAPPROVAL
```

불일치하면 worker를 unblock/dispatch하지 않는다.

## Coder / Reviewer 모델 전이

Task에는 `dev-flow-model-policy`를 runtime pin한다.

```text
Coder
- 승인된 task model_override/provider_override 사용
- 동일 승인 모델 retry는 재승인 없음
- Reviewer handoff 직전 flow_model_policy.py review-enter

Reviewer
- task model override가 cleared 상태 → Reviewer profile DEFAULT
- CHANGES_REQUESTED 직전 flow_model_policy.py changes-return
- 원래 Coder model/provider snapshot 복원
```

Reviewer의 PREMIUM 자동 escalation은 금지한다.

## Coder / Reviewer 대형 Workspace 계약

```text
Coder
→ 실제 구현 Changed Files 확정
→ change_summary.py --include <changed-path>...

Reviewer
→ Coder Changed Files 재사용
→ review_context.py --include <changed-path>...
```

정상 Standard Flow에서 scope 없는 `change_summary.py` / `review_context.py` 호출은 금지한다. 전체 scan은 명시적 diagnostic mode에서만 허용한다.

## 불변식

- `/opt/data/shared/references/approval-gate-rules.md`가 Standard Flow 사용자 승인 UI의 canonical contract다.
- 서로 다른 승인 Gate를 한 질문으로 합치지 않는다.
- 추가 요구사항 입력은 승인으로 간주하지 않고 같은 Gate를 다시 출력한다.
- 이전 Gate에서 승인된 값을 이후 Gate에서 다시 묻지 않는다.
- `.hermes/project.yaml`의 managed metadata만 사용하며 repo/Board/profile을 추측하지 않는다.
- Task Key, branch, Base SHA는 helper 계약을 따른다.
- `Applicable Skills`와 runtime pinned `task.skills`를 동일시하지 않는다.
- approval 없는 bootstrap/branch/worktree/Kanban 생성 금지.
- Coder Model approval 없는 worker dispatch 금지.
- Coder Model Tier/Provider/Model 변경은 사용자 재승인 없이는 금지.
- Reviewer는 DEFAULT 고정이며 PREMIUM 자동 승격 금지.
- pre-policy 활성 Task는 모델 정책 때문에 새 카드를 강제 생성하지 않는다.
- 대체 Task 생성 승인을 다른 Gate 승인으로 해석하지 않는다.
- Orchestrator는 commit, push, PR, merge를 수행하지 않는다.
- 원격 저장소에 직접 기록하는 제목/설명/commit 메시지는 한국어를 기본으로 한다.

세부 성능 규칙은 `references/dispatch-efficiency.md`를 따른다.
