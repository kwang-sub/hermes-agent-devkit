---
name: dev-breakdown
description: managed 프로젝트의 실제 코드·디자인 Reference·데이터 근거와 기존 project pattern으로 단일 Work Unit의 한국어 Implementation Plan을 생성하며 구현하지 않는 orchestrator 전용 skill.
version: 0.17.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, planning, analysis, breakdown, orchestrator, pattern, work-unit, java, kotlin, frontend, design-reference, image, figma, data, dbml, api, spec, infrastructure, runtime, host, port, container, env]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-tech-dispatch, dev-skill-preflight, dev-workspace-dispatch, dev-workflow-orchestrate, dev-java-guidelines, dev-kotlin-guidelines, dev-spring-feature, dev-spring-data, dev-frontend-feature, dev-design-reference, dev-data-feature, dev-db-migration, dev-api-spec, dev-api-contract, dev-infrastructure]
    requires_tools: [terminal, skill_view]
---

# dev-breakdown

요구사항을 Coder가 실행 가능한 근거 기반 **한국어 Implementation Plan**으로 바꾸는 read-only 단계다. source/config 수정, dependency 설치, workspace/branch/Kanban 생성, commit/push/reset/restore/clean/stash를 하지 않는다.

Standard Flow Plan은 `/opt/data/shared/references/standard-work-unit-rules.md`를 적용해 **한 Task = 한 주 Work Unit** 경계를 먼저 확정한다.

## 계약

1. `<repo>/.hermes/project.yaml`을 읽고 Project/Repository/Board/Base/Profiles를 검증한다.
2. `skill_view("dev-project-pattern")`으로 전체 pattern 계약을 읽고 Foundation references를 적용한다.
3. project pattern 결과의 Detected Stacks, Database Vendor Candidates, Pattern References, Design Source, Applicable Skills, Frontend/Data Capability Hints를 재사용한다.
4. targeted search로 source/call flow/config/tests/similar code만 확인하고 repository 전체 재분석을 피한다.
5. Goal/Constraints/In-Out Scope/minimum affected areas를 정한다. product intent를 추측하지 않는다.
6. 중요한 assumption은 source evidence로 닫고, product/architecture/design/data model 승인 결정이 필요하면 Open Question으로 남긴다.
7. **Implementation Tasks를 만들기 전에 Work Unit Class/Boundary를 확정한다.** 원 요청이 여러 독립 phase를 포함하면 현재 Plan에는 첫 Work Unit만 남기고 후속 phase는 Follow-up metadata로 분리한다.
8. 현재 Work Unit 안에서 최대 7개 Implementation Tasks를 변경·근거·완료조건·verification과 함께 순서화한다.
9. Java 프로젝트의 Java 변경은 `dev-java-guidelines`, Kotlin 프로젝트의 Kotlin 변경은 `dev-kotlin-guidelines`, Spring 변경은 기존 `dev-spring-*` capability를 Applicable Skills에 지정한다. Java + Kotlin mixed project에서는 실제 affected source 언어에 따라 둘을 함께 또는 각각 적용한다.
10. Frontend Task는 `dev-frontend-feature`를 canonical Applicable Skill로 지정하고 하위 Skill은 `Frontend Capability Hints`로만 전달한다. IMAGE/Figma Reference가 있으면 `dev-design-reference`를 hint에 포함한다.
11. Data 모델/schema/SQL/migration/performance Task는 `dev-data-feature`를 canonical Applicable Skill로 지정한다. Data DESIGN Task와 physical MIGRATION Task는 같은 Plan에 넣지 않는다. 승인된 기존 schema의 단순 JPA 구현은 기존 `dev-spring-data`만 사용할 수 있다.
12. Docker/Compose, Application/DB runtime·host·network, 환경변수 전달 경로, Supabase runtime/platform 등 실행 위치와 연결 토폴로지가 바뀌는 Task는 `dev-infrastructure`를 canonical Applicable Skill로 지정한다. Spring/Frontend/Data 변경이 같은 Work Unit의 단일 deliverable에 필요하면 companion으로 함께 지정할 수 있다.
13. Backend API와 Frontend가 함께 바뀌는 Task는 Frontend Capability Hints에 `dev-api-contract`를 포함한다.
14. API endpoint 신규/변경/문서화/감사 작업은 `dev-api-spec`을 적용하고 API Spec Mode/Gate/Status/Path/Source를 계획에 명시한다.
15. Frontend 디자인 입력은 `REFERENCE_DRIVEN | CODE_DRIVEN`으로 일반화하고 `IMAGE | FIGMA | EXISTING_CODE` source를 구분한다.
16. data model/schema 의미 변경이면 아래 Data Model 계약을 계획에 보존한다.
17. Storybook/Playwright는 기존 project evidence가 있을 때만 계획에 활용한다. 화면 구현만을 이유로 자동 dependency 추가를 계획하지 않는다.
18. `Applicable Skills`에 추정 이름을 만들지 않는다. runtime pin 가능 여부는 dispatch 직전 `dev-skill-preflight`가 검증한다.
19. testable Acceptance Criteria와 risk-based Test Plan, Dependencies, Risks, Open Questions를 작성한다.
20. project/repo·Work Unit boundary·scope·pattern·AC·tasks·test·필요한 design/API/data model/Infrastructure approval이 확립될 때만 `READY`, 아니면 `BLOCKED`다.

