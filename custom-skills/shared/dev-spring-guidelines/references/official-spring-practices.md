# Official Spring Practices Reference

이 문서는 Spring Framework / Spring Boot 공식 Reference를 바탕으로 `dev-spring-guidelines`가 판단할 때 사용하는 상세 근거다.

감사 기준일: 2026-09-11. 당시 공식 문서의 최신 Stable 계열은 Spring Framework 7.0.x, Spring Boot 4.1.x이지만, **실제 작업에서는 대상 프로젝트의 Spring Boot / Spring Framework major/minor version이 항상 우선**한다. Boot 2.x/3.x/4.x 또는 Framework 5.x/6.x/7.x 사이의 API·annotation·Jakarta 전환 차이를 무시하고 최신 방식으로 자동 migration하지 않는다.

## 1. Dependency Injection

Spring Framework는 required dependency에 constructor injection을 일반적으로 권장한다. constructor injection은 필수 의존성을 완전 초기화 상태로 만들고 immutable component 구성을 돕는다.

기본 판단:

```text
required dependency
→ constructor injection 우선

optional / runtime reconfiguration dependency
→ 기존 프로젝트가 사용하면 setter injection 검토

field injection
→ 기존 legacy pattern 유지가 필요한 경우 외에 신규 기본값으로 선택하지 않음
```

constructor parameter가 지나치게 많다면 annotation을 바꾸는 문제가 아니라 class responsibility가 과도한지 검토한다.

공식 근거:
- https://docs.spring.io/spring-framework/reference/core/beans/dependencies/factory-collaborators.html

## 2. Externalized Configuration

Spring Boot는 structured application configuration에 `@ConfigurationProperties`를 제공하고, 단일/간단 property에는 `@Value`도 지원한다.

새 application-owned 설정 묶음은 다음을 우선 검토한다.

```text
여러 관련 key / type-safe configuration / metadata 필요
→ @ConfigurationProperties

한두 개 단순 값 / 기존 프로젝트가 @Value 사용
→ @Value 유지 가능
```

`@ConfigurationProperties` type은 환경 설정 표현에 집중하고 다른 application bean dependency를 섞지 않는 것을 기본으로 한다. Relaxed binding, validation, scanning/`@EnableConfigurationProperties` 방식은 대상 Boot version과 기존 convention을 따른다.

`@Value` property key를 새로 추가할 때는 Boot 공식 권장처럼 canonical kebab-case를 우선 검토한다.

공식 근거:
- https://docs.spring.io/spring-boot/reference/features/external-config.html

## 3. Declarative Transaction

Spring declarative transaction은 기본적으로 AOP proxy 기반이다.

핵심 제약:

```text
proxy를 통과한 external call
→ @Transactional advice 적용 가능

같은 bean 내부 self-invocation
→ 기본 proxy mode에서는 새 @Transactional metadata가 적용되지 않음

@PostConstruct / initialization 시점 의존
→ transaction proxy 동작을 전제로 하지 않음
```

Spring 팀은 transaction annotation을 구체 클래스의 method에 두는 방식을 권장한다.

기본 rollback semantics:

```text
RuntimeException / Error
→ rollback

checked Exception
→ 기본값은 rollback 아님
```

따라서 checked exception rollback이 요구사항이면 기존 프로젝트의 `rollbackFor` convention 또는 명시적 transaction policy를 확인한다.

`readOnly = true`는 데이터 불변성을 강제하는 보안 장치가 아니라 transaction/provider 최적화 hint 성격으로 취급한다. 실제 write 차단 여부를 가정하지 않는다.

외부 API/File/Network 호출을 DB transaction 내부에 새로 넣으면 lock duration, retry, timeout, partial failure를 검토한다.

공식 근거:
- https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/tx-decl-explained.html
- https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/annotations.html
- https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/rolling-back.html

## 4. MVC Validation

Spring MVC는 Bean Validation과 method validation을 모두 지원한다.

일반 객체 binding validation:

```text
@RequestBody / @ModelAttribute / @RequestPart object
+ @Valid 또는 프로젝트의 @Validated
→ object validation
```

Spring Framework 6.1+ MVC에는 built-in method validation이 있으며 method parameter/return value에 constraint가 직접 선언되면 `HandlerMethodValidationException` 경로가 사용될 수 있다. Object validation은 `MethodArgumentNotValidException`을 사용할 수 있다.

Framework 6.1+에서 controller class-level `@Validated`는 AOP method validation을 유발할 수 있으므로 built-in MVC method validation을 의도하면 기존 controller convention과 version을 확인해야 한다.

따라서 신규 global exception handling을 만들 때 version이 지원한다면 두 validation exception 경로를 확인한다. 기존 공통 error handler가 이미 처리하고 있으면 중복 handler를 추가하지 않는다.

공식 근거:
- https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-validation.html
- https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-config/validation.html
- https://docs.spring.io/spring-framework/reference/core/validation.html

## 5. Error Response / ProblemDetail

Spring Framework 6+는 RFC 9457 기반 `ProblemDetail`, `ErrorResponse`, `ErrorResponseException`, `ResponseEntityExceptionHandler`를 지원한다.

