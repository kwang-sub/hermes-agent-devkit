---
name: dev-spring-guidelines
description: Spring/Spring Boot 구현에서 대상 프로젝트 version/convention을 최우선으로 유지하고 Spring 공식 문서 기준의 DI, configuration, transaction, validation, web stack, HTTP client, nullability 규칙을 적용한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, spring, spring-boot, guidelines, convention, official-docs, dependency-injection, configuration, transaction, validation, webmvc, webflux, rest-client]
    related_skills: [dev-implement-plan, dev-java-guidelines, dev-kotlin-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-api-docs]
    requires_tools: [terminal]
---

# dev-spring-guidelines

Spring/Spring Boot 작업에 항상 추가 적용하는 공통 규칙이다. 프로젝트 자체 convention을 대체하지 않고 확장한다.

상세 공식 근거와 version별 판단은 필요할 때만 `references/official-spring-practices.md`를 읽는다.

## 우선순위

```text
사용자/Task 명시 정책
→ 대상 프로젝트의 Spring Boot / Spring Framework version과 기존 convention
→ 이 Skill의 합의 규칙
→ 현재 공식 Spring Stable 관례
```

최신 Spring 공식 문서에 있는 기능을 쓰기 위해 Boot/Framework/Java/Kotlin/dependency를 자동 upgrade하지 않는다.

## 작업 전 확인

- Spring Boot / Spring Framework version과 major migration 경계
- Java/Kotlin 및 build tool
- MVC / WebFlux / mixed client stack
- JDBC/JPA / R2DBC / reactive persistence stack
- 현재 package/layer 구조
- 유사 Controller/Service/DTO/Exception 구현
- 공통 Response/Error contract
- DI / validation / transaction convention
- externalized configuration 방식 (`@ConfigurationProperties`, `@Value`, custom loader)
- HTTP client 방식 (`RestClient`, `WebClient`, `RestTemplate`, Feign, HTTP Service Client, project wrapper)
- 이미 사용 중인 mapper/library/helper

## Version Compatibility Gate

대상 프로젝트 version이 source of truth다.

```text
project version에서 지원 + 기존 convention과 호환
→ 적용 가능

새 major/minor에서 추가된 API
→ 현재 project version이 지원하지 않으면 사용 금지

javax ↔ jakarta / proxy / validation / web error semantics 차이
→ 현재 project major에 맞춰 유지
```

Boot 2.x/3.x/4.x, Framework 5.x/6.x/7.x 차이를 일반 feature task에서 migration하지 않는다.

## Dependency Injection

required dependency의 신규 기본값은 constructor injection이다.

```text
required dependency
→ constructor injection

optional / reconfigurable dependency
→ project pattern에 따라 setter injection 검토
```

- 신규 field injection은 기존 legacy pattern을 유지해야 하는 명확한 근거가 없으면 만들지 않는다.
- dependency가 많아 constructor가 비대해지면 injection style보다 책임 분리가 필요한지 먼저 검토한다.
- Kotlin은 `private val`, Java는 final field 등 해당 언어 convention을 따른다.

## Externalized Configuration

application-owned 설정 key가 여러 개로 묶이면 `@ConfigurationProperties`를 우선 검토한다.

```text
관련 설정 묶음 / type-safe binding / metadata 필요
→ @ConfigurationProperties

단일 값 / 기존 @Value convention
→ @Value 유지 가능
```

- `@ConfigurationProperties` type은 환경 설정 표현에 집중하고 application service dependency를 섞지 않는다.
- `@Value` 신규 key는 가능하면 canonical kebab-case를 사용한다.
- 기존 설정 class를 요구 범위 밖에서 일괄 migration하지 않는다.

## 공통 응답 / Error Contract

API 응답은 프로젝트에 이미 존재하는 공통 응답 규격을 사용한다.

```text
ApiResponse<T>
CommonResponse<T>
BaseResponse<T>
기타 프로젝트 고유 wrapper
```

- 동일 module/API에서 실제 사용 중인 response/error wrapper를 찾아 재사용한다.
- 프로젝트에 공통 규격이 없으면 임의 wrapper를 새로 강제하지 않는다.
- Spring Framework 6+의 `ProblemDetail` / `ErrorResponse`는 공식 지원 기능이지만 기존 error contract를 자동 대체하지 않는다.
- ProblemDetail 도입은 public API/error body/content-type 변경 가능성이 있으므로 명시적 요구가 있을 때만 Standard Flow에서 결정한다.

## 계층 책임

```text
Controller: HTTP binding / validation / Service 호출 / response contract
Service/Application: use case orchestration + transaction boundary
Domain/Entity: 해당 객체에 자연스럽게 귀속되는 domain behavior
Repository/Data: persistence/query
```

기존 프로젝트가 다른 architecture를 명확히 사용하면 그 구조를 유지한다.

## Transaction

