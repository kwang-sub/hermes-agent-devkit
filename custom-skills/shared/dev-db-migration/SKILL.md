---
name: dev-db-migration
description: 승인된 DBA logical model을 별도 승인된 마이그레이션 단계에서 target DBMS 물리 schema로 변환하고 기존 migration convention을 존중해 Flyway-first/Liquibase-compatible migration을 작성·검증할 때 구현 단계가 실행하고 자체 검토 단계가 read-only 기준으로 공유하는 DB migration capability.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, database, physicalization, migration, flyway, liquibase, ddl, compatibility, work-unit]
    related_skills: [dev-data-feature, dev-data-modeling, dev-db-schema, dev-spring-data]
    requires_tools: [terminal, skill_view]
---

# dev-db-migration

DB physicalization / migration capability다. `/opt/data/shared/references/lite-development-contract.md`를 따른다. 현재 세션이 구현과 자체 검토를 수행하며 독립 Reviewer·Worker를 요구하지 않는다.

## 시작 조건과 권한
새 테이블 또는 의미 있는 schema 변경은 합의된 logical model/DBML, 업무 제약, 대상 DBMS/버전, 기존 migration tool과 배포 순서가 필요하다. 기존 schema의 작은 보정은 해당 근거를 재사용하고 불필요하게 새 DBML을 요구하지 않는다.

설계만 요청했거나 logical model이 미확정이면 migration 파일을 자동 작성하지 않는다. 구현까지 명시 요청한 경우 같은 세션에서 합의된 물리화로 진행할 수 있다. `Work Unit Class`, Kanban Task, profile, 별도 Dispatch는 입력 조건이 아니다.

논리 의미를 변경해야 하면 영향과 변경안을 확인한 뒤 진행한다. 파일 작성·local/test 검증과 운영 DB 실제 적용은 별도 권한이다. Production은 프로젝트의 승인된 deployment/migration pipeline을 따른다.

## 검토
logical ↔ physical mapping, naming/version/order, backward compatibility, rollback/backfill, 검증 evidence를 확인한다. 리뷰만 요청했으면 파일을 수정하지 않으며 수정 요청이 있으면 같은 세션에서 반영한다.

## 구현 단계 책임

```text
기존 migration framework/convention 탐지
Target DBMS/version 확인
Logical → Physical table mapping
DBMS-specific type / identifier generation
PK/FK/UNIQUE/NOT NULL/CHECK/default
Index
Backward compatibility / backfill / deployment order
Flyway 또는 Liquibase migration 작성
project-controlled local/test/CI migration 실행·검증
JPA @Table/@Column 등 persistence mapping 영향 반영
```

## Migration Tool Resolution

항상 기존 프로젝트 evidence를 먼저 본다.

```text
Existing Flyway only    → Flyway 유지
Existing Liquibase only → Liquibase 유지
Flyway + Liquibase      → CONFLICT / BLOCK
기존 명시적 migration convention → 기존 convention 우선
아무 migration framework도 없는 신규/승인 프로젝트 → Flyway 기본
사용자가 Liquibase를 명시 → Liquibase
```

기존 migration tool을 편의상 교체하지 않는다. 신규 프로젝트 기본값은 **Flyway**다.

먼저 bounded helper를 실행할 수 있다.

```bash
python3 /opt/custom-skills/shared/dev-db-migration/scripts/migration_guard.py \
  --root "<module-or-project-root>" \
  --json
```

`MIGRATION_TOOL=conflict`이면 자동 진행하지 않는다.

## Physical Naming

프로젝트에 명시적 기존 물리 naming convention이 있으면 그것을 우선한다. 신규 `DEVKIT_DEFAULT`는 다음이다.

```text
Physical Table = tbl_<subject_area>_<entity>
```

규칙:

1. `tbl_` prefix 필수.
2. `<subject_area>`는 DBA가 승인한 Subject Area만 사용한다.
3. 구현 단계가 Subject Area를 임의 생성·변경·축약하지 않는다.
4. lowercase snake_case를 사용한다.
5. logical table이 이미 `<subject_area>_` prefix를 갖는 legacy 형태라면 정확히 한 번만 제거한다.
6. `tbl_investment_investment_account` 같은 중복 prefix를 만들지 않는다.
7. `master`, `info`, `data`, `temp` 같은 모호한 suffix/prefix를 의미 없이 추가하지 않는다.

예:

```text
Subject Area: investment
Logical Table: account
→ tbl_investment_account

Subject Area: investment
Legacy Logical Table: investment_account
→ tbl_investment_account
```

helper로 deterministic mapping을 확인할 수 있다.

```bash
python3 /opt/custom-skills/shared/dev-db-migration/scripts/migration_guard.py \
  --root "<root>" \
  --subject-area investment \
  --logical-table investment_account
```

## Physical Schema Decision

구현 단계가 실제 물리 판단이 필요할 때 `skill_view("dev-db-schema")`를 로드한다.

```text
Approved logical intent
→ Subject Area / physical name
→ project convention
→ DBMS/version
→ physical type / key generation
→ constraints
→ access pattern / indexes
→ compatibility / migration order
```

논리 DBML 자체를 physical table 이름으로 재작성하는 것을 기본으로 하지 않는다. Logical DBML은 DBA source of truth로 유지하고 migration이 physical implementation source다.

