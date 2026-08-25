# Stack / Capability Skill Extension Guide

이 문서는 `shared/references/coding-rules.md`를 기반으로 특정 언어, 프레임워크, 기술 기능을 구현하는 전문 Skill을 추가할 때의 설계 규칙이다.

목표는 공통 코딩 규칙을 중복하지 않고 다음 구조로 확장하는 것이다.

```text
Common Coding Rules
        ↓
Workflow Skill
(dev-fast-flow / dev-implement-plan / dev-code-review)
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
```

### Workflow Skill

작업 lifecycle을 담당한다.

```text
dev-fast-flow
dev-implement-plan
dev-code-review
dev-review-cycle
```

Workflow Skill은 특정 프레임워크 기능을 직접 구현하지 않는다.

### Stack / Capability Skill

특정 기술과 구현 패턴을 담당한다.

예정 예:

```text
dev-spring-openapi
dev-spring-validation
dev-jpa-converter
```

필요하면 이후 다음처럼 확장할 수 있다.

```text
dev-spring-security
dev-spring-controller
dev-spring-service
dev-jpa-query
dev-jpa-entity
dev-spring-test
```

## 2. Java/Kotlin 분리 원칙

Spring 기능의 의미와 workflow가 동일하다면 Java/Kotlin을 별도 Skill로 만들지 않는다.

기본 구조:

```text
custom-skills/coder/dev-spring-validation/
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
2. 기존 동일 기능 검색
3. 기존 convention/implementation 결정
4. 사용자 요구와 기존 구현 비교
5. 필요한 경우 선택지 확인
6. 최소 변경 구현
7. stack-specific verification
8. coder → reviewer handoff evidence 기록
```

새 dependency나 framework를 기본값으로 추가하지 않는다.

이미 프로젝트가 같은 목적의 library 또는 설정을 사용한다면 기존 것을 우선 사용한다.

## 4. dev-spring-openapi 설계 방향

목적:

```text
Spring API 규격 및 개발용 API 문서 자동화
```

먼저 탐색:

```text
Spring Boot version
Java / Kotlin
springdoc-openapi 존재 여부
기존 Swagger/OpenAPI annotation
기존 Swagger UI 설정
Postman collection 존재 여부
Controller/Request/Response DTO convention
공통 Error Response
Security/Auth header convention
```

사용자 선택이 필요한 대표 항목:

```text
Swagger UI
Postman Collection
둘 다
```

가능한 경우 기존 dependency/config를 재사용한다.

산출물 예:

```text
OpenAPI metadata/config
Controller operation documentation
Request/Response schema
Error response documentation
Swagger UI configuration
Postman collection
```

검증 예:

```text
compile/test
OpenAPI JSON/YAML generation
Swagger UI endpoint 확인
Postman collection schema validation
실제 Controller contract와 문서 일치 확인
```

## 5. dev-spring-validation 설계 방향

목적:

```text
Spring Request validation을 프로젝트 기존 Bean Validation 패턴에 맞게 생성/적용
```

먼저 탐색:

```text
jakarta.validation / javax.validation 버전
기존 validation annotation
기존 custom ConstraintValidator
기존 validation message convention
Validation Group 사용 여부
Request DTO convention
Controller의 @Valid / @Validated 사용 방식
Global exception handler / error response
```

적용 우선순위:

```text
기존 표준 annotation으로 해결 가능
  → 기존 annotation 사용

기존 custom validator 재사용 가능
  → 재사용

새 domain value / Enum 정의가 요구됨
  → 기존 Enum/domain type 위치 확인 후 생성

새 validation rule이 필요하고 기존 validator 없음
  → custom annotation + validator 생성 검토
```

예상 작업:

```text
새 Enum 생성
Request DTO field type 적용
기존 Validator 재사용
필요 시 custom Constraint annotation 생성
ConstraintValidator 구현
Request DTO annotation 적용
validation failure test
```

새 custom validator는 단순히 한 번 쓰기 위한 과도한 abstraction이 되지 않도록 한다.

## 6. dev-jpa-converter 설계 방향

목적:

```text
JPA AttributeConverter를 생성하거나 기존 Converter를 재사용해 Entity mapping에 적용
```

먼저 탐색:

```text
JPA/Jakarta Persistence version
Java / Kotlin
기존 AttributeConverter
Converter package/naming convention
@Converter(autoApply = ...) 사용 방식
Entity field type
DB column type
null handling
legacy value compatibility
Enum/value object persistence convention
```

적용 순서:

```text
기존 Converter 존재
  → 재사용

동일 타입의 project-wide conversion
  → autoApply 여부를 기존 convention과 함께 검토

특정 field 전용 conversion
  → explicit @Convert 적용 우선 검토
```

검증 예:

```text
entity → DB value conversion
DB value → entity round-trip
null handling
legacy/unknown persisted value 처리
repository integration test
schema compatibility
```

## 7. Capability Skill과 Fast Flow

전문 Skill이라고 해서 반드시 Standard Flow를 요구하지 않는다.

예:

```text
기존 Validator를 Request DTO 한 필드에 적용
기존 Converter를 Entity 한 필드에 적용
기존 OpenAPI pattern으로 Controller 한 개 문서화
```

처럼 scope가 작고 선택/설계가 필요 없으면 Fast Flow에서도 사용할 수 있다.

반대로 다음은 Standard Flow 대상이다.

```text
OpenAPI 도구 자체 신규 도입
전체 API 문서 체계 변경
공통 Validation architecture 설계
다수 module에 걸친 Validator 체계 변경
새 persistence representation 설계
대규모 Converter migration
Dependency 추가/업그레이드가 필요한 작업
```

즉 Workflow 선택과 Capability Skill 선택은 서로 다른 축이다.

```text
Workflow = 작업 크기/모호성/승인 필요성
Capability Skill = 어떤 기술 작업을 수행하는가
```

## 8. Reviewer 확장 규칙

Capability Skill은 Reviewer가 확인할 수 있는 다음 정보를 남겨야 한다.

```text
Skill name
감지한 stack/version
재사용한 기존 pattern
새로 생성한 artifact
변경된 contract
실행한 verification
Residual risk
```

Reviewer는 공통 Coding Rules를 먼저 적용하고, Task에 사용된 Capability Skill의 Acceptance Criteria를 추가로 검증한다.

## 9. Naming 규칙

가능하면 다음 패턴을 사용한다.

```text
dev-<stack>-<capability>
```

예:

```text
dev-spring-openapi
dev-spring-validation
dev-jpa-converter
```

JPA처럼 stack 자체가 명확한 경우 `dev-jpa-*`를 허용한다.

언어 이름은 기능이 언어에 강하게 종속될 때만 포함한다.

```text
권장: dev-spring-validation
비권장 기본값: dev-java-spring-validation / dev-kotlin-spring-validation
```

## 10. Skill 추가 전 체크리스트

새 Skill을 만들기 전에 다음을 확인한다.

```text
[ ] 공통 coding-rules.md로 해결할 수 없는 전문 기능인가
[ ] 반복 사용할 수 있는 작업 패턴인가
[ ] 기존 Skill과 역할이 겹치지 않는가
[ ] project detection 절차가 정의됐는가
[ ] 기존 구현 재사용 우선순위가 정의됐는가
[ ] 사용자 선택이 필요한 항목이 정의됐는가
[ ] dependency 추가 정책이 정의됐는가
[ ] stack-specific verification이 정의됐는가
[ ] Reviewer가 확인할 evidence가 정의됐는가
[ ] Java/Kotlin을 정말 별도 Skill로 분리해야 하는지 검토했는가
```
