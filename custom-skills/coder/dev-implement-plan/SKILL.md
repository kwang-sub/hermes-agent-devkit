---
name: dev-implement-plan
description: Orchestrator가 승인·dispatch한 Direct 또는 Standard Kanban 단일 Work Unit을 할당 Workspace에서 구현·검증하고 항상 Reviewer에게 인계한다.
version: 0.24.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review, direct-flow, standard-flow, work-unit, capability, java, refactor, structural-quality, performance, infrastructure, runtime, container, env]
    related_skills: [dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review, dev-java-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-spring-refactor, dev-api-spec, dev-api-contract, dev-api-docs, dev-frontend-feature, dev-infrastructure, dev-data-feature, dev-data-modeling, dev-db-migration]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_block, kanban_heartbeat, skill_view]
---

# dev-implement-plan

Coder worker의 compact 실행 계약이다. **Coder는 새 mutation request의 실행 방식을 선택하거나 self-dispatch하지 않고 Orchestrator가 생성한 Kanban Task만 수행한다.** 상세 구현/검증/risk 형식이 필요할 때만 `references/implementation-details.md`를 읽는다. Direct/Standard 모두 `/opt/data/shared/references/standard-work-unit-rules.md`를 적용한다.

## 실행 순서 — Worker Context Gate → Workspace Verify

Coder run은 다음 순서를 고정한다.

```text
kanban_show
→ dev-implement-plan load
→ Worker Context Gate 정확히 1회
→ WORKER CONTEXT valid
→ verify_workspace.py 단독 1회
→ STATUS=valid
→ Work Unit Boundary Gate
→ 필요한 target source/test만 탐색
→ 현재 Work Unit만 구현
→ targeted verification
→ IMPLEMENTATION_STABLE
→ final regression gate (필요한 경우 full test 1회)
→ change_summary.py 1회
→ kanban_request_review 또는 kanban_block 정확히 1회
```

### Worker Context Gate

Task body의 `Coder Provider` snapshot을 기준으로 검증 경로를 분리한다.

**`openai-codex` Worker**는 Codex native shell에 Kanban ownership 환경변수를 노출하지 않는 Hermes 보안 경계를 그대로 유지한다.

```text
kanban_worker_context MCP tool 정확히 1회
→ status == valid
→ task_id == 현재 Task
→ board == 현재 Board
→ task_status == running
→ claim_bound == true
```

`kanban_worker_context`가 없거나 호출 실패/`status != valid`이면 `CAPABILITY` 또는 context blocker로 `kanban_block`하고 종료한다. Codex shell에서 `HERMES_KANBAN_TASK` 등을 수동 주입하거나 `verify_worker_context.py`로 우회하지 않는다.

**그 외 Hermes Worker**는 아래 helper를 첫 terminal command로 정확히 1회 실행한다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/verify_worker_context.py \
  --expected-workspace "<Workspace>" \
  --expected-profile coder
```

`WORKER_CONTEXT_STATUS=valid`이 아니면 구현/검증을 시작하지 않는다.

Worker Context Gate가 성공한 뒤 `verify_workspace.py`가 **첫 Git/workspace terminal command**다. 그 전에 workspace를 훑는 terminal probe는 실행하지 않는다.

Workspace 검증 전에 다음 명령 또는 동등한 inline Python/subprocess 조합을 실행하지 않는다.

```text
git status
git diff
git branch
git rev-parse
git ls-files
tracked/effective/EOL 변경 분류
working-tree 파일 개수 계산
```

Task body의 Workspace / Expected Branch / Base SHA는 Orchestrator가 이미 확정한 dispatch contract이므로 사전 재검증하지 않는다.

## Canonical Workspace Verification

`verify_workspace.py`는 **Git/Workspace 전용 검증기**다. Workspace 검증은 아래 **독립 terminal command로 정확히 1회** 실행한다. 다른 명령을 `+`, `&&`, `;`, background process 또는 batch 형태로 붙이지 않는다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/verify_workspace.py \
  --task-key "<Task Key>" \
  --workspace "<Workspace>" \
  --expected-workspace "<Workspace>" \
  --expected-branch "<Expected Branch>" \
  --base-sha "<Base SHA>"
```

`STATUS=valid`이면 helper가 확인한 workspace/branch/base를 신뢰한다. 이를 재확인하기 위한 `git status`, `git branch`, `git rev-parse` probe를 실행하지 않는다.

