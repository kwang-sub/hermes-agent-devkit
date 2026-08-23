# 상세 정책 보존본

이 문서는 compact entrypoint 이전의 `custom-skills/coder/dev-implement-plan/SKILL.md` 전체 내용을 보존한다. compact 문서가 지시하는 상황에 필요한 절만 적용한다. 아래 원본의 YAML frontmatter는 참조 정보이며 중첩 skill 선언이 아니다.

---

---
name: dev-implement-plan
description: 사용자 승인된 dev-breakdown 계획을 할당된 승인된 Git Workspace에서 구현·검증하고, commit/push 없이 동일 Kanban 카드를 설정된 reviewer에게 전달한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review]
    related_skills: [dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_block, kanban_heartbeat]
---

# dev-implement-plan

**coder** 프로필이 Dispatch 완료된 Implementation Plan을 실제 코드로 구현한다.

이 Skill은 구현 전용이며 `dev-workspace-dispatch`가 이미 준비한 승인된 Git Workspace에서만 작업한다.

표준 흐름:

```text
dev-workspace-dispatch
        ↓
Kanban task를 coder가 claim
        ↓
dev-implement-plan
        ↓
구현 + 검증
        ↓
kanban_request_review
        ↓
reviewer
```

이 단계에서는 commit, push, merge, Workspace cleanup을 하지 않는다.

---

# 1. Worker 시작 절차

Kanban Worker로 실행되면 다음 순서를 지킨다.

1. 먼저 `kanban_show()`를 호출한다.
2. Task Body, 이전 Attempt, Comment, Review Feedback을 모두 읽는다.
3. `$HERMES_KANBAN_WORKSPACE`로 이동한다.
4. 파일 수정 전에 Workspace와 Branch를 검증한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/verify_workspace.py" \
  --task-key "<Task Key>" \
  --expected-branch "<Expected Branch>" \
  --base-sha "<Base SHA>"
```

Helper 검증 항목:

- 현재 디렉터리가 Git Workspace Root인지
- Kanban에 승인된 Workspace인지
- Workspace가 Git repository root인지
- 현재 Branch가 Task의 Expected Branch와 일치하는지
- dispatch Base SHA가 full commit SHA로 resolve되는지
- dispatch Base SHA가 현재 HEAD의 ancestor인지 (`git merge-base --is-ancestor`)
- 중첩 Workspace를 만들지 않았는지

검증 실패 시 파일을 수정하지 말고 `kanban_block`을 호출한다.

---

# 2. 필수 Task 계약

Kanban Body에는 다음 정보가 있어야 한다.

```text
Task Key:
...

Goal:
...

Acceptance Criteria:
...

Implementation Tasks:
...

Test Plan:
...

Known Risks:
...

Expected Branch:
<Kanban Workspace Contract의 Expected Branch>

Base Branch:
...

Base SHA:
...

Reviewer Profile:
reviewer
```

Goal, Acceptance Criteria, Implementation Tasks, Reviewer Profile이 없고 Task History에서도 복구할 수 없다면 임의로 만들지 말고 Block한다.

현재 Branch가 Kanban Workspace Contract의 Expected Branch와 다르거나 Base SHA 검증이 실패하면 작업을 시작하지 않는다.

---

# 3. 최초 구현과 Review 재작업 구분

## 최초 구현

승인된 Breakdown을 따른다.

수정 전 확인:

```bash
git status --short
git branch --show-current
```

계획된 변경 주변의 실제 코드를 확인한다. 승인된 Plan은 Scope 계약이지만 실제 코드 증거를 무시해도 된다는 의미는 아니다.

## `CHANGES_REQUESTED` 이후 재작업

`kanban_show()`에 이전 Attempt와 Review Feedback이 포함된다.

재작업 시:

- 이미 올바른 구현은 유지한다.
- Reviewer의 Blocking Finding을 수정한다.
- 이유 없이 처음부터 다시 구현하지 않는다.
- 관계없는 Cleanup으로 Scope를 확장하지 않는다.
- 영향받은 검증을 다시 실행한다.
- 다음 Review Handoff에 어떤 Finding을 처리했는지 기록한다.

---

# 4. 구현 원칙

승인된 Plan을 만족하는 **가장 작은 변경**을 우선한다.

새 Framework나 추측성 추상화보다 다음 기존 패턴을 우선한다.

```text
existing project conventions
existing abstractions
existing error model
existing transaction boundaries
existing test style
```

다음의 관계없는 변경은 하지 않는다.

- Rename
- 대규모 Formatting
- Dependency Upgrade
- Architecture Rewrite
- Legacy Cleanup
- Plan에 없는 API/Schema 변경

실제 코드 증거가 승인된 Plan과 충돌해 제품/설계 결정이 필요해지면 임의로 다른 구현을 선택하지 말고 정확한 불일치 근거와 함께 Block한다.

---

# 5. 정확성 확인

관련 있는 경우 다음을 검토한다.

- Nullability
- Input Validation
- Idempotency
- Transaction Scope
- Concurrency / Race Condition
- Error Propagation
- Backward Compatibility
- Configuration Default
- Data / Schema Compatibility
- Security / Secret
- Observable Logging
- Rollback / Failure Behavior

프로젝트에 필요하지 않은 과도한 방어 로직은 추가하지 않는다.

---

# 6. 검증

가장 좁고 직접적인 검증부터 실행하고, 필요할 때만 범위를 넓힌다.

예:

```text
targeted unit test
targeted integration test
module test
build/compile
lint/static analysis
git diff --check
```

Repository/Tooling상 불가능하지 않은 한 항상 다음을 실행한다.

```bash
git diff --check
```

Reviewer에게 넘기기 전 변경 증거를 수집한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/change_summary.py"
```

