---
name: dev-db-migration
description: Schema/data 변경을 backward compatibility·backfill·deployment order·rollback/roll-forward 관점에서 설계하는 DBMS 중립 migration capability.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, database, migration, ddl, backfill, compatibility]
    related_skills: [dev-data-feature, dev-data-modeling, dev-db-schema]
    requires_tools: [terminal]
---

# dev-db-migration

실행 가능한 migration을 만들기 전에 구버전 application/기존 data와의 compatibility를 설계한다.

## Migration Plan

```text
Current Schema
Target Schema
Expand Step
Application Compatibility
Backfill
Constraint/Index Enforcement
Contract/Cleanup Step
Verification
Rollback 또는 Roll-forward
```

모든 변경에 expand-contract가 필요한 것은 아니다. rolling deployment/대용량/호환성 위험이 있을 때 적용한다.

## 위험 변경

```text
column/table drop
rename
nullable → NOT NULL
type/precision 축소
unique/FK/check 신규 적용
large backfill
index build on large table
data rewrite
enum/code 의미 변경
```

## 원칙

- 기존 migration framework(Flyway/Liquibase/raw SQL 등)를 우선한다.
- 새 migration library를 편의상 추가하지 않는다.
- DDL transactional behavior를 모든 DBMS에서 동일하다고 가정하지 않는다.
- rollback이 데이터 복원을 보장하지 못하면 거짓 rollback script 대신 roll-forward/recovery 조건을 명시한다.
- 운영 DB 직접 실행은 이 Skill의 책임이 아니다.

## Verification

가능한 경우 test/staging schema 또는 project migration test에서 다음을 확인한다.

```text
clean install
upgrade from current version
backfill row count/invariant
old/new application compatibility
constraint violation case
post-migration query
```

## Handoff

```text
Migration Strategy:
Compatibility Window:
Backfill:
Lock/Rewrite Risk:
Deployment Order:
Rollback/Roll-forward:
Verification:
```
