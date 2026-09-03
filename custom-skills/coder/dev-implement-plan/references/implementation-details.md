# dev-implement-plan 상세 구현 규칙

이 문서는 compact entrypoint인 `custom-skills/coder/dev-implement-plan/SKILL.md`에서 **필요할 때만 읽는 상세 규칙**이다. 기본 작업은 SKILL.md 계약만으로 처리하고, Fast Flow escalation, review risk 경계, retry/BLOCKED 판단처럼 세부 기준이 필요한 경우에만 해당 절을 읽는다.

## 1. Workflow

Standard Flow는 Orchestrator가 승인한 Plan/Workspace Contract를 사용하며 구현 후 항상 Reviewer에게 넘긴다. Fast Flow는 Coder intake가 만든 작은 작업 계약을 사용하며 구현 후 risk를 판정한다.

```text
Standard: Orchestrator → Kanban → Coder → Reviewer
Fast LOW: Coder intake → Kanban → Coder worker → done
Fast Review: Coder intake → Kanban → Coder worker → Reviewer
```

`CHANGES_REQUESTED` 재작업은 Flow와 무관하게 반드시 Reviewer에게 다시 넘긴다.

## 2. Worker 시작

1. `kanban_show()`로 body/history/feedback을 읽는다.
2. `$HERMES_KANBAN_WORKSPACE`에서 Task Key/Expected Branch/Base SHA를 검증한다.
3. Goal, AC, Implementation Tasks, Test Plan, Risks를 확인한다.
4. Task의 Project Pattern Summary / Pattern References / Applicable Skills를 재사용한다.

Workspace 검증은 canonical `verify_workspace.py`를 **단독 terminal command로 정확히 1회** 실행한다. 같은 terminal invocation에 `git status`, `git branch`, `git rev-parse`, toolchain/wrapper probe 등을 batch하지 않는다. `STATUS=valid`이면 branch/base/workspace를 다시 확인하기 위한 중복 Git probe를 실행하지 않는다. helper 자체가 실패했을 때만 실패 원인을 직접 확인하는 최소 probe를 허용한다.

계약 누락 또는 Workspace 불일치로 correctness가 흔들리면 수정 전에 Block한다.

## 3. Fast Flow 재검증

다음 중 하나라도 실제 evidence에서 확인되면 구현 범위를 넓히지 말고 `FAST_FLOW_ESCALATION_REQUIRED`로 Block한다.

- 요구사항이 둘 이상으로 해석됨
- architecture/product 정책 결정 필요
- public API request/response contract 변경
- DB schema/migration 변경
- cross-repository 작업
- dependency 추가/upgrade
- transaction/security/concurrency 정책 결정
- 예상보다 큰 구조 변경
- clean current-branch 전제가 깨짐

## 4. 구현

가장 가까운 기존 구현을 기준으로 요구사항을 만족하는 최소 diff만 만든다. Rename, formatting, dependency upgrade, architecture rewrite, legacy cleanup, API/schema 변경은 요청 범위에 직접 필요하지 않으면 섞지 않는다.

`CHANGES_REQUESTED`에서는 기존 올바른 변경을 유지하고 blocking finding만 처리한다.

## 5. Capability lazy loading

- Spring 공통 규칙은 실제 Spring 작업에서만 `dev-spring-guidelines`를 로드한다.
- feature/data/docs Skill은 해당 영역을 실제 수정할 때만 로드한다.
- `dev-spring-test`는 테스트 **작성/수정/설계** 시에만 로드한다. 기존 테스트 명령을 실행하는 것만으로는 로드하지 않는다.
- Task에 이미 Pattern References가 있으면 프로젝트 전체를 재탐색하지 않고 reference 존재/일치만 확인한 뒤 필요한 주변 코드로 제한한다.

## 6. 정확성 / 검증

관련 항목만 확인한다: null/input/failure, compatibility, transaction, concurrency, idempotency, security, config/data 영향.

검증은 좁은 범위부터 넓힌다.

```text
targeted test
→ 필요한 integration/module test
→ IMPLEMENTATION_STABLE
→ 필요한 경우 full test 1회
→ artifact 검증
→ scoped change_summary
```

### 6.1 구현 중 검증

구현 중에는 변경 범위를 빠르게 확인할 수 있는 targeted/integration test를 우선한다. 전체 `test`는 중간 탐색 또는 단순 재확인 용도로 사용하지 않는다.

