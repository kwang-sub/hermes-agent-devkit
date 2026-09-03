---
name: dev-java-guidelines
description: Java 구현에서 대상 프로젝트의 Java 버전·빌드·Lombok·타입 배치·JavaDoc convention을 감지하고 기존 프로젝트 패턴을 우선해 적용하는 공통 capability skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, java, guidelines, convention, lombok, javadoc]
    related_skills: [dev-implement-plan, dev-project-pattern, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test]
    requires_tools: [terminal]
---

# dev-java-guidelines

Java 작업에 추가 적용하는 공통 규칙이다. `/opt/data/shared/references/coding-rules.md`의 언어 독립 규칙과 대상 프로젝트의 기존 convention을 반복하거나 대체하지 않는다.

## 우선순위

```text
사용자/Task 명시 정책
→ 대상 프로젝트의 기존 Java convention
→ 이 Skill의 Java 전용 규칙
→ 일반 Java 관례
```

## 작업 전 확인

- `.hermes/toolchain.env`, Gradle/Maven 설정과 실제 target Java version
- 기존 package/naming/type 배치 방식
- Lombok dependency와 기존 annotation 사용 여부
- record/class/interface/enum 및 nested type 사용 패턴
- JavaDoc 또는 프로젝트 documentation convention
- 직렬화/JPA/프레임워크가 생성자·접근자·reflection에 요구하는 제약

Java/JDK/Gradle/Maven을 task-time에 새로 설치하거나 버전을 임의 변경하지 않는다.

## Lombok

Lombok은 프로젝트가 이미 사용하고 있고 현재 코드 패턴과 호환될 때만 기존 convention을 따른다.

- Lombok이 없는 프로젝트에 편의를 이유로 dependency를 추가하지 않는다.
- 기존 코드가 `@Getter`, `@RequiredArgsConstructor`, `@Builder` 등을 일관되게 사용하면 같은 계층의 유사 코드에서 그 패턴을 우선한다.
- Entity/JPA model에서 `@Data`, 광범위한 `@EqualsAndHashCode`, 무분별한 `@ToString` 등은 기존 프로젝트 사용 여부와 persistence 특성을 먼저 확인한다.
- 명시적 constructor/getter가 프로젝트 convention이면 Lombok으로 임의 치환하지 않는다.

## Top-level / Nested Type

새 DTO, enum, record, helper type은 대상 프로젝트의 동일 역할 타입 배치를 먼저 따른다.

기본 판단:

```text
여러 클래스에서 사용되거나 독립적인 도메인/API 의미가 있음
→ top-level type 우선

한 클래스의 구현 세부사항이며 외부 재사용 의미가 없음
→ private/static nested type 검토
```

단순히 파일 수를 줄이기 위해 공개 DTO/record/enum을 nested type으로 몰아넣지 않는다. 반대로 한 메서드 내부 구현 세부 타입을 무조건 top-level로 승격하지 않는다.

Spring/Jackson/JPA/validation/schema generation 등 framework가 타입 가시성 또는 생성자 형태에 의존하면 해당 제약을 우선한다.

## Java 언어 기능과 호환성

- 프로젝트 target Java version에서 지원되는 문법/API만 사용한다.
- record, sealed class, pattern matching, Stream API 등 최신 문법을 사용하기 전에 target version과 기존 코드 채택 여부를 확인한다.
- 기존 프로젝트가 명확히 사용하지 않는 새 언어 스타일로 unrelated code를 함께 변환하지 않는다.
- public API/serialization/persistence 타입을 record나 다른 형태로 바꾸는 것은 단순 style refactor로 취급하지 않는다.

## JavaDoc / Documentation

공통 `coding-rules.md`의 documentation 원칙을 Java에서는 JavaDoc과 프로젝트 기존 방식으로 구체화한다.

- public/protected API와 비직관적인 주요 로직은 프로젝트가 JavaDoc을 사용하는 경우 동일 수준으로 작성한다.
- `@param`, `@return`, `@throws`는 의미 있는 계약 정보가 있을 때 사용하고 메서드 시그니처를 그대로 번역하지 않는다.
- 구현 이유, 호환성 제약, 입력/출력 계약처럼 코드만 보고 알기 어려운 내용을 우선 설명한다.

## Spring과의 관계

Java + Spring 작업에서는 이 Skill이 Java 언어/convention만 담당하고 Spring 계층·응답·transaction·JPA 규칙은 각각의 Spring capability가 담당한다.

```text
dev-java-guidelines
  → Java version / Lombok / type placement / JavaDoc

dev-spring-guidelines
  → Spring common convention / response / layer / transaction

dev-spring-data
  → JPA / Repository / QueryDSL / Converter
```

동일 규칙을 여러 Skill에 복제하지 않는다.

## Verification / Evidence

Java 변경 handoff에는 필요할 경우 다음을 남긴다.

```text
Skill: dev-java-guidelines
Detected Java version
Build tool
Lombok convention: existing | absent | not-applicable
Type placement convention
Documentation convention
Intentional deviations
Verification
```
