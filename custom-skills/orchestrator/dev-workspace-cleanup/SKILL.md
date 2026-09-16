---
name: dev-workspace-cleanup
description: Git worktree 목록을 보여주고 사용자가 선택한 linked worktree의 상태를 검증한 뒤 승인 범위에 따라 worktree와 안전한 로컬/원격 브랜치를 정리한다.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, workspace, worktree, cleanup, branch, pull-request, github, approval]
    related_skills: [dev-pr-publish, dev-workspace-dispatch]
    requires_tools: [terminal, clarify]
---

# dev-workspace-cleanup

PR/branch 작업이 끝난 linked Git worktree를 **목록에서 선택**한 뒤, clean/merge 상태를 확인하고 사용자 승인 범위만 정리하는 post-merge Skill이다.

`dev-worktree-cleanup`은 과거 deprecated 이름이므로 사용하지 않는다. 신규 cleanup 표준은 `dev-workspace-cleanup`이다.

표준 흐름:

```text
PR merge 완료
→ /dev-workspace-cleanup
→ linked worktree 목록 조회
→ [Worktree 선택]
→ 선택 대상 read-only cleanup preflight
→ [Worktree 정리 Preview]
→ [Worktree 정리 승인]
→ worktree remove
→ feature branch cleanup이 허용된 경우 exact local branch ref delete
→ worktree prune
→ 승인한 경우에만 feature remote branch delete
→ 결과 보고
```

## 0. 독립 실행 원칙

이 Skill은 Kanban Task context가 없어도 동작한다.

- `HERMES_KANBAN_TASK` 또는 명시적 task id가 없으면 `kanban_show`, `kanban_sh` 등 Kanban 조회를 호출하지 않는다.
- helper가 `STATUS=blocked`를 반환하면 해당 `ERROR`를 그대로 판단 근거로 사용한다.
- helper 실패 후 `git config --global --add safe.directory ...` 같은 전역 Git 설정 변경을 자동 시도하지 않는다.
- safe.directory는 helper 내부의 **process-local Git config**만 사용한다.
- unrelated remediation을 수행한 뒤 helper를 재실행하지 않는다.

## 1. Worktree 목록 조회

현재 repository 또는 사용자가 지정한 repository에서 먼저 다음 helper를 실행한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/list_worktrees.py" \
  --repo "<REPOSITORY_OR_ANY_WORKTREE_PATH>" \
  --remote "<REMOTE>"
```

helper는 **read-only**이며 `git worktree list --porcelain`을 기준으로 모든 worktree를 조회한다.

목록에는 최소 다음을 표시한다.

```text
Index
Path
Branch
HEAD
Primary 여부
Clean / Dirty
Remote Branch 존재 여부
Cleanup Scope Hint
```

Primary worktree는 정보로는 표시할 수 있지만 선택지에는 넣지 않는다. linked worktree만 cleanup 선택 후보가 된다.

일반 메시지 예시:

```text
[Worktree 목록]
1. ui-dashboard-investment
   Path: /workspace/.worktrees/chagok/ui-dashboard-investment
   Branch: dev
   Status: CLEAN
   Remote: origin/dev
   Cleanup: Worktree만 정리 (base branch 보존)

2. investment-data-model
   Path: /workspace/.worktrees/chagok/investment-data-model
   Branch: feature/investment-data-model
   Status: CLEAN
   Remote: origin/feature/investment-data-model
   Cleanup: Worktree + Branch 정리 가능 여부 검증
```

그 다음 **독립 clarify Gate**로 하나만 선택한다.

```text
question:
  [Worktree 선택]
  정리할 linked Worktree를 선택해 주세요.
choices:
  - <worktree-name> — <branch> (<scope hint>)
  - <worktree-name> — <branch> (<scope hint>)
  - 취소