Java/Gradle 검증은 Coder가 `hermes-java ./gradlew ...`를 여러 형태로 직접 반복하지 않고 아래 helper를 canonical 경로로 사용한다.

TARGETED_TEST:

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/gradle_verification.py \
  --workspace "<Workspace>" \
  --mode TARGETED_TEST \
  --test "<fully-qualified-test-selector>"
```

여러 selector는 `--test`를 반복한다.

COMPILE:

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/gradle_verification.py \
  --workspace "<Workspace>" \
  --mode COMPILE
```

Final full test가 필요한 경우에만 다음 형식을 사용한다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/gradle_verification.py \
  --workspace "<Workspace>" \
  --mode COMPILE \
  --task test
```

Helper contract:

```text
capability: hermes-java ./gradlew --version
primary: requested compile/targeted/full test exactly once
common args: --no-daemon --console=plain
primary timeout: default 240s
on primary timeout:
  - timed-out primary command 재실행 금지
  - online `help --info` 1회
  - offline `help --offline --info` 1회
  - blocker 분류 후 종료
```

대표 결과:

```text
GRADLE_STATUS=PASS
GRADLE_BLOCKER=NONE
```

```text
GRADLE_STATUS=FAIL
GRADLE_BLOCKER=BUILD_FAILURE
```

```text
GRADLE_STATUS=BLOCKED
GRADLE_BLOCKER=DEPENDENCY_RESOLUTION | PROJECT_CONFIGURATION | BUILD_TASK_TIMEOUT | CAPABILITY
PRIMARY_RETRY_ALLOWED=false
```

`GRADLE_STATUS=BLOCKED` 이후 Coder가 `compileJava`, 동일 targeted test, `--info` 변형, background Gradle process wait를 임의로 추가 실행하지 않는다. helper evidence를 Kanban blocker에 그대로 기록한다. 실제 source 수정으로 실패 원인이 바뀐 경우에만 새 최종 verification cycle을 시작할 수 있다.

### 6.2 Final regression gate

Full test가 Task/AC/Standard Flow에서 요구되면 다음 순서를 지킨다.

```text
1. targeted/integration 검증 통과
2. IMPLEMENTATION_STABLE 선언
3. full test 1회
4. PASS 또는 failure classification
5. 필요한 artifact 검증
6. change_summary
```

한 stable verification cycle에서 동일 full test를 반복하지 않는다.

Full test 실패는 다음 셋 중 하나로 분류한다.

```text
IN_SCOPE_OR_IMPACTED
OUT_OF_SCOPE_UNCHANGED
UNCERTAIN
```

#### IN_SCOPE_OR_IMPACTED

변경 production/test와 직접 연관되거나 영향 가능성이 있는 실패다.

- 실패 test를 targeted하게 재현한다.
- 원인을 수정한다.
- 필요한 targeted/integration test를 다시 통과시킨다.
- 다시 `IMPLEMENTATION_STABLE`이 된 뒤에만 full test를 최종 1회 재실행할 수 있다.

#### OUT_OF_SCOPE_UNCHANGED

다음 조건을 **모두** 만족해야 한다.

- 실패 test/source가 Task Changed Files에 없다.
- `SOURCE_EVIDENCE_READY`의 Direct Impact 기준으로 변경 production symbol과 직접 영향 관계가 없다.
- 첫 full test 후 이 실패를 위한 production/test 변경을 하지 않았다.
- 실패 signature가 동일하다. signature는 test class/method를 우선하고, 필요하면 대표 failure message를 추가한다.

이 경우 첫 full test 결과를 회귀 evidence로 재사용한다.

```text
Full Test: FAIL_REUSED_OUT_OF_SCOPE
Failure Signature: <class#method | representative message>
Full Test Retry: SKIPPED_IDENTICAL_OUT_OF_SCOPE_FAILURE
```

같은 Coder run에서 동일 full test를 다시 실행해 같은 실패를 재확인하지 않는다.

#### UNCERTAIN

직접 영향 여부를 안전하게 판단할 근거가 부족한 경우다. 기존 실패라고 추정해서 재사용하지 않는다. Standard Flow에서는 Reviewer에 residual risk로 전달하고, 필수 AC를 충족할 수 없다면 blocker로 처리한다.

### 6.3 Evidence invalidation

- full test PASS 이후 executable production/test가 변경되면 해당 PASS는 무효다.
- `IN_SCOPE_OR_IMPACTED` 실패 수정 후에는 이전 full test 실패 evidence를 최종 evidence로 사용하지 않는다.
- `OUT_OF_SCOPE_UNCHANGED` 실패는 해당 실패를 위해 코드를 수정하지 않는 한 재실행하지 않는다.
- bootJar/assemble은 full test 실패를 성공으로 바꾸지 않는다. artifact 생성 성공과 test 결과는 별도로 기록한다.

실행하지 않은 검증을 PASS라고 쓰지 않는다. 필수 검증이 불가능하면 LOW 판정을 금지한다.

## 7. Risk-based Review

### LOW 가능 예

다음 특성을 모두 만족하는 Fast Flow 작업이다.

- 작은 null/edge-case 처리
- 기존 validation rule의 국소 적용
- 로그/메시지/문서/주석 변경
- 테스트 케이스 보완
- 기존 패턴의 단순 Repository Method Query 수정
- 작은 조건/계산 수정
- 변경된 behavior를 targeted test 또는 동등 검증으로 직접 확인

그리고 다음 위험 신호가 없어야 한다.

```text
public API contract
DB schema/migration
Entity relation/fetch/cascade
complex QueryDSL
Native Query
transaction boundary
security/auth/authz
concurrency/locking
new dependency/framework/config infrastructure
shared/common module with broad callers
architecture boundary
cross-module/repository ripple
meaningful backward compatibility risk
uncertain residual risk
```

### REVIEW_REQUIRED

위 위험 신호 하나라도 있거나, diff 규모 자체가 작더라도 독립 검토가 correctness에 의미 있으면 Reviewer를 요청한다. 파일 개수만으로 LOW/HIGH를 결정하지 않는다.

### LOW 완료 증거

```text
Review Risk: LOW
Reasons:
- <왜 위험 영역이 아닌지>
Verification:
- <exact command> -> PASS
Residual Risk:
- none | <낮은 잔여 위험>
```

권장 metadata:

```json
{
  "phase": "implementation",
  "flow": "FAST",
  "review_risk": "LOW",
  "review_skipped": true,
  "risk_reasons": [],
  "changed_files": [],
  "verification": [],
  "residual_risk": [],
  "base_sha": "<verified Base SHA>"
}
```

LOW일 때만 Coder가 `kanban_complete`한다. Standard Flow나 review retry에서는 이 예외를 사용하지 않는다.

### Reviewer handoff

REVIEW_REQUIRED면 동일 evidence와 risk reasons를 포함해 `kanban_request_review`하고 멈춘다.

Full test가 실패했다면 handoff에 반드시 다음을 포함한다.

```text
Full Test: PASS | NOT_REQUIRED | FAIL_REUSED_OUT_OF_SCOPE | FAIL_IN_SCOPE | UNCERTAIN
Full Test Failure Signature: <signature | NONE>
Full Test Retry: <NOT_NEEDED | SKIPPED_IDENTICAL_OUT_OF_SCOPE_FAILURE | RERUN_AFTER_IN_SCOPE_FIX>
```

Reviewer는 `FAIL_REUSED_OUT_OF_SCOPE`를 자동 PASS로 간주하지 않고 변경 영향 관계와 AC 충족 여부를 독립 검토한다. 단, 동일 full test를 단순 재확인하기 위해 다시 실행하지 않는다.

## 8. Git / Safety

Coder는 commit, push, merge, rebase, cherry-pick, reset, clean, stash, workspace cleanup을 하지 않는다. secret/raw credential도 body/summary/metadata에 기록하지 않는다.

## 9. BLOCKED

Task 계약 부족, Workspace mismatch, 요구사항/코드 충돌, 필수 input/dependency 누락, 필수 검증 불가, Fast Flow scope escalation은 `kanban_block`한다.

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
- 최소 scope 구현
- relevant verification 수행
- full test는 implementation stable 이후 필요한 경우 1회 실행
- 동일한 범위 밖 full-test failure는 evidence 재사용으로 중복 실행 방지
- changed/untracked files와 residual risk 기록
- Fast LOW는 근거를 남기고 done
- Fast REVIEW_REQUIRED / Standard / retry는 Reviewer handoff
- commit/push/PR/merge 없음
