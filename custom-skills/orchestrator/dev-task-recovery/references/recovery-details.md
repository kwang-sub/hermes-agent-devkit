# dev-task-recovery 상세 계약

이 문서는 `dev-task-recovery`의 edge case, read-only evidence, durable revision 형식을 보존한다. 기본 실행에서는 `SKILL.md`만 사용하고 필요한 절만 읽는다.

## 1. Recovery Flow 상태 머신

```text
START
→ BOARD_INVENTORY_READY
→ BOARD_APPROVED
→ BLOCKED_TASK_INVENTORY_READY
→ TASK_APPROVED
→ TASK_INSPECTED
→ RECOVERY_ANALYSIS_READY
→ RECOVERY_PLAN_APPROVED
→ REVISION_COMMENTED
→ REVISION_READBACK_VERIFIED
→ SAME_TASK_UNBLOCKED
→ RESUMED
```

`REPLACEMENT_REQUIRED`이면:

```text
RECOVERY_PLAN_APPROVED
→ ESCALATION_COMMENTED
→ ESCALATION_READBACK_VERIFIED
→ CURRENT_TASK_PRESERVED_BLOCKED
→ STANDARD_FLOW_REQUIRED
```

## 2. Board Inventory

Gate 1의 board inventory는 live board만 보여준다.

사용 helper:

```bash
python3 /opt/custom-skills/orchestrator/dev-task-recovery/scripts/recovery_board_inventory.py
```

helper는:

```text
hermes kanban boards list --json
```

만 실행한다.

JSON payload가 list 또는 `{"boards": [...]}` 형태여도 다음 normalized payload로 바꾼다.

```json
{
  "status": "pass",
  "source": "hermes kanban boards list --json",
  "current": "chagok",
  "count": 2,
  "boards": [
    {
      "slug": "chagok",
      "name": "Chagok",
      "is_current": true,
      "blocked_count": 2,
      "total": 7
    }
  ]
}
```

archived board는 Gate 1 후보에서 제외한다.

board helper failure는 임의 filesystem scan으로 fallback하지 않는다.

## 3. Gate UI

Recovery Gate는 `clarify` 하나당 질문 하나다.

### Gate 1

```text
[보드 선택]
복구할 작업이 있는 보드를 선택해주세요.
```

### Gate 2

```text
[차단 카드 선택]
원인을 분석하고 복구할 카드를 선택해주세요.
```

### Gate 3

Recovery Plan 전체는 일반 메시지에 먼저 표시하고 질문은 다음 고정 리터럴을 사용한다.

```text
[복구 계획 승인]
위 Recovery Plan을 승인할까요?
```

Gate 3 choices:

```text
복구 계획 승인
보류
```

Gate 1/2에서 `Other`가 반환되면 해당 값을 현재 inventory에서 read-back 검증하고 **같은 Gate**를 다시 확정한다. 이것은 Gate 추가가 아니다.

## 4. Blocked Task Inventory

Task discovery는 반드시 Orchestrator `kanban_list`를 사용한다.

```text
board=<Gate 1 approved slug>
status=blocked
limit=200
```

표시 label:

```text
<task_id> — <title>
```

선택 직전 또는 자유 입력 Task ID 사용 시:

```text
kanban_show(board=<slug>, task_id=<id>)
```

로 status를 다시 확인한다.

status가 이미 바뀌었으면 stale candidate이므로 Gate 2를 다시 만든다.

## 5. Read-only 원인 분석

Gate 2 이후 Gate 3 이전에는 mutation이 없다.

허용:

```text
kanban_show
bounded source/config/test read
git identity/base/branch read-only 확인
dependency manifest/lockfile read
existing verification evidence read
```

금지:

```text
source edit
dependency install/update
lockfile mutation
kanban_comment
kanban_unblock
kanban_create
git reset/restore/clean/stash
branch switch/create
```

### 우선 evidence

