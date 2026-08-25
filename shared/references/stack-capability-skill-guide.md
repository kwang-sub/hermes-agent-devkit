# Stack / Capability Skill Extension Guide

이 문서는 `shared/references/coding-rules.md`와 `shared/references/project-pattern-rules.md`를 기반으로 특정 언어, 프레임워크, 기술 기능을 구현하는 전문 Skill을 추가할 때의 설계 규칙이다.

목표는 공통 코딩 규칙을 중복하지 않고 다음 구조로 확장하는 것이다.

```text
Common Coding Rules
        ↓
Project Pattern Rules
        ↓
Workflow Skill
(dev-fast-flow / dev-breakdown / dev-implement-plan / dev-code-review)
        ↓
Stack / Capability Skill
        ↓
Project-specific convention
        ↓
Implementation / Review
```

## 1. Skill 계층

### Foundation

항상 적용되는 언어 독립 규칙:

```text
shared/references/coding-rules.md
shared/references/project-pattern-rules.md
```

프로젝트 자체의 기존 구조와 convention은 stack skill보다 우선적인 구현 reference다. 단, 사용자/Task에 명시된 정책이 기존 코드와 충돌하면 해당 정책을 우선하되 범위를 넓혀 주변 코드를 자동 migration하지 않는다.

### Workflow Skill

작업 lifecycle을 담당한다.

```text
dev-fast-flow
dev-project-pattern
dev-breakdown
dev-implement-plan
dev-code-review
dev-review-cycle
```

Workflow Skill은 특정 프레임워크 기능을 직접 구현하지 않는다.

### Stack / Capability Skill

현재 1차 capability set:

```text
dev-spring-guidelines
dev-spring-feature
dev-spring-data
dev-spring-test
dev-api-docs
```

역할:

```text
dev-spring-guidelines
  Spring 공통 convention, response, transaction, 계층 책임

dev-spring-feature
  Controller, Service, DTO, Validation, Exception 기반 기능 구현

dev-spring-data
  JPA, Data JPA, QueryDSL, Entity, Repository, Converter, Paging

dev-spring-test
  Spring/JPA test stack과 검증

dev-api-docs
  OpenAPI/Swagger/Postman. Framework 독립 capability
```

`dev-tech-dispatch`는 두 번째 이상 framework가 실제로 필요할 때 도입한다. 현재는 Orchestrator `dev-project-pattern`과 Coder `dev-implement-plan`이 실제 project evidence에서 필요한 capability를 식별한다.

## 2. Java/Kotlin 분리 원칙

Spring 기능의 의미와 workflow가 동일하다면 Java/Kotlin을 별도 Skill로 만들지 않는다.

기본 구조:

```text
custom-skills/coder/dev-spring-<capability>/
├─ SKILL.md
├─ references/
│  ├─ java.md       # 필요할 때만
│  └─ kotlin.md     # 필요할 때만
├─ scripts/
└─ tests/
```

Skill은 먼저 실제 project source를 확인해 언어를 감지하고 현재 프로젝트 convention을 따른다.

Java/Kotlin의 차이가 단순 syntax 수준이면 하나의 SKILL.md 안에서 처리한다. Annotation target, nullability, data class, companion object, extension function 등 언어 특성으로 규칙이 충분히 달라질 때만 language-specific reference를 분리한다.

## 3. 모든 Capability Skill의 공통 실행 순서

```text
1. 프로젝트 stack/version 탐색
2. project-pattern-rules 기준으로 기존 동일/유사 기능 검색
3. 기존 convention/implementation 결정
4. 사용자 정책과 기존 구현 충돌 확인
5. 필요한 capability 선택
6. 최소 변경 구현
7. stack-specific verification
8. coder → reviewer handoff evidence 기록
```

새 dependency나 framework를 기본값으로 추가하지 않는다.

이미 프로젝트가 같은 목적의 library 또는 설정을 사용한다면 기존 것을 우선 사용한다.

## 4. Spring 공통 규칙

Spring/Spring Boot 프로젝트에서는 `dev-spring-guidelines`를 기본 capability로 적용한다.

핵심:

```text
대상 프로젝트 기존 패턴 최대 유지
공통 Response/Error contract 재사용
기존 transaction convention 유지
새 architecture/library/common contract 자동 도입 금지
```

Controller/Service/DTO/Validation/Exception 기능 작업은 `dev-spring-feature`를 추가 적용한다.

## 5. JPA / Query 정책

`dev-spring-data`는 다음 우선순위를 강제한다.

```text
1. Spring Data JPA Method Query
2. QueryDSL
3. Native Query
```

### Method Query

단순 조회, 존재 여부, count 등은 derived method query를 우선한다.

### QueryDSL

다음은 QueryDSL 우선:

```text
동적 조건
복수 조건 조합
복잡 JOIN
Projection
Paging/Sorting
Fetch Join
Method name이 과도하게 복잡해지는 조회
```

### Native Query

Native Query는 편의성 때문에 사용하지 않는다. DB vendor 전용 기능, QueryDSL/JPQL 표현 한계, 명확한 성능 근거, 유지 필수 legacy contract 등 앞 두 방식으로 해결하기 어려운 이유가 있어야 한다.

