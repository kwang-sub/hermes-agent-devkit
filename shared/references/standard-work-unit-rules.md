# Standard Flow Work Unit Rules

Standard Flow의 한 Task는 **하나의 주된 작업 단위(Work Unit)** 를 수행한다. 여러 capability를 함께 사용하는 것은 허용하지만, 독립 승인 가능한 산출물을 만든 뒤 그 산출물을 입력으로 다음 mutation phase까지 같은 Task에서 연속 수행하지 않는다.

## Work Unit Class

모든 Standard Flow Plan은 정확히 하나의 주 Work Unit Class를 가진다.

```text
DESIGN          독립 승인 가능한 설계/계약/모델 산출물
IMPLEMENTATION  승인된 요구/설계를 application/runtime behavior로 구현
MIGRATION       승인된 schema/data intent를 migration/physicalization으로 구현
REFACTOR        behavior를 유지한 구조 개선
AUDIT           read-only 조사/차이 분석/검증
```

Capability 수, 파일 수, module 수만으로 Task를 분리하지 않는다.

## Boundary Contract

Plan과 Kanban Task body는 다음 계약을 보존한다.

```text
Work Unit Class: DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT
Work Unit Boundary: SINGLE_UNIT | SPLIT_REQUIRED
Current Deliverable: <이번 Task에서 완료되는 산출물>
Follow-up Required: YES | NO
Follow-up Work Unit: DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT | NONE
Follow-up Input: <다음 Task가 authoritative input으로 사용할 산출물 | NONE>
Excluded Follow-up Scope: <이번 Task에서 하지 않을 후속 mutation | NONE>
```

`SPLIT_REQUIRED`는 원래 사용자 요청이 둘 이상의 독립 Work Unit을 포함하지만 **현재 Plan과 현재 Kanban Task에는 첫 Work Unit만 포함한다**는 뜻이다. 후속 Work Unit을 같은 Plan 승인으로 자동 dispatch하지 않는다.

## Split 기준

다음을 모두 만족하면 기본적으로 Task를 분리한다.

1. 현재 단계가 독립적으로 검토/승인 가능한 artifact 또는 decision을 만든다.
2. 그 산출물이 다음 단계의 authoritative input이 된다.
3. 다음 단계가 application/runtime/schema/data를 실제 mutation한다.

예:

```text
Logical DB Model
→ Physical DB Migration
= SPLIT_REQUIRED

Architecture Decision / ADR
→ broad implementation
= 보통 SPLIT_REQUIRED

Audit Findings
→ source fix
= 보통 SPLIT_REQUIRED
```

다음은 분리 근거가 아니다.

```text
Spring + Infrastructure capability를 함께 사용
Backend + Frontend가 같은 승인 API contract를 한 기능으로 구현
Docker Compose + Spring datasource env 연결
여러 파일/모듈을 수정하지만 하나의 명확한 deliverable을 완성
```

즉 **여러 Skill 사용 != Task 분리**다.

## Data 강제 경계

Data `DESIGN_FIRST` logical model과 physical DB 구현은 항상 별도 Standard Task다.

### Task A — DESIGN

```text
Work Unit Class: DESIGN
Current Deliverable: approved/materialized logical DBML
Allowed:
- Subject Area
- responsibility / ownership / lifecycle
- relationship / cardinality
- logical key/nullability intent
- canonical logical DBML materialization
- dbml_guard / 문서 검증

Forbidden in same Task:
- Flyway/Liquibase migration
- CREATE/ALTER/DROP DDL
- vendor-specific physical schema decision
- physical tbl_* naming 적용
- JPA @Table/@Column physical mapping
- schema mutation
```

`Physicalization Required: YES`이면:

```text
Work Unit Boundary: SPLIT_REQUIRED
Follow-up Required: YES
Follow-up Work Unit: MIGRATION
Follow-up Input: approved/materialized logical DBML
```

Task A가 DONE되어도 MIGRATION Task를 자동 생성/dispatch하지 않는다. 사용자가 별도 Standard Flow로 physicalization을 요청해야 한다.

### Task B — MIGRATION