## Flyway Policy

### Existing project

기존 Flyway 프로젝트가 이미 `V1`, `V1_1`, release-version 등 일관된 version convention을 사용하면 그 convention을 보존한다. 신규 default를 이유로 과거 migration을 rename/rewrite하지 않는다.

### New/default project

기존 Flyway version convention이 없는 경우 기본 format:

```text
V<yyyyMMddHHmmss>__<description>.sql
```

- timestamp는 **UTC** 기준이다.
- description은 lowercase snake_case 영어로 실제 DB 변경을 설명한다.
- 날짜만(`yyyyMMdd`) 사용하지 않는다.
- migration version을 업무 주제영역 번호처럼 사용하지 않는다.

예:

```text
V20260916140615__create_investment_account.sql
V20260917101522__add_account_type.sql
V20260918142351__add_holding_account_fk.sql
```

새 version 발급:

```bash
python3 /opt/custom-skills/shared/dev-db-migration/scripts/migration_guard.py \
  --root "<root>" \
  --allocate-flyway-version
```

같은 worktree에 동일 second version이 있으면 helper는 다음 비어 있는 UTC second를 사용한다. 서로 다른 branch/worktree 간 충돌은 merge/CI Gate에서 다시 확인한다.

### Immutable versioned migration

한 번 shared environment 또는 production에 적용된 versioned migration은 수정하지 않는다.

```text
기존 V...sql 수정 ❌
새 V...sql 추가 ✅
```

Flyway checksum mismatch를 파일 재작성으로 숨기지 않는다.

### Out-of-order

`outOfOrder=true`를 자동 활성화하지 않는다.

장기 branch가 merge되면서 신규 migration version이 현재 deployed version보다 낮아졌다면:

```text
아직 shared environment에 적용되지 않은 migration → merge 전에 새 유효 version으로 재발급 검토
이미 적용된 migration → history/compatibility evidence를 보존하고 명시적 운영 결정 필요
```

`--deployed-version` evidence가 있으면 helper로 ordering을 검사한다. deployed version evidence가 없으면 “검사했다”고 주장하지 않는다.

### Repeatable migration

`R__`는 project convention과 대상 object 성격에 따라 View/Function/Procedure처럼 정의 전체 재적용이 자연스러운 경우에 검토한다. Table/column/FK 같은 구조 변경을 Repeatable로 우회하지 않는다.

## Liquibase Policy

기존 Liquibase 프로젝트에서는 기존 master changelog와 XML/YAML/JSON/SQL format, include 구조, changeset id/author convention을 유지한다.

```text
기존 changelog 구조 유지
새 changeset 추가
기존 적용 changeset 임의 수정 금지
rollback은 실제 데이터 복원이 안전할 때만 작성
```

Flyway 기본 정책을 이유로 Liquibase 프로젝트에 Flyway를 병행 추가하지 않는다.

## Compatibility / Deployment Plan

위험 변경은 최소 다음을 검토한다.

```text
column/table drop 또는 rename
nullable → NOT NULL
type/precision 축소
UNIQUE/FK/CHECK 신규 적용
large backfill
large-table index build
data rewrite
enum/code 의미 변경
```

필요하면:

```text
Expand
→ old/new application compatibility
→ Backfill
→ Constraint/Index enforcement
→ Contract/Cleanup
```

모든 변경에 expand-contract를 기계적으로 적용하지 않는다.

## Spring / JPA Schema Ownership

Flyway/Liquibase가 schema source of truth인 환경에서는 Hibernate schema mutation을 함께 사용하지 않는다.

권장:

```yaml
spring:
  jpa:
    hibernate:
      ddl-auto: validate
```

기존 프로젝트 설정을 task 범위 밖에서 강제 변경하지 않지만 다음 충돌은 명시한다.

```text
migration-managed production + ddl-auto=create/update
Flyway + Liquibase 무계획 혼용
Flyway/Liquibase + schema.sql 이중 schema ownership
```

## Verification Gate

구현 단계는 가능한 범위에서 다음을 수행하고 자체 검토 단계는 그 evidence와 실제 diff를 대조한다.

```text
1. migration tool/convention detection
2. physical table mapping 확인
3. duplicate migration version 확인
4. current deployed version evidence가 있으면 ordering 확인
5. Flyway: validate 또는 프로젝트 동등 검증
6. clean install migration test
7. current supported schema → target upgrade test
8. backfill row count / invariant
9. constraint violation case
10. post-migration application/JPA mapping test
```

`flyway clean`은 production/shared DB에 사용하지 않는다. 격리된 test schema/container에서만 프로젝트 정책에 따라 사용한다.

## Handoff

```text
Work Unit Class: MIGRATION
Work Unit Boundary: SINGLE_UNIT
Logical Model Status / DBML:
Migration Tool / Evidence:
Target DBMS / Version:
Subject Area → Physical Table Mapping:
Physical Schema Decisions:
Migration Files:
Flyway Version Policy:
Deployed Version Evidence:
Compatibility Window:
Backfill:
Lock/Rewrite Risk:
Deployment Order:
Rollback/Roll-forward:
JPA Mapping Impact:
Verification:
Intentional Deviations:
Residual Risk:
```
