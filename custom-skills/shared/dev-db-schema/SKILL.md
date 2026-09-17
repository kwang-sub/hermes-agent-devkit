---
name: dev-db-schema
description: 승인된 logical relational model을 Coder/Reviewer가 PK/FK/UNIQUE/nullability/default/type/index/constraint와 물리 naming으로 구체화할 때 사용하는 DBMS 중립 physical schema support capability.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, database, physical-schema, constraint, index, datatype, naming]
    related_skills: [dev-data-feature, dev-data-modeling, dev-db-migration]
    requires_tools: [terminal]
---

# dev-db-schema

`dev-data-modeling`에서 **APPROVED**된 논리 의미를 Coder migration 단계가 관계형/물리 schema로 구체화할 때 사용하는 support capability다. DBA logical modeling capability가 아니다.

## Role Boundary

입력:

```text
Approved Subject Area mapping
Approved logical tables / relationships
Business constraints
Target DBMS/version evidence
Existing project naming/schema convention
```

출력:

```text
Physical table/column naming
Physical identifier generation
PK/FK/UNIQUE/NOT NULL/CHECK/default
DBMS-specific data type
Index design
Migration implementation decision evidence
```

Subject Area를 임의로 추가·변경하지 않는다. 실제 migration/changelog 생성과 실행 순서는 Coder `dev-db-migration`이 담당한다.

## 판단 순서

```text
Approved logical intent + Subject Area
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

기존 schema/migration/DDL/JPA mapping에 일관된 물리 규칙이 있으면 기존 규칙이 우선이다. `DEVKIT_DEFAULT`는 신규 physical schema에만 적용한다.

### DEVKIT_DEFAULT Physical Naming

```text
Logical Table → lowercase snake_case entity/local name
Physical Table → tbl_<subject_area>_<entity>
Column → snake_case
Internal PK → id
Internal FK → <referenced_entity>_id
Public ID → public_id      # 필요할 때만
External ID → external_id # 실제 외부 시스템 요구가 있을 때만
```

예:

```text
Subject Area: investment
Logical Table: account
Physical Table: tbl_investment_account
```

기존 logical table이 `investment_account`처럼 Subject Area prefix를 이미 포함하면 정확히 한 번만 제거해서 `tbl_investment_account`로 만들고 `tbl_investment_investment_account`를 만들지 않는다.

물리 table명은 lowercase snake_case이며 `tbl_` prefix와 승인 Subject Area를 반드시 포함한다. 임의 약어(`inv`, `mkt`)를 생성하지 않는다.

Java/JPA naming은 다음을 기본으로 한다.

```text
Entity → PascalCase
Field → camelCase
@Table → resolved physical table name
```

## Identifier Strategy

- Internal PK는 application/database-owned identity다.
- 단일 primary DB와 높은 FK/JOIN 밀도에서는 BIGINT + target DBMS의 identity/sequence 계열을 우선 검토할 수 있다.
- 분산/DB INSERT 전 ID 생성/global uniqueness 요구가 실제로 있으면 UUID를 검토한다.
- 신규 UUID에서 시간 정렬성과 index locality가 중요하면 UUIDv7을 우선 검토하되 runtime/DBMS/project 지원 근거를 확인한다.
- `public_id`는 외부 API/URL/Event 식별자가 실제로 필요한 Entity에만 추가한다.
- Dual ID는 `id`를 내부 PK, `public_id`를 UNIQUE 외부 식별자로 분리한다.
- 내부 FK/JOIN은 특별한 근거가 없으면 internal PK를 참조한다.

## Audit Convention

기존 convention이 없는 신규 mutable business table의 fallback은 다음이다.

```text
created_at
created_by
updated_at
updated_by
```

시간은 논리적으로 UTC Instant를 표현하고 실제 temporal type은 target DBMS/version과 project convention으로 mapping한다. Append-only History/Ledger처럼 update audit가 의미 없는 table에는 기계적으로 추가하지 않는다.

## Soft Delete

Soft Delete는 lifecycle/use case가 요구할 때만 적용한다.

기존 convention이 없는 신규 모델의 fallback:

```text
deleted_at
deleted_by
```

`is_deleted`는 기존 project convention이나 명확한 요구가 있을 때만 허용한다. 업무상 종료/해지/만기/유효기간 종료는 Soft Delete와 분리한다.

## 원칙

- nullable은 편의가 아니라 데이터 의미다.
- default가 과거 row와 신규 row에 같은 의미인지 확인한다.
- FK cascade는 lifecycle ownership이 분명할 때만 사용한다.
- index는 모든 FK/검색 column에 기계적으로 추가하지 않고 query/selectivity/write pattern을 본다.
- monetary/quantity 값은 precision/scale과 rounding 책임을 명시한다.
- vendor-specific type/index 선택은 target DBMS/version evidence를 요구한다.
- 신규 fallback convention은 기존 schema를 자동 rename하기 위한 기준이 아니다.

## Handoff

```text
Schema Decisions:
- Subject Area / Physical Table Mapping:
- Data Naming Source:
- Keys / Identifier Strategy:
- Audit / Soft Delete:
- Constraints:
- Types/Precision:
- Indexes:
- Vendor-specific Mapping:
- Integrity Risks:
```
