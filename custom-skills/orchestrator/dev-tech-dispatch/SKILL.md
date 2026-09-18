---
name: dev-tech-dispatch
description: managed Repository의 bounded build/dependency manifest에서 기술 stack과 DBMS vendor candidate를 감지하고 확장 가능한 backend entry/hint, frontend entry/hint, data capability 후보와 fingerprint를 반환하는 orchestrator 전용 resolver.
version: 0.6.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, stack, capability, java, kotlin, spring, typescript, react, nextjs, frontend, data, database, fingerprint, monorepo, infrastructure]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-breakdown, dev-java-guidelines, dev-kotlin-guidelines, dev-spring-guidelines, dev-spring-feature, dev-frontend-feature, dev-data-feature, dev-infrastructure, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-figma-design, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-tech-dispatch

기술 감지와 capability name resolution만 담당한다. Workflow/source/dependency/Kanban을 수정하지 않는다.

일반 Standard Flow에서는 detector를 매번 직접 실행하지 않고 `dev-project-bootstrap/scripts/stack_cache.py`가 관리하는 `.hermes/project.yaml technology:` cache를 우선 사용한다.

Infrastructure는 build/dependency stack과 lifecycle이 다르므로 technology fingerprint에 합치지 않는다. Docker/Compose/Supabase/runtime topology는 `dev-infrastructure`의 bounded detector와 별도 `infrastructure:` metadata가 담당한다.

## Canonical detector

```bash
python3 /opt/custom-skills/orchestrator/dev-tech-dispatch/scripts/detect_capabilities.py \
  --repo "<managed repository>"
```

예:

```text
DETECTOR_VERSION=5
STACK_FINGERPRINT=sha256:...
STACK_INPUTS=backend/build.gradle.kts,backend/schema.prisma,frontend/package.json
STACKS=kotlin,spring,typescript,react,nextjs
BACKEND_ENTRIES=dev-spring-feature
BACKEND_HINTS=dev-kotlin-guidelines,dev-spring-guidelines
BACKEND_SKILLS=dev-kotlin-guidelines,dev-spring-guidelines
FRONTEND_ENTRY=dev-frontend-feature
DATABASE_VENDORS=postgresql
DATA_ENTRY_CANDIDATE=dev-data-feature
STATUS=pass
```

Infrastructure가 Task affected area이면 stack 결과와 별도로 다음 entry를 결합한다.

```text
INFRA_ENTRY_CANDIDATE=dev-infrastructure
```

JVM mixed project도 그대로 보존한다.

```text
Kotlin + Spring
→ STACKS=kotlin,spring

Java + Kotlin + Spring
→ STACKS=java,kotlin,spring
```

Fingerprint만 필요하면 `--fingerprint-only`를 사용한다.

## 탐지 범위

Repository 전체 source를 읽지 않는다. root 및 최대 3단계 하위에서 build/dependency manifest만 확인하고 generated/vendor 디렉터리는 제외한다.

대표 input:

```text
build.gradle / build.gradle.kts / settings.gradle*
pom.xml / gradle.properties / libs.versions.toml
package.json / package lock/workspace files
tsconfig*.json
schema.prisma
```

일반 `.java`, `.kt`, `.ts`, `.tsx`, `.sql` source 변경은 stack fingerprint를 바꾸지 않는다.

`Dockerfile`, `compose.yml`, `compose.yaml`, `supabase/config.toml`도 이 technology fingerprint에는 넣지 않는다. 해당 파일은 Infrastructure observed state evidence다.

## Backend / Frontend capability

Backend 감지 결과는 **실행 진입 capability**와 **보조 guideline/hint**를 분리한다.

```text
BACKEND_ENTRIES
→ 실제 Backend Work Unit의 domain/framework entry 후보
→ 현재 Spring: dev-spring-feature

BACKEND_HINTS
→ language/framework guideline 후보
→ Java: dev-java-guidelines
→ Kotlin: dev-kotlin-guidelines
→ Spring: dev-spring-guidelines
```

현재 지원 stack은 JVM/Spring이지만 metadata schema는 특정 Backend 생태계에 고정하지 않는다. 향후 Python/FastAPI 같은 실제 capability를 추가할 때 detector에 manifest evidence와 mapping만 추가한다.

```text
예: 향후 실제 FastAPI capability가 추가되는 경우

stacks:
- python
- fastapi

backend_entries:
- dev-fastapi-feature

backend_hints:
- dev-python-guidelines
```

