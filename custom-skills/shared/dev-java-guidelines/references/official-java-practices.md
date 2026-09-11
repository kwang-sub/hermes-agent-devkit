# Java Official Practice Reference

이 문서는 `dev-java-guidelines`의 상세 판단 근거다. Oracle Java SE 문서와 OpenJDK JEP에서 확인되는 언어/API 의미를 프로젝트 convention 우선 원칙에 맞게 적용한다.

Audit baseline: Java SE / JDK 26 documentation, 2026-09-11.

> 이 baseline은 신규 프로젝트의 Java version을 26으로 강제하지 않는다. 실제 구현에서는 대상 프로젝트의 target Java version과 framework/toolchain 호환성을 먼저 확인한다.

## 공식 근거

- Oracle Java Language Changes Summary: https://docs.oracle.com/en/java/javase/26/language/java-language-changes-summary.html
- Oracle Record Classes: https://docs.oracle.com/en/java/javase/26/language/records.html
- Oracle Sealed Classes: https://docs.oracle.com/en/java/javase/26/language/sealed-classes-interfaces.html
- Oracle Pattern Matching: https://docs.oracle.com/en/java/javase/26/language/pattern-matching.html
- Oracle Pattern Matching with switch: https://docs.oracle.com/en/java/javase/26/language/pattern-matching-switch.html
- Oracle Record Patterns: https://docs.oracle.com/en/java/javase/26/language/record-patterns.html
- Oracle Optional API: https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/Optional.html
- Oracle Unmodifiable Collections: https://docs.oracle.com/en/java/javase/26/core/creating-immutable-lists-sets-and-maps.html
- Oracle Virtual Threads: https://docs.oracle.com/en/java/javase/26/core/virtual-threads.html
- OpenJDK JEP 444 Virtual Threads: https://openjdk.org/jeps/444

## Language Feature Stability

기본 정책:

```text
Stable + target Java에서 지원
→ 프로젝트 convention과 가독성에 맞으면 사용 가능

Preview / Incubator
→ 기존 프로젝트가 이미 명시적으로 enable한 경우가 아니면 신규 도입 금지
→ `--enable-preview` 또는 incubator module을 Task 범위 밖에서 추가하지 않는다

최신 JDK에서만 지원
→ target Java를 올려서 사용하지 않는다
```

Java 26 공식 문서에도 primitive types in patterns/switch 같은 기능은 Preview로 남아 있다. 최신 문서에 존재한다는 이유만으로 production 기본 문법으로 취급하지 않는다.

대표 Stable 도입 시점:

```text
Java 10  local variable type inference (`var`)
Java 14  switch expressions
Java 15  text blocks
Java 16  record classes / pattern matching for instanceof
Java 17  sealed classes
Java 21  pattern matching for switch / record patterns / virtual threads
```

## `var`

`var`는 타입을 숨기기 위한 문법이 아니라 local variable type inference다.

권장:
- 우변만으로 타입과 의미가 명확하고 중복 타입 표기를 줄일 때 사용한다.
- generic factory/긴 타입처럼 명시 타입이 오히려 읽기 어려운 local variable에서 검토한다.

피함:
- method call 결과의 의미/타입이 이름만으로 불명확한 경우.
- primitive/boxed/numeric conversion 차이를 숨기는 경우.
- public field, parameter, return type을 `var`처럼 추론형 계약으로 바꾸려는 시도.

## Record

Oracle은 record를 plain data aggregate를 간결하게 모델링하는 특수 class로 설명한다. record component는 final이며 accessor, canonical constructor, equals/hashCode/toString이 자동 생성된다.

기본 후보:
- immutable request/response DTO
- command/query/result carrier
- 독립적인 immutable tuple/data aggregate

자동 적용하지 않음:
- JPA Entity / persistence identity object
- framework가 no-arg constructor/proxy/subclassing/mutable property를 요구하는 타입
- identity 기반 equals/hashCode 의미가 필요한 domain entity
- serialization/API contract를 깨뜨릴 수 있는 기존 public class

기존 class를 record로 바꾸는 것은 style-only refactor가 아니라 constructor/accessor/equality/serialization compatibility 변경 가능성이 있는 작업으로 본다.

## Sealed Class / Interface

Oracle/JLS는 sealed hierarchy를 도메인의 가능한 종류를 닫힌 집합으로 모델링하는 용도로 설명한다.

검토 대상:
- 고정된 domain result/error/state/type family
- permitted subtype 전체를 compile time에 관리할 의미가 있는 hierarchy
- exhaustive `switch`와 결합해 누락 case를 줄일 수 있는 경우

피함:
- extension point/plugin SPI처럼 외부 확장이 필요한 hierarchy
- 단순 code reuse 목적으로 hierarchy를 닫는 경우
- framework proxy/subclass 요구와 충돌하는 타입

## Pattern Matching / Switch

지원 Java version에서 Stable인 pattern matching을 사용하면 명시적 cast와 중복 type check를 줄일 수 있다.

권장:
- `instanceof Type value`로 바로 narrowing 가능한 경우
- sealed hierarchy의 exhaustive `switch`
- record pattern으로 구조 분해가 실제 로직을 더 명확하게 만드는 경우

