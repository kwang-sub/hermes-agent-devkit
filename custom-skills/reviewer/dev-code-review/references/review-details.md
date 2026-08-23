# 상세 정책 보존본

이 문서는 compact entrypoint 이전의 `custom-skills/reviewer/dev-code-review/SKILL.md` 전체 내용을 보존한다. compact 문서가 지시하는 상황에 필요한 절만 적용한다. 아래 원본의 YAML frontmatter는 참조 정보이며 중첩 skill 선언이 아니다.

---

---
name: dev-code-review
description: coder가 동일 Workspace에 구현한 미커밋 변경을 승인된 계획과 Acceptance Criteria 기준으로 독립 검토하고, 승인하거나 정확한 수정 요청을 원래 구현자에게 반환한다.
version: 0.1.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, reviewer, kanban, quality, verification]
    related_skills: [dev-implement-plan, dev-review-cycle, dev-workspace-dispatch]
    requires_tools: [terminal, kanban_show, kanban_request_changes, kanban_complete, kanban_block, kanban_heartbeat]
---

# dev-code-review

**reviewer** 프로필이 독립적인 Code Review를 수행한다.

Review는 Coder가 사용한 동일 Kanban Card와 동일 External Workspace에서 진행한다.

Reviewer는 구현 파일을 수정하지 않는다.

---

# 1. 시작 절차

Review Worker로 실행되면:

1. `kanban_show()`를 호출한다.
2. 다음을 읽는다.
   - Original Task Body
   - Implementation Plan
   - Acceptance Criteria
   - Coder의 Review Request Summary/Metadata
   - 이전 Review Attempt/Comment
3. `$HERMES_KANBAN_WORKSPACE`로 이동한다.
4. Review Context를 검증한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/review_context.py" \
  --base-branch "<Base Branch>" \
  --base-sha "<Base SHA>" \
  --expected-branch "<Expected Branch>"
```

Workspace 또는 Branch가 Task와 일치하지 않으면 Block한다.

Expected Branch는 정상 Workflow에서 다음 형식이다.

```text
<Kanban Workspace Contract의 Expected Branch>
```

---

# 2. Review 범위

요청된 구현만 Review하되 Correctness 판단에 필요한 주변 코드는 충분히 확인한다.

비교 순서:

```text
Requirement / Goal
        ↓
Acceptance Criteria
        ↓
Approved Implementation Plan
        ↓
Actual diff + untracked files
        ↓
Verification evidence
```

Style만 검토하고 끝내지 않는다.

---

# 3. Diff 확인

구현은 의도적으로 아직 Commit되지 않은 상태다.

Tracked Change는 dispatch 시점의 Base SHA 기준으로 확인한다. Base Branch/ref가 이후 이동한 경우 `BASE_BRANCH_DRIFTED=true`로 별도 보고하되 비교 기준은 Base SHA에서 이동하지 않는다.

```bash
git diff --no-ext-diff <Base SHA> -- .
```

추가로 확인:

```bash
git status --short --untracked-files=all
git diff --check
git ls-files --others --exclude-standard
```

Untracked Source/Test/Config File도 Review 대상이며 무시하지 않는다.

Workspace를 변경하는 명령은 실행하지 않는다.

---

# 4. Review 우선순위

다음 Severity를 사용한다.

## P0 — Critical

예:

- Data Loss / Corruption
- 심각한 Security Exposure
- 파괴적이며 호환되지 않는 동작
- Requirement를 근본적으로 위반한 구현

P0는 항상 수정 요청이다.

## P1 — Must Fix

예:

- Acceptance Criterion 미충족
- 잘못된 Execution Path
- 의미 있는 Regression
- 필요한 Error/Transaction/Concurrency 처리 누락
- 필수 Test Coverage 누락
- Bug Fix가 Root Cause를 다루지 않음

P1은 수정 요청이다.

## P2 — Non-blocking Improvement

예:

- Maintainability 개선
- 합리적인 추가 Test
- 현재 코드가 올바른 상태에서의 명확한 Naming 개선

P2만 있다면 Note와 함께 승인할 수 있다.

## P3 — Nit

Correctness에 영향을 주지 않는 Formatting/Style Preference.

P3 때문에 승인을 막지 않는다.

---

# 5. Review Checklist

관련 있는 항목만 적용한다.

- Goal 및 Acceptance Criteria 충족
- 승인된 Scope 내 변경
- 기존 Project Pattern 준수
- 관계없는 우발적 변경 없음
- Null/Input Edge Case
- Error Handling
- Transaction Boundary
- Idempotency
- Concurrency
- Backward Compatibility
- Schema/Config Compatibility
- Secret/Security
- Test가 실제 변경 동작을 검증하는지
- 중요한 Failure Path Coverage
- `git diff --check` 통과
- Coder의 Verification Claim과 실제 Evidence 일치

코드 근거가 없는 이론적 문제를 만들어내지 않는다.

---

# 6. Reviewer는 구현하지 않는다

Application/Test/Config Source를 Reviewer가 직접 수정하지 않는다.

"간단하니 바로 고친다"는 방식도 금지한다.

Blocking Finding은 `kanban_request_changes`로 돌려보내 원래 Coder가 수정하도록 한다.

Reviewer가 수행할 수 있는 것은 Read-only Inspection과 Test/Build Command다.

---

# 7. Verdict: CHANGES_REQUESTED

P0 또는 P1 Finding이 하나라도 있으면 `kanban_request_changes`를 호출한다.

Reason은 실행 가능해야 한다.

권장 형식:

```text
CHANGES_REQUESTED

