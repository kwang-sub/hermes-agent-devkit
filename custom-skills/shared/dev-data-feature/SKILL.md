---
name: dev-data-feature
description: 데이터 작업의 canonical entry로 DBA logical modeling과 SQL·성능 분석을 task evidence에 따라 조합하고, 승인된 논리 모델의 물리화는 명시적으로 합의한 마이그레이션 단계에서 구현하는 DBMS 중립 shared skill.
version: 0.4.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, data, database, dba, dbml, logical-model, subject-area, sql, performance, work-unit]
    related_skills: [dev-data-modeling, dev-db-schema, dev-db-query, dev-db-migration, dev-db-performance, dev-spring-data, dev-api-contract]
    requires_tools: [terminal, skill_view]
---

# dev-data-feature

데이터 affected area의 canonical runtime entry다. 논리 설계와 물리화의 책임·승인 범위를 구분하되 같은 DevKit 세션에서 이어서 진행할 수 있다. 별도 Task·프로필을 요구하지 않는다.

공통 Foundation:

```text
/opt/data/shared/references/coding-rules.md
/opt/data/shared/references/implementation-decision-rules.md
/opt/data/shared/references/project-pattern-rules.md
/opt/data/shared/references/data-design-rules.md
/opt/data/shared/references/development-contract.md
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

### 구현 단계 physical phase

승인된 logical model의 물리화가 사용자 요청 범위에 포함되면 `dev-db-migration`을 사용한다. 설계만 요청한 경우 파일/DB 변경으로 자동 확대하지 않는다.

```text
Target DBMS/version 확인
기존 migration tool/convention 탐지
Physical table/type/constraint/index 결정
Flyway 또는 Liquibase migration 작성
project-controlled local/test/CI migration 검증
JPA physical mapping 영향 반영
```

`dev-db-schema`와 `dev-db-migration`은 같은 세션이 필요한 시점에 선택하는 shared capability다. 스킬을 읽었다는 사실이 실제 DB 변경 권한을 뜻하지 않는다.

## 설계와 물리화 경계
논리 모델링 요청에서는 Subject Area, 책임, cardinality, ownership, DBML과 검증 근거를 정리한다. 물리 테이블명·vendor DDL·ORM mapping·migration 파일을 자동으로 생성하지 않는다.

사용자가 구현까지 명시적으로 요청했다면 승인된 논리 모델을 기준으로 물리화와 migration 파일 작성·프로젝트 통제 테스트를 같은 세션에서 진행할 수 있다. 새로운 Kanban 카드나 별도 승인 상태 머신은 필요하지 않다. 실제 운영 DB 적용은 별도 배포/마이그레이션 권한을 따른다.

논리 의미 변경이 드러나면 차이와 영향을 설명하고 합의 범위를 다시 확인한다. 현재 단계와 다음 행동은 간단히 기록하며 DONE 상태나 Worker 인계로 판단하지 않는다.

## Task Classification

```text
MODEL_CHANGE  - Subject Area/table relation/ownership/lifecycle/cardinality 논리 설계
SCHEMA_CHANGE - schema 변경 영향과 논리 의미 변경 여부 확인
QUERY_ONLY    - SQL/relational query 작성·수정·검토
MIGRATION     - 합의된 logical/schema intent를 migration 파일과 통제된 테스트로 검증
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

Vendor가 `unknown`인데 vendor-specific DDL/type/index가 필요한 경우 DBA가 추측하지 않는다. 별도 구현 단계 physicalization 작업이 target DBMS/version evidence를 확보한다.

## Capability routing

```text
주제영역/책임/관계/lifecycle/cardinality/DBML → dev-data-modeling
SQL/query semantics/dialect → dev-db-query
execution plan/query tuning/locking/statistics → dev-db-performance
승인 logical model의 physical schema 판단 → MIGRATION 작업의 구현 단계가 dev-db-schema lazy-load
DDL/backfill/Flyway/Liquibase/deployment → 별도 MIGRATION 작업의 구현 단계가 shared dev-db-migration 실행
JPA/Repository/QueryDSL/Converter/Paging → dev-spring-data
```

모든 capability를 시작부터 읽지 않는다. 실제 Task affected area에 필요한 것만 `skill_view`한다.

## Vendor reference

DBA logical modeling은 vendor-neutral을 유지한다. Query/performance 분석 또는 구현 단계 physicalization에서 DBMS 차이가 실제로 필요할 때만 다음 reference를 읽는다.

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

기존 합의된 직접 개발 Plan Approval에서 Subject Area + proposed logical DBML/table/relationship diff가 명시적으로 제시되면 별도 중복 승인 질문 없이 Data Model Gate를 함께 충족할 수 있다.

```text
Data Design Mode: DESIGN_FIRST | SOURCE_SYNC | QUERY_ONLY | PERFORMANCE
Data Model Gate: REQUIRED | NOT_REQUIRED
Data Model Status: DRAFT | APPROVED | NOT_REQUIRED
DBML Path: <path | none>
Subject Areas: <list | none>
```

`DRAFT`를 구현 단계가 임의로 `APPROVED`로 승격하지 않는다.

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

`MODEL_CHANGE`/`SCHEMA_CHANGE`가 실제 DB schema 변경을 요구하면 현재 설계 결과에 다음을 남긴다.

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

이 evidence는 **다음 합의된 직접 개발 MIGRATION 작업의 입력**이지 현재 Task에서 `dev-db-migration`을 계속 실행하라는 의미가 아니다.

## 자체 검토 단계 실행

자체 검토 단계는 DESIGN Task에서는 logical artifact와 Work Unit Boundary를 검토하고, MIGRATION Task에서는 shared `dev-db-migration` 계약을 read-only 검토 기준으로 본다.

- Subject Area와 logical table 책임이 Use Case 근거를 갖는가.
- logical DBML에 `tbl_`/vendor DDL/migration 구현이 섞이지 않았는가.
- DESIGN Task diff에 Flyway/Liquibase/JPA physical mapping이 섞이지 않았는가.
- MIGRATION 작업의 physical table mapping이 승인 Subject Area를 임의 변경하지 않았는가.
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
구현 단계 Migration Skill Required: YES | NO
Query / Performance Changes:
Verification:
DBML Canvas Manual Review: PASS | NOT_RUN | NOT_REQUIRED
Intentional Deviations:
Residual Risk:
```

## 운영 경계

이 Skill의 DBA responsibility는 Design-Time logical modeling이다. 운영 DB에 직접 DDL/DML을 실행하거나 backup/restore/session kill/index maintenance를 수행하지 않는다. 구현 단계 migration execution도 승인 없는 운영 DB 직접 변경 권한을 부여하지 않는다.