특히 Windows bind mount에서 raw `git status`는 수천 개 EOL-only 파일 때문에 매우 비쌀 수 있다. raw modified-file 개수를 baseline으로 재정의하거나 작업 중단 근거로 사용하지 않는다.

## Existing Changes Preservation Fast Path

Task body에 다음 중 하나가 있으면 Orchestrator가 기존 workspace 전체 변경 보존을 이미 승인한 것이다.

```text
Existing changes preservation approved: true
Workspace change scan mode: skipped-approved-preservation
```

이 경우 Coder는 exact pre-existing file list/count를 복구하려고 repository-wide `git status`, `git diff`, `git ls-files --others`, EOL 분류를 다시 실행하지 않는다. 기존 변경 전체를 baseline으로 보존하고 자신의 실제 변경 path만 별도로 추적한다. **기존 파일은 preserve-first**이며 Work Unit 경계 도입을 이유로 기존 사용자 변경이나 기존 설정을 자동 정리하지 않는다.

## Work Unit Boundary Gate

Direct/Standard Task는 구현 전에 다음 Task body 계약을 반드시 가진다.

```text
Work Unit Class: DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT
Work Unit Boundary: SINGLE_UNIT | SPLIT_REQUIRED
Current Deliverable: ...
Follow-up Required: YES | NO
Follow-up Work Unit: ... | NONE
Follow-up Input: ... | NONE
Excluded Follow-up Scope: ... | NONE
```

누락되면 production patch를 시작하지 않고 `CAPABILITY`/contract blocker로 `kanban_block`한다.

`Work Unit Boundary: SPLIT_REQUIRED`는 **현재 Task가 첫 Work Unit만 실행한다**는 의미다. Follow-up metadata를 현재 구현 범위로 승격하지 않는다.

### DESIGN

```text
허용:
- 승인된 설계 artifact materialization
- 문서/DBML/API spec/ADR 등 현재 deliverable에 필요한 파일
- artifact 자체 검증

금지:
- Excluded Follow-up Scope의 application/runtime/schema/data mutation
```

Data logical DESIGN이면:

```text
skill_view("dev-data-feature")
skill_view("dev-data-modeling")
→ approved logical DBML materialize
→ dbml_guard
→ STOP at DESIGN boundary
```

같은 Task에서 `dev-db-migration`을 사용해 Flyway/Liquibase/DDL/JPA physical mapping을 만들지 않는다.

### IMPLEMENTATION

승인된 requirement/design/contract를 application/runtime behavior로 구현한다. 같은 deliverable을 완성하는 Backend/Frontend/Infrastructure companion은 함께 사용할 수 있다. 여러 capability를 사용한다는 이유만으로 scope를 임의 축소하거나 Follow-up Task를 만들지 않는다.

### MIGRATION

```text
필수:
- approved/canonical logical model 또는 명시적 migration intent
- Work Unit Class: MIGRATION
```

필요하면 `skill_view("dev-data-feature")`와 `skill_view("dev-db-migration")`을 적용한다. migration 중 logical responsibility/cardinality/ownership redesign이 필요하면 현재 scope를 확장하지 않고 BLOCK하고 새 DESIGN Work Unit을 요구한다.

### REFACTOR

behavior-preserving structural change만 수행한다. API/schema/behavior 의미 변경을 refactor에 섞지 않는다.

### AUDIT

기본 read-only다. 승인된 audit report/document path가 있으면 문서 산출물은 쓸 수 있지만 application/test/config source를 수정하지 않는다. finding을 고치는 작업은 별도 IMPLEMENTATION/REFACTOR Work Unit이다.

### Boundary escalation

실제 source evidence에서 `Excluded Follow-up Scope`가 반드시 필요하다고 드러나면 임의 구현하지 않는다.

```text
WORK_UNIT_BOUNDARY_EXCEEDED
- Current Work Unit: ...
- Required Follow-up Work Unit: ...
- Evidence: ...
```

를 기록하고 `kanban_block`한다. Requirement Delta를 같은 Task에 주입해 Work Unit Class를 바꾸는 것도 금지한다.

## Flow: DIRECT

Direct Task는 Orchestrator의 compact eligibility를 통과한 작은 단일 Work Unit이다. Task body는 최소 다음을 만족해야 한다.

