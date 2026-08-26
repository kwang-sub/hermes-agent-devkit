---
name: dev-spring-refactor
description: Spring 구현 완료 후 변경 범위에서 드러난 책임 혼재, orchestration/detail 결합, 문서화 부족을 점검하고 기존 프로젝트 패턴 안에서 behavior-preserving task-coupled refactoring을 수행한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, spring, refactor, structural-quality, orchestration, javadoc, comments]
    related_skills: [dev-implement-plan, dev-code-review, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test]
    requires_tools: [terminal]
---

# dev-spring-refactor

Spring/Spring Boot 작업의 **Post-Implementation Structural Quality Gate**다. 기능을 새로 설계하는 스킬이 아니라, 이미 구현한 Task 범위에서 드러난 구조적 복잡성과 설명 부족을 기존 프로젝트 convention 안에서 정리한다.

## 목표

상위 Service/Application 코드는 가능한 한 업무 흐름을 읽을 수 있는 orchestration 형태를 유지하고, parsing/validation/mapping/query/file/network/persistence 세부 책임은 프로젝트의 기존 패턴에 맞는 타입이나 컴포넌트로 분리한다.

```text
Use-case / Service
  -> 업무 흐름과 transaction/orchestration
  -> 세부 처리 책임은 명확한 메서드/DTO/Resolver/Mapper/Helper/Component로 위임
```

클래스 수 증가 자체를 목표로 하지 않는다. 파일 길이, 메서드 수, private 메서드 수만으로 분리하지 않는다.

## 적용 시점

Coder가 Task의 기능 구현을 끝낸 뒤 최종 verification 전에 수행한다.

- Standard Flow의 Spring source 변경: Structural Quality Check를 항상 수행한다.
- Fast Flow: 변경이 작고 국소적이면 check만 수행하고, trigger가 확인될 때만 refactor한다.
- `CHANGES_REQUESTED` 재작업: Reviewer가 구조 finding을 준 경우 해당 finding 범위에서 수행한다.

## Refactor Trigger

다음 중 하나 이상이 **이번 Task 변경으로 새로 생겼거나 명확히 드러난 경우** refactor 후보로 본다.

- 한 Service 메서드가 validation + mapping + persistence + external/file I/O 중 3개 이상을 직접 수행한다.
- raw `Map<String, Object>` 또는 generic payload parsing이 핵심 use-case orchestration과 섞여 있다.
- 동일 클래스의 private method들이 parsing, lookup, gateway/file I/O, persistence/state update처럼 서로 다른 책임 cluster로 명확히 나뉜다.
- 반복되는 config id/key/type mapping 또는 변환 규칙이 use-case 코드에 흩어져 있다.
- Repository/Gateway/File I/O와 상태 저장이 하나의 긴 제어 흐름에 결합되어 있다.
- 동일한 DTO/result builder 조립이나 null/error 처리 패턴이 반복된다.
- 새 기능을 이해하려면 구현 세부를 끝까지 따라가야 하고 상위 메서드만으로 업무 단계가 읽히지 않는다.

다음은 단독 trigger가 아니다.

- 파일이 길다.
- private 메서드가 많다.
- 메서드가 20/30/50줄을 넘는다.
- 클래스를 더 작게 만들 수 있다.

## Refactor 방향

프로젝트에 이미 존재하는 패턴을 우선한다. 적절한 경계가 확인될 때만 다음을 사용한다.

```text
DTO / Value Object
Resolver
Mapper / Converter
Parser / Validator
Index / Context / Result object
Gateway adapter
Focused helper/component
private orchestration method
```

상위 Service는 가능하면 다음처럼 단계가 드러나도록 만든다.

```java
public SaveResult save(Request request) {
  ValidatedRequest validated = validateRequest(request);
  ApplyContext context = prepareContext(validated);
  List<ApplyResult> results = applyToNodes(context);
  persistResults(results);
  return summarize(results);
}
```

하지만 대상 프로젝트가 다른 구조를 명확히 사용하면 그 패턴을 유지한다.

## Javadoc / Comment Quality Gate

구조 리팩터링 후 코드는 **왜 존재하고 어떤 계약을 가지는지** 읽을 수 있어야 한다. 프로젝트의 기존 주석/Javadoc 스타일을 먼저 확인하고 동일한 톤과 밀도로 맞춘다.

### Javadoc 기본 원칙

다음 대상은 동작이 자명하지 않거나 업무 의미가 있는 경우 Javadoc을 작성/보강한다.

