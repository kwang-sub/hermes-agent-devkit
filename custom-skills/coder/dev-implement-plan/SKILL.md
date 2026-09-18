---
name: dev-implement-plan
description: Orchestrator가 승인·dispatch한 Direct 또는 Standard Kanban 단일 Work Unit을 할당 Workspace에서 구현·검증하고 항상 Reviewer에게 인계한다.
version: 0.24.2
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review, direct-flow, standard-flow, work-unit, capability, java, refactor, structural-quality, performance, infrastructure, runtime, container, env]
    related_skills: [dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review, dev-java-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-spring-refactor, dev-api-spec, dev-api-contract, dev-api-docs, dev-frontend-feature, dev-infrastructure, dev-data-feature, dev-data-modeling, dev-db-migration]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_block, kanban_heartbeat, skill_view]
---

# dev-implement-plan

Coder는 새 mutation request의 실행 방식을 선택하거나 self-dispatch하지 않고 Orchestrator가 생성한 Kanban Task만 수행한다. Direct/Standard Task 모두 `/opt/data/shared/references/standard-work-unit-rules.md`를 적용한다. 상세 절차·retry·verification 분류가 필요할 때만 `references/implementation-details.md`를 읽는다.

## 실행 순서

```text
kanban_show
→ Worker Context Gate 1회
→ verify_workspace.py 1회
→ Work Unit Boundary Gate
→ 필요한 source/test만 bounded read
→ 현재 Work Unit만 구현
→ targeted verification
→ IMPLEMENTATION_STABLE
→ 필요한 final regression
→ scoped change_summary.py
→ kanban_request_review | kanban_block
```

Workspace/Expected Branch/Base SHA와 Pattern References는 Task body를 재사용한다. 기존 변경은 preserve-first이며 reset/restore/clean/stash하지 않는다. Existing Changes Preservation Fast Path가 승인된 경우 repository-wide dirty/EOL/untracked scan을 반복하지 않는다.

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
- Frontend → `skill_view("dev-frontend-feature")`
- Infrastructure 영향이면 **첫 production patch 전에 반드시** `skill_view("dev-infrastructure")`
- Data → `skill_view("dev-data-feature")`
- MIGRATION → `skill_view("dev-db-migration")`

기존 파일은 preserve-first다. Infrastructure companion에서 Spring 설정은 `skill_view("dev-spring-feature")`, DB physicalization은 `skill_view("dev-data-feature")` + `skill_view("dev-db-migration")`을 사용한다.

구조 evidence는 `Structural quality check: PASS | REFACTORED | ESCALATED`로 남긴다.

## Verification / Handoff

Java/Gradle은 기존 toolchain과 canonical cached verification helper를 사용하고 동일 PASS fingerprint를 불필요하게 재실행하지 않는다. raw `./gradlew ...` 또는 `gradle ...` 직접 실행은 금지하며, 단순 bounded 진단이 필요하면 `hermes-java ./gradlew ...`, COMPILE/TARGETED_TEST는 `gradle_verification_cached.py`만 사용한다. 최종 scope 확정 후 **scoped change_summary.py**를 실행한다. Standard Flow에서 `--include` 없이 호출하지 않는다. 결과의 Changed Files와 verification evidence를 handoff한다.

```text
Work Unit Boundary Respected: true
Verification Final: true
Review Risk: REVIEW_REQUIRED
```

**Direct Flow, Standard Flow, CHANGES_REQUESTED 재작업은 모두 항상 review한다.** CHANGES_REQUESTED는 original coder가 동일 Workspace에서 blocking finding만 수정하고 다시 review한다. Direct/Standard Flow 모두 Coder self-complete 금지.

Terminal transition은 `kanban_request_review` 또는 `kanban_block` 중 정확히 하나다. 검증이 BLOCKED이면 residual risk로 넘기지 않고 차단한다.

## 공통 Coding Rules 핵심

`/opt/data/shared/references/coding-rules.md`를 적용한다. 기존 abstraction/pattern 재사용, 최소 scope, 기본 `2-depth`, 반복 I/O/N+1, 기존 response/error contract를 확인한다.

## 불변식

- Workspace 밖 수정, branch 전환, 다른 worktree 생성, commit, push, PR, merge 금지.
- secret/raw credential 기록 금지.
- Follow-up Work Unit 전용 capability를 현재 Task에서 실행하지 않는다.
- Interactive Coder가 Kanban 없이 새 mutation request를 구현하지 않는다.
- 상세 BLOCKED/retry/full-test/evidence 형식은 `references/implementation-details.md`를 따른다.
