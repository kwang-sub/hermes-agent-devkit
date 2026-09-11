---
name: dev-frontend-feature
description: Frontend 작업의 canonical entry point로 승인된 Design Reference 또는 기존 코드 기준을 TypeScript·React/Next.js·UI/UX·API contract·test capability와 조합한다.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, feature, design-reference, image, figma, ui, ux, typescript, react, nextjs]
    related_skills: [dev-design-reference, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-figma-design, dev-ui-ux]
    requires_tools: [terminal, skill_view]
---

# dev-frontend-feature

Frontend 구현/검토의 canonical entry다. 실제 Task에 필요한 하위 capability만 lazy-load하며 Design Source 자체와 구현 기술을 분리한다.

## Frontend Mode

```text
REFERENCE_DRIVEN
- IMAGE 또는 FIGMA Reference가 있음
- dev-design-reference로 Normalized Design Evidence를 먼저 확보
- APPROVED는 구현 기준, REFERENCE는 방향 참고, DRAFT는 planning only

CODE_DRIVEN
- authoritative external Design Reference가 없음
- 현재 project component/token/style/화면이 source of truth
```

기존 `FIGMA_DRIVEN`은 호환 개념상 `REFERENCE_DRIVEN + Design Source=FIGMA`로 해석한다. 신규 Task에서는 `REFERENCE_DRIVEN`을 canonical 표현으로 사용한다.

## Design Source

```text
IMAGE
FIGMA
EXISTING_CODE
```

IMAGE와 FIGMA의 차이는 provider 단계에서만 다루고 이후 Coder/Reviewer는 Normalized Design Evidence를 공통 계약으로 사용한다.

## Coder 실행 순서

```text
1. Frontend stack/package manager/version 확인
2. REFERENCE_DRIVEN | CODE_DRIVEN 결정
3. REFERENCE_DRIVEN이면 dev-design-reference load
4. Screen Spec / Design Evidence와 기존 component/token/style/API/test pattern 대조
5. 필요한 하위 capability만 lazy-load
6. IMPLEMENTATION_SCOPE_READY 확정
7. 최소 변경 구현
8. 의미 있는 stateful/shared UI면 기존 Storybook catalog 갱신 검토
9. UI 변경이면 dev-ui-ux quality gate
10. affected test/typecheck/lint/build + 필요한 visual verification
11. handoff evidence 기록
```

## Lazy capability

- Design Reference 정규화 → `dev-design-reference`
- Figma provider read → `dev-figma-design`
- TypeScript type/config/nullability → `dev-typescript-guidelines`
- React component/state/form/browser behavior → `dev-frontend-guidelines`
- Next.js router/server-client/cache/metadata → `dev-nextjs-feature`
- frontend unit/component/e2e/visual verification → `dev-frontend-test`
- backend↔frontend request/response contract → `dev-api-contract`
- visual/interaction/responsive/accessibility/chart → `dev-ui-ux`

React/Next.js가 존재한다는 이유만으로 모든 Skill을 로드하지 않는다.

## REFERENCE_DRIVEN 우선순위

`Design Status=APPROVED`일 때:

```text
사용자/Task 명시 요구
→ Approved Reference의 OBSERVED evidence
→ project Design System/component/token/convention
→ INFERRED evidence
→ dev-ui-ux quality guardrail
→ 일반 best practice
```

`REFERENCE` 상태는 source of truth가 아니므로 project pattern보다 위에 놓지 않는다.

Reference와 전역 token/component가 충돌하면 현재 Task 범위를 넘어 global migration하지 않는다. `Design Conflict`와 `Improvement Deferred`로 남긴다.

## IMAGE Reference Package

프로젝트에 별도 convention이 없으면:

```text
docs/ui/screens/<screen>/
├─ reference.png
└─ screen-spec.md
```

을 권장한다.

`reference.png`는 보이는 계약이고 `screen-spec.md`는 interaction/state/responsive/API 같은 보이지 않는 계약이다.

이미지에서 직접 확인할 수 없는 값은 `INFERRED` 또는 `UNKNOWN`으로 남긴다. screenshot을 보고 exact token/CSS 값을 사실처럼 만들지 않는다.