- public/protected API
- package-visible 메서드 중 테스트 또는 협업 계약으로 사용되는 메서드
- 주요 orchestration 메서드
- 복잡한 Resolver/Mapper/Context/Result 타입
- retry/idempotency/transaction/file migration처럼 운영 의미가 중요한 처리

Javadoc에는 필요한 경우 다음을 포함한다.

```text
무엇을 수행하는지
중요한 전제/경계
실패 또는 retry 의미
@param의 업무 의미
@return의 의미
@throws가 실제 contract인 경우
```

구현 코드를 그대로 한국어로 번역하는 주석은 만들지 않는다.

좋은 예:

```java
/**
 * 성공한 history mapping을 기준으로 이미지 owner를 재조회하고 파일 이관을 수행한다.
 * 이미지 실패는 mapping을 롤백하지 않으며 다음 실행에서 재시도한다.
 *
 * @param migratedHistories 성공 또는 재사용된 history mapping
 */
private void migrateImages(List<MigratedHistoryData> migratedHistories) {
  ...
}
```

피해야 할 예:

```java
/** 이미지를 마이그레이션한다. */
private void migrateImages(...) { ... }
```

### 메서드 흐름 주석

한 메서드 안에 서로 다른 업무 단계가 연속되고 코드만으로 경계가 즉시 보이지 않을 때 단계 주석을 허용한다.

```java
// 1. source 데이터를 bulk 조회해 이번 batch 입력을 고정한다.
...
// 2. history/size 저장을 건별 transaction으로 확정한다.
...
// 3. transaction 밖에서 파일/이미지 후처리를 수행한다.
...
```

적용 원칙:

- 2~5개의 의미 있는 단계에만 사용한다.
- `if 확인`, `리스트 생성`, `repository 호출`처럼 코드 자체가 설명하는 내용에는 붙이지 않는다.
- 번호는 실제 처리 순서가 중요한 orchestration에만 사용한다.
- 추출 메서드 이름만으로 충분히 읽히면 단계 주석을 줄인다.
- 주석이 코드 변경과 쉽게 불일치할 구조라면 메서드 추출/이름 개선을 우선한다.

### 주석과 리팩터링 우선순위

```text
좋은 이름/타입/메서드 추출
  > 필요한 Javadoc
  > 필요한 흐름 주석
  > 설명용 inline comment
```

주석으로 나쁜 구조를 덮지 않는다.

## 자동 적용 범위

다음 조건을 모두 만족하면 Coder가 같은 Task 안에서 자동 refactor한다.

- 현재 Task 변경과 직접 연관된다.
- behavior/API/schema를 바꾸지 않는다.
- 새 dependency/framework가 필요 없다.
- 기존 프로젝트 패턴으로 근거를 제시할 수 있다.
- targeted test로 기존 behavior를 증명할 수 있다.

이 조건에서 수행한 정리는 `unrelated refactor`가 아니라 **task-coupled refactoring**이다.

## 자동 적용 금지 / Escalation

다음이 필요하면 임의 적용하지 않는다.

- public API/schema 변경
- DB schema/entity relation 변경
- 새 dependency/framework/library 도입
- transaction boundary 의미 변경
- security/concurrency 정책 변경
- package/module architecture 재설계
- 대규모 공통 abstraction 신설
- 사용자의 기존 코드 스타일과 다른 새로운 표준 강제

Standard Flow에서는 Reviewer에게 구조 대안을 evidence로 넘긴다. Fast Flow에서 범위가 커지면 `FAST_FLOW_ESCALATION_REQUIRED`로 전환한다.

## Structural Quality Check 결과

Coder는 최종 evidence에 다음을 남긴다.

```text
Structural Quality Check: PASS | REFACTORED | ESCALATED
Refactor Triggers: none | <observed triggers>
Refactor Scope: <changed classes/types>
Javadoc/Comment Review: PASS | UPDATED
Behavior Preserved By: <tests/verification>
Intentional Non-Refactors: <reason>
```

## 불변식

- behavior-preserving이 아닌 변경을 refactor라는 이름으로 섞지 않는다.
- 사용자가 합의하지 않은 architecture 개선을 임의 적용하지 않는다.
- 기존 프로젝트와 다른 naming/package/layer 규칙을 새로 만들지 않는다.
- 테스트를 통과시키기 위해 production behavior를 약화하지 않는다.
- 주석/Javadoc을 줄 수 맞추기 용도로 추가하지 않는다.
- 자명한 코드에 설명 주석을 반복하지 않는다.
