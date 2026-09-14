---
name: dev-db-schema
description: 승인된 relational model을 PK/FK/UNIQUE/nullability/default/type/index/constraint 중심의 physical schema로 구체화하는 DBMS 중립 capability.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, database, schema, constraint, index, datatype]
    related_skills: [dev-data-feature, dev-data-modeling, dev-db-migration]
    requires_tools: [terminal]
---

# dev-db-schema

`dev-data-modeling`에서 확정된 의미를 관계형/물리 schema로 구체화한다.

## 판단 순서

```text
Approved relational intent
→ existing project schema convention
→ naming / identifier / audit convention source
→ integrity constraints
→ logical type/precision/nullability
→ access pattern/index intent
→ detected DBMS/version
→ vendor-specific physical mapping
```

## 검토 대상

```text
PK / candidate key
FK + cascade behavior
UNIQUE
NOT NULL
CHECK / default
numeric precision/scale
text length/unicode/collation
Date/Time/Timezone
identifier role / generation
internal / public / external identifier boundary
audit columns / actor semantics
soft delete strategy
index key/order/include/partial/function 등 vendor option
```

## Convention Source

식별자·naming·audit·soft delete는 `/opt/data/shared/references/data-design-rules.md`의 evidence 우선순위를 따른다.

```text
Data Naming Source: PROJECT_EXISTING | PROJECT_INFERRED | DEVKIT_DEFAULT
```

`schema.dbml`이 없더라도 기존 JPA Entity, migration/DDL, 실제 schema 등에서 일관된 규칙을 확인할 수 있으면 `DEVKIT_DEFAULT`를 적용하지 않는다.

### DEVKIT_DEFAULT

유효한 기존 convention evidence가 없는 신규 모델에서만 다음 fallback을 사용한다.

```text
Table       → singular snake_case
Column      → snake_case
Internal PK → id
Internal FK → <referenced_entity>_id
Public ID   → public_id   # 필요할 때만
External ID → external_id # 실제 외부 시스템 연동이 있을 때만
```

Java/JPA naming은 다음을 기본으로 한다.

```text
Entity      → PascalCase
Field       → camelCase
```

특정 인증 Provider의 사용자 identifier naming/table 구조는 generic schema fallback으로 강제하지 않는다.

## Identifier Strategy

- Internal PK는 application/database-owned identity다.
- 단일 primary DB와 높은 FK/JOIN 밀도에서는 BIGINT + target DBMS의 identity/sequence 계열을 우선 검토할 수 있다.
- 분산/DB INSERT 전 ID 생성/global uniqueness 요구가 실제로 있으면 UUID를 검토한다.
- 신규 UUID에서 시간 정렬성과 index locality가 중요하면 UUIDv7을 우선 검토하되 runtime/DBMS/project 지원 근거를 확인한다.
- `public_id`는 외부 API/URL/Event 식별자가 실제로 필요한 Entity에만 추가한다.
- Dual ID는 `id`를 내부 PK, `public_id`를 UNIQUE 외부 식별자로 분리하며 둘을 단순히 composite PK로 만들지 않는다.
- 내부 FK/JOIN은 특별한 근거가 없으면 internal PK를 참조한다.

## Audit Convention

기존 convention이 없는 신규 mutable business table의 fallback은 다음이다.

```text
created_at
created_by
updated_at
updated_by
```

Java/JPA field:

```text
createdAt
createdBy
updatedAt
updatedBy
```

- audit 시간은 논리적으로 UTC Instant 시점을 표현한다.
- 실제 temporal type은 target DBMS/version과 project convention으로 mapping한다.
- 사용자 Actor를 식별할 수 있으면 `created_by` / `updated_by`는 application-owned internal user identifier를 우선한다.
- 외부 인증 Provider의 raw identifier를 business table audit FK의 기본값으로 사용하지 않는다.
- System/Batch actor에 `0`, `-1` 같은 magic ID를 자동 배정하지 않는다.
- Append-only History/Ledger처럼 update audit가 의미 없는 table에는 `updated_at` / `updated_by`를 기계적으로 추가하지 않는다.

## Soft Delete

Soft Delete는 lifecycle/use case가 요구할 때만 적용한다.

기존 convention이 없는 신규 모델에서 Soft Delete를 채택하면 다음을 기본으로 한다.

```text
deleted_at
deleted_by
```

```text
deleted_at IS NULL     → active
deleted_at IS NOT NULL → soft deleted
```

- `deleted_by`는 사용자 Actor가 존재하면 create/update audit와 동일한 internal user identifier 규칙을 따른다.
- `is_deleted`는 기존 project convention이나 명확한 요구가 있을 때 허용하지만 `DEVKIT_DEFAULT`는 아니다.
- 특별한 이유 없이 `is_deleted`와 `deleted_at`을 동시에 두어 delete state source of truth를 이중화하지 않는다.
- 업무상 종료/해지/만기/유효기간 종료는 Soft Delete와 분리하고 domain status/time으로 모델링한다.

## 원칙

- nullable은 편의가 아니라 데이터 의미다.
- default가 과거 row와 신규 row에 같은 의미인지 확인한다.
- FK cascade는 lifecycle ownership이 분명할 때만 사용한다.
- index는 모든 FK/검색 column에 기계적으로 추가하지 않고 query/selectivity/write pattern을 본다.
- monetary/quantity 값은 precision/scale과 rounding 책임을 명시한다.
- vendor-specific type/index를 선택할 때는 `dev-data-feature`의 해당 vendor reference를 읽는다.
- 신규 fallback convention은 기존 schema를 rename하거나 migration하기 위한 자동 기준이 아니다.

## DBML

`LOGICAL_RELATIONAL` DBML에서는 물리 옵션을 과도하게 넣지 않는다.

`PHYSICAL` mode에서는 실제 target DBMS와 migration이 일치하도록 type/index/constraint를 반영할 수 있다.

## Handoff

```text
Schema Decisions:
- Data Naming Source:
- Keys / Identifier Strategy:
- Naming Convention:
- Audit Convention:
- Soft Delete Strategy:
- Constraints:
- Types/Precision:
- Indexes:
- Vendor-specific Mapping:
- Integrity Risks:
```
