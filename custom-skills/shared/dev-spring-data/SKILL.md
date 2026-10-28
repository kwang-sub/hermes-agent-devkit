---
name: dev-spring-data
description: Spring Data JPA/JPA 구현에서 단순 조회는 Data JPA 메서드 쿼리를 우선하고 복잡·동적 조회는 QueryDSL로 해결하며 Native Query는 최후 수단으로 제한한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, spring, jpa, data-jpa, querydsl, repository, entity, converter]
    related_skills: [dev-spring-guidelines, dev-spring-feature, dev-spring-test]
    requires_tools: [terminal]
---

# dev-spring-data

JPA/Spring Data JPA/QueryDSL 관련 persistence 작업에 적용하는 capability Skill이다.

먼저 `dev-spring-guidelines`와 `/opt/data/shared/references/project-pattern-rules.md`를 적용한다.

## 적용 대상

```text
Entity / Embeddable / Value Object mapping
Spring Data Repository
Derived Method Query
JPQL/QueryDSL
Projection / Paging / Fetch Join
AttributeConverter
N+1 / persistence performance
```

## Query 선택 정책

기본 우선순위는 다음과 같다.

```text
1. Spring Data JPA Method Query
2. QueryDSL
3. Native Query
```

### 1) Method Query 우선

단순 조건 조회는 Spring Data JPA derived query를 우선한다.

예:

```text
findById
findByUserId
findByStatusAndUseYn
existsByEmail
countByStatus
```

메서드명이 지나치게 길어져 의미가 떨어지거나 동적 조건/복잡 join이 필요하면 QueryDSL로 전환한다.

### 2) QueryDSL 사용

다음은 QueryDSL을 우선 검토한다.

```text
동적 검색 조건
다수 조건의 선택적 조합
복수 JOIN
Projection
복잡한 Paging/Sorting
Fetch Join
하나의 derived method로 읽기 어려운 조회
```

프로젝트에 기존 QueryDSL support/custom repository 패턴이 있으면 그 구조를 그대로 재사용한다.

### 3) Native Query 제한

편의성 때문에 `nativeQuery = true`를 사용하지 않는다.

Native Query는 다음과 같이 Data JPA/QueryDSL로 현실적으로 해결하기 어려운 근거가 있을 때만 사용한다.

```text
DB vendor 전용 기능
QueryDSL/JPQL 표현 불가 또는 비현실적 구현
명확한 성능 근거가 있는 DB-specific query
반드시 보존해야 하는 legacy query contract
```

사용 전 handoff/plan에 다음을 기록한다.

```text
Why Method Query is insufficient
Why QueryDSL is insufficient
Why Native Query is required
DB compatibility / migration impact
Verification
```

## Entity / Mapping

- Entity naming, constructor/setter policy, association ownership, fetch/cascade, enum/value persistence는 기존 프로젝트를 따른다.
- 새 association은 N+1, cascade/orphanRemoval, lifecycle 영향을 확인한다.
- `EAGER` 또는 광범위한 cascade를 편의상 추가하지 않는다.
- Converter가 이미 있으면 재사용하고 null/legacy persisted value를 확인한다.

## Converter / 암호화 샘플의 선택적 적용

Converter 신규 작성·변경 또는 저장값 암복호화/해싱이 실제 범위일 때만 `references/jpa-converter-reference.md`를 읽는다. 먼저 기존 Converter/암호 서비스·DB 저장 포맷·키 주입·provider/언어 버전을 확인한다. 기존 프로젝트 구성과 동작 계약이 샘플보다 우선한다.

공통 코드는 `/opt/data/shared/references/samples/spring/README.md`와 `ADAPTATION.md`에 연결돼 있다. Kotlin은 구현 예시일 뿐 Java/Python에 같은 클래스·문법·JPA를 강제하지 않는다. 대상 언어/ORM의 기존 확장 지점으로 책임과 동작을 옮긴다.

명시적 `@Convert`, null/빈 값, 기존 암호문, 저장·조회 round-trip과 재저장을 확인한다. Argon2 해싱은 암복호화와 구분하고 해시를 재저장할 때 재해시하는 Converter 패턴을 자동 채택하지 않는다. 필요한 샘플만 읽고 실제 읽은 경로·재사용 대상·차이·검증을 기존 계획에 기록한다. 전체 샘플 복사·새 의존성 자동 설치·운영 데이터 변경은 하지 않는다.

## Repository / QueryDSL

- existing repository split/custom interface/implementation naming을 따른다.
- query에서 API/DB/File 호출을 하지 않는다.
- paging query는 count query 비용과 ordering 안정성을 확인한다.
- collection fetch join + paging 등 JPA 제약을 무시하지 않는다.
- loop/collection pipeline 내 repository 반복 호출은 N+1 가능성을 확인한다.

## Dependency 정책

프로젝트에 QueryDSL이 없는데 복잡 쿼리가 필요한 경우 자동으로 dependency를 추가하지 않는다. dependency 추가는 합의된 직접 개발 결정사항으로 올린다.

## Verification / Evidence

```text
Skill: dev-spring-data
Detected JPA / QueryDSL versions
Pattern References
Query Strategy: METHOD_QUERY | QUERYDSL | NATIVE
Reason for Strategy
SQL/N+1 considerations
Repository/Integration Tests
Residual Risk
```
