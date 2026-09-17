# Supabase Runtime

Supabase는 runtime도 database vendor도 아니다. Infrastructure에서는 `database_platform=SUPABASE`, `database_vendor=postgresql`로 표현한다.

## Cloud / remote

```text
database_runtime=NETWORK_HOST
database_platform=SUPABASE
database_vendor=postgresql
```

Repository의 remote endpoint와 credential contract를 재사용한다. DB container를 추가하지 않는다.

## Local

```text
database_runtime=CONTAINER
database_platform=SUPABASE
database_vendor=postgresql
```

`supabase/config.toml`과 기존 Supabase CLI local stack을 우선한다. Supabase를 단일 PostgreSQL Docker service로 대체하지 않는다.

## Transition

NATIVE PostgreSQL -> Supabase PostgreSQL은 vendor 변경이 아니다. runtime/platform 변경으로 분류한다.

MySQL/MSSQL/Oracle -> Supabase는 PostgreSQL vendor 전환이 포함되므로 Data Migration Gate가 필요하다.
