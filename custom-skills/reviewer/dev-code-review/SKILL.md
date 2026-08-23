---
name: dev-code-review
description: 동일 Workspace의 미커밋 구현을 계획/AC 기준으로 독립 검토하고 승인·수정요청·차단한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, reviewer, kanban, quality, verification]
    related_skills: [dev-implement-plan, dev-review-cycle, dev-workspace-dispatch]
    requires_tools: [terminal, kanban_show, kanban_request_changes, kanban_complete, kanban_block, kanban_heartbeat]
---

# dev-code-review

## 실행 계약
1. `kanban_show()`에서 original requirement/plan/AC, coder handoff, attempts/comments를 읽는다.
2. 같은 `$HERMES_KANBAN_WORKSPACE`에서 `scripts/review_context.py --base-branch <Base Branch> --base-sha <Base SHA>`로 dispatch Base SHA/Expected Branch를 검증한다.
3. dispatch Base SHA에 고정된 tracked diff, full status, untracked files, `git diff --check`와 필요한 주변 flow를 read-only로 확인한다. `BASE_BRANCH_DRIFTED`는 별도 metadata로 보고하되 diff 기준을 바꾸지 않는다.
4. Goal/AC/approved scope/correctness/compatibility/security/tests와 coder verification evidence를 비교한다.
5. P0/P1이 있으면 `kanban_request_changes`; 없고 evidence가 충분하면 APPROVED `kanban_complete`; 안전한 판단 자체가 불가능하거나 외부 결정이 필요하면 `BLOCKED`로 `kanban_block` 중 정확히 하나만 실행하고 멈춘다.

## 불변식
- Reviewer는 application/test/config source를 수정하지 않는다.
- untracked source/test/config를 누락하지 않고 style/nit만으로 승인을 막지 않는다.
- finding은 file/symbol, evidence, required change, expected verification이 있는 실행 가능한 내용이어야 한다.
- secret/raw credential을 출력하지 않고 commit, push, PR, cleanup하지 않는다.
- 같은 중요한 blocker가 3 review cycle 지속되면 needs_input으로 escalation한다.
- CHANGES_REQUESTED는 terminal 상태가 아니며 Card를 original coder에게 돌려 같은 Workspace의 수정 loop를 계속한다. Reviewer가 직접 고치거나 Orchestrator가 정상 round 사이에 개입하지 않는다.

Severity, checklist, verdict metadata와 escalation 세부 기준이 필요하면 `references/review-details.md`를 먼저 읽는다.
