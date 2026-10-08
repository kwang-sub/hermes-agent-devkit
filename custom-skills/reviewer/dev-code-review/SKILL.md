---
name: dev-code-review
description: 동일 Workspace의 Direct/Standard 미커밋 구현을 requirement/AC와 Work Unit·project pattern·capability·구조 품질 계약 기준으로 독립 검토하고 승인·수정요청·차단한다.
version: 0.22.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, reviewer, kanban, quality, verification, direct-flow, standard-flow, work-unit, capability, lifecycle, java, refactor, structural-quality, performance]
    related_skills: [dev-implement-plan, dev-review-cycle, dev-workspace-dispatch, dev-java-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-spring-refactor, dev-frontend-feature, dev-data-feature, dev-data-modeling, dev-db-migration, dev-infrastructure, dev-api-spec, dev-api-contract, dev-api-docs]
    requires_tools: [terminal, kanban_show, kanban_comment, kanban_request_changes, kanban_complete, kanban_block, kanban_heartbeat, skill_view]
---

# dev-code-review

Reviewer는 같은 Workspace의 미커밋 변경을 독립 검토하며 application/test/config source를 수정하지 않는다. `/opt/data/shared/references/kanban-execution-boundary.md`의 `KANBAN_EXECUTION_BOUNDARY_V1`과 `/opt/data/shared/references/verification-level-policy.md`의 `VERIFICATION_LEVEL_POLICY_V1`에 따라 Kanban에서 requirement/AC/state/evidence를 읽되 launcher/timeout/retry/cache 같은 HOW는 Task body에서 재구성하지 않고 현재 role Skill과 canonical runtime/execution 정책을 사용한다. 상세 severity/checklist/retry는 필요할 때만 `references/review-details.md`를 읽는다.

## 실행 계약

1. `kanban_show()`로 requirement/AC, Work Unit Contract, Pattern References, Applied Capability Skills, coder evidence를 읽는다.
2. `/opt/data/shared/references/session-history-rules.md`의 `SESSION_HISTORY_BEST_EFFORT_V1`에 따라 `python3 /opt/devkit/bin/task_session_history.py capture --task-id "<Task ID>" --profile reviewer --profile-home /opt/data/profiles/reviewer --workspace "<Workspace>" --session-mode UNKNOWN --phase start`를 실행한다. 아래 공통 상태/receipt 정책을 적용한다.
3. Task별 인계는 먼저 저비용 Scope/EOL 검증을 통과해야 하며, Handoff/fingerprint 불일치 시 Maven/Gradle/pnpm 실행 전에 중단한다. 기존 Coder의 검증 결과를 자동 승인하지 않으며 검토 범위가 충분한지도 판단한다.\n3. Task의 Workspace Version Control을 읽고 `review_context.py --task-id "<Task ID>" --version-control <git|none> --include <Changed Files>`를 한 번 실행한다. Git이면 Base SHA/branch/scope fingerprint를 검증하고, Non-Git이면 Coder가 선언한 Changed Files만 범위로 사용한다. Git Workspace의 기존 `review_context.py --include <Changed Files>` scoped review 계약은 그대로 유지한다.
4. Git은 diff-first, Non-Git은 declared-files-first로 requirement/AC/correctness/compatibility/security/tests를 확인한다.
5. Capability와 verification evidence를 필요한 범위에서만 검증한다.
6. 미확인/comment 미완료이면 `SESSION_HISTORY_FINALIZE`를 적용한 뒤, P0/P1이면 `kanban_request_changes`, 충분하면 `kanban_complete`, 판단 불가/외부 결정/반복 blocker면 `kanban_block` 중 정확히 하나를 실행한다.

Direct/Standard Flow에서는 scope 없는 review를 하지 않는다. Standard Flow에서는 `--include`를 반드시 제공한다. Git Workspace의 `--allow-full-scan`은 명시적 진단 전용이며 tracked와 untracked 모두 Git pathspec으로 제한한다. Non-Git Workspace는 자동 change discovery/snapshot을 하지 않고 Coder의 선언 scope만 검토한다.

## Session History Review Gate — SESSION_HISTORY_BEST_EFFORT_V1

Standard / Direct / Recovery / CHANGES_REQUESTED에 동일한 `session-history-rules.md`를 적용한다. Reviewer는 자기 profile/session만 기록한다.

```text
TASK_SESSION_HISTORY
- Session ID: <actual session id>
- Profile: reviewer
- Mode: NEW | RESUME | UNKNOWN
```

