---
name: dev-kotlin-guidelines
description: Kotlin/JVM 구현에서 프로젝트 Kotlin 버전과 기존 convention을 우선하면서 null-safety, immutable modeling, data/value/sealed class, annotation target, coroutine, KSP/kapt, Spring/JPA interop을 안전하게 적용하는 공통 capability skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, kotlin, jvm, guidelines, convention, null-safety, coroutine, spring, jpa, ksp]
    related_skills: [dev-implement-plan, dev-project-pattern, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test]
    requires_tools: [terminal]
---

# dev-kotlin-guidelines

Kotlin/JVM 작업에 추가 적용하는 언어 전용 규칙이다. `/opt/data/shared/references/coding-rules.md`의 언어 독립 규칙과 대상 프로젝트 convention을 대체하지 않는다.

## 우선순위

```text
사용자/Task 명시 정책
→ 대상 프로젝트의 Kotlin/Spring/JPA convention
→ 대상 프로젝트 Kotlin compiler/language version에서 지원되는 Stable 기능
→ 이 Skill의 Kotlin 기본 규칙
→ 일반 Kotlin 관례
```

기존 프로젝트의 Kotlin version, languageVersion, apiVersion, Spring Boot/Framework, Gradle/Maven, compiler plugin을 임의로 올리지 않는다. 신규 프로젝트의 version 선택은 planning 시점의 최신 Stable과 선택한 Spring Boot/toolchain 호환성을 확인해 결정한다.

현재 규칙은 Kotlin 2.4 계열에서 Stable이 된 context parameters, explicit backing fields, annotation target 개선을 이해하지만, **프로젝트가 해당 language level을 사용하지 않으면 이전 문법으로 작성한다.**

## 작업 전 확인

- Kotlin plugin/compiler version과 `languageVersion` / `apiVersion`
- JVM target / Java toolchain / Gradle 또는 Maven
- `kotlin("jvm")`, `kotlin-spring`, `kotlin-jpa` 등 compiler plugin
- `kotlin-reflect`, Jackson Kotlin module 등 runtime integration
- KSP/kapt 및 실제 annotation processor 지원 방식
- Java/Kotlin mixed source 여부와 Java interop boundary
- Spring MVC/WebFlux, JDBC/JPA/R2DBC 등 blocking/reactive stack
- 동일 역할의 기존 DTO/entity/domain/service/test convention

Task-time에 Kotlin/JDK/Gradle/Maven을 임의 설치하거나 버전을 변경하지 않는다.

## Language Feature Stability

기본 정책:

```text
Stable       → project version이 지원하고 기존 코드와 맞으면 사용 가능
Beta         → 기존 프로젝트가 이미 사용하거나 Task에 명시적 근거가 있을 때만
Experimental → 사용자/Task 승인 없는 신규 도입 금지
```

새 문법이 더 짧다는 이유만으로 unrelated code를 일괄 변환하지 않는다.

### Context parameters

Kotlin 2.4에서 Stable이지만 일반 Spring dependency injection을 대체하지 않는다.

- Spring component dependency는 constructor injection을 기본으로 한다.
- context parameters는 DSL, bounded domain operation처럼 contextual dependency 자체가 모델의 일부일 때만 검토한다.
- Service/Repository dependency를 숨기기 위한 일반적인 DI 수단으로 사용하지 않는다.

### Explicit backing fields

프로젝트 Kotlin version이 지원하면 내부 mutable / 외부 read-only 계약을 명확히 표현하는 경우 검토한다.

```text
Aggregate 내부 MutableList + 외부 List view
observable/internal state + public read-only API
```

지원하지 않는 version에서는 기존 `_items` + read-only property 패턴을 유지한다.

## Null-safety / Java Interop

- 부재 가능성은 `T?`로 표현하고 public Kotlin API에서 `Optional<T>`를 기본값으로 사용하지 않는다.
- `!!`는 기본 금지에 가깝게 취급한다.
- Java platform type은 application/domain 안으로 퍼뜨리지 말고 boundary에서 nullable/non-null contract를 정규화한다.
- smart cast, safe-call, Elvis, `requireNotNull`/`checkNotNull` 중 의미에 맞는 방식을 사용한다.
- `requireNotNull`은 caller input/precondition, `checkNotNull`은 internal state invariant 성격을 우선 고려한다.
- null을 빈 문자열/0/empty collection과 임의로 동일시하지 않는다.

`!!` 허용은 외부 framework/library contract가 실제로 non-null인데 Kotlin type으로 표현되지 않고 대체 수단이 과도하게 복잡한 boundary에 한정한다. 사용 이유가 diff/context에서 설명 가능해야 한다.

