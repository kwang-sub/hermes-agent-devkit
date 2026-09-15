# dev-worktree-cleanup

`dev-worktree-cleanup`은 PR/branch merge가 끝난 linked Git worktree를 사용자 승인 후 안전하게 정리하는 Orchestrator Skill입니다.

## 사용 시점

```text
/dev-pr-publish
→ 사용자가 GitHub에서 PR merge
→ /dev-worktree-cleanup
```

또는 자연어로 다음처럼 요청할 수 있습니다.

```text
ui-dashboard-investment worktree 정리해줘
이 작업 PR merge했으니 worktree 삭제해줘
```

## 기본 안전 규칙

- primary worktree는 삭제하지 않습니다.
- dirty/untracked 변경이 있으면 BLOCK합니다.
- open PR이 있으면 BLOCK합니다.
- local HEAD와 remote branch HEAD가 다르면 BLOCK합니다.
- GitHub merged PR 또는 Git ancestor evidence가 있어야 합니다.
- `git worktree remove --force`, `git branch -D`, reset/stash/clean을 사용하지 않습니다.
- 승인 뒤 상태가 바뀌면 cleanup fingerprint가 달라져 이전 승인을 무효화합니다.

## Merge Evidence

일반 merge는 Git ancestry로 확인할 수 있습니다.

```text
feature HEAD ∈ base history
→ MERGE_EVIDENCE=git-ancestor
```

Squash/Rebase PR merge는 feature HEAD가 base history에 직접 남지 않을 수 있으므로 GitHub PR 상태와 정확한 PR head SHA를 확인합니다.

```text
PR merged
AND PR head SHA == local HEAD
→ MERGE_EVIDENCE=github-pr-merged
```

## Cleanup scope

Remote branch가 남아 있으면 한 번의 승인 Gate에서 다음 중 하나를 선택합니다.

```text
Worktree + 로컬/원격 Branch 정리
Worktree + 로컬 Branch만 정리
취소
```

GitHub의 `Automatically delete head branches` 설정 등으로 remote branch가 이미 사라졌다면 local cleanup만 수행합니다.

## Helper

Read-only preflight:

```bash
python3 scripts/prepare_cleanup.py \
  --workspace /workspace/.worktrees/chagok/ui-dashboard-investment \
  --remote origin \
  --base-branch feature/supabase-auth
```

승인 후 local cleanup:

```bash
python3 scripts/cleanup_worktree.py \
  --workspace /workspace/.worktrees/chagok/ui-dashboard-investment \
  --remote origin \
  --base-branch feature/supabase-auth \
  --fingerprint <CLEANUP_FINGERPRINT>
```

승인 후 remote branch까지 cleanup:

```bash
python3 scripts/cleanup_worktree.py \
  --workspace /workspace/.worktrees/chagok/ui-dashboard-investment \
  --remote origin \
  --base-branch feature/supabase-auth \
  --fingerprint <CLEANUP_FINGERPRINT> \
  --delete-remote
```

## Branch 삭제 방식

Local branch는 `git branch -D` 대신 다음 형태의 exact ref delete를 사용합니다.

```text
git update-ref -d refs/heads/<branch> <approved-head-sha>
```

승인 뒤 branch가 다른 SHA로 이동했다면 삭제하지 않고 partial 상태로 종료합니다.

Remote branch도 삭제 직전 `git ls-remote`로 SHA를 다시 확인합니다.

## Windows / IntelliJ

Worktree가 Windows bind mount에 있고 IntelliJ가 해당 프로젝트를 열고 있다면 OS file lock 때문에 `git worktree remove`가 실패할 수 있습니다. 가능하면 IDE에서 해당 Worktree 프로젝트를 닫고 cleanup을 실행하는 것을 권장합니다.

실패하더라도 Skill은 `--force`로 우회하지 않으며 branch refs를 보존합니다.
