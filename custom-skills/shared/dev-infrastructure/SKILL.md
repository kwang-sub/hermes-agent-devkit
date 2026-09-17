---
name: dev-infrastructure
description: 애플리케이션과 데이터베이스의 실행 위치·플랫폼을 desired/observed state로 관리하고 Docker 중심 기본 구성을 안전하게 전환하는 Infrastructure canonical entry.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, infrastructure, runtime, docker, compose, database, supabase, reconciliation, worktree]
    related_skills: [dev-tech-dispatch, dev-project-bootstrap, dev-workspace-dispatch, dev-data-feature, dev-db-migration, dev-official-docs-context]
    requires_tools: [terminal, skill_view]
---

# dev-infrastructure

애플리케이션 코드 바깥의 **실행 위치와 연결 토폴로지**를 관리하는 Infrastructure canonical entry다.

현재 구현 범위는 의도적으로 좁다.

```text
Application Runtime
- LOCAL_HOST
- NETWORK_HOST
- CONTAINER        # 신규/미설정 프로젝트 기본값

Database Runtime
- LOCAL_HOST
- NETWORK_HOST
- CONTAINER        # 신규/미설정 프로젝트 기본값

Database Platform
- NATIVE
- SUPABASE

Database Vendor
- postgresql
- mysql
- mariadb
- mssql
- oracle
- UNKNOWN
```

Kubernetes, Terraform, Ansible, cloud provisioning, reverse proxy, CI/CD deployment, observability, backup automation은 이번 capability의 자동 구현 범위가 아니다. 다만 이후 하위 capability로 확장할 수 있도록 runtime/platform/vendor를 분리한다.

## 핵심 원칙

Infrastructure는 최초 파일 생성기가 아니라 **Desired State reconciliation**을 수행한다.

```text
Approved implementation Workspace evidence
→ Observed State

Primary Repository .hermes/project.yaml infrastructure
+ approved Task snapshot
→ Desired State

Observed + Desired
→ Transition Plan
→ 최소 변경 적용
→ Verification
```

`CONTAINER`는 **default desired policy**일 뿐 현재 상태를 추측하는 fallback이 아니다. 기존 repository에 명확한 runtime evidence가 있으면 이를 Observed State로 보존한다. evidence가 충분하지 않으면 `UNKNOWN`으로 남긴다.

## Project / Workspace ownership

Infrastructure Desired State와 구현 source의 소유 위치를 분리한다.

```text
Primary Repository
/workspace/chagok
└─ .hermes/project.yaml
   └─ infrastructure:     # canonical Desired State

Implementation Workspace
/workspace/chagok
또는
/workspace/.worktrees/chagok/<task>
└─ Dockerfile / compose / application config ...  # Observed State + implementation
```

linked worktree에 `.hermes/project.yaml`이 없더라도 정상이다. `plan_transition.py`는 Workspace의 `.git` worktree metadata로 Primary Repository를 자동 해석하고 그곳의 Desired State를 읽는다. 필요하면 `--project-repo`로 Primary Repository를 명시할 수 있다.

Coder는 linked worktree 밖의 Primary metadata를 임의 수정하지 않는다. Infrastructure Task에서 Desired State가 바뀌면 **Plan Approval 이후 Orchestrator의 `dev-workspace-dispatch/prepare_dispatch.py`가 worker dispatch 전에 승인된 4축을 Primary metadata에 atomic하게 기록**한다. Coder는 Task snapshot과 persisted metadata가 일치하는지 확인한 뒤 이를 read-only desired contract로 사용한다.

## Desired State metadata

프로젝트 기본값은 `.hermes/project.yaml`의 독립 `infrastructure:` section으로 관리한다. `technology:` cache와 섞지 않는다.

```yaml
infrastructure:
  version: "1"
  application_runtime: "CONTAINER"
  database_runtime: "CONTAINER"
  database_platform: "NATIVE"
  database_vendor: "UNKNOWN"
```

- 신규 bootstrap에서 application/database runtime 기본값은 `CONTAINER`다.
- `database_vendor`는 기존 technology detector의 명확한 단일 vendor evidence가 있으면 재사용할 수 있다.
- 기존 프로젝트의 명시적 runtime evidence를 기본값으로 덮어쓰지 않는다.
- Infrastructure Gate가 REQUIRED인 Task에서 desired state를 바꾸면 Plan 승인 후 dispatch 단계에서 4축을 함께 갱신한다.
- 일부 축만 암묵적으로 merge하지 않는다.

