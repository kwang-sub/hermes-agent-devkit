---
name: dev-frontend-feature
description: Frontend 작업의 canonical entry point로 Figma/CODE 기반 디자인 소스와 TypeScript·React/Next.js·UI/UX·API contract·test capability를 task evidence에 따라 조합한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, feature, figma, ui, ux, typescript, react, nextjs]
    related_skills: [dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-figma-design, dev-ui-ux]
    requires_tools: [terminal, skill_view]
---

# dev-frontend-feature

Frontend 구현/검토의 상위 조합 Skill이다. Foundation과 project pattern을 반복하지 않고 실제 Task에 필요한 하위 capability만 lazy-load한다.

## 1. 진입 모드

```text
FIGMA_DRIVEN
- Task에 승인된 Figma frame/component URL이 있음
- Design Status=APPROVED
- dev-figma-design으로 targeted design evidence를 먼저 확보

CODE_DRIVEN
- 승인된 Figma가 없음
- 현재 프로젝트의 기존 화면/component/token/style이 source of truth
```

`DRAFT` Figma는 계획/비교 참고자료일 뿐 구현 source of truth가 아니다.

## 2. Coder 실행 순서

```text
1. Frontend stack/package manager/version 확인
2. FIGMA_DRIVEN | CODE_DRIVEN 결정
3. 기존 component/token/style/API client/test pattern 확인
4. 필요한 하위 Skill만 skill_view
5. IMPLEMENTATION_SCOPE_READY 확정
6. 최소 변경 구현
7. UI 변경이면 dev-ui-ux quality gate
8. affected test/typecheck/lint/build 중 필요한 검증
9. handoff evidence 기록
```

## 3. Lazy capability

- TypeScript type/tsconfig/nullability → `dev-typescript-guidelines`
- React component/state/form/browser behavior → `dev-frontend-guidelines`
- Next.js router/server-client/cache/metadata → `dev-nextjs-feature`
- frontend spec/e2e → `dev-frontend-test`
- backend↔frontend request/response type → `dev-api-contract`
- 승인 Figma → `dev-figma-design`
- visual/interaction/responsive/accessibility/chart → `dev-ui-ux`

React/Next.js가 존재한다는 이유만으로 모든 Skill을 로드하지 않는다.

FIGMA_DRIVEN에서는 정확한 selected node URL만 `dev-figma-design`에 전달한다. file 전체 read는 기본 경로가 아니다.

## 4. Design 우선순위

FIGMA_DRIVEN:

```text
사용자/Task 명시 요구
→ 승인된 Figma/Design System
→ 기존 project component/token/convention
→ dev-ui-ux quality guardrail
→ 일반 best practice
```

CODE_DRIVEN:

```text
사용자/Task 명시 요구
→ 기존 project component/token/convention
→ dev-ui-ux quality guardrail
→ 일반 best practice
```

Figma와 전역 token/component가 충돌하면 현재 Task 범위를 넘어 전역 migration하지 않는다. `Design Conflict`와 `Improvement Deferred`로 남긴다.

## 5. Frontend Verification

package manager와 script는 lockfile/package.json evidence로 선택한다.

```text
affected component/spec
→ typecheck
→ lint
→ related integration
→ 필요한 경우 build
→ 필요한 경우 e2e
```

같은 scope의 PASS command를 확신 확보용으로 반복하지 않는다. 새 test/library를 편의상 추가하지 않는다.

## 6. Reviewer 적용

Reviewer가 이 Skill을 runtime pinned context로 받은 경우 기존 `dev-code-review`의 diff-first/verification reuse 계약을 유지하면서 다음만 추가한다.

- `Frontend Mode`, `Design Source`, `Design Status`, Coder의 `Design Evidence`를 먼저 확인한다.
- FIGMA_DRIVEN에서 실제 fidelity/correctness 판단에 Figma 원본이 필요한 경우에만 `skill_view("dev-figma-design")` 후 같은 selected node URL을 targeted read한다.
- 일반 code correctness만으로 판단 가능한 경우 Figma API를 다시 호출하지 않고 Coder evidence를 재사용한다.
- TypeScript/React/Next.js/API/UI·UX finding 판단에 필요한 하위 Skill만 `skill_view`한다.
- Figma와 코드가 다르다는 이유만으로 global redesign을 요구하지 않는다. Task scope의 승인 디자인과 AC를 기준으로 판단한다.
- 접근성/security/data integrity처럼 보호 영역이 승인 디자인과 충돌하면 `Design Conflict`로 명시하고 필요한 수정/결정을 요구한다.

## 7. Handoff

```text
Frontend Mode: FIGMA_DRIVEN | CODE_DRIVEN
Design Source: <Figma frame | existing code>
Design Status: APPROVED | N/A
Figma File/Node/Version: <해당 시>
Applied Capability Skills:
- ...
Pattern References:
- ...
Component/Token Reuse:
- ...
Design Conflicts:
- ...
Verification:
- ...
Residual Risk:
- ...
```

## 불변식

- Figma DRAFT를 승인된 디자인으로 취급하지 않는다.
- Figma 일치를 이유로 unrelated global style/token refactor를 하지 않는다.
- UI/UX recommendation이 승인된 디자인/프로젝트 contract를 조용히 대체하지 않는다.
- dependency/state/form/query/UI library를 편의상 추가하지 않는다.
- Reviewer가 독립성을 이유로 같은 Figma/API/test evidence를 불필요하게 반복 조회하지 않는다.