## Standard Work Unit Boundary

모든 Standard Plan은 다음을 포함한다.

```text
Work Unit Class: DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT
Work Unit Boundary: SINGLE_UNIT | SPLIT_REQUIRED
Current Deliverable: ...
Follow-up Required: YES | NO
Follow-up Work Unit: DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT | NONE
Follow-up Input: ... | NONE
Excluded Follow-up Scope: ... | NONE
```

분리 기준은 **Skill 수나 파일 수가 아니라 독립 산출물의 lifecycle**이다.

```text
현재 단계가 독립 승인 가능한 artifact/decision을 생성
+ 그것이 다음 mutation 단계의 authoritative input
+ 다음 단계가 application/runtime/schema/data를 실제 변경
→ SPLIT_REQUIRED
```

여러 Skill을 사용해도 하나의 deliverable을 완성하는 경우는 한 Work Unit으로 유지한다.

```text
Docker Compose + Spring datasource env 연결
Backend + Frontend가 하나의 승인 API contract를 구현
여러 파일/모듈의 동일 use case 변경
→ SINGLE_UNIT 가능
```

`SPLIT_REQUIRED`여도 현재 Plan은 첫 Work Unit만 READY로 만든다. Follow-up Work Unit을 현재 Implementation Tasks에 넣지 않는다.

### Work Unit 분류 기본값

```text
독립 설계/모델/계약 산출물 자체가 목표 → DESIGN
승인 요구/설계를 실제 behavior/runtime로 구현 → IMPLEMENTATION
승인 schema/data intent physicalization → MIGRATION
behavior-preserving 구조 개선 → REFACTOR
read-only 조사/차이 분석 → AUDIT
```

Audit에서 수정 필요성이 발견되어도 같은 Task에 fix를 자동 추가하지 않는다. 처음부터 작고 명확한 fix가 주 목적이면 AUDIT가 아니라 IMPLEMENTATION으로 분류한다.

## API Spec 계약

```text
API Spec Mode: DESIGN_FIRST | SOURCE_SYNC | AUDIT | NOT_REQUIRED
API Spec Gate: REQUIRED | NOT_REQUIRED
API Spec Status: DRAFT | APPROVED | NOT_REQUIRED
API Spec Path: <planned/existing markdown path | none>
API Spec Source: DESIGN | APPLICATION_SOURCE | MIGRATED_SPEC | none
```

```text
신규 endpoint 또는 method/path/request/response/error 의미 변경 → DESIGN_FIRST
기존 endpoint의 누락 Markdown 문서화 → SOURCE_SYNC
Source ↔ Markdown ↔ OpenAPI 차이 조사 → AUDIT
API contract 영향 없음 → NOT_REQUIRED
```

