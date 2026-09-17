# dev-implement-plan 상세 구현 규칙

이 문서는 compact entrypoint인 `custom-skills/coder/dev-implement-plan/SKILL.md`에서 **필요할 때만 읽는 상세 규칙**이다. 기본 작업은 SKILL.md 계약만으로 처리하고, Direct scope escalation, retry/BLOCKED 판단, verification failure classification처럼 세부 기준이 필요할 때만 해당 절을 읽는다.

## 1. Workflow

새 mutation request의 실행 방식은 Orchestrator가 결정한다. Coder는 이미 Kanban으로 dispatch된 `Direct Flow | Standard Flow` Task만 수행한다.

```text
Direct:   Orchestrator → compact approval → Kanban → Coder → Reviewer
Standard: Orchestrator → breakdown/approval → Kanban → Coder → Reviewer
```

두 Flow 모두 Coder self-complete는 허용하지 않는다. `CHANGES_REQUESTED` 재작업도 반드시 다시 Reviewer에게 넘긴다.

## 2. Worker 시작

1. `kanban_show()`로 body/history/feedback과 `Coder Provider` snapshot을 읽는다.
2. Worker Context Gate를 provider-aware 경로로 정확히 1회 통과한다.
   - `openai-codex`: Hermes MCP `kanban_worker_context`를 호출하고 `status=valid`, 현재 Task/Board, `task_status=running`, `claim_bound=true`를 확인한다.
   - 그 외 provider: `verify_worker_context.py --expected-workspace <Workspace> --expected-profile coder`를 첫 terminal command로 실행하고 `WORKER_CONTEXT_STATUS=valid`를 확인한다.
3. Worker Context Gate 성공 후 canonical `verify_workspace.py`를 **독립 terminal command로 정확히 1회** 실행해 Workspace/Expected Branch/Base SHA를 검증한다.
4. `Flow`, Work Unit Contract, Goal, AC, Implementation Tasks, Test Plan, Risks를 확인한다.
5. Task의 Project Pattern Summary / Pattern References / Applicable Skills를 재사용한다.

Codex native shell에는 Hermes가 Kanban ownership env를 노출하지 않는다. `HERMES_KANBAN_TASK`를 수동 주입하거나 direct chat/manual resume로 Worker Context Gate를 우회하지 않는다.

`STATUS=valid`이면 branch/base/workspace를 다시 확인하기 위한 `git status`, `git branch`, `git rev-parse` probe를 실행하지 않는다.

## 3. Direct Flow 재검증

`Flow: DIRECT`는 작은 단일 Work Unit만 허용한다. 실제 source evidence에서 다음 중 하나가 필요하다고 확인되면 구현을 넓히지 않고 `DIRECT_SCOPE_EXCEEDED`로 `kanban_block`한다.

- 요구사항이 둘 이상으로 해석됨
- DESIGN 또는 MIGRATION Work Unit 필요
- architecture/common shared contract 결정 필요
- public API request/response/error/auth 의미 변경
- DB schema/data migration 변경
- dependency 추가/upgrade
- Infrastructure runtime/topology/env delivery 변경
- transaction/security/authz/concurrency 정책 결정
- cross-repository 또는 승인 범위를 넘는 multi-module 변경
- current workspace/current branch 전제 위반

Block evidence에는 확인 근거와 `Required Flow: STANDARD`를 남긴다. Coder가 같은 Task를 내부적으로 Standard scope로 전환하지 않는다.

## 4. 구현

가장 가까운 기존 구현을 기준으로 승인 요구사항을 만족하는 최소 diff만 만든다. Rename, formatting, dependency upgrade, architecture rewrite, legacy cleanup, API/schema 변경은 승인 Work Unit에 직접 필요하지 않으면 섞지 않는다.

`CHANGES_REQUESTED`에서는 기존 올바른 변경을 유지하고 blocking finding만 처리한다.

## 5. Capability lazy loading

- Task의 `Applicable Skills`와 현재 affected scope만 사용한다.
- Spring 공통 규칙은 실제 Spring 작업에서만 `dev-spring-guidelines`를 로드한다.
- feature/data/docs Skill은 해당 영역을 실제 수정할 때만 로드한다.
- `dev-spring-test`는 테스트 작성/수정/설계 시에만 로드한다.
- Task에 Pattern References가 있으면 프로젝트 전체를 재탐색하지 않는다.
- Follow-up Work Unit 전용 capability는 현재 Task에서 실행하지 않는다.

## 6. 정확성 / 검증

관련 항목만 확인한다: null/input/failure, compatibility, transaction, concurrency, idempotency, security, config/data 영향.

```text
targeted test
→ 필요한 integration/module test
→ IMPLEMENTATION_STABLE
→ 필요한 경우 full test 1회
→ artifact 검증
→ scoped change_summary
→ Reviewer handoff
```

### 6.1 구현 중 검증

구현 중에는 변경 범위를 직접 검증할 수 있는 targeted/integration test를 우선한다. 전체 `test`는 중간 탐색 또는 단순 재확인 용도로 사용하지 않는다.

