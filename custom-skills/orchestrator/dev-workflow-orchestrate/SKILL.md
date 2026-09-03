---
name: dev-workflow-orchestrate
description: Jira/text 개발 요청의 project·plan·workspace 승인을 거쳐 coder/reviewer로 dispatch하는 orchestrator 전용 workflow.
version: 0.4.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, workflow, orchestrator, approval, breakdown, dispatch, kanban, preflight, performance]
    related_skills: [dev-work-intake, dev-project-resolve, dev-project-bootstrap, dev-breakdown, dev-skill-preflight, dev-workspace-dispatch]
---

# dev-workflow-orchestrate

개발 요청의 상태 머신만 조정한다. Orchestrator는 application/test code, refactor, code review를 직접 하지 않고 commit, push, PR, merge, destructive cleanup도 하지 않는다.

## 상태 머신과 Gate

`START → WORK_ITEM_READY → PROJECT_APPROVED → dev-breakdown READY → PLAN_APPROVED → WORKSPACE_APPROVED → dev-workspace-dispatch → SKILL_PREFLIGHT → KANBAN_CREATED → coder ↔ reviewer → DONE/BLOCKED`

1. Jira는 `dev-work-intake`, text는 원문 보존 Common Work Item으로 정규화한다.
2. 사용자가 정확한 managed project를 명시하지 않았다면 resolver 후보를 보여주고 **Project Approval Gate**에서 STOP한다. 단일 후보도 자동 승인하지 않는다.
3. managed metadata를 ensure한 뒤 `dev-breakdown`을 실행한다.
4. READY 계획을 한국어로 보여주고 **Plan Approval Gate**에서 STOP한다. READY 자체는 승인이 아니다.
5. Plan 승인 뒤 **Workspace / Branch Approval Gate**에서는 working-tree 전체 scan을 하지 않는다. repository/workspace/current branch/base branch처럼 가벼운 identity 정보만 사용하고, 사용자가 `현재/새 branch`와 `기존 변경이 있으면 그대로 보존할지`를 선택하게 한다.
6. Workspace/Branch 승인이 끝난 뒤 `dev-workspace-dispatch`를 실행한다. 이 단계의 `prepare_dispatch.py`가 working-tree 상태를 최초이자 표준 방식으로 분류한다.
7. Dispatch 내부에서 `skill_view("dev-skill-preflight")`를 로드하고 Coder/Reviewer profile 기준으로 Applicable Skills를 검증한다. preflight 실패 시 Kanban Task를 만들지 않는다.
8. Kanban Task는 `kanban_create` tool로 직접 만들고 즉시 `kanban_show` tool로 검증한다. CLI 사용법 탐색이나 임시 body file 생성은 하지 않는다.
9. dispatch 후 구현/review에 개입하지 않는다. reviewer가 human input으로 BLOCKED일 때만 사용자 결정을 연결한다.

## Workspace 상태 검사 단일화 계약

Workspace Approval 전에 허용되는 Git 조회는 **working tree를 훑지 않는 identity 조회**뿐이다.

허용 예:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
```

Workspace Approval 전에 다음 working-tree scan을 실행하지 않는다.

```text
git status
git diff --name-only
git diff --ignore-cr-at-eol
git ls-files --others
별도 Python subprocess를 이용한 tracked/effective/EOL 분류
collect_project_context 결과를 dirty 상태 계산에 재사용하는 추가 Git scan
```

사용자에게는 exact dirty count를 얻기 위한 선행 scan 대신 다음을 확인한다.

```text
- 사용할 workspace
- current/create branch 전략
- 기존 변경이 존재하면 reset/restore/stash하지 않고 모두 보존한 채 작업해도 되는지
```

사용자가 기존 변경 보존을 승인했다면 `dev-workspace-dispatch`는 `prepare_dispatch.py --confirmed-dirty`를 사용한다. Helper가 반환한 정확한 `EFFECTIVE_CHANGED_COUNT`, `EOL_ONLY_COUNT`, `HERMES_MANAGED_COUNT`는 Task body와 dispatch 결과에 기록한다.

**정상 dispatch 한 번에서 working-tree 상태 분류는 `prepare_dispatch.py` 정확히 한 번만 수행한다.** Helper 실행 전후로 동일 상태를 확인하기 위한 `git status`, `git diff`, inline Python 분류를 추가하지 않는다.

Helper가 예상치 못한 effective change 때문에 승인 조건과 충돌해 실패한 경우에만 사용자에게 결과를 보여주고 새로운 승인 시도를 시작할 수 있다. 이 예외는 정상 경로의 사전 중복 scan을 허용하는 근거가 아니다.

## Kanban 생성 단일 경로 계약

Workspace helper와 Skill Preflight가 성공하면 다음 경로만 사용한다.

```text
prepare_dispatch PASS
→ dev-skill-preflight PASS
→ kanban_create tool 1회
→ kanban_show tool 1회
→ notification subscribe helper 1회
→ worker dispatch
```

Task body는 `kanban_create`의 body 인자로 직접 전달한다. 다음 capability probing/fallback은 금지한다.

```text
hermes kanban ... create --help
hermes project list
hermes project --help
/tmp 또는 workspace에 Kanban body 임시 파일 생성
CLI body-file 지원 여부 탐색
kanban_create tool 사용 가능 여부를 확인하기 위한 별도 CLI probe
```

`kanban_show`는 생성된 Task의 workspace, assignee/reviewer, status, `task.skills == VALIDATED_SKILLS`를 검증하는 용도로 정확히 한 번 사용한다. 검증 실패 시 다른 생성 경로를 탐색하지 말고 BLOCK한다.

## 불변식

- `.hermes/project.yaml`의 managed metadata만 사용하며 repo/Board/profile을 추측하지 않는다.
- Task Key와 branch는 helper 계약을 따르고 mismatch를 rename으로 우회하지 않는다.
- Task에는 Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Dependencies, Risks, workspace contract와 Base SHA가 있어야 한다.
- `Applicable Skills`는 계획 후보이고 `task.skills`는 runtime pinned skill이다. 둘을 직접 동일시하지 않는다.
- 존재하지 않거나 일부 target profile에만 존재하는 skill은 `task.skills`에 넣지 않는다.
- skill 이름을 비슷한 이름으로 자동 보정하지 않는다.
- approval 없는 bootstrap/branch/worktree/Kanban 생성은 금지한다.
- publication과 automatic cleanup은 별도 workflow다.

입력 판별/Task Key/일반 Gate 세부 기준은 `references/workflow-details.md`를 참고한다. **Workspace 상태 검사와 Kanban 생성 방식은 오래된 reference보다 이 문서의 단일 경로 계약이 항상 우선한다.** Workspace/dispatch 성능 규칙만 필요하면 `references/dispatch-efficiency.md`를 먼저 읽는다.
