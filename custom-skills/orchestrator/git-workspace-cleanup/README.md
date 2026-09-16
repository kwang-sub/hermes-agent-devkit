# dev-workspace-cleanup

`dev-workspace-cleanup`은 repository의 linked Git worktree 목록을 보여주고 사용자가 하나를 선택한 뒤, 상태를 확인하고 승인 범위에 따라 worktree와 안전한 branch refs를 정리하는 Orchestrator Skill입니다.

## 사용 흐름

```text
/dev-pr-publish
→ 사용자가 GitHub에서 PR merge
→ /dev-workspace-cleanup
→ Worktree 목록 표시
→ Worktree 선택
→ 정리 Preview
→ 승인 범위 선택
→ cleanup
```

자연어 요청도 가능합니다.

```text
워크트리 정리해줘
현재 프로젝트 Worktree 목록 보여주고 정리할거 선택하게 해줘
```

## 목록 예시

```text
[Worktree 목록]
1. ui-dashboard-investment
   Branch: dev
   Status: CLEAN
   Remote: origin/dev
   Cleanup: Worktree만 정리 (base branch 보존)

2. investment-data-model
   Branch: feature/investment-data-model
   Status: CLEAN
   Remote: origin/feature/investment-data-model
   Cleanup: Worktree + Branch 정리 가능 여부 검증
```

Primary worktree는 선택 대상에서 제외하고 linked worktree만 선택하게 합니다.

## 두 가지 Cleanup Scope

### 1. Feature branch Worktree

현재 branch와 resolved base branch가 다르고 merge evidence가 확인되면 기존처럼 branch까지 정리할 수 있습니다.

```text
CLEANUP_SCOPE=worktree-and-branch
BRANCH_CLEANUP_ALLOWED=true
```

Remote branch가 남아 있으면:

```text
[Worktree 정리 승인]
- Worktree + 로컬/원격 Branch 정리
- Worktree + 로컬 Branch만 정리
- 취소
```

첫 번째를 선택하면 선택한 worktree에 연결된 **동일 feature branch 이름의 local/remote ref까지** 정리합니다.

### 2. Base branch로 이미 전환된 linked Worktree

PR merge 이후 linked worktree가 `dev`, `main` 같은 base branch를 checkout하고 있을 수 있습니다. 이 경우 worktree 자체는 삭제할 수 있지만 현재 branch를 삭제 대상으로 해석하면 base branch를 지울 위험이 있습니다.

따라서:

```text
current branch == resolved base branch
→ CLEANUP_SCOPE=worktree-only
→ BRANCH_CLEANUP_ALLOWED=false
→ MERGE_EVIDENCE=base-branch-worktree
```

승인은 다음처럼 단순화됩니다.

```text
[Worktree 정리 승인]
- Worktree만 정리
- 취소
```

이 경로에서는:

```text
linked worktree 제거
local dev/main 보존
origin/dev/main 보존
```

만 수행합니다. `--delete-remote`를 전달하면 BLOCK합니다.

## 안전 규칙

- primary worktree는 삭제하지 않습니다.
- dirty/untracked 변경이 있으면 BLOCK합니다.
- feature branch cleanup은 open PR이 있으면 BLOCK합니다.
- feature branch cleanup은 local HEAD와 존재하는 remote branch HEAD가 다르면 BLOCK합니다.
- feature branch 삭제에는 GitHub merged PR 또는 Git ancestor evidence가 필요합니다.
- base branch worktree는 worktree만 제거하고 local/remote base branch를 보존합니다.
- `git worktree remove --force`, `git branch -D`, reset/stash/clean을 사용하지 않습니다.
- 승인 뒤 상태가 바뀌면 cleanup fingerprint가 달라져 이전 승인을 무효화합니다.
- `safe.directory` 문제를 해결하기 위해 global Git config를 수정하지 않고 helper process-local config만 사용합니다.
- 명시적 Kanban task id가 없으면 Kanban 조회를 시도하지 않습니다.

## Merge Evidence

일반 feature merge:

```text
feature HEAD ∈ base history
→ MERGE_EVIDENCE=git-ancestor
```

Squash/Rebase PR merge:

```text
PR merged
AND PR head SHA == local HEAD
→ MERGE_EVIDENCE=github-pr-merged
```

Base branch linked worktree:

```text
current branch == resolved base branch
→ MERGE_EVIDENCE=base-branch-worktree
```

마지막 값은 branch 삭제 근거가 아니라 **worktree-only cleanup 모드**를 뜻합니다.

## Helper

Worktree 목록:

```bash
python3 scripts/list_worktrees.py \
  --repo /workspace/chagok \
  --remote origin
```

선택 대상 read-only preflight:

```bash
python3 scripts/prepare_cleanup.py \
  --workspace /workspace/.worktrees/chagok/ui-dashboard-investment \
  --remote origin \
  --base-branch dev
```

승인 후 cleanup:

```bash
python3 scripts/cleanup_workspace.py \
  --workspace /workspace/.worktrees/chagok/ui-dashboard-investment \
  --remote origin \
  --base-branch dev \
  --fingerprint <CLEANUP_FINGERPRINT>
```

Feature remote branch까지 cleanup할 때만:

```bash
python3 scripts/cleanup_workspace.py \
  --workspace /workspace/.worktrees/chagok/investment-data-model \
  --remote origin \
  --base-branch dev \
  --fingerprint <CLEANUP_FINGERPRINT> \
  --delete-remote
```

## Branch 삭제 방식

Feature Local branch는 `git branch -D` 대신 다음 exact ref delete를 사용합니다.

```text
git update-ref -d refs/heads/<feature-branch> <approved-head-sha>
```

Feature Remote branch도 삭제 직전 `git ls-remote`로 SHA를 다시 확인합니다.

Base branch worktree cleanup에서는 branch ref delete 자체를 실행하지 않습니다.

## Windows / IntelliJ

Worktree 프로젝트가 IntelliJ에서 열려 있으면 Windows file lock으로 `git worktree remove`가 실패할 수 있습니다. 가능하면 선택한 Worktree 프로젝트를 닫고 cleanup을 승인하는 것을 권장합니다.

실패하더라도 Skill은 force 삭제하지 않습니다.
