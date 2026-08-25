# dev-implement-plan 상세 구현 규칙

이 문서는 compact entrypoint인 `custom-skills/coder/dev-implement-plan/SKILL.md`의 상세 판단 기준이다. Coder worker는 Kanban Task가 Standard Flow에서 왔는지 Fast Flow에서 왔는지 먼저 확인하고, 공통 구현/검증/Reviewer handoff 계약을 동일하게 적용한다.

---

# 1. 지원 Workflow

## Standard Flow

```text
User / Jira
  ↓
Orchestrator
  ↓
Project Resolve / Breakdown / Approval
  ↓
dev-workspace-dispatch
  ↓
Kanban
  ↓
Coder worker / dev-implement-plan
  ↓
Reviewer
```

Standard Flow Task는 Orchestrator가 승인된 Implementation Plan과 Workspace Contract를 준비한다.

## Fast Flow

```text
User
  ↓
Coder interactive intake / dev-fast-flow
  ↓
Kanban self-dispatch
  ↓
Coder worker / dev-implement-plan
  ↓
Reviewer
```

Fast Flow는 full `dev-breakdown`을 생략하지만 구현 계약을 생략하지 않는다. Kanban Body에 최소한 `Flow: FAST`, Task Key, Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Known Risks, Reviewer Profile, Workspace/Branch/Base SHA가 있어야 한다.

Fast Flow Coder worker는 interactive intake 세션과 별도의 dispatcher-owned worker다. Interactive Coder가 Task를 만든 뒤 직접 source를 수정하지 않는 이유는 Kanban lifecycle, worker ownership, reviewer handoff를 동일한 실행 계약으로 유지하기 위해서다.

---

# 2. Worker 시작 절차

Kanban Worker로 실행되면 다음 순서를 지킨다.

1. `kanban_show()`를 호출한다.
2. Original Task Body, 이전 Attempt, Comment, Review Feedback을 읽는다.
3. `$HERMES_KANBAN_WORKSPACE`로 이동한다.
4. Task의 `Flow`를 확인한다.
5. 파일 수정 전에 Workspace/Branch/Base SHA를 검증한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/verify_workspace.py" \
  --task-key "<Task Key>" \
  --expected-branch "<Expected Branch>" \
  --base-sha "<Base SHA>"
```

Helper 검증 항목:

- 현재 directory가 Git Workspace Root인지
- Kanban Workspace와 실제 Workspace가 일치하는지
- 현재 Branch가 Expected Branch인지
- Base SHA가 full 40-character commit으로 resolve되는지
- Base SHA가 현재 HEAD의 ancestor인지
- 중첩 Workspace에서 실행되지 않는지

검증 실패 시 source를 수정하지 않고 `kanban_block`한다.

---

# 3. 필수 Task 계약

Standard/Fast Flow 모두 다음 정보를 요구한다.

```text
Task Key:
Goal:
Acceptance Criteria:
Implementation Tasks:
Test Plan:
Known Risks:
Expected Branch:
Base Branch:
Base SHA:
Reviewer Profile:
```

Fast Flow는 추가로 다음 marker를 갖는다.

```text
Flow: FAST
```

Standard Flow는 Orchestrator의 approved plan을 scope source로 사용하고, Fast Flow는 Coder intake가 작성한 작은 작업 계약을 scope source로 사용한다.

Goal, Acceptance Criteria, Implementation Tasks, Reviewer Profile 또는 Workspace Contract가 없고 Task History에서도 복구할 수 없으면 임의로 작성하지 않고 Block한다.

---

# 4. Fast Flow 사전 재검증

`Flow: FAST` Task는 실제 source를 수정하기 전에 **Fast Flow가 여전히 안전한지** 확인한다. Intake는 요청만 보고 판단하지만 worker는 실제 코드와 설정을 볼 수 있으므로 두 번째 gate가 필요하다.

다음 중 하나가 실제 evidence에서 확인되면 구현을 확장하지 않는다.

- 요구사항이 둘 이상으로 해석됨
- 제품 정책 또는 사용자 의도가 추가로 필요함
- Architecture 책임 경계를 바꿔야 함
- Public API request/response contract를 바꿔야 함
- DB schema/migration 변경이 필요함
- 여러 Repository를 동시에 변경해야 함
- dependency 추가/upgrade가 필요함
- transaction/concurrency 정책 결정이 필요함
- 예상보다 변경 범위가 크게 확장됨
- clean current-branch 전제가 더 이상 성립하지 않음

이 경우 다음 형식으로 `kanban_block`한다.

```text
FAST_FLOW_ESCALATION_REQUIRED

Evidence:
- <file/symbol/config/test에서 확인한 사실>

Why Fast Flow is no longer safe:
- <scope/design/compatibility 이유>

