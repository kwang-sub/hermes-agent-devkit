# Data Design Rules

이 문서는 DBMS·ORM·언어와 무관하게 데이터 모델링, 관계형 스키마, SQL, migration, 성능 작업에 적용하는 공통 Foundation 규칙이다.

`coding-rules.md`, `implementation-decision-rules.md`, `project-pattern-rules.md`를 대체하지 않고 데이터 영역 판단을 확장한다.

## 1. 설계 순서와 역할 경계

데이터 구조는 컬럼 수나 특정 ORM 제약부터 시작하지 않는다.

```text
Use Case / Business Rule
→ 책임과 소유권
→ lifecycle
→ cardinality
→ Current / History / Snapshot / Derived 구분
→ Subject Area
→ transaction / concurrency 경계
→ logical relational model
→ DBA Logical Model Approval
→ Coder physical DBMS mapping
→ Flyway/Liquibase migration / implementation
```

테이블 분리는 컬럼 개수만으로 결정하지 않는다. 책임, 소유권, 생명주기, 관계, 변경 주기, 무결성, transaction 경계, 성능과 확장성을 근거로 판단한다.

책임은 다음처럼 분리한다.

```text
DBA logical modeling
- Subject Area
- logical table / relation / cardinality
- ownership / lifecycle
- business invariant
- canonical logical DBML

Coder physicalization
- physical table/type/key/index/constraint
- target DBMS mapping
- Flyway/Liquibase migration
- project-controlled migration verification
- persistence mapping impact
```

DBA logical model은 `tbl_*` 물리 이름, vendor-specific DDL, migration file을 source of truth로 만들지 않는다.

## 2. 데이터 성격 구분

최소 다음을 구분한다.

```text
Current State
- 현재 상태를 빠르게 읽기 위한 데이터

History / Ledger
- 사건·거래·변경 이력을 보존하는 원장성 데이터

Snapshot
- 특정 시점의 계산/상태를 재현하기 위한 고정 결과

Derived Data
- 다른 source에서 재계산 가능한 파생 데이터
```

파생 값을 저장하면 source of truth, 갱신 시점, 정합성 복구 방법을 명시한다.

## 3. 관계와 소유권

- 1:1 / 1:N / N:M cardinality를 Use Case로 검증한다.
- FK 방향은 단순 조회 편의가 아니라 소유권과 lifecycle을 반영한다.
- N:M은 관계 자체에 속성이 있거나 lifecycle이 있으면 association entity/table을 우선 검토한다.
- Aggregate 또는 domain boundary와 DB FK는 동일 개념이 아니다. DB 제약은 데이터 무결성을, Aggregate는 변경 일관성 경계를 표현한다.
- soft delete, tenant, version, status 같은 공통 컬럼은 프로젝트의 기존 정책을 먼저 확인한다.

## 4. 무결성

다음은 application code만으로 암묵적으로 유지하지 말고 DB constraint와 application 책임을 함께 검토한다.

```text
PK / candidate key
FK
UNIQUE
NOT NULL
CHECK 또는 동등한 validation
Default
Optimistic/pessimistic concurrency control
```

DB constraint가 실제 업무 불변식을 안전하게 표현할 수 있으면 우선 검토한다. 단, legacy compatibility 또는 migration 위험 때문에 즉시 적용하기 어렵다면 이유와 단계적 적용 전략을 기록한다.

DBA logical model은 constraint의 **업무 의미**를 확정하고, target DBMS의 실제 DDL 표현은 Coder physicalization이 결정한다.

## 5. 기존 Convention 우선과 신규 프로젝트 Fallback

식별자·table/column naming·audit·soft delete 규칙은 기존 프로젝트 evidence를 최우선으로 한다. `schema.dbml`이 없다는 이유만으로 신규 프로젝트라고 단정하지 않는다.

판정 순서는 다음을 기본으로 한다.

```text
1. repository/project의 명시적 data/schema 규칙
2. 기존 DBML / ERD / migration / DDL / schema-as-code
3. JPA Entity 등 persistence model의 @Table / @Column / @Id convention
4. 제공되거나 안전하게 확인 가능한 실제 DB schema
5. 위 evidence가 모두 없을 때만 DEVKIT_DEFAULT
```

Data Naming Source는 다음 중 하나로 기록한다.

