---
name: dev-implement-plan
description: Orchestrator가 승인·dispatch한 Direct 또는 Standard Kanban 단일 Work Unit을 할당 Workspace에서 구현·검증하고 항상 Reviewer에게 인계한다.
version: 0.30.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review, direct-flow, standard-flow, work-unit, capability, java, refactor, structural-quality, performance, infrastructure, runtime, container, env]
    related_skills: [dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review, dev-java-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-spring-refactor, dev-api-spec, dev-api-contract, dev-api-docs, dev-frontend-feature, dev-infrastructure, dev-data-feature, dev-data-modeling, dev-db-migration]
    requires_tools: [terminal, kanban_show, kanban_comment, kanban_request_review, kanban_block, kanban_heartbeat, skill_view]
---

# dev-implement-plan

Coder는 새 mutation request의 실행 방식을 선택하거나 self-dispatch하지 않고 Orchestrator가 생성한 Kanban Task만 수행한다. Direct/Standard Task 모두 `/opt/data/shared/references/standard-work-unit-rules.md`, `/opt/data/shared/references/session-history-rules.md`, `/opt/data/shared/references/kanban-execution-boundary.md`의 `KANBAN_EXECUTION_BOUNDARY_V1`, `/opt/data/shared/references/verification-level-policy.md`의 `VERIFICATION_LEVEL_POLICY_V1`을 적용한다. Kanban은 WHAT/STATE의 source of truth이며 launcher/timeout/retry/cache/process cleanup 같은 HOW는 이 Skill과 canonical runtime/execution 정책에서 결정한다. 상세 절차·retry·verification 분류가 필요할 때만 `references/implementation-details.md`를 읽는다.

## 시작 계약 전달

실제 spawn query의 `DEVKIT_WORKER_STARTUP_V1`은 이 Skill을 첫 `kanban_show` 직후 로드하도록 안내한다. 새/재개 worker, Direct/Standard/Recovery/CHANGES_REQUESTED에서 같은 절차다. source read 또는 raw `git branch/status/rev-parse` 전에 아래 시작 Gate를 수행한다. 지정 helper를 `find`/`--help`로 재탐색하지 않는다. 런타임 안내는 tool guard나 승인 정책을 대체하지 않는다.

## 실행 순서

```text
kanban_show
→ task_session_history.py capture
→ SESSION_HISTORY_BEST_EFFORT_V1: 실제 marker/receipt 또는 미확인 warning
→ Worker Context Gate 1회
→ verify_workspace.py 1회
→ Work Unit Boundary Gate
→ Standard Flow Verification Contract Gate
→ Bounded Pre-Mutation Impact Scan (최대 2-hop)
→ Impact Summary / Implementation Scope 확정
→ 현재 Work Unit만 구현
→ targeted verification
→ IMPLEMENTATION_STABLE
→ 필요한 final regression
→ scoped change_summary.py
→ SESSION_HISTORY_FINALIZE (pending일 때만)
→ kanban_request_review | kanban_block
```

Workspace Version Control과 Pattern References는 Task body를 재사용한다. Git Workspace는 Expected Branch/Base SHA를 검증하고, Non-Git Workspace는 `Version Control: none`, `Branch/Base SHA: NONE` 계약으로 `verify_workspace.py --version-control none`을 사용한다. 기존 변경은 preserve-first이며 reset/restore/clean/stash하지 않는다. Existing Changes Preservation Fast Path가 승인된 Git Workspace에서는 repository-wide dirty/EOL/untracked scan을 반복하지 않는다.

## Bounded Pre-Mutation Impact Scan

