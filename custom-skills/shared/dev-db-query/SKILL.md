---
name: dev-db-query
description: Business Query를 관계형 Query Intent로 먼저 정의하고 ANSI SQL 전략을 우선한 뒤 필요할 때만 DBMS dialect를 적용하는 query capability.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, database, sql, query, join, cte, window]
    related_skills: [dev-data-feature, dev-db-performance, dev-spring-data]
    requires_tools: [terminal]
---

# dev-db-query

SQL syntax보다 Query Intent와 결과 semantics를 먼저 확정한다.

예:

```text
각 account별 최신 snapshot 1건
→ partition/order/rank semantics 결정
→ ANSI window strategy 검토
→ 필요할 때만 vendor-specific 대안
```

## 실행 순서

1. 기대 row grain을 한 문장으로 정의한다.
2. duplicate/null/outer join semantics를 확인한다.
3. filter/order/group/paging requirement를 명시한다.
4. 기존 query/repository pattern을 확인한다.
5. ANSI JOIN/CTE/window/aggregate로 표현 가능한지 먼저 본다.
6. vendor dialect가 필요하면 해당 vendor reference를 적용한다.
7. test data로 edge case와 deterministic order를 검증한다.

## 주의

- `DISTINCT`로 잘못된 join cardinality를 숨기지 않는다.
- `NOT IN` + NULL, outer join predicate 위치 등 3-valued logic 영향을 확인한다.
- pagination은 stable ordering key를 갖는지 확인한다.
- application loop 안 반복 query보다 set/batch query를 우선 검토한다.
- Native SQL이 Spring/JPA query 선택과 연결되면 `dev-spring-data` 정책도 함께 따른다.

## Handoff

```text
Query Intent / Row Grain:
Join/Cardinality:
Null/Duplicate Semantics:
Dialect Used: ANSI | <vendor>
Deterministic Ordering/Paging:
Verification:
```
