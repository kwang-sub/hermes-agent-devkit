---
name: dev-data-feature
description: 데이터 작업의 canonical entry로 DBA logical modeling과 SQL·성능 분석을 task evidence에 따라 조합하고, 승인된 논리 모델의 물리화는 별도 Standard MIGRATION Work Unit으로 handoff하는 DBMS 중립 shared skill.
version: 0.4.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, data, database, dba, dbml, logical-model, subject-area, sql, performance, work-unit]
    related_skills: [dev-data-modeling, dev-db-schema, dev-db-query, dev-db-migration, dev-db-performance, dev-spring-data, dev-api-contract]
    requires_tools: [terminal, skill_view]
---

# dev-data-feature

데이터 affected area의 canonical runtime entry다. **DBA logical phase와 Coder physical phase를 책임뿐 아니라 Standard Flow Task 경계로도 분리**한다.

공통 Foundation:

```text
/opt/data/shared/references/coding-rules.md
/opt/data/shared/references/implementation-decision-rules.md
/opt/data/shared/references/project-pattern-rules.md
/opt/data/shared/references/data-design-rules.md
/opt/data/shared/references/standard-work-unit-rules.md
```

## 책임 분리

### DBA logical phase

```text
Subject Area 정의
Logical Entity / Table 구성
책임 / ownership / lifecycle
relationship / cardinality
Current / History / Snapshot / Derived
업무 불변식
canonical logical DBML
```

DBA logical phase에서는 다음을 생성하지 않는다.

```text
tbl_* physical table name
vendor-specific DDL/type/index
Flyway/Liquibase migration
JPA physical mapping
실제 DB schema mutation
```

### Coder physical phase

승인된 logical model이 실제 schema 변경으로 이어지면 **같은 Standard Task를 계속 확장하지 않는다.** 별도 Standard Flow의 `Work Unit Class: MIGRATION`에서 shared/pinnable `dev-db-migration` capability를 실행 책임으로 사용한다.

```text
Target DBMS/version 확인
기존 migration tool/convention 탐지
Physical table/type/constraint/index 결정
Flyway 또는 Liquibase migration 작성
project-controlled local/test/CI migration 검증
JPA physical mapping 영향 반영
```

`dev-db-schema`는 Coder/Reviewer가 physical schema 판단에 사용하는 shared support capability이며 DBA logical output의 범위를 확장하지 않는다. `dev-db-migration`도 dispatch에서 Coder/Reviewer가 동일 계약을 볼 수 있도록 shared에 두되, **migration 파일 작성·변경의 실행 권한은 Coder**에만 있다.

## Standard Work Unit Boundary

Data `DESIGN_FIRST` logical model과 physical DB 구현은 반드시 분리한다.

### Logical Design Task

```text
Work Unit Class: DESIGN
Work Unit Boundary: SPLIT_REQUIRED        # Physicalization Required=YES일 때
Current Deliverable: approved/materialized logical DBML
Follow-up Required: YES | NO
Follow-up Work Unit: MIGRATION | NONE
Follow-up Input: approved/materialized logical DBML | NONE
Excluded Follow-up Scope: Flyway/Liquibase, DDL, physical schema, JPA physical mapping
```

DESIGN Task에서 Coder가 할 수 있는 mutation은 **승인된 logical artifact의 materialization/documentation**뿐이다.

```text
허용:
- docs/data/schema.dbml 생성/갱신
- 승인된 Subject Area / logical table / relationship 반영
- dbml_guard 실행
- logical documentation 갱신

금지:
- Flyway/Liquibase migration
- CREATE/ALTER/DROP DDL
- tbl_* physical naming 적용
- vendor-specific type/index 결정
- JPA @Table/@Column physical mapping
- 실제 schema mutation
```

DESIGN Task가 DONE되어도 후속 MIGRATION Task를 자동 생성하거나 dispatch하지 않는다. Physicalization은 사용자가 별도 Standard Flow로 요청한다.

### Physicalization Task

```text
Work Unit Class: MIGRATION
Work Unit Boundary: SINGLE_UNIT
Authoritative Input: repository canonical DBML 또는 이전 승인 logical artifact snapshot
```

