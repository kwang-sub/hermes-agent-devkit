---
name: dev-infrastructure
description: 애플리케이션과 DB의 실행 위치, host/port endpoint, DB 플랫폼/벤더, 기존 환경과 목표 환경의 전환을 안전하게 감지·계획하는 Infrastructure canonical entry.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, infrastructure, runtime, host, port, docker, compose, database, supabase, transition, reconciliation]
    related_skills: [dev-tech-dispatch, dev-data-feature, dev-db-migration, dev-spring-feature, dev-frontend-feature]
    requires_tools: [terminal, skill_view]
---

# dev-infrastructure

애플리케이션 코드 밖의 **실행 위치와 연결 토폴로지**를 다루는 canonical Infrastructure entry다.
Kubernetes/Terraform/배포 자동화는 현재 범위가 아니며 runtime/endpoint/container/platform/provider 연결만 소유한다.

설정/Secret을 다룰 때는 `/opt/data/shared/references/application-configuration-security.md` 계약을 함께 적용한다.

```text
Application Runtime
- LOCAL_HOST
- NETWORK_HOST
- CONTAINER

Application Endpoint
- host: hostname/address | unknown
- port: 1..65535 | unknown

Database Runtime
- LOCAL_HOST
- NETWORK_HOST
- CONTAINER

Database Endpoint
- host: hostname/address | unknown
- port: 1..65535 | unknown

Database Platform
- NATIVE
- SUPABASE

Database Vendor
- postgresql
- mysql
- mariadb
- mssql
- oracle
- unknown
```

host/port는 credential이 아니다. username/password/token/connection string 전체는 Infrastructure metadata에 저장하지 않는다.

## 기본 정책

명시적인 사용자/Task 요구, 기존 Infrastructure metadata, 명확한 Repository evidence가 모두 없을 때만 다음 Desired 기본값을 사용한다.

```text
Application Runtime = CONTAINER
Database Runtime = CONTAINER
Database Platform = NATIVE
```

중요한 구분:

```text
Observed State
= 실제 Repository evidence만 표현
= evidence가 없으면 UNKNOWN 유지

Desired State
= 사용자 승인 목표 또는 project metadata
= 아무 근거가 없는 신규 프로젝트에서만 기본 정책 사용 가능
```

따라서 Observed의 `UNKNOWN`을 `NATIVE`나 `CONTAINER` 기본값으로 바꾸지 않는다. 신규 프로젝트는 Planner에서 `INITIAL_CONFIGURATION`으로 분류한다.

## Desired State / Observed State

Infrastructure는 최초 생성기가 아니라 reconciliation capability다.

```text
Observed State  = Repository에서 매 실행 시 재계산
Desired State   = 사용자/Task 또는 .hermes/project.yaml의 infrastructure 설정
Transition Plan = Observed와 Desired의 차이
```

사용자가 Standard Flow에서 Infrastructure Desired State를 승인하면 dispatch 단계가 **Primary Repository**의 `.hermes/project.yaml`에 승인 snapshot을 atomic하게 저장한다.

```text
Plan Approval
→ Workspace/Primary Repository 검증
→ Approved Desired State persist
→ Kanban body에 동일 snapshot 보존
→ Coder dispatch
```

Desired State는 구현 성공 여부가 아니라 승인된 목표다. 구현이 중단되어 `Observed != Desired`가 남아도 정상이며 다음 reconciliation에서 drift로 사용한다.

## 실행 순서

1. `scripts/detect_infrastructure.py`로 bounded evidence를 수집한다.
2. 사용자/Task의 명시 Desired State가 있으면 최우선 적용한다.
3. 없으면 프로젝트의 `infrastructure.desired` 값을 사용한다.
4. 그것도 없고 Observed가 명확하면 기존 환경을 보존한다.
5. 모두 없을 때만 신규 Desired에 CONTAINER/NATIVE 기본값을 사용한다.
6. `scripts/plan_transition.py`로 transition class와 Data Migration Gate를 계산한다.
7. Task 범위에 해당하는 Docker/Compose/env/connection 변경만 수행한다.
8. 연결/health/test를 검증한다.
9. 이전 persistent resource는 detach와 destroy를 구분한다.

## 전환 분류

```text
NO_CHANGE
INITIAL_CONFIGURATION
RUNTIME_CHANGE
HOST_CHANGE
PLATFORM_CHANGE
VENDOR_CHANGE
COMBINED_CHANGE
```

