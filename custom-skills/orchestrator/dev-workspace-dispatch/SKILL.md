---
name: dev-workspace-dispatch
description: 승인된 구현 계획을 Git workspace와 Kanban으로 인계한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, workspace, branch, kanban, dispatch, orchestrator]
    related_skills: [dev-project-bootstrap, dev-breakdown, dev-workflow-orchestrate]
    requires_tools: [terminal, kanban_create, kanban_show, clarify]
---

# dev-workspace-dispatch

사용자 승인까지 완료된 READY 구현 계획을 사용자가 승인한 Git workspace와 branch 전략에 맞춰 Kanban 작업으로 인계한다.

이 Skill이 신규 Dispatch의 표준이다. deprecated `dev-worktree-dispatch`와 달리 기본 동작으로 git worktree add를 실행하지 않는다. 작업 위치와 branch 전략은 사람에게 보여주고 승인받은 뒤 사용한다.

## 1. 사용 시점

다음 조건을 모두 만족할 때 사용한다.

- dev-breakdown이 구현 계획을 생성했다.
- 계획의 Dispatch Readiness가 READY다.
- 사용자가 현재 Implementation Plan을 명시적으로 승인했다.
- 사용자가 Git Workspace / Branch 방식을 명시적으로 승인했다.
- 대상 Repository가 dev-project-bootstrap으로 관리되고 있다.
- 구현을 프로젝트 metadata의 profiles.coder에게 인계해야 한다.

사용하지 않을 경우:

- Plan이 BLOCKED다.
- Plan 승인 또는 Workspace/Branch 승인이 없다.
- workspace가 Git repository root가 아니다.
- workspace가 project metadata의 repository와 같은 Git common dir에 속하지 않는다.
- workspace에 기존 변경이 있는데 사용자가 그 상태를 승인하지 않았다.

## 2. 승인 Gate

이 Skill은 Plan Approval과 Git Workspace / Branch Approval이 모두 끝난 뒤에만 실행한다.

Workspace / Branch Approval에서 사용자에게 보여줄 최소 항목:

```text
Project:
Repository:
Approved workspace:
Current branch:
Git status: clean / dirty
Base branch:
Suggested new branch: feature/<TASK-KEY>
```

사용자 선택지는 다음이다.

```text
1. 현재 workspace + 현재 branch 사용
2. 현재 workspace + 새 branch 생성
3. 사용자가 지정한 별도 workspace + 현재 branch 사용
4. 사용자가 지정한 별도 workspace + 새 branch 생성
```

기존 변경이 있으면 git status --short --untracked-files=all 결과를 요약하고, 사용자가 해당 dirty 상태를 작업에 포함해도 된다고 승인해야 한다.

## 3. Helper 실행

현재 branch를 그대로 사용할 때:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<TASK-KEY>" \
  --workspace "<APPROVED_WORKSPACE>" \
  --branch-mode current
```

새 branch를 만들 때:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<TASK-KEY>" \
  --workspace "<APPROVED_WORKSPACE>" \
  --branch-mode create \
  --branch "feature/<TASK-KEY>"
```

workspace에 기존 변경이 있고 사용자가 이를 승인한 경우에만 --confirmed-dirty를 추가한다.

Helper 검증 항목:

1. Task Key가 안전한지 확인한다.
2. Workspace가 Git repository root인지 확인한다.
3. .hermes/project.yaml이 managed metadata인지 확인한다.
4. Metadata repository와 실제 repository가 일치하는지 확인한다.
5. Approved workspace가 managed repository와 같은 Git common dir인지 확인한다.
6. Base branch/ref와 base SHA를 확정한다.
7. 현재 branch 또는 새 branch 생성 결과를 검증한다.

예상 출력:

```text
PROJECT_ID=dashboard
REPO_ROOT=/workspace/dashboard
BOARD=dashboard
BASE_BRANCH=dev
BASE_SHA=<sha>
WORKSPACE_PATH=/workspace/dashboard
WORKSPACE=dir:/workspace/dashboard
ASSIGNEE=coder
REVIEWER=reviewer
TASK_KEY=CALC-001
BRANCH_MODE=create
BRANCH=feature/CALC-001
PREVIOUS_BRANCH=dev
CREATED_BRANCH=true
WORKSPACE_DIRTY=false
STATUS=prepared
```

Helper가 non-zero로 종료되면 Kanban Task를 만들지 않는다.

## 4. Kanban Body 계약

Body에는 최소 다음을 포함한다.

```text
Task Key:
Goal:
Acceptance Criteria:
Implementation Tasks:
Test Plan:
Dependencies:
Known Risks:
Reviewer Profile:
Implementation Skill: dev-implement-plan
Review Skill: dev-code-review
Workspace Contract:
- Workspace: <WORKSPACE_PATH>
- Branch mode: current | create
- Expected branch: <BRANCH>
- Base branch: <BASE_BRANCH>
- Base SHA: <BASE_SHA>
- Workspace dirty at dispatch: true | false
- 기존 변경이 있었다면 사용자가 해당 상태를 승인했다.
- Coder는 할당된 Workspace 밖을 수정하지 않는다.
- Coder는 Branch를 전환하지 않는다.
- Coder는 다른 Git Worktree를 만들지 않는다.
```

## 5. 성공 기준

- Plan Readiness = READY
- Plan 승인 확인됨
- Workspace/Branch 승인 확인됨
- Approved workspace가 Git repository root임
- Approved workspace가 managed repository와 같은 Git common dir에 속함
- Expected Branch가 실제 현재 branch와 일치함
- Base SHA가 기록됨
- Kanban Workspace가 dir:<approved-workspace>임
- Implementation Plan, Acceptance Criteria, Workspace Contract, Reviewer 정보가 보존됨

## 6. 회귀 검증

Helper의 current/create branch mode, dirty workspace gate, unsafe task key 검증은 다음 명령으로 실행한다.

```bash
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
```

관련 orchestrator 회귀 검증 전체:

```bash
python3 -m compileall -q custom-skills
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-project-bootstrap/tests/test_metadata_preservation.py
python3 custom-skills/orchestrator/dev-project-resolve/tests/test_project_resolve.py
```