- `captured`: `SESSION_HISTORY_COMMENT_PENDING`이면 기존 marker를 확인하고 없을 때만 `kanban_comment`한다. 성공/정확한 기존 marker 확인 후 `ack-comment --profile reviewer`한다. `SESSION_HISTORY_NEW=false`만으로 전달 성공을 가정하지 않는다.
- `unavailable` 또는 시작 시 `error` / captured marker·receipt 기록 오류: durable warning comment를 만들지 않고 `SESSION_HISTORY_RECHECK_REQUIRED=true`와 sanitized status/reason을 현재 reviewer 근거에 유지한 채 review를 계속한다. `invalid`는 context blocker다. 실제 승인·Workspace·검증 오류를 세션 경고로 바꾸지 않는다.

**SESSION_HISTORY_FINALIZE:** 미확인/comment 미완료일 때만 판정 확정 후 `kanban_complete` / `kanban_request_changes` / `kanban_block` 직전에 같은 reviewer context로 `capture --phase finalize`를 대기 없이 1회 실행한다. 이미 확인한 ID가 있으면 `--session-id`로 고정한다. 성공하면 같은 Task marker/receipt를 보완한다. 계속 미확인/추적 오류이거나 marker/receipt 보완이 실패하면 그때만 `TASK_SESSION_HISTORY_WARNING`을 최대 1회 durable comment로 남기고 verdict에 상태·원인을 보존한 뒤 원래 판정/차단 사유를 유지한다. 완료된 추적은 재조회하지 않으며 잘못된 실행 context에는 보완하지 않는다.

동일 `task_id + reviewer + session_id`는 중복 comment하지 않는다. Coder Session History를 덮어쓰거나 Reviewer ID로 Coder 누락을 대신 채우지 않는다. 새 Recovery 세션으로 과거 미확인 세션이 복구됐다고 기록하지 않는다.

## Recovery Revision Review Gate

`kanban_show()` comments에 `TASK_RECOVERY_REVISION_V<N>` 또는 `TASK_RECOVERY_RETRY_V<N>`가 있으면 Coder와 동일한 effective contract를 재구성한다.

```text
Effective Review Contract
= Original Task Contract
+ Latest Approved Recovery Revision의 명시적 delta
```

승인 Revision 조건:

```text
Recovery Gate: APPROVED
Recovery Mode: SAME_TASK_RESUME
Task: <현재 Task ID>
Original Contract: PRESERVED
Revision Authority: LATEST_APPROVED_RECOVERY_REVISION
```

가장 큰 `N`의 유효한 Revision만 사용한다. malformed latest marker, Task ID 불일치, Work Unit boundary를 실제로 바꾸는 delta는 `RECOVERY_CONTRACT_INVALID` finding으로 처리한다.

`RETRY_SAME_CONTRACT`는 Original Contract/AC를 그대로 검토한다. `REPLACEMENT_REQUIRED + Current Task: PRESERVE_BLOCKED` marker가 있는데 review에 진입했다면 lifecycle 위반으로 `kanban_block`한다.

Coder handoff의:

```text
Recovery Contract
Recovery Revision
Recovery Delta Applied
Recovery Acceptance Criteria
```

를 comments의 durable marker와 대조한다.

## Standard Work Unit Review Gate

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

Reviewer는 diff가 Current Deliverable과 Excluded Follow-up Scope를 넘었는지 본다. 여러 Skill 사용 자체를 split finding으로 만들지 않는다.

- DESIGN: Data logical design에 **Flyway/Liquibase migration** 또는 physical mapping/schema mutation이 섞이면 blocking.
- IMPLEMENTATION: 하나의 deliverable을 위한 여러 capability 조합 허용.
- MIGRATION: approved logical model/migration intent 기준으로 physicalization.
- REFACTOR: behavior/API/schema 의미 변경 금지.
- **AUDIT Task**: application/test/config source mutation은 blocking.

Follow-up Work Unit을 현재 Task에 구현하도록 요구하지 않는다.

## Verification Evidence Reuse

Git Workspace에서는 Coder의 `Verification Final: true`, `Verification Level`, command/result, verification/effective scope fingerprint, `Work Unit Boundary Respected: true`가 실제 diff와 일치하면 PASS evidence를 재사용한다. Reviewer는 독립성 확보만을 이유로 `STATIC_COMPILE`을 `PACKAGE_BUILD`로 승격하지 않으며, 더 높은 수준이 필요하면 build/dependency/packaging/deployment/framework build-time 영향 또는 uncovered P0/P1 behavior 근거를 명시한다. 동일 scope PASS를 독립성 확보만을 이유로 반복 실행하지 않는다. Coder의 `IMPACT_SUMMARY`는 review 탐색의 navigation evidence로 재사용하며, 실제 diff/requirement와 충돌하지 않는 한 같은 caller/history/security 범위를 repository-wide로 다시 탐색하지 않는다. 단, Impact Summary 자체가 diff보다 우선하는 source of truth는 아니다. Non-Git Workspace에는 fingerprint 재사용 Gate가 없으므로 선언된 변경 파일을 직접 읽고 필요한 최소 verification을 fresh 실행한다.