출력 항목:

- Branch
- Tracked Changed Files
- Untracked Files
- Git Status
- Diff Check Result

실제로 성공한 명령만 PASS라고 보고한다.

환경/Dependency 문제로 필수 테스트를 실행할 수 없으면 Residual Risk에 명시한다. 해당 테스트 없이는 Correctness를 판단할 수 없다면 Review로 넘기지 말고 Block한다.

---

# 7. Git Publication 금지

이 단계는 Git Publication 이전에서 끝난다.

다음 명령은 실행하지 않는다.

```text
git commit
git push
git merge
git rebase
git cherry-pick
git reset
git clean
git stash
```

Workspace도 제거하지 않는다.

Git/PR 연동은 이후 별도 Workflow 단계다.

---

# 8. Reviewer Handoff

구현이 준비되면 `kanban_complete`를 호출하지 않는다.

동일 Kanban Card에서 `kanban_request_review`를 호출한다.

Reviewer는 Task Body의 `Reviewer Profile` 값을 사용한다.

권장 Handoff:

```text
summary:
Implemented <goal>.
Changed:
- ...
Verification:
- <exact command> → PASS
Residual risk:
- none / ...
Review feedback addressed:
- ... (retry only)
```

권장 Metadata:

```json
{
  "phase": "implementation",
  "review_verdict": null,
  "changed_files": ["..."],
  "verification": ["<command> -> PASS"],
  "residual_risk": [],
  "review_feedback_addressed": [],
  "base_sha": "<verified Base SHA>"
}
```

Metadata에는 Secret이나 Raw Credential/Config Value를 넣지 않는다.

`kanban_request_review` 호출 후 작업을 멈춘다. 다음 실행은 Reviewer 소유다.

---

# 9. BLOCKED 처리

다음 경우 `kanban_block`을 호출한다.

- Task 계약이 불충분함
- Workspace/Branch 검증 실패
- Requirement와 실제 코드가 충돌하며 결정이 필요함
- 필수 Dependency/Input 누락
- 안전한 구현을 완료할 수 없음
- 필수 검증으로 Correctness를 확립할 수 없음

Block Reason에는 간결하게 다음을 포함한다.

```text
what is blocked
evidence
what decision/input is needed
what has already been changed, if anything
```

Review가 필요하다는 이유로 Block하지 않는다. Review는 `kanban_request_review`를 사용한다.

---

# 10. 성공 기준

다음을 모두 만족해야 구현 단계가 성공이다.

- 할당된 Git Workspace가 올바름
- Branch가 Kanban Workspace Contract의 Expected Branch와 일치함
- 승인된 Scope만 구현함
- 관계없는 변경이 없음
- 관련 Test/Check를 실행함
- Changed/Untracked File을 보고함
- Residual Risk를 명시함
- commit/push하지 않음
- 동일 Task를 `kanban_request_review`로 설정된 Reviewer에게 넘김