## Storybook Catalog

Storybook이 이미 프로젝트에 있거나 project convention이 Storybook을 사용하면 다음 UI를 catalog 후보로 본다.

```text
공용 UI Component
독립적으로 의미 있는 화면 Component
여러 상태를 가진 Component
복잡한 Chart / Form
```

작은 내부 wrapper/layout helper까지 story를 강제하지 않는다.

상태가 의미 있으면 가능한 범위에서 다음을 story로 분리한다.

```text
Default
Loading
Empty
Error
Selected / Disabled / Positive / Negative 등 실제 domain state
```

Storybook이 없는 프로젝트에 이번 화면 구현만을 이유로 dependency를 자동 추가하지 않는다. 도입이 필요하면 dependency/architecture 결정으로 Standard Flow에서 별도 승인한다.

## Visual Verification

시각 검증은 두 목적을 구분한다.

```text
DESIGN_CONFORMANCE
Approved Design Reference ↔ 최초 구현 결과
목표: 구조/배치/시각 hierarchy/주요 visual intent 일치

VISUAL_REGRESSION
승인된 실제 browser screenshot ↔ 이후 구현 결과
목표: 이미 승인된 구현의 의도치 않은 visual 변경 탐지
```

ChatGPT/디자인 PNG를 곧바로 장기 regression golden으로 사용하지 않는다. 최초 구현 승인 후 실제 browser screenshot을 regression baseline으로 사용한다.

실제 실행 규칙은 `dev-frontend-test`를 따른다.

## CODE_DRIVEN

```text
사용자/Task 명시 요구
→ project Design System/component/token/convention
→ current screen pattern
→ dev-ui-ux quality guardrail
→ 일반 best practice
```

## Reviewer 적용

Reviewer는 기존 `dev-code-review`의 diff-first/verification reuse 계약을 유지하면서 다음을 추가한다.

- Frontend Mode / Design Source / Status / Fidelity를 확인한다.
- REFERENCE_DRIVEN이면 Coder의 Normalized Design Evidence와 `screen-spec.md`를 우선 재사용한다.
- fidelity finding에 원본이 필요할 때만 IMAGE/Figma Reference를 다시 확인한다.
- `OBSERVED`, `INFERRED`, `UNKNOWN` 경계를 Coder가 무너뜨리지 않았는지 확인한다.
- approved reference와 project Design System 충돌을 global redesign 요구로 확대하지 않는다.
- Storybook/Playwright가 없는 프로젝트에 review 단계에서 새 dependency 도입을 강제하지 않는다.

## Handoff

```text
Frontend Mode: REFERENCE_DRIVEN | CODE_DRIVEN
Design Source: IMAGE | FIGMA | EXISTING_CODE
Design Status: DRAFT | REFERENCE | APPROVED | N/A
Design Fidelity: STRUCTURE | VISUAL | HIGH | N/A
Reference: <repo path | Figma URL | current code>
Screen Spec: <path | none>
Observed / Inferred / Unknown:
- ...
Applied Capability Skills:
- ...
Component/Token Reuse:
- ...
Storybook Catalog: UPDATED | NOT_REQUIRED | NOT_AVAILABLE
Design Conformance: PASS | MANUAL_PASS | NOT_RUN | NOT_REQUIRED
Visual Regression: PASS | NOT_RUN | NOT_REQUIRED
Design Conflicts:
- ...
Verification:
- ...
Residual Risk:
- ...
```

## 불변식

- DRAFT/REFERENCE를 APPROVED로 임의 승격하지 않는다.
- 이미지 추정치를 exact design fact로 바꾸지 않는다.
- Approved Reference 일치를 이유로 unrelated global style/token refactor를 하지 않는다.
- dependency/state/form/query/UI/test library를 편의상 추가하지 않는다.
- Design Conformance reference와 Visual Regression golden을 동일 개념으로 취급하지 않는다.
- Reviewer가 독립성을 이유로 같은 이미지/Figma/test evidence를 불필요하게 반복 조회하지 않는다.
