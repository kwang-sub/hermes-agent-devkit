---
name: dev-spring-guidelines
description: Spring/Spring Boot 구현에서 대상 프로젝트 convention을 최우선으로 유지하고 공통 응답 규격, 계층 책임, transaction 등 합의된 Spring 공통 규칙을 적용한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, spring, spring-boot, guidelines, convention]
    related_skills: [dev-implement-plan, dev-spring-feature, dev-spring-data, dev-spring-test, dev-api-docs]
    requires_tools: [terminal]
---

# dev-spring-guidelines

Spring/Spring Boot 작업에 항상 추가 적용하는 공통 규칙이다. 프로젝트 자체 convention을 대체하지 않고 확장한다.

## 우선순위

```text
사용자/Task 명시 정책
→ 대상 프로젝트의 기존 convention
→ 이 Skill의 합의 규칙
→ 일반 Spring best practice
```

상세 프로젝트 패턴 원칙은 `/opt/data/shared/references/project-pattern-rules.md`를 따른다.

## 작업 전 확인

- Spring Boot/Spring Framework version
- Java/Kotlin 및 build tool
- 현재 package/layer 구조
- 유사 Controller/Service/DTO/Exception 구현
- 공통 Response/Error contract
- validation/transaction convention
- 이미 사용 중인 mapper/library/helper

## 공통 응답 규격

API 응답은 프로젝트에 이미 존재하는 공통 응답 규격을 사용한다.

예:

```text
ApiResponse<T>
CommonResponse<T>
BaseResponse<T>
기타 프로젝트 고유 wrapper
```

- 이름이나 구조를 Skill에서 고정하지 않는다.
- 동일 module/API에서 실제 사용 중인 공통 response wrapper를 찾아 재사용한다.
- 프로젝트에 공통 응답 규격이 없으면 기존 API contract를 임의로 wrapper로 교체하지 않는다.
- 사용자가 공통 응답 규격 도입을 요구했지만 기존 규격이 없으면 public API contract 변경으로 보고 Standard Flow에서 구조를 결정한다.
- 성공/실패 응답의 code/message/data/meta/page 형식도 기존 convention을 따른다.

## 계층 책임

Controller/Service/DTO/Exception의 세부 형태는 기존 프로젝트를 우선한다. 새 코드에서는 다음 방향을 기본 검토한다.

```text
Controller: HTTP 입력/검증/Service 호출/응답 contract
Service/Application: transaction + use case orchestration
Domain/Entity: 해당 객체에 자연스럽게 귀속되는 domain behavior
Repository/Data: persistence/query
```

단, 기존 프로젝트가 다른 architecture를 명확히 사용하면 그 구조를 유지한다.

## Transaction

- 기존 `@Transactional` 위치와 readOnly convention을 먼저 확인한다.
- 조회 작업은 프로젝트가 readOnly transaction을 사용하면 동일하게 적용한다.
- transaction boundary를 임의로 넓히거나 줄이지 않는다.
- 외부 API/File/Network 호출을 transaction 안에 새로 포함해야 하면 위험을 검토한다.

## 변경 통제

다음은 요구 범위 밖에서 자동 적용하지 않는다.

```text
architecture 변경
공통 response/error 재설계
새 mapper/library 도입
package 재구성
대규모 annotation/naming 정리
framework/dependency upgrade
```

개선이 필요하면 이유와 대안을 handoff에 남긴다.

## Verification / Evidence

Coder handoff에 다음을 남긴다.

```text
Skill: dev-spring-guidelines
Detected Spring/Boot version
Pattern References
Response Contract Used
Transaction Convention Used
Intentional Deviations
Verification
```