- 기존 `@Transactional` 위치와 readOnly convention을 먼저 확인한다.
- declarative transaction은 기본적으로 proxy 기반이므로 **self-invocation**에서 별도 method의 `@Transactional`이 새로 적용된다고 가정하지 않는다.
- transaction annotation은 가능하면 concrete service method/class의 기존 convention을 따른다.
- 기본 rollback은 `RuntimeException`/`Error`이며 checked exception은 기본 rollback 대상이 아님을 고려한다.
- `readOnly = true`를 write 차단 보안 장치로 간주하지 않는다.
- transaction boundary를 임의로 넓히거나 줄이지 않는다.
- 외부 API/File/Network 호출을 transaction 안에 새로 포함하면 lock/timeout/retry/partial failure 위험을 검토한다.
- `@PostConstruct` 같은 initialization 시점에 proxy transaction 동작을 전제로 하지 않는다.

## MVC / WebFlux / Reactive Boundary

```text
Spring MVC + JDBC/JPA
→ blocking model 유지가 기본

WebFlux + R2DBC/reactive downstream
→ end-to-end reactive 흐름 검토
```

- MVC 프로젝트가 `WebClient`를 사용한다고 WebFlux server architecture로 간주하지 않는다.
- blocking JPA/JDBC를 `Mono`/`Flux`/`suspend`로 감싼다고 non-blocking persistence가 되는 것으로 간주하지 않는다.
- WebFlux event-loop 경로에 blocking I/O를 새로 넣으면 scheduler/runtime 영향과 기존 대응 방식을 확인한다.
- imperative `PlatformTransactionManager`와 `ReactiveTransactionManager` semantics를 혼동하지 않는다.

## HTTP Client 선택

대상 version과 기존 project client abstraction을 우선한다.

```text
RestClient → synchronous fluent client 후보
WebClient → reactive/non-blocking client 후보
RestTemplate → 기존 synchronous code 유지 가능
HTTP Service Client → interface-based remote contract 후보
```

- 기존 `RestTemplate`/`WebClient`/Feign/project wrapper를 unrelated task에서 migration하지 않는다.
- synchronous flow에서 `WebClient.block()` 확산을 새 기본 패턴으로 만들지 않는다.
- reactive pipeline에 blocking client를 직접 섞지 않는다.
- timeout/retry/error mapping/auth/observability 공통 abstraction이 있으면 재사용한다.

## Validation / Nullability

- Controller object validation은 대상 version과 기존 `@Valid` / `@Validated` convention을 따른다.
- Framework 6.1+에서는 MVC built-in method validation과 class-level `@Validated` AOP 방식 차이를 확인한다.
- 해당 version에서 method validation이 사용되면 `MethodArgumentNotValidException`과 `HandlerMethodValidationException` error contract를 모두 점검한다.
- Spring Framework 7의 JSpecify nullability 때문에 Java/Kotlin boundary가 달라질 수 있으므로 project major와 language guideline을 함께 확인한다.
- JSpecify/null annotation dependency를 일반 feature task에서 새로 도입하지 않는다.

## Spring과 Language Capability 관계

```text
dev-java-guidelines
→ Java language / Optional / collection / concurrency

dev-kotlin-guidelines
→ Kotlin language / null-safety / coroutine / interop

dev-spring-guidelines
→ Spring DI / config / transaction / validation / web / HTTP client

dev-spring-data
→ JPA / Repository / QueryDSL / Converter
```

동일 규칙을 여러 Skill에 복제하지 않는다.

## 변경 통제

다음은 요구 범위 밖에서 자동 적용하지 않는다.

```text
Boot / Framework major-minor upgrade
architecture 변경
공통 response/error → ProblemDetail migration
field injection project-wide migration
@Value project-wide migration
RestTemplate → RestClient migration
MVC → WebFlux
JPA/JDBC → R2DBC
새 mapper/library/client dependency 도입
package 재구성
```

## Review Hotspots

Spring diff에서는 필요할 때 다음을 우선 점검한다.

```text
project Spring version에서 지원하지 않는 API
required dependency field injection 신규 도입
transaction self-invocation / rollback semantics 오해
external I/O를 포함한 과도한 transaction
기존 error contract를 무시한 ProblemDetail 도입
MVC/WebFlux 또는 JPA/R2DBC blocking/reactive 혼합
WebClient.block() 확산 / reactive pipeline blocking client
ConfigurationProperties에 application bean dependency 혼합
Framework 6.1+ validation exception 경로 누락
unrelated Boot/Framework/dependency migration
```

## Verification / Evidence

Coder handoff에 필요할 경우 다음을 남긴다.

```text
Skill: dev-spring-guidelines
Detected Spring Boot / Framework version
Web Stack: MVC | WEBFLUX | MIXED
Data Stack: JPA_JDBC | R2DBC | MIXED | NONE
DI Convention
Configuration Convention
Response / Error Contract Used
Transaction Convention Used
HTTP Client Convention
Validation Convention
Intentional Deviations
Verification
```
