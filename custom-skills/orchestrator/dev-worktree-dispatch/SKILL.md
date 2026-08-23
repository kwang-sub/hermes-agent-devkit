---
name: dev-worktree-dispatch
description: Legacy linked-worktree Dispatch 마이그레이션에만 사용한다.
version: 0.4.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, worktree, kanban, dispatch, orchestrator, legacy, deprecated]
    related_skills: [dev-workspace-dispatch, dev-project-bootstrap, dev-breakdown]
    requires_tools: [terminal, kanban_create, kanban_show]
---

# dev-worktree-dispatch

> **DEPRECATED / LEGACY ONLY**
>
> 신규 Dispatch에는 `dev-workspace-dispatch`를 사용한다. 이 Skill은 기존 linked external worktree Workflow의 마이그레이션 또는 호환성 유지가 명시적으로 필요한 경우에만 사용한다.

기존 linked-worktree 방식으로 구현 준비가 끝난 계획을 프로젝트에 설정된 `coder` 프로필로 전달한다.

이 Skill은 **orchestrator 전용**이다.

프로젝트 설정은 다음 파일에서 자동으로 읽는다.

```text
<repo>/.hermes/project.yaml
```

따라서 일반적으로 호출자는 다음 값을 다시 입력할 필요가 없다.

- Repository
- Kanban Board
- Base Branch
- Worktree Root
- Coder Profile
- Reviewer Profile

표준 흐름:

```text
dev-project-bootstrap
        ↓
dev-breakdown
        ↓
사용자 Plan 승인
        ↓
dev-worktree-dispatch
        ↓
Kanban
        ↓
coder
```

Dispatch가 끝난 뒤 orchestrator는 구현을 직접 수행하지 않는다.

---

# 1. 사용 시점

신규 작업에는 사용하지 않는다. 기존 linked-worktree Workflow를 마이그레이션하거나 재현해야 하고 다음 조건을 모두 만족할 때만 사용한다.

- `dev-breakdown`이 구현 계획을 생성했다.
- 계획의 `Dispatch Readiness`가 `READY`다.
- **사용자가 현재 계획을 명시적으로 승인했다.**
- 현재 작업 디렉터리가 대상 Git Repository 내부다.
- 프로젝트가 `dev-project-bootstrap`으로 이미 관리되고 있다.
- 실제 구현을 프로젝트에 설정된 coder에게 위임해야 한다.

다음 경우에는 사용하지 않는다.

- Breakdown 결과가 `BLOCKED`다.
- 사용자가 아직 Implementation Plan을 승인하지 않았다.
- 대상 Repository를 결정할 수 없다.
- `.hermes/project.yaml`이 없거나 일관되지 않는다.
- 조사만 필요한 작업이다.
- orchestrator가 직접 코드를 구현하려 한다.
- 파괴적인 Git 작업이 필요하다.

`READY`는 기술적으로 Dispatch 가능한 상태라는 뜻이며, 사용자 승인과 동일하지 않다.

---

# 2. 필수 입력

일반적으로 작업별로 필요한 값은 다음뿐이다.

- `task_key`
  - Jira/Issue Key가 있으면 그대로 사용한다. 예: `POBA-123`
  - Jira가 없다면 사용자가 승인한 안정적인 Task Key를 사용한다.
- `implementation_plan`
  - 가능하면 전체 `dev-breakdown` 결과를 전달한다.
  - 반드시 Dispatch 가능한 상태여야 한다.
- optional `branch`
  - 호환성 확인용 입력이다.
  - 입력하는 경우 반드시 `feature/<TASK-KEY>`와 정확히 같아야 한다.

Breakdown에는 다음 정보가 포함되어 있어야 한다.

- Suggested Kanban Title
- Goal
- Acceptance Criteria
- Implementation Tasks
- Test Plan
- Dependencies
- Known Risks
- Dispatch Readiness

`.hermes/project.yaml`에서 확인 가능한 Repository, Board, Base Branch, Worktree Root, Coder, Reviewer를 사용자에게 다시 묻지 않는다.

---

# 3. Dispatch Readiness 및 사용자 승인 Gate

Branch, Worktree, Kanban Task를 만들기 전에 계획을 검증한다.

## 진행 가능

계획이 명확하게 다음 상태여야 한다.

```text
Dispatch Readiness
- READY
```

또는 `dev-breakdown`의 동등한 `READY` 결과여야 한다.

또한 현재 대화 흐름에서 **사용자가 해당 계획을 승인한 사실이 확인되어야 한다.**

사용자 승인이 확인되지 않으면 Worktree를 만들지 말고 승인 단계로 돌아간다.

## BLOCKED

계획이 다음 상태이면 Dispatch하지 않는다.

```text
BLOCKED
```

또는 해결되지 않은 P0 blocker가 존재하는 경우도 동일하다.

보고 항목:

- blocker
- 필요한 결정/정보
- Worktree 미생성
- Kanban Task 미생성

## Readiness가 없는 수기 계획

