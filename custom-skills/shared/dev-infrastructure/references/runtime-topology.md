# Runtime Topology / Transition Reference

## Axes

Infrastructure state는 한 enum으로 합치지 않고 독립 축으로 관리한다.

```text
application_runtime = LOCAL_HOST | NETWORK_HOST | CONTAINER | UNKNOWN
database_runtime    = LOCAL_HOST | NETWORK_HOST | CONTAINER | UNKNOWN
database_platform   = NATIVE | SUPABASE | UNKNOWN
database_vendor     = postgresql | mysql | mariadb | mssql | oracle | UNKNOWN
```

신규 desired state의 application/database runtime 기본값은 `CONTAINER`다. Observed State에는 이 기본값을 적용하지 않는다.

## Common transitions

```text
CONTAINER -> LOCAL_HOST
- container dependency detach
- host endpoint로 connection 변경
- persistent data 보존

CONTAINER -> NETWORK_HOST
- container dependency detach
- remote endpoint로 connection 변경
- persistent data 보존

LOCAL_HOST/NETWORK_HOST -> CONTAINER
- Dockerfile/Compose 필요 여부 확인
- service hostname/network/health 구성
```

## Database transition risk

```text
runtime only
postgresql container -> local postgresql
=> Infrastructure transition

platform only/runtime combined
native postgresql -> Supabase PostgreSQL
=> Infrastructure transition + platform-specific connection 검토

vendor
postgresql -> mysql
=> Infrastructure + Data Migration Gate
```

## Supabase

```text
Supabase Cloud
runtime=NETWORK_HOST
platform=SUPABASE
vendor=postgresql

Supabase Local
runtime=CONTAINER
platform=SUPABASE
vendor=postgresql
```

`SUPABASE`를 DB vendor로 추가하지 않는다.

## Destructive boundary

Transition planning은 detach와 destroy를 분리한다.

```text
Detached  = 더 이상 active topology에 연결하지 않음
Preserved = rollback/data safety를 위해 유지
Removed   = 명시적으로 삭제 승인된 resource
```

DB runtime 이동만으로 volume/data를 삭제하지 않는다. `docker compose down -v`와 동등한 동작은 별도 명시적 승인 범위다.
