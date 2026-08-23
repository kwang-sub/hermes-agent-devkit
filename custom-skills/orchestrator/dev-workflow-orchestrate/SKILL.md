---
name: dev-workflow-orchestrate
description: Jira/text 개발 요청의 project·plan·workspace 승인을 거쳐 coder/reviewer로 dispatch하는 orchestrator 전용 workflow.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, workflow, orchestrator, approval, breakdown, dispatch, kanban]
    related_skills: [dev-work-intake, dev-project-resolve, dev-project-bootstrap, dev-breakdown, dev-workspace-dispatch]
---

# dev-workflow-orchestrate

개발 요청의 상태 머신만 조정한다. Orchestrator는 application/test code, refactor, code review를 직접 하지 않고 commit, push, PR, merge, destructive cleanup도 하지 않는다.

## 상태 머신과 Gate
`START → WORK_ITEM_READY → PROJECT_APPROVED → dev-breakdown READY → PLAN_APPROVED → WORKSPACE_APPROVED → dev-workspace-dispatch → coder ↔ reviewer → DONE/BLOCKED`

1. Jira는 `dev-work-intake`, text는 원문 보존 Common Work Item으로 정규화한다.
2. 사용자가 정확한 managed project를 명시하지 않았다면 resolver 후보를 보여주고 **Project Approval Gate**에서 STOP한다. 단일 후보도 자동 승인하지 않는다.
3. managed metadata를 ensure한 뒤 `dev-breakdown`을 실행한다.
4. READY 계획을 한국어로 보여주고 **Plan Approval Gate**에서 STOP한다. READY 자체는 승인이 아니다.
5. 실제 status/branch/base와 dirty file을 보여주고 current/create branch 및 workspace를 선택받는 **Workspace / Branch Approval Gate**에서 STOP한다.
6. 승인된 뒤에만 `dev-workspace-dispatch`를 실행하고 Project, Board, coder, reviewer, ready, Workspace, Expected Branch, Base Branch, Base SHA를 검증한다.
7. dispatch 후 구현/review에 개입하지 않는다. reviewer가 human input으로 BLOCKED일 때만 사용자 결정을 연결한다.

## 불변식
- `.hermes/project.yaml`의 managed metadata만 사용하며 repo/Board/profile을 추측하지 않는다.
- Task Key와 branch는 helper 계약을 따르고 mismatch를 rename으로 우회하지 않는다.
- task에는 Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Dependencies, Risks와 workspace contract가 있어야 한다.
- approval 없는 bootstrap/branch/worktree/Kanban 생성은 금지한다.
- publication과 automatic cleanup은 별도 workflow다.

입력 판별, Task Key, gate 출력, dispatch 검증, BLOCKED 조건의 세부 기준이 필요하면 `references/workflow-details.md`를 먼저 읽는다.