`DESIGN_FIRST`이면 `API Spec Gate: REQUIRED`, 최초 `API Spec Status: DRAFT`다. Plan Approval 전에 Markdown 규격 초안을 사용자에게 보여주되 source를 수정하지 않는다.

API Spec Gate는 항상 별도 Work Unit을 뜻하지 않는다.

```text
하나의 구현 use case에 종속된 bounded API contract
→ Work Unit Class: IMPLEMENTATION
→ API 규격 승인 후 같은 Task에서 구현 가능

API 설계 자체가 사용자 요청의 독립 deliverable이거나 여러 후속 consumer가 재사용
→ Work Unit Class: DESIGN
→ 후속 구현은 별도 IMPLEMENTATION Work Unit
```

`SOURCE_SYNC`는 Application Source 역문서화이며 `Status: DRAFT`, `Documentation Source: APPLICATION_SOURCE`를 유지하고 자동 APPROVED로 승격하지 않는다.

`AUDIT`은 기본 read-only이며 결과를 다음 중 하나로 남긴다.

```text
IN_SYNC | SOURCE_ONLY | SPEC_ONLY | CONTRACT_MISMATCH
```

기존 application source에는 endpoint가 있지만 Markdown specification이 없으면 `SOURCE_ONLY`로 분류하고, Task 범위 안에서 필요하면 `SOURCE_SYNC` 문서화를 계획한다. 전체 API 스캔은 사용자가 명시적으로 전체 감사를 요청한 경우에만 허용한다.

## Data Model 계약

의미 있는 데이터 모델 변경은 다음을 계획에 명시한다.

```text
Data Design Mode: DESIGN_FIRST | SOURCE_SYNC | QUERY_ONLY | PERFORMANCE | NOT_REQUIRED
Data Model Gate: REQUIRED | NOT_REQUIRED
Data Model Status: DRAFT | APPROVED | NOT_REQUIRED
Data Task Class: MODEL_CHANGE | SCHEMA_CHANGE | QUERY_ONLY | MIGRATION | PERFORMANCE | NOT_REQUIRED
Database Vendor: generic | mssql | mysql | mariadb | postgresql | oracle | unknown
Data Model Mode: LOGICAL_RELATIONAL | PHYSICAL
DBML Mode: CANONICAL | PROJECT_EXISTING | NOT_REQUIRED
DBML Path: <planned/existing path | none>
Physicalization Required: YES | NO
```

### Data Model Gate REQUIRED

기본 대상:

```text
새 table
relationship/cardinality 변경
PK/FK/UNIQUE 의미 변경
nullable 의미 변경
Current/History/Snapshot 책임 변경
ownership/lifecycle 변경
```

`DESIGN_FIRST`이면 Orchestrator는 실제 파일을 수정하지 않고 Plan 안에 table/relationship/DBML proposal 또는 diff를 제시한다. 사용자가 해당 proposed model을 포함한 Plan을 승인하면 기존 Plan Approval로 Data Model Gate도 함께 충족할 수 있으므로 별도 중복 질문을 만들지 않는다.

`DRAFT`를 임의로 `APPROVED`로 승격하지 않는다.

### Data DESIGN → MIGRATION 강제 분리

`MODEL_CHANGE` 또는 `SCHEMA_CHANGE`의 logical design이 필요한 경우 현재 Task는 다음으로 고정한다.

```text
Work Unit Class: DESIGN
Current Deliverable: approved/materialized logical DBML
Applicable Skills:
- dev-data-feature
Data Capability Hints:
- dev-data-modeling
```

`Physicalization Required: YES`이면:

```text
Work Unit Boundary: SPLIT_REQUIRED
Follow-up Required: YES
Follow-up Work Unit: MIGRATION
Follow-up Input: approved/materialized logical DBML
Excluded Follow-up Scope: Flyway/Liquibase, DDL, physical schema, JPA physical mapping
```

