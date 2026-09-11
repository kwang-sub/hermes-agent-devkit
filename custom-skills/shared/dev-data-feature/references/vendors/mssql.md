# MSSQL Vendor Reference

Target SQL Server major version/compatibility level을 먼저 확인한다. version/edition에 따라 가능한 기능을 추측하지 않는다.

## Schema
- Unicode text는 프로젝트의 `nvarchar` 사용 convention을 우선한다.
- 시간 타입은 기존 `datetime2`/`datetimeoffset` 등 의미와 precision을 확인한다.
- 자동 번호는 기존 `IDENTITY`/sequence 전략을 따른다.
- `INCLUDE`, filtered index 등 SQL Server 전용 index 기능은 실제 access pattern과 version 근거가 있을 때만 사용한다.

## Query
- ANSI JOIN/window/CTE로 충분하면 우선 사용한다.
- `TOP`, `OFFSET/FETCH`, APPLY 등 T-SQL 기능은 요구사항과 기존 pattern이 필요할 때만 사용한다.
- implicit conversion이 index seek를 방해할 수 있으므로 parameter/column type 일치를 확인한다.

## Performance
```text
Actual Execution Plan
Index Seek / Scan
Key Lookup
estimated vs actual rows
statistics
predicate SARGability
parameter-sensitive behavior
lock/blocking
```

Index 추가 전 기존 clustered/nonclustered key와 write 비용을 확인한다.

## Migration
- 큰 table ALTER/INDEX 작업의 lock과 log 영향, online 지원 여부는 version/edition을 확인한다.
- `IDENTITY_INSERT`, schema transfer, linked-server 같은 운영성 기능을 일반 migration 기본값으로 사용하지 않는다.
- rollback이 데이터 손실을 유발하면 roll-forward 전략을 우선 검토한다.
