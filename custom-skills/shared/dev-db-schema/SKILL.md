---
name: dev-db-schema
description: 승인된 relational model을 PK/FK/UNIQUE/nullability/default/type/index/constraint 중심의 physical schema로 구체화하는 DBMS 중립 capability.
version: 0.1.0
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
identifier generation
index key/order/include/partial/function 등 vendor option
```

## 원칙

- nullable은 편의가 아니라 데이터 의미다.
- default가 과거 row와 신규 row에 같은 의미인지 확인한다.
- FK cascade는 lifecycle ownership이 분명할 때만 사용한다.
- index는 모든 FK/검색 column에 기계적으로 추가하지 않고 query/selectivity/write pattern을 본다.
- monetary/quantity 값은 precision/scale과 rounding 책임을 명시한다.
- vendor-specific type/index를 선택할 때는 `dev-data-feature`의 해당 vendor reference를 읽는다.

## DBML

`LOGICAL_RELATIONAL` DBML에서는 물리 옵션을 과도하게 넣지 않는다.

`PHYSICAL` mode에서는 실제 target DBMS와 migration이 일치하도록 type/index/constraint를 반영할 수 있다.

## Handoff

```text
Schema Decisions:
- Keys:
- Constraints:
- Types/Precision:
- Indexes:
- Vendor-specific Mapping:
- Integrity Risks:
```