현재 DESIGN Plan의 Applicable Skills/Implementation Tasks에 `dev-db-migration`을 넣지 않는다. DBML materialization과 `dbml_guard`까지 완료한 뒤 Task를 종료한다.

후속 physical implementation 요청은 별도 Standard Flow다.

```text
Work Unit Class: MIGRATION
Applicable Skills:
- dev-data-feature
- dev-db-migration
Data Capability Hints:
- dev-db-schema
- dev-spring-data (실제 JPA mapping 영향이 있을 때)
```

MIGRATION Task는 repository canonical DBML 또는 별도 승인 artifact snapshot을 authoritative input으로 사용한다. logical responsibility/cardinality redesign이 필요해지면 migration scope를 확장하지 않고 새 DESIGN Work Unit으로 되돌린다.

### 기타 Data Capability mapping

```text
QUERY_ONLY → dev-data-feature + dev-db-query
PERFORMANCE → dev-data-feature + dev-db-performance
승인된 기존 schema의 JPA 구현 → dev-spring-data
```

작업에 실제 필요한 hint만 남긴다.

### DBML Documentation

프로젝트가 기존 ERD/schema-as-code 표준을 갖고 있으면 그대로 사용한다. 없으면 기본 proposal은:

```text
docs/data/schema.dbml
```

이다. DBML Canvas는 IntelliJ Human Review View로 사용할 수 있지만 Plugin 설치를 Flow 전제조건으로 만들지 않는다.

## Infrastructure Capability mapping

다음 변화가 실제 Task scope에 있으면 `Infrastructure Impact: YES`다.

```text
Dockerfile / Compose / containerization
Application Runtime: LOCAL_HOST | NETWORK_HOST | CONTAINER 전환
Application host 변경
Database Runtime: LOCAL_HOST | NETWORK_HOST | CONTAINER 전환
DB host / port / network / service DNS / volume 변경
.env / container environment / remote runtime environment 전달 경로 변경
Supabase Local ↔ Cloud 또는 NATIVE ↔ SUPABASE platform/runtime 변경
```

단순 Spring business code, 일반 frontend UI, DB schema/query만 바뀌고 위 실행 토폴로지 변화가 없으면 Infrastructure로 과도하게 승격하지 않는다.

Infrastructure Task는 계획에 다음을 남긴다.

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
- Database Platform: NATIVE | SUPABASE | UNKNOWN
- Database Vendor: ... | unknown

Desired State:
- Application Runtime: LOCAL_HOST | NETWORK_HOST | CONTAINER
- Application Host: ... | unknown
- Database Runtime: LOCAL_HOST | NETWORK_HOST | CONTAINER
- Database Host: ... | unknown
- Database Port: ... | unknown
- Database Platform: NATIVE | SUPABASE
- Database Vendor: postgresql | mysql | mariadb | mssql | oracle | unknown

Configuration Delivery:
- Spring LOCAL_HOST: IntelliJ | OS_ENV
- Next.js LOCAL_HOST: .env.local
- CONTAINER: COMPOSE_ENV | container environment
- NETWORK_HOST: REMOTE_RUNTIME_ENV
```

Observed State는 Repository evidence가 없는 값을 기본값으로 채우지 않는다. 증거가 없으면 `UNKNOWN/unknown`이다. Desired State만 사용자 요구/기존 metadata/기본 정책을 사용할 수 있다.

`NEXT_PUBLIC_SUPABASE_URL` 또는 일반 `SUPABASE_URL`만 존재하는 것은 Supabase Auth/Client provider evidence일 수 있으므로 Database Platform을 `SUPABASE`로 확정하는 근거로 사용하지 않는다. Supabase DB 전환은 명시적 요구, `supabase/config.toml`, 명확한 DB connection contract 같은 강한 evidence를 요구한다.

동일 runtime/vendor에서 host 또는 port만 바뀌면 `HOST_CHANGE`로 계획한다. runtime/platform/vendor 변경과 함께 발생하면 `COMBINED_CHANGE`다.

Companion capability는 같은 Work Unit의 Current Deliverable에 실제 필요한 경우에만 추가한다.

```text
Spring application.yml|yaml|properties 또는 Spring connection 설정 변경
→ dev-spring-feature

