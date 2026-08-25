---
name: dev-spring-test
description: Spring/Spring Data JPA 기능의 테스트를 프로젝트 기존 테스트 프레임워크와 스타일에 맞춰 작성하고 변경 위험에 비례한 최소 검증을 수행한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, spring, test, junit, kotest, mockito, mockk, data-jpa]
    related_skills: [dev-spring-guidelines, dev-spring-feature, dev-spring-data]
    requires_tools: [terminal]
---

# dev-spring-test

Spring/Spring Data JPA 작업의 테스트 생성·수정·검증에 적용한다.

먼저 프로젝트의 기존 테스트 framework/style을 확인하고 `/opt/data/shared/references/project-pattern-rules.md`를 따른다.

## 작업 전 확인

```text
JUnit / Kotest
Mockito / MockK
AssertJ / Kotlin assertions
@SpringBootTest / @WebMvcTest / @DataJpaTest 사용 방식
fixture/factory/builder convention
test naming / display name
test package 위치
Testcontainers 사용 여부
DB test profile/config
```

새 테스트 라이브러리를 편의상 추가하지 않는다.

## 테스트 선택

변경 위험에 가장 가까운 테스트부터 작성한다.

```text
순수 domain/service logic → unit test
Controller contract/validation → 기존 MVC/API test 방식
Repository/QueryDSL/mapping → repository/integration test
여러 Spring bean wiring 필요 → 기존 integration test 방식
```

모든 변경을 무조건 `@SpringBootTest`로 검증하지 않는다. 반대로 실제 persistence/query behavior를 mock unit test만으로 증명하지 않는다.

## 테스트 작성 원칙

- 기존 test naming/arrange-act-assert/Given-When-Then style을 따른다.
- 구현 세부사항보다 외부 behavior와 contract를 검증한다.
- bug fix에는 가능하면 기존 실패를 재현하는 regression test를 추가한다.
- validation/error response 변경은 성공 케이스와 실패 contract를 함께 확인한다.
- QueryDSL/Repository 변경은 조건 조합, paging/order, null/empty edge case, duplicate/join 영향을 확인한다.
- mocking은 필요한 boundary에만 사용하고 실제 framework behavior 검증이 필요한 곳을 과도하게 mock하지 않는다.

## JPA / Query 검증

`dev-spring-data`와 함께 사용하면 다음을 추가 확인한다.

```text
Method Query 결과 정확성
QueryDSL 동적 조건 조합
Entity ↔ DB round-trip
AttributeConverter null/legacy value
fetch/join으로 인한 duplicate
N+1 가능성에 대한 실행 근거
```

## Verification / Evidence

```text
Skill: dev-spring-test
Detected Test Stack
Pattern References
Tests Added / Updated
Commands Executed
Passed / Failed / Not Run
Not-run Reason
Residual Risk
```

## 불변식

- 테스트를 통과시키기 위해 production behavior를 요구사항 밖으로 변경하지 않는다.
- flaky test를 삭제/skip/disable해서 성공으로 만들지 않는다.
- 기존 테스트 실패가 Task 변경과 무관하면 사실과 영향 범위를 구분해 보고한다.