```

여러 worktree를 한 번에 선택/삭제하지 않는다. 한 실행에서 정확히 하나만 정리한다.

## 2. 선택 후 공통 진입 조건

선택된 대상은 다음을 모두 만족해야 한다.

- primary worktree가 아닌 linked worktree다.
- detached HEAD가 아니다.
- Git metadata에 정확히 1개로 등록되어 있다.
- `locked` 또는 `prunable` 상태가 아니다.
- tracked/untracked 변경이 전혀 없다.

변경 파일이 하나라도 있으면 `--force`, reset, stash, clean으로 우회하지 않고 BLOCK한다.

## 3. Cleanup Scope 결정

### A. Feature/작업 Branch Worktree

현재 branch와 base branch가 다르면 기존 feature branch cleanup 경로를 사용한다.

추가 조건:

- 같은 branch가 다른 worktree에도 연결되어 있지 않다.
- local HEAD와 존재하는 remote branch HEAD가 동일하다.
- open Pull Request가 남아 있지 않다.
- 아래 Merge Evidence 중 하나가 존재한다.

```text
1. GitHub merged PR + PR head SHA == local HEAD
2. local HEAD가 resolved base ref의 ancestor
```

Evidence 값:

```text
github-pr-merged
git-ancestor
```

이 경우:

```text
CLEANUP_SCOPE=worktree-and-branch
BRANCH_CLEANUP_ALLOWED=true
```

### B. Base Branch에 이미 전환된 linked Worktree

PR merge 이후 linked worktree가 `dev`, `main` 등 resolved base branch로 전환된 경우 **worktree 자체는 삭제할 수 있어야 한다.**

이 상태에서 현재 branch를 cleanup branch로 해석하면 `dev/main` 로컬·원격 branch를 삭제할 위험이 있으므로 branch 삭제는 절대 수행하지 않는다.

```text
current branch == resolved base branch
→ CLEANUP_SCOPE=worktree-only
→ BRANCH_CLEANUP_ALLOWED=false
→ MERGE_EVIDENCE=base-branch-worktree
→ linked worktree만 제거
→ local base branch 보존
→ remote base branch 보존
```

이 경로에서는 `--delete-remote`를 전달하면 BLOCK한다. `origin/dev`, `origin/main` 같은 base branch를 삭제 대상으로 제시하지 않는다.

Worktree 이름이 과거 feature branch 이름과 비슷하더라도 이름만으로 원래 branch를 추측하여 삭제하지 않는다. 원래 feature branch를 안전하게 증명할 수 없는 경우 branch는 보존한다.

## 4. Base Branch 결정

Base Branch 우선순위:

```text
1. 사용자가 명시한 base branch
2. 현재 HEAD와 정확히 일치하는 merged PR의 base branch (feature cleanup 경로)
3. refs/remotes/<remote>/HEAD
4. 그래도 불명확하면 사용자에게 clarify
```

Feature cleanup 경로에서는 Base Branch와 cleanup 대상 branch가 같으면 feature branch 삭제 경로로 진행하지 않는다.
대신 선택 worktree가 실제 base branch를 checkout 중이면 **Worktree-only 경로**로 전환한다.

## 5. Read-only Cleanup Preflight

선택 후 다음 helper를 실행한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_cleanup.py" \
  --workspace "<SELECTED_WORKTREE>" \
  --remote "<REMOTE>" \
  [--base-branch "<BASE_BRANCH>"]
```

helper는 mutation 없이 다음을 확정한다.

```text
Primary worktree
Selected worktree
Branch / HEAD SHA
Base branch / base ref
Cleanup Scope
Branch Cleanup Allowed
Remote URL
Remote branch 존재 여부와 SHA
GitHub auth 상태 (필요한 경우)
Merged PR URL/번호 (feature cleanup일 때)
Merge Evidence
Remote branch 삭제 가능 여부
Cleanup fingerprint
```

`CLEANUP_FINGERPRINT`는 approval snapshot이다. 승인 후 다음 중 하나라도 바뀌면 이전 승인은 무효다.

```text
worktree registration
branch / HEAD
working tree status
base branch/ref
remote branch SHA
merged PR evidence
cleanup scope
```

변경되면 선택 대상 preflight부터 다시 수행하고 Preview/Gate를 다시 보여준다.

## 6. Worktree 정리 Preview

`clarify` 전에 일반 메시지로 다음을 보여준다.

Feature branch 예시:

```text
[Worktree 정리 Preview]
Worktree: <path>
Branch: <feature branch>
HEAD: <sha>
Base: <base>
Cleanup Scope: worktree-and-branch
Merge Evidence: <github-pr-merged | git-ancestor>
PR: <url | none>
Remote Branch: <remote>/<feature branch> <exists | already absent>

정리 대상:
- linked worktree 제거
- local feature branch 제거
- remote feature branch: <승인 시 삭제 가능 | 이미 없음 | 삭제 불가>
```

Base branch worktree 예시:

```text
[Worktree 정리 Preview]
Worktree: <path>
Branch: dev
Base: dev
Cleanup Scope: worktree-only
Merge Evidence: base-branch-worktree

정리 대상:
- linked worktree 제거
- local dev 보존
- origin/dev 보존
```

Windows/IntelliJ가 선택 Worktree를 열고 있으면 파일 lock으로 `git worktree remove`가 실패할 수 있으므로 가능하면 해당 프로젝트를 닫고 승인하도록 안내한다. 실패해도 force 삭제하지 않는다.

## 7. Gate — Worktree 정리 승인

### Feature branch cleanup

Remote branch가 존재하고 삭제 가능한 경우:

```text
question:
  [Worktree 정리 승인]
  선택한 Worktree와 연결 Branch를 정리할까요?
choices:
  - Worktree + 로컬/원격 Branch 정리
  - Worktree + 로컬 Branch만 정리
  - 취소
```