Frontend .env / Next.js runtime env 변경
→ dev-frontend-feature
→ Next.js-specific 변경이면 dev-nextjs-feature hint

DB Vendor 변경 + 실제 physicalization Task
→ dev-data-feature
→ dev-db-migration
```

기존 Repository의 하드코딩 설정은 Bootstrap security warning만으로 migration scope에 자동 포함하지 않는다. 사용자가 설정 외부화를 요구하거나 이번 Task에서 해당 설정을 새로 만들거나 변경해야 할 때만 `${ENV_VAR}` / `.env.example` 계약을 Implementation Task에 포함한다.

## Kotlin 계획 규칙

Kotlin 변경이 포함되면 project pattern/technology cache에서 Kotlin/compiler version, JVM target, kotlin-spring/kotlin-jpa, KSP/kapt, blocking/reactive, Java interop evidence를 재사용한다.

Implementation Plan에는 Kotlin language upgrade, compiler plugin 추가, kapt→KSP migration을 요구사항 없이 자동 포함하지 않는다. `!!`, Entity `data class`, coroutine/Flow, value class boundary, annotation use-site target 변화가 실제 scope에 들어가면 위험과 검증 근거를 명시한다.

## Frontend Design Reference 계약

Frontend 디자인 입력은 다음 계약으로 보존한다.

```text
Frontend Mode: REFERENCE_DRIVEN | CODE_DRIVEN
Design Source: IMAGE | FIGMA | EXISTING_CODE
Design Status: DRAFT | REFERENCE | APPROVED | N/A
Design Fidelity: STRUCTURE | VISUAL | HIGH | N/A
Reference: <repo image path | selected Figma URL | current code>
Screen Spec: <path | none>
View Strategy: SHARED | RESPONSIVE | HYBRID | SPLIT_VIEW | N/A
Platform Scope: DESKTOP | MOBILE | BOTH | N/A
```

판정:

```text
IMAGE + APPROVED
→ stable GitHub Reference Package와 Screen Spec을 구현 기준으로 사용

FIGMA + APPROVED
→ REFERENCE_DRIVEN
→ dev-design-reference + dev-figma-design hint

REFERENCE
→ 방향 참고. exact source of truth 아님

DRAFT
→ planning only. 구현 기준으로 임의 승격 금지

외부 authoritative Reference 없음
→ CODE_DRIVEN + EXISTING_CODE
```

현재 Task가 새 UI 설계 자체를 독립 deliverable로 만드는 경우 `DESIGN`으로 분류하고 후속 구현과 분리한다. 이미 승인된 IMAGE/Figma를 입력으로 구현하는 경우는 `IMPLEMENTATION` Work Unit에서 그대로 사용할 수 있다.

## Frontend 계획 규칙

```text
Frontend Entry: dev-frontend-feature
Frontend Mode: REFERENCE_DRIVEN | CODE_DRIVEN
Design Source / Status / Fidelity
Reference / Screen Spec
View Strategy: SHARED | RESPONSIVE | HYBRID | SPLIT_VIEW
View Strategy Rationale
Platform Scope: DESKTOP | MOBILE | BOTH
Section Overrides: <section=strategy | NONE>
Package Manager / Framework evidence
Existing Package / Component / Token references
Package / View Plan
Shared Implementation: api | model | state | hooks | common UI
Split Implementation: desktop/mobile presentation | NONE
Responsive / Breakpoint Source
Frontend Capability Hints
Observed / Inferred / Unknown
Affected UI States: loading | empty | error | populated (해당 시)
API Impact: NONE | SHARED_CONTRACT | CONTRACT_CHANGE
Storybook Catalog Plan: UPDATE | NOT_REQUIRED | NOT_AVAILABLE
Visual Verification: DESIGN_CONFORMANCE | VISUAL_REGRESSION | BOTH | NOT_REQUIRED
Desktop/Mobile Verification Matrix
Regression Baseline: APPROVED_BROWSER_SCREENSHOT | EXISTING_PROJECT_BASELINE | NOT_REQUIRED
Verification plan
```

`DESIGN_CONFORMANCE`는 Approved IMAGE/Figma Reference와 최초 구현의 구조·배치·visual intent 일치를 확인한다. `VISUAL_REGRESSION`은 승인된 실제 browser screenshot을 이후 golden으로 사용하는 회귀 검증이다. Design Reference PNG를 장기 regression golden과 동일시하지 않는다.

Desktop/Mobile이 모두 scope이면 View Strategy를 구현 전에 확정한다. 기존 project package/component/state/API convention을 먼저 사용하고, 없을 때만 `dev-frontend-feature`의 feature-first 기본 구조를 적용한다.

```text
SHARED / RESPONSIVE
→ presentation tree 공유 우선