Standard Flow decision needed:
- <Orchestrator가 분석/승인해야 할 항목>
```

Fast Flow escalation은 실패가 아니라 올바른 routing 결과다. Coder가 속도를 위해 임의로 architecture/API/schema 결정을 내려서는 안 된다.

---

# 5. 최초 구현과 Review 재작업

## 최초 구현

수정 전 다음을 확인한다.

```bash
git status --short --untracked-files=all
git branch --show-current
```

Task 계약 주변의 실제 source, 호출 흐름, config, tests, 기존 pattern을 읽는다. 계약은 scope를 고정하지만 실제 코드 증거를 무시하라는 의미가 아니다.

구현은 요구사항을 만족하는 **가장 작은 변경**을 우선한다.

다음은 요청 범위에 직접 필요하지 않으면 섞지 않는다.

- Rename
- 대규모 Formatting
- Dependency Upgrade
- Architecture Rewrite
- Legacy Cleanup
- API/Schema 변경
- unrelated test cleanup

## `CHANGES_REQUESTED` 이후 재작업

`kanban_show()`의 Review Feedback을 기준으로:

- 이미 올바른 구현은 유지한다.
- P0/P1 blocking finding만 정확히 처리한다.
- 처음부터 다시 구현하지 않는다.
- Scope를 관계없는 cleanup으로 넓히지 않는다.
- 영향받은 검증을 다시 실행한다.
- 다음 review handoff에 어떤 finding을 처리했는지 기록한다.

Fast Flow가 review 중 더 큰 설계 문제로 드러났다면 동일하게 `FAST_FLOW_ESCALATION_REQUIRED`로 Block할 수 있다.

---

# 6. 정확성 확인

관련 있는 항목만 적용한다.

- Nullability
- Input Validation
- Failure Path
- Error Propagation
- Idempotency
- Retry / Duplicate execution
- Transaction Scope
- Concurrency / Race Condition
- Backward Compatibility
- Configuration Default
- Data / Schema Compatibility
- Security / Secret
- Logging / Observability
- Rollback / Failure Behavior

단순 Fast Flow 작업에 필요하지 않은 추측성 방어 로직이나 새 abstraction을 추가하지 않는다.

---

# 7. 검증

가장 좁고 직접적인 검증부터 실행하고 필요할 때만 범위를 넓힌다.

권장 순서:

```text
targeted unit test
→ targeted integration test
→ module test/build
→ lint/static analysis
→ git diff --check
```

Repository/Tooling상 불가능하지 않은 한 Reviewer handoff 전에 다음을 실행한다.

```bash
git diff --check
```

그리고 변경 증거를 수집한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/change_summary.py"
```

확인 항목:

- Branch
- Tracked Changed Files
- Untracked Files
- Git Status
- Diff Check Result

실제로 성공한 command만 PASS라고 보고한다. 실행하지 못한 검증은 이유와 residual risk를 명시한다.

필수 검증 없이는 correctness를 판단할 수 없다면 Reviewer에게 넘기지 않고 Block한다.

---

# 8. Git Publication 금지

Coder implementation 단계에서는 다음을 수행하지 않는다.

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

Workspace cleanup도 하지 않는다.

기존 사용자 변경을 자동으로 정리하거나 숨기지 않는다. Publication은 별도 workflow 단계다.

---

# 9. Reviewer Handoff

구현과 검증이 준비되면 `kanban_complete`를 호출하지 않는다.

동일 Kanban Card에서 configured `Reviewer Profile`에게 `kanban_request_review`를 호출한다.

권장 summary:

```text
Implemented: <Goal 요약>

Changed:
- <file/symbol>

Verification:
- <exact command> → PASS

Residual risk:
- none / <risk>

Review feedback addressed:
- <retry인 경우 finding>
```

권장 metadata:

```json
{
  "phase": "implementation",
  "flow": "FAST | STANDARD",
  "review_verdict": null,
  "changed_files": ["..."],
  "verification": ["<command> -> PASS"],
  "residual_risk": [],
  "review_feedback_addressed": [],
  "base_sha": "<verified Base SHA>"
}
```

Metadata와 summary에는 Secret, raw credential, 실제 password/token/config secret value를 넣지 않는다.

`kanban_request_review` 호출 후 Coder worker는 멈춘다.

---

# 10. BLOCKED 처리

다음 경우 `kanban_block`을 사용한다.

- Task 계약이 불충분함
- Workspace/Branch/Base SHA 검증 실패
- requirement와 실제 코드가 충돌하며 사용자/설계 결정 필요
- 필수 dependency/input 누락
- 안전한 구현을 완료할 수 없음
- 필수 검증으로 correctness를 확립할 수 없음
- Fast Flow가 실제 evidence상 더 이상 작은 작업이 아님

일반 Block summary:

```text
What is blocked:
Evidence:
Decision/input needed:
Current change state:
Resume condition:
```

Fast Flow scope escalation이면 첫 줄에 반드시 다음 reason을 사용한다.

```text
FAST_FLOW_ESCALATION_REQUIRED
```

Review가 필요하다는 이유로 Block하지 않는다. 정상 review handoff에는 `kanban_request_review`를 사용한다.

---

# 11. 성공 기준

Coder implementation 단계의 성공 조건:

- Kanban Task와 Workspace가 일치함
- Expected Branch가 실제 Branch와 일치함
- Base SHA가 검증됨
- Fast Flow라면 scope 재검증을 통과함
- Task 계약 범위만 구현함
- unrelated diff가 없음
- 관련 테스트/check가 수행됨
- changed/untracked files가 보고됨
- residual risk가 명시됨
- commit/push/PR/merge를 수행하지 않음
- 동일 Task를 `kanban_request_review`로 configured reviewer에게 넘김

Reviewer 승인 전에는 전체 개발 Workflow가 완료된 것이 아니다.