`Worktree + 로컬/원격 Branch 정리`를 선택하면 다음을 모두 승인한 것으로 본다.

```text
selected linked worktree 삭제
local refs/heads/<feature branch> 삭제
remote refs/heads/<feature branch> 삭제
```

### Base branch worktree cleanup

`CLEANUP_SCOPE=worktree-only`이면 branch 삭제 선택지를 보여주지 않는다.

```text
question:
  [Worktree 정리 승인]
  선택한 linked Worktree만 제거할까요? Base Branch는 보존됩니다.
choices:
  - Worktree만 정리
  - 취소
```

`Worktree만 정리` 승인에는 worktree remove + worktree prune만 포함한다.

## 8. 승인 후 Mutation

Feature branch에서 remote branch 유지:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/cleanup_workspace.py" \
  --workspace "<SELECTED_WORKTREE>" \
  --remote "<REMOTE>" \
  --base-branch "<BASE_BRANCH>" \
  --fingerprint "<CLEANUP_FINGERPRINT>"
```

Feature remote branch까지 삭제:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/cleanup_workspace.py" \
  --workspace "<SELECTED_WORKTREE>" \
  --remote "<REMOTE>" \
  --base-branch "<BASE_BRANCH>" \
  --fingerprint "<CLEANUP_FINGERPRINT>" \
  --delete-remote
```

Base branch worktree는 첫 번째 명령과 동일하게 실행하되 helper가 자동으로 `worktree-only` 경로를 선택한다. `--delete-remote`는 사용하지 않는다.

Feature helper 순서:

```text
fingerprint + merge evidence 재검증
→ git worktree remove <worktree>
→ target worktree 미등록 확인
→ git update-ref -d refs/heads/<feature branch> <expected HEAD>
→ git worktree prune
→ remote 삭제 승인 시 remote SHA 재확인
→ git push <remote> --delete <feature branch>
```

Base worktree helper 순서:

```text
fingerprint + worktree-only scope 재검증
→ git worktree remove <worktree>
→ target worktree 미등록 확인
→ git worktree prune
→ base local/remote branch 보존
```

Local feature branch는 `git branch -D`를 사용하지 않는다. squash/rebase merge도 지원하면서 잘못 이동한 branch를 삭제하지 않기 위해 **승인된 exact HEAD를 old SHA로 지정한 `git update-ref -d`**만 사용한다.

## 9. Remote Branch 삭제 규칙

Remote branch 삭제는 `CLEANUP_SCOPE=worktree-and-branch`이고 `Worktree + 로컬/원격 Branch 정리` choice를 명시적으로 승인했을 때만 수행한다.

삭제 직전에 `git ls-remote`로 remote branch SHA를 다시 읽고 승인 시점 SHA와 다르면 remote branch를 보존하고 `partial`로 종료한다.

HTTPS GitHub remote에서는 `dev-pr-publish`와 같은 persistent `gh` 인증을 one-command credential helper로 사용한다. GitHub 인증이 준비되지 않으면 remote 삭제 option을 제공하지 않는다.

GitHub에서 PR merge 후 feature branch를 자동 삭제해 remote ref가 이미 없으면 성공 상태로 간주하고 local cleanup만 수행한다.

`CLEANUP_SCOPE=worktree-only`에서는 remote branch deletion 자체가 금지다.

## 10. Partial Failure

Mutation은 rollback을 시도하지 않는다.

```text
worktree remove 실패
→ branch refs는 건드리지 않고 BLOCK

worktree remove 성공 + local feature ref delete 실패
→ STATUS=partial
→ worktree 제거 상태와 남은 local branch를 보고

local cleanup 성공 + remote feature delete 실패
→ STATUS=partial
→ local cleanup 완료 상태와 남은 remote branch를 보고
```

Partial 상태에서는 자동 재시도하지 않는다. 현재 repository에서 worktree 목록/preflight를 다시 읽어 다음 조치를 결정한다.

## 11. 절대 금지

```text
git worktree remove --force
git branch -D
git push --force
git push --force-with-lease
git reset
git restore
git clean
git stash
rm -rf
primary worktree 삭제
open PR feature branch 삭제
merge evidence 없는 feature branch 삭제
base branch local/remote 삭제
승인되지 않은 remote branch 삭제
git config --global safe.directory 자동 변경
```

## 12. dev-pr-publish와 역할 분리

```text
dev-pr-publish
  commit + push + PR create까지만 담당
  PR merge는 사용자가 GitHub에서 수행

dev-workspace-cleanup
  merge 완료 후 목록 선택 + worktree cleanup
  안전하게 증명된 feature branch만 local/remote cleanup
```

PR 생성 직후 자동 cleanup하지 않는다. 사용자가 GitHub에서 merge를 완료한 뒤 별도 요청으로 실행한다.
