---
name: dev-worktree-create
description: Hermes DevKit에서 Kanban·Orchestrator 없이 안전하게 Git linked worktree를 생성한다.
version: 0.1.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, core, git, worktree, workspace]
    requires_tools: [terminal]
---

# DevKit Git worktree 생성

사용자가 분리된 작업 공간을 요청한 경우에만 실행한다. Standard의 `dev-workspace-dispatch` 또는 Kanban 카드/프로젝트 메타데이터를 요구하지 않는다. 기존 Git 저장소의 정책은 존중한다.

## 사전 확인
1. 프로젝트 경로를 확정하고 `git -C "$REPO" rev-parse --show-toplevel`, `git -C "$REPO" rev-parse --git-common-dir`, `git -C "$REPO" worktree list --porcelain`로 Git 저장소 및 기존 worktree를 확인한다. Non-Git 디렉터리라면 중단한다.
2. 사용자 요청의 대상 브랜치, 기준 ref, 새 worktree 경로를 구분한다. 명시되지 않은 값은 제안하고 경로·브랜치 충돌을 검사한다. 현재 repo 내부를 경로로 사용하지 않으며 기존 디렉터리를 덮어쓰지 않는다.
3. 기존 수정 사항을 절대로 `reset`, `restore`, `clean`, `stash`하지 않는다. 기존 worktree의 dirty 여부는 새 worktree 생성을 자동 차단하지 않지만 해당 변경이 새 공간으로 복제된다고 설명하지 않는다.
4. 생성 대상 경로가 존재하면 거부한다. 브랜치가 다른 worktree에서 checkout 중이면 거부한다. 기존 브랜치와 새 브랜치를 구분한다. 기본 브랜치 이름을 임의로 재설정하지 않는다.
5. Windows bind mount의 경로는 Git 실행 환경(Linux 컨테이너)의 실제 경로로 변환하고 그 경로에 쓰기 권한이 있는지 확인한다.

## 실행
기존 로컬 브랜치를 사용할 때:

```bash
git -C "$REPO" worktree add "$TARGET" "$BRANCH"
```

새 브랜치를 명시적으로 생성할 때:

```bash
git -C "$REPO" worktree add -b "$BRANCH" "$TARGET" "$BASE_REF"
```

`--force`, `--detach`, `--guess-remote`, `-B`는 자동 사용하지 않는다. 사용자 승인 없이 원격 push를 하지 않는다.

## 사후 검증
- `git -C "$REPO" worktree list --porcelain`에서 대상 경로가 하나만 등록되었는지 확인한다.
- `git -C "$TARGET" rev-parse --show-toplevel`, `git -C "$TARGET" branch --show-current`, `git -C "$TARGET" status --short`를 확인한다.
- 생성 경로, 브랜치, HEAD SHA, 작업 시작 명령을 출력한다.
- 생성 실패 시 기존 경로 또는 브랜치를 자동 제거하지 않는다. 실패 상태를 보고한다.

## 금지
Kanban 생성·수정, worker dispatch, 기존 작업 공간 변경 삭제, 자동 checkout/reset/stash/clean, 자동 commit/push/merge, 다른 저장소의 worktree 조작.
