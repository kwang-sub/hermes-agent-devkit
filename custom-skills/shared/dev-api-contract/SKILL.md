---
name: dev-api-contract
description: 승인된 Markdown API Specification 또는 기존 Application Source를 기준으로 backend API DTO/response와 frontend type/client 사이의 method·path·payload·error·nullability 계약을 일관되게 유지하고 drift를 검증하는 framework 독립 capability skill.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, api, contract, backend, frontend, integration, typescript, spec]
    related_skills: [dev-api-spec, dev-api-docs, dev-spring-feature, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature]
    requires_tools: [terminal, skill_view]
---

# dev-api-contract

Backend/Frontend 경계를 함께 변경할 때 사용하는 framework 독립 capability다. `dev-api-spec`의 Mode와 승인 상태를 먼저 확인하고 contract source 우선순위를 정한다.

## Source of Truth

### DESIGN_FIRST

`API Spec Status: APPROVED`인 Markdown이 있으면 최우선 normative contract다.

```text
APPROVED Markdown API Specification
→ OpenAPI/shared schema (프로젝트가 이미 canonical로 사용하는 경우)
→ Backend DTO / Controller
→ Frontend API client / types
```

Application Source나 Frontend가 승인 Markdown과 다르면 문서를 source에 맞춰 조용히 바꾸지 않는다.

```text
API_SPEC_MISMATCH
```

으로 보고하고, 의미 있는 계약 변경이 필요하면 Requirement Delta + API Spec 재승인 대상으로 올린다.

### SOURCE_SYNC

기존 API의 역문서화에서는 현재 Application Source가 descriptive Markdown DRAFT의 기준이다.

```text
Application Source
→ Markdown DRAFT (Documentation Source: APPLICATION_SOURCE)
→ OpenAPI/Postman
```

SOURCE_SYNC 결과를 자동 `APPROVED`로 승격하지 않는다.

### Spec 없음

승인 Markdown이 없고 SOURCE_SYNC도 아닌 기존 프로젝트에서는 실제 contract source를 찾는다.

가능한 형태:

```text
OpenAPI generated client/schema
Backend DTO + documented contract
shared schema/package
hand-written API client/types
기타 project-specific source
```

Skill이 임의로 OpenAPI나 code generation을 도입하지 않는다.

## Audit 분류

`dev-api-spec` AUDIT/SOURCE_SYNC 결과가 있으면 다음 분류를 그대로 사용한다.

```text
IN_SYNC
SOURCE_ONLY
SPEC_ONLY
CONTRACT_MISMATCH
```

- `SOURCE_ONLY`: 실제 API는 있으나 Markdown Spec이 없다. 변경 Task 범위 안이면 `dev-api-spec SOURCE_SYNC`로 DRAFT 문서화를 포함한다.
- `SPEC_ONLY`: 문서에는 있으나 실제 endpoint를 확인할 수 없다. 삭제로 단정하지 않고 compatibility 위험으로 보고한다.
- `CONTRACT_MISMATCH`: 어느 쪽을 바꿀지 임의 결정하지 않는다.

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
date/time/timezone format
money/decimal representation
enum/code value
paging/sorting contract
auth/authz requirement
idempotency/compatibility note (해당 시)
```

Backend와 Frontend에 같은 의미의 필드를 서로 다른 이름/nullable semantics로 조용히 만들지 않는다.

## 변경 순서

1. Task의 `API Spec Mode`, `API Spec Status`, `API Spec Path`를 확인한다.
2. DESIGN_FIRST면 APPROVED Markdown을 먼저 읽고 구현 contract를 고정한다.
3. SOURCE_SYNC면 실제 Controller/route/DTO/error/auth를 bounded read해 현재 contract를 확정한다.
4. backend implementation과 frontend type/client를 같은 의미 계약으로 맞춘다.
5. serialization/deserialization과 오류 경로를 검증한다.
6. SOURCE_ONLY 문서화가 Task에 포함되면 `dev-api-spec`으로 Markdown DRAFT를 생성한다.
7. OpenAPI/Postman 산출물이 필요하면 `dev-api-docs`를 추가 적용한다.

## 금지

- TypeScript `as`로 backend mismatch 숨기기
- UI 내부 ad-hoc mapping으로 공통 contract drift 숨기기
- APPROVED Markdown을 실제 source에 맞춰 자동 덮어쓰기
- 문서 생성을 이유로 API 의미 변경
- float precision이 위험한 money/decimal contract를 근거 없이 변경
- API contract 변경을 LOW risk로 자동 self-complete

## Verification / Handoff

```text
API Spec Mode / Status / Path
Contract Source
Backend Contract
Frontend Contract
Audit Result: IN_SYNC | SOURCE_ONLY | SPEC_ONLY | CONTRACT_MISMATCH
API Spec Mismatch: true | false
Intentional Deviations
Serialization/Error verification
Affected tests
Residual compatibility risk
```
