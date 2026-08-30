---
name: dev-workflow-orchestrate
description: Jira/text 개발 요청의 project·plan·workspace 승인을 거쳐 coder/reviewer로 dispatch하는 orchestrator 전용 workflow.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, workflow, orchestrator, approval, breakdown, dispatch, kanban, preflight]
    related_skills: [dev-work-intake, dev-project-resolve, dev-project-bootstrap, dev-breakdown, dev-skill-preflight, dev-workspace-dispatch]
---

# dev-workflow-orchestrate

개발 요청의 상태 머신만 조정한다. Orchestrator는 application/test code, refactor, code review를 직접 하지 않고 commit, push, PR, merge, destructive cleanup도 하지 않는다.

## 상태 머신과 Gate
`START → WORK_ITEM_READY → PROJECT_APPROVED → dev-breakdown READY → PLAN_APPROVED → WORKSPACE_APPROVED → SKILL_PREFLIGHT → dev-workspace-dispatch → coder ↔ reviewer → DONE/BLOCKED`

1. Jira는 `dev-work-intake`, text는 원문 보존 Common Work Item으로 정규화한다.
2. 사용자가 정확한 managed project를 명시하지 않았다면 resolver 후보를 보여주고 **Project Approval Gate**에서 STOP한다. 단일 후보도 자동 승인하지 않는다.
3. managed metadata를 ensure한 뒤 `dev-breakdown`을 실행한다.
4. READY 계획을 한국어로 보여주고 **Plan Approval Gate**에서 STOP한다. READY 자체는 승인이 아니다.
5. 실제 status/branch/base와 dirty file을 보여주고 current/create branch 및 workspace를 선택받는 **Workspace / Branch Approval Gate**에서 STOP한다.
6. 승인된 뒤에만 `dev-workspace-dispatch`를 실행한다. Dispatch는 내부에서 `skill_view("dev-skill-preflight")`를 로드하고 Coder/Reviewer profile 기준으로 Applicable Skills를 검증한다. preflight 자체가 실패하면 Kanban Task를 만들지 않는다.
7. `kanban_create.skills`에는 preflight의 `VALIDATED_SKILLS` 전체만 전달한다. `REJECTED_SKILLS`는 body에 기록하되 pinned skill로 전달하지 않는다. 생성 직후 `kanban_show`로 실제 `task.skills`가 validated 목록과 정확히 같은지 확인한 뒤에만 dispatch한다.
8. dispatch 후 구현/review에 개입하지 않는다. reviewer가 human input으로 BLOCKED일 때만 사용자 결정을 연결한다.

## 불변식
- `.hermes/project.yaml`의 managed metadata만 사용하며 repo/Board/profile을 추측하지 않는다.
- Task Key와 branch는 helper 계약을 따르고 mismatch를 rename으로 우회하지 않는다.
- task에는 Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Dependencies, Risks와 workspace contract가 있어야 한다.
- `Applicable Skills`는 계획 후보이고 `task.skills`는 runtime pinned skill이다. 둘을 직접 동일시하지 않는다.
- 존재하지 않거나 일부 target profile에만 존재하는 skill은 `task.skills`에 넣지 않는다.
- skill 이름을 비슷한 이름으로 자동 보정하지 않는다.
- approval 없는 bootstrap/branch/worktree/Kanban 생성은 금지한다.
- publication과 automatic cleanup은 별도 workflow다.

입력 판별, Task Key, gate 출력, dispatch 검증, BLOCKED 조건의 세부 기준이 필요하면 `references/workflow-details.md`를 먼저 읽는다.