MIGRATION Task는 승인 logical model을 구현하며 responsibility/cardinality/ownership을 임의 redesign하지 않는다. 논리 변경이 새로 필요하면 현재 MIGRATION scope를 확장하지 않고 새 DESIGN Work Unit으로 되돌린다.

## Task Classification

```text
MODEL_CHANGE  - Subject Area/table relation/ownership/lifecycle/cardinality 논리 설계
SCHEMA_CHANGE - 논리 의미 변경. DESIGN 완료 후 별도 MIGRATION 필요
QUERY_ONLY    - SQL/relational query 작성·수정·검토
MIGRATION     - 승인 logical/schema intent를 별도 Coder migration Task로 구현
PERFORMANCE   - execution plan/index/query shape/locking/cardinality 분석
```

승인된 기존 schema에서 단순 JPA Repository/QueryDSL 구현만 바꾸는 작업은 기존 `dev-spring-data`만으로 충분할 수 있다.

## Model Contract

```text
Database Vendor: generic | mssql | mysql | mariadb | postgresql | oracle | unknown
Data Model Mode: LOGICAL_RELATIONAL
DBML Mode: CANONICAL | PROJECT_EXISTING | NOT_REQUIRED
Data Naming Source: PROJECT_EXISTING | PROJECT_INFERRED | DEVKIT_DEFAULT | NOT_REQUIRED
Subject Areas: <approved list | NOT_REQUIRED>
Physicalization Required: YES | NO
```

Canonical DBA output은 `LOGICAL_RELATIONAL`이다. 기존 프로젝트가 Physical DBML을 source of truth로 이미 사용하더라도 DBA가 신규 physical convention을 발명하지 않고 `PROJECT_EXISTING` evidence로 취급한다.

Vendor가 `unknown`인데 vendor-specific DDL/type/index가 필요한 경우 DBA가 추측하지 않는다. 별도 Coder physicalization Task가 target DBMS/version evidence를 확보한다.

## Capability routing

```text
주제영역/책임/관계/lifecycle/cardinality/DBML → dev-data-modeling
SQL/query semantics/dialect → dev-db-query
execution plan/query tuning/locking/statistics → dev-db-performance
승인 logical model의 physical schema 판단 → MIGRATION Task의 Coder가 dev-db-schema lazy-load
DDL/backfill/Flyway/Liquibase/deployment → 별도 MIGRATION Task의 Coder가 shared dev-db-migration 실행
JPA/Repository/QueryDSL/Converter/Paging → dev-spring-data
```

모든 capability를 시작부터 읽지 않는다. 실제 Task affected area에 필요한 것만 `skill_view`한다.

## Vendor reference

DBA logical modeling은 vendor-neutral을 유지한다. Query/performance 분석 또는 Coder physicalization에서 DBMS 차이가 실제로 필요할 때만 다음 reference를 읽는다.

```text
/opt/custom-skills/shared/dev-data-feature/references/vendors/mssql.md
/opt/custom-skills/shared/dev-data-feature/references/vendors/mysql.md
/opt/custom-skills/shared/dev-data-feature/references/vendors/mariadb.md
/opt/custom-skills/shared/dev-data-feature/references/vendors/postgresql.md
/opt/custom-skills/shared/dev-data-feature/references/vendors/oracle.md
```

Vendor detection 기준은 `references/vendor-detection.md`를 따른다.

## DBML / Documentation

프로젝트에 별도 표준이 없으면 `docs/data/schema.dbml`을 canonical logical relational model로 사용한다.

Canonical 모델의 Subject Area는 DBML `TableGroup`으로 표현한다. DBML Canvas는 사람이 시각적으로 검토하기 위한 View일 뿐 Agent runtime 전제조건이 아니다.

상세 문서 계약은 `references/documentation-contract.md`를 따른다.

## Data Model Gate

다음은 기본적으로 `Data Model Gate: REQUIRED`다.

