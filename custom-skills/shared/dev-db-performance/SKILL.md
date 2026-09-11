---
name: dev-db-performance
description: 실행계획과 실제 query/cardinality evidence를 기반으로 index·query shape·locking·statistics 병목을 분석하는 DBMS 중립 performance capability.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, database, performance, execution-plan, index, locking]
    related_skills: [dev-data-feature, dev-db-query, dev-db-schema]
    requires_tools: [terminal]
---

# dev-db-performance

성능 튜닝은 index/hint 추가부터 시작하지 않고 측정과 실행계획 evidence부터 시작한다.

## 분석 순서

```text
1. Slow Use Case / target query
2. 실제 parameter/data distribution
3. execution plan 또는 가능한 evidence
4. estimated vs actual cardinality
5. predicate SARGability / implicit conversion
6. join/order/group/paging cost
7. existing index coverage/selectivity
8. lock/transaction/wait 영향
9. 최소 변경 후보
10. before/after verification
```

## Index 판단

- read benefit뿐 아니라 insert/update/delete 비용과 storage를 함께 본다.
- composite key order는 predicate/equality/range/order pattern을 근거로 한다.
- covering/include/partial/function index는 vendor capability와 실제 plan evidence가 있을 때만 사용한다.
- 비슷한 중복 index를 추가하기 전에 기존 index를 확인한다.

## Query 판단

- function/cast로 indexable predicate가 깨지는지 확인한다.
- N+1 또는 loop I/O는 set/batch 전략을 검토한다.
- 큰 OFFSET, 불필요한 wide projection, 중복 sort/hash를 확인한다.
- optimizer hint는 원인 이해보다 먼저 적용하지 않는다.

## Evidence

Vendor별 plan 도구/용어는 `dev-data-feature/references/vendors/<vendor>.md`를 필요할 때만 읽는다.

```text
Performance Baseline:
Plan Evidence:
Root Cause Candidate:
Change:
Before/After:
Write/Lock Trade-off:
Residual Risk:
```
