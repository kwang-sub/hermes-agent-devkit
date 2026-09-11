---
name: dev-spring-feature
description: Spring 기능 단위 구현에서 기존 프로젝트 패턴을 유지하며 Controller, Service, DTO, Validation, Exception을 함께 변경하고 version-aware MVC validation/error contract를 적용한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, spring, feature, controller, service, dto, validation, exception, problem-detail]
    related_skills: [dev-spring-guidelines, dev-spring-data, dev-spring-test, dev-api-docs]
    requires_tools: [terminal]
---

# dev-spring-feature

Spring/Spring Boot에서 하나의 API/use case 기능을 구현하거나 수정할 때 사용하는 capability Skill이다.

먼저 `dev-spring-guidelines`와 `/opt/data/shared/references/project-pattern-rules.md`를 적용한다. Spring version별 상세 근거가 필요하면 `dev-spring-guidelines/references/official-spring-practices.md`를 읽는다.

## 적용 대상

```text
Controller/API endpoint
Service/Application use case
Request/Response DTO
Bean Validation / method validation
Exception / ErrorCode 연계
공통 Response wrapper 적용
ProblemDetail / ErrorResponse (기존 contract 또는 명시적 요구가 있을 때)
```

JPA/Repository/QueryDSL이 포함되면 `dev-spring-data`도 적용한다. 테스트가 포함되면 `dev-spring-test`, API 문서가 포함되면 `dev-api-docs`를 적용한다.

## 실행 순서

1. 요청과 가장 유사한 기존 기능을 찾는다.
2. Controller → Service → Data/Domain → Response의 실제 호출 흐름을 확인한다.
3. Spring Boot/Framework version과 MVC/WebFlux 여부를 확인한다.
4. 기존 DTO naming/type, validation, exception, response wrapper를 확인한다.
5. 요구사항을 만족하는 최소 변경을 구현한다.
6. 기존 공통 응답/error 규격을 유지한다.
7. validation 실패와 domain/business 오류가 기존 error contract로 표현되는지 확인한다.
8. public API contract가 변경되면 Task/AC에 명시된 범위인지 확인한다.
9. targeted test 및 compile을 실행한다.

## Controller

- URL/versioning/HTTP method/status code convention은 기존 API를 따른다.
- Controller에서 새 business logic을 만들지 않는다. 단 기존 architecture가 의도적으로 다른 구조면 유지한다.
- Request binding과 validation annotation은 대상 Spring version과 기존 방식(`@Valid`, `@Validated` 등)을 따른다.
- 응답은 기존 공통 Response 규격을 사용한다.
- Spring Framework 6+ `ProblemDetail` 지원만을 이유로 기존 error body를 바꾸지 않는다.

## Validation

표준 Bean Validation annotation으로 해결 가능하면 기존 annotation을 우선한다.

```text
@RequestBody / @ModelAttribute / @RequestPart object + @Valid
→ object validation 후보

method parameter / return value 직접 constraint
→ 해당 Spring version의 method validation semantics 확인
```

Framework 6.1+ MVC에서는 built-in method validation이 `HandlerMethodValidationException`을 만들 수 있고 object validation은 `MethodArgumentNotValidException` 경로를 사용할 수 있다.

- GlobalExceptionHandler/ControllerAdvice가 두 경로를 이미 처리하는지 확인한다.
- class-level `@Validated`가 기존 AOP method validation을 위해 쓰이는지 확인하고, Framework 6.1+ built-in validation으로 임의 migration하지 않는다.
- validation group은 기존 convention이 있을 때 재사용하고 단순 케이스에 불필요한 group/custom annotation을 추가하지 않는다.
- `@Valid` 자체는 nested validation marker이며 모든 method validation 요구를 대신한다고 가정하지 않는다.

## Service / Application

- use case orchestration과 transaction boundary는 기존 pattern을 따른다.
- `@Transactional` method 간 self-invocation으로 새로운 transaction metadata가 적용된다고 가정하지 않는다.
- checked exception도 자동 rollback된다고 가정하지 않는다.
- 단순 pass-through layer를 새로 추가하지 않는다.
- Entity/Domain object에 이미 있는 behavior는 중복 구현하지 않는다.
- 다른 Service를 호출하는 패턴, mapper 사용 방식도 기존 프로젝트를 우선한다.

## DTO

- `Request`, `Response`, `Command`, `Condition`, `Query` 등 naming은 프로젝트 기존 naming을 따른다.
- Java record/Kotlin data class/class 선택은 각 language guideline과 기존 convention을 따른다.
- Entity를 API response로 직접 노출하지 않는 기존 convention이 있다면 유지한다.
- nullable/required field 의미는 Java/Kotlin type, validation annotation, OpenAPI/schema contract가 서로 모순되지 않는지 확인한다.

## Exception / Error Response

- ErrorCode/BusinessException/GlobalExceptionHandler가 있으면 기존 체계를 사용한다.
- Spring `ProblemDetail`, `ErrorResponse`, `ResponseEntityExceptionHandler`는 기존 contract와 호환되거나 명시적 migration 범위일 때만 사용한다.
- ProblemDetail 도입 시 status/body/content-type/extension field가 기존 client contract에 미치는 영향을 확인한다.
- framework exception을 그대로 노출해 내부 메시지/stack/구현 정보가 API contract가 되지 않게 한다.

## 변경 금지 기본값

요구사항에 없는 다음 변경을 함께 하지 않는다.

```text
공통 response wrapper 재설계
기존 error contract → ProblemDetail migration
exception hierarchy 전면 변경
validation AOP → built-in method validation 일괄 migration
새 mapper/library 도입
package/layer migration
unrelated endpoint refactor
```

## Verification / Evidence

```text
Skill: dev-spring-feature
Detected Spring Boot / Framework version
Pattern References
Affected API / Use Case
Response Contract Used
Validation Mode: OBJECT | METHOD | BOTH | NONE
Validation Exception Contract
Error Contract Used
Automated Tests
Manual Contract Checks
Residual Risk
```
