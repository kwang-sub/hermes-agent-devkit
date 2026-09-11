---
name: dev-data-feature
description: 데이터/DB 작업의 canonical entry로 모델링·스키마·SQL·migration·성능 capability와 DBML 문서 계약을 task evidence에 따라 조합하는 DBMS 중립 shared skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, data, database, dba, dbml, schema, sql, migration, performance]
    related_skills: [dev-data-modeling, dev-db-schema, dev-db-query, dev-db-migration, dev-db-performance, dev-spring-data, dev-api-contract]
    requires_tools: [terminal, skill_view]
---

# dev-data-feature

데이터 모델·관계형 schema·SQL·migration·DB 성능 작업의 canonical runtime entry다.

공통 Foundation:

```text
/opt/data/shared/references/coding-rules.md
/opt/data/shared/references/implementation-decision-rules.md
/opt/data/shared/references/project-pattern-rules.md
/opt/data/shared/references/data-design-rules.md
```

## 적용 범위

```text
MODEL_CHANGE  - table/entity relation, ownership, lifecycle, cardinality 설계
SCHEMA_CHANGE - PK/FK/UNIQUE/NOT NULL/index/type/default/constraint 변경
QUERY_ONLY    - SQL/relational query 작성·수정·검토
MIGRATION     - DDL/data backfill/compatibility/deployment order
PERFORMANCE   - execution plan/index/query shape/locking/cardinality 분석
```

승인된 기존 schema에서 단순 JPA Repository/QueryDSL 구현만 바꾸는 작업은 기존 `dev-spring-data`만으로 충분할 수 있다. Schema/DBML/DDL/SQL vendor 의미까지 건드리면 `dev-data-feature`를 함께 적용한다.

## Task Classification

```text
Data Task Class: MODEL_CHANGE | SCHEMA_CHANGE | QUERY_ONLY | MIGRATION | PERFORMANCE
Database Vendor: generic | mssql | mysql | mariadb | postgresql | oracle | unknown
Data Model Mode: LOGICAL_RELATIONAL | PHYSICAL
DBML Mode: CANONICAL | PROJECT_EXISTING | NOT_REQUIRED
```

Vendor가 `unknown`인데 vendor-specific DDL/type/index가 필요한 경우 추측하지 않는다.

## 하위 Capability lazy-load

```text
도메인/관계/lifecycle/cardinality/DBML → dev-data-modeling
PK/FK/constraint/index/type/nullability/default → dev-db-schema
SQL/query semantics/dialect → dev-db-query
DDL/backfill/compatibility/deployment → dev-db-migration
execution plan/index tuning/locking/statistics → dev-db-performance
JPA/Repository/QueryDSL/Converter/Paging 구현 → dev-spring-data
```

모든 하위 Skill을 시작부터 읽지 않는다. 실제 Task affected area에 필요한 것만 `skill_view`한다.

## Vendor reference

DBMS 공통 판단 후 물리 차이가 실제로 필요할 때만 다음을 읽는다.

```text
/opt/custom-skills/shared/dev-data-feature/references/vendors/mssql.md
/opt/custom-skills/shared/dev-data-feature/references/vendors/mysql.md
/opt/custom-skills/shared/dev-data-feature/references/vendors/mariadb.md
/opt/custom-skills/shared/dev-data-feature/references/vendors/postgresql.md
/opt/custom-skills/shared/dev-data-feature/references/vendors/oracle.md
```

Vendor detection 기준은 `references/vendor-detection.md`를 따른다.

## DBML / Documentation

프로젝트에 별도 표준이 없으면 `docs/data/schema.dbml`을 canonical relational model로 사용한다.

DBML Canvas는 IntelliJ에서 이 파일을 사람이 시각적으로 검토하기 위한 View로 활용할 수 있지만 Plugin 설치 여부를 Agent runtime 전제조건으로 만들지 않는다.

상세 문서 계약은 `references/documentation-contract.md`를 따른다.

## Data Model Gate

의미 있는 모델 변경은 구현 전에 설계가 명시돼야 한다.

다음은 기본적으로 `Data Model Gate: REQUIRED`다.

```text
새 table
relationship/cardinality 변경
PK/FK/UNIQUE 의미 변경
nullable 의미 변경
Current/History/Snapshot 책임 변경
data ownership/lifecycle 변경
```

기존 Standard Flow의 Plan Approval에서 proposed DBML/table/relationship diff가 명시적으로 제시되면 별도 중복 승인 질문 없이 Data Model Gate를 함께 충족할 수 있다.

```text
Data Design Mode: DESIGN_FIRST | SOURCE_SYNC | QUERY_ONLY | PERFORMANCE
Data Model Gate: REQUIRED | NOT_REQUIRED
Data Model Status: DRAFT | APPROVED | NOT_REQUIRED
DBML Path: <path | none>
```

`DRAFT`를 Coder가 임의로 `APPROVED`로 승격하지 않는다.

## Coder 실행

```text
1. Task/Project Pattern/Data Model Status 재사용
2. DBMS vendor/version evidence 확인
3. 기존 schema/migration/query/documentation pattern 확인
4. 필요한 하위 capability만 lazy-load
5. DBML/schema/query/migration 최소 scope 확정
6. 구현
7. DBML guard / project parser / SQL test / migration test 등 가능한 검증
8. handoff evidence 기록
```

DBML 변경 후 IntelliJ DBML Canvas rendering은 권장 Human Verification이지만 자동 PASS라고 주장하지 않는다.

## Reviewer 실행

Reviewer가 이 Skill을 runtime context로 받으면 기존 `dev-code-review`의 diff-first 계약을 유지하면서 다음을 추가 확인한다.

- Data Task Class와 실제 diff가 일치하는가.
- table 분리가 책임/lifecycle/cardinality 근거를 갖는가.
- DBML, migration, Entity/Repository가 서로 의미상 drift하지 않는가.
- PK/FK/UNIQUE/nullability/default/index가 업무 불변식과 맞는가.
- migration이 기존 데이터/구버전 application과 호환되는가.
- query/performance finding이 실제 evidence에 기반하는가.
- vendor-specific 선택이 target DBMS/version 근거를 갖는가.

스타일 선호만으로 schema redesign을 요구하지 않는다.

## Handoff Evidence

```text
Data Task Class:
Database Vendor / Version:
Data Model Mode:
DBML Mode / Path:
Data Model Status:
Applied Data Capabilities:
Pattern References:
Schema / Query / Migration Changes:
Integrity Constraints:
Compatibility / Backfill:
Verification:
DBML Canvas Manual Review: PASS | NOT_RUN | NOT_REQUIRED
Intentional Deviations:
Residual Risk:
```

## 운영 경계

이 Skill은 Design-Time DBA capability다. 운영 DB에 직접 DDL/DML을 실행하거나 backup/restore/session kill/index maintenance를 수행하지 않는다. 운영 실행 자동화가 필요하면 별도 프로필/권한/Skill을 설계한다.