```text
PROJECT_EXISTING
- 명시적 schema/data convention이 존재

PROJECT_INFERRED
- 기존 Entity/migration/DDL/schema에서 일관된 convention을 추론

DEVKIT_DEFAULT
- 유효한 기존 convention evidence가 없는 신규 데이터 모델
```

`DEVKIT_DEFAULT`는 기존 프로젝트를 일괄 rename하거나 migration하는 기준이 아니다.

## 6. Subject Area / Logical Naming

Subject Area는 화면 메뉴나 임시 기능명이 아니라 데이터 책임을 묶는 안정적인 업무 영역이다.

```text
예: household, investment, market, budget
```

규칙:

- lowercase snake_case.
- 기존 승인 Subject Area 우선 재사용.
- 신규 Subject Area는 책임/소유권/lifecycle 근거 필요.
- `common`, `misc`, `etc`, `management`, `data` 같은 포괄 이름은 실제 독립 책임 근거 없이 fallback으로 사용하지 않는다.
- 하나의 canonical logical table은 기본적으로 하나의 Subject Area에 속한다.
- canonical DBML에서는 `TableGroup <subject_area>`를 machine-readable Subject Area 표현으로 사용한다.

신규 canonical logical model의 table 이름은 Subject Area 안의 local entity 이름을 우선한다.

```text
Subject Area: investment
Logical Table: account
```

기존 logical model이 `investment_account`처럼 주제영역 prefix를 이미 사용하면 대규모 rename하지 않는다. 물리화 시 Coder가 prefix를 정확히 한 번만 조합한다.

## 7. DEVKIT_DEFAULT Physical Naming

기존 physical convention evidence가 전혀 없는 신규 migration-managed schema에서 Coder fallback은 다음과 같다.

```text
Physical DB table → tbl_<subject_area>_<entity>
DB column         → snake_case
Java Entity       → PascalCase
Java field        → camelCase
Internal PK       → id
Internal FK       → <referenced_entity>_id
Public ID         → public_id        # 실제 외부 공개 식별자가 필요할 때만
External ID       → external_id      # 외부 시스템 식별자를 저장할 실제 요구가 있을 때만
```

예:

```text
Subject Area: investment
Logical Table: account
Physical Table: tbl_investment_account
```

물리 이름 규칙:

- `tbl_` prefix 필수.
- 승인된 Subject Area만 사용.
- lowercase snake_case.
- Coder가 `inv`, `mkt` 같은 임의 약어를 발명하지 않는다.
- logical table이 `investment_account`이면 `tbl_investment_account`로 만들고 `tbl_investment_investment_account`로 중복하지 않는다.

SQL reserved word와 target DBMS identifier 제약은 Coder physical mapping 단계에서 확인한다.

`public_id`는 application이 소유하는 외부/API/Event 식별자다. 내부 FK/JOIN은 특별한 근거가 없으면 internal PK를 사용한다. `external_id`는 다른 시스템이 소유하는 식별자이므로 `public_id`와 동일 개념으로 취급하지 않는다.

인증 Provider가 발급하는 사용자 식별자는 application-owned domain identifier와 lifecycle/ownership을 분리한다. 특정 인증 제품의 column 이름이나 identity table 구조를 Data Foundation의 신규 기본 컬럼으로 강제하지 않는다.

## 8. Identifier Strategy

Identifier는 역할을 먼저 구분한 뒤 물리 생성 전략을 선택한다.

```text
Internal / Domain ID
- DB 내부 PK/FK/Join과 application-owned identity

Public / External-facing ID
- API/URL/Event 등 외부 경계에서 공개 가능한 application-owned identifier

External System ID
- 다른 시스템이 발급하고 소유하는 identifier
```

### Internal PK

단일 primary DB, 높은 FK/JOIN 밀도, DB 중심 ID 생성이면 `BIGINT + IDENTITY/SEQUENCE/AUTO_INCREMENT` 계열을 우선 검토할 수 있다. 이 선택은 target DBMS evidence가 있는 Coder physicalization 단계에서 확정한다.

여러 node/service가 DB INSERT 전 ID를 생성해야 하거나 multi-writer/distributed/offline 생성처럼 전역 충돌 회피가 중요한 경우 UUID 계열을 검토한다.

UUID가 필요한 신규 설계에서 시간 정렬성과 index locality가 중요하면 UUIDv7을 우선 검토하되, 실제 application/runtime/DBMS의 지원과 기존 project convention을 확인한다. UUIDv4 등 기존 전략을 근거 없이 교체하지 않는다.

### Dual ID

