# Database Vendor Detection

DBMS vendor는 source 전체 검색보다 build/dependency/config evidence를 우선한다.

```text
MSSQL      → mssql-jdbc / com.microsoft.sqlserver / r2dbc-mssql / npm mssql|tedious
MySQL      → mysql-connector-j / com.mysql / npm mysql|mysql2 / Prisma provider=mysql
MariaDB    → mariadb-java-client / org.mariadb.jdbc / r2dbc-mariadb / npm mariadb
PostgreSQL → org.postgresql / PostgreSQL JDBC·R2DBC / npm pg|postgres / Prisma provider=postgresql
Oracle     → ojdbc* / com.oracle.database.jdbc / oracle.jdbc / r2dbc-oracle / npm oracledb
```

## 판정 규칙

- dependency marker가 있으면 project-level vendor candidate로 기록한다.
- connection URL/config가 Task evidence로 주어지면 실제 target vendor 판단에 사용할 수 있다.
- monorepo에서 vendor가 둘 이상 감지되면 Task affected module의 vendor를 다시 특정한다.
- driver dependency만 있고 target version이 없으면 version-specific feature는 추측하지 않는다.
- vendor 근거가 없으면 `generic` 또는 `unknown`을 유지한다.
- proprietary SQL이 이미 존재하면 project pattern evidence로 사용할 수 있지만 repository 전체 SQL scan을 기본 detector가 수행하지 않는다.