HYBRID
→ common shell/data/state + 필요한 section만 platform split

SPLIT_VIEW
→ DesktopView / MobileView 분리
→ API/model/state/business/data hook은 기본 공유
```

화면 차이만으로 Backend API를 desktop/mobile superset DTO 또는 중복 endpoint로 확대하지 않는다. 실제 use case/data-volume/security/performance 차이로 contract 변경이 필요할 때만 API Spec Gate를 재평가한다.

예:

```text
Applicable Skills:
- dev-frontend-feature: Frontend canonical implementation entry

Frontend Capability Hints:
- dev-design-reference: APPROVED IMAGE/Figma evidence 정규화
- dev-typescript-guidelines: API/UI type change
- dev-nextjs-feature: App Router page/component change
- dev-frontend-test: Storybook/Playwright visual verification
- dev-ui-ux: responsive/accessibility/chart quality gate
- dev-api-contract: Backend DTO와 frontend type 동시 변경
```

Figma인 경우에만 추가로 `dev-figma-design` hint를 사용한다.

## 기존 Spring/JPA 정책 보존

```text
기존 프로젝트 pattern 최대 유지
공통 Response 규격 재사용
단순 JPA 조회 → Spring Data JPA Method Query 우선
복잡/동적 조회 → QueryDSL 우선
Native Query → 앞 방식으로 해결하기 어려운 근거가 있을 때만
```

DBML/schema 자체를 설계하지 않는 순수 JPA 구현까지 `dev-data-feature`로 과도하게 승격하지 않는다.

## 필수 출력

Task Identity; Project/working tree; Goal/Type/Requirement; Assumptions/Constraints/Out of Scope; **Work Unit Class/Boundary/Current Deliverable/Follow-up Required/Follow-up Work Unit/Follow-up Input/Excluded Follow-up Scope**; **Project Pattern Summary**; Frontend Mode/Design Source/Status/Fidelity/Reference/Screen Spec/**View Strategy/Platform Scope/Package-View Plan/Shared-Split Implementation/API Impact/Desktop-Mobile Verification Matrix**(해당 시); **API Spec Mode/Gate/Status/Path/Source(해당 시)**; **Data Design Mode/Gate/Status/Task Class/Vendor/DBML Path/Physicalization Required(해당 시)**; **Infrastructure Impact/Observed State/Desired State/Configuration Delivery(해당 시, host/port 포함)**; Findings; Affected Areas; Implementation Tasks; Applicable Skills; Frontend Capability Hints; Data Capability Hints; Observed/Inferred/Unknown(해당 시); Storybook/Visual Verification Plan(해당 시); Acceptance Criteria; Automated/Manual/Regression Test Plan; Dependencies; Risks; Open Questions; Dispatch Handoff; `READY | BLOCKED`와 이유.

유형별 상세 체크리스트와 출력 템플릿은 `references/planning-details.md`를 필요할 때만 읽는다.
