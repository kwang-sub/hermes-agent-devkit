# dev-review-cycle 상세 계약

Coder와 Reviewer가 하나의 implementation Card와 동일 Workspace를 재사용한다. **Standard Flow는 항상 Reviewer**, Fast Flow는 구현 후 risk 판정에 따라 LOW self-complete 또는 Reviewer 인계다. 이 문서는 coder/reviewer profile에 동일하게 유지한다.

## 1. 상태 전이

```text
Fast Flow
coder running
  ├─ Review Risk LOW + verification PASS
  │    └─ kanban_complete → done
  └─ REVIEW_REQUIRED
       └─ kanban_request_review → reviewer
            ├─ APPROVED → kanban_complete → done
            ├─ CHANGES_REQUESTED → original coder ready → fix → review
            └─ BLOCKED → kanban_block

Standard Flow
coder running → kanban_request_review → reviewer
  ├─ APPROVED → done
  ├─ CHANGES_REQUESTED → original coder ready → fix → review
  └─ BLOCKED → human/external resolution
```

## 2. Coder

Coder는 `kanban_show`, 동일 Workspace/Branch, verification, change summary를 유지한다.

Fast LOW self-complete는 다음 조건에서만 허용된다.
- `Flow: FAST`
- 최초 implementation round
- `Review Risk: LOW` 근거 존재
- public API/schema/entity relation/dependency/transaction/security/concurrency/complex query/common architecture 위험 없음
- targeted verification PASS
- residual risk가 낮음

LOW completion metadata에는 `review_risk=LOW`, `review_skipped=true`, risk reasons, changed files, exact verification, residual risk, Base SHA를 남긴다.

다음은 무조건 Reviewer에게 보낸다.
- Standard Flow
- Fast `REVIEW_REQUIRED`
- 한 번이라도 `CHANGES_REQUESTED`가 발생한 Card
- LOW 여부가 불확실함

Coder의 `kanban_block`은 workspace mismatch, 계약 누락, 필수 검증 불가, scope escalation 같은 genuine blocker에만 허용된다.

## 3. Reviewer

Reviewer는 source를 수정하지 않고 read-only inspection/test 후 정확히 하나를 실행한다.
- APPROVED → `kanban_complete`
- 수정 가능한 P0/P1 → `kanban_request_changes`
- 판단 불가/외부 입력/동일 중요 blocker 3회 → `kanban_block`

CHANGES_REQUESTED는 terminal 상태가 아니다. original coder가 동일 Workspace에서 blocking finding만 수정하고 반드시 다시 review를 요청한다.

## 4. 금지 전이

- Standard Flow Coder self-complete
- Fast Flow에서 LOW evidence 없이 `kanban_complete`
- review가 시작된 Card의 Coder가 LOW로 재분류해 Reviewer 우회
- Coder가 구현 완료 후 review 대신 `kanban_block`
- 정상 correction을 위한 새 Review Card/Workspace
- Reviewer의 application/test/config/workflow source 수정
- P0/P1을 둔 APPROVED
- 수정 가능한 finding을 BLOCKED로 종료
- commit, push, PR, cleanup, branch 전환, workspace 제거

## 5. Retry / escalation

동일 중요 blocker가 3 review cycle 동안 해결되지 않으면 Reviewer는 `kanban_block(kind=needs_input)`하고 repeated finding, round evidence, 실패 이유, 필요한 human decision, 재개 조건을 남긴다.

## 6. 완료 의미

```text
Kanban status = done
Workspace = remains
working tree = uncommitted changes may remain
publication = no commit/push/PR
```

Fast LOW 완료도 Reviewer APPROVED 완료도 publication/cleanup 허가가 아니다.
