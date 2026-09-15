# dev-workspace-cleanup

`dev-workspace-cleanup`은 repository의 linked Git worktree 목록을 보여주고 사용자가 하나를 선택한 뒤, merge 완료 상태를 확인하고 승인 범위에 따라 worktree와 branch refs를 정리하는 Orchestrator Skill입니다.

## 사용 흐름

```text
/dev-pr-publish
→ 사용자가 GitHub에서 PR merge
→ /dev-workspace-cleanup
→ Worktree 목록 표시
→ Worktree 선택
→ 정리 Preview
→ Worktree + 로컬/원격 Branch 정리 승인
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
   Branch: feature/ui-dashboard-investment
   Status: CLEAN
   Remote: origin/feature/ui-dashboard-investment

2. investment-data-model
   Branch: feature/investment-data-model
   Status: DIRTY
   Remote: origin/feature/investment-data-model
```

Primary worktree는 선택 대상에서 제외하고 linked worktree만 선택하게 합니다.

## 승인 범위

Remote branch가 남아 있으면:

```text
[Worktree 정리 승인]
- Worktree + 로컬/원격 Branch 정리
- Worktree + 로컬 Branch만 정리
- 취소
```

첫 번째를 선택하면 선택한 worktree에 연결된 **동일 branch 이름의 local/remote ref까지** 정리합니다.

## 안전 규칙

- primary worktree는 삭제하지 않습니다.
- dirty/untracked 변경이 있으면 BLOCK합니다.
- open PR이 있으면 BLOCK합니다.
- local HEAD와 존재하는 remote branch HEAD가 다르면 BLOCK합니다.
- GitHub merged PR 또는 Git ancestor evidence가 있어야 합니다.
- `git worktree remove --force`, `git branch -D`, reset/stash/clean을 사용하지 않습니다.
- 승인 뒤 상태가 바뀌면 cleanup fingerprint가 달라져 이전 승인을 무효화합니다.

## Merge Evidence

일반 merge:

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
  --base-branch feature/supabase-auth
```

승인 후 local cleanup:

```bash
python3 scripts/cleanup_workspace.py \
  --workspace /workspace/.worktrees/chagok/ui-dashboard-investment \
  --remote origin \
  --base-branch feature/supabase-auth \
  --fingerprint <CLEANUP_FINGERPRINT>
```

승인 후 remote branch까지 cleanup:

```bash
python3 scripts/cleanup_workspace.py \
  --workspace /workspace/.worktrees/chagok/ui-dashboard-investment \
  --remote origin \
  --base-branch feature/supabase-auth \
  --fingerprint <CLEANUP_FINGERPRINT> \
  --delete-remote
```

## Branch 삭제 방식

Local branch는 `git branch -D` 대신 다음 exact ref delete를 사용합니다.

```text
git update-ref -d refs/heads/<branch> <approved-head-sha>
```

Remote branch도 삭제 직전 `git ls-remote`로 SHA를 다시 확인합니다.

## Windows / IntelliJ

Worktree 프로젝트가 IntelliJ에서 열려 있으면 Windows file lock으로 `git worktree remove`가 실패할 수 있습니다. 가능하면 선택한 Worktree 프로젝트를 닫고 cleanup을 승인하는 것을 권장합니다.

실패하더라도 Skill은 force 삭제하지 않습니다.
