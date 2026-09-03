---
name: dev-spring-feature
description: Spring 기능 단위 구현에서 기존 프로젝트 패턴을 유지하며 Controller, Service, DTO, Validation, Exception을 함께 변경하고 공통 응답 규격을 사용한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, spring, feature, controller, service, dto, validation, exception]
    related_skills: [dev-spring-guidelines, dev-spring-data, dev-spring-test, dev-api-docs]
    requires_tools: [terminal]
---

# dev-spring-feature

Spring/Spring Boot에서 하나의 API/use case 기능을 구현하거나 수정할 때 사용하는 capability Skill이다.

먼저 `dev-spring-guidelines`와 `/opt/data/shared/references/project-pattern-rules.md`를 적용한다.

## 적용 대상

```text
Controller/API endpoint
Service/Application use case
Request/Response DTO
Bean Validation / custom validation
Exception / ErrorCode 연계
공통 Response wrapper 적용
```

JPA/Repository/QueryDSL이 포함되면 `dev-spring-data`도 적용한다. 테스트가 포함되면 `dev-spring-test`, API 문서가 포함되면 `dev-api-docs`를 적용한다.

## 실행 순서

1. 요청과 가장 유사한 기존 기능을 찾는다.
2. Controller → Service → Data/Domain → Response의 실제 호출 흐름을 확인한다.
3. 기존 DTO naming/type, validation, exception, response wrapper를 확인한다.
4. 요구사항을 만족하는 최소 변경을 구현한다.
5. 기존 공통 응답 규격을 유지한다.
6. validation 실패와 domain/business 오류가 기존 error contract로 표현되는지 확인한다.
7. public API contract가 변경되면 Task/AC에 명시된 범위인지 확인한다.
8. targeted test 및 compile을 실행한다.

## Controller

- URL/versioning/HTTP method/status code convention은 기존 API를 따른다.
- Controller에서 새 business logic을 만들지 않는다. 단 기존 architecture가 의도적으로 다른 구조면 유지한다.
- Request binding과 validation annotation은 기존 방식(`@Valid`, `@Validated` 등)을 따른다.
- 응답은 기존 공통 Response 규격을 사용한다.

## Service / Application

- use case orchestration과 transaction boundary는 기존 pattern을 따른다.
- 단순 pass-through layer를 새로 추가하지 않는다.
- Entity/Domain object에 이미 있는 behavior는 중복 구현하지 않는다.
- 다른 Service를 호출하는 패턴, mapper 사용 방식도 기존 프로젝트를 우선한다.

## DTO

- `Request`, `Response`, `Command`, `Condition`, `Query` 등 naming은 프로젝트 기존 naming을 따른다.
- Java record/Kotlin data class/class 선택도 기존 convention을 따른다.
- Entity를 API response로 직접 노출하지 않는 기존 convention이 있다면 유지한다.

## Validation / Exception

- 표준 Bean Validation annotation으로 해결 가능하면 기존 annotation을 우선한다.
- 기존 custom validator가 있으면 재사용한다.
- 한 번만 쓰는 단순 검증을 위해 과도한 custom annotation을 만들지 않는다.
- ErrorCode/BusinessException/GlobalExceptionHandler가 있으면 기존 체계를 사용한다.

## 변경 금지 기본값

요구사항에 없는 다음 변경을 함께 하지 않는다.

```text
공통 response wrapper 재설계
exception hierarchy 전면 변경
새 mapper/library 도입
package/layer migration
unrelated endpoint refactor
```

## Verification / Evidence

```text
Skill: dev-spring-feature
Pattern References
Affected API / Use Case
Response Contract Used
Validation / Error Contract Used
Automated Tests
Manual Contract Checks
Residual Risk
```