Spring 7+ JSpecify 또는 Java nullability annotation을 Kotlin이 해석하는 boundary에서는 annotation contract를 존중하며 cast/`!!`로 무시하지 않는다.

## Immutability

- local/field는 기본 `val`; 상태 변경이 실제 domain/lifecycle에 필요할 때만 `var`.
- collection도 외부 계약은 read-only `List/Set/Map`을 우선한다.
- mutable collection/reference를 그대로 외부에 노출하지 않는다.
- `copy()`가 자연스러운 immutable value/DTO에는 `data class`를 적극 검토한다.

## DTO / Value / Domain Modeling

### data class

Request/Response/command/query/result/value 성격의 immutable carrier에는 기존 프로젝트 convention과 맞으면 `data class`를 우선 검토한다.

단순히 boilerplate를 줄이기 위해 lifecycle/identity entity를 `data class`로 바꾸지 않는다.

### value class

타입 안전성이 실제 의미를 가지는 단일 값 domain type에 `@JvmInline value class`를 검토한다.

예:

```text
AccountId / AssetId / OrderId
Money 단위가 이미 별도 amount/currency 모델로 합의된 경우의 좁은 scalar wrapper
```

다음 boundary에서는 먼저 호환성을 확인한다.

```text
JPA entity id mapping
Jackson serialization/deserialization
Spring configuration binding
reflection/generic framework
Java 호출 API
```

framework 호환성 때문에 반복 adapter/converter가 과도해지면 primitive/string wrapper를 강제하지 않는다.

### sealed class / sealed interface

닫힌 상태 집합, domain result, domain error category에는 sealed hierarchy를 우선 검토한다. `when`은 가능한 경우 exhaustive하게 작성하고 의미 없는 `else`로 새 subtype 누락을 숨기지 않는다.

`enum class`로 충분한 단순 상수 집합을 sealed hierarchy로 과설계하지 않는다.

## JPA Entity 규칙

JPA Entity는 기본적으로 일반 `class`를 사용한다.

- Entity를 기본적으로 `data class`로 만들지 않는다.
- `equals/hashCode/toString/copy/componentN`이 persistence identity/lazy association/lifecycle에 미치는 영향을 확인한다.
- proxy/open/no-arg 요구는 수동 `open`/dummy constructor 도배보다 프로젝트가 사용하는 `kotlin-spring` / `kotlin-jpa` compiler plugin을 우선한다.
- plugin이 없는 기존 프로젝트에 Task 범위 밖으로 dependency/plugin을 자동 추가하지 않는다.
- Entity property mutability와 constructor visibility는 동일 프로젝트의 JPA convention을 우선한다.

## Spring DI / Class Openness

Spring component는 constructor injection을 기본으로 한다.

```kotlin
@Service
class AssetService(
    private val assetRepository: AssetRepository,
)
```

- field injection을 새로 도입하지 않는다.
- DI 목적으로 `lateinit var`를 기본 사용하지 않는다.
- Kotlin class/method가 final이라는 이유로 application code에 `open`을 광범위하게 직접 추가하지 않는다.
- Spring proxy가 필요한 프로젝트는 기존 `kotlin-spring` / all-open 설정을 확인한다.

## Annotation Use-site Target

Validation/JPA/Jackson/DI 등 annotation target이 runtime/reflection 의미를 바꾸는 경우 target을 의식적으로 선택한다.

```text
@field:
@get:
@param:
@set:
@all:
```

- 모든 annotation에 기계적으로 `@field:`를 붙이지 않는다.
- Kotlin 2.4의 annotation default target 변화가 프로젝트 framework 동작과 충돌할 수 있으면 명시적 use-site target을 사용한다.
- 기존 validation/Jackson convention이 있으면 동일 방식이 우선이다.

## Scope Function

의미가 분명할 때만 사용한다.

```text
apply → receiver 설정/초기화
also  → receiver를 유지하는 부수효과
let   → nullable/local transform
run   → receiver 기반 계산 결과
with  → 이미 가진 receiver의 여러 member 접근
```

- scope function 중첩을 기본적으로 피한다.
- `it`와 `this`가 여러 겹 겹쳐 receiver/값을 추적하기 어려우면 명시적 local variable/function으로 바꾼다.
- 한 줄을 줄이기 위한 체이닝보다 control/data flow 가독성을 우선한다.

## Extension Function

- type 자체에 자연스럽게 귀속되는 변환/행동이고 dependency가 숨겨지지 않을 때 사용한다.
- repository/network/config 같은 외부 dependency를 extension 뒤에 숨기지 않는다.
- broad package의 공용 extension 난립을 피하고 bounded package/module에 둔다.
- 기존 member/API와 혼동되는 이름을 만들지 않는다.

