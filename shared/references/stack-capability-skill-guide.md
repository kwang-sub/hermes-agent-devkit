# Stack / Capability Skill Extension Guide

이 문서는 `coding-rules.md`, `implementation-decision-rules.md`, `project-pattern-rules.md`를 기반으로 특정 언어·프레임워크·기술 기능 Skill을 추가할 때의 설계 규칙이다.

## 1. 계층

```text
Foundation
- coding-rules.md
- implementation-decision-rules.md
- project-pattern-rules.md
        ↓
Workflow
- dev-fast-flow
- dev-project-pattern
- dev-tech-dispatch
- dev-breakdown
- dev-implement-plan
- dev-code-review
        ↓
Stack / Capability
        ↓
Project-specific convention
        ↓
Implementation / Review
```

프로젝트 자체의 기존 구조와 convention은 stack skill보다 우선한다. 단, 사용자/Task 명시 정책이 기존 코드와 충돌하면 해당 정책을 우선하되 주변 코드를 자동 migration하지 않는다.

## 2. Workflow와 Capability는 다른 축이다

```text
Workflow
= 작업 크기 / 모호성 / 승인 / workspace / review lifecycle

Capability
= 어떤 기술 지식과 검증이 필요한가
```

전문 Skill이라고 Standard Flow를 강제하지 않는다. 반대로 작은 syntax 변경처럼 보여도 API/schema/dependency/architecture 결정이 필요하면 Standard Flow다.

## 3. dev-tech-dispatch

두 번째 이상의 framework가 실제로 사용되므로 `dev-tech-dispatch`를 canonical stack resolver로 사용한다.

책임:

```text
build/dependency evidence
→ stack detection
→ baseline capability name mapping
```

하지 않는 일:

```text
source 수정
architecture 선택
dependency 설치
runtime skill 설치 여부 판단
Kanban 생성
```

실제 Task capability는 detector 결과와 affected area를 합쳐 `dev-project-pattern`/`dev-breakdown`이 결정한다.

## 4. 현재 capability set

### Backend

```text
dev-java-guidelines
dev-spring-guidelines
dev-spring-feature
dev-spring-data
dev-spring-test
dev-spring-refactor
```

### Frontend

```text
dev-typescript-guidelines
dev-frontend-guidelines
dev-nextjs-feature
dev-frontend-test
dev-ui-ux
```

### Cross-stack

```text
dev-api-contract
dev-api-docs
```

## 5. 모든 Capability Skill의 공통 실행 순서

```text
1. project stack/version 탐색
2. 기존 동일/유사 구현 검색
3. 기존 convention/implementation 결정
4. 중요한 assumption과 사용자 정책 충돌 확인
5. implementation-decision-rules의 필요성 사다리 적용
6. 최소 변경 구현
7. stack-specific verification
8. coder → reviewer handoff evidence 기록
```

새 dependency나 framework를 기본값으로 추가하지 않는다.

이미 프로젝트가 같은 목적의 library 또는 설정을 사용하면 기존 것을 우선한다.

## 6. Java / Spring

Java 언어 convention은 `dev-java-guidelines`, Spring 공통 계층/응답/transaction은 `dev-spring-guidelines`가 담당한다.

```text
Controller/Service/DTO/Validation/Exception
→ dev-spring-feature

JPA/Repository/Data JPA/QueryDSL/Converter/Paging
→ dev-spring-data

Spring/JPA test
→ dev-spring-test
```

### JPA Query 정책

```text
1. Spring Data JPA Method Query
2. QueryDSL
3. Native Query
```

Native Query는 DB vendor 기능, 표현 한계, 명확한 성능/legacy 근거 등이 있을 때만 사용한다.

QueryDSL dependency가 없는 프로젝트에 자동으로 새 dependency를 추가하지 않는다.

## 7. TypeScript / Frontend / Next.js

### TypeScript

`dev-typescript-guidelines`는 다음만 추가한다.

```text
tsconfig/strictness
type placement
nullability/optional
import/module convention
API type strategy
```