첫 production mutation 전에 승인된 변경 식별자/파일을 기준으로 **최대 2-hop**만 확인한다. 1-hop은 direct caller/reference/mapping/validation, 2-hop은 실제 1-hop 근거가 security/session/history/audit/persistence/external contract 경계를 가리킬 때만 확장한다. 프로젝트 전체 architecture 분석이나 `혹시 더 있을까` 식 반복 탐색은 하지 않는다. 최초 `kanban_show`와 그 spillover를 Task Snapshot으로 재사용하고 같은 정보 확인을 위한 `kanban_show`를 반복하지 않는다. read-only 탐색은 전용 `read/find/grep`을 우선하며 파일/JSON 확인을 위한 inline `python3 -c`·`hermes_tools` exec·Path traversal을 만들지 않는다. 범위가 확정되면 짧은 `Impact Summary`로 압축하고, 승인 범위를 넘는 영향이 확인되면 source mutation 없이 기존 blocker/triage 경로로 넘긴다. 상세 scan/stop/evidence 형식은 필요할 때만 `references/implementation-details.md`의 Source/Scope 절을 읽는다.

## Reference Lazy-Load

정상 경로에서는 이 `SKILL.md`를 기본 계약으로 사용하고 reference 전문을 선로딩하지 않는다. `session-history-rules.md`는 capture/receipt가 비정상·모호할 때, `standard-work-unit-rules.md`는 boundary/split/DESIGN·AUDIT edge case일 때, `kanban-execution-boundary.md`는 runtime 책임 경계가 실제로 모호할 때, `implementation-details.md`는 Recovery/impact-scan/blocker/verification 상세 형식이 필요할 때만 관련 절을 읽는다. Maven/Node/stack runtime reference는 해당 toolchain이 실제 affected scope에 있을 때만 load한다.

## Session History Gate — SESSION_HISTORY_BEST_EFFORT_V1

모든 실행 카드(Parent 없는 일반 단일 카드와 `[자식]` 카드)는 공통 `session-history-rules.md`를 따른다. Standard / Direct / Recovery / CHANGES_REQUESTED에 동일하게 적용한다.

```bash
python3 /opt/devkit/bin/task_session_history.py capture \
  --task-id "<Task ID from kanban_show>" \
  --profile coder \
  --profile-home /opt/data/profiles/coder \
  --workspace "<Workspace from kanban_show>" \
  --session-mode UNKNOWN --phase start
```

Task ID/Workspace는 `kanban_show`, profile/profile-home은 현재 역할에서 명시적으로 전달한다. 터미널의 scrub된 Kanban ownership ENV로 추측하지 않는다. Helper만 최대 3회 제한 재시도하며 외부 retry/sleep loop는 금지한다.

- `SESSION_HISTORY_STATUS=captured`: `SESSION_HISTORY_COMMENT_PENDING`을 확인한다. pending이면 기존 Task comments와 실제 `Session ID + Profile` marker를 대조하고 없을 때만 `TASK_SESSION_HISTORY`를 `kanban_comment`한다. 성공/기존 marker 확인 후 `ack-comment`한다.
- `SESSION_HISTORY_NEW=false`는 DB 중복일 뿐 comment 성공 증거가 아니다. receipt 성공 뒤에만 추적을 resolved로 처리한다.
- `SESSION_HISTORY_STATUS=unavailable` 또는 `error`: 시작 시 durable warning comment를 만들지 않고 `SESSION_HISTORY_RECHECK_REQUIRED=true`와 sanitized status/reason을 현재 worker 근거에 유지한 채 source mutation을 계속한다. captured marker·receipt 기록 오류도 같은 pending trace로 처리한다. `invalid`는 context blocker다. Task/Workspace/승인/검증 Gate는 완화하지 않는다.

**SESSION_HISTORY_FINALIZE:** 미확인/comment 미완료일 때만 구현·검증 완료 후 `kanban_request_review` 직전 또는 다른 원인의 `kanban_block` 직전에 같은 context로 `capture --phase finalize`를 1회 실행한다. 이미 확인한 ID가 있으면 `--session-id`로 고정한다. 성공하면 같은 Task marker/receipt를 보완한다. 계속 미확인/추적 오류이거나 marker/receipt 보완이 실패하면 그때만 `TASK_SESSION_HISTORY_WARNING`을 최대 1회 durable comment로 남기고 handoff에 상태·원인을 보존한 뒤 원래 전이를 수행한다. 완료된 추적은 재조회하지 않는다. 잘못된 실행 context에는 보완하지 않는다.