```text
1. task.last_failure_error
2. 최근 blocked/crashed/timed_out/gave_up event
3. 최근 task run error/summary/metadata
4. Coder/Reviewer durable comments
5. original task body / completion_contract
6. current repository evidence
```

원인과 추측을 구분한다.

```text
Observed:
- actual tool/error/task evidence

Inferred:
- probable relationship requiring validation

Unknown:
- evidence unavailable
```

## 6. SAME_TASK_RESUME 판정

다음 질문으로 판단한다.

```text
1. 최종 Deliverable이 동일한가?
2. Work Unit Class가 동일한가?
3. Project/Workspace/Branch/Model을 재사용할 수 있는가?
4. 독립 승인 artifact가 새로 필요한가?
5. 기존 Excluded Follow-up Scope를 침범하는가?
```

`1=yes, 2=yes, 3=yes, 4=no, 5=no`이면 bounded 변경은 기본적으로 `SAME_TASK_RESUME` 후보다.

Scope가 늘어난다는 이유만으로 새 카드를 만들지 않는다.

## 7. Recovery Revision 번호

Task comment에서 기존 marker를 확인한다.

```text
TASK_RECOVERY_REVISION_V1
TASK_RECOVERY_REVISION_V2
...
```

가장 큰 revision 번호 + 1을 사용한다.

Retry marker는 계약 revision 번호와 별개다.

```text
TASK_RECOVERY_RETRY_V1
```

동일 Task에서 여러 retry가 필요하면 V2, V3로 증가시킨다.

Escalation:

```text
TASK_RECOVERY_ESCALATION_V1
```

## 8. Recovery Revision canonical body

```text
TASK_RECOVERY_REVISION_V<N>

Recovery Gate: APPROVED
Recovery Mode: SAME_TASK_RESUME
Board: <slug>
Task: <task_id>
Approved At: <timestamp if available>

Block Cause:
- ...

Cause Class:
- ...

Requirement Delta:
- Changed:
  - ...
- Preserved:
  - ...
- Rollback/Removal:
  - ...
- Forbidden:
  - ...
- Reverification:
  - ...

Recovery Plan:
- ...

Acceptance Criteria:
- ...

Approval Reuse:
- Project: REUSE
- Workspace: REUSE
- Branch: REUSE
- Existing Changes: REUSE | NOT_REQUIRED
- Coder Model: REUSE
- API Spec: REUSE | NOT_REQUIRED
- Work Unit Boundary: REUSE

Original Contract: PRESERVED
Revision Authority: LATEST_APPROVED_RECOVERY_REVISION
```

Timestamp를 임의로 만들지 않는다. 현재 time evidence가 없으면 `Approved At`을 생략한다.

## 9. Retry canonical body

```text
TASK_RECOVERY_RETRY_V<N>

Recovery Gate: APPROVED
Recovery Mode: RETRY_SAME_CONTRACT
Board: <slug>
Task: <task_id>

Block Cause:
- ...

Resolution Evidence:
- ...

Original Contract: PRESERVED
Acceptance Criteria: PRESERVED
```

## 10. Escalation canonical body

```text
TASK_RECOVERY_ESCALATION_V<N>

Recovery Gate: APPROVED
Recovery Mode: REPLACEMENT_REQUIRED
Board: <slug>
Task: <task_id>

Reason:
- ...

Preserved Evidence:
- ...

Current Task: PRESERVE_BLOCKED
Next Flow: dev-workflow-orchestrate
```

## 11. Gate 3 승인 후 pre-mutation revalidation

Gate 3 승인 직후 `kanban_comment` 전에 동일 board/task를 `kanban_show`로 다시 읽는다.

필수 확인:

```text
task.id == Gate 2 approved task
task.status == blocked
active/running claim 없음
Gate 2 분석 시점 이후 더 큰 approved TASK_RECOVERY_REVISION_V<N> 없음
```

다르면:

```text
RECOVERY_STATUS=STALE_RECOVERY_SELECTION
```

