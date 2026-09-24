---
name: dev-breakdown
description: managed 프로젝트의 실제 코드·디자인 Reference·데이터 근거와 기존 project pattern으로 단일 Work Unit의 한국어 Implementation Plan을 생성하며 구현하지 않는 orchestrator 전용 skill.
version: 0.17.3
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, planning, analysis, breakdown, orchestrator, pattern, work-unit, java, kotlin, frontend, design-reference, image, figma, data, dbml, api, spec, infrastructure, runtime, host, port, container, env]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-tech-dispatch, dev-skill-preflight, dev-workspace-dispatch, dev-workflow-orchestrate, dev-java-guidelines, dev-kotlin-guidelines, dev-spring-feature, dev-spring-data, dev-frontend-feature, dev-design-reference, dev-data-feature, dev-db-migration, dev-api-spec, dev-api-contract, dev-infrastructure]
    requires_tools: [terminal, skill_view]
---

# dev-breakdown

요구사항을 실제 Repository evidence에 근거한 **한국어 Implementation Plan**으로 변환한다. 구현, commit, push, PR, destructive cleanup은 하지 않는다. 세부 유형별 checklist/출력 예시는 필요할 때만 `references/planning-details.md`를 읽는다.

## 계약

1. managed project metadata와 요구사항을 확인한다.
2. `skill_view("dev-project-pattern")`으로 Project Pattern Summary / Pattern References / technology cache를 재사용한다.
3. 필요한 source/test/config만 bounded read한다.
4. **Implementation Tasks를 만들기 전에 Work Unit Class/Boundary를 확정**한다.
5. API/Data/Infrastructure/Frontend 계약을 affected scope에 따라 분류한다.
6. Acceptance Criteria와 verification plan을 만들고 `READY | BLOCKED`를 출력한다.

`READY`는 구현 가능한 Plan 상태이며 사용자 승인이나 dispatch 완료를 의미하지 않는다.

## Standard Work Unit Boundary

필수 출력:

```text
Work Unit Class: DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT
Work Unit Boundary: SINGLE_UNIT | SPLIT_REQUIRED
Current Deliverable: ...
Follow-up Required: YES | NO
Follow-up Work Unit: ... | NONE
Follow-up Input: ... | NONE
Excluded Follow-up Scope: ... | NONE
```

여러 Skill 사용 != Task 분리다. 독립 승인 artifact가 다음 mutation phase의 authoritative input이면 별도 Work Unit으로 분리한다.

**Data DESIGN → MIGRATION 강제 분리**:
- 현재 DESIGN: logical model/DBML materialization까지만.
- `dev-db-migration`은 현재 DESIGN Applicable Skills에 넣지 않는다.
- physicalization은 승인 DBML을 입력으로 **별도 Standard Flow**의 MIGRATION Work Unit에서 수행한다.

API Spec Gate 자체는 자동으로 별도 Work Unit을 뜻하지 않는다. API 설계 자체가 독립 deliverable이면 DESIGN, 구현은 별도 Work Unit으로 분리한다.

## API Spec 계약

```text
API Spec Mode: DESIGN_FIRST | SOURCE_SYNC | AUDIT | NOT_REQUIRED
API Spec Gate: REQUIRED | NOT_REQUIRED
API Spec Status: DRAFT | APPROVED | NOT_REQUIRED
API Spec Path: <docs/api/<domain>.md | existing path | NONE>
API Spec Source: DESIGN | APPLICATION_SOURCE | ...
```

- DESIGN_FIRST → `dev-api-spec`, API Spec Gate REQUIRED.
- SOURCE_SYNC → existing Application Source를 DRAFT로 역문서화; `SOURCE_ONLY` 포함 상태를 기록.
- AUDIT → Source/Markdown/OpenAPI 차이 조사.
- Backend↔Frontend 동일 contract → `dev-api-contract`.
- API contract 의미 변경이 없으면 과도하게 DESIGN_FIRST로 승격하지 않는다.

## Data Model 계약

Data 변경은 `dev-data-feature`를 canonical entry로 사용한다.

```text
Data Design Mode: LOGICAL_RELATIONAL | PHYSICAL | QUERY_ONLY | ...
Data Model Gate: REQUIRED | NOT_REQUIRED
Data Model Status: DRAFT | APPROVED | NOT_REQUIRED
Data Task Class: MODEL_CHANGE | SCHEMA_CHANGE | MIGRATION | QUERY_ONLY | PERFORMANCE
DBML Path: docs/data/schema.dbml | existing path | NONE
Physicalization Required: YES | NO
```

Capability hints:
- logical model → `dev-data-modeling`
- physical schema rule → `dev-db-schema`
- query/SQL → `dev-db-query`
- migration → `dev-db-migration`
- performance → `dev-db-performance`

## Infrastructure Capability mapping

Runtime/topology/configuration 변경이면:

```text
Infrastructure Impact: YES
Applicable Skills:
- dev-infrastructure: runtime/topology/configuration canonical entry

Observed State:
- Application Runtime: ...
- Application Host: ... | unknown
- Database Runtime: ...
- Database Host: ... | unknown
- Database Port: ... | unknown

Desired State:
- Application Runtime: LOCAL_HOST | NETWORK_HOST | CONTAINER
- Database Runtime: LOCAL_HOST | NETWORK_HOST | CONTAINER
- Database Platform: NATIVE | SUPABASE
- Database Vendor: postgresql | mysql | mariadb | mssql | oracle | unknown
```

