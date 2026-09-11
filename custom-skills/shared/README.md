# Shared Custom Skills

`custom-skills/shared`는 `orchestrator`, `coder`, `reviewer`가 공통으로 참조하는 Hermes Custom Skill 원본 디렉터리입니다.

## 관리 원칙

- 역할 전용 Skill은 `custom-skills/orchestrator`, `custom-skills/coder`, `custom-skills/reviewer`에서 관리합니다.
- 둘 이상의 프로필이 동일 규칙/기능을 사용하면 이 디렉터리에 한 벌만 둡니다.
- 세 프로필은 자신의 역할 디렉터리와 `/opt/custom-skills/shared`를 함께 `skills.external_dirs`로 참조합니다.
- Foundation 규칙은 `/opt/data/shared/references`에 두고 언어/프레임워크/기능 전문 지식만 capability Skill로 분리합니다.
- Public Skill/외부 provider/IDE plugin은 직접 Workflow에 박지 않고 DevKit adapter/capability 뒤에 둡니다.

## Backend

```text
dev-java-guidelines
dev-kotlin-guidelines
dev-spring-guidelines
dev-spring-feature
dev-spring-data
dev-spring-test
dev-spring-refactor
```

## Frontend

```text
dev-frontend-feature        # canonical frontend entry
dev-typescript-guidelines
dev-frontend-guidelines
dev-nextjs-feature
dev-frontend-test
dev-figma-design            # Figma REST read-only design evidence
dev-ui-ux                   # audited UI/UX quality baseline
```

Frontend Task는 `dev-frontend-feature`를 runtime entry로 사용하고 세부 capability는 실제 evidence에 따라 lazy-load합니다.

## Data / Design-Time DBA

```text
dev-data-feature            # canonical data/DB entry
dev-data-modeling           # responsibility/lifecycle/cardinality/DBML
dev-db-schema               # key/constraint/type/index
dev-db-query                # query intent/SQL dialect
dev-db-migration            # DDL/backfill/compatibility
dev-db-performance          # execution plan/index/locking evidence
```

Data Skill은 특정 DBMS에 종속되지 않습니다. 공통 판단 후 실제 target이 필요한 경우에만 다음 vendor reference를 lazy-load합니다.

```text
MSSQL
MySQL
MariaDB
PostgreSQL
Oracle
```

기존 프로젝트에 별도 표준이 없으면 `docs/data/schema.dbml`을 canonical relational model 기본값으로 권장합니다. IntelliJ의 DBML Canvas 같은 plugin은 Human ERD View로 활용할 수 있지만 DevKit runtime 의존성은 아닙니다.

운영 DB 직접 DDL/DML, backup/restore, session kill, index maintenance 등은 현재 Data Skill의 책임이 아닙니다. 그런 권한이 실제 필요해질 때 별도 DBA profile/운영 Skill을 검토합니다.

## Cross-stack

```text
dev-api-contract
dev-api-docs
dev-api-spec
```

## Figma

현재 `dev-figma-design`은 Figma 공식 REST API를 read-only provider로 사용합니다.

```text
FIGMA_ACCESS_TOKEN
→ Personal Access Token 또는 Plan REST Access Token

FIGMA_OAUTH_TOKEN
→ OAuth access token
```

선택한 frame/component의 `node-id` URL을 우선해 bounded context를 읽고, 필요 시 rendered preview를 `HERMES_WRITE_SAFE_ROOT` 안에 저장합니다.

## Java legacy

legacy `java-project-conventions`를 새 Task에서 사용하지 않습니다. Java convention은 canonical `dev-java-guidelines`를 사용합니다.
