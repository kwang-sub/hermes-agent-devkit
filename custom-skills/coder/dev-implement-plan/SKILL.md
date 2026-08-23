---
name: dev-implement-plan
description: 승인 계획을 할당 Workspace에서 최소 구현·검증하고 commit/push 없이 reviewer에게 인계한다.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review]
    related_skills: [dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_block, kanban_heartbeat]
---

# dev-implement-plan

## 실행 계약
1. 먼저 `kanban_show()`로 body, attempts, comments, feedback을 읽는다.
2. `$HERMES_KANBAN_WORKSPACE`에서 `scripts/verify_workspace.py --base-sha <Base SHA>`로 Task Key, approved Workspace/Git root, Expected Branch, dispatch Base SHA resolve 및 HEAD ancestor 관계를 검증한다. mismatch면 수정 전에 BLOCKED다.
3. Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Risks, Expected/Base Branch, Reviewer Profile이 있는지 확인한다.
4. 실제 source/flow/config/tests/pattern을 확인하고 승인 scope를 만족하는 최소 변경만 구현한다. reviewer 재작업이면 blocking finding만 처리한다.
5. targeted verification부터 실행하고 `git diff --check` 및 `scripts/change_summary.py`로 tracked/untracked/status를 수집한다.
6. 정확한 command/result와 검증된 `BASE_SHA`, residual risk를 기록하고 configured `reviewer`에게 `kanban_request_review`만 호출한 뒤 멈춘다. 구현 완료 상태에서 `kanban_complete` 또는 review 대용 `kanban_block`을 호출하지 않는다.

## 불변식
- 할당 Workspace 밖 수정, branch 전환, 다른 worktree 생성, unrelated refactor/format/upgrade/API-schema 변경 금지.
- secret/raw credential을 source, log, Kanban summary/metadata에 기록 금지.
- commit, push, PR, merge, rebase, cherry-pick, reset, clean, stash, cleanup 금지.
- 필수 검증 불가 또는 plan과 실제 evidence의 설계 충돌은 추측하지 말고 BLOCKED.
- CHANGES_REQUESTED는 종료가 아니라 original coder에게 돌아온 retry다. 동일 Workspace에서 blocking finding만 수정하고 다시 `kanban_request_review`한다.

정확성 checklist, retry, handoff metadata와 BLOCKED 형식이 필요하면 `references/implementation-details.md`를 먼저 읽는다.
