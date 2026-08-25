---
name: dev-api-docs
description: Framework에 종속되지 않은 API 문서화 skill로 OpenAPI/Swagger와 Postman Collection을 생성·갱신하며 Spring에서는 합의된 SpringDoc 예시 규격과 프로젝트 공통 응답 규격을 함께 반영한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, api, docs, openapi, swagger, postman, springdoc]
    related_skills: [dev-spring-guidelines, dev-spring-feature]
    requires_tools: [terminal]
---

# dev-api-docs

API 문서화 전용 capability Skill이다. Spring 전용이 아니며 OpenAPI, Postman, 또는 둘 다를 지원한다.

## Mode

Task가 명확히 지정하면 그대로 사용한다.

```text
OPENAPI
POSTMAN
BOTH
```

지정이 없고 기존 프로젝트에 한 방식만 존재하면 기존 방식을 우선한다. 새 문서 체계나 dependency 도입이 필요한 경우 Standard Flow 결정사항으로 올린다.

## 공통 실행 순서

1. 실제 Controller/route/request/response/error/auth contract를 source에서 확인한다.
2. 기존 API 문서 artifact와 grouping/naming/environment 구조를 확인한다.
3. 문서가 source contract와 동일하도록 생성/수정한다.
4. 프로젝트의 공통 응답 규격과 공통 Error contract를 문서 Schema/Example에 반영한다.
5. 문서 때문에 production API contract를 임의 변경하지 않는다.
6. 가능한 schema/collection validation과 compile/test를 수행한다.

## Spring OpenAPI Reference

Spring/Spring Boot + SpringDoc에서는 기본 reference로 다음 예시 프로젝트의 구조를 사용한다.

```text
Repository: kwang-sub/backend-lab-archive
Path: level-up-backend-gpt/level2-book-management-system
```

참고할 핵심 패턴:

```text
@Tag(name, description)
@Operation(summary, description)
API별 error code annotation
GroupedOpenApi 기반 API 그룹화
OperationCustomizer 기반 error response example 생성
JWT bearer SecurityScheme가 필요한 경우 기존 auth convention과 함께 구성
```

예시의 `ResponseEntity<DTO>` 자체를 공통 응답 규격으로 간주하지 않는다. 대상 프로젝트에 공통 response wrapper가 있으면 그 wrapper의 schema를 우선한다.

### Spring OpenAPI 적용 규칙

- 기존 springdoc config/annotation/customizer가 있으면 재사용한다.
- Controller annotation 스타일과 API group naming은 프로젝트 기존 convention을 따른다.
- API별 예상 ErrorCode를 실제 throw/handler flow와 대조한다.
- request/response field description/example annotation은 기존 DTO 문서화 패턴을 따른다.
- 새 `SwaggerConfig`, custom annotation, dependency를 편의상 중복 생성하지 않는다.
- SpringDoc이 없는 프로젝트에 신규 dependency를 추가해야 하면 자동 추가하지 않는다.

## Postman

Postman Collection은 실제 API contract와 동일하게 구성한다.

권장 구조는 프로젝트 기존 grouping을 우선하고 없으면 API/domain 단위 folder를 사용한다.

```text
Collection
├─ Auth
├─ <Domain A>
│  ├─ Create
│  ├─ Get
│  └─ Update
└─ Environment variables
```

가능하면 다음 변수를 재사용 가능한 환경 값으로 둔다.

```text
baseUrl
accessToken / auth token
project-specific ids only when useful
```

각 request에는 필요에 따라 다음을 반영한다.

```text
HTTP method / path
query/path parameters
headers/auth
request body example
success response example
known error response examples
```

secret/token 실제 값을 collection에 기록하지 않는다.

## BOTH Mode

OpenAPI와 Postman을 동시에 만들 때 두 문서가 별도 source of truth로 divergence하지 않도록 실제 application source contract를 기준으로 각각 검증한다.

## Verification / Evidence

```text
Skill: dev-api-docs
Mode: OPENAPI | POSTMAN | BOTH
Framework / API documentation stack
Pattern References
Response/Error Contract Used
Artifacts Added / Updated
Validation / Compile / Tests
Contract Mismatches Found
Residual Risk
```
