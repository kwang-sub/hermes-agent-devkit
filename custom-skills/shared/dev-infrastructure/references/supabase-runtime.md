# Supabase Runtime

Supabase는 DB Runtime이 아니라 Database Platform이다.

## Cloud

```text
Database Runtime  = NETWORK_HOST
Database Platform = SUPABASE
Database Vendor   = postgresql
```

Remote Supabase endpoint를 사용한다. DB container를 새로 생성하지 않는다.

## Local

```text
Database Runtime  = CONTAINER
Database Platform = SUPABASE
Database Vendor   = postgresql
```

`supabase/config.toml`과 기존 Supabase CLI/local stack을 authoritative configuration으로 본다.
단순 `postgres` 이미지 하나로 Supabase local stack을 대체하지 않는다.

## Transition examples

```text
NATIVE PostgreSQL container -> Supabase Cloud
RUNTIME_CHANGE + PLATFORM_CHANGE
Vendor unchanged(postgresql)

MySQL network host -> Supabase Cloud
RUNTIME_CHANGE(if changed) + PLATFORM_CHANGE + VENDOR_CHANGE
Data Migration Gate required
```

Supabase auth/storage/realtime 등 부가 서비스 구성은 현재 Infrastructure v0.1의 자동 구성 범위가 아니다. 기존 구성이 있으면 보존한다.