내부 관계에는 compact sequential key가 유리하지만 외부에는 opaque/global identifier가 필요한 경우 다음과 같은 Dual ID를 사용할 수 있다.

```text
id        → internal PK
public_id → UNIQUE external-facing identifier
```

둘이 존재한다는 이유만으로 `(id, public_id)`를 composite PK로 만들지 않는다. Composite PK는 실제 relational/business identity가 복수 column으로 구성될 때만 별도 근거로 선택한다.

`public_id`가 필요하지 않은 내부 Entity/History/Snapshot까지 기계적으로 추가하지 않는다.

## 9. Audit Convention

기존 convention이 없는 신규 mutable business table의 기본 audit naming은 다음과 같다.

```text
created_at
created_by
updated_at
updated_by
```

Java/JPA field 기본 naming은 다음과 같다.

```text
createdAt
createdBy
updatedAt
updatedBy
```

시간 audit 값은 논리적으로 UTC Instant 시점을 표현한다. 실제 `timestamp`/`timestamptz`/`datetime2` 등 물리 type은 target DBMS와 project convention으로 mapping한다.

사용자 Actor를 application이 식별할 수 있으면 `created_by` / `updated_by`에는 외부 인증 Provider의 raw identifier보다 application-owned internal user identifier를 우선한다. System/Batch actor를 `0`, `-1` 같은 magic ID로 자동 정의하지 않는다.

Audit column은 모든 table에 기계적으로 추가하지 않는다. Append-only History/Ledger는 update audit가 의미 없을 수 있고, Snapshot/Derived/association table은 생성·수정 책임에 따라 필요한 audit만 둔다.

## 10. Soft Delete Convention

Soft Delete는 모든 Entity의 기본 기능이 아니다. 삭제 후 데이터 보존이 필요한 lifecycle/use case가 있을 때만 적용한다.

기존 convention이 없고 Soft Delete를 실제 채택하는 신규 모델의 fallback은 다음이다.

```text
deleted_at
deleted_by
```

판정:

```text
deleted_at IS NULL     → active / not deleted
deleted_at IS NOT NULL → soft deleted
```

`deleted_by`는 사용자 Actor가 존재하면 `created_by` / `updated_by`와 동일한 application-owned internal user identifier 규칙을 따른다.

`is_deleted` Boolean은 기존 프로젝트 convention 또는 명확한 요구가 있을 때 사용할 수 있지만 DEVKIT_DEFAULT는 아니다. 특별한 이유 없이 `is_deleted + deleted_at`을 동시에 두어 두 개의 delete source of truth를 만들지 않는다.

Soft Delete와 업무 lifecycle 종료를 구분한다. 계좌 해지, 계약 종료, 만기, 유효기간 종료 같은 업무 상태를 단순히 `deleted_at`으로 표현하지 않고 `status`, `closed_at`, `ended_at`, `valid_to` 등 도메인 의미로 모델링한다.

## 11. 논리 모델과 물리 모델 분리

기본 사고 순서는 다음이다.

```text
DBA Logical / Relational Intent
→ Subject Area + logical DBML approval
→ Coder Target DBMS/version evidence
→ Physical naming/type/index/DDL
→ Migration implementation
```

`IDENTITY`, `AUTO_INCREMENT`, vendor-specific index option, proprietary JSON type처럼 DBMS에 종속되는 선택은 Coder 물리 단계에서 결정한다.

Target DBMS/version을 모르면 vendor-specific syntax를 추측하지 않는다.

## 12. DBML 문서 계약

새 프로젝트 또는 별도 데이터 문서 규칙이 없는 프로젝트의 기본 relational model artifact는 다음을 권장한다.

```text
docs/data/schema.dbml
```

역할:

```text
domain-model.md      = 도메인 책임/lifecycle 설명
schema.dbml          = canonical logical relational model / ERD source
data-dictionary.md   = DBML만으로 부족한 업무 의미·불변식
decisions/           = 중요한 설계 결정과 trade-off
migrations/          = 복잡하거나 위험한 migration 계획/evidence
```

Canonical logical DBML은 Subject Area를 `TableGroup`으로 표현한다. 물리 table 이름을 논리 DBML의 source of truth로 만들지 않는다.

Canonical logical DBML의 사람이 읽는 논리명/설명은 DBML 표준 `Note`를 사용한다.

```text
Table Note 첫 줄   = 한글 논리 테이블명
Table Note 다음 문단 = 테이블 책임/업무 의미 설명
Column note        = 한글 논리 컬럼명
```

