# Oracle Vendor Reference

Target Oracle Database version과 프로젝트의 schema/tablespace/sequence convention을 먼저 확인한다.

## Schema
- 식별자 생성은 기존 identity/sequence 전략을 따른다.
- text는 `VARCHAR2`/`NVARCHAR2`, large text/binary는 기존 LOB convention을 확인한다.
- `DATE`와 `TIMESTAMP` 계열의 시간 의미/precision 차이를 명시한다.
- function-based index, virtual column 등은 실제 query evidence와 target version을 확인한다.

## Query
- 표준 JOIN/window/CTE를 우선한다.
- Oracle-specific analytic/query syntax는 기존 pattern 또는 명확한 필요가 있을 때만 사용한다.

## Performance
```text
DBMS_XPLAN / execution plan
access path
estimated cardinality
index range/full scan
join method
predicate placement
statistics
bind-sensitive behavior
lock/transaction scope
```

Hint는 원인 분석보다 먼저 넣지 않는다.

## Migration
Oracle DDL의 implicit commit 특성을 고려해 application transaction과 동일하게 rollback할 수 있다고 가정하지 않는다.

대형 table/index 변경의 online option과 edition/version 제약을 확인한다.