여러 Session ID를 마지막 하나로 덮어쓰지 않는다. Reviewer/새 Recovery 세션으로 과거 Coder 누락을 대신 채우지 않는다. 상세 comment 중복/응답 유실 처리는 공통 reference가 source of truth다.

## Approved Recovery Revision Contract

초기 `kanban_show`의 comments에 Task Recovery marker가 있으면 source mutation 전에 복구 계약을 판정한다.

```text
TASK_RECOVERY_RETRY_V<N>
→ RETRY_SAME_CONTRACT
→ Original Contract / AC 그대로 재사용

TASK_RECOVERY_REVISION_V<N>
+ Recovery Gate: APPROVED
+ Recovery Mode: SAME_TASK_RESUME
→ 가장 큰 N의 승인 Revision만 Latest Approved Recovery Revision으로 사용

TASK_RECOVERY_ESCALATION_V<N>
+ Current Task: PRESERVE_BLOCKED
→ 이 Task가 running으로 들어온 상태 자체가 계약 위반
→ RECOVERY_CONTRACT_INVALID로 BLOCK
```

`SAME_TASK_RESUME`에서는 Task body를 덮어쓴 것으로 간주하지 않는다.

```text
Effective Task Contract
= Original Task Contract
+ Latest Approved Recovery Revision의 명시적 delta
```

우선순위:

```text
Latest Approved Recovery Revision에서 명시적으로 Changed/Forbidden/Reverification/Acceptance Criteria로 갱신한 항목
→ 해당 항목만 Revision 우선

Revision이 언급하지 않은 Goal/Work Unit/기존 constraint
→ Original Contract 유지
```

Coder는 Recovery Revision을 이유로 새 카드/branch/worktree를 만들지 않고, 승인된 delta만 현재 Task 범위에 합친다. 가장 큰 Revision이 malformed이거나 `Recovery Gate: APPROVED`, Task ID, Recovery Mode 정합성이 없으면 추측하지 않고 `RECOVERY_CONTRACT_INVALID`로 `kanban_block`한다.

Handoff에는 다음을 남긴다.

```text
Recovery Contract: NONE | RETRY_SAME_CONTRACT | SAME_TASK_RESUME
Recovery Revision: <TASK_RECOVERY_REVISION_VN | TASK_RECOVERY_RETRY_VN | NONE>
Recovery Delta Applied: true | false
```

## Work Unit Boundary Gate

필수 계약:

```text
Work Unit Class: DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT
Work Unit Boundary: SINGLE_UNIT | SPLIT_REQUIRED
Current Deliverable: ...
Follow-up Required: YES | NO
Follow-up Work Unit: ... | NONE
Follow-up Input: ... | NONE
Excluded Follow-up Scope: ... | NONE
```

- DESIGN: 승인 artifact만 materialize한다. Data logical DESIGN은 DBML 검증 후 **STOP at DESIGN boundary**. 같은 Task에서 `dev-db-migration`을 실행하지 않는다.
- IMPLEMENTATION: 승인된 requirement/design/contract의 현재 deliverable만 구현한다.
- MIGRATION: approved logical model 또는 명시적 migration intent를 입력으로 사용한다.
- REFACTOR: behavior-preserving 변경만 허용한다.
- ### AUDIT
  기본 read-only이며 application/test/config source를 수정하지 않는다.

경계를 넘는 구현이 필요하면 `WORK_UNIT_BOUNDARY_EXCEEDED`로 BLOCKED 처리한다. Follow-up Work Unit을 현재 Task에서 선행 구현하지 않는다.