영문 lowercase snake_case table/column 식별자는 유지하며, 별도 `logical_name` custom property를 DevKit canonical 규격으로 정의하지 않는다. 이 규칙은 특정 IDE plugin이나 외부 DBML renderer에 종속되지 않는 문서 계약이다. 기존 프로젝트에 명시적인 DBML 문서 규격이 있으면 PROJECT_EXISTING을 우선한다.

기존 프로젝트가 다른 ERD/schema-as-code 규칙을 이미 사용하면 기존 규칙이 우선한다.

DBML Canvas, dbdiagram.io 같은 시각화 도구는 `schema.dbml`의 Human View다. DevKit 실행 자체가 특정 IDE plugin이나 외부 웹 서비스에 의존하지 않는다.

Mermaid ERD는 설명용 파생 문서로 사용할 수 있지만 DBML과 동시에 독립적인 source of truth로 관리하지 않는다.

## 13. DBML 모델 모드

```text
LOGICAL_RELATIONAL
- DBA canonical output 기본값
- Subject Area, 관계, 키 intent, nullable 의미, portable type 중심
- vendor-specific physical option 제외

PHYSICAL
- 기존 프로젝트가 이미 physical DBML을 source of truth로 관리하는 경우의 PROJECT_EXISTING evidence
- 신규 DBA canonical output 기본값이 아님
```

기존 Physical DBML 프로젝트를 자동 변환하지 않는다. 신규 physical 구현 source는 Flyway/Liquibase migration을 우선한다.

## 14. Migration Tool / Version Policy

기존 project migration framework가 있으면 유지한다.

```text
Existing Flyway only    → Flyway
Existing Liquibase only → Liquibase
둘 다 탐지             → ownership conflict로 BLOCK
없음                    → 신규 프로젝트 기본 Flyway
```

신규 Flyway 기본 version은 UTC timestamp다.

```text
V<yyyyMMddHHmmss>__<lowercase_snake_case_description>.sql
```

기존 프로젝트의 일관된 Flyway version convention은 유지한다. 이미 shared/prod environment에 적용된 versioned migration은 수정하지 않고 새로운 migration을 추가한다. `outOfOrder=true`를 자동 활성화하지 않는다.

## 15. 문서 변경 최소화

```text
QUERY_ONLY    → schema 문서 변경 불필요가 기본
MODEL_CHANGE  → Subject Area + schema.dbml + domain 의미 검토
SCHEMA_CHANGE → logical model 승인 + Coder migration 영향 검토
MIGRATION     → Coder migration + compatibility / roll-forward evidence
PERFORMANCE   → logical 의미가 실제로 바뀔 때만 DBA model 반영
```

현재 Task와 관계없는 전체 data dictionary 재작성이나 ERD formatting을 섞지 않는다.

## 16. DBMS Vendor 분리

공통 데이터 판단과 vendor-specific 물리 지식을 분리한다.

```text
DBA Common Logical Rules
→ dev-data-feature / dev-data-modeling
→ APPROVED handoff
→ Coder dev-db-migration + dev-db-schema
→ detected DBMS vendor reference
```

MSSQL/MySQL/MariaDB/PostgreSQL/Oracle 차이는 별도 vendor reference로 lazy-load하고, DBA logical model을 특정 DBMS 문법으로 오염시키지 않는다.

## 17. Use Case 검증

ERD/DBML은 그림 자체가 완료 조건이 아니다. 관련 Use Case로 검증한다.

```text
생성 / 수정 / 상태 전이 / 삭제·종료
1:N 추가·제거 / 중복 입력 / 동시 수정
이력 보존 / 대량 조회·페이징 / migration·backfill에 필요한 업무 의미
```

설계가 Use Case를 설명하지 못하면 테이블을 먼저 늘리기보다 책임과 관계를 다시 검토한다.

## 18. 운영 작업 경계

DBA Foundation과 logical modeling capability는 Design-Time DBA다.

Coder `dev-db-migration`은 repository의 Flyway/Liquibase migration을 구현하고 project-controlled local/test/CI에서 검증할 수 있지만, 운영 DB 직접 ad-hoc DDL/DML 실행, backup/restore, session kill, 통계 강제 갱신, 운영 index maintenance, 권한/계정 변경 권한을 자동으로 부여하지 않는다.

SQL/migration 생성·검토와 실제 production 적용 권한은 분리한다.
