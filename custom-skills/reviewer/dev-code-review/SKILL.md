---
name: dev-code-review
description: 동일 Workspace의 Direct/Standard 미커밋 구현을 requirement/AC와 Work Unit·project pattern·capability·구조 품질 계약 기준으로 독립 검토하고 승인·수정요청·차단한다.
version: 0.18.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, reviewer, kanban, quality, verification, direct-flow, standard-flow, work-unit, capability, lifecycle, java, refactor, structural-quality, performance]
    related_skills: [dev-implement-plan, dev-review-cycle, dev-workspace-dispatch, dev-java-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-spring-refactor, dev-frontend-feature, dev-data-feature, dev-data-modeling, dev-db-migration, dev-infrastructure, dev-api-spec, dev-api-contract, dev-api-docs]
    requires_tools: [terminal, kanban_show, kanban_request_changes, kanban_complete, kanban_block, kanban_heartbeat, skill_view]
---

# dev-code-review

Reviewer는 같은 Workspace의 미커밋 변경을 독립 검토하며 application/test/config source를 수정하지 않는다. 상세 severity/checklist/retry는 필요할 때만 `references/review-details.md`를 읽는다.

## 실행 계약

1. `kanban_show()`로 requirement/AC, Work Unit Contract, Pattern References, Applied Capability Skills, coder evidence를 읽는다.
2. Task의 Workspace Version Control을 읽고 `review_context.py --version-control <git|none> --include <Changed Files>`를 한 번 실행한다. Git이면 Base SHA/branch/scope fingerprint를 검증하고, Non-Git이면 Coder가 선언한 Changed Files만 범위로 사용한다. Git Workspace의 기존 `review_context.py --include <Changed Files>` scoped review 계약은 그대로 유지한다.
3. Git은 diff-first, Non-Git은 declared-files-first로 requirement/AC/correctness/compatibility/security/tests를 확인한다.
4. Capability와 verification evidence를 필요한 범위에서만 검증한다.
5. P0/P1이면 `kanban_request_changes`, 충분하면 `kanban_complete`, 판단 불가/외부 결정/반복 blocker면 `kanban_block` 중 정확히 하나를 실행한다.

Direct/Standard Flow에서는 scope 없는 review를 하지 않는다. Standard Flow에서는 `--include`를 반드시 제공한다. Git Workspace의 `--allow-full-scan`은 명시적 진단 전용이며 tracked와 untracked 모두 Git pathspec으로 제한한다. Non-Git Workspace는 자동 change discovery/snapshot을 하지 않고 Coder의 선언 scope만 검토한다.

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

Git Workspace에서는 Coder의 `Verification Final: true`, command/result, verification/effective scope fingerprint, `Work Unit Boundary Respected: true`가 실제 diff와 일치하면 PASS evidence를 재사용한다. 동일 scope PASS를 독립성 확보만을 이유로 반복 실행하지 않는다. Non-Git Workspace에는 fingerprint 재사용 Gate가 없으므로 선언된 변경 파일을 직접 읽고 필요한 최소 verification을 fresh 실행한다.

Coder PASS 이후 executable source/test/build/toolchain이 바뀌었거나 fingerprint/evidence가 불일치하면 fresh verification을 요구한다. `GRADLE_STATUS=BLOCKED`를 같은 primary command로 우회 재시도하지 않는다.

Java/Gradle 재검증은 `hermes-java` 기반 cached helper를 사용하고 임의 JDK/host Java로 우회하지 않는다. raw `./gradlew ...` 또는 `gradle ...` 직접 실행도 금지하며, fresh verification이 필요하면 동일 canonical cached helper를 사용한다.

## Common Coding Review Gate

`/opt/data/shared/references/coding-rules.md`와 project pattern을 기준으로 기존 abstraction 재사용, scope, 기본 `2-depth`, 반복 I/O/N+1, API response/error, JPA query 선택, test adequacy를 확인한다. Style/nit만으로 승인을 막지 않는다.

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
- 상세 checklist/escalation은 `references/review-details.md`를 따른다.