```text
Flow: DIRECT
Review Policy: REQUIRED
Work Unit Class: IMPLEMENTATION | REFACTOR
Work Unit Boundary: SINGLE_UNIT
API Spec Gate: NOT_REQUIRED
Infrastructure Impact: NO
Workspace Approval Source: DIRECT_FIXED_CURRENT
Branch Approval Source: DIRECT_FIXED_CURRENT
```

실제 source에서 다음이 필요하다고 드러나면 구현 범위를 확대하지 않는다.

```text
API/schema/dependency/DB migration
Infrastructure runtime/topology/env delivery
security/authz/transaction/concurrency 정책
architecture/common shared contract 결정
cross-repository 또는 승인 범위를 벗어난 multi-module 변경
새 DESIGN/MIGRATION Work Unit
복수 해석 요구사항
```

이 경우:

```text
DIRECT_SCOPE_EXCEEDED
- Evidence: <확인 근거>
- Required Flow: STANDARD
```

를 남기고 `kanban_block`한다. Direct Task를 내부에서 Standard 범위로 조용히 확장하지 않는다.

## Source / Scope 계약

Task의 `Project Pattern Summary`, `Pattern References`, `Goal`, `Acceptance Criteria`, `Implementation Tasks`, Work Unit Contract, 기존 변경 baseline을 재사용한다. 실제 source와 충돌하지 않는 한 프로젝트 전체를 다시 분석하지 않는다.

첫 production patch 전에 다음을 만족한다.

```text
SOURCE_EVIDENCE_READY
Target:
- <file/symbol>
Direct Impact:
- <caller/callee/persistence boundary>
Tests:
- <existing test path>
Open Questions: NONE

IMPLEMENTATION_SCOPE_READY
Production:
- <files>
Tests:
- <files>
Docs:
- <files if required>
Excluded:
- <Work Unit의 Excluded Follow-up Scope + directly checked unchanged>
```

DESIGN/AUDIT Work Unit에서는 Production scope가 비어 있을 수 있다.

탐색 규칙:
- Task/Pattern References에 정확한 path가 있으면 바로 사용한다.
- 같은 목적 symbol은 한 grep으로 묶는다.
- 큰 파일은 필요한 symbol 주변만 읽는다.
- `Open Questions: NONE`이면 반복 grep/find/read를 종료한다.
- 존재가 확인되지 않은 예상 test 파일을 연속 probe하지 않는다.
- 기존 사용자 변경을 reset/restore/clean/stash하지 않는다.

## Capability lazy-load

Task body의 `Applicable Skills`와 실제 **현재 Work Unit** affected scope를 기준으로 필요한 capability만 로드한다. Follow-up Work Unit 전용 capability는 현재 Task에서 로드/실행하지 않는다.

### Infrastructure

다음 중 하나면 첫 production patch 전에 반드시 `skill_view("dev-infrastructure")`를 적용한다.

```text
Applicable Skills에 dev-infrastructure 존재
Dockerfile / Compose / containerization 변경
Application Runtime 또는 Database Runtime 변경
DB host / port / network / service DNS / volume 변경
.env / container environment / remote runtime environment 전달 경로 변경
Supabase Local ↔ Cloud 또는 NATIVE ↔ SUPABASE runtime/platform 변경
```

Plan에 Infrastructure 영향이 명확한데 `dev-infrastructure`가 누락되어 있으면 routing 누락으로 기록하고 기존 승인 Goal/AC와 Work Unit 안에서만 적용한다. 새로운 architecture/product/Work Unit 결정이 필요하면 Block/Escalate한다.

```text
Spring application.yml|yaml|properties / connection config 변경
→ skill_view("dev-spring-feature")

Frontend runtime env 변경
→ skill_view("dev-frontend-feature")

DB Vendor 변경이 현재 MIGRATION Work Unit 범위
→ skill_view("dev-data-feature")
→ skill_view("dev-db-migration")
```

기존 프로젝트의 하드코딩/추적 Secret WARN만으로 설정 migration을 자동 수행하지 않는다. 이번 Task가 해당 설정을 새로 만들거나 실제 수정해야 할 때만 configuration security 계약을 적용한다.

### Java / Spring

실제 evidence가 필요한 경우에만 로드한다.

