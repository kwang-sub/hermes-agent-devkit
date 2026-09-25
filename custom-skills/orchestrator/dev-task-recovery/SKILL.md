---
name: dev-task-recovery
description: Hermes Kanban의 blocked Task를 보드 선택 → 차단 카드 선택 → 원인/복구 계획 승인 3단 Gate로 분석하고, 기존 Task ID를 유지한 채 durable Contract Revision과 SAME_TASK_RESUME을 수행하는 orchestrator 전용 recovery workflow.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, recovery, kanban, blocked, resume, orchestrator, approval, triage, task, contract-revision]
    related_skills: [dev-workflow-orchestrate, dev-breakdown, dev-workspace-dispatch, dev-flow-model-policy]
    requires_tools: [terminal, skill_view, clarify, kanban_list, kanban_show, kanban_comment, kanban_unblock]
---

# dev-task-recovery

기존 Kanban Task가 `blocked` 상태에서 멈췄을 때 새 카드를 우선 만들지 않고, **현재 카드의 차단 원인을 읽고 필요한 범위만 승인받아 같은 Task ID로 재개**하는 Orchestrator 전용 Workflow다.

사용자 진입 예:

```text
리커버 플로우 실행해줘
차단된 작업 복구해줘
t_9ed73170 복구해줘
```

Task ID가 입력되어도 Gate 1/2를 생략하지 않는다. 해당 Task가 후보 목록에 있으면 추천/강조만 할 수 있다.

Recovery Flow의 사용자 승인 Gate는 **정확히 3개**다.

```text
RECOVERY_GATE_COUNT=3

Gate 1 [보드 선택]
→ Gate 2 [차단 카드 선택]
→ read-only 원인 분석
→ Gate 3 [복구 계획 승인]
→ durable Recovery Revision
→ same Task unblock
```

일반 Standard Flow의 Project/Workspace/Branch/Model/Plan Gate를 Recovery 정상 경로 뒤에 추가하지 않는다. Recovery 범위를 넘는 독립 결정이 필요하면 `REPLACEMENT_REQUIRED`로 종료하고 별도 Standard Flow로 넘긴다.

상세 edge case와 Recovery Revision 형식은 `references/recovery-details.md`를 필요할 때 읽는다.

## 1. 적용 대상

정상 자동 재개 대상:

```text
task.status == blocked
현재 Task ID / Board / Workspace / Branch / Coder Model을 재사용할 수 있음
현재 최종 Deliverable을 유지할 수 있음
현재 blocker를 bounded delta로 해결 가능
```

기본 Recovery Mode 우선순위:

```text
RETRY_SAME_CONTRACT
→ SAME_TASK_RESUME
→ REPLACEMENT_REQUIRED
```

새 카드 생성은 기본값이 아니다.

## 2. Gate 1 — 보드 선택

먼저 사용자가 접근 가능한 live board를 read-only로 조회한다.

```bash
python3 /opt/custom-skills/orchestrator/dev-task-recovery/scripts/recovery_board_inventory.py
```

helper는 정확히 다음 read-only CLI만 사용한다.

```text
hermes kanban boards list --json
```

다음을 금지한다.

```text
boards switch
boards create
boards rename
boards rm
현재 board pointer 변경
```

일반 메시지에 board display name, slug, blocked count를 보여준 다음 독립 `clarify`를 호출한다.

```text
question:
  [보드 선택]
  복구할 작업이 있는 보드를 선택해주세요.
choices:
  - <board display name> (<slug>)
  - ...
```

첫 번째 Gate가 승인되기 전에 Task 후보를 선택시키지 않는다.

후보가 많으면 최대 20개를 choice로 보여주고, `Other (type your answer)`에서 정확한 board slug를 받을 수 있다. 자유 입력 slug도 helper inventory에 존재하는 live board인지 다시 검증한 뒤 같은 Gate를 승인 처리한다.

## 3. Gate 2 — 차단 카드 선택

Gate 1에서 승인된 board를 명시해 Orchestrator tool을 사용한다.

```text
kanban_list(
  board=<APPROVED_BOARD>,
  status="blocked",
  limit=200
)
```

Task 목록 조회를 위해 `hermes kanban list` shell fallback을 사용하지 않는다.

사용자에게 최소 다음을 보여준다.

```text
<Task ID> — <Title>
상태: BLOCKED
Assignee: <profile | none>
```

그 다음 독립 `clarify`:

```text
question:
  [차단 카드 선택]
  원인을 분석하고 복구할 카드를 선택해주세요.
choices:
  - <task_id> — <title>
  - ...
```

choice는 최대 20개다. 더 많은 blocked 카드가 있으면 전체 count를 알리고 `Other`에서 Task ID를 받을 수 있다. 입력된 Task ID는 반드시:

```text
selected board에 존재
status == blocked
```