```text
Work Unit Class: MIGRATION
Input:
- repository의 approved/canonical DBML 또는 이전 승인 artifact snapshot
- Subject Area / logical relationships / business constraints

Allowed:
- physical schema decision
- Flyway/Liquibase
- backfill/compatibility
- 필요한 JPA physical mapping
- migration verification

Forbidden:
- 승인된 logical responsibility/cardinality를 임의 redesign
```

Migration 중 logical redesign이 필요해지면 현재 MIGRATION scope를 확장하지 않고 새 DESIGN Work Unit으로 되돌린다.

## API 경계

기존 API `DESIGN_FIRST` Gate는 무조건 별도 DESIGN Task로 분리하지 않는다.

다음은 같은 `IMPLEMENTATION` Work Unit 안의 bounded contract Gate로 유지할 수 있다.

```text
하나의 구현 Task에 종속된 endpoint/request/response/error contract
→ API Spec 승인
→ 같은 Task에서 구현
```

다음은 분리를 검토한다.

```text
사용자가 API 설계 자체만 요청
여러 후속 구현/consumer가 재사용할 독립 API specification
대규모 계약 설계가 구현 방향을 별도로 승인받아야 함
```

이 경우 현재 Task는 `DESIGN`, 후속 구현은 별도 `IMPLEMENTATION`이다.

## Frontend / Infrastructure

Approved IMAGE/Figma/기존 Architecture가 **이미 입력**인 경우 구현과 같은 Task에서 사용한다. 현재 Task 자체가 새 UI/Architecture 설계를 독립 산출물로 만드는 경우에만 후속 구현과 분리한다.

Infrastructure에서도 단일 목표의 containerization에 Docker/Compose + Spring env delivery가 함께 필요한 것은 하나의 `IMPLEMENTATION` Work Unit으로 허용한다.

## AUDIT

`AUDIT`은 기본적으로 read-only다. Audit 결과에서 수정 필요성이 발견되어도 현재 Task에 자동 source fix를 추가하지 않는다. 사용자가 처음부터 작고 명확한 audit+fix를 하나의 구현 목표로 승인한 경우에는 `IMPLEMENTATION`으로 분류해야 한다.

## Coder 불변식

Coder는 Task의 Work Unit Contract를 구현 범위 상한으로 사용한다.

- `Excluded Follow-up Scope`를 구현하지 않는다.
- DESIGN Task에서 production/schema/runtime mutation을 하지 않는다.
- MIGRATION Task에서 logical model을 재설계하지 않는다.
- AUDIT Task에서 application/test/config를 수정하지 않는다.
- 후속 Work Unit이 필요해져도 임의로 scope를 확장하지 않고 BLOCK/escalate한다.

### Standard Flow scoped summary

최종 변경 범위 검증은 현재 Work Unit의 실제 Changed Files로 제한한다.

```text
change_summary.py --include <changed-path>...
```

- Standard Flow에서 `--include` 없이 repository 전체를 훑지 않는다.
- `--allow-full-scan`은 명시적 진단 전용이다.
- tracked와 untracked 모두 Git pathspec으로 제한한다.
- Follow-up Work Unit의 파일을 현재 Task summary scope에 선행 포함하지 않는다.

## Reviewer 불변식

Reviewer는 diff가 Work Unit Boundary를 넘었는지 확인한다.

- DESIGN Task에 migration/application mutation이 섞이면 blocking finding.
- MIGRATION Task가 승인 logical model을 재설계하면 blocking finding.
- AUDIT Task가 source mutation을 포함하면 blocking finding.
- 단순히 여러 capability를 사용했다는 이유로 split을 요구하지 않는다.

## Orchestrator 불변식

- `dev-breakdown`이 Work Unit을 분류하고 split 여부를 Plan에 명시한다.
- `dev-workflow-orchestrate`는 현재 Work Unit만 승인/dispatch한다.
- 후속 Work Unit은 현재 Plan 승인으로 자동 생성하지 않는다.
- Requirement Delta가 현재 Work Unit 경계를 넘어가면 SAME_TASK_RESUME 대신 FOLLOW_UP_TASK 또는 새 Standard Flow를 사용한다.