예:

```text
CONTAINER PostgreSQL -> LOCAL_HOST PostgreSQL
= RUNTIME_CHANGE

NETWORK_HOST PostgreSQL db-a:5432 -> db-b:5432
= HOST_CHANGE

NETWORK_HOST PostgreSQL db-a:5432 -> LOCAL_HOST localhost:5432
= COMBINED_CHANGE (Runtime + Host)

PostgreSQL -> MySQL
= VENDOR_CHANGE + Data Migration Gate

NATIVE PostgreSQL container -> Supabase Cloud
= RUNTIME_CHANGE + PLATFORM_CHANGE
  vendor는 postgresql로 유지
```

Host/port만 달라지고 runtime/platform/vendor가 같으면 `HOST_CHANGE`다. Host/port와 다른 축이 함께 바뀌면 `COMBINED_CHANGE`다.

## Supabase 모델

Supabase를 Runtime enum으로 만들지 않는다.

```text
Supabase Cloud DB
runtime  = NETWORK_HOST
platform = SUPABASE
vendor   = postgresql

Supabase Local DB
runtime  = CONTAINER
platform = SUPABASE
vendor   = postgresql
```

`NEXT_PUBLIC_SUPABASE_URL` / `SUPABASE_URL`은 Supabase Auth/API provider를 사용한다는 evidence일 뿐 **프로젝트 DB가 Supabase라는 근거가 아니다**.

DB Platform을 `SUPABASE`로 확정하는 강한 근거는 다음을 우선한다.

```text
사용자/Task의 명시 Desired State
supabase/config.toml (Local stack)
SUPABASE_DB_URL / SUPABASE_DATABASE_URL
실제 Supabase DB endpoint evidence
```

Auth-only Supabase 프로젝트의 별도 PostgreSQL/MySQL 등을 Supabase DB로 오인하지 않는다.

`SUPABASE + CONTAINER`를 단일 `postgres` container로 축약하지 않는다. `supabase/config.toml`과 기존 Supabase CLI/local stack을 우선한다.

## Repository evidence

Detector는 bounded scan을 유지하되 일반적인 파일 변형을 지원한다.

```text
Dockerfile
Dockerfile.dev
Dockerfile.prod
Dockerfile.<role>

compose.yml
compose.dev.yml
compose.local.yaml
docker-compose.yml
docker-compose.prod.yml
```

파일명만으로 확정하지 않고 Dockerfile은 `FROM`, Compose는 top-level `services:` evidence를 확인한다.

Spring datasource/JDBC 또는 runtime env에 실제 endpoint가 있으면 host/port evidence로 사용할 수 있다. placeholder나 빈 example 값은 Observed endpoint로 확정하지 않는다.

## Runtime / Configuration 전달 계약

Infrastructure는 runtime topology뿐 아니라 **실제 설정값이 application process까지 전달되는 경로**를 명확히 해야 한다.

```text
Application LOCAL_HOST + Spring
→ Dockerfile/Compose 생성 안 함
→ application.yml|yaml|properties는 신규/변경 시 ${ENV_VAR} 우선
→ IntelliJ Run Configuration 또는 OS Environment가 실제 값 제공

Application LOCAL_HOST + Next.js
→ .env.local이 로컬 실제 값 제공
→ .env.example은 변수명 계약만 Git 추적

Application CONTAINER
→ Dockerfile/Compose 대상
→ .env 또는 deployment environment를 Compose/container environment로 주입
→ 신규 Secret value는 Compose/Application config에 하드코딩하지 않음
```

Spring Boot 자체가 일반적인 `.env`를 자동 로드한다고 가정하지 않는다. `.env`를 사용하는 Container 경로에서는 Compose `env_file`/`environment` 등 **누가 process environment로 주입하는지**를 명시한다.

Supabase의 `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`는 browser-visible 값이므로 Secret은 아니다. 실제 project별 값은 환경별 runtime configuration으로 취급한다. `SUPABASE_SECRET_KEY` / service-role 계열은 server-only secret이다.

## 기존 프로젝트 보안 상태와 이번 Task 위반 구분

Bootstrap의 Preserve First 정책과 Infrastructure implementation gate를 구분한다.

```text
Existing Security Findings
- NONE
- WARN_EXISTING

New Security Violations Introduced By Task
- NONE   # 완료 조건
```