- Java 언어/convention → `skill_view("dev-java-guidelines")`
- 공통 Spring 규칙 → `skill_view("dev-spring-guidelines")`
- API/Controller/Service/DTO/Validation/Exception 및 Infrastructure companion Spring 설정 → `skill_view("dev-spring-feature")`
- JPA/Repository/QueryDSL/Converter/Paging → `skill_view("dev-spring-data")`
- 테스트 작성/수정 → `skill_view("dev-spring-test")`
- Spring source 구현 완료 후 구조 trigger가 실제로 있을 때만 → `skill_view("dev-spring-refactor")`
- OpenAPI/Swagger/Postman → `skill_view("dev-api-docs")`

### API / Cross-stack

현재 Work Unit의 `Applicable Skills`에 `dev-api-spec` 또는 `dev-api-contract`가 있거나 Backend/Frontend가 동일 API contract를 함께 구현하면 필요한 계약만 lazy-load한다.

- 승인된 Markdown API specification 구현/동기화 → `skill_view("dev-api-spec")`
- Backend DTO/response/error와 Frontend type/client가 동일 계약을 공유 → `skill_view("dev-api-contract")`
- OpenAPI/Swagger/Postman 산출물 → `skill_view("dev-api-docs")`

API DESIGN Work Unit에서 후속 IMPLEMENTATION이 제외되어 있으면 contract artifact까지만 다루고 application source 구현으로 넘어가지 않는다.

구조 점검 evidence는 `Structural quality check: PASS | REFACTORED | ESCALATED`로 남긴다.

## Java / Gradle 검증

Java/Gradle/Maven 프로젝트는 Bootstrap의 `.hermes/toolchain.env`를 사용한다. JDK/Gradle/Maven을 task-time에 설치하지 않는다.

Gradle compile/targeted test의 canonical 실행은 `scripts/gradle_verification_cached.py`다. 기본 verification timeout은 600초이며 600초를 초과할 수 없다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/gradle_verification_cached.py \
  --workspace "<Workspace>" \
  --mode TARGETED_TEST \
  --test "<fully-qualified-test-selector>" \
  --scope-path "<covered-production-or-test-path>" \
  --evidence-root "/opt/data/gradle/verification-evidence/<Task ID>"
```

규칙:
- 여러 targeted test는 가능한 한 한 invocation으로 합친다.
- 구현 중에는 targeted test 또는 필요한 integration/module test만 사용한다.
- 전체 `test`는 `IMPLEMENTATION_STABLE` 이후 final regression gate에서만 실행한다.
- 한 stable verification cycle에서 full test는 기본 1회다.
- 실제 BUILD_FAILURE는 source/test 수정 후 최소 재검증할 수 있다.
- PASS evidence의 scope/request fingerprint가 동일하면 재사용하며 같은 Gradle command를 다시 실행하지 않는다.
- PASS 이후 covered production/test/build/toolchain 파일이 바뀌면 **fresh Gradle verification을 반드시 다시 실행한다.**
- `GRADLE_STATUS=BLOCKED`이면 direct Gradle 반복이나 우회 wrapper를 만들지 않고 `kanban_block`한다.

### Gradle PASS Evidence 재사용 계약

```text
Verification Request SHA256: <VERIFICATION_REQUEST_SHA256>
Verification Scope SHA256: <VERIFICATION_SCOPE_SHA256>
Verification Evidence: EXECUTED | REUSED
Primary Reused: true | false
```

## Full Test 실패 재사용 정책

```text
FULL_TEST_FAILURE_CLASSIFICATION
- IN_SCOPE_OR_IMPACTED
- OUT_OF_SCOPE_UNCHANGED
- UNCERTAIN
```

`OUT_OF_SCOPE_UNCHANGED`는 실패 source/test가 Changed Files와 직접 영향 범위 밖이고 signature가 동일한 경우에만 사용한다. 이 경우 같은 Coder run에서 전체 test를 반복하지 않는다.

`IN_SCOPE_OR_IMPACTED`이면 targeted 수정 후 stable 상태에서 final full test를 1회 다시 수행할 수 있다. `UNCERTAIN`은 risk/blocker로 남긴다.

## Implementation Stable / Final Scope

```text
IMPLEMENTATION_STABLE
- Work Unit Boundary respected: true
- Production scope fixed: true
- Test scope fixed: true
- Additional production edits planned: false
- Structural quality check: PASS | REFACTORED | ESCALATED
```

검증 순서:

```text
targeted/integration verification
→ IMPLEMENTATION_STABLE
→ full test 1회 (필요한 경우)
→ failure classification 또는 PASS
→ artifact 검증 (필요한 경우)
→ scoped change_summary.py 1회
```

최종 변경 범위가 확정된 뒤:

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/change_summary.py \
  --workspace "<Workspace>" \
  --include "<changed-path-1>" \
  --include "<changed-path-2>"
```