피함:
- 기존 단순 분기가 더 읽기 쉬운데 최신 문법 시연을 위해 변경
- 긴 guarded switch에 business logic을 몰아넣어 method 책임이 커지는 경우
- Preview pattern 기능을 production 기본으로 도입

## Optional

Oracle Optional API Note 기준으로 `Optional`은 주로 "결과 없음"을 명확히 표현하는 **method return type** 용도다.

기본 규칙:
- 조회/계산 결과 부재가 정상적인 결과일 때 return type 후보.
- `Optional` 변수 자체는 `null`이면 안 된다.
- `Optional.get()`보다 의도가 드러나는 `orElseThrow`, `map`, `flatMap`, `ifPresent` 등을 우선 검토한다.

자동 사용하지 않음:
- 모든 nullable field/parameter를 `Optional`로 변환
- JPA Entity field / DTO field / serialization contract를 근거 없이 Optional로 변경
- `Optional<List<T>>`처럼 empty collection만으로 충분히 부재 의미를 표현할 수 있는데 중복 wrapping
- `isPresent()` + `get()`을 단순 null-check 대체 패턴으로 반복

## Collection Mutability / Defensive Copy

외부에 변경 권한을 주지 않아야 하는 collection은 target Java에서 가능한 경우 `List.copyOf`, `Set.copyOf`, `Map.copyOf` 등 unmodifiable snapshot을 검토한다.

주의:
- unmodifiable collection과 immutable object graph는 같은 개념이 아니다. element가 mutable하면 collection 내부 상태가 관찰상 바뀔 수 있다.
- `Collections.unmodifiableList` 계열은 backing collection의 read-only view이므로 backing collection 변경이 보인다.
- 변경이 빈번한 내부 working collection까지 모두 immutable copy로 만들지 않는다.
- defensive copy 비용과 ownership/lifecycle을 고려한다.

기본 판단:

```text
외부에 snapshot 전달 / 내부 collection mutation 노출 금지
→ copyOf 계열 검토

동일 backing state의 live read-only view가 의도
→ unmodifiable view 검토

내부에서 계속 변경되는 working set
→ modifiable collection 유지
```

## Stream / Loop

Stream API는 collection pipeline을 명확하게 표현할 때 사용한다. `for` loop보다 무조건 우월한 것으로 취급하지 않는다.

- map/filter/reduce 성격의 side-effect 없는 변환은 Stream 후보.
- 복잡한 branching, checked exception, stateful mutation이 많아 pipeline 가독성이 떨어지면 명시적 loop를 유지한다.
- Stream 내부에서 DB/API/File/Network I/O를 숨겨 반복 I/O/N+1을 만들지 않는다.
- `parallelStream()`은 CPU/ordering/thread-safety/workload 근거 없이 사용하지 않는다.

## Exception

- catch 후 무시하거나 로그만 남기고 정상 성공처럼 진행하지 않는다.
- 광범위한 `catch (Exception)`은 boundary/fallback 등 구체적 이유가 있을 때만 사용한다.
- 원인 exception을 변환할 때 cause를 보존한다.
- checked/unchecked 선택은 기존 project/framework contract를 우선하며 전역 변환하지 않는다.
- 예외를 일반 control flow로 남용하지 않는다.

## Virtual Threads

Virtual threads는 Java 21에서 final된 기능이며 Oracle/OpenJDK는 **높은 동시성의 blocking I/O workload에서 throughput 확장**을 위한 기능으로 설명한다. 더 빠른 thread가 아니며 latency 개선 기능도 아니다.

검토 조건:
- target Java >= 21
- 많은 동시 task가 대부분 blocking I/O 대기
- framework/application runtime이 virtual thread 사용을 명시적으로 지원하거나 적용 범위가 통제됨
- thread-local, pooling, synchronization, monitoring 영향 검토 완료

금지/주의:
- CPU-bound 작업을 빠르게 만들 목적으로 도입
- virtual thread를 다시 작은 fixed pool로 제한해 장점을 상쇄
- 기존 Executor/transaction/security context 의미를 검토하지 않고 executor만 교체
- framework runtime 설정 변경을 unrelated task에서 자동 적용

application-level fan-out에서 직접 `Executors.newVirtualThreadPerTaskExecutor()`를 사용할 필요가 있다면 lifecycle을 명시하고 가능하면 try-with-resources로 종료/대기를 관리한다.

## Immutability / API Boundary

- mutable state가 필요하지 않으면 `final` field/local reference를 우선 검토한다.
- public API에서 mutable collection/array를 그대로 노출하지 않도록 ownership을 확인한다.
- immutable data carrier와 mutable domain entity를 같은 규칙으로 취급하지 않는다.
- defensive copy는 실제 mutation/ownership 위험이 있을 때 적용하며, 성능 비용 없는 스타일 규칙으로 취급하지 않는다.

## Review Hotspots

Reviewer는 Java diff에서 다음을 우선 확인한다.

```text
unsupported/Preview language feature
record ↔ Entity/framework compatibility
sealed hierarchy의 의도치 않은 extension 차단
Optional field/parameter 남용 또는 Optional 자체 null
Optional.get() 반복
mutable collection/array 노출
Stream에서 반복 I/O/N+1
근거 없는 parallelStream
catch Exception / swallowed exception
virtual thread의 CPU-bound 오용 또는 runtime context 영향
unrelated Java/framework/toolchain upgrade
```
