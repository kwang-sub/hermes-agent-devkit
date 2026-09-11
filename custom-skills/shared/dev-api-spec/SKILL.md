---
name: dev-api-spec
description: Markdown API Specification을 기준으로 신규 API를 설계하거나 기존 Application Source에서 누락 규격을 역문서화하고 Source·Spec·OpenAPI drift를 감사하는 framework 독립 capability skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, api, spec, markdown, design-first, source-sync, audit, legacy, contract]
    related_skills: [dev-api-contract, dev-api-docs, dev-breakdown, dev-workflow-orchestrate, dev-spring-feature, dev-frontend-feature]
    requires_tools: [terminal, skill_view]
---

# dev-api-spec

API 구현 전후의 **사람이 읽고 Git diff로 검토할 수 있는 Markdown 계약**을 관리한다. Framework에 종속되지 않으며 OpenAPI를 자동으로 source of truth로 승격하지 않는다.

기본 규격 위치는 프로젝트 기존 문서 구조를 우선하고, 기존 규칙이 없을 때만 `docs/api/README.md` + `docs/api/<domain>.md`를 사용한다.

## Mode

Task 목적에 따라 정확히 하나를 선택한다.

```text
DESIGN_FIRST
SOURCE_SYNC
AUDIT
```

### DESIGN_FIRST

신규 API 또는 기존 API의 의미 있는 contract 변경에 사용한다.

```text
Requirement / Use Case
→ Markdown API Spec DRAFT
→ [API 규격 승인]
→ APPROVED snapshot
→ Coder가 repository Markdown으로 materialize/update
→ Backend / Frontend 구현
→ dev-api-contract 검증
→ dev-api-docs OpenAPI/Postman 정렬
```

`DESIGN_FIRST`에서 승인 전 Spec은 구현 기준이 아니다. 승인된 Markdown Spec만 normative contract다.

### SOURCE_SYNC

기존 프로젝트의 실제 API는 존재하지만 Markdown/OpenAPI가 없거나 불완전할 때 사용한다. **현재 Application Source를 설명하는 역문서화 모드**다.

```text
Controller / Route
+ Request / Response DTO
+ Validation
+ Error / Exception Handler
+ Auth / Security
→ 현재 contract 추출
→ 기존 Markdown/OpenAPI와 비교
→ 누락 Markdown DRAFT 생성 또는 안전한 범위에서 갱신
```

순수 `SOURCE_SYNC`는 API 의미를 바꾸지 않으므로 별도 `[API 규격 승인]` Gate가 필요하지 않다. 승인된 Implementation Plan 안에서 바로 문서화할 수 있다.

자동 생성 결과는 반드시 다음처럼 descriptive 상태로 남긴다.

```text
Status: DRAFT
Documentation Source: APPLICATION_SOURCE
```

동작 중인 source라는 이유만으로 `APPROVED`로 자동 승격하지 않는다. 이후 Markdown을 normative contract로 채택하려면 별도의 API 규격 승인을 받는다.

### AUDIT

Source와 문서 상태를 변경하지 않고 차이만 조사한다.

```text
Application Source ↔ Markdown Spec ↔ OpenAPI/Postman
```

기본 결과 분류:

```text
IN_SYNC
SOURCE_ONLY
SPEC_ONLY
CONTRACT_MISMATCH
```

- `SOURCE_ONLY`: 실제 API 존재, Markdown Spec 없음.
- `SPEC_ONLY`: Markdown에는 있으나 실제 API를 확인할 수 없음.
- `CONTRACT_MISMATCH`: 양쪽 모두 있으나 method/path/payload/error 등 계약이 다름.
- `IN_SYNC`: 확인 범위에서 의미 계약이 일치함.

## Mode 선택 규칙

```text
신규 endpoint                         → DESIGN_FIRST
method/path/request/response/error 의미 변경 → DESIGN_FIRST
기존 endpoint 문서 누락 보완              → SOURCE_SYNC
기존 프로젝트 API 현황/차이 조사           → AUDIT
```

API를 건드리는 기존 프로젝트 Task에서 대상 endpoint가 `SOURCE_ONLY`로 확인되면, 요구사항 범위를 넘지 않는 한 같은 Task에 bounded `SOURCE_SYNC` 문서화를 포함할 수 있다.

단순 annotation/description 정리처럼 runtime contract를 바꾸지 않는 문서 보완을 `DESIGN_FIRST`로 과도하게 승격하지 않는다.

## Markdown Source of Truth

프로젝트 기존 convention이 없으면 다음 구조를 권장한다.

```text
docs/api/
├─ README.md
├─ account.md
├─ asset.md
├─ transaction.md
└─ <domain>.md
```

`README.md`에는 반복되는 공통 계약을 둔다.

```text
Base Path
Authentication / Authorization
Common Response Wrapper
Common Error
Pagination / Sorting
Date / Time / Timezone
Money / Decimal
Naming Convention
```

도메인 파일에는 endpoint별 계약을 둔다. 기본 template은 `references/api-spec-template.md`를 사용한다.

## Endpoint 필수 계약

Markdown Spec에는 해당되는 항목을 명시한다.

```text
Status: DRAFT | APPROVED | DEPRECATED
Documentation Source: DESIGN | APPLICATION_SOURCE | MIGRATED_SPEC
Use Case
HTTP Method / Path
Authentication / Authorization
Path / Query / Header
Request Body
Success Status / Response
Error Status / Error Code / Condition
Required / Optional / Nullable
Enum / Code
Money / Decimal
Date / Time / Timezone
Paging / Sorting
Idempotency
Compatibility / Migration note
```