Direct/Standard Flow에서 `--include` 없이 호출하지 않는다. `--allow-full-scan`은 명시적 진단 전용이다. tracked와 untracked 모두 Git pathspec으로 제한하며 unrelated repository 전체를 훑지 않는다. `EOL_ONLY_COUNT > 0` + `WHITESPACE_ERROR_COUNT=0`은 정상이다.

`change_summary.py`가 DevKit runtime/capability 문제로 실패하면 **임시 wrapper/script 생성**, executable bit 변경, inline Python monkey-patch 등으로 우회하지 않고 `CAPABILITY` blocker로 종료한다.

## Review / Handoff

**Direct Flow, Standard Flow, CHANGES_REQUESTED 재작업은 모두 항상 review한다.** Coder가 risk를 LOW로 판정해도 self-complete하지 않는다.

다음은 특히 높은 review attention이 필요한 영역이다.
- API/request/response 의미 변경
- DB schema/data/query 의미 변경
- Work Unit DESIGN/MIGRATION artifact 변경
- transaction/security/concurrency 영향
- shared/common behavior 변경
- legacy/fallback/backward compatibility 변경
- operational config/persistence 의미 변경
- Infrastructure runtime/topology/environment delivery 변경
- 영향 범위 불명확

Review handoff에는 최소 다음을 남긴다.

```text
Flow: DIRECT | STANDARD
Work Unit Class: <...>
Work Unit Boundary: <...>
Current Deliverable: <...>
Follow-up Required: <YES|NO>
Follow-up Work Unit: <...|NONE>
Excluded Follow-up Scope: <...|NONE>
Work Unit Boundary Respected: true
Changed Files:
- ...
Verification Mode: <mode>
Verification Commands / Results:
- <command> -> PASS | FAIL
Verification Request SHA256: <...|NONE>
Verification Scope SHA256: <...|NONE>
Verification Evidence: EXECUTED | REUSED | NOT_REUSABLE
Primary Reused: true | false
Full Test: PASS | NOT_REQUIRED | FAIL_REUSED_OUT_OF_SCOPE | FAIL_IN_SCOPE | UNCERTAIN
Verification Final: true
Effective Scope SHA256: <...>
Structural Quality Check: PASS | REFACTORED | ESCALATED
Review Risk: REVIEW_REQUIRED
Risk Reasons:
- Impact Scope: ...
- Compatibility: ...
- Operational Config: ...
- Reason: ...
Residual Risk:
- ...
```

## Terminal transition

한 Coder run의 terminal transition은 `kanban_block`, `kanban_request_review` 중 정확히 하나다.

- Direct/Standard Flow 모두 Coder self-complete 금지.
- `CHANGES_REQUESTED`는 terminal 상태가 아니며 original coder가 동일 Workspace에서 blocking finding만 수정 후 재-review한다.
- `GRADLE_STATUS=BLOCKED`인 검증은 review residual risk로 넘기지 않고 `kanban_block`한다.
- `kanban_request_review` 성공 후 즉시 종료한다.

## 공통 Coding Rules 핵심

`/opt/data/shared/references/coding-rules.md`를 적용한다.

- 기존 abstraction/library/pattern을 재사용하고 unrelated refactor를 섞지 않는다.
- 함수/메서드 실행 block은 기본 `2-depth`를 지향한다.
- 반복 I/O/N+1을 확인한다.
- API는 기존 common response/error contract를 유지한다.
- JPA는 단순 Method Query → 복잡/동적 QueryDSL → 근거 있는 Native Query 순서다.

## 공통 불변식

- Workspace 밖 수정, branch 전환, 다른 worktree 생성, commit, push, PR, merge, reset, clean, stash 금지.
- secret/raw credential 기록 금지.
- behavior/API/schema 의미 변경을 refactor라는 이름으로 섞지 않는다.
- existing preservation fast path를 이유로 repository-wide dirty/EOL/untracked scan을 재실행하지 않는다.
- Follow-up Work Unit을 현재 Task에서 선행 구현하지 않는다.
- Interactive Coder가 Kanban 없이 새 mutation request를 직접 구현하거나 self-dispatch하지 않는다.

retry/BLOCKED/검증/risk metadata의 추가 세부 형식이 필요할 때만 `references/implementation-details.md`를 읽는다.