## Flow: DIRECT

```text
Flow: DIRECT
Review Policy: REQUIRED
Work Unit Class: IMPLEMENTATION | REFACTOR
Work Unit Boundary: SINGLE_UNIT
API Spec Gate: NOT_REQUIRED
Infrastructure Impact: NO
```

Direct 범위 밖의 API/schema/dependency/DB migration, Infrastructure, security/authz/transaction/concurrency, architecture/common contract, 새 DESIGN/MIGRATION이 필요하면 `DIRECT_SCOPE_EXCEEDED`와 `Required Flow: STANDARD`를 남기고 차단한다.

## Capability lazy-load

Applicable Skills와 실제 현재 Work Unit만 기준으로 필요한 capability를 `skill_view`한다.

- Java → `skill_view("dev-java-guidelines")`
- Spring 공통 → `skill_view("dev-spring-guidelines")`
- Spring feature/config → `skill_view("dev-spring-feature")`
- JPA/Repository/QueryDSL → `skill_view("dev-spring-data")`
- Test → `skill_view("dev-spring-test")`
- 구조 trigger가 실제로 있을 때 → `skill_view("dev-spring-refactor")`
- API Spec → `skill_view("dev-api-spec")`
- API cross-stack → `skill_view("dev-api-contract")`
- OpenAPI/Swagger/Postman → `skill_view("dev-api-docs")`
- Frontend → `skill_view("dev-frontend-feature")`; 이후 첫 Node command 전에 해당 skill의 Frontend Environment Gate를 반드시 수행
- Infrastructure 영향이면 **첫 production patch 전에 반드시** `skill_view("dev-infrastructure")`
- Data → `skill_view("dev-data-feature")`
- MIGRATION → `skill_view("dev-db-migration")`

기존 파일은 preserve-first다. Infrastructure companion에서 Spring 설정은 `skill_view("dev-spring-feature")`, DB physicalization은 `skill_view("dev-data-feature")` + `skill_view("dev-db-migration")`을 사용한다.

구조 evidence는 `Structural quality check: PASS | REFACTORED | ESCALATED`로 남긴다.

## Standard Flow Verification Contract Gate

Standard Flow Coder는 구현 전에 Task body의 승인된 Verification Contract를 읽는다.

```text
Verification Target
Verification Level
Verification Escalation Reason
Project Verification Source
Verification Method
Verification Provider
Environment Dependency
Required Environment
Lifecycle
Fallback Policy
Verification Approval: APPROVED
```

환경 의존 검증의 provider는 구현 후 Coder가 새로 선정하지 않는다. 승인 provider가 unavailable이면 로컬 DB, Docker, Testcontainers, 외부 서비스 등 다른 provider로 자동 fallback하지 않고 `VERIFICATION_PROVIDER_UNAVAILABLE` evidence와 함께 차단/재승인 경로로 넘긴다. 프로젝트가 제공하는 canonical verification이 승인되어 있으면 그 경로를 우선 사용하며 Hermes 공용 검증 인프라를 임의 생성하지 않는다. Direct Flow에는 이 Standard 전용 계약을 강제하지 않는다.

## Verification / Handoff

Frontend/Node Work Unit은 `dev-frontend-feature`를 load한 뒤 **첫 Node command 전에** `node_environment_gate.py`를 실행한다. `FRONTEND_ENVIRONMENT_GATE=BLOCKED`이면 `PROJECT_TOOLCHAIN_MIGRATION_REQUIRED`, `PNPM_BUILD_POLICY_REVIEW_REQUIRED` 등 실제 blocker class를 evidence로 남기고 `kanban_block`한다. 같은 Task에서 npm→pnpm migration을 암묵적으로 시작하거나 source worktree에서 `npm`, `npx`, `next`, `tsc`, 직접 `pnpm run`으로 fallback하지 않는다. `.next` 권한 수정/삭제를 반복해 canonical verification을 대신하지 않는다.

