---
name: dev-data-modeling
description: Use Case에서 데이터 책임·소유권·lifecycle·cardinality·Current/History/Snapshot/Derived를 모델링하고 DBML relational model로 표현하는 DBMS 중립 capability.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, data, modeling, erd, dbml, relationship, cardinality]
    related_skills: [dev-data-feature, dev-db-schema, dev-db-migration]
    requires_tools: [terminal]
---

# dev-data-modeling

데이터 구조의 의미와 관계를 설계한다. 특정 DBMS DDL이나 ORM annotation을 먼저 선택하지 않는다.

## 실행 순서

```text
1. Use Case와 business rule 확인
2. 기존 domain/data model reference 확인
3. 책임/ownership/lifecycle 분류
4. Current / History / Snapshot / Derived 구분
5. cardinality와 관계 lifecycle 검증
6. relational table/association 결정
7. DBML 변경안 작성
8. Use Case로 재검증
```

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

기존 프로젝트 표준이 없으면 `docs/data/schema.dbml`을 기본 relational model로 사용한다.

```text
Data Model Mode: LOGICAL_RELATIONAL
```

이 기본 mode에서는 vendor-specific physical option을 최소화한다.

DBML 변경 후 lightweight guard:

```bash
python3 /opt/custom-skills/shared/dev-data-modeling/scripts/dbml_guard.py \
  --path docs/data/schema.dbml \
  --mode logical
```

이 guard는 full DBML parser가 아니다. duplicate Table, top-level Ref target, logical mode의 vendor-specific token 위험만 빠르게 점검한다. 실제 syntax/rendering은 프로젝트의 DBML parser/CI 또는 DBML Canvas 같은 Human View로 확인한다.

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
migration/backfill
```

## Handoff

```text
Data Modeling:
- Responsibilities:
- Ownership/Lifecycle:
- Cardinality:
- Current/History/Snapshot/Derived:
- DBML Changes:
- Use Cases Validated:
- Open Model Questions:
```