Java/Gradle 검증은 canonical `gradle_verification_cached.py`를 사용하며 Task의 `--scope-path`와 evidence root를 유지한다. `GRADLE_STATUS=BLOCKED` 이후 timed-out primary, `compileJava`, `--info` 변형, background wait를 임의로 반복하지 않는다.

### 6.2 Final regression gate

Full test가 Task/AC에서 필요하면 다음 순서를 지킨다.

```text
1. targeted/integration 검증 통과
2. IMPLEMENTATION_STABLE 선언
3. full test 1회
4. PASS 또는 failure classification
5. 필요한 artifact 검증
6. scoped change_summary
```

Full test 실패는 다음 셋 중 하나로 분류한다.

```text
IN_SCOPE_OR_IMPACTED
OUT_OF_SCOPE_UNCHANGED
UNCERTAIN
```

#### IN_SCOPE_OR_IMPACTED

변경 production/test와 직접 연관되거나 영향 가능성이 있는 실패다. 실패 test를 targeted하게 재현하고 수정한 뒤 다시 stable 상태가 되었을 때만 full test를 최종 1회 재실행할 수 있다.

#### OUT_OF_SCOPE_UNCHANGED

다음을 모두 만족해야 한다.

- 실패 test/source가 Changed Files에 없다.
- `SOURCE_EVIDENCE_READY`의 Direct Impact 기준으로 변경 production symbol과 직접 영향 관계가 없다.
- 첫 full test 후 이 실패를 위한 production/test 변경을 하지 않았다.
- 실패 signature가 동일하다.

이 경우 같은 Coder run에서 동일 full test를 다시 실행하지 않는다.

```text
Full Test: FAIL_REUSED_OUT_OF_SCOPE
Failure Signature: <class#method | representative message>
Full Test Retry: SKIPPED_IDENTICAL_OUT_OF_SCOPE_FAILURE
```

#### UNCERTAIN

직접 영향 여부를 안전하게 판단할 근거가 부족한 경우다. 기존 실패라고 추정해서 재사용하지 않는다. 필수 AC를 충족할 수 없다면 `kanban_block`하고, 판단 가능한 residual risk만 Reviewer에 전달한다.

### 6.3 Evidence invalidation

- full test PASS 이후 executable production/test가 변경되면 PASS는 무효다.
- covered source/test/build/toolchain이 변경되면 fresh verification이 필수다.
- `IN_SCOPE_OR_IMPACTED` 수정 후 이전 failure evidence를 최종 evidence로 사용하지 않는다.
- bootJar/assemble 성공은 test 실패를 성공으로 바꾸지 않는다.
- 실행하지 않은 검증을 PASS라고 쓰지 않는다.

## 7. Reviewer handoff

Direct와 Standard 모두 `Review Policy: REQUIRED`다. 변경이 작거나 risk가 낮아도 Reviewer를 생략하지 않는다.

Coder는 verification 완료 후 `kanban_request_review`하고 멈춘다. handoff에는 최소 다음을 남긴다.

```text
Flow: DIRECT | STANDARD
Work Unit Class / Boundary
Current Deliverable
Changed Files
Verification Commands / Results
Verification Request SHA256
Verification Scope SHA256
Effective Scope SHA256
Verification Final: true
Work Unit Boundary Respected: true
Full Test classification
Structural Quality Check
Risk Reasons
Residual Risk
```

Reviewer는 동일 PASS를 단순 확신 확보 목적으로 재실행하지 않고 fingerprint와 diff를 독립 검토한다.

## 8. Git / Safety

Coder는 commit, push, merge, rebase, cherry-pick, reset, clean, stash, workspace cleanup을 하지 않는다. secret/raw credential도 body/summary/metadata에 기록하지 않는다.

## 9. BLOCKED

Task 계약 부족, Workspace mismatch, 요구사항/코드 충돌, 필수 input/dependency 누락, 필수 검증 불가, `DIRECT_SCOPE_EXCEEDED`, `WORK_UNIT_BOUNDARY_EXCEEDED`는 `kanban_block`한다.

Gradle helper가 `GRADLE_STATUS=BLOCKED`를 반환하면 blocker type, primary command/result, diagnostic 결과를 evidence로 사용한다. 같은 Gradle primary command를 재시도해서 worker 시간을 소모하지 않는다.

일반 형식:

```text
What is blocked:
Evidence:
Decision/input needed:
Current change state:
Resume condition:
```

## 10. 성공 조건

- 승인 Workspace/Branch/Base SHA 유지
- 승인 Work Unit의 최소 scope 구현
- relevant targeted verification 수행
- full test는 implementation stable 이후 필요한 경우 1회 실행
- 범위 밖 동일 failure는 evidence 재사용으로 중복 실행 방지
- changed/untracked files와 residual risk 기록
- Direct/Standard 모두 `kanban_request_review`
- CHANGES_REQUESTED 후에도 동일 Workspace에서 수정하고 재-review
- commit/push/PR/merge 없음
