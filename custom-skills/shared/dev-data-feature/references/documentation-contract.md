# Data Documentation Contract

기존 프로젝트에 데이터 문서 표준이 없으면 다음을 권장한다.

```text
docs/data/
├─ README.md              # 필요할 때만: 문서 역할/Source of Truth 설명
├─ domain-model.md        # 도메인 책임/lifecycle/ownership
├─ schema.dbml            # canonical relational model
├─ data-dictionary.md     # DBML만으로 부족한 업무 의미/불변식
├─ decisions/             # 중요한 설계 ADR
└─ migrations/            # 복잡하거나 위험한 migration 계획
```

모든 파일을 기계적으로 생성하지 않는다. 현재 변경에 필요한 artifact만 만든다.

## schema.dbml

- 관계, table, column, PK/FK, nullable, index 의도를 표현한다.
- 기본 `LOGICAL_RELATIONAL` mode에서는 DBMS 고유 문법/옵션을 최소화한다.
- 프로젝트가 physical DBML을 기존 규칙으로 사용하면 실제 vendor type을 유지한다.
- DBML Canvas/dbdiagram.io에서 해석 가능한 표준 DBML core syntax를 우선한다.
- 특정 renderer만 이해하는 extension은 프로젝트가 이미 사용하고 실제 호환성을 확인한 경우에만 쓴다.

## DBML Canvas

IntelliJ/JetBrains에서 `schema.dbml`을 ERD로 보는 Human Review 도구로 사용할 수 있다.

```text
Agent/Hermes → schema.dbml 수정
→ Git diff
→ IntelliJ DBML Canvas ERD 확인
→ 사용자/Reviewer 검토
```

DevKit은 Plugin 설치를 강제하거나 Plugin API에 의존하지 않는다. Plugin이 없어도 DBML 파일과 Git review는 정상 동작해야 한다.

## domain-model.md / data-dictionary.md

`domain-model.md`는 책임, ownership, lifecycle, 주요 불변식, Current/History/Snapshot 구분처럼 ERD만으로 알기 어려운 의미를 설명할 때만 유지한다.

`data-dictionary.md`는 column 이름만 보고 알 수 없는 업무 의미·단위·nullable 의미·invariant를 기록하며 DBML과 동일한 타입/PK/FK 표를 복제하지 않는다.

## decisions/ / migrations/

Current State 저장 여부, append-only history, snapshot 주기, soft delete, key 전략처럼 나중에 이유를 잃기 쉬운 결정만 ADR로 남긴다.

단순 DDL 한 줄마다 migration Markdown을 만들지 않는다. large backfill, NOT NULL 단계 적용, rename/drop, rolling deployment, dual-write, 데이터 재계산처럼 운영/호환성 판단이 필요한 변경만 별도 migration note를 검토한다.

## 변경 분류별 문서 영향

```text
QUERY_ONLY    → 기본 문서 변경 없음
MODEL_CHANGE  → schema.dbml, 필요 시 domain-model/decision
SCHEMA_CHANGE → schema.dbml + executable migration
MIGRATION     → migration file + 위험할 때 migration note
PERFORMANCE   → index/schema 변경이 있을 때 schema.dbml 반영
```

Mermaid ERD를 추가하더라도 설명용 파생 View로 취급하며 DBML과 독립적인 canonical model을 만들지 않는다.
