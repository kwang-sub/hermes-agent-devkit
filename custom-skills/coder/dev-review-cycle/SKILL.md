---
name: dev-review-cycle
description: 동일 Kanban card/workspace에서 coder와 reviewer가 risk 기반 Fast Flow와 필수 Standard review loop를 수행하는 프로토콜.
version: 0.4.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, workflow, coder, reviewer, kanban]
    related_skills: [dev-implement-plan, dev-code-review]
    requires_tools: [kanban_show, kanban_request_review, kanban_request_changes, kanban_complete, kanban_block]
---

# dev-review-cycle

```text
Fast LOW: coder running → kanban_complete → done
Fast REVIEW_REQUIRED / Standard:
coder running → kanban_request_review → reviewer → APPROVED/done | CHANGES_REQUESTED/original coder ready
```

## 허용 전이
- `Flow: FAST`이고 `Review Risk: LOW`이며 targeted verification이 충분한 최초 구현은 Coder가 risk evidence를 남기고 `kanban_complete`할 수 있다.
- Fast `REVIEW_REQUIRED`, 모든 Standard Flow, 모든 `CHANGES_REQUESTED` 재작업은 Coder가 동일 Card/Workspace에서 `kanban_request_review`하고 멈춘다.
- Reviewer는 source를 수정하지 않고 정확히 하나만 호출한다: APPROVED=`kanban_complete`, 수정 가능한 P0/P1=`kanban_request_changes`, 판단 불가/외부 결정/반복 blocker=`kanban_block`.
- CHANGES_REQUESTED는 terminal 상태가 아니다. Card는 original coder에게 ready로 돌아가고 같은 Workspace에서 수정 후 반드시 다시 review를 요청한다.

## 금지 전이
- Standard Flow의 Coder self-approval 또는 LOW 근거 없는 Fast `kanban_complete`.
- review가 이미 시작된 Card에서 Coder가 LOW로 재분류해 reviewer를 우회하는 것.
- 구현 완료 후 review 대용 `kanban_block`, 새 review card 생성.
- Reviewer source 수정, P0/P1을 둔 APPROVED, 수정 가능한 finding을 BLOCKED로 종료.
- Orchestrator가 정상 coder↔reviewer round 사이에 개입하는 것.

동일 중요 blocker가 3 review cycle 지속되면 Reviewer가 `kind=needs_input`으로 human escalation한다. 정상 완료는 `workspace remains + no commit/push`이며 cleanup하지 않는다.

상세 risk metadata/상태 전이는 `references/review-protocol.md`를 읽는다.