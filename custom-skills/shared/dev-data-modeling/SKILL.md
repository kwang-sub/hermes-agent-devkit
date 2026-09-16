---
name: dev-data-modeling
description: Use Case에서 주제영역·데이터 책임·소유권·lifecycle·cardinality·Current/History/Snapshot/Derived를 정의하고 canonical logical DBML로 표현하는 DBMS 중립 DBA capability.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, data, dba, modeling, subject-area, erd, dbml, relationship, cardinality]
    related_skills: [dev-data-feature, dev-db-schema, dev-db-migration]
    requires_tools: [terminal]
---

# dev-data-modeling

Design-Time DBA의 **논리 모델링** capability다. Use Case와 업무 의미를 기준으로 Subject Area와 logical relational model을 확정한다. 특정 DBMS DDL, 물리 table 이름, migration framework, ORM annotation을 먼저 선택하지 않는다.

## 책임 경계

DBA가 결정한다.

```text
Subject Area
Logical Entity / Logical Table
책임 / ownership / lifecycle
Current / History / Snapshot / Derived
cardinality / relationship
logical key intent / nullable 의미
업무 불변식과 Use Case 검증
canonical logical DBML
```

DBA가 결정하지 않는다.

```text
tbl_<subject_area>_<entity> 물리 table 이름
PostgreSQL/MSSQL/Oracle/MySQL/MariaDB 전용 type
IDENTITY / SEQUENCE / AUTO_INCREMENT 같은 물리 생성 방식
vendor-specific index option
CREATE / ALTER / DROP TABLE SQL
Flyway / Liquibase changelog 또는 migration file
JPA @Table / @Column annotation
실제 DB migration 실행
```

위 물리화는 승인된 logical model을 입력으로 Coder의 `dev-db-migration`이 담당한다.

## 실행 순서

```text
1. Use Case와 business rule 확인
2. 기존 domain/data model reference 확인
3. Subject Area 정의 또는 기존 승인 정의 재사용
4. 책임/ownership/lifecycle 분류
5. Current / History / Snapshot / Derived 구분
6. cardinality와 관계 lifecycle 검증
7. logical table/association 결정
8. canonical DBML + TableGroup Subject Area 반영
9. Use Case로 재검증
10. Logical Model Handoff 생성
```

## Subject Area 규칙

Subject Area는 화면 메뉴나 임시 기능명이 아니라 데이터 책임의 안정적인 업무 경계다.

```text
좋음: household, investment, market, budget
주의: common, misc, etc, management, data
```

원칙:

- Subject Area는 lowercase snake_case를 사용한다.
- 동일 의미의 유사 Subject Area를 임의로 추가하지 않는다.
- 기존 승인 Subject Area가 있으면 우선 재사용한다.
- 새로운 Subject Area가 필요하면 책임·소유권·lifecycle 근거를 남긴다.
- `common`, `misc`, `etc`, `system` 같은 포괄 영역은 실제 독립 책임 근거 없이 fallback으로 사용하지 않는다.
- 하나의 logical table은 기본적으로 하나의 canonical Subject Area에 속한다. 교차 영역 관계는 Ref로 표현하지 중복 소속으로 해결하지 않는다.

Canonical DBML에서는 `TableGroup`을 Subject Area의 machine-readable 표현으로 사용한다.

```dbml
Table account {
  id bigint [pk]
  name varchar(100) [not null]
}

Table holding {
  id bigint [pk]
  account_id bigint [not null]
}

TableGroup investment {
  account
  holding
}

Ref: holding.account_id > account.id
```

새 canonical logical model에서는 Subject Area 안의 logical table을 가능한 한 local entity 이름으로 표현한다.

```text
Subject Area: investment
Logical Table: account

권장: account
레거시 허용: investment_account
금지: tbl_investment_account   # 물리 이름
```

기존 프로젝트의 승인된 logical naming을 대규모 rename하지 않는다. `investment_account` 같은 기존 logical name은 유지할 수 있으며 Coder physicalization이 Subject Area prefix 중복을 방지한다.

## 분리 기준

테이블 분리는 컬럼 수가 아니라 다음으로 판단한다.

```text
책임
소유권
생명주기
cardinality
transaction/concurrency boundary
history/snapshot 요구
조회/쓰기 패턴
독립 확장 가능성
```

1:1 분리는 실제 독립 lifecycle/보안/성능/optional 책임이 있는지 확인한다.

## DBML

기존 프로젝트 표준이 없으면 `docs/data/schema.dbml`을 canonical relational model로 사용한다.

```text
Data Model Mode: LOGICAL_RELATIONAL
```

Canonical DESIGN_FIRST 모델에서는 vendor-specific physical option을 넣지 않고 Subject Area를 `TableGroup`으로 기록한다.

DBML 변경 후 lightweight guard:

```bash
python3 /opt/custom-skills/shared/dev-data-modeling/scripts/dbml_guard.py \
  --path docs/data/schema.dbml \
  --mode logical \
  --require-subject-area
```

`--require-subject-area`는 canonical DBA model에 사용한다. 기존 프로젝트가 별도 DBML convention을 갖는 SOURCE_SYNC 작업은 해당 프로젝트 convention을 우선하고 자동으로 전체 DBML을 재구성하지 않는다.

이 guard는 full DBML parser가 아니다. duplicate Table, top-level Ref target, Subject Area membership, logical/physical naming drift, vendor-specific token 위험만 빠르게 점검한다. 실제 syntax/rendering은 프로젝트의 DBML parser/CI 또는 DBML Canvas 같은 Human View로 확인한다.

## Use Case Validation

관련되는 경우 최소 다음을 검토한다.

```text
create
update/state transition
child add/remove
partial/full delete 또는 종료
중복 입력
history 보존
snapshot 생성
동시 수정
대량 조회/paging
migration/backfill에 필요한 logical intent
```

물리 migration 전략 자체는 Coder 책임이며 DBA는 그 전략에 필요한 업무 의미와 불변식만 handoff한다.

## Logical Model Gate

새 table 또는 의미 있는 관계 변경은 다음 상태를 사용한다.

```text
Data Model Status: DRAFT | APPROVED
```

`DRAFT`를 Agent가 임의로 `APPROVED`로 승격하지 않는다. Coder physicalization은 `APPROVED` logical model만 입력으로 사용한다.

## Handoff

```text
Data Modeling:
- Subject Areas:
- Subject Area Rationale:
- Logical Tables by Subject Area:
- Responsibilities:
- Ownership/Lifecycle:
- Cardinality:
- Current/History/Snapshot/Derived:
- Logical Key / Nullability Intent:
- Business Constraints:
- DBML Path / Changes:
- Use Cases Validated:
- Data Model Status: DRAFT | APPROVED
- Open Model Questions:
```