P1
- <file/symbol>: <problem>
  Evidence: ...
  Required change: ...
  Verification expected: ...

P2
- ...
```

다음처럼 모호한 피드백은 보내지 않는다.

```text
needs cleanup
tests insufficient
please improve
```

동일 Card가 원래 Implementer에게 돌아간다.

---

# 8. Verdict: APPROVED

P0/P1이 남아 있지 않고 필요한 Verification이 신뢰할 수 있을 때만 승인한다.

승인은 현재 Git/PR 이전 단계의 최종 Review이므로 `kanban_complete`를 호출한다.

권장 Summary:

```text
APPROVED

Acceptance Criteria: satisfied
Blocking findings: none
Verification reviewed:
- ...
Residual risk:
- ...
```

권장 Metadata:

```json
{
  "phase": "review",
  "review_verdict": "APPROVED",
  "blocking_findings": [],
  "non_blocking_findings": [],
  "verification": [],
  "residual_risk": [],
  "base_sha": "<verified Base SHA>",
  "base_branch_drifted": false
}
```

Approval은 Uncommitted Change가 있는 Workspace를 삭제해도 된다는 뜻이 아니다.

이 Skill은 commit/push하지 않는다.

---

# 9. Review Loop Escalation

`kanban_show()`로 이전 Attempt를 읽는다.

실질적으로 동일한 Blocking Finding이 **3번의 Review Cycle** 동안 남아 있으면 무한 반복하지 않는다.

`kind=needs_input`으로 `kanban_block`을 호출하고 다음을 설명한다.

```text
repeated finding
review rounds attempted
why prior fixes did not resolve it
human decision needed
```

새로운 별개 Finding은 동일 Blocker 반복 횟수로 자동 계산하지 않는다.

---

# 10. BLOCKED

다음처럼 Review 자체를 안전하게 수행할 수 없으면 승인/수정요청 대신 Block한다.

- Workspace가 없거나 잘못됨
- Base Branch를 확인할 수 없음
- Task Contract/Plan이 없음
- Diff를 확립할 수 없음
- 필요한 환경 문제로 Correctness를 판단할 수 없음
- Repository 상태가 일관되지 않음

---

# 11. 성공 기준

Reviewer는 정확히 다음 Terminal Action 중 하나를 수행해야 한다.

```text
kanban_request_changes
or
kanban_complete (APPROVED)
or
kanban_block
```

그리고 Reviewer가 Source를 수정하지 않아야 한다.
