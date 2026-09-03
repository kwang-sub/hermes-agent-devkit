---
name: dev-workspace-dispatch
description: 승인된 구현 계획과 project pattern/capability 계약을 Git workspace와 Kanban으로 인계한다.
version: 0.8.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, workspace, branch, kanban, dispatch, orchestrator, capability, preflight, notification, performance]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-breakdown, dev-skill-preflight, dev-workflow-orchestrate]
    requires_tools: [terminal, skill_view, kanban_create, kanban_show, clarify]
---

# dev-workspace-dispatch

사용자 승인까지 완료된 READY 구현 계획을 승인된 Git workspace와 branch 전략에 맞춰 Kanban 작업으로 인계한다.

이 Skill이 신규 Dispatch의 표준이다. deprecated worktree dispatch 경로를 사용하지 않는다.

## 1. 진입 조건

다음이 모두 충족되어야 한다.

- dev-breakdown 결과가 READY다.
- 사용자가 Implementation Plan을 승인했다.
- 사용자가 workspace와 current/create branch 전략을 승인했다.
- 현재 workspace에 기존 변경이 있을 경우 이를 reset/restore/stash하지 않고 보존한 채 작업해도 된다는 승인을 받았다.
- 대상 repository가 dev-project-bootstrap managed metadata를 가진다.

Plan/Workspace 승인이 없거나 project pattern/capability handoff가 누락되면 STOP한다.

## 2. Working-tree 상태 검사 단일화

**정상 Standard Flow에서 working-tree 전체 상태 분류는 `prepare_dispatch.py`가 정확히 한 번만 수행한다.**

이 helper 실행 전에 exact dirty count를 얻기 위한 다음 작업을 하지 않는다.

```text
git status
git diff --name-only
git diff --ignore-cr-at-eol
git ls-files --others
inline Python/subprocess로 tracked/effective/EOL/untracked 재분류
```

승인 전에는 repository/workspace/current branch/base branch 같은 identity만 확인한다. 사용자에게는 다음을 선택받는다.

```text
1. 현재 workspace + 현재 branch 사용
2. 현재 workspace + 새 branch 생성
3. 지정 workspace + 현재 branch 사용
4. 지정 workspace + 새 branch 생성

기존 변경이 존재할 경우 모든 기존 변경을 보존한 채 진행할지 승인
```

기존 변경 보존 승인을 받았으면 helper에 `--confirmed-dirty`를 전달한다. 정확한 변경 개수와 path는 helper 실행 후 처음 확정한다.

## 3. Helper 실행

현재 branch:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<TASK-KEY>" \
  --workspace "<APPROVED_WORKSPACE>" \
  --branch-mode current \
  [--confirmed-dirty]
```

새 branch:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<TASK-KEY>" \
  --workspace "<APPROVED_WORKSPACE>" \
  --branch-mode create \
  --branch "feature/<TASK-KEY>" \
  [--confirmed-dirty]
```

Helper는 다음을 한 번에 수행한다.

- Task Key 안전성
- repository root/common Git dir/managed metadata 검증
- Base branch와 Base SHA 확정
- managed `kanban.board` 확정
- current/create branch 계약 검증
- tracked/untracked를 effective/EOL-only/Hermes managed로 분류

변경 분류는 다음 batch scan 3회 + Python set 연산으로만 수행한다.

```text
git diff --name-only -z HEAD
git diff --name-only -z --ignore-cr-at-eol HEAD
git ls-files -z --others --exclude-standard
```

파일별 `git diff --quiet` 반복 호출은 금지한다.

Helper의 결과가 dispatch working-tree evidence의 단일 기준이다.

```text
BOARD
EFFECTIVE_CHANGED_COUNT
EOL_ONLY_COUNT
HERMES_MANAGED_COUNT
GIT_TRACKED_SCAN_SECONDS
GIT_EFFECTIVE_SCAN_SECONDS
GIT_UNTRACKED_SCAN_SECONDS
CLASSIFICATION_SECONDS
WORKSPACE_CLASSIFICATION_TOTAL_SECONDS
```

`BOARD`는 `<repo>/.hermes/project.yaml`의 `kanban.board`에서 나온 값이며 Standard Flow의 유일한 Kanban board source다. `HERMES_KANBAN_BOARD`, 현재 세션의 이전 보드, CLI default board를 fallback으로 사용하지 않는다.

Helper 실행 후 동일 상태를 다시 확인하려고 `git status`, `git diff`, inline Python 분류를 추가하지 않는다.

Helper가 non-zero면 Kanban Task를 만들지 않는다. 예상하지 못한 effective change 때문에 사용자 승인과 충돌한 경우에만 helper 결과를 보여주고 새 승인 턴을 시작한다.

## 4. Skill Preflight Gate

Helper 성공 후 `skill_view("dev-skill-preflight")`를 로드한다.