으로 종료한다. comment/unblock을 호출하지 않는다. 이 read-back은 사용자 승인 Gate가 아니며 새 clarify를 추가하지 않는다.

## 12. Durable read-back

`kanban_comment`이 성공한 뒤 반드시 `kanban_show`를 다시 호출한다.

확인:

```text
selected board/task 동일
status == blocked
comments에 expected marker 존재
Recovery Gate: APPROVED 존재
Recovery Mode 일치
```

가장 최근 comment만 대충 보고 성공으로 간주하지 않는다. expected marker가 실제 comment thread에 존재해야 한다.

## 13. Unblock

정상 Recovery만:

```text
kanban_unblock(board=<approved board>, task_id=<approved task>)
```

정확히 1회 호출한다.

성공 payload 또는 read-back이:

```text
ready
todo
```

중 하나여야 한다.

`todo`면 부모 dependency가 남아 있는 상태이므로 수동 ready 전환을 하지 않는다.

## 14. 반복 차단

같은 Recovery Revision 이후 같은 원인으로 다시 blocked 되면 새 카드를 즉시 만들지 않는다.

먼저 다시 Recovery Flow를 시작한다.

다만 다음이면 `REPLACEMENT_REQUIRED` 후보로 높인다.

```text
같은 approved recovery plan을 수행했는데 동일 root cause 재발
원인 evidence가 이전 plan과 충돌
bounded delta가 반복적으로 확대
Work Unit boundary를 넘기 시작함
```

Hermes의 unblock recurrence breaker가 task를 `triage`로 올린 경우 이 v0.1 skill은 raw status mutation으로 우회하지 않는다.

## 15. Triage 제한

`kanban_unblock`은 blocked Task recovery tool이다. 따라서 Gate 2는 `status=blocked`만 선택 가능하다.

`triage` 카드는 별도 orchestration attention 상태다.

Recovery Skill이 triage card를 발견하더라도:

```text
자동 unblock 금지
DB 직접 UPDATE 금지
dashboard API raw status 변경 금지
```

로 유지한다.

향후 Hermes가 orchestrator-safe triage recovery tool을 제공하면 별도 version에서 확장한다.

## 16. Re-dispatch contract

`kanban_unblock` 이후 새 Task를 만들지 않는다.

기존 Task의 durable metadata:

```text
task id
assignee
workspace
model/provider override
parents/children
original body
comments
```

를 재사용한다.

다음 worker는 latest approved Recovery Revision comment를 읽고 기존 계약과 합성한다.

Coder는 Original Contract와 Latest Approved Recovery Revision이 충돌하면 latest Recovery Revision의 **명시적 delta만** 우선하고, 나머지 Original Contract는 유지한다.

## 17. Failure behavior

### Board inventory 실패

```text
RECOVERY_STATUS=BLOCKED
BLOCKER=BOARD_INVENTORY_UNAVAILABLE
```

임의 board를 추측하지 않는다.

### Blocked candidate 없음

```text
RECOVERY_STATUS=NO_BLOCKED_TASK
```

Gate 2를 만들지 않는다.

### Task status drift

Gate 2 후보 조회 후 Task가 더 이상 blocked가 아니면:

```text
RECOVERY_STATUS=STALE_TASK_SELECTION
```

Gate 2를 다시 구성한다.

### Stale recovery selection

Gate 3 승인 후 pre-mutation read-back에서 status/claim/revision이 바뀌면:

```text
RECOVERY_STATUS=STALE_RECOVERY_SELECTION
```

comment/unblock을 수행하지 않는다.

### Revision persistence 실패

```text
RECOVERY_STATUS=BLOCKED
BLOCKER=RECOVERY_REVISION_NOT_PERSISTED
```

unblock 금지.

### Unblock 실패

댓글은 durable history로 남긴다.

```text
RECOVERY_STATUS=BLOCKED
BLOCKER=KANBAN_UNBLOCK_FAILED
```

같은 mutation을 자동 반복하지 않는다.