isolated restore가 `ERR_PNPM_IGNORED_BUILDS`로 실패하면 일반 build 실패로 처리하지 않는다. **package별로 즉시 하나씩 BLOCK하지 말고**, 실패한 restore output의 전체 matcher를 수집한 뒤 같은 `RESTORE_WORKDIR`에서 read-only `pnpm ignored-builds`를 정확히 1회 실행해 pending build 목록을 보강한다. 이미 `pnpm-workspace.yaml > allowBuilds`에 boolean 결정이 있는 matcher를 제외하고 남은 exact `package@version` 전체를 하나의 `PNPM_BUILD_POLICY_REVIEW_REQUIRED` batch로 사용자에게 제시한다.

사용자가 여러 항목을 승인/거부하면 `pnpm_build_policy.py`에 모든 `--approve` / `--deny`를 한 invocation으로 전달하고, 출력된 `POLICY_UPDATE_COMMAND_<N>`을 source package root에서 한 번 적용한 뒤 같은 Work Unit을 재개한다. evidence는 `PNPM_BUILD_POLICY_DECISION_MODE=BATCH`와 decision/approval/denial count를 남긴다. 같은 dependency graph에서 policy 적용 후 restore를 1회 재시도했는데 새 미검토 matcher가 또 나오면 자동 승인 루프를 만들지 않고 `PNPM_BUILD_POLICY_DISCOVERY_INCOMPLETE`로 BLOCK한다. package.json 또는 pnpm-lock.yaml이 변경되어 graph가 달라진 경우만 새 review batch다.

이미 `pnpm-workspace.yaml > allowBuilds`에 동일 matcher가 boolean으로 결정되어 있으면 재승인을 요청하지 않는다. `dangerouslyAllowAllBuilds=true`, `strictDepBuilds=false`, `pnpm approve-builds --all`, bare package 전체 true 승인은 자동 사용하지 않는다.

Gate PASS 이후 Node 검증은 `VERIFICATION_LEVEL_POLICY_V1`에 따라 최소 수준부터 선택하고 `node_runtime.py` Linux isolated workspace만 사용한다. 일반 TypeScript/source 변경의 기본은 project canonical `typecheck`/`check`이며, `build`는 `PACKAGE_BUILD` 승격 근거가 있을 때만 실행한다.

Maven 프로젝트는 `/opt/data/shared/references/maven-worker-runtime.md`와 `VERIFICATION_LEVEL_POLICY_V1`을 적용한다. 일반 source 변경은 `COMPILE` mode의 project canonical compile/testCompile 계열부터 시작하고, 관련 behavior 검증이 필요할 때 `TARGETED_TEST`, artifact/build 자체가 scope일 때만 `PACKAGE`/`VERIFY`로 승격한다. 진단은 `/usr/local/bin/hermes-maven --diagnose ./mvnw`, 실제 검증은 `/opt/custom-skills/coder/dev-implement-plan/scripts/maven_verification_cached.py`를 canonical 경로로 실행한다. 동일 verification request + executable scope의 PASS fingerprint는 재사용한다. raw `mvn`/`./mvnw` 또는 HOME `.m2` 탐색으로 우회하지 않으며 `MAVEN_STATUS=BLOCKED`이면 실제 blocker/evidence를 기록한다. 불필요한 `PACKAGE_BUILD`를 실행해 생긴 timeout을 현재 Task blocker로 만들지 않는다.