Coder PASS 이후 executable source/test/build/toolchain이 바뀌었거나 fingerprint/evidence가 불일치하면 fresh verification을 요구한다. `GRADLE_STATUS=BLOCKED`를 같은 primary command로 우회 재시도하지 않는다.

Maven 검증은 `/opt/data/shared/references/maven-worker-runtime.md`를 따른다. Coder의 `MAVEN_STATUS/MAVEN_BLOCKER/MAVEN_EVIDENCE`, `Verification Request SHA256`, `Verification Scope SHA256`와 변경 이후 최신 결과를 검토한다. 추가 검증이 필요하면 `/opt/custom-skills/coder/dev-implement-plan/scripts/maven_verification_cached.py`로 동일 `--scope-path`를 사용한다. scope가 동일하면 `VERIFICATION_EVIDENCE=REUSED`, `PRIMARY_REUSED=true`여야 하며 Maven primary를 다시 실행하지 않는다. raw `mvn`/`mvnw`/HOME cache 탐색으로 우회하지 않는다. launcher READY 또는 compile PASS를 승인된 실제 HTTP 검증 완료로 간주하지 않는다.

Java/Gradle 재검증은 `hermes-java` 기반 cached helper를 사용하고 임의 JDK/host Java로 우회하지 않는다. raw `./gradlew ...` 또는 `gradle ...` 직접 실행도 금지하며, fresh verification이 필요하면 동일 canonical cached helper를 사용한다.

## Common Coding Review Gate

`/opt/data/shared/references/coding-rules.md`와 project pattern을 기준으로 기존 abstraction 재사용, scope, 기본 `2-depth`, 반복 I/O/N+1, API response/error, JPA query 선택, test adequacy를 확인한다. 변경된 executable source의 logging call에 한글 등 비영어 자연어 로그 메시지가 있으면 공통 Coding Rule 위반으로 수정 요청한다. 사용자 UI/localized response/문서/주석은 로그 언어 Gate로 판정하지 않는다. 그 외 Style/nit만으로 승인을 막지 않는다.

## Capability Lifecycle Review Gate

source of truth는 `capability-lifecycle.json`이다. Task/diff에 해당하는 capability만 `skill_view`한다.

```text
dev-spring-feature
dev-spring-data
dev-frontend-feature
dev-data-feature
dev-db-migration
dev-infrastructure
dev-api-spec
dev-api-contract
```

`strict_pin=true` applicable capability가 validated/pinned skill에서 누락되면 Dispatch Preflight 계약 위반이다.

## Java Convention Review Gate

Java diff에서 필요하면 `dev-java-guidelines`를 적용해 target version, convention, type 배치, JavaDoc 품질을 확인한다.

## Structural Quality Review Gate

`dev-spring-refactor`의 관점으로 책임 혼재, raw payload/persistence/external I/O 결합, behavior-preserving verification을 본다. Coder의 `Structural Quality/Javadoc evidence`를 실제 diff와 대조한다. architecture/API/schema 변경이 필요한 개선은 현재 Work Unit을 넘어가면 follow-up으로 분리한다.

## Stack / Capability Review Gate

Reviewer가 별도 stack/capability 목록을 source of truth로 만들지 않는다. Task/diff와 lifecycle registry만 사용한다.

## Verdict

```text
P0/P1 + coder 수정 가능 → kanban_request_changes
P0/P1 없음 + evidence 충분 → kanban_complete
판단 불가/외부 결정/동일 blocker 3회 → kanban_block(kind=needs_input...)
```

CHANGES_REQUESTED는 original coder가 같은 Workspace에서 수정한다.

## 불변식

- Reviewer는 source를 수정하지 않는다.
- secret/raw credential 출력 금지.
- commit, push, PR, cleanup 금지.
- EOL-only noise는 finding이 아니다.
- finding은 file/symbol, evidence, required change, expected verification을 포함한다.
- Direct/Standard Task는 모두 Reviewer가 검토한다.
- Recovery Task는 Original Contract와 Latest Approved Recovery Revision의 명시적 delta를 합성해 검토하며, Recovery comment 전체를 Task body 대체로 간주하지 않는다.
- Reviewer Session History는 append-only이며 Coder/기존 reviewer Session marker를 덮어쓰지 않는다.
- 상세 checklist/escalation은 `references/review-details.md`를 따른다.