```text
새 table
Subject Area 신규/변경
relationship/cardinality 변경
PK/FK/UNIQUE의 업무 의미 변경
nullable 의미 변경
identifier 역할 변경
audit/soft delete 의미 변경
Current/History/Snapshot 책임 변경
data ownership/lifecycle 변경
```

기존 Standard Flow Plan Approval에서 Subject Area + proposed logical DBML/table/relationship diff가 명시적으로 제시되면 별도 중복 승인 질문 없이 Data Model Gate를 함께 충족할 수 있다.

```text
Data Design Mode: DESIGN_FIRST | SOURCE_SYNC | QUERY_ONLY | PERFORMANCE
Data Model Gate: REQUIRED | NOT_REQUIRED
Data Model Status: DRAFT | APPROVED | NOT_REQUIRED
DBML Path: <path | none>
Subject Areas: <list | none>
```

`DRAFT`를 Coder가 임의로 `APPROVED`로 승격하지 않는다.

## DBA 실행

```text
1. Task/Project Pattern/Data Model Status 재사용
2. Use Case와 기존 domain/data model evidence 확인
3. Subject Area 정의/재사용
4. dev-data-modeling으로 logical model 작성
5. canonical DBML이면 dbml_guard --require-subject-area 검증
6. Use Case 재검증
7. APPROVED 여부와 logical artifact handoff evidence 기록
8. DESIGN Work Unit에서 승인 DBML만 materialize하고 종료
```

DBA logical phase는 migration 파일을 만들지 않는다.

## Next Work Unit Gate

`MODEL_CHANGE`/`SCHEMA_CHANGE`가 실제 DB schema 변경을 요구하면 현재 DESIGN Task의 handoff에 다음을 남긴다.

```text
Data Model Status: APPROVED
DBML Path: <canonical/project path>
Subject Areas: <approved mapping>
Logical Tables / Relationships:
Business Constraints:
Physicalization Required: YES
Follow-up Required: YES
Follow-up Work Unit: MIGRATION
Follow-up Input: approved/materialized logical DBML
```

이 evidence는 **다음 Standard Flow MIGRATION Task의 입력**이지 현재 Task에서 `dev-db-migration`을 계속 실행하라는 의미가 아니다.

## Reviewer 실행

Reviewer는 DESIGN Task에서는 logical artifact와 Work Unit Boundary를 검토하고, MIGRATION Task에서는 shared `dev-db-migration` 계약을 read-only 검토 기준으로 본다.

- Subject Area와 logical table 책임이 Use Case 근거를 갖는가.
- logical DBML에 `tbl_`/vendor DDL/migration 구현이 섞이지 않았는가.
- DESIGN Task diff에 Flyway/Liquibase/JPA physical mapping이 섞이지 않았는가.
- MIGRATION Task의 physical table mapping이 승인 Subject Area를 임의 변경하지 않았는가.
- DBML, migration, Entity/Repository가 의미상 drift하지 않는가.
- 기존 Data Naming Source와 migration framework를 존중했는가.
- migration이 기존 데이터/구버전 application과 호환되는가.
- query/performance finding이 실제 evidence에 기반하는가.

스타일 선호만으로 schema redesign을 요구하지 않는다.

## Handoff Evidence

```text
Data Task Class:
Data Design Mode / Model Status:
DBML Mode / Path:
Subject Areas:
Logical Tables / Relationships:
Ownership / Lifecycle:
Business Constraints:
Physicalization Required:
Work Unit Class:
Work Unit Boundary:
Follow-up Required:
Follow-up Work Unit:
Follow-up Input:
Excluded Follow-up Scope:
Target DBMS / Version Evidence:
Coder Migration Skill Required: YES | NO
Query / Performance Changes:
Verification:
DBML Canvas Manual Review: PASS | NOT_RUN | NOT_REQUIRED
Intentional Deviations:
Residual Risk:
```

## 운영 경계

이 Skill의 DBA responsibility는 Design-Time logical modeling이다. 운영 DB에 직접 DDL/DML을 실행하거나 backup/restore/session kill/index maintenance를 수행하지 않는다. Coder migration execution도 승인 없는 운영 DB 직접 변경 권한을 부여하지 않는다.
