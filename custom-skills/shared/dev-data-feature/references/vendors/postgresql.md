# PostgreSQL Vendor Reference

Target PostgreSQL major version과 extension 사용 여부를 먼저 확인한다.

## Schema
- 신규 surrogate key는 기존 identity/sequence convention을 따른다. legacy `serial`을 새 코드의 유일한 기본값으로 가정하지 않는다.
- timezone 의미가 필요한 시간은 기존 `timestamp`/`timestamptz` 정책을 확인한다.
- `jsonb`, array, enum, generated column은 관계형 모델보다 실제 요구에 적합한지 먼저 판단한다.
- partial/expression index는 predicate/query evidence가 있을 때 사용한다.

## Query
- 표준 JOIN/window/CTE를 우선한다.
- `DISTINCT ON`, `LATERAL`, PostgreSQL-specific operator는 기존 pattern 또는 명확한 이점이 있을 때만 사용한다.

## Performance
```text
EXPLAIN (ANALYZE, BUFFERS)
Seq Scan / Index Scan / Bitmap Scan
estimated vs actual rows
filter rows
sort/hash memory
index selectivity
MVCC / lock behavior
statistics
```

실제 운영 데이터에서 `ANALYZE`를 무조건 실행하지 않고 안전한 환경/승인을 확인한다.

## Migration
- table rewrite/lock 가능성을 변경 종류와 version별로 확인한다.
- `CREATE INDEX CONCURRENTLY` 같은 기능은 transaction 제약과 실패 복구 방식을 함께 검토한다.