를 `kanban_show(board=..., task_id=...)`로 다시 확인한다.

`triage`, `done`, `archived`, `running`, `review` 카드는 이 v0.1 Recovery Gate 2의 자동 재개 후보가 아니다. 특히 반복 block-loop breaker로 `triage`가 된 카드는 `kanban_unblock` 대상이 아니므로 억지로 같은 경로에서 상태를 직접 수정하지 않는다.

## 4. 카드 선택 후 원인 분석 — 승인 없는 Read-only 단계

Gate 2가 승인되면 다음을 정확한 board/task에 대해 읽는다.

```text
kanban_show(board=<APPROVED_BOARD>, task_id=<APPROVED_TASK>)
```

최소 분석 대상:

```text
task.title / body / status
assignee
workspace_kind / workspace_path
project_id
model_override / provider_override
completion_contract
last_failure_error
parents / unsatisfied_parents
comments
events
runs
worker_context
```

필요한 경우 Task workspace/source를 bounded read-only로 확인한다. 원인 분석 단계에서 source/config/dependency/Kanban state를 수정하지 않는다.

차단 원인은 가능한 범위에서 다음으로 분류한다.

```text
ENVIRONMENT
DEPENDENCY
BUILD_POLICY
APPLICATION_SOURCE
TEST_CONTRACT
VERIFICATION_CONTRACT
WORKSPACE
BRANCH
API_CONTRACT
DATA_CONTRACT
INFRASTRUCTURE
SCOPE_MISMATCH
TRANSIENT
UNKNOWN
```

## 5. Recovery Mode 판정

### RETRY_SAME_CONTRACT

다음과 같으면 기존 계약을 변경하지 않는다.

```text
일시적 외부 장애/환경 blocker가 이미 해결됨
기존 Goal/AC/scope/implementation plan 변경 불필요
동일 Workspace/Branch/Model 재사용 가능
```

### SAME_TASK_RESUME

같은 최종 Deliverable을 완성하기 위한 bounded delta면 같은 카드를 우선한다.

예:

```text
누락 dependency / lockfile 정합성
같은 기능의 application source 누락/불일치
현재 test와 구현 계약의 bounded 정합성 수정
검증 command/type generation/config 보정
동일 기능 범위의 environment/config 수정
현재 AC를 충족하기 위해 필수인 작은 scope 확장
```

다음은 새 카드를 만드는 이유가 아니다.

```text
파일 수가 늘어남
여러 capability가 필요함
dependency + source + test를 같이 고쳐야 함
Coder가 최초 Plan에서 누락한 정합성 작업이 발견됨
```

### REPLACEMENT_REQUIRED

다음이면 같은 카드에서 억지로 확장하지 않는다.

```text
Work Unit Class 자체가 달라짐
기존 Excluded Follow-up Scope에 해당
독립 승인 artifact가 필요
새 API 의미 계약에 별도 API Spec Approval 필요
새 Data DESIGN / physical MIGRATION 단계 필요
독립 Infrastructure Desired State 결정 필요
Project / Workspace / Branch / Coder Model을 새로 선택해야 함
현재 최종 Deliverable과 다른 기능이 목표가 됨
```

이 경우 Recovery Gate 3에서 방향을 승인받을 수는 있지만 현재 blocked Task는 자동 unblock하지 않는다. durable escalation comment를 남기고 `dev-workflow-orchestrate`의 별도 Standard Flow로 전환한다.

## 6. Gate 3 — 복구 계획 승인

원인 분석 결과와 방향을 **일반 메시지로 먼저** 보여준다.

필수 형식:

```text
Task Recovery Analysis

Board:
<slug>

Task:
<task_id>
<title>

Current Status:
BLOCKED

Block Cause:
- <fact/evidence>
- ...

Cause Class:
<one or more classifications>

Recovery Mode:
RETRY_SAME_CONTRACT | SAME_TASK_RESUME | REPLACEMENT_REQUIRED

Contract Delta:
- <change | NONE>

Preserved Contract:
- <existing requirement/constraint>

Recovery Plan:
- <bounded step>
- ...

Acceptance Criteria:
- <existing/updated criterion>

Verification:
- <commands/evidence>

Forbidden:
- <unsafe/unrelated actions>
```

그 뒤 독립 `clarify` 하나만 호출한다.

```text
question:
  [복구 계획 승인]
  위 Recovery Plan을 승인할까요?
choices:
  - 복구 계획 승인
  - 보류
```

`Other` 입력은 Recovery Plan 수정 요청이다. 반영 후 **같은 Gate 3**을 다시 보여준다. 새 승인 Gate를 만들지 않는다.

`복구 계획 승인`은 정상 Recovery 경로의 단일 의사결정이며:

```text
RETRY_SAME_CONTRACT
→ retry 승인

SAME_TASK_RESUME
→ bounded Requirement Delta + Recovery Plan 승인
```

