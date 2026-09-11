---
name: dev-api-docs
description: Framework에 종속되지 않은 API 문서화 skill로 승인 Markdown API Specification과 실제 Application Source를 대조해 OpenAPI/Swagger와 Postman Collection을 생성·갱신한다.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, api, docs, openapi, swagger, postman, springdoc, spec]
    related_skills: [dev-api-spec, dev-api-contract, dev-spring-guidelines, dev-spring-feature]
    requires_tools: [terminal, skill_view]
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

## API Spec 연동

먼저 Task의 `API Spec Mode`, `API Spec Status`, `API Spec Path`를 확인한다.

### DESIGN_FIRST

`API Spec Status: APPROVED`이면 다음 순서를 사용한다.

```text
APPROVED Markdown API Specification
↕ contract check
Application Source
→ OpenAPI / Postman
```

승인 Markdown과 source가 다르면 현재 source 기준으로 문서를 조용히 생성하지 않는다.

```text
API_SPEC_MISMATCH
```

를 보고하고 Requirement Delta + API Spec 재승인 대상으로 올린다.

### SOURCE_SYNC

기존 API 역문서화에서는 Application Source가 descriptive 문서의 기준이다.

```text
Application Source
→ Markdown DRAFT
  Documentation Source: APPLICATION_SOURCE
→ OpenAPI / Postman
```

SOURCE_SYNC Markdown DRAFT를 자동 APPROVED로 승격하지 않는다.

### AUDIT

AUDIT Task에서는 기본적으로 artifact를 수정하지 않고 Source ↔ Markdown ↔ OpenAPI/Postman 차이를 보고한다.

## Reference Loading

문서 구현 전에 필요한 reference만 선택적으로 읽는다.

```text
Spring + OpenAPI/SpringDoc
→ skill_view("dev-api-docs", "references/spring-openapi-reference.md")

Postman
→ skill_view("dev-api-docs", "references/postman-reference.md")

BOTH
→ 두 reference 모두 로드
```

Reference는 외부 GitHub 저장소를 매번 조회하기 위한 것이 아니라, 합의된 패턴을 로컬에 고정해 반복 사용량과 네트워크 의존성을 줄이기 위한 것이다.

## 공통 실행 순서

1. API Spec Mode/Status/Path를 확인한다.
2. APPROVED Markdown API Specification이 있으면 먼저 읽는다.
3. 실제 Controller/route/request/response/error/auth contract를 source에서 확인한다.
4. Markdown과 source가 normative contract 기준으로 일치하는지 확인한다.
5. 기존 API 문서 artifact와 grouping/naming/environment 구조를 확인한다.
6. 필요한 local reference를 로드한다.
7. OpenAPI/Postman이 승인 Spec과 실제 source contract 모두에 맞도록 생성/수정한다.
8. 프로젝트의 공통 응답 규격과 공통 Error contract를 문서 Schema/Example에 반영한다.
9. 문서 때문에 production API contract를 임의 변경하지 않는다.
10. 가능한 schema/collection validation과 compile/test를 수행한다.

## Spring OpenAPI Reference

Spring/Spring Boot + SpringDoc에서는 `references/spring-openapi-reference.md`를 기본 reference로 사용한다.

해당 reference의 origin은 다음 예시 프로젝트다.

```text
Repository: kwang-sub/backend-lab-archive
Path: level-up-backend-gpt/level2-book-management-system
```

핵심 패턴:

```text
@Tag(name, description)
@Operation(summary, description)
API별 error code annotation
GroupedOpenApi 기반 API 그룹화
OperationCustomizer 기반 error response example 생성
실제 인증 방식에 맞는 SecurityScheme
```

예시의 `ResponseEntity<DTO>` 자체를 공통 응답 규격으로 간주하지 않는다. 대상 프로젝트에 공통 response wrapper가 있으면 그 wrapper의 schema를 우선한다.

### Spring OpenAPI 적용 규칙

- 기존 springdoc config/annotation/customizer가 있으면 재사용한다.
- Controller annotation 스타일과 API group naming은 프로젝트 기존 convention을 따른다.
- API별 예상 ErrorCode를 실제 throw/handler flow와 대조한다.
- APPROVED Markdown이 있으면 method/path/request/response/error/auth/nullability가 일치하는지 먼저 확인한다.
- request/response field description/example annotation은 기존 DTO 문서화 패턴을 따른다.
- 새 `SwaggerConfig`, custom annotation, dependency를 편의상 중복 생성하지 않는다.
- SpringDoc이 없는 프로젝트에 신규 dependency를 추가해야 하면 자동 추가하지 않는다.

## Postman

Postman 작업은 `references/postman-reference.md`를 사용한다.

Postman Collection은 실제 API contract와 동일하게 구성하고, APPROVED Markdown Spec이 있으면 그 의미 계약과도 일치해야 한다.

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

OpenAPI와 Postman을 동시에 만들 때 두 문서가 별도 source of truth로 divergence하지 않게 한다.

```text
APPROVED Markdown API Specification (있을 때)
              ↕
Application Source Contract
    ├─ OpenAPI
    └─ Postman
```

## Verification / Evidence

```text
Skill: dev-api-docs
Mode: OPENAPI | POSTMAN | BOTH
API Spec Mode / Status / Path
Framework / API documentation stack
References Loaded
Pattern References
Response/Error Contract Used
Artifacts Added / Updated
Validation / Compile / Tests
Contract Mismatches Found
API Spec Mismatch: true | false
Residual Risk
```
