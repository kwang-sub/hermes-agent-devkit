---
name: dev-workspace-dispatch
description: 승인된 구현 계획과 project pattern/capability 계약을 Git workspace와 Kanban으로 인계한다.
version: 0.9.1
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

## 1. 진입 조건
- Plan 승인 완료
- workspace/current 또는 create branch 승인 완료
- 기존 변경이 있을 수 있는 workspace라면 reset/restore/stash 없이 전부 보존할지 승인 완료
- `.hermes/project.yaml` managed metadata 존재

## 2. 대형 Workspace Fast Path

Bootstrap과 동일하게 **필요하지 않은 repository-wide Git scan은 생략**한다.

사용자가 기존 변경 전체 보존을 이미 승인한 경우:

```text
prepare_dispatch.py --confirmed-dirty
→ repository/workspace/branch/Base SHA/Board만 검증
→ repository-wide dirty/EOL/untracked 분류를 **생략**
→ WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation
→ *_COUNT=-1, WORKSPACE_*_DIRTY=unknown
```

`-1/unknown`은 실패가 아니라 **not-scanned** 의미다. 이 값을 0으로 해석하지 않는다.

기존 변경 보존 승인이 없는 경우에만 `prepare_dispatch.py`가 정확한 dirty 상태 확인을 위해 다음 batch scan을 수행한다.

```text
git diff --name-only -z HEAD
git diff --name-only -z --ignore-cr-at-eol HEAD
git ls-files -z --others --exclude-standard
```

이 진단 경로에서도 파일별 `git diff --quiet` 반복 호출은 금지한다.

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

Helper 출력의 `BOARD`는 `.hermes/project.yaml`의 `kanban.board`이며 Standard Flow의 유일한 Kanban board source다. `HERMES_KANBAN_BOARD`나 이전 세션/default board를 fallback으로 사용하지 않는다.

## 4. Skill Preflight

`skill_view("dev-skill-preflight")` 후 Coder/Reviewer 공통 사용 가능 skill만 pin한다.

```text
VALIDATED_SKILLS → kanban_create.skills
REJECTED_SKILLS → body 기록만 하고 pin 금지
```

## 5. Kanban 생성 단일 경로

```text
prepare_dispatch.py 정확히 한 번만 수행
→ dev-skill-preflight
→ kanban_create(board=BOARD, ...) tool 정확히 1회
→ kanban_show(board=BOARD, task_id=<CREATED_TASK_ID>) tool 정확히 1회
→ subscribe_notification.py 정확히 1회
→ worker dispatch
```

호출 횟수 계약은 `kanban_create tool 정확히 1회`, `kanban_show tool 정확히 1회`이다.

금지:

```text
board 인자 생략
HERMES_KANBAN_BOARD fallback
hermes kanban --board <board> create --help
hermes project list / --help
Kanban body 임시 파일
CLI body-file 지원 여부 탐색
CLI fallback을 탐색하지 않고 BLOCK
```

`kanban_show`에서 최소 다음을 검증한다.

```text
board == BOARD
workspace == dir:<APPROVED_WORKSPACE>
assignee == profiles.coder
reviewer == profiles.reviewer
task.skills == VALIDATED_SKILLS
```

## 6. Workspace Contract

Task body에는 다음을 남긴다.

```text
- Kanban board: <BOARD>
- Workspace: <WORKSPACE_PATH>
- Branch mode: current | create
- Expected branch: <BRANCH>
- Base branch: <BASE_BRANCH>
- Base SHA: <BASE_SHA>
- Existing changes preservation approved: true | false
- Workspace change scan mode: full | skipped-approved-preservation
- Effective project changes at dispatch: <count | unknown>
- EOL-only changes at dispatch: <count | unknown>
- Hermes managed files at dispatch: <count | unknown>
```

Fast Path에서는 exact 기존 변경 목록 대신 **모든 기존 변경 보존 승인** 자체가 baseline 계약이다. Coder는 자신의 실제 변경 scope를 구현 과정에서 명시적으로 기록하고 그 scope만 검증한다.

## 7. 성능 불변식

- Workspace 승인 전 working-tree 전체 scan을 하지 않는다.
- `--confirmed-dirty` 이후 exact count를 얻기 위해 다시 `git status`, `git diff`, `git ls-files`, inline Python 분류를 실행하지 않는다.
- Coder/Reviewer는 Task 전체 repository가 아니라 실제 changed scope만 검증한다.
- large/binary file을 임의 크기 기준으로 제외하지 않는다. 불필요한 전체 scan 자체를 생략하고 필요한 path만 검사한다.

## 8. 회귀 검증

```bash
python3 scripts/check_skill_contract.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py
```

성능 관찰용 full scan 출력은 다음을 유지한다.

```text
GIT_TRACKED_SCAN_SECONDS
GIT_EFFECTIVE_SCAN_SECONDS
GIT_UNTRACKED_SCAN_SECONDS
CLASSIFICATION_SECONDS
WORKSPACE_CLASSIFICATION_TOTAL_SECONDS
```
