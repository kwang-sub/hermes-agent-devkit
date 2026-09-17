---
name: dev-infrastructure
description: 애플리케이션과 DB의 실행 위치, DB 플랫폼/벤더, 기존 환경과 목표 환경의 전환을 안전하게 감지·계획하는 Infrastructure canonical entry.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, infrastructure, runtime, docker, compose, database, supabase, transition, reconciliation]
    related_skills: [dev-tech-dispatch, dev-data-feature, dev-db-migration, dev-spring-feature, dev-frontend-feature]
    requires_tools: [terminal, skill_view]
---

# dev-infrastructure

애플리케이션 코드 밖의 **실행 위치와 연결 토폴로지**를 다루는 canonical Infrastructure entry다.
현재 버전은 Kubernetes/Terraform/배포 자동화를 구현하지 않고 다음 범위만 소유한다.

설정/Secret을 다룰 때는 `/opt/data/shared/references/application-configuration-security.md` 계약을 함께 적용한다.

```text
Application Runtime
- LOCAL_HOST
- NETWORK_HOST
- CONTAINER

Database Runtime
- LOCAL_HOST
- NETWORK_HOST
- CONTAINER

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

## 기본 정책

명시적인 사용자/Task 요구, 기존 Infrastructure metadata, 명확한 Repository evidence가 모두 없을 때만 다음 기본값을 사용한다.

```text
Application Runtime = CONTAINER
Database Runtime = CONTAINER
Database Platform = NATIVE
```

기존 프로젝트의 명확한 runtime evidence를 기본값으로 덮어쓰지 않는다.

## Desired State / Observed State

Infrastructure는 최초 생성기가 아니라 reconciliation capability다.

```text
Observed State  = Repository에서 매 실행 시 재계산
Desired State   = 사용자/Task 또는 .hermes/project.yaml의 infrastructure 설정
Transition Plan = Observed와 Desired의 차이
```

Observed State를 metadata의 현재값으로 신뢰하지 않는다. 사람이 Docker/Compose/env/Supabase 구성을 직접 변경해도 drift를 감지할 수 있어야 한다.

## 실행 순서

1. `scripts/detect_infrastructure.py`로 bounded evidence를 수집한다.
2. 사용자/Task의 명시 Desired State가 있으면 최우선 적용한다.
3. 없으면 프로젝트의 `infrastructure:` desired 값을 사용한다.
4. 그것도 없고 Observed가 명확하면 기존 환경을 보존한다.
5. 모두 없을 때만 CONTAINER 기본값을 사용한다.
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

Runtime 변경과 Vendor 변경은 같은 위험도로 취급하지 않는다.

```text
CONTAINER PostgreSQL -> LOCAL_HOST PostgreSQL
= RUNTIME_CHANGE

PostgreSQL -> MySQL
= VENDOR_CHANGE + Data Migration Gate

NATIVE PostgreSQL container -> Supabase Cloud
= RUNTIME_CHANGE + PLATFORM_CHANGE
  vendor는 postgresql로 유지
```

## Supabase 모델

Supabase를 Runtime enum으로 만들지 않는다.

```text
Supabase Cloud
runtime  = NETWORK_HOST
platform = SUPABASE
vendor   = postgresql

Supabase Local
runtime  = CONTAINER
platform = SUPABASE
vendor   = postgresql
```

`SUPABASE + CONTAINER`를 단일 `postgres` container로 축약하지 않는다. `supabase/config.toml`과 기존 Supabase CLI/local stack을 우선한다.

## Runtime / Configuration 전달 계약

Infrastructure는 runtime topology뿐 아니라 **실제 설정값이 application process까지 전달되는 경로**를 명확히 해야 한다.

```text
Application LOCAL_HOST + Spring
→ Dockerfile/Compose 생성 안 함
→ application.yml에는 ${ENV_VAR} placeholder 유지
→ IntelliJ Run Configuration 또는 OS Environment가 실제 값 제공

Application LOCAL_HOST + Next.js
→ .env.local이 로컬 실제 값 제공
→ .env.example은 변수명 계약만 Git 추적

Application CONTAINER
→ Dockerfile/Compose 대상
→ .env 또는 deployment environment를 Compose/container environment로 주입
→ Secret value는 Compose YAML/Application YAML에 하드코딩하지 않음
```

Spring Boot 자체가 일반적인 `.env`를 자동 로드한다고 가정하지 않는다. `.env`를 사용하는 Container 경로에서는 Compose `env_file`/`environment` 등 **누가 process environment로 주입하는지**를 명시한다.

Supabase의 `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`는 browser-visible 값이므로 Secret은 아니다. 그러나 실제 project별 값은 환경별 runtime configuration으로 취급해 Git에 하드코딩하지 않고 `.env.local`/deployment environment에서 주입한다. `SUPABASE_SECRET_KEY` / service-role 계열은 server-only secret이다.

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

Infrastructure는 DB가 **어디서 실행되는지**를 소유한다. 논리/물리 데이터 모델은 소유하지 않는다.

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
- `UNKNOWN` observed state를 임의로 LOCAL_HOST/NETWORK_HOST/CONTAINER로 추측하지 않는다.
- NATIVE ↔ SUPABASE와 DB Vendor 변경을 별도로 판정한다.
- Vendor 변경은 반드시 Data Migration Gate를 연다.
- 전환 완료 후 실제 connection/health evidence를 남긴다.
- 실제 Secret을 Git tracked config/Dockerfile/Compose에 하드코딩하지 않는다.
- `.env.example`에는 실제 값이 아니라 환경변수 이름/placeholder만 둔다.

## Handoff

```text
Infrastructure Desired State:
- Application Runtime: ...
- Database Runtime: ...
- Database Platform: ...
- Database Vendor: ...

Infrastructure Observed State:
- Application Runtime: ...
- Database Runtime: ...
- Database Platform: ...
- Database Vendor: ...

Transition:
- Class: ...
- Runtime: ...
- Platform: ...
- Vendor: ...

Configuration Delivery:
- Contract: .env.example / application.yml placeholders
- Local source: IntelliJ | OS_ENV | .env.local | COMPOSE_ENV | REMOTE_RUNTIME_ENV
- Secret files tracked: NONE

Resources:
- Added:
- Updated:
- Detached:
- Preserved:
- Removed:

Data Migration: NOT_REQUIRED | REQUIRED | COMPLETED | BLOCKED
Destructive Operations: NONE | APPROVAL_REQUIRED
Verification:
- ...
Residual Risk:
- ...
```
