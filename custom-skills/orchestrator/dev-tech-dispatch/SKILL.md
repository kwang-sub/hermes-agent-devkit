---
name: dev-tech-dispatch
description: managed Repository의 bounded build/dependency manifest에서 JVM/Frontend stack과 DBMS vendor candidate를 감지하고 backend/frontend/data capability entry 후보와 fingerprint를 반환하는 orchestrator 전용 resolver.
version: 0.5.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, stack, capability, java, kotlin, spring, typescript, react, nextjs, frontend, data, database, fingerprint, monorepo]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-breakdown, dev-java-guidelines, dev-kotlin-guidelines, dev-spring-guidelines, dev-frontend-feature, dev-data-feature, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-figma-design, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-tech-dispatch

기술 감지와 capability name resolution만 담당한다. Workflow/source/dependency/Kanban을 수정하지 않는다.

일반 Standard Flow에서는 detector를 매번 직접 실행하지 않고 `dev-project-bootstrap/scripts/stack_cache.py`가 관리하는 `.hermes/project.yaml technology:` cache를 우선 사용한다.

## Canonical detector

```bash
python3 /opt/custom-skills/orchestrator/dev-tech-dispatch/scripts/detect_capabilities.py \
  --repo "<managed repository>"
```

예:

```text
DETECTOR_VERSION=4
STACK_FINGERPRINT=sha256:...
STACK_INPUTS=backend/build.gradle.kts,backend/schema.prisma,frontend/package.json
STACKS=kotlin,spring,typescript,react,nextjs
BACKEND_SKILLS=dev-kotlin-guidelines,dev-spring-guidelines
FRONTEND_ENTRY=dev-frontend-feature
DATABASE_VENDORS=postgresql
DATA_ENTRY_CANDIDATE=dev-data-feature
STATUS=pass
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

## JVM / Frontend capability

```text
Java   → dev-java-guidelines
Kotlin → dev-kotlin-guidelines
Spring → dev-spring-guidelines
Frontend affected area → dev-frontend-feature
```

Frontend 하위 skill은 `FRONTEND_HINTS`로만 제공하고 시작부터 전부 runtime pin하지 않는다.

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
```

## 불변식

- project source/SQL 전체 scan 금지.
- dependency 설치/architecture 선택/DB version 추측 금지.
- database vendor를 language/framework stack과 동일시하지 않는다.
- `dev-tech-dispatch` 자체는 Coder/Reviewer runtime pinned skill이 아니다.
- cache 정책은 `dev-project-bootstrap/scripts/stack_cache.py`가 소유한다.

## 회귀 검증

```bash
python3 custom-skills/orchestrator/dev-tech-dispatch/tests/test_detect_capabilities.py
```
