---
name: git-pr-publish
description: Hermes Lite에서 검증한 Git 변경사항을 사용자 승인에 따라 커밋·푸시하고 PR을 미리 보여준 뒤 생성한다.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [git, lite, commit, push, pull-request, github, worktree, approval]
    related_skills: [dev-lite-review, dev-worktree-create, dev-worktree-remove]
    requires_tools: [terminal]
---

# Lite Git PR 게시

사용자가 명시적으로 Git 게시를 요청할 때만 수행한다. Orchestrator, Kanban Task, Reviewer 승인 또는 worker context를 요구하지 않는다. 기존 Git helper의 fingerprint/EOL-only 안전 계약을 재사용한다. Git publish는 source 수정, merge, branch/worktree 삭제를 하지 않는다.

## 실행 순서
1. 현재 Git repository와 현재 branch, remote, 사용자가 지정한 base branch를 확인한다. 지정이 없고 remote HEAD가 명확할 때만 사용하며, 불명확하면 사용자에게 확인한다. main/master/dev를 추측하지 않는다.
2. 현재 세션의 테스트 결과 및 미완료 위험을 사용자에게 알린다. 검증했다고 주장할 근거가 없으면 그대로 표시한다.
3. read-only preflight:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_publish.py" --workspace "<WORKSPACE>" --remote "<REMOTE>" [--base-branch "<BASE_BRANCH>"]
```

4. semantic changes가 있으면 파일 목록·diff stat·fingerprint·Conventional Commit 메시지를 먼저 보여주고 **커밋+푸시**의 명시적 승인을 받은 후 실행한다:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/publish_commit.py" --workspace "<WORKSPACE>" --remote "<REMOTE>" --branch "<BRANCH>" --fingerprint "<PUBLISH_FINGERPRINT>" --message "<COMMIT_MESSAGE>"
```

5. semantic changes가 없고 기존 HEAD가 원격에 있으면 커밋·푸시를 생략한다. 기존 HEAD를 원격에 새로 게시해야 한다면 branch/HEAD/remote 상태를 미리 보여주고 **푸시**를 별도 승인받는다:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/push_existing.py" --workspace "<WORKSPACE>" --remote "<REMOTE>" --branch "<BRANCH>" --expected-head "<HEAD_SHA>"
```

6. 푸시 이후 PR 사전 검사를 수행한다:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_pr.py" --workspace "<WORKSPACE>" --remote "<REMOTE>" --base "<BASE_BRANCH>" --head "<BRANCH>"
```

7. 동일 base/head의 열린 PR이 있으면 URL을 반환하고 생성하지 않는다. 없으면 PR 제목/본문을 미리 보여주고 **PR 생성**을 별도 승인받은 다음 실행한다:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/create_pr.py" --workspace "<WORKSPACE>" --remote "<REMOTE>" --base "<BASE_BRANCH>" --head "<BRANCH>" --title "<PR_TITLE>" --body "<PR_BODY>"
```

## 불변식
- EOL-only 변경은 UTF-8 tracked file의 index/worktree bytes가 CRLF→LF 정규화에서만 일치하는 경우다. 의미 있는 파일 내용 변경과 구분하며 줄바꿈 변환을 위해 reset/restore/stash/clean하지 않는다.
- helper가 `STATUS=blocked`면 unrelated remediation 없이 원인과 미게시 상태를 보고한다. 실행 전후 fingerprint/HEAD/remote가 달라지면 기존 승인을 폐기하고 다시 확인한다.
- force push, detached/기본 branch 임의 게시, source 수정, PR approve/merge, 자동 Worktree·branch 정리는 하지 않는다.
- 기존 Kanban 정보는 사용자가 요청할 때만 참고한다. Git 게시 여부는 Kanban 상태와 독립이다.

## 검증
```bash
python3 custom-skills/lite/git-pr-publish/tests/test_pr_publish.py
```