React/UI 책임을 중복하지 않는다.

### Frontend

`dev-frontend-guidelines`는 다음을 담당한다.

```text
component responsibility
state/data fetching
form/validation pattern
style/component library
browser/accessibility baseline
loading/empty/error states
```

새 상태 관리, form, query, UI library를 편의상 추가하지 않는다.

### Next.js

`dev-nextjs-feature`는 실제 Next.js version/router를 감지하고 다음을 담당한다.

```text
App/Pages Router
Server/Client Component boundary
route handler/server action
data cache/revalidation
layout/loading/error/metadata
```

`"use client"` boundary나 data library를 임의 확장하지 않는다.

### Frontend Test

`dev-frontend-test`는 기존 package/test stack을 감지해 affected test부터 실행한다.

```text
Vitest/Jest
Testing Library
Playwright/Cypress
기타 기존 runner
```

새 test framework를 추가하지 않는다.

## 8. API Contract

`dev-api-contract`는 framework 독립 capability다.

Backend와 Frontend가 함께 바뀌면 다음 계약을 대조한다.

```text
method/path
request/query/header
success/error body
common response wrapper
field name
required/optional/nullability
date/time
money/decimal
enum/code
paging/sorting
auth
```

프로젝트가 OpenAPI-generated client를 사용하면 그것을 source of truth로 유지한다. 수동 type/client 구조면 기존 방식을 따른다. Skill이 code generation을 자동 도입하지 않는다.

## 9. UI/UX Public Skill Adapter

`dev-ui-ux`는 UI/UX Pro Max의 공개 가이드에서 안정적인 quality priority를 참고한 audited adapter다.

```text
사용자 요구
→ project Design System/token/component
→ same-page existing pattern
→ dev-ui-ux baseline
```

upstream의 Claude-specific runtime 경로나 전체 search engine을 자동 vendor하지 않는다. 검색을 실제 실행하지 않았는데 database result로 보고하지 않는다.

UI/UX는 다음 보호 영역을 포함한다.

```text
accessibility
touch/interaction
responsive/layout
typography/color
reduced motion
form feedback
navigation
chart semantics
```

## 10. dev-api-docs

`dev-api-docs`는 Spring 전용이 아니다.

지원 mode:

```text
OPENAPI
POSTMAN
BOTH
```

실제 application contract가 source of truth이며 문서 생성을 이유로 API 의미를 바꾸지 않는다.

## 11. Reviewer 확장 규칙

Capability Skill은 Reviewer가 확인할 수 있는 다음 정보를 남긴다.

```text
Skill name
Detected stack/version
Pattern References
Preserved Conventions
Contract/Query/UI strategy (해당 시)
생성/수정 artifact
Verification
Intentional Deviations
Improvement Deferred
Residual Risk
```

Reviewer는 공통 Foundation과 Project Pattern을 먼저 적용하고 실제 diff 판단에 필요한 capability만 읽는다.

## 12. Naming

기본:

```text
dev-<stack>-<capability>
```

예:

```text
dev-spring-data
dev-nextjs-feature
```

framework 독립 기능은 stack 이름을 넣지 않는다.

```text
dev-api-contract
dev-api-docs
dev-ui-ux
```

## 13. Skill 추가 전 체크리스트

```text
[ ] Foundation reference만으로 해결할 수 없는 전문 기능인가
[ ] 반복 사용할 수 있는 작업 패턴인가
[ ] 기존 Skill과 역할이 겹치지 않는가
[ ] project/stack detection 절차가 정의됐는가
[ ] 기존 구현 재사용 우선순위가 정의됐는가
[ ] assumption/충돌 처리 방식이 정의됐는가
[ ] dependency 추가 정책이 정의됐는가
[ ] stack-specific verification이 정의됐는가
[ ] Reviewer evidence가 정의됐는가
[ ] Public Skill이면 source/version/license/update policy를 검토했는가
[ ] profile-local 설치가 아니라 shared가 필요한지 검토했는가
```
