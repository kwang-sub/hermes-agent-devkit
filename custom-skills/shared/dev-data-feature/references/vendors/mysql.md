# MySQL Vendor Reference

Target MySQL major version과 storage engine을 먼저 확인한다.

## Schema
- text charset/collation은 프로젝트의 `utf8mb4` 등 기존 정책을 따른다.
- 자동 번호는 기존 `AUTO_INCREMENT` 전략을 확인한다.
- `DATETIME`/`TIMESTAMP` 선택은 timezone/range/default 의미와 기존 convention을 확인한다.
- JSON, generated column, functional/index 기능은 target version 근거 없이 가정하지 않는다.

## Query
- 표준 JOIN/CTE/window 기능을 우선하되 target major version이 지원하는지 확인한다.
- pagination에서 큰 OFFSET이 문제면 keyset pagination을 access pattern과 함께 검토한다.

## Performance
```text
EXPLAIN / EXPLAIN ANALYZE (version 확인)
access type
estimated rows
possible/used key
covering index
filesort / temporary
selectivity
lock/transaction scope
```

Composite index는 leftmost prefix와 실제 predicate/order를 함께 검토한다.

## Migration
- ALTER TABLE algorithm/lock 특성은 version과 변경 종류별로 확인한다.
- charset/collation 변경은 데이터 크기와 index length/호환성 영향을 함께 검토한다.
- online DDL 가능 여부를 일반화하지 않는다.