기존 Repository에 이미 tracked secret/hardcoded credential이 있으면 그 사실만으로 Infrastructure 작업 범위를 자동 확장하거나 실패시키지 않는다. 단 이번 Task가 해당 설정을 실제로 수정한다면 신규/변경 부분에는 application configuration security 계약을 적용한다.

이번 Task가 새 secret/credential을 Git tracked config, Dockerfile, Compose, `.env.example`에 추가하는 것은 허용하지 않는다.

## Docker / Compose 책임

`CONTAINER`가 Desired State일 때만 Docker artifact를 생성/수정한다.

```text
Application CONTAINER
→ Dockerfile / .dockerignore / compose service / env / healthcheck

Database CONTAINER + NATIVE
→ DB image / volume / port / healthcheck / network

Database NETWORK_HOST 또는 LOCAL_HOST
→ DB container를 새로 만들지 않음
→ endpoint/env/connection만 조정
```

CONTAINER 기본값은 곧바로 Docker artifact가 존재한다는 뜻이 아니다. `READY | PARTIAL | NOT_CONFIGURED | UNKNOWN` 상태를 evidence로 구분한다.

## Data capability 경계

Infrastructure는 DB가 **어디서 실행되고 어떻게 연결되는지**를 소유한다. 논리/물리 데이터 모델은 소유하지 않는다.

```text
dev-infrastructure
- runtime / host / port / network / volume
- environment / connection
- container / compose
- platform/provider

dev-data-feature / dev-db-migration
- table / column / PK / FK / index
- DBML
- Flyway / Liquibase
- SQL / backfill / vendor migration
```

`VENDOR_CHANGE`이면 Infrastructure 단독으로 완료하지 않고 `dev-data-feature`와 `dev-db-migration`을 요구한다.

## 안전 불변식

- `Desired State 변경 != 기존 리소스 삭제`다.
- Runtime 변경 시 persistent data를 자동 삭제하지 않는다.
- Docker volume은 명시적 cleanup 승인 없이 삭제하지 않는다.
- `docker compose down -v`를 전환 기본 동작으로 사용하지 않는다.
- `Detach != Destroy`를 유지한다.
- `UNKNOWN` Observed State를 임의로 LOCAL_HOST/NETWORK_HOST/CONTAINER/NATIVE로 추측하지 않는다.
- Supabase Auth/API evidence만으로 Database Platform을 SUPABASE로 확정하지 않는다.
- NATIVE ↔ SUPABASE와 DB Vendor 변경을 별도로 판정한다.
- Vendor 변경은 반드시 Data Migration Gate를 연다.
- host/port metadata에 URL, username, password, token을 넣지 않는다.
- 전환 완료 후 실제 connection/health evidence를 남긴다.
- 신규 Secret을 Git tracked config/Dockerfile/Compose에 하드코딩하지 않는다.
- `.env.example`에는 실제 값이 아니라 환경변수 이름/placeholder만 둔다.

## Handoff

```text
Infrastructure Desired State:
- Application Runtime: ...
- Application Host: ... | unknown
- Application Port: ... | unknown
- Database Runtime: ...
- Database Host: ... | unknown
- Database Port: ... | unknown
- Database Platform: ...
- Database Vendor: ...

Infrastructure Observed State:
- Application Runtime: ...
- Application Host: ... | unknown
- Application Port: ... | unknown
- Database Runtime: ...
- Database Host: ... | unknown
- Database Port: ... | unknown
- Database Platform: ...
- Database Vendor: ...

Transition:
- Class: NO_CHANGE | INITIAL_CONFIGURATION | RUNTIME_CHANGE | HOST_CHANGE | PLATFORM_CHANGE | VENDOR_CHANGE | COMBINED_CHANGE
- Changes: ...

Configuration Delivery:
- Contract: .env.example / application config placeholders
- Local source: IntelliJ | OS_ENV | .env.local | COMPOSE_ENV | REMOTE_RUNTIME_ENV

Configuration Security:
- Existing Security Findings: NONE | WARN_EXISTING
- New Security Violations Introduced By Task: NONE

Resources:
- Added:
- Updated:
- Detached:
- Preserved:
- Removed:

Data Migration: NOT_REQUIRED | REQUIRED | COMPLETED | BLOCKED
Destructive Operations: NONE | APPROVAL_REQUIRED
Desired State Persistence: UPDATED | REUSED
Verification:
- ...
Residual Risk:
- ...
```
