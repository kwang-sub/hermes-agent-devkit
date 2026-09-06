---
name: dev-workflow-orchestrate
description: Jira/text 개발 요청의 project·plan·workspace 승인을 거쳐 coder/reviewer로 dispatch하는 orchestrator 전용 workflow.
version: 0.5.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, workflow, orchestrator, approval, breakdown, dispatch, kanban, preflight, performance]
    related_skills: [dev-work-intake, dev-project-resolve, dev-project-bootstrap, dev-breakdown, dev-skill-preflight, dev-workspace-dispatch]
---

# dev-workflow-orchestrate

개발 요청의 상태 머신만 조정한다. Orchestrator는 application/test code, refactor, code review를 직접 하지 않고 commit, push, PR, merge, destructive cleanup도 하지 않는다.

## 상태 머신

`START → WORK_ITEM_READY → PROJECT_APPROVED → dev-breakdown READY → PLAN_APPROVED → WORKSPACE_APPROVED → dev-workspace-dispatch → SKILL_PREFLIGHT → KANBAN_CREATED → coder ↔ reviewer → DONE/BLOCKED`

1. 요구사항을 Common Work Item으로 정규화한다.
2. managed project를 확정하고 Project Approval Gate를 통과한다.
3. `dev-breakdown`으로 READY 계획을 만들고 사용자에게 한국어 Implementation Plan을 제시한다.
4. Plan Approval Gate를 통과한다.
5. Workspace / Branch Approval Gate에서 workspace, current/create branch, 기존 변경 전체 보존 여부를 승인받는다.
6. `dev-workspace-dispatch`를 실행해 승인 workspace/branch와 Base SHA를 확정한다.
7. Skill preflight 후 `kanban_create` / `kanban_show`로 Task를 생성·검증한다.
8. 이후 Coder/Reviewer 흐름에 맡긴다.

## Workspace 상태 검사 단일화 계약

Workspace Approval 전에 **working-tree 전체 scan을 하지 않는다**. 허용되는 것은 repository/workspace/current branch/base branch 같은 identity 조회뿐이다.

금지:

```text
git status
git diff --name-only
git diff --ignore-cr-at-eol
git ls-files --others
inline Python tracked/effective/EOL 분류
```

사용자에게는 exact dirty count가 아니라 다음을 확인한다.

```text
- 사용할 workspace
- current/create branch 전략
- 기존 변경이 존재하면 reset/restore/stash하지 않고 모두 보존한 채 진행할지
```

### Existing changes preservation fast path

사용자가 기존 변경 전체 보존을 승인하면 반드시:

```text
prepare_dispatch.py --confirmed-dirty
```

를 사용한다. 이 경우 `prepare_dispatch.py`는 repository-wide dirty/EOL/untracked 분류를 **생략**하며 다음이 정상이다.

```text
WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation
WORKSPACE_DIRTY=unknown
WORKSPACE_EFFECTIVE_DIRTY=unknown
EFFECTIVE_CHANGED_COUNT=-1
EOL_ONLY_COUNT=-1
HERMES_MANAGED_COUNT=-1
```

이 값을 얻은 뒤 exact count를 복구하려고 `git status`, `git diff`, `git ls-files`, 별도 helper를 실행하지 않는다. Task body에는 count 대신 `Existing changes preservation approved=true`와 scan mode를 보존한다.

기존 변경 보존 승인이 없는 경우에만 helper의 full classification 결과를 사용자에게 보여주고 승인 후 다시 fast path로 진입할 수 있다.

**정상 dispatch에서 `prepare_dispatch.py`는 정확히 한 번 실행한다.**

## Kanban 생성 단일 경로 계약

```text
prepare_dispatch PASS
→ dev-skill-preflight PASS
→ kanban_create tool 1회
→ kanban_show tool 1회
→ notification subscribe helper 1회
→ worker dispatch
```

Task body는 tool 인자로 직접 전달한다. 다음 capability probing/fallback은 금지한다.

```text
hermes kanban ... create --help
hermes project list
hermes project --help
Kanban body 임시 파일
CLI body-file capability probing
```

Board는 `.hermes/project.yaml`의 managed board를 명시적으로 사용하며 세션 default에 의존하지 않는다.

## Coder / Reviewer 대형 Workspace 계약

Dispatch에서 exact 기존 변경 목록을 생략했더라도 Coder/Reviewer는 전체 저장소를 다시 스캔하지 않는다.

```text
Coder
→ 실제 구현 Changed Files 확정
→ change_summary.py --include <changed-path>...

Reviewer
→ Coder Changed Files 재사용
→ review_context.py --include <changed-path>...
```

정상 Standard Flow에서 scope 없는 `change_summary.py` / `review_context.py` 호출은 금지한다. 전체 scan은 명시적 diagnostic mode에서만 허용한다.

## 불변식

- `.hermes/project.yaml`의 managed metadata만 사용하며 repo/Board/profile을 추측하지 않는다.
- Task Key, branch, Base SHA는 helper 계약을 따르고 임의 재해석하지 않는다.
- `Applicable Skills`와 runtime pinned `task.skills`를 동일시하지 않는다.
- approval 없는 bootstrap/branch/worktree/Kanban 생성 금지.
- Orchestrator는 commit, push, PR, merge를 수행하지 않는다.
- 원격 저장소에 직접 기록하는 제목/설명/commit 메시지는 사용자 정책에 따라 한국어를 기본으로 한다.
- publication과 cleanup은 별도 workflow다.

세부 성능 규칙은 `references/dispatch-efficiency.md`를 따른다.