## Runtime과 Platform은 독립 축

Supabase를 runtime으로 취급하지 않는다.

```text
Supabase Cloud
Database Runtime  = NETWORK_HOST
Database Platform = SUPABASE
Database Vendor   = postgresql

Supabase Local
Database Runtime  = CONTAINER
Database Platform = SUPABASE
Database Vendor   = postgresql

일반 PostgreSQL Docker
Database Runtime  = CONTAINER
Database Platform = NATIVE
Database Vendor   = postgresql
```

이 구분은 NATIVE PostgreSQL → Supabase Cloud 전환을 `RUNTIME_CHANGE + PLATFORM_CHANGE`로 판정하고 잘못된 `VENDOR_CHANGE`를 만들지 않게 한다.

## Observed State detection

다음 bounded evidence만 확인한다.

```text
Dockerfile / *.Dockerfile
compose.yml / compose.yaml / docker-compose.yml / docker-compose.yaml
.env.example / application*.yml / application*.yaml / application*.properties
supabase/config.toml
package/build manifest의 DB vendor evidence
```

일반 source 전체를 scan하지 않는다. placeholder host나 서로 충돌하는 runtime evidence를 억지로 하나의 runtime으로 확정하지 않고 `UNKNOWN`으로 남긴다.

정규 detector:

```bash
python3 /opt/custom-skills/shared/dev-infrastructure/scripts/detect_infrastructure.py \
  --repo "<approved Workspace>"
```

Desired/Observed transition 계획:

```bash
python3 /opt/custom-skills/shared/dev-infrastructure/scripts/plan_transition.py \
  --repo "<approved Workspace>" \
  [--project-repo "<Primary Repository>"]
```

`--repo`는 Observed State source인 구현 Workspace다. `--project-repo`를 생략하면 linked worktree의 Git metadata로 Primary Repository를 자동 해석한다.

## Transition classification

```text
NO_CHANGE
RUNTIME_CHANGE
HOST_CHANGE
PLATFORM_CHANGE
VENDOR_CHANGE
COMBINED_CHANGE
UNKNOWN
```

두 축 이상 변경되면 `COMBINED_CHANGE`이며 세부 `changes`를 함께 기록한다. Observed evidence 부족만으로 명확한 change라고 주장하지 않고 `UNKNOWN`과 `requires_observed_verification`으로 남긴다.

예:

```text
CONTAINER / NATIVE / postgresql
→ NETWORK_HOST / SUPABASE / postgresql

changes:
- DATABASE_RUNTIME: CONTAINER -> NETWORK_HOST
- DATABASE_PLATFORM: NATIVE -> SUPABASE

VENDOR_CHANGE 없음
```

## Runtime transition

동일 vendor runtime 이동은 Infrastructure 중심 변경이다.

```text
CONTAINER → LOCAL_HOST
- container DB service detach
- datasource endpoint를 host runtime에 맞게 변경
- depends_on/network/healthcheck 정리
- persistent volume 자동 삭제 금지

CONTAINER → NETWORK_HOST
- DB container service detach
- remote endpoint/env 연결
- persistent volume 보존

LOCAL_HOST/NETWORK_HOST → CONTAINER
- 기존 endpoint를 증거로 보존
- Docker/Compose service 구성
- application connection을 service hostname으로 변경
```

Docker endpoint의 OS별 세부 구현(`host.docker.internal`, host-gateway 등)은 실제 runtime 조합과 프로젝트 실행 환경이 확인된 경우에만 적용한다.

## Database vendor transition gate

`VENDOR_CHANGE`는 Infrastructure만으로 완료하지 않는다.

```text
postgresql → mysql
mysql → postgresql
mssql → postgresql
...
```

이면 최소 다음 capability를 연다.

```text
dev-data-feature
dev-db-migration
필요 시 dev-db-schema / dev-db-query
```

먼저 schema/type/constraint/query/migration compatibility를 검토하고 target DB 준비와 application connection 변경을 뒤에 수행한다.

`Database Runtime`만 변경되고 vendor가 같다면 vendor migration을 만들지 않는다.

## Supabase

### SUPABASE + NETWORK_HOST

Supabase Cloud 또는 외부 Supabase를 의미한다.

- PostgreSQL vendor로 해석한다.
- 임의 PostgreSQL container를 생성하지 않는다.
- endpoint/credential/SSL/auth 방식은 실제 project contract를 따른다.
- 외부 SDK/API 또는 version-sensitive config를 변경하면 `dev-official-docs-context`를 적용한다.

