---
name: dev-review-cycle
description: 동일 Kanban card/workspace에서 coder와 reviewer가 제한된 구현 리뷰 loop를 수행하는 프로토콜.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, workflow, coder, reviewer, kanban]
    related_skills: [dev-implement-plan, dev-code-review]
    requires_tools: [kanban_show, kanban_request_review, kanban_request_changes, kanban_complete, kanban_block]
---

# dev-review-cycle

`coder running → kanban_request_review → reviewer review → APPROVED/done | CHANGES_REQUESTED/original coder ready → repeat`

## 허용 전이
- Coder는 동일 Card와 동일 Workspace에서 구현·검증 후 `kanban_request_review`만 호출하고 멈춘다. 구현 불가나 필수 입력 누락 때만 `kanban_block`할 수 있다.
- Reviewer는 source를 수정하지 않고 verdict에 따라 정확히 하나만 호출한다: APPROVED는 `kanban_complete`, 수정 가능한 P0/P1은 `kanban_request_changes`, 안전한 판단 불가·외부 결정 필요·반복 blocker는 `kanban_block`.
- CHANGES_REQUESTED는 terminal 상태가 아니다. Card는 original coder에게 ready로 돌아가고 같은 Workspace에서 수정 후 다시 review를 요청한다.

## 금지 전이
- Coder의 self-approval 또는 `kanban_complete`, 구현 완료 후 `kanban_block`, 새 review card 생성.
- Reviewer의 source 수정, P0/P1을 둔 APPROVED, 수정 가능한 finding을 BLOCKED로 종료, 한 round에서 복수 verdict action 실행.
- Orchestrator가 정상 coder↔reviewer round 사이에 개입하거나 status를 수동 대체하는 것.

동일 중요 blocker가 3 review cycle 지속되면 Reviewer가 `kind=needs_input`으로 human escalation한다. 정상 APPROVED 결과는 `done + workspace remains + no commit/push`이며 uncommitted change를 cleanup하지 않는다. Plan 밖 독립 작업만 별도 follow-up으로 분리한다.

Handoff metadata와 retry/scope 세부 기준이 필요하면 `references/review-protocol.md`를 읽는다.
