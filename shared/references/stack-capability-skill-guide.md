# Stack / Capability Skill Extension Guide

이 문서는 `coding-rules.md`, `implementation-decision-rules.md`, `project-pattern-rules.md`, 데이터 작업에서는 `data-design-rules.md`를 기반으로 특정 언어·프레임워크·기술 기능 Skill을 추가할 때의 설계 규칙이다.

## 1. 계층

```text
Foundation
- coding-rules.md
- implementation-decision-rules.md
- project-pattern-rules.md
- data-design-rules.md (data affected area)
        ↓
Workflow
- dev-project-pattern
- dev-tech-dispatch
- dev-breakdown
- dev-implement-plan
- dev-code-review
        ↓
Capability Entry
- Backend dev-*
- Frontend dev-frontend-feature
- Data dev-data-feature
        ↓
Lazy Sub-capability
        ↓
Project convention
        ↓
Implementation / Review
```

## 2. Workflow와 Capability는 다른 축

```text
Workflow = 작업 크기/모호성/승인/workspace/review lifecycle
Capability = 어떤 기술 지식과 검증이 필요한가
```

## 3. dev-tech-dispatch

canonical resolver는 bounded build/dependency/schema manifest에서 stack과 DB vendor candidate를 감지한다.

```text
manifest evidence
→ stack / database vendor candidate
→ baseline capability entry candidate
```

source 수정, architecture 선택, dependency 설치, runtime pin 결정, Kanban 생성은 하지 않는다.

`Stack Detection != Skill Loading`이다.

## 4. Capability set

### Backend

```text
dev-java-guidelines
dev-kotlin-guidelines
dev-spring-guidelines
dev-spring-feature
dev-spring-data
dev-spring-test
dev-spring-refactor
```

### Frontend canonical entry

```text
dev-frontend-feature
```

### Frontend lazy capability

```text
dev-typescript-guidelines
dev-frontend-guidelines
dev-nextjs-feature
dev-frontend-test
dev-figma-design
dev-ui-ux
```

### Data canonical entry

```text
dev-data-feature
```

### Data lazy capability

```text
dev-data-modeling
dev-db-schema
dev-db-query
dev-db-migration
dev-db-performance
```

### Cross-stack

```text
dev-api-contract
dev-api-docs
dev-api-spec
```

## 5. Capability 공통 실행 순서

```text
1. stack/vendor/version evidence 탐색
2. 기존 동일/유사 구현 검색
3. 기존 convention 결정
4. assumption/정책 충돌 확인
5. implementation-decision-rules 필요성 사다리 적용
6. 최소 변경 구현
7. capability-specific verification
8. reviewer handoff evidence
```

새 dependency/framework/language/DB migration tool을 기본값으로 추가하지 않는다.

## 6. Java / Kotlin / Spring

```text
Java convention → dev-java-guidelines
Kotlin convention → dev-kotlin-guidelines
Spring common → dev-spring-guidelines
Controller/Service/DTO/Validation/Exception → dev-spring-feature
JPA/Repository/QueryDSL/Converter/Paging → dev-spring-data
Spring/JPA test → dev-spring-test
```

Java/Kotlin은 first-class language capability다. mixed project에서는 실제 changed source 언어에 적용한다.

JPA Query 정책은 Method Query → QueryDSL → 근거 있는 Native Query 순서다.

## 7. Frontend entry와 lazy-load

실제 frontend Task는 `dev-frontend-feature`를 runtime entry로 한다.

```text
TypeScript → dev-typescript-guidelines
React/component/state/form/browser → dev-frontend-guidelines
Next.js → dev-nextjs-feature
spec/e2e → dev-frontend-test
Figma APPROVED → dev-figma-design
visual/interaction/responsive/accessibility/chart → dev-ui-ux
API integration → dev-api-contract
```

repository가 React/Next.js를 포함한다는 이유만으로 frontend skill을 로드하지 않는다.

## 8. Data entry와 lazy-load

Data/DB Task는 다음 두 경로를 구분한다.

