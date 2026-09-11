---
name: dev-breakdown
description: managed 프로젝트의 실제 코드·디자인·데이터 근거와 기존 project pattern으로 한국어 Implementation Plan을 생성하며 구현하지 않는 orchestrator 전용 skill.
version: 0.12.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, planning, analysis, breakdown, orchestrator, pattern, java, kotlin, frontend, figma, data, dbml, api, spec]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-tech-dispatch, dev-skill-preflight, dev-workspace-dispatch, dev-workflow-orchestrate, dev-java-guidelines, dev-kotlin-guidelines, dev-frontend-feature, dev-data-feature, dev-api-spec]
    requires_tools: [terminal, skill_view]
---

# dev-breakdown

요구사항을 Coder가 실행 가능한 근거 기반 한국어 계획으로 바꾸는 read-only 단계다. source/config 수정, dependency 설치, workspace/branch/Kanban 생성, commit/push/reset/restore/clean/stash를 하지 않는다.

## 계약

1. `<repo>/.hermes/project.yaml`을 읽고 Project/Repository/Board/Base/Profiles를 검증한다.
2. `skill_view("dev-project-pattern")`으로 전체 pattern 계약을 읽고 Foundation references를 적용한다.
3. project pattern 결과의 Detected Stacks, Database Vendor Candidates, Pattern References, Design Source, Applicable Skills, Frontend/Data Capability Hints를 재사용한다.
4. targeted search로 source/call flow/config/tests/similar code만 확인하고 repository 전체 재분석을 피한다.
5. Goal/Constraints/In-Out Scope/minimum affected areas를 정한다. product intent를 추측하지 않는다.
6. 중요한 assumption은 source evidence로 닫고, product/architecture/design/data model 승인 결정이 필요하면 Open Question으로 남긴다.
7. 최대 7개 Implementation Tasks를 변경·근거·완료조건·verification과 함께 순서화한다.
8. Java 프로젝트의 Java 변경은 `dev-java-guidelines`, **Kotlin 프로젝트의 Kotlin 변경은 `dev-kotlin-guidelines`**, Spring 변경은 기존 `dev-spring-*` capability를 Applicable Skills에 지정한다. Java + Kotlin mixed project에서는 실제 affected source 언어에 따라 둘을 함께 또는 각각 적용한다.
9. Frontend Task는 `dev-frontend-feature`를 canonical Applicable Skill로 지정하고 하위 Skill은 `Frontend Capability Hints`로만 전달한다.
10. Data 모델/schema/SQL/migration/performance Task는 `dev-data-feature`를 canonical Applicable Skill로 지정하고 하위 Skill은 `Data Capability Hints`로 전달한다. 승인된 기존 schema의 단순 JPA 구현은 기존 `dev-spring-data`만 사용할 수 있다.
11. Backend API와 Frontend가 함께 바뀌는 Task는 Frontend Capability Hints에 `dev-api-contract`를 포함한다.
12. API endpoint 신규/변경/문서화/감사 작업은 `dev-api-spec`을 적용하고 API Spec Mode/Gate/Status/Path/Source를 계획에 명시한다.
13. Figma URL이 있으면 Design Source/Status/Figma URL/Frontend Mode를 보존하며 `APPROVED`만 FIGMA_DRIVEN으로 확정한다. 이 경우 Frontend Capability Hints에 `dev-figma-design`을 포함한다.
14. data model/schema 의미 변경이면 아래 Data Model 계약을 계획에 보존한다.
15. `Applicable Skills`에 추정 이름을 만들지 않는다. runtime pin 가능 여부는 dispatch 직전 `dev-skill-preflight`가 검증한다.
16. testable Acceptance Criteria와 risk-based Test Plan, Dependencies, Risks, Open Questions를 작성한다.
17. project/repo·scope·pattern·AC·tasks·test·필요한 design/API/data model approval이 확립될 때만 `READY`, 아니면 `BLOCKED`다.

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

`DESIGN_FIRST`이면 Plan Approval에서 spec 초안을 명시적으로 승인한다. `SOURCE_SYNC`는 Application Source 역문서화이며 자동 APPROVED로 승격하지 않는다.

`AUDIT`은 기본 read-only이며 결과를 다음 중 하나로 남긴다.

```text
IN_SYNC | SOURCE_ONLY | SPEC_ONLY | CONTRACT_MISMATCH
```

기존 application source에는 endpoint가 있지만 Markdown specification이 없으면 `SOURCE_ONLY`로 분류하고, Task 범위 안에서 필요하면 `SOURCE_SYNC` 문서화를 계획한다.

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

### Data Capability mapping

```text
Applicable Skills:
- dev-data-feature: Data/DB canonical implementation entry

Data Capability Hints:
- dev-data-modeling: 책임/lifecycle/cardinality/DBML
- dev-db-schema: PK/FK/constraint/type/index
- dev-db-query: SQL semantics/dialect
- dev-db-migration: DDL/backfill/deployment compatibility
- dev-db-performance: execution plan/index/locking evidence
- dev-spring-data: JPA/Repository implementation companion
```

작업에 실제 필요한 hint만 남긴다.

### DBML Documentation

프로젝트가 기존 ERD/schema-as-code 표준을 갖고 있으면 그대로 사용한다. 없으면 기본 proposal은:

```text
docs/data/schema.dbml
```

이다. DBML Canvas는 IntelliJ Human Review View로 사용할 수 있지만 Plugin 설치를 Flow 전제조건으로 만들지 않는다.

## Kotlin 계획 규칙

Kotlin 변경이 포함되면 project pattern/technology cache에서 Kotlin/compiler version, JVM target, kotlin-spring/kotlin-jpa, KSP/kapt, blocking/reactive, Java interop evidence를 재사용한다.

language upgrade, compiler plugin 추가, kapt→KSP migration을 요구사항 없이 자동 포함하지 않는다.

## Frontend 계획 규칙

```text
Frontend Entry: dev-frontend-feature
Frontend Mode: FIGMA_DRIVEN | CODE_DRIVEN
Package Manager / Framework evidence
Existing Component/Token references
Frontend Capability Hints
Design Source / Status
Affected UI States
Responsive scope
API contract impact
Verification plan
```

Figma가 `APPROVED`이면 필요한 hint 예시는 다음과 같다.

```text
- dev-figma-design: approved selected frame/component evidence
- dev-ui-ux: responsive/accessibility/interaction quality gate
```

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

Task Identity; Project/working tree; Goal/Type/Requirement; Assumptions/Constraints/Out of Scope; Project Pattern Summary; Design Source/Status/Frontend Mode(해당 시); API Spec Mode/Gate/Status/Path/Source(해당 시); **Data Design Mode/Gate/Status/Task Class/Vendor/DBML Path(해당 시)**; Findings; Affected Areas; Implementation Tasks; Applicable Skills; Frontend Capability Hints; Data Capability Hints; Acceptance Criteria; Automated/Manual/Regression Test Plan; Dependencies; Risks; Open Questions; Dispatch Handoff; `READY | BLOCKED`와 이유.

유형별 상세 체크리스트와 출력 템플릿은 `references/planning-details.md`를 필요할 때만 읽는다.