하지만 공식 지원 기능이라는 이유만으로 프로젝트 기존 응답 규격을 교체하지 않는다.

```text
기존 CommonResponse / ErrorCode / BusinessException / GlobalExceptionHandler 존재
→ 기존 contract 우선

신규 프로젝트 또는 명시적 RFC 9457 migration 요구
→ ProblemDetail 검토
```

ProblemDetail 도입은 status/body/content-type/error field contract가 바뀔 수 있으므로 public API 변경으로 취급한다.

공식 근거:
- https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-ann-rest-exceptions.html
- https://docs.spring.io/spring-framework/reference/web/webflux/ann-rest-exceptions.html

## 6. MVC vs WebFlux

Spring MVC는 Servlet/blocking stack, Spring WebFlux는 Reactive Streams 기반 non-blocking stack이다. 두 모듈은 공존할 수 있으며 MVC application에서 reactive `WebClient`를 사용할 수도 있다.

따라서:

```text
MVC + JDBC/JPA
→ blocking model 유지가 기본

WebFlux + R2DBC/reactive downstream
→ end-to-end reactive 흐름 검토

MVC인데 WebClient가 필요함
→ WebFlux server architecture로 migration할 이유는 아님
```

blocking JPA/JDBC 호출을 `Mono`, `Flux`, `suspend`로 감싼다고 non-blocking persistence가 되는 것은 아니다. WebFlux handler/event-loop에서 blocking I/O를 새로 수행하면 scheduler/threading 영향과 기존 프로젝트 전략을 확인한다.

공식 근거:
- https://docs.spring.io/spring-framework/reference/web/webflux.html
- https://docs.spring.io/spring-framework/reference/web/webflux/new-framework.html
- https://docs.spring.io/spring-framework/reference/web/webflux/reactive-spring.html

## 7. REST Client 선택

현재 Spring Framework는 다음 client option을 제공한다.

```text
RestClient
→ synchronous fluent client

WebClient
→ reactive/non-blocking client

RestTemplate
→ 기존 synchronous client

HTTP Service Client
→ annotated Java interface 기반 client proxy
```

선택 규칙:

- 대상 Spring Framework version에서 지원하는 API만 사용한다.
- 기존 `RestTemplate`, `WebClient`, Feign 또는 project-specific client abstraction이 있으면 unrelated task에서 migration하지 않는다.
- synchronous use case에 reactive `WebClient`를 도입해 `.block()`을 곳곳에 확산시키지 않는다.
- reactive pipeline에서는 blocking client 호출을 직접 섞지 않는다.
- HTTP Service Client는 interface-based remote contract가 프로젝트 구조와 맞고 version이 지원할 때 검토한다.
- timeout, retry, error mapping, authentication, observability는 기존 공통 client abstraction이 있으면 재사용한다.

공식 근거:
- https://docs.spring.io/spring-framework/reference/web/webmvc-client.html
- https://docs.spring.io/spring-framework/reference/integration/rest-clients.html
- https://docs.spring.io/spring-framework/reference/web/webflux-http-service-client.html

## 8. Null-safety / JSpecify

Spring Framework 7은 framework API nullability를 JSpecify annotation으로 표현한다. Kotlin 2.1+는 JSpecify nullability를 strict하게 처리한다.

규칙:

- Java project에 JSpecify/NullAway/JetBrains annotation 등을 공식 문서만 보고 새 dependency로 자동 도입하지 않는다.
- 기존 Java null annotation convention을 유지한다.
- Kotlin + Spring Framework 7 조합에서는 `dev-kotlin-guidelines`와 함께 platform/nullability boundary를 확인한다.
- Spring major version upgrade와 nullability annotation migration을 일반 feature task에 섞지 않는다.

공식 근거:
- https://docs.spring.io/spring-framework/reference/languages/kotlin/null-safety.html

## 9. Reactive Transaction

Reactive transaction은 imperative transaction과 execution context가 다르다. Reactive transaction manager를 사용하는 경우 Reactor context 기반 semantics를 고려해야 하며 ThreadLocal 기반 imperative transaction assumption을 그대로 적용하지 않는다.

```text
JPA/JDBC + PlatformTransactionManager
→ imperative transaction

R2DBC/reactive resource + ReactiveTransactionManager
→ reactive transaction semantics
```

한 use case에서 두 모델을 혼합하면 commit/rollback boundary를 명확히 검증한다. 단순히 return type을 `Mono`/`Flux`로 바꾸는 것은 transaction model migration이 아니다.

공식 근거:
- https://docs.spring.io/spring-framework/reference/data-access/transaction.html

## 10. Project Convention First

공식 문서가 더 새로운 API를 제시하더라도 다음은 자동 migration 근거가 아니다.

```text
RestTemplate → RestClient
custom error wrapper → ProblemDetail
field injection → project-wide constructor migration
@Value → project-wide @ConfigurationProperties migration
MVC → WebFlux
JPA/JDBC → R2DBC
legacy transaction structure → 새 architecture
```

해당 migration이 요구사항에 직접 필요하면 Standard Flow에서 API/dependency/runtime/operational impact를 별도 결정한다.
