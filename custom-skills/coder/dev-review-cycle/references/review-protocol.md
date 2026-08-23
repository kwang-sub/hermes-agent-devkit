# dev-review-cycle 상세 계약

Coder와 Reviewer가 하나의 implementation Card와 동일 Workspace를 재사용하며 제한된 review loop를 수행하는 공통 계약이다. 이 문서는 coder/reviewer profile에 동일한 내용으로 유지한다.

## 1. 상태와 소유권

```text
coder running
  └─ kanban_request_review(reviewer=<configured reviewer>)
       └─ review (reviewer owns the card)
            ├─ APPROVED → kanban_complete → done
            ├─ CHANGES_REQUESTED → kanban_request_changes → original coder ready
            │    └─ same Workspace fix → kanban_request_review → review
            └─ BLOCKED → kanban_block(kind=needs_input|capability|transient)
```

최초 Implementation Card가 모든 round의 Task Body, Attempt, Comment, Handoff Metadata, Workspace와 Branch 이력을 보존한다. CHANGES_REQUESTED는 terminal 상태가 아니라 original coder에게 돌아가는 수정 loop다. 정상 수정 때문에 새 Review Task를 만들지 않는다.

## 2. 허용 상태 전이

### Coder

1. `kanban_show`로 original plan, prior attempts, comments와 review feedback을 읽는다.
2. 승인된 동일 Workspace/Branch에서 최초 구현 또는 blocking finding 수정만 수행한다.
3. 영향받은 검증, `git diff --check`, change summary를 실행한다.
4. changed files, exact verification, residual risk, addressed feedback, verified Base SHA를 handoff metadata에 기록한다.
5. 구현이 완료되면 `kanban_request_review`만 호출하고 즉시 멈춘다.

Coder의 `kanban_block`은 workspace mismatch, 계약 누락, 필수 검증 불가, 구현을 막는 외부 입력처럼 구현 완료에 도달할 수 없는 genuine blocker에만 허용된다.

### Reviewer

Reviewer는 source를 수정하지 않고 read-only inspection/test만 수행한 뒤 다음 중 정확히 하나를 실행한다.

- APPROVED: P0/P1이 없고 evidence가 충분하면 `kanban_complete`.
- CHANGES_REQUESTED: original coder가 source 변경으로 해결할 수 있는 P0/P1이면 `kanban_request_changes`.
- BLOCKED: 안전한 판단 자체가 불가능하거나 외부 결정/입력이 필요하거나 동일 중요 blocker가 제한 횟수를 소진했으면 `kanban_block`.

한 review round에서 verdict action을 둘 이상 실행하지 않는다. Verdict action 후에는 작업을 멈춘다.

## 3. 금지 상태 전이

- Coder가 구현 또는 수정 후 `kanban_complete`로 self-approval하는 것.
- Coder가 구현 완료 상태에서 review 대신 `kanban_block`하는 것.
- Coder가 정상 review correction을 위해 새 Card나 Workspace를 만드는 것.
- Reviewer가 application, test, config 또는 workflow source를 직접 수정하는 것.
- Reviewer가 P0/P1을 남긴 채 APPROVED `kanban_complete`하는 것.
- Reviewer가 original coder가 수정 가능한 finding을 BLOCKED로 종료하는 것.
- Reviewer가 `kanban_request_changes` 후 같은 round에서 `kanban_complete`나 `kanban_block`도 호출하는 것.
- Orchestrator가 정상 coder↔reviewer round 사이에 개입해 status/assignee를 수동 대체하는 것.
- 어느 역할이든 commit, push, PR, cleanup, branch 전환, workspace 제거를 수행하는 것.

## 4. CHANGES_REQUESTED 수정 loop

`kanban_request_changes`는 현재 review run을 닫고 Card를 original coder에게 requeue한다. Card는 done이나 blocked가 아니며 동일 Workspace가 보존된다. 다음 coder attempt는 올바른 기존 구현을 유지하고 blocking finding만 최소 수정한다. Reviewer reason은 file/symbol, evidence, required change, expected verification을 포함해야 한다. Coder는 처리한 finding과 재실행한 검증을 다음 `kanban_request_review` metadata에 기록한다.

새로운 별개 finding은 기존 blocker의 반복 횟수에 합산하지 않는다. Plan 밖 독립 작업은 현재 Card에 조용히 포함하지 않고 별도 follow-up 후보로 기록한다. 현재 correctness에 필수이며 product/architecture 결정이 필요한 scope 충돌은 BLOCKED로 사람에게 넘긴다.

## 5. Retry와 human escalation

동일한 중요한 blocker가 3 review cycle 동안 실질적으로 해결되지 않으면 Reviewer는 다시 request_changes하지 않는다. `kanban_block(kind=needs_input)`을 정확히 한 번 호출하고 다음을 남긴다.

- repeated finding과 영향
- 세 round의 attempt/evidence
- 이전 수정이 해결하지 못한 이유
- 필요한 human decision 또는 input
- 재개 조건

이 escalation은 구현 가능한 첫 번째/두 번째 finding이나 서로 다른 새 finding에는 적용하지 않는다. 환경의 일시 장애는 필요에 따라 transient, 권한/접근의 hard wall은 capability를 사용하되 source 수정 요구와 혼동하지 않는다.

## 6. Orchestrator 개입 경계

Orchestrator는 승인된 plan과 workspace contract를 dispatch하기 전까지 결정권을 가진다. Dispatch 후 정상 review correction은 coder와 reviewer가 동일 Card에서 직접 반복한다. Orchestrator 개입은 다음 예외로 제한한다.

- 승인 scope 밖 product/architecture 결정
- contract 또는 workspace를 안전하게 복구할 수 없는 불일치
- 동일 중요 blocker 3회 반복에 대한 human escalation
- 현재 Card와 독립적인 follow-up 작업의 routing

Orchestrator가 review verdict를 대신하거나 정상 CHANGES_REQUESTED를 새 implementation Card로 바꾸지 않는다.

## 7. Handoff metadata

Implementation review request 권장 metadata:

```json
{
  "phase": "implementation",
  "review_verdict": null,
  "changed_files": [],
  "verification": [],
  "residual_risk": [],
  "review_feedback_addressed": [],
  "base_sha": "<verified Base SHA>"
}
```

APPROVED completion 권장 metadata:

```json
{
  "phase": "review",
  "review_verdict": "APPROVED",
  "blocking_findings": [],
  "non_blocking_findings": [],
  "verification": [],
  "residual_risk": [],
  "base_sha": "<verified Base SHA>",
  "base_branch_drifted": false
}
```

Metadata에는 secret, credential, raw PII를 기록하지 않는다.

## 8. 완료 의미와 Git 경계

APPROVED 뒤 정상 상태는 다음과 같다.

```text
Kanban status = done
Workspace = remains
working tree = uncommitted changes may remain
publication = no commit/push/PR
```

따라서 `done`은 workspace cleanup이나 publication 허가가 아니다. 별도 승인된 후속 단계 전에는 branch 전환, commit, push, PR 생성, reset, clean, stash 또는 workspace 제거를 하지 않는다.

## 9. 종료 조건

Review loop의 terminal 결과는 `APPROVED → done` 또는 genuine `BLOCKED → human/external resolution`뿐이다. CHANGES_REQUESTED는 original coder ready로 이어지는 비-terminal 전이다. Coder는 request-review 외 성공 terminal action을 소유하지 않으며 Reviewer만 세 verdict action 중 정확히 하나를 소유한다.
