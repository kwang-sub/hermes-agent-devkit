---
name: dev-worktree-remove
description: Hermes DevKit에서 Git worktree를 확인하고 미커밋·미추적 데이터를 보존하며 안전하게 제거한다.
version: 0.1.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, core, git, worktree, cleanup]
    requires_tools: [terminal]
---

# DevKit Git worktree 제거

사용자가 특정 worktree 제거를 요청할 때만 실행한다. Standard의 `git-workspace-cleanup`, Kanban 완료 상태 또는 PR 게시 여부를 전제하지 않는다.

## 제거 전 필수 점검
1. 저장소와 삭제 대상 경로를 확정하고 `git -C "$REPO" worktree list --porcelain`에서 **정확히 등록된** linked worktree인지 확인한다.
2. `git -C "$REPO" worktree list --porcelain`에서 첫 번째 `worktree` 항목인 primary worktree 경로를 확인하고 그 경로는 절대 삭제하지 않는다. (`git rev-parse --show-toplevel`은 현재 linked worktree를 가리킬 수 있으므로 primary 판별에 사용하지 않는다.) 현재 에이전트의 working directory나 사용 중인 세션·프로세스의 작업 공간이라면 다른 안전한 작업 디렉터리로 이동할 수 없는 경우 중단한다.
3. `git -C "$TARGET" status --porcelain=v1 --untracked-files=all` 결과가 비어 있는지 확인한다. staged/unstaged/untracked 변경이 하나라도 있으면 중단하고 목록을 제시한다. ignored 파일도 남을 수 있으므로 `git -C "$TARGET" status --ignored --short`를 확인하고 데이터 가치가 있는 ignored 파일이 있다면 보존을 우선한다.
4. `git -C "$REPO" worktree list --porcelain`의 locked 상태를 확인한다. locked, 손상, 접근 불가, 경로 불일치가 있으면 중단한다.
5. 제거 전에 대상 절대 경로와 브랜치를 사용자에게 제시한다. 데이터 파괴 가능성이 있다면 명시적 승인을 받고, `--force`를 제안하거나 자동 사용하지 않는다.

## 실행
안전성 검사를 통과한 linked worktree만 제거한다.

```bash
git -C "$REPO" worktree remove "$TARGET"
```

이 명령이 실패하면 오류를 보고하고 `rm -rf`, `git worktree prune`, `git worktree remove --force`로 우회하지 않는다.

## 사후 검증
- `git -C "$REPO" worktree list --porcelain`에서 해당 경로가 더 이상 등록되지 않았는지 확인한다.
- 원본 primary worktree 및 다른 linked worktree가 유지되는지 확인한다.
- 브랜치는 **삭제하지 않는다**. `git branch -d`조차 별도 사용자 요청·검증이 필요한 독립 작업이다.
- 제거 성공 여부와 유지된 브랜치를 보고한다.

## 금지
Kanban mutation, 임의 branch 삭제, 강제 제거, 수동 재귀 삭제, reset/clean/stash, 다른 worktree에 대한 일괄 정리.
