---
name: dev-java-guidelines
description: Java 구현에서 대상 프로젝트의 target Java와 기존 convention을 우선하고 Oracle/OpenJDK 공식 문서 기준의 Stable 언어 기능·Optional·collection·동시성·문서화 규칙을 적용하는 공통 capability skill.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, java, guidelines, convention, official-docs, record, sealed, pattern-matching, optional, collections, virtual-thread, lombok, javadoc]
    related_skills: [dev-implement-plan, dev-project-pattern, dev-kotlin-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test]
    requires_tools: [terminal]
---

# dev-java-guidelines

Java 작업에 추가 적용하는 공통 규칙이다. `/opt/data/shared/references/coding-rules.md`의 언어 독립 규칙과 대상 프로젝트의 기존 convention을 반복하거나 대체하지 않는다.

상세 공식 근거와 feature별 판단은 필요할 때만 `references/official-java-practices.md`를 읽는다.

## 우선순위

```text
사용자/Task 명시 정책
→ 대상 프로젝트의 target Java / 기존 Java convention
→ 이 Skill의 Java 전용 규칙
→ Oracle/OpenJDK Stable 관례
```

공식 최신 문법을 사용할 수 있다는 이유로 project Java version, framework, build tool을 자동 upgrade하지 않는다.

## 작업 전 확인

- `.hermes/toolchain.env`, Gradle/Maven 설정과 실제 target/source Java version
- preview/incubator enable 여부와 compiler arguments
- 기존 package/naming/type 배치 방식
- Lombok dependency와 기존 annotation 사용 여부
- record/class/interface/enum/sealed hierarchy 및 pattern matching 사용 패턴
- Optional/null, collection mutability/ownership, Stream 사용 패턴
- Executor/thread/concurrency 사용과 runtime/framework 제약
- JavaDoc 또는 프로젝트 documentation convention
- 직렬화/JPA/프레임워크가 생성자·접근자·reflection/proxy에 요구하는 제약

Java/JDK/Gradle/Maven을 task-time에 새로 설치하거나 버전을 임의 변경하지 않는다.

## Language Feature Stability Gate

```text
Stable + target Java 지원 + project convention과 호환
→ 사용 가능

Preview / Incubator
→ 기존 프로젝트가 명시적으로 사용 중인 경우에만 현재 범위에서 유지 가능
→ 신규 `--enable-preview`, incubator module, preview syntax 자동 도입 금지

지원 version보다 새로운 문법/API
→ Java version upgrade로 해결하지 않고 현재 target에서 구현
```

Java 26 공식 문서에 존재하는 기능이라도 Preview이면 production 기본값으로 취급하지 않는다.

## Modern Java 적용 기준

### `var`

- local variable의 우변과 이름만으로 타입/의도가 명확할 때 중복 타입 표기를 줄이는 용도로 검토한다.
- method result type, numeric conversion, generic 의미가 흐려지면 명시 타입을 유지한다.
- 최신 문법 사용 자체를 목적으로 기존 local variable을 일괄 변환하지 않는다.

### Record

record는 immutable한 plain data aggregate/data carrier의 기본 후보다.

```text
immutable DTO / command / query / result carrier
→ record 검토

JPA Entity / persistence identity / framework proxy-noarg-mutable 제약
→ 일반 class 우선
```

기존 public class를 record로 바꾸면 constructor/accessor/equality/serialization contract가 달라질 수 있으므로 style-only refactor로 취급하지 않는다.

### Sealed Class / Interface

- 가능한 subtype이 의도적으로 닫힌 domain result/error/state/type family이면 검토한다.
- 외부 extension point, plugin SPI, framework subclass/proxy 대상은 자동으로 sealed 처리하지 않는다.
- sealed hierarchy + exhaustive `switch`가 누락 case를 줄이는 경우 활용할 수 있다.

### Pattern Matching / Switch

- target Java에서 Stable인 `instanceof` pattern, switch pattern, record pattern만 사용한다.
- 명시적 cast와 중복 type check를 줄이고 읽기 쉬워질 때 적용한다.
- business logic을 거대한 pattern `switch` 한 곳에 몰아넣는 근거로 사용하지 않는다.

## Optional / Null

Oracle Optional API Note에 맞춰 `Optional`은 **주로 method return type에서 결과 부재를 표현하는 용도**로 사용한다.

- `Optional` 자체를 `null`로 반환/저장하지 않는다.
- `Optional.get()`보다 `orElseThrow`, `map`, `flatMap`, `ifPresent` 등 의도가 드러나는 연산을 우선 검토한다.
- 모든 nullable field/parameter를 Optional로 기계적으로 바꾸지 않는다.
- JPA Entity/DTO/serialization field를 근거 없이 Optional로 바꾸지 않는다.
- empty collection이 충분한데 `Optional<List<T>>`를 중복 사용하지 않는다.
- `isPresent()` + `get()` 반복이 단순 null-check 대체라면 더 명확한 Optional API 또는 기존 project null contract를 검토한다.

## Collection Ownership / Mutability

collection을 외부에 전달할 때 ownership과 mutation contract를 확인한다.

```text
변경 불가능한 snapshot 필요
→ target Java가 지원하면 List.copyOf / Set.copyOf / Map.copyOf 검토

backing collection의 live read-only view가 실제 의도
→ Collections.unmodifiable* 검토

내부 working collection이 계속 변경됨
→ modifiable collection 유지
```