```bash
python3 /opt/custom-skills/orchestrator/dev-skill-preflight/scripts/validate_skills.py \
  --profile "<ASSIGNEE>" \
  --profile "<REVIEWER>" \
  --skill "<APPLICABLE_SKILL_1>" \
  --skill "<APPLICABLE_SKILL_2>"
```

- `VALIDATED_SKILLS` 전체만 `kanban_create.skills`에 전달한다.
- `REJECTED_SKILLS`는 body에 기록하고 pin하지 않는다.
- preflight non-zero면 Kanban Task를 만들지 않는다.

## 5. Kanban 생성 단일 경로

Preflight 성공 후 다음 순서만 허용한다.

```text
kanban_create(board=BOARD, ...) tool 정확히 1회
→ kanban_show(board=BOARD, task_id=<CREATED_TASK_ID>) tool 정확히 1회
→ subscribe_notification.py 정확히 1회
→ worker dispatch
```

`BOARD`는 반드시 같은 dispatch에서 `prepare_dispatch.py`가 반환한 값을 그대로 사용한다. `kanban_create` 또는 `kanban_show`에서 board 인자를 생략하지 않는다.

Task body는 `kanban_create` tool의 body 인자로 직접 전달한다.

다음 capability probing/fallback은 금지한다.

```text
board 인자를 생략한 kanban_create / kanban_show
HERMES_KANBAN_BOARD 환경변수를 project board 대신 사용
hermes kanban --board <board> create --help
hermes project list
hermes project --help
/tmp 또는 workspace에 Kanban body 임시 파일 생성
CLI body-file 지원 여부 탐색
CLI로 동일 Task create 재시도
kanban_create tool 사용 가능 여부를 확인하기 위한 CLI probe
```

`kanban_create` tool이 실패하면 CLI fallback을 탐색하지 않고 BLOCK한다.

`kanban_show`는 **동일한 `BOARD`를 명시해** 생성된 Task의 다음 항목을 검증한다.

```text
board == BOARD
status
workspace == dir:<APPROVED_WORKSPACE>
assignee == metadata profiles.coder
reviewer == metadata profiles.reviewer
task.skills == VALIDATED_SKILLS
```

생성 직후 Task가 `BOARD`에서 조회되지 않거나 다른 board로 해석되는 경우 잘못된 보드에 새 Task를 재생성하지 않고 BLOCK한다. worker dispatch는 board 검증 성공 후에만 수행한다.

## 6. Kanban Body 계약

Body에는 승인된 Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Dependencies, Risks, Project Pattern Summary/References/Conflicts, Applicable Skills, Validated/Rejected Pinned Skills, Reviewer Profile과 Workspace Contract를 보존한다.

Workspace Contract 최소 항목:

```text
- Kanban board: <BOARD>
- Workspace: <WORKSPACE_PATH>
- Branch mode: current | create
- Expected branch: <BRANCH>
- Base branch: <BASE_BRANCH>
- Base SHA: <BASE_SHA>
- Effective project changes at dispatch: <EFFECTIVE_CHANGED_COUNT>
- EOL-only changes at dispatch: <EOL_ONLY_COUNT>
- Hermes managed files at dispatch: <HERMES_MANAGED_COUNT>
- 기존 변경 보존 승인 여부
- Coder는 기존 변경을 reset/restore/stash하지 않는다.
- Coder는 할당된 Workspace 밖을 수정하지 않는다.
- Coder는 Branch를 전환하거나 다른 Worktree를 만들지 않는다.
```

EOL-only/Hermes managed 파일을 사용자 변경으로 표현하지 않는다.

## 7. Kanban 알림

Task 생성 및 `kanban_show` board 검증 성공 후:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/subscribe_notification.py" --task-id "<KANBAN_TASK_ID>"
```

알림 disabled/warning은 dispatch를 막지 않는다. 알림 실패를 이유로 retry loop나 별도 Task를 만들지 않는다.

## 8. 성공 기준

- Plan/Workspace/Branch 승인 완료
- `prepare_dispatch.py` 정확히 1회
- helper가 `BOARD`, effective/EOL/Hermes managed 수와 Base SHA를 확정
- Skill Preflight PASS
- `kanban_create(board=BOARD, ...)` 1회
- `kanban_show(board=BOARD, ...)` 1회 및 board/validated skill/workspace/profile 일치
- notification helper 1회
- worker dispatch

## 9. 회귀 검증

```bash
python3 scripts/check_skill_contract.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py
```

회귀 기준: 실행 환경의 `HERMES_KANBAN_BOARD`가 managed project의 `kanban.board`와 달라도 Task 생성/조회에는 반드시 `BOARD`가 명시되어 project board를 사용해야 한다.

상위 workflow의 중복 scan/CLI probing 금지 계약은 `dev-workflow-orchestrate/references/dispatch-efficiency.md`를 따른다.
