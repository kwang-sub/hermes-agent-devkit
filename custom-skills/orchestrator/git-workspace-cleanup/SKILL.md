---
name: git-workspace-cleanup
description: Git worktree 목록을 보여주고 선택한 linked worktree와 안전하게 증명된 작업 브랜치를 Preview/승인 후 정리한다.
version: 0.4.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [git, workspace, worktree, cleanup, branch, pull-request, github, approval]
    related_skills: [git-pr-publish, dev-workspace-dispatch]
    requires_tools: [terminal, clarify]
---

# git-workspace-cleanup

PR/branch 작업이 끝난 linked Git worktree를 목록에서 선택하고, clean/merge 상태와 삭제될 branch 이름을 확인한 뒤 사용자가 승인한 범위만 정리한다.

```text
PR merge 완료
→ /git-workspace-cleanup
→ linked worktree 목록
→ [Worktree 선택]
→ read-only preflight
→ [Worktree 정리 Preview]
→ 삭제 예정 branch 이름 명시
→ [Worktree 정리 승인]
→ 승인 범위만 cleanup
```

## 독립 실행 원칙

- 명시적 Task id 또는 `HERMES_KANBAN_TASK`가 없으면 Kanban 조회를 호출하지 않는다.
- helper `STATUS=blocked` 뒤 unrelated remediation을 하지 않는다.
- `git config --global safe.directory` 자동 변경 금지. helper process-local 설정만 사용한다.
- 한 실행에서 linked worktree 하나만 정리한다.

## 목록 / 선택

```bash
python3 "${HERMES_SKILL_DIR}/scripts/list_worktrees.py" --repo "<REPO>" --remote "<REMOTE>"
```

Primary worktree는 표시만 하고 선택하지 않는다. Path, Branch, HEAD, `CLEAN | EOL_ONLY | DIRTY`, remote 존재 여부, cleanup hint를 보여준 뒤 `[Worktree 선택]` clarify Gate에서 하나를 선택한다.

## 공통 안전 조건

선택 대상은 primary가 아닌 linked worktree, non-detached, 정확히 등록된 worktree, unlocked/non-prunable이어야 한다. 일반적으로 `CLEAN`이어야 하며, `EOL_ONLY`는 아래의 좁은 예외 계약으로만 허용한다. semantic modified/staged/untracked 변경이 하나라도 있으면 force/reset/restore/stash/clean으로 우회하지 않고 BLOCK한다.

## EOL-only Noise 예외

Windows/WSL/Container 경계에서 tracked UTF-8 text 파일이 LF↔CRLF 차이만으로 Git `DIRTY`처럼 보일 수 있다. 이 경우 실제 사용자 변경과 줄바꿈 노이즈를 구분한다.

판정 기준:

```text
status == unstaged tracked modify (" M")
index blob != worktree bytes
index/worktree 둘 다 UTF-8 text
CRLF→LF 정규화 후 bytes 완전 동일
→ EOL_ONLY
```

다음은 EOL-only가 아니다.

```text
staged change
untracked file
rename/copy/delete
binary/non-UTF8
trailing-space/content 변경
CRLF/LF 외 내용 차이
```

Preflight evidence:

```text
WORKTREE_SEMANTIC_DIRTY=false
WORKTREE_EOL_NOISE_ONLY=true
EOL_ONLY_COUNT=<N>
EOL_ONLY_FILE=<path>
EOL_ONLY_FORCE_REMOVE_ALLOWED=true
```

`EOL_ONLY`이면 파일을 reset/restore/normalize하지 않는다. Git 자체의 `git worktree remove`가 dirty worktree를 거부하므로, **preflight와 mutation 시점의 fingerprint 재검증이 모두 통과하고 semantic dirty가 0인 경우에만** `git worktree remove --force`를 허용한다.

이 scoped force 예외는 worktree directory 제거에만 적용된다. branch 삭제는 기존 exact SHA `git update-ref -d` 계약을 그대로 사용하며 force branch 삭제/force push는 계속 금지한다.

## 현재 Feature Branch Worktree

`current branch != base branch`이면 기존 feature cleanup 경로다. 같은 branch가 다른 worktree에서 사용되지 않고, local/remote HEAD가 일치하며, open PR이 없고 다음 중 하나의 merge evidence가 있어야 한다.

```text
GitHub merged PR + exact PR head SHA
또는
git merge-base --is-ancestor <branch-head> <base-ref>
```

```text
CLEANUP_SCOPE=worktree-and-branch
BRANCH_CLEANUP_ALLOWED=true
```

Preview에 삭제될 current feature branch 이름을 정확히 표시한다.

## Base Branch로 전환된 Worktree의 이전 작업 Branch 추적

`current branch == resolved base branch`이면 `dev/main` 자체는 절대 삭제하지 않는다. 대신 선택 worktree의 **HEAD reflog**에서 최신 `checkout: moving from <source> to <base>` 전환을 읽어 이전 작업 branch 후보를 찾는다.

Worktree 디렉터리명과 branch 이름 유사성만으로 추측하지 않는다.

추적 branch를 삭제 후보로 올리려면 모두 충족해야 한다.

```text
1. refs/heads/<tracked branch> 실제 존재
2. tracked branch != base branch
3. 다른 worktree에서 checkout 중이지 않음
4. GitHub remote라면 인증된 상태에서 open PR 없음 확인
5. merged PR exact head SHA 또는 base ancestry로 merge 증명
6. remote 삭제 선택지를 제공하려면 remote SHA == tracked local SHA
```

안전하면:

```text
CLEANUP_SCOPE=worktree-and-tracked-branch
TRACKED_BRANCH_CLEANUP_ALLOWED=true
```

증명되지 않으면:

```text
CLEANUP_SCOPE=worktree-only
TRACKED_BRANCH_CLEANUP_ALLOWED=false
```

이때는 worktree만 제거하고 branch는 모두 보존한다.

## Preflight

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_cleanup.py" \
  --workspace "<SELECTED_WORKTREE>" \
  --remote "<REMOTE>" \
  [--base-branch "<BASE_BRANCH>"]
```

Base worktree에서 이전 branch를 추적하면 다음을 포함해 반환한다.

```text
CLEANUP_SCOPE
TRACKED_PREVIOUS_BRANCH
TRACKED_PREVIOUS_HEAD_SHA
TRACKED_PREVIOUS_MERGE_EVIDENCE
TRACKED_PREVIOUS_PR_URL
TRACKED_PREVIOUS_REMOTE_EXISTS
TRACKED_PREVIOUS_REMOTE_SHA
TRACKED_PREVIOUS_REMOTE_DELETE_AVAILABLE
TRACKED_PREVIOUS_REASON
TRACKED_REFLOG_MESSAGE
CLEANUP_FINGERPRINT
```

Fingerprint에는 worktree/HEAD/base/status/remote/PR/추적 branch/reflog evidence를 포함한다. EOL-only 상태도 fingerprint에 포함되며 mutation helper가 동일 판정을 다시 수행한다. 승인 뒤 semantic 상태나 EOL-only 상태가 바뀌면 Preview/Gate를 다시 수행한다.

## Preview

삭제 branch가 있으면 **정확한 이름을 삭제 전에 반드시 사용자에게 보여준다.**

```text
[Worktree 정리 Preview]
Worktree: /workspace/.worktrees/chagok/ui-dashboard-investment
Current Branch: dev
Base: dev
Cleanup Scope: worktree-and-tracked-branch
Merge Evidence: base-branch-worktree

Tracked Previous Branch: feature/ui-dashboard-investment
Tracked HEAD: <sha>
Tracked Merge Evidence: git-ancestor
Remote Branch: origin/feature/ui-dashboard-investment <exists | already absent>

삭제 예정:
- Worktree: ui-dashboard-investment
- Local Branch: feature/ui-dashboard-investment
- Remote Branch: origin/feature/ui-dashboard-investment <승인 시 삭제 | 이미 없음 | 보존>

보존:
- local dev
- origin/dev
```

추적 후보가 안전하지 않으면 `TRACKED_PREVIOUS_REASON`을 설명하고 삭제 대상으로 표시하지 않는다.

## 승인 Gate

현재 feature branch:

```text
[Worktree 정리 승인]
삭제 Branch: <feature branch>
- Worktree + 로컬/원격 Branch 정리
- Worktree + 로컬 Branch만 정리
- 취소
```

Base worktree + 안전한 tracked branch:

```text
[Worktree 정리 승인]
삭제 Branch: <tracked previous branch>
- Worktree + 추적 로컬/원격 Branch 정리
- Worktree + 추적 로컬 Branch만 정리
- Worktree만 정리
- 취소
```

삭제 가능한 tracked branch가 없으면 `Worktree만 정리 / 취소`만 제공한다.

## Mutation

현재 feature branch cleanup:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/cleanup_workspace.py" \
  --workspace "<SELECTED_WORKTREE>" --remote "<REMOTE>" \
  --base-branch "<BASE_BRANCH>" --fingerprint "<CLEANUP_FINGERPRINT>" \
  [--delete-remote]
```

Base worktree에서 추적 local branch 삭제 승인:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/cleanup_workspace.py" \
  --workspace "<SELECTED_WORKTREE>" --remote "<REMOTE>" \
  --base-branch "<BASE_BRANCH>" --fingerprint "<CLEANUP_FINGERPRINT>" \
  --delete-tracked-branch
```

추적 local + remote 삭제 승인 시 `--delete-tracked-branch --delete-remote`를 함께 전달한다.

Base branch local/remote는 항상 보존한다. local feature/tracked branch 삭제는 승인된 exact SHA를 old SHA로 지정한 `git update-ref -d`만 사용한다. remote 삭제 직전 `git ls-remote` SHA를 다시 확인한다.

## Partial Failure

- worktree remove 실패: branch refs 건드리지 않고 BLOCK
- worktree 제거 후 local ref 실패: partial + 남은 branch명 보고
- local cleanup 후 remote SHA 변경/삭제 실패: partial + remote 보존
- 자동 rollback/force 재시도 없음

## 절대 금지

```text
git worktree remove --force  # 단, 검증된 EOL_ONLY + fingerprint 일치의 scoped exception만 허용
git branch -D
git push --force
git push --force-with-lease
git reset
git restore
git clean
git stash
rm -rf
primary worktree 삭제
open PR branch 삭제
merge evidence 없는 branch 삭제
base branch local/remote 삭제
Preview에 이름을 표시하지 않은 branch 삭제
git config --global safe.directory 자동 변경
```

## 역할 분리

```text
git-pr-publish: commit + push + PR create
git-workspace-cleanup: merge 후 worktree/승인된 branch cleanup
```

## 회귀 검증

```bash
python3 custom-skills/orchestrator/git-workspace-cleanup/tests/test_workspace_cleanup.py
python3 scripts/check_workspace_cleanup_contract.py
python3 scripts/check_skill_contract.py
python3 scripts/check_update_devkit_contract.py
```