- unmodifiable collection과 deep immutable object graph를 동일시하지 않는다.
- mutable collection/array를 public boundary에 그대로 노출하지 않도록 검토한다.
- defensive copy를 비용 없는 style 규칙처럼 무조건 적용하지 않는다.

## Stream / Iteration

- side-effect 없는 map/filter/reduce pipeline이 명확할 때 Stream을 사용한다.
- 복잡한 branching, checked exception, stateful mutation 때문에 pipeline이 더 어려워지면 명시적 loop를 유지한다.
- Stream 내부에서 DB/API/File/Network I/O를 숨겨 N+1/반복 I/O를 만들지 않는다.
- `parallelStream()`은 workload, ordering, thread-safety, pool 영향 근거 없이 사용하지 않는다.

## Exception

- catch 후 예외를 무시하거나 정상 성공처럼 계속하지 않는다.
- 광범위한 `catch (Exception)`은 boundary/fallback 같은 명확한 이유가 있을 때만 사용한다.
- exception을 변환할 때 가능한 경우 cause를 보존한다.
- exception을 일반 control flow로 남용하지 않는다.
- checked/unchecked 정책은 기존 project/framework contract를 우선하며 unrelated 전역 변환을 하지 않는다.

## Virtual Threads

Virtual threads는 target Java >= 21에서 높은 동시성의 **blocking I/O throughput**을 위한 후보이며 latency/CPU 성능 향상 기능으로 취급하지 않는다.

도입 전 확인:

```text
target Java >= 21
많은 동시 blocking I/O task
framework/runtime 지원 또는 통제 가능한 적용 범위
ThreadLocal / transaction / security context / synchronization / monitoring 영향
```

- CPU-bound 작업 가속을 위해 사용하지 않는다.
- virtual thread를 다시 작은 fixed pool로 제한하지 않는다.
- 기존 Executor/framework runtime 설정을 unrelated task에서 자동 교체하지 않는다.
- 직접 `Executors.newVirtualThreadPerTaskExecutor()`를 쓰면 lifecycle/종료를 명확히 관리한다.

## Lombok

Lombok은 프로젝트가 이미 사용하고 있고 현재 코드 패턴과 호환될 때만 기존 convention을 따른다.

- Lombok이 없는 프로젝트에 편의를 이유로 dependency를 추가하지 않는다.
- 기존 코드가 `@Getter`, `@RequiredArgsConstructor`, `@Builder` 등을 일관되게 사용하면 같은 계층의 유사 코드에서 그 패턴을 우선한다.
- Entity/JPA model에서 `@Data`, 광범위한 `@EqualsAndHashCode`, 무분별한 `@ToString` 등은 기존 프로젝트 사용 여부와 persistence 특성을 먼저 확인한다.
- record가 존재한다는 이유로 기존 Lombok DTO를 unrelated task에서 record로 자동 변환하지 않는다.

## Top-level / Nested Type

새 DTO, enum, record, helper type은 대상 프로젝트의 동일 역할 타입 배치를 먼저 따른다.

```text
여러 클래스에서 사용되거나 독립적인 도메인/API 의미가 있음
→ top-level type 우선

한 클래스의 구현 세부사항이며 외부 재사용 의미가 없음
→ private/static nested type 검토
```

단순히 파일 수를 줄이기 위해 공개 DTO/record/enum을 nested type으로 몰아넣지 않는다. Spring/Jackson/JPA/validation/schema generation 등이 타입 가시성/생성자에 의존하면 framework 제약을 우선한다.

## JavaDoc / Documentation

- public/protected API와 비직관적인 주요 로직은 프로젝트가 JavaDoc을 사용하는 경우 동일 수준으로 작성한다.
- `@param`, `@return`, `@throws`는 의미 있는 contract 정보가 있을 때 사용하고 시그니처를 그대로 번역하지 않는다.
- 구현 이유, compatibility 제약, 입력/출력 의미처럼 코드만 보고 알기 어려운 내용을 우선 설명한다.

## Spring / Kotlin과의 관계

```text
dev-java-guidelines
→ Java version / Stable feature / Optional / collection / concurrency / Lombok / JavaDoc

dev-kotlin-guidelines
→ Kotlin language / idiom / interop

dev-spring-guidelines
→ Spring common convention / response / layer / transaction

dev-spring-data
→ JPA / Repository / QueryDSL / Converter
```

Java + Kotlin mixed project에서는 실제 changed source 언어에 맞는 guideline을 적용한다. 동일 규칙을 여러 Skill에 복제하지 않는다.

## Review Hotspots

Java diff에서는 필요할 때 다음을 우선 점검한다.

```text
unsupported / Preview / Incubator feature
record ↔ JPA/framework/serialization compatibility
sealed hierarchy의 의도치 않은 extension 차단
Optional field/parameter 남용 / Optional 자체 null / Optional.get 반복
mutable collection/array boundary 노출
Stream 내부 반복 I/O / N+1 / 근거 없는 parallelStream
catch Exception / swallowed cause
virtual thread의 CPU-bound 오용 또는 runtime context 영향
unrelated Java/JDK/Gradle/Maven/framework upgrade
```

## Verification / Evidence

Java 변경 handoff에는 필요할 경우 다음을 남긴다.

```text
Skill: dev-java-guidelines
Detected Java version
Language feature stability: Stable | Existing Preview | Not Applicable
Build tool
Lombok convention: existing | absent | not-applicable
Record / Sealed / Pattern decision
Optional / Collection ownership decision
Concurrency / Virtual Thread impact
Type placement convention
Documentation convention
Intentional deviations
Verification
```
