---
name: dev-pr-publish
description: 완료된 별도 Git branch/worktree의 변경을 사용자 승인 기반으로 commit+push하고 PR preview 재승인 후 GitHub PR을 생성한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, commit, push, pull-request, github, worktree, branch, publish, approval]
    related_skills: [dev-workspace-dispatch, dev-review-cycle, dev-workflow-orchestrate]
    requires_tools: [terminal, clarify, kanban_show]
---

# dev-pr-publish

완료된 구현을 **사용자가 확인한 내용만** Git 원격에 게시하는 post-review publish Skill이다. 구현/리뷰 Skill과 분리되어 있으며 source 수정, review, merge를 수행하지 않는다.

표준 흐름:

```text
DONE / Reviewer APPROVED / Fast LOW 완료
→ read-only publish preflight
→ [커밋 승인]
→ commit
→ 즉시 push
→ PR preview 생성
→ [PR 생성 승인]
→ PR 생성
→ PR URL 출력
→ STOP
→ 사용자가 GitHub에서 직접 review/merge
```

## 1. 진입 조건

다음을 모두 만족해야 한다.

- 대상은 Git repository다.
- detached HEAD가 아니다.
- 현재 branch는 PR base branch와 다르다.
- 별도 branch 또는 linked worktree에서 작업된 변경이다.
- publish할 변경이 존재한다.
- `origin` 또는 사용자가 지정한 remote가 존재한다.
- GitHub PR 생성에 사용할 `gh` CLI가 존재하고 인증 상태가 정상이다.
- Standard/Fast Kanban Task를 통해 완료된 작업이면 가능한 경우 `kanban_show`로 Task 상태, Workspace, Branch, Base Branch, 검증/리뷰 결과를 read-only 확인한다.

`dev-workflow-orchestrate`/Coder/Reviewer의 구현 단계에서는 commit/push/PR을 하지 않는다. `dev-pr-publish`가 **사용자 요청 후 별도 단계**로만 이를 담당한다.

## 2. Base Branch 결정

Base Branch는 추측하지 않는다. 우선순위는 다음과 같다.

```text
1. Kanban Task body의 Base branch
2. 사용자가 명시한 base branch
3. refs/remotes/origin/HEAD가 명확할 때 해당 branch
4. 그래도 불명확하면 사용자에게 clarify
```

`main`, `master`, `dev`를 임의 선택하지 않는다.

## 3. Read-only Publish Preflight

먼저 다음 helper를 실행한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_publish.py" \
  --workspace "<WORKSPACE>" \
  --remote "<REMOTE>" \
  [--base-branch "<BASE_BRANCH>"]
```

helper는 source/index를 변경하지 않고 다음을 확정한다.

```text
Repository root
Current branch
Base branch
Local HEAD
Remote URL
Changed files
Diff stat
Publish scope
Publish fingerprint
기존 open PR 존재 여부
```

`PUBLISH_FINGERPRINT`는 승인 직후 mutation 전에 다시 비교하는 immutable snapshot이다. 승인 이후 파일 내용/상태가 바뀌면 이전 승인은 무효다.

### Publish Scope

기본 publish scope는 preflight 시점의 현재 변경 전체다. 파일별 목록을 사용자에게 반드시 보여준다.

사용자가 일부 파일 제외/추가를 요청하면 승인으로 간주하지 않는다. scope를 갱신하고 preflight를 다시 실행한 뒤 같은 `[커밋 승인]` Gate를 다시 보여준다.

`git add .`를 승인 전에 실행하지 않는다.

## 4. 커밋 Preview

`clarify`를 호출하기 전에 일반 메시지로 다음을 보여준다.

```text
[커밋 Preview]
Workspace: <workspace>
Branch: <head branch>
Base: <base branch>
Remote: <remote>

Changed Files:
- <status> <path>
...

Diff Stat:
<stat>

Commit Message:
<type>: <한국어 설명>
```

Commit message 기본 규칙:

```text
Conventional Commits prefix는 영어
설명은 한국어

feat: 투자 대시보드 UI 구현
fix: Git worktree 상대경로 처리 수정
refactor: 출력 이력 조회 구조 정리
```

PR title/body도 기본적으로 한국어로 작성한다. 코드/API/클래스/브랜치명/기술 용어는 영어를 유지한다.

## 5. Gate C — Commit + Push 승인

커밋 Preview를 일반 메시지로 전부 보여준 직후 **독립 clarify Gate**를 호출한다.

```text
question:
  [커밋 승인]
  위 변경을 커밋하고 현재 Branch를 원격에 Push할까요?
choices:
  - 커밋 및 Push 승인
  - 커밋 메시지 수정
  - 취소