지원하지 않는 stack 이름이나 존재하지 않는 Skill을 placeholder로 미리 등록하지 않는다.

복수 Backend를 가진 monorepo를 표현할 수 있도록 `BACKEND_ENTRIES`는 list 계약이다. 실제 Task에서는 repository 전체 후보를 모두 적용하지 않고 affected area와 사용자 요구를 함께 보고 Applicable Skill을 선택한다.

`BACKEND_SKILLS`는 기존 managed project/reader 호환을 위한 legacy alias이며 현재 `BACKEND_HINTS`와 같은 값을 반환한다. 신규 consumer는 `BACKEND_ENTRIES + BACKEND_HINTS`를 사용한다.

Frontend affected area의 canonical entry는 계속 `dev-frontend-feature`다. Frontend 하위 skill은 `FRONTEND_HINTS`로만 제공하고 시작부터 전부 runtime pin하지 않는다.

## Database vendor candidate

Detector는 build/dependency manifest에서 다음 vendor candidate를 bounded하게 감지한다.

```text
mssql
mysql
mariadb
postgresql
oracle
```

근거 예:

```text
JDBC/R2DBC driver dependency
npm database driver
schema.prisma provider
```

DB vendor는 `STACKS`에 섞지 않고 `DATABASE_VENDORS`로 분리한다. Repository에 DB driver가 있다는 이유만으로 Data Skill을 자동 실행하지 않는다.

Persistence evidence가 있으면:

```text
DATA_ENTRY_CANDIDATE=dev-data-feature
```

를 반환한다. 실제 Task가 schema/model/SQL/migration/performance를 건드릴 때만 Orchestrator가 canonical Data entry로 선택한다.

Vendor가 둘 이상이면 monorepo/module affected area를 확인해 Task target vendor를 다시 특정한다. Driver만으로 target DB version을 추측하지 않는다.

## Infrastructure candidate

다음과 같은 Task는 `dev-infrastructure`를 별도 capability entry로 선택한다.

```text
Dockerfile / Compose 생성·변경
Application Runtime 변경
Database Runtime 변경
LOCAL_HOST / NETWORK_HOST / CONTAINER 전환
NATIVE / SUPABASE 전환
DB connection endpoint / runtime env 변경
기존 runtime topology drift 조정
```

`dev-infrastructure`는 현재 Repository evidence에서 Observed State를 계산하고, 사용자/Task 또는 `.hermes/project.yaml infrastructure:`의 Desired State와 비교한다.

DB Vendor 변경이 포함되면 Infrastructure만으로 완료하지 않는다.

```text
VENDOR_CHANGE
→ dev-infrastructure
+ dev-data-feature
+ dev-db-migration
```

## Stack Detection != Skill Loading

```text
Repository capability candidate
+ 사용자 요구사항
+ Task affected area
= Applicable Skill
```

예:

```text
Spring + MSSQL project / Service logic only
→ backend skill만 적용

Spring + MSSQL / Repository method only, 기존 schema 유지
→ dev-spring-data

Schema/ERD/migration/SQL tuning
→ dev-data-feature

Compose PostgreSQL -> local PostgreSQL
→ dev-infrastructure

PostgreSQL -> MySQL
→ dev-infrastructure + dev-data-feature + dev-db-migration
```

## 불변식

- project source/SQL 전체 scan 금지.
- dependency 설치/architecture 선택/DB version 추측 금지.
- database vendor를 language/framework stack과 동일시하지 않는다.
- technology fingerprint와 infrastructure topology fingerprint/lifecycle을 섞지 않는다.
- Backend 생태계 확장을 위해 unsupported stack/Skill placeholder를 미리 등록하지 않는다.
- 신규 Backend detector consumer는 legacy `BACKEND_SKILLS` 대신 `BACKEND_ENTRIES + BACKEND_HINTS`를 사용한다.
- `dev-tech-dispatch` 자체는 Coder/Reviewer runtime pinned skill이 아니다.
- cache 정책은 `dev-project-bootstrap/scripts/stack_cache.py`가 소유한다.
- Infrastructure desired-state 초기화는 `dev-project-bootstrap/scripts/infrastructure_cache.py`가 소유하며 기존 `infrastructure:` section을 자동 덮어쓰지 않는다.

## 회귀 검증

```bash
python3 custom-skills/orchestrator/dev-tech-dispatch/tests/test_detect_capabilities.py
python3 custom-skills/shared/dev-infrastructure/tests/test_detect_infrastructure.py
python3 custom-skills/shared/dev-infrastructure/tests/test_plan_transition.py
```
