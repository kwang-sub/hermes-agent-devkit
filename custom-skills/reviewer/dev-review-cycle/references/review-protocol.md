# dev-review-cycle 상세 계약

Coder와 Reviewer는 하나의 implementation Card와 동일 Workspace를 재사용한다. **Direct와 Standard Flow는 모두 Reviewer 필수**다. 이 문서는 coder/reviewer profile에 동일하게 유지한다.

## 1. 상태 전이

```text
Direct | Standard
coder running
→ kanban_request_review
→ reviewer DEFAULT
  ├─ APPROVED → kanban_complete → done
  ├─ CHANGES_REQUESTED → original coder ready → fix → review
  └─ BLOCKED → kanban_block
```

`kanban_request_review`와 `kanban_request_changes` 내부의 trusted lifecycle handler가 승인 모델의 review-enter/changes-return 전이를 담당한다. Worker가 shell에서 model override를 직접 바꾸지 않는다.

## 2. Coder

Coder는 `kanban_show`, 동일 Workspace/Branch, Work Unit Boundary, verification, scoped change summary를 유지한다.

다음은 모두 Reviewer에게 보낸다.
- Direct Flow
- Standard Flow
- 한 번이라도 `CHANGES_REQUESTED`가 발생한 Card

Risk가 낮거나 변경 파일이 작아도 Coder self-complete는 허용하지 않는다. `kanban_block`은 workspace mismatch, 계약 누락, 필수 검증 불가, Direct/Work Unit scope escalation 같은 genuine blocker에만 사용한다.

## 3. Reviewer

Reviewer는 source를 수정하지 않고 read-only inspection/test 후 정확히 하나를 실행한다.
- APPROVED → `kanban_complete`
- 수정 가능한 P0/P1 → `kanban_request_changes`
- 판단 불가/외부 입력/동일 중요 blocker 3회 → `kanban_block`

CHANGES_REQUESTED는 terminal 상태가 아니다. original coder가 동일 Workspace에서 blocking finding만 수정하고 반드시 다시 review를 요청한다.

## 4. 모델 전이

```text
Coder approved model/provider
→ kanban_request_review 내부 review-enter
→ Reviewer profile DEFAULT
→ kanban_request_changes 내부 changes-return
→ approved Coder model/provider 복원
```

- Coder/Reviewer가 `flow_model_policy.py review-enter|changes-return` 또는 `hermes kanban set-model`을 shell에서 직접 호출하지 않는다.
- lifecycle 실패 시 다음 lane으로 진행하지 않고 capability blocker로 종료한다.
- retry 때 ENV를 재해석하지 않고 Task 승인 snapshot을 유지한다.

## 5. 금지 전이

- Direct/Standard Coder self-complete
- LOW risk를 이유로 Reviewer 우회
- Coder가 구현 완료 후 review 대신 `kanban_block`
- 정상 correction을 위한 새 Review Card/Workspace
- Reviewer의 application/test/config/workflow source 수정
- P0/P1을 둔 APPROVED
- 수정 가능한 finding을 BLOCKED로 종료
- commit, push, PR, cleanup, branch 전환, workspace 제거

## 6. Retry / escalation

동일 중요 blocker가 3 review cycle 동안 해결되지 않으면 Reviewer는 `kanban_block(kind=needs_input)`하고 repeated finding, round evidence, 실패 이유, 필요한 human decision, 재개 조건을 남긴다.

Direct Task가 승인 scope를 벗어나면 Coder가 `DIRECT_SCOPE_EXCEEDED`로 block하고 Orchestrator가 Standard Flow/Requirement Delta로 재분류한다.

## 7. 완료 의미

```text
Kanban status = done
Workspace = remains
working tree = uncommitted changes may remain
publication = no commit/push/PR
```

Reviewer APPROVED 완료는 publication/cleanup 허가가 아니다.