프로젝트 공통 규칙으로 충분한 항목은 `docs/api/README.md`를 참조하고 endpoint마다 중복 복사하지 않는다.

## DESIGN_FIRST 승인 계약

Orchestrator는 source/config를 수정하지 않고 Markdown 형태의 Spec DRAFT를 사용자에게 먼저 보여준다.

계약 변경이 있는 경우:

```text
API_SPEC_MODE=DESIGN_FIRST
API_SPEC_GATE=REQUIRED
API_SPEC_STATUS=DRAFT
API_SPEC_PATH=<planned markdown path>
API_SPEC_SOURCE=DESIGN
```

사용자가 독립 `[API 규격 승인]` Gate에서 `규격 승인`을 선택한 뒤:

```text
API_SPEC_APPROVED=true
API_SPEC_STATUS=APPROVED
API_SPEC_SOURCE=approved-plan-snapshot
```

승인된 Spec 내용은 Implementation Plan/Kanban body에 보존한다. Coder는 production API를 변경하기 전에 승인 snapshot을 대상 Markdown 파일에 동일 의미로 materialize/update한다.

Spec Gate에서 필드/method/path/error 같은 계약 내용이 바뀌면 기존 API Spec 승인을 무효화하고 갱신된 Spec을 같은 Gate에서 다시 승인받는다.

## SOURCE_SYNC 역문서화 계약

먼저 실제 runtime contract를 bounded evidence로 확정한다.

우선 확인 대상:

```text
Controller / route declaration
Request DTO / binding
Response DTO / serialization
Validation
Exception / ErrorCode / Handler
Authentication / Authorization
closest tests
existing OpenAPI/Swagger annotation or schema
frontend client/type (Task 영향 범위일 때만)
```

Repository 전체를 자동으로 훑지 않는다.

```text
단일 API Task        → 해당 endpoint와 직접 DTO/error/auth만
도메인 문서화 Task     → 해당 도메인 Controller/route 범위
전체 API 감사 요청     → 명시적 AUDIT full scope
```

`SOURCE_ONLY` endpoint는 기본적으로 해당 도메인 Markdown에 DRAFT를 생성한다. 기존 Markdown이 있으면 새 파일을 난립시키지 않고 기존 domain grouping을 따른다.

Source에서 확정할 수 없는 설명, business intent, error condition은 추측하지 않고 `Unknown / Review Required`로 남긴다.

## Conflict 처리

### APPROVED Spec vs Application Source

`DESIGN_FIRST`에서 승인된 Markdown과 source가 다르면 source에 맞춰 Markdown을 조용히 덮어쓰지 않는다.

```text
API_SPEC_MISMATCH
Spec: <approved contract>
Implementation: <observed contract>
```

구현 중 새로운 계약 변경이 필요하면 Requirement Delta + API Spec 재승인 대상으로 올린다.

### SOURCE_SYNC DRAFT vs Application Source

`Documentation Source: APPLICATION_SOURCE`인 DRAFT는 descriptive 문서이므로 Application Source가 우선한다. 문서는 source와 동일하게 갱신할 수 있지만 `APPROVED`로 자동 변경하지 않는다.

### OpenAPI와 불일치

OpenAPI가 존재해도 자동으로 어느 쪽이 정답이라고 가정하지 않는다.

```text
APPROVED Markdown 존재 → Markdown과 source를 먼저 대조
SOURCE_SYNC DRAFT       → Application Source 우선
승인 상태 불명확         → CONTRACT_MISMATCH로 보고
```

## dev-api-contract 연결

Backend/Frontend가 함께 바뀌거나 contract 검증이 필요한 경우 `dev-api-contract`를 함께 적용한다.

DESIGN_FIRST 우선순위:

```text
APPROVED Markdown API Specification
→ Backend DTO / Controller
→ Frontend type / API client
→ OpenAPI / Postman
```

SOURCE_SYNC에서는 Application Source가 descriptive Markdown의 기준이다.

## dev-api-docs 연결

OpenAPI/Swagger/Postman 산출물은 `dev-api-docs`가 담당한다.

`APPROVED` Markdown이 존재하면 `dev-api-docs`는 먼저 source와 일치하는지 확인한다. mismatch를 발견하면 현재 source 기준으로 문서를 조용히 생성하지 않고 `API_SPEC_MISMATCH`를 보고한다.

## 금지

- SOURCE_SYNC 결과 자동 `APPROVED`
- Markdown 부재를 이유로 runtime API 의미 변경
- OpenAPI YAML을 프로젝트 합의 없이 canonical source로 강제
- Controller/DTO 이름만 보고 business 의미 추측
- 전체 repository Controller를 매 Task마다 자동 scan
- money/decimal/date/nullability를 근거 없이 추정
- APPROVED Spec mismatch를 ad-hoc mapper나 TypeScript cast로 숨기기

## Verification / Handoff

```text
Skill: dev-api-spec
API Spec Mode: DESIGN_FIRST | SOURCE_SYNC | AUDIT
API Spec Gate: REQUIRED | NOT_REQUIRED
API Spec Status: APPROVED | DRAFT | NOT_REQUIRED
API Spec Path
API Spec Source
Endpoints Inspected
Audit Result: IN_SYNC | SOURCE_ONLY | SPEC_ONLY | CONTRACT_MISMATCH
Markdown Added / Updated
Contract Mismatches Found
OpenAPI/Postman State
Residual Unknowns
```
