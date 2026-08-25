---
name: dev-implement-plan
description: 승인 계획을 할당 Workspace에서 최소 구현·검증하고 commit/push 없이 reviewer에게 인계한다.
version: 0.4.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review, fast-flow]
    related_skills: [dev-fast-flow, dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_block, kanban_heartbeat]
---

# dev-implement-plan

## 실행 계약
1. 먼저 `kanban_show()`로 body, attempts, comments, feedback을 읽는다.
2. `$HERMES_KANBAN_WORKSPACE`에서 `scripts/verify_workspace.py --base-sha <Base SHA>`로 Task Key, approved Workspace/Git root, Expected Branch, dispatch Base SHA resolve 및 HEAD ancestor 관계를 검증한다. mismatch면 수정 전에 BLOCKED다.
3. Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Risks, Expected/Base Branch, Reviewer Profile이 있는지 확인한다.
4. `Flow: FAST` Task라면 실제 source를 수정하기 전에 Fast Flow 범위가 여전히 유효한지 확인한다. 모호한 제품 의도, architecture 결정, public API/DB schema 변경, cross-repository 작업, dependency 변경, materially broader scope가 발견되면 구현을 확장하지 않고 `FAST_FLOW_ESCALATION_REQUIRED`로 `kanban_block`한다.
5. 실제 source/flow/config/tests/pattern을 확인하고 승인 scope를 만족하는 최소 변경만 구현한다. reviewer 재작업이면 blocking finding만 처리한다.
6. targeted verification부터 실행하고 `git diff --check` 및 `scripts/change_summary.py`로 tracked/untracked/status를 수집한다.
7. 정확한 command/result와 검증된 `BASE_SHA`, residual risk를 기록하고 configured `reviewer`에게 `kanban_request_review`만 호출한 뒤 멈춘다. 구현 완료 상태에서 `kanban_complete` 또는 review 대용 `kanban_block`을 호출하지 않는다.

## Fast Flow escalation

`Flow: FAST`에서 다음 증거를 발견하면 파일을 수정하기 전에 Block한다.

```text
FAST_FLOW_ESCALATION_REQUIRED
- Evidence: <실제 source/config/test에서 확인한 사실>
- Why Fast Flow is no longer safe: <설계/범위/호환성 이유>
- Standard Flow decision needed: <Orchestrator가 확인해야 할 항목>
```

이미 최소 변경을 시작한 뒤 escalation 조건이 드러난 경우에는 추가 변경을 멈추고 현재 변경 상태를 Block summary에 정확히 남긴다. 기존 사용자 변경을 reset/restore/clean/stash하지 않는다.

## 불변식
- 할당 Workspace 밖 수정, branch 전환, 다른 worktree 생성, unrelated refactor/format/upgrade/API-schema 변경 금지.
- secret/raw credential을 source, log, Kanban summary/metadata에 기록 금지.
- commit, push, PR, merge, rebase, cherry-pick, reset, clean, stash, cleanup 금지.
- 필수 검증 불가 또는 plan과 실제 evidence의 설계 충돌은 추측하지 말고 BLOCKED.
- Fast Flow가 실제 evidence상 단순하지 않으면 속도를 위해 scope를 확장하지 않고 Standard Flow escalation을 우선한다.
- CHANGES_REQUESTED는 종료가 아니라 original coder에게 돌아온 retry다. 동일 Workspace에서 blocking finding만 수정하고 다시 `kanban_request_review`한다.

정확성 checklist, retry, handoff metadata와 BLOCKED 형식이 필요하면 `references/implementation-details.md`를 먼저 읽는다.