Java/Gradle은 기존 toolchain과 `VERIFICATION_LEVEL_POLICY_V1`의 최소 수준을 적용하고 canonical cached verification helper를 사용한다. 일반 source 변경은 COMPILE, behavior 검증이 필요할 때 TARGETED_TEST를 사용하며 `build`/`assemble`/`bootJar`/`war` 같은 artifact task는 `PACKAGE_BUILD` 승격 근거가 있을 때만 실행한다. 동일 PASS fingerprint는 불필요하게 재실행하지 않는다. raw `./gradlew ...` 또는 `gradle ...` 직접 실행은 금지하며, 단순 bounded 진단이 필요하면 `hermes-java ./gradlew ...`, COMPILE/TARGETED_TEST는 `gradle_verification_cached.py`만 사용한다. 최종 scope 확정 후 **scoped change_summary.py**를 실행한다. Standard Flow에서 `--include` 없이 호출하지 않는다. Git Workspace는 기존 diff/fingerprint handoff를 사용한다. Non-Git Workspace는 `change_summary.py --version-control none --include <changed-path>`로 Coder가 실제 변경 파일을 명시하며 Hermes가 snapshot이나 자동 diff를 만들지 않는다. 결과의 Changed Files와 verification evidence를 handoff한다.

```text
Work Unit Boundary Respected: true
Verification Level: STATIC_COMPILE | TARGETED_TEST | PACKAGE_BUILD
Verification Escalation Reason: <NONE | evidence>
Project Verification Source: TASK_APPROVED | PROJECT_SCRIPT | CI | BUILD_TOOL_DEFAULT
Verification Final: true
Review Risk: REVIEW_REQUIRED
```

**Direct Flow, Standard Flow, CHANGES_REQUESTED 재작업은 모두 항상 review한다.** CHANGES_REQUESTED는 original coder가 동일 Workspace에서 blocking finding만 수정하고 다시 review한다. Direct/Standard Flow 모두 Coder self-complete 금지.

Terminal transition은 `kanban_request_review` 또는 `kanban_block` 중 정확히 하나다. 검증이 BLOCKED이면 residual risk로 넘기지 않고 차단한다.

## 공통 Coding Rules 핵심

`/opt/data/shared/references/coding-rules.md`를 적용한다. 기존 abstraction/pattern 재사용, 최소 scope, 기본 `2-depth`, 반복 I/O/N+1, 기존 response/error contract를 확인한다.

## 불변식

- Workspace 밖 수정 금지. Git Workspace에서는 branch 전환, 다른 worktree 생성, commit, push, PR, merge 금지. Non-Git Workspace에서는 branch/worktree/commit 계약이 적용되지 않는다.
- secret/raw credential 기록 금지.
- Follow-up Work Unit 전용 capability를 현재 Task에서 실행하지 않는다.
- `TASK_RECOVERY_REVISION_V<N>`은 가장 큰 승인 Revision의 명시적 delta만 Original Contract에 합성하며, 전체 Task body 대체나 임의 scope 확장 근거로 사용하지 않는다.
- Frontend Environment Gate가 toolchain migration을 요구하면 현재 IMPLEMENTATION Work Unit에서 migration/fallback 검증을 수행하지 않는다.
- pnpm build-script 승인 결정은 `pnpm-workspace.yaml > allowBuilds`에 Git 관리하고, 같은 exact matcher를 반복 승인받지 않는다.
- 초기 pnpm 안정화에서는 `ERR_PNPM_IGNORED_BUILDS` 항목을 하나씩 사용자에게 묻지 않고 전체 pending set을 한 batch로 승인받는다.
- build-script 승인 후 정책 변경은 현재 pnpm migration/dependency Work Unit의 승인된 재개로 처리하며 별도 Hermes allowlist를 만들지 않는다.
- Standard Flow에서 승인된 Verification Provider/Environment/Lifecycle을 임의 변경하지 않는다.
- Interactive Coder가 Kanban 없이 새 mutation request를 구현하지 않는다.
- 실행 카드의 `TASK_SESSION_HISTORY`는 append-only이며 여러 Session ID를 마지막 값 하나로 덮어쓰지 않는다.
- 상세 BLOCKED/retry/full-test/evidence 형식은 `references/implementation-details.md`를 따른다.