### SUPABASE + CONTAINER

Supabase Local을 의미한다.

- `supabase/config.toml`과 기존 Supabase CLI/local stack을 authoritative evidence로 우선한다.
- Supabase 전체를 단일 `postgres` service로 축약하지 않는다.
- 기존 local stack을 임의 custom Compose로 재구현하지 않는다.

## Data responsibility boundary

```text
dev-infrastructure
- DB가 어디서 실행되는가
- runtime/platform/vendor
- endpoint/env/network/volume/container/health

dev-data-feature / dev-db-*
- table/column/key/index
- DBML/schema
- SQL
- Flyway/Liquibase
- data/schema migration
```

DB container가 존재한다는 이유로 Infrastructure가 physical schema를 소유하지 않는다.

## Safe reconciliation invariants

- `Desired State 변경 != 기존 리소스 삭제`다.
- `Detach != Destroy`다.
- runtime 전환에서 Docker volume/persistent data를 자동 삭제하지 않는다.
- `docker compose down -v`와 동등한 destructive cleanup을 자동 기본값으로 실행하지 않는다.
- cleanup/removal은 명시적 Task 범위 또는 별도 승인 없이는 수행하지 않는다.
- vendor 변경은 Data Migration Gate 없이 완료 처리하지 않는다.
- repository evidence와 metadata가 충돌하면 `DRIFT`를 보고하고 observed state를 metadata로 덮어쓰지 않는다.
- `UNKNOWN`을 편의상 `CONTAINER`/`LOCAL_HOST`로 추측하지 않는다.
- 신규/미설정 desired state에만 `CONTAINER` default를 사용한다.
- 전환 후 실제 connection/health/build/test 등 affected verification을 수행한다.
- Coder가 Workspace 경계를 넘어 Primary metadata를 수정하지 않는다.

## Coder 실행 순서

```text
1. approved Workspace에서 detector로 Observed State 확보
2. Primary infrastructure metadata + Task snapshot으로 Desired State 확보
3. 두 Desired State가 불일치하면 구현 전에 BLOCK
4. plan_transition.py로 Transition Plan 생성
5. VENDOR_CHANGE 여부 확인
6. vendor 변경이면 Data capability Gate
7. destructive operation 후보를 제거하거나 별도 승인 대상으로 분리
8. 최소 변경 적용
9. Desired/Observed drift 재검사
10. affected runtime/connection/test/build 검증
11. handoff evidence 기록
```

## Reviewer hot spots

- CONTAINER default를 기존 observed state로 오인했는가
- runtime/platform/vendor 축을 섞었는가
- Supabase를 별도 vendor 또는 단일 postgres container로 축약했는가
- 동일 vendor runtime 전환인데 불필요한 DB migration을 만들었는가
- vendor 변경인데 Data Migration Gate를 생략했는가
- volume/data를 명시적 승인 없이 제거했는가
- metadata만 바꾸고 actual connection/config를 검증하지 않았는가
- 기존 외부 DB evidence를 Docker 기본값으로 덮었는가
- linked worktree의 stale/missing metadata를 Primary Desired State 대신 사용했는가

## Handoff

```text
Skill: dev-infrastructure
Project Repository: <Primary Repository>
Workspace: <approved implementation Workspace>
Desired State:
- Application Runtime: LOCAL_HOST | NETWORK_HOST | CONTAINER
- Database Runtime: LOCAL_HOST | NETWORK_HOST | CONTAINER
- Database Platform: NATIVE | SUPABASE
- Database Vendor: ... | UNKNOWN
Observed State:
- Application Runtime: ... | UNKNOWN
- Database Runtime: ... | UNKNOWN
- Database Platform: ... | UNKNOWN
- Database Vendor: ... | UNKNOWN
Drift: NONE | DETECTED | UNKNOWN
Transition: NO_CHANGE | RUNTIME_CHANGE | HOST_CHANGE | PLATFORM_CHANGE | VENDOR_CHANGE | COMBINED_CHANGE | UNKNOWN
Changes:
- ...
Required Capability Skills:
- ...
Resources Added:
- ...
Resources Updated:
- ...
Resources Detached:
- ...
Resources Preserved:
- ...
Resources Removed:
- ...
Data Migration: NOT_REQUIRED | REQUIRED | COMPLETED | BLOCKED
Destructive Operations: NONE | APPROVED:<evidence>
Verification:
- ...
Residual Risk:
- ...
```