으로 취급한다. Board와 Task는 이미 Gate 1/2에서 승인되었고, Workspace/Branch/Model/API Spec처럼 독립 의사결정이 새로 필요한 경우는 애초에 `REPLACEMENT_REQUIRED`이므로 이 Gate에 합치지 않는다.

## 7. Gate 3 승인 후 — Durable Revision

Gate 3 승인 전에는 다음을 호출하지 않는다.

```text
kanban_comment
kanban_unblock
kanban_create
task mutation CLI
```

### RETRY_SAME_CONTRACT

다음 marker를 포함한 durable comment를 남긴다.

```text
TASK_RECOVERY_RETRY_V1

Recovery Gate: APPROVED
Recovery Mode: RETRY_SAME_CONTRACT
Block Cause:
...
Resolution Evidence:
...
Original Contract: PRESERVED
Acceptance Criteria: PRESERVED
```

### SAME_TASK_RESUME

다음 marker를 포함한 Contract Revision comment를 남긴다.

```text
TASK_RECOVERY_REVISION_V1

Recovery Gate: APPROVED
Recovery Mode: SAME_TASK_RESUME

Requirement Delta:
- Changed:
- Preserved:
- Rollback/Removal:
- Forbidden:
- Reverification:

Recovery Plan:
- ...

Acceptance Criteria:
- ...

Approval Reuse:
- Project: REUSE
- Workspace: REUSE
- Branch: REUSE
- Coder Model: REUSE
- API Spec: REUSE | NOT_REQUIRED

Original Contract: PRESERVED
Revision Authority: LATEST_APPROVED_RECOVERY_REVISION
```

댓글은:

```text
kanban_comment(
  board=<APPROVED_BOARD>,
  task_id=<APPROVED_TASK>,
  body=<REVISION>
)
```

로 기록한다.

## 8. Revision Read-back Gate — 사용자 Gate 아님

comment 성공만 믿고 unblock하지 않는다. 같은 Task를 `kanban_show`로 다시 읽고 다음을 확인한다.

```text
task id 동일
status == blocked
새 comment에 예상 marker 존재
Recovery Gate: APPROVED 존재
Recovery Mode 일치
```

실패하면 Task를 unblock하지 않고 Recovery 자체를 BLOCKED로 보고한다.

## 9. 같은 Task 재개

Read-back PASS 후에만:

```text
kanban_unblock(
  board=<APPROVED_BOARD>,
  task_id=<APPROVED_TASK>
)
```

을 정확히 1회 호출한다.

성공 후 다시 `kanban_show`를 읽고:

```text
task id 동일
status == ready | todo
```

를 확인한다.

`todo`는 open parent dependency가 남아 있는 정상 상태일 수 있으므로 새 카드를 만들지 않는다. `ready`가 되면 기존 assignee/model/workspace 계약으로 dispatcher가 같은 Task의 새 worker run을 시작한다.

Recovery 정상 경로에서는:

```text
kanban_create 금지
새 Task ID 생성 금지
기존 Task body 덮어쓰기 금지
Original Contract 삭제 금지
Base SHA history 삭제 금지
```

다음 worker는 `kanban_show`의 comment/worker_context를 통해 최신 승인 Recovery Revision을 읽고 이를 기존 Task 계약에 합성한다.

## 10. REPLACEMENT_REQUIRED 처리

Gate 3에서 방향이 승인되면:

```text
TASK_RECOVERY_ESCALATION_V1
Recovery Gate: APPROVED
Recovery Mode: REPLACEMENT_REQUIRED
Reason: ...
Current Task: PRESERVE_BLOCKED
Next Flow: dev-workflow-orchestrate
```

comment를 남기고 read-back한다.

현재 Task에는 `kanban_unblock`을 호출하지 않는다. 새 카드 생성도 이 Skill에서 하지 않는다. 이후 Standard Flow가 자신의 Project/API/Workspace/Branch/Model/Plan 승인 계약을 적용한다.

## 11. 3-Gate 불변식

```text
Gate 1 = Board 선택
Gate 2 = blocked Task 선택
Gate 3 = Recovery Plan 승인
```

- Gate 1 승인 전 Gate 2 금지.
- Gate 2 승인 전 Task 분석/선정 확정 금지.
- Gate 3 승인 전 Kanban mutation 금지.
- 정상 Recovery에서 Gate 3 뒤 추가 사용자 승인 금지.
- same deliverable이면 `SAME_TASK_RESUME`를 새 카드보다 우선한다.
- 독립 결정이 필요하면 Recovery Gate를 늘리지 않고 `REPLACEMENT_REQUIRED`로 종료한다.
- Recovery는 application implementation을 Orchestrator가 직접 수행한다는 뜻이 아니다. Orchestrator는 분석/승인/계약 revision/unblock만 담당한다.
