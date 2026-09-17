# Infrastructure / Data Boundary

```text
dev-infrastructure
- runtime/platform/vendor topology
- endpoint/env/network/container/volume/health

dev-data-feature / dev-db-*
- logical/physical schema
- table/column/key/index
- SQL
- Flyway/Liquibase
- vendor migration/backfill
```

DB vendor 변경은 Infrastructure와 Data를 함께 적용한다. Runtime만 변경되고 vendor가 유지되면 schema migration을 자동 요구하지 않는다.