사용 시 handoff에 다음을 남긴다.

```text
Why Method Query is insufficient
Why QueryDSL is insufficient
Why Native Query is required
DB compatibility impact
Verification
```

QueryDSL dependency가 없는 프로젝트에 자동으로 새 dependency를 추가하지 않는다.

## 6. dev-api-docs 설계 방향

`dev-api-docs`는 Spring 전용이 아니다.

지원 mode:

```text
OPENAPI
POSTMAN
BOTH
```

공통 원칙:

```text
실제 application source contract가 source of truth
기존 문서 artifact/config 재사용
공통 Response/Error/Auth contract 반영
secret/token 실제 값 기록 금지
문서 생성을 이유로 API contract 변경 금지
```

### Spring OpenAPI Reference

Spring/SpringDoc 작업은 다음 예시 프로젝트를 reference로 사용한다.

```text
kwang-sub/backend-lab-archive
level-up-backend-gpt/level2-book-management-system
```

핵심 reference pattern:

```text
@Tag
@Operation
API별 ErrorCode example annotation
GroupedOpenApi
OperationCustomizer 기반 error response examples
필요 시 bearer/JWT SecurityScheme
```

예시 프로젝트의 `ResponseEntity<DTO>`는 응답 contract reference가 아니다. 대상 프로젝트에 공통 response wrapper가 있으면 해당 schema를 문서화한다.

### Postman

기존 collection grouping을 우선하고 없으면 domain/API별 folder를 사용한다.

반영 대상:

```text
method/path
query/path parameters
headers/auth
request body example
success response example
known error examples
baseUrl/auth environment variables
```

## 7. dev-spring-test 설계 방향

프로젝트에서 실제 사용하는 test stack을 우선한다.

```text
JUnit / Kotest
Mockito / MockK
AssertJ / Kotlin assertions
@WebMvcTest / @DataJpaTest / @SpringBootTest
Testcontainers
fixture/builder convention
```

변경 위험과 가장 가까운 테스트를 선택한다.

```text
순수 logic → unit
Controller/validation → API/MVC test
Repository/QueryDSL/mapping → persistence/integration test
실제 wiring 필요 → project integration test pattern
```

새 테스트 라이브러리를 편의상 추가하지 않는다.

## 8. Capability Skill과 Fast Flow

전문 Skill이라고 해서 반드시 Standard Flow를 요구하지 않는다.

예:

```text
기존 validation pattern의 한 필드 적용
기존 Data JPA method query 추가
기존 QueryDSL repository의 작은 조건 추가
기존 OpenAPI pattern으로 Controller 한 개 문서화
작은 regression test 보완
```

처럼 scope가 작고 선택/설계가 필요 없으면 Fast Flow에서도 사용할 수 있다.

반대로 다음은 Standard Flow 대상이다.

```text
새 API/public contract 설계
DB schema/migration 변경
QueryDSL/SpringDoc 등 새 dependency 도입
전체 API 문서 체계 변경
공통 Response/Error architecture 설계
다수 module에 걸친 migration
```

즉 Workflow 선택과 Capability Skill 선택은 서로 다른 축이다.

```text
Workflow = 작업 크기/모호성/승인 필요성
Capability Skill = 어떤 기술 작업을 수행하는가
```

## 9. Reviewer 확장 규칙

Capability Skill은 Reviewer가 확인할 수 있는 다음 정보를 남겨야 한다.

```text
Skill name
감지한 stack/version
Pattern References
Preserved Conventions
Query Strategy (해당 시)
Response Contract (해당 시)
생성/수정 artifact
실행한 verification
Intentional Deviations
Improvement Deferred
Residual Risk
```

Reviewer는 공통 Coding Rules와 Project Pattern Rules를 먼저 적용하고, 사용된 Capability Skill의 계약을 추가로 검증한다.

## 10. Naming 규칙

가능하면 다음 패턴을 사용한다.

```text
dev-<stack>-<capability>
```

예:

```text
dev-spring-guidelines
dev-spring-feature
dev-spring-data
dev-spring-test
```

Framework 독립 기능은 stack 이름을 넣지 않는다.

```text
dev-api-docs
```

언어 이름은 기능이 언어에 강하게 종속될 때만 포함한다.

## 11. Skill 추가 전 체크리스트

새 Skill을 만들기 전에 다음을 확인한다.

```text
[ ] coding-rules/project-pattern-rules로 해결할 수 없는 전문 기능인가
[ ] 반복 사용할 수 있는 작업 패턴인가
[ ] 기존 Skill과 역할이 겹치지 않는가
[ ] project detection 절차가 정의됐는가
[ ] 기존 구현 재사용 우선순위가 정의됐는가
[ ] 사용자 정책과 기존 pattern 충돌 처리 방식이 정의됐는가
[ ] dependency 추가 정책이 정의됐는가
[ ] stack-specific verification이 정의됐는가
[ ] Reviewer가 확인할 evidence가 정의됐는가
[ ] Java/Kotlin을 정말 별도 Skill로 분리해야 하는지 검토했는가
```