동일 runtime/vendor에서 host/port만 바뀌면 `HOST_CHANGE`. Supabase Auth/Client provider evidence만으로 DB Platform을 SUPABASE로 확정하지 않는다. 기존 Repository의 하드코딩 설정은 현재 요구 없이 migration scope에 자동 포함하지 않는다. DB Vendor 변경 + physicalization이면 `dev-db-migration`을 companion으로 고려한다.

## Kotlin 계획 규칙

Kotlin 프로젝트의 Kotlin 변경은 `dev-kotlin-guidelines`를 사용한다. compiler/language version, JVM target, kotlin-spring/kotlin-jpa, KSP/kapt, coroutine/reactive, Java interop evidence를 기존 project pattern에서 재사용한다.

Java 변경은 `dev-java-guidelines`, Spring 기능은 `dev-spring-feature`, JPA 구현은 `dev-spring-data`를 affected scope에 따라 Applicable Skills로 지정한다.

## Frontend Design Reference 계약

```text
Frontend Mode: REFERENCE_DRIVEN | CODE_DRIVEN
Design Source: IMAGE | FIGMA | EXISTING_CODE
Design Status: DRAFT | REFERENCE | APPROVED | N/A
Design Fidelity: STRUCTURE | VISUAL | HIGH | N/A
Reference: <repo path | Figma URL | current code>
Screen Spec: <path | none>
```

IMAGE/Figma면 `dev-design-reference`, Figma provider read가 필요할 때만 `dev-figma-design`을 hint로 사용한다.

## Frontend 계획 규칙

```text
Frontend Entry: dev-frontend-feature
Frontend Environment Gate: REQUIRED
Toolchain Mismatch Handling: BLOCK_AND_SPLIT_MIGRATION
pnpm Build Policy Source: pnpm-workspace.yaml
Build Approval Scope: package@exact-version
Build Approval Reuse: SAME_MATCHER_NO_REPROMPT
Build Approval Bootstrap: SINGLE_REVIEW_BATCH
Build Approval Discovery: RESTORE_OUTPUT_PLUS_PNPM_IGNORED_BUILDS
Verification Runtime: LINUX_ISOLATED_NODE_RUNTIME
View Strategy: SHARED | RESPONSIVE | HYBRID | SPLIT_VIEW
View Strategy Rationale
Platform Scope: DESKTOP | MOBILE | BOTH
Package / View Plan
Shared Implementation: api | model | state | hooks | common UI
Split Implementation: desktop/mobile presentation | NONE
Responsive / Breakpoint Source
Desktop/Mobile Verification Matrix
Storybook Catalog Plan: UPDATE | NOT_REQUIRED | NOT_AVAILABLE
Visual Verification: DESIGN_CONFORMANCE | VISUAL_REGRESSION | BOTH | NOT_REQUIRED
Regression Baseline: APPROVED_BROWSER_SCREENSHOT | EXISTING_PROJECT_BASELINE | NOT_REQUIRED
API Impact: NONE | SHARED_CONTRACT | CONTRACT_CHANGE
```

Frontend canonical Applicable Skill은 `dev-frontend-feature`. 필요 시 `dev-api-contract`, `dev-frontend-test`, `dev-ui-ux`를 hint로 추가한다. Node 기반 Frontend는 구현/검증 전에 Environment Gate가 필수이며 npm/yarn/bun 또는 pnpm 계약 미완성은 현재 기능 Task에서 자동 migration하지 않고 `PROJECT_TOOLCHAIN_MIGRATION_REQUIRED`로 분리한다. pnpm migration/dependency Work Unit에서 `ERR_PNPM_IGNORED_BUILDS`가 발생하는 경우 build-script 허용 결정 자체는 별도 Work Unit으로 쪼개지 않고 사용자 1회 승인 Gate로 처리한다. 첫 restore output과 isolated `pnpm ignored-builds`를 이용해 **현재 dependency graph의 미검토 matcher 전체를 먼저 수집**하고, package별 연속 BLOCK이 아니라 `SINGLE_REVIEW_BATCH` 하나로 승인/거부를 받는다. 승인 결과는 `pnpm-workspace.yaml > allowBuilds`에 exact package/version으로 기록하며 동일 matcher는 재승인하지 않는다. 동일 graph에서 batch 반영 후 새 matcher가 연속 발견되면 자동 반복하지 않고 discovery incomplete로 차단한다. 화면 차이만으로 Backend API를 superset DTO/중복 endpoint로 확대하지 않는다.

## 기존 Spring/JPA 정책 보존

기존 프로젝트 pattern을 우선한다. 공통 response/error contract를 재사용하고, 조회는 Method Query → QueryDSL → 근거 있는 Native Query 순서를 유지한다.

## 필수 출력

Task Identity; Project/working tree; Goal/Requirement; Assumptions/Out of Scope; Work Unit Contract; Project Pattern Summary; API/Data/Infrastructure/Frontend 계약(해당 시); Findings; Affected Areas; Implementation Tasks; Applicable Skills; Frontend Capability Hints; Data Capability Hints; Acceptance Criteria; Automated/Manual/Regression Test Plan; Dependencies; Risks; Open Questions; Dispatch Handoff; `READY | BLOCKED`와 이유.

상세 분석 절차와 출력 template은 `references/planning-details.md`를 따른다.
