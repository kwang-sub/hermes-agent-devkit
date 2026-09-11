# MariaDB Vendor Reference

MariaDB를 MySQL과 동일 제품으로 취급하지 않는다. target MariaDB major version의 문법/optimizer/JSON/index 차이를 확인한다.

## Schema
- charset/collation, `AUTO_INCREMENT`, temporal type은 기존 프로젝트 convention을 우선한다.
- JSON 표현과 generated/virtual column 기능은 MySQL 문서를 그대로 적용하지 않고 MariaDB version을 확인한다.

## Query / Performance
```text
EXPLAIN / ANALYZE 지원 형태 확인
chosen index
rows/filter 추정
filesort/temporary
join order
composite index selectivity
transaction/lock scope
```

MySQL optimizer hint나 feature를 MariaDB에 자동 이식하지 않는다.

## Migration
ALTER/online DDL behavior는 MariaDB target version에 맞춰 확인한다. MySQL migration 가정을 그대로 복제하지 않는다.