`dev-breakdown` 결과가 아닌 수기 Implementation Plan이라면 최소 다음이 있는지 확인한다.

- Goal
- Acceptance Criteria
- 실행 가능한 Implementation Tasks
- Test Plan
- 해결되지 않은 correctness blocker가 없음
- 사용자 승인

확인할 수 없다면 추측하지 말고 `dev-breakdown`을 실행하거나 권장한다.

---

# 4. 프로젝트 메타데이터 확인 및 Worktree 준비

현재 Repository에서 다음 Helper를 실행한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<task_key>"
```

`--branch`는 이전 호출부 호환성 확인 용도로만 허용한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<task_key>" \
  --branch "feature/<task_key>"
```

다른 Branch를 입력하면 Helper는 실패해야 한다.

Helper 동작:

1. 현재 Git Repository Root를 확인한다.
2. `<repo>/.hermes/project.yaml`을 읽는다.
3. 메타데이터의 Repository가 현재 Repository와 일치하는지 검증한다.
4. 다음 값을 읽는다.
   - Project ID
   - Kanban Board
   - Default Base Branch
   - Worktree Root
   - Coder Profile
   - Reviewer Profile
5. Git `2.48+`인지 검증한다.
6. `feature/<TASK-KEY>` Branch로 외부 Worktree를 생성하거나 안전하게 재사용한다.
7. 상대 경로 Worktree 메타데이터를 검증한다.
8. Machine-readable Dispatch 값을 출력한다.

예상 출력:

```text
PROJECT_ID=dashboard
REPO_ROOT=/workspace/dashboard
BOARD=dashboard
BASE_BRANCH=dev
WORKTREE_ROOT=/workspace/.worktrees/dashboard
WORKTREE_PATH=/workspace/.worktrees/dashboard/POBA-123
WORKSPACE=dir:/workspace/.worktrees/dashboard/POBA-123
ASSIGNEE=coder
REVIEWER=reviewer
TASK_KEY=POBA-123
BRANCH=feature/POBA-123
REUSED=false
STATUS=prepared
```

Helper가 non-zero로 종료되면 더 진행하지 않는다.

---

# 5. Worktree 규칙

표준 외부 경로:

```text
/workspace/.worktrees/<repo>/<task-key>
```

예:

```text
/workspace/.worktrees/dashboard/POBA-123
```

`/workspace`가 Windows의 `D:\workspace`와 bind mount되어 있다면 Host 경로 예:

```text
D:\workspace\.worktrees\dashboard\POBA-123
```

Branch 규칙:

```text
feature/<TASK-KEY>
```

예:

```text
feature/POBA-123
feature/CALC-001
```

Task 제목이나 설명 slug를 Branch에 붙이지 않는다.

규칙:

- Git은 `2.48+`이어야 한다.
- 신규 Worktree는 다음 방식을 사용한다.

```text
git worktree add --relative-paths
```

- Docker/Windows 공유 Worktree에 Linux 절대경로 `gitdir:` 링크를 만들지 않는다.
- Agent Worktree를 Source Repository 내부에 만들지 않는다.
- Source Checkout을 수정/reset/clean하지 않는다.
- 관계없는 기존 Local Branch를 조용히 재사용하지 않는다.
- 기존 Target은 동일 Source Repository에 속하고, 예상 Branch의 올바른 linked Worktree일 때만 재사용한다.
- Worktree 준비 후 Kanban 생성이 실패해도 준비된 Worktree를 삭제하지 않는다.

---

# 6. Kanban Task 생성

`kanban_create`를 사용한다.

Helper 반환값을 그대로 사용한다.

- board = `BOARD`
- assignee = `ASSIGNEE`
- workspace = 정확한 `WORKSPACE`
- title = Breakdown의 `Suggested Kanban Title`
- body = Implementation Plan + Workspace Rules

다음 Workspace 형식은 사용하지 않는다.

```text
workspace=worktree
workspace=worktree:<path>
```

Worktree는 이미 생성되어 있으므로 Kanban에는 다음처럼 전달한다.

```text
dir:<worktree-path>
```

---

# 7. Kanban Body 계약

Implementation Plan을 충실하게 보존한다.

상세 Breakdown을 모호한 한 문장으로 축약하지 않는다.

Body에는 다음 내용이 포함되어야 한다.

```text
Task Key:
<task_key>

Goal:
<goal from breakdown>

Acceptance Criteria:
<acceptance criteria from breakdown>

Implementation Tasks:
<ordered P1/P2 implementation tasks>

Test Plan:
<automated/manual/regression plan>

Dependencies:
<dependencies or None>

Known Risks:
<risks or None>

Reviewer Profile:
<reviewer profile from project metadata>

Implementation Skill:
dev-implement-plan

Review Skill:
dev-code-review

Workspace Rules:
- 할당된 Kanban Workspace 내부에서만 작업한다.
- Source Checkout을 수정하지 않는다.
- 다른 Git Worktree를 만들지 않는다.
- Branch를 전환하지 않는다.
- 관계없는 기존 변경을 보존한다.
- 승인된 Plan만 구현한다.
- 관련 Test를 실행하고 정확한 Command/Result를 보고한다.
- Workflow가 명시적으로 요청하지 않으면 Push하지 않는다.
- Worktree를 삭제하거나 Cleanup하지 않는다.

Expected Branch:
feature/<TASK-KEY>

Base Branch:
<base_branch>
```

