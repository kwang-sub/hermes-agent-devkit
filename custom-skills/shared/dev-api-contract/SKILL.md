---
name: dev-api-contract
description: backend API DTO/response와 frontend type/client 사이의 method·path·payload·error·nullability 계약을 한 작업에서 일관되게 유지하고 contract drift를 검증하는 framework 독립 capability skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, api, contract, backend, frontend, integration, typescript]
    related_skills: [dev-api-docs, dev-spring-feature, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature]
    requires_tools: [terminal]
---

# dev-api-contract

Backend/Frontend 경계를 함께 변경할 때 사용하는 framework 독립 capability다.

## Source of Truth

먼저 프로젝트에서 실제 contract source를 찾는다.

가능한 형태:

```text
OpenAPI generated client/schema
Backend DTO + documented contract
shared schema/package
hand-written API client/types
기타 project-specific source
```

Skill이 임의로 OpenAPI나 code generation을 도입하지 않는다.

## 확인 항목

```text
HTTP method/path
path/query/header
request body
success status/body
common response wrapper
error status/code/body
field naming
required/optional/nullability
date/time format
money/decimal representation
enum/code value
paging/sorting contract
auth requirement
```

Backend와 Frontend에 같은 의미의 필드를 서로 다른 이름/nullable semantics로 조용히 만들지 않는다.

## 변경 순서

1. 기존 contract와 closest API reference를 확인한다.
2. 요구사항에서 contract 변화가 실제 필요한지 확정한다.
3. source-of-truth artifact를 먼저 또는 함께 수정한다.
4. backend implementation과 frontend type/client를 일치시킨다.
5. serialization/deserialization과 오류 경로를 검증한다.
6. OpenAPI/Postman 산출물이 필요하면 `dev-api-docs`를 추가 적용한다.

## 금지

- TypeScript `as`로 backend mismatch 숨기기
- UI 내부 ad-hoc mapping으로 공통 contract drift 숨기기
- 문서 생성을 이유로 API 의미 변경
- float precision이 위험한 money/decimal contract를 근거 없이 변경
- API contract 변경을 LOW risk로 자동 self-complete

## Verification / Handoff

```text
Contract Source
Backend Contract
Frontend Contract
Intentional Deviations
Serialization/Error verification
Affected tests
Residual compatibility risk
```