## Coroutine / Flow

Kotlin이라는 이유만으로 `suspend`/`Flow`를 자동 도입하지 않는다.

```text
Spring MVC + JDBC/JPA → blocking stack 유지가 기본
WebFlux/R2DBC/coroutine-native integration → coroutine/Flow 검토
```

- blocking JPA/JDBC 호출을 `suspend`로 감싼 것만으로 non-blocking이라고 간주하지 않는다.
- structured concurrency를 유지하고 lifecycle 밖 `GlobalScope` 신규 사용을 금지한다.
- dispatcher 전환은 실제 blocking/CPU 특성 근거가 있을 때만 한다.
- transaction boundary와 coroutine context 전파를 확인한다.
- cancellation을 일반 Exception으로 삼켜버리지 않는다.

## KSP / kapt

신규 processor 선택 정책:

```text
processor가 KSP 지원 → KSP 우선
KSP 미지원          → kapt/기존 방식 유지
기존 kapt 프로젝트   → unrelated migration 금지
```

KSP 사용을 위해 framework/library를 임의 교체하거나 version upgrade를 강제하지 않는다. KSP와 kapt가 병행되는 기존 migration 단계면 현재 module convention을 유지한다.

## Serialization / Jackson

- Spring/Jackson 프로젝트에서 Kotlin DTO serialization이 필요하면 기존 Jackson Kotlin module 설정을 확인한다.
- nullable/default parameter 의미를 API contract와 맞춘다.
- absent와 explicit `null`을 동일 취급하면 안 되는 API에서는 serializer/deserializer/config 동작을 확인한다.
- `lateinit`, platform type, unchecked cast로 deserialization 문제를 숨기지 않는다.

## Equality / Copy / Destructuring

- domain identity와 value equality를 구분한다.
- `data class.copy()`가 invariant를 우회할 수 있는 domain object에는 data class 사용 자체를 재검토한다.
- destructuring이 변수 의미를 흐리면 명시적 property 접근을 사용한다.
- position 기반 destructuring에 domain 의미를 과도하게 의존하지 않는다.

## Naming / KDoc / Public API

Kotlin 공식 convention과 프로젝트 기존 스타일을 따른다.

- class/interface/object/type alias: PascalCase
- function/property/local: camelCase
- package: lowercase without underscore를 기본으로 하되 기존 package convention 우선
- public/protected API는 library/module convention이 요구하면 explicit return type과 KDoc을 작성한다.
- private/internal 구현의 자명한 타입까지 기계적으로 explicit type/KDoc을 강제하지 않는다.
- KDoc은 구현 번역보다 계약, 제약, 이유, 예외/호환성 정보를 우선한다.

## Java + Kotlin Mixed Project

- Java와 Kotlin을 서로 다른 first-class language capability로 취급한다.
- Kotlin diff에는 `dev-kotlin-guidelines`, Java diff에는 `dev-java-guidelines`를 적용한다.
- 공유 public API에서 SAM, checked exception, nullability, default argument, overload/JVM name, collection mutability 등 interop을 확인한다.
- Kotlin idiom을 이유로 Java caller contract를 조용히 깨지 않는다.

## Spring capability와의 관계

```text
dev-kotlin-guidelines
  → Kotlin version / idiom / null-safety / interop / compiler plugin / coroutine

dev-spring-guidelines
  → Spring layer / response / transaction / component convention

dev-spring-data
  → JPA / Repository / QueryDSL / Converter / persistence
```

같은 규칙을 여러 Skill에 복제하지 않는다. Kotlin + Spring/JPA 작업은 필요한 capability를 조합한다.

## Review 위험 신호

다음은 diff에서 반드시 의도를 확인한다.

```text
!! 신규 사용
Entity data class
public mutable collection exposure
unbounded scope-function nesting
platform type propagation
unchecked cast로 null/type 문제 은폐
Spring DI를 context parameter/lateinit으로 대체
JPA/JDBC 위에 근거 없는 suspend/Flow
GlobalScope
Experimental language feature opt-in 신규 추가
KSP/kapt/framework version 동시 변경
annotation use-site target 변경
value class를 persistence/serialization boundary에 신규 투입
```

## Verification / Evidence

Kotlin 변경 handoff에는 필요할 경우 다음을 남긴다.

```text
Skill: dev-kotlin-guidelines
Detected Kotlin version / language level
JVM target / build tool
Spring/JPA compiler plugins
Annotation processing: KSP | kapt | none
Blocking/Reactive stack
Java interop boundary
Intentional deviations
Verification
```