Coder에게 필요한 `Affected Areas` 또는 `Current-State Findings`가 Breakdown에 있다면 함께 보존한다.

Secret, Credential, 불필요한 대용량 Source Dump는 포함하지 않는다.

---

# 8. 저장된 Kanban Task 검증

`kanban_create`가 Task ID를 반환하면 `kanban_show`로 다시 검증한다.

확인 항목:

- 올바른 Board
- 올바른 Assignee
- Body에 Reviewer Profile 보존
- 올바른 Workspace
- 올바른 Title
- Implementation Plan 보존
- Task가 dispatchable / ready 상태
- Body의 `Expected Branch`가 `feature/<TASK-KEY>`

검증 실패 시:

- Worktree를 삭제하지 않는다.
- Task가 생성되었다면 Task ID를 보고한다.
- Worktree Path를 보고한다.
- 수정이 안전하고 명백한 경우에만 Kanban Task를 수정한다.

---

# 9. Handoff

검증 성공 후:

- orchestrator의 구현 활동을 종료한다.
- Kanban Dispatcher가 coder에게 Task를 claim하도록 둔다.
- Dispatch 결과를 보고한다.

권장 보고 형식:

```text
Task: t_xxxxxxxx
Project: dashboard
Board: dashboard
Assignee: coder
Reviewer: reviewer
Branch: feature/POBA-123
Base: dev
Workspace: /workspace/.worktrees/dashboard/POBA-123
Worktree reused: false
Status: ready
```

---

# 10. 중복 및 Retry 안전성

새 Task를 만들기 전에 사용 가능한 Kanban 조회 기능으로 동일 Task Key + Repository의 명백한 Active Task 중복을 피한다.

다음 이유만으로 두 번째 Coding Task를 만들지 않는다.

- Dispatcher가 아직 첫 Task를 claim하지 않았다.
- 첫 Task가 일시적으로 Blocked다.
- 첫 Worktree가 이미 존재한다.

동일 Worktree가 존재하면:

- Helper가 재사용 전 검증한다.
- Worktree 재사용 가능 여부와 새 Kanban Task 생성 여부는 동일한 의미가 아니다.

Worktree 준비 후 Task 생성이 실패하면:

```text
Worktree = KEEP
Branch = KEEP
Kanban task = retry/fix
```

Worktree를 자동 제거하지 않는다.

---

# 11. 안전 규칙

이 Skill이 생성할 수 있는 것은 다음뿐이다.

- `feature/<TASK-KEY>` Task Branch 1개
- Linked External Worktree 1개
- Kanban Task 1개

다음은 절대 하지 않는다.

- 구현 파일 수정
- Source Checkout의 사용자 변경 수정
- reset/restore/clean/stash
- commit
- push
- merge
- rebase
- force push
- Worktree 삭제
- Branch 삭제
- Board/Project 삭제 또는 archive
- `.hermes/project.yaml` 변경

프로젝트 설정 변경은 `dev-project-bootstrap`의 책임이다.

---

# 12. 성공 기준

다음을 모두 만족해야 성공이다.

- Plan Readiness = `READY`
- 현재 Plan에 대한 사용자 승인이 확인됨
- `.hermes/project.yaml`이 현재 Repository 기준으로 유효함
- Project/Board/Base/Coder/Reviewer를 사용자에게 반복 입력받지 않고 해석함
- Target Worktree가 Source Repository 외부에 존재함
- Branch가 정확히 `feature/<TASK-KEY>`임
- Linked Worktree 메타데이터가 상대 경로임
- Worktree가 예상 Source Repository 소속임
- Kanban Workspace가 `dir:<worktree-path>`임
- Kanban Task가 설정된 coder에 할당됨
- Implementation Plan과 Acceptance Criteria가 Task에 보존됨
- Reviewer 정보가 보존됨
- orchestrator가 코드를 구현하지 않음

---

# 13. 예상 Workflow

```text
Current repository
      ↓
.hermes/project.yaml
      │
      ├─ repository
      ├─ board
      ├─ base branch
      ├─ worktree root
      ├─ coder
      └─ reviewer
      ↓
dev-breakdown = READY
      ↓
사용자 Plan 승인
      ↓
dev-worktree-dispatch
      ↓
feature/<TASK-KEY>
      ↓
git worktree add --relative-paths
      ↓
/workspace/.worktrees/<repo>/<task-key>
      ↓
kanban_create(workspace=dir:<path>)
      ↓
kanban_show 검증
      ↓
coder
```
