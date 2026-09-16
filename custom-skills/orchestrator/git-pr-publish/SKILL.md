---
name: git-pr-publish
description: 완료된 별도 Git branch/worktree의 변경을 사용자 승인 기반으로 commit+push하고 PR preview 재승인 후 GitHub PR을 생성한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [git, commit, push, pull-request, github, worktree, branch, publish, approval]
    related_skills: [dev-workspace-dispatch, dev-review-cycle, dev-workflow-orchestrate, git-workspace-cleanup]
    requires_tools: [terminal, clarify, kanban_show]
---

# git-pr-publish

완료된 구현을 사용자가 확인한 내용만 Git 원격에 게시하는 post-review Skill이다. source 수정, review, PR approve/merge, branch/worktree cleanup은 수행하지 않는다.

표준 흐름:

```text
DONE / Reviewer APPROVED / Fast LOW 완료
→ read-only publish preflight
→ [커밋 Preview]
→ [커밋 승인]
→ commit + normal push
→ [PR Preview]
→ [PR 생성 승인]
→ PR 생성
→ PR URL 출력
→ STOP
→ 사용자가 GitHub에서 직접 review/merge
```

## 독립 실행 / Kanban

- 명시적 Task id 또는 `HERMES_KANBAN_TASK`가 있을 때만 Kanban Task 상태를 read-only 확인한다.
- Task context가 없어도 동작해야 한다.
- helper가 `STATUS=blocked`를 반환하면 원인을 보고하고 임의의 Git 전역 설정 변경 같은 unrelated remediation을 수행하지 않는다.

## Base Branch 결정

Base Branch는 추측하지 않는다.

```text
1. Kanban Task body의 Base branch
2. 사용자가 명시한 base branch
3. refs/remotes/<remote>/HEAD가 명확할 때 해당 branch
4. 그래도 불명확하면 clarify
```

`main`, `master`, `dev`를 임의 선택하지 않는다.

## Commit preflight / 승인

먼저 read-only helper를 실행한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_publish.py" \
  --workspace "<WORKSPACE>" \
  --remote "<REMOTE>" \
  [--base-branch "<BASE_BRANCH>"]
```

파일 목록, diff stat, branch/base, remote, `PUBLISH_FINGERPRINT`와 Conventional Commit 메시지를 `[커밋 Preview]`로 먼저 보여준다.

```text
[커밋 승인]
- 커밋 및 Push 승인
- 커밋 메시지 수정
- 취소
```

`커밋 및 Push 승인`만 mutation 승인이다. 승인 전 `git add`, `git commit`, `git push`는 금지한다. 승인 후 다음 helper를 정확히 한 번 실행한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/publish_commit.py" \
  --workspace "<WORKSPACE>" \
  --remote "<REMOTE>" \
  --branch "<BRANCH>" \
  --fingerprint "<PUBLISH_FINGERPRINT>" \
  --message "<COMMIT_MESSAGE>"
```

Commit message는 `feat: 한국어 설명`, `fix: 한국어 설명` 같은 Conventional Commits 형식을 사용한다. 정상 push만 허용하며 force/force-with-lease/reset/restore/clean/stash은 금지한다.

## PR preflight / 승인

Push 성공 후 바로 PR을 생성하지 않는다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_pr.py" \
  --workspace "<WORKSPACE>" \
  --remote "<REMOTE>" \
  --base "<BASE_BRANCH>" \
  --head "<BRANCH>"
```

동일 base/head open PR이 있으면 기존 URL을 보여주고 STOP한다. 신규 PR이면 한국어 title/body를 `[PR Preview]`로 보여준다. 내부 model/provider/session/OAuth 정보는 PR body에 넣지 않는다.

```text
[PR 생성 승인]
- PR 생성
- PR 내용 수정
- 취소
```

`PR 생성`만 실제 생성 승인이다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/create_pr.py" \
  --workspace "<WORKSPACE>" \
  --remote "<REMOTE>" \
  --base "<BASE_BRANCH>" \
  --head "<BRANCH>" \
  --title "<PR_TITLE>" \
  --body "<PR_BODY>"
```

성공 후 PR URL을 출력하고 STOP한다. 최종 merge는 사용자가 GitHub에서 직접 수행한다.

## 승인 무효화

Commit 승인 뒤 changed files/content/staged 상태/branch/HEAD/scope가 바뀌면 fingerprint가 달라져 다시 승인받는다. Push 후 remote head/base/title/body/open PR 상태가 바뀌면 PR Preview와 승인을 다시 만든다.

## Worktree 공통 처리

linked worktree 여부와 상관없이 Git repository root/current branch를 기준으로 처리한다. PR identity는 `remote + head branch + base branch`다.

## 절대 금지

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

## 회귀 검증

```bash
python3 custom-skills/orchestrator/git-pr-publish/tests/test_pr_publish.py
python3 scripts/check_skill_contract.py
python3 scripts/check_update_devkit_contract.py
python3 scripts/check_git_publish_bootstrap_contract.py
```