```text
기존 승인 schema + JPA 구현만 변경
→ dev-spring-data

데이터 모델/DBML/schema/SQL dialect/migration/performance 자체가 Task 책임
→ dev-data-feature
```

`dev-data-feature` 하위 lazy capability:

```text
model/relationship/cardinality/DBML → dev-data-modeling
PK/FK/UNIQUE/type/index/constraint → dev-db-schema
SQL/query semantics/dialect → dev-db-query
DDL/backfill/deployment compatibility → dev-db-migration
execution plan/index/locking/statistics → dev-db-performance
```

공통 data 판단은 DBMS 중립으로 수행하고, 실제 physical 차이가 필요한 경우에만 MSSQL/MySQL/MariaDB/PostgreSQL/Oracle vendor reference를 읽는다.

DB driver가 Repository에 있다는 이유만으로 Data entry를 자동 적용하지 않는다.

## 9. DBML / Human ERD Review

기존 프로젝트 표준이 없으면 `docs/data/schema.dbml`을 canonical relational model 기본값으로 사용한다.

```text
LOGICAL_RELATIONAL (기본)
→ vendor-neutral relation/key/nullability intent

PHYSICAL
→ target DBMS/version이 확정된 project에서 실제 physical mapping 허용
```

DBML Canvas는 IntelliJ에서 `schema.dbml`을 시각화하는 Human View로 사용할 수 있다. DevKit runtime은 Plugin 설치에 의존하지 않는다.

Mermaid는 설명용 파생 View이며 DBML과 독립적인 canonical model로 중복 관리하지 않는다.

의미 있는 model 변경은 기존 Plan Approval에서 proposed DBML/table/relationship을 명시적으로 보여 `Data Model Gate`를 함께 충족할 수 있다.

## 10. FIGMA_DRIVEN / CODE_DRIVEN

```text
FIGMA_DRIVEN
사용자/Task
→ APPROVED Figma frame/component
→ project component/token/convention
→ dev-ui-ux quality guardrail

CODE_DRIVEN
사용자/Task
→ project component/token/convention
→ dev-ui-ux quality guardrail
```

Figma `DRAFT`는 planning reference다.

## 11. API Contract

`dev-api-contract`는 framework 독립 capability다.

```text
method/path
request/query/header
success/error body
field name/nullability
date/time/money/decimal
enum/paging/auth
```

기존 OpenAPI-generated client가 있으면 재사용하고 code generation을 자동 도입하지 않는다.

## 12. Verification

Frontend는 기존 package manager/test runner를 사용하고 affected test → typecheck → lint → 필요한 build/e2e 순으로 넓힌다.

Data는 Task 성격에 따라 다음을 사용한다.

```text
DBML → lightweight guard + project parser/DBML Canvas manual review
query → fixture/integration/result semantics
migration → clean/upgrade/backfill/compatibility test
performance → execution plan + before/after evidence
```

실행하지 않은 검증을 PASS라고 보고하지 않는다.

## 13. Reviewer evidence

```text
Skill / Applied Capability Skills
Detected stack/vendor/version
Pattern References
Frontend Mode / Design Source / Status (해당 시)
Data Task Class / Data Model Status / DBML Path (해당 시)
Schema/Query/Migration/UI strategy
Verification
Intentional Deviations
Improvement Deferred
Residual Risk
```

Reviewer는 실제 diff 판단에 필요한 capability만 읽는다.

## 14. Skill 추가 체크리스트

```text
[ ] Foundation만으로 해결할 수 없는 전문 기능인가
[ ] 반복 가능한 작업인가
[ ] 기존 Skill과 역할이 겹치지 않는가
[ ] stack/vendor/task detection이 정의됐는가
[ ] dependency/migration tool 정책이 정의됐는가
[ ] verification/evidence가 정의됐는가
[ ] Public Skill/provider/tool source/version/security를 검토했는가
[ ] runtime pin 대신 lazy-load가 적합한지 검토했는가
```