```

규칙:

- `커밋 및 Push 승인`만 mutation 승인이다.
- 승인에는 **현재 preview 그대로 commit + 정상 push**까지 포함한다.
- Push만을 위한 별도 승인 Gate는 만들지 않는다.
- `커밋 메시지 수정`/Other는 메시지를 갱신한 뒤 같은 Gate를 다시 보여준다.
- 파일/scope 변경 요청이면 preflight부터 다시 수행한다.
- 승인 전 `git add`, `git commit`, `git push` 금지다.

승인 후 다음 helper를 정확히 한 번 실행한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/publish_commit.py" \
  --workspace "<WORKSPACE>" \
  --remote "<REMOTE>" \
  --branch "<BRANCH>" \
  --fingerprint "<PUBLISH_FINGERPRINT>" \
  --message "<COMMIT_MESSAGE>"
```

helper 계약:

```text
현재 fingerprint 재검증
→ approved scope stage
→ commit
→ git push --set-upstream <remote> <branch>
→ PUSHED_COMMIT_SHA 반환
```

Push는 정상 fast-forward/non-force path만 허용한다. 다음은 금지한다.

```text
git push --force
git push --force-with-lease
git reset
git restore
git clean
git stash
```

remote rejection이 발생하면 강제 push하지 않고 BLOCK한다. 이 경우 local commit이 이미 생성되었을 수 있으므로 해당 SHA를 보존해 보고한다.

## 6. PR Preview

Commit+Push 성공 후 **바로 PR을 생성하지 않는다.** 먼저 helper로 원격/중복 PR 상태를 read-only 확인한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_pr.py" \
  --workspace "<WORKSPACE>" \
  --remote "<REMOTE>" \
  --base "<BASE_BRANCH>" \
  --head "<BRANCH>"
```

기존 동일 `base + head` open PR이 있으면:

```text
STATUS=existing-pr
```

로 종료하고 새 PR을 생성하지 않는다. 기존 PR URL을 사용자에게 보여주고 STOP한다.

신규 PR이면 Task/commit/검증 결과를 바탕으로 일반 메시지에 다음 Preview를 보여준다.

```text
[PR Preview]
Base: <base>
Head: <head>

Title:
<한국어 제목>

Body:
## 변경 내용
- ...

## 검증
- ...

## 작업 정보
- Task: <task | none>
- Branch: <head>
- Base: <base>
```

내부 모델명/provider/session id/OAuth 정보는 PR body에 넣지 않는다.

## 7. Gate P — PR 생성 승인

PR Preview를 일반 메시지로 보여준 직후 별도 `clarify`를 호출한다.

```text
question:
  [PR 생성 승인]
  위 내용으로 Pull Request를 생성할까요?
choices:
  - PR 생성
  - PR 내용 수정
  - 취소
```

규칙:

- `PR 생성`만 실제 PR 생성 승인이다.
- `PR 내용 수정`/Other는 title/body를 갱신한 뒤 같은 Gate를 다시 보여준다.
- Commit 승인과 PR 생성 승인을 한 질문으로 합치지 않는다.
- Reviewer APPROVED/DONE 자체를 PR 생성 승인으로 간주하지 않는다.

승인 후 다음 helper를 정확히 한 번 실행한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/create_pr.py" \
  --workspace "<WORKSPACE>" \
  --remote "<REMOTE>" \
  --base "<BASE_BRANCH>" \
  --head "<BRANCH>" \
  --title "<PR_TITLE>" \
  --body "<PR_BODY>"
```

성공 출력:

```text
STATUS=created
PR_URL=<url>
```

그 뒤 즉시 STOP한다.

## 8. 명시적 금지

이 Skill은 다음을 절대 수행하지 않는다.

```text
PR approve
PR merge
auto-merge enable
branch delete
worktree cleanup
source 수정
Reviewer 대체
force push
base branch 직접 commit
```

최종 merge는 사용자가 GitHub에 직접 방문해 수행한다.

## 9. 상태 변경 시 승인 무효화

다음 중 하나라도 발생하면 `[커밋 승인]`부터 다시 받아야 한다.

- changed file set 변경
- file content 변경
- staged/unstaged 상태가 의미 있게 변경
- branch 변경
- HEAD 변경
- publish scope 변경

Commit+Push 이후 다음이 바뀌면 `[PR 생성 승인]` Preview를 다시 만들어야 한다.

- remote head SHA
- base branch
- PR title/body
- 기존 open PR 상태

## 10. Worktree/Branch 공통 처리

linked worktree 여부와 상관없이 Git repository root/current branch를 기준으로 처리한다.

```text
/workspace/.worktrees/project/task-a   → feature/task-a
/workspace/project                     → feature/task-b
```

둘 다 동일 helper를 사용한다. Worktree path 자체를 PR identity로 사용하지 않고 `remote + head branch + base branch`를 사용한다.

## 11. 회귀 검증

```bash
python3 custom-skills/orchestrator/dev-pr-publish/tests/test_pr_publish.py
python3 scripts/check_skill_contract.py
python3 scripts/check_update_devkit_contract.py
```

DevKit 변경 최종 반영 전 기존 Git CI와 `update-devkit` 계약이 모두 정상인지 확인한다.
