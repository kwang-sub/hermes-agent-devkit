---
name: dev-frontend-guidelines
description: React 기반 frontend 구현에서 기존 component/state/style/data-fetching/browser convention을 유지하고 접근성·상태 책임·불필요한 dependency 도입을 통제하는 공통 capability skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, react, component, state, accessibility, convention]
    related_skills: [dev-typescript-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-frontend-guidelines

React 계열 UI application의 공통 구현 규칙이다. framework-specific routing/rendering 규칙은 `dev-nextjs-feature`, 시각/UX 판단은 `dev-ui-ux`가 담당한다.

## 작업 전 확인

- React 및 UI framework/version
- component/module 디렉터리 구조
- styling 방식(CSS module, Tailwind, styled solution 등)
- state 관리(local/context/existing store)
- server data fetching/cache library
- form/validation 방식
- API client/error 처리
- design token/component library
- test framework/style

## Existing Pattern First

새 라이브러리를 기본값으로 제안하지 않는다.

예:

```text
상태 관리 필요
→ local state로 충분한가
→ 기존 Context/store가 있는가
→ 이미 설치된 state library가 있는가
→ 그래도 부족할 때만 새 선택 제안

form 필요
→ 기존 form pattern/validator 확인
→ native/platform 기능 또는 설치된 library 재사용
```

Zustand, TanStack Query, React Hook Form, Zod, 새로운 UI library 등을 단순 선호로 추가하지 않는다.

## Component 책임

- component를 단순히 line count 때문에 쪼개지 않는다.
- 독립된 UI 책임, 재사용, 테스트 경계, rendering 비용이 명확할 때 분리한다.
- business/domain 계산을 view component에 중복 구현하지 않는다.
- derived state를 불필요하게 별도 state로 보관하지 않는다.
- effect는 외부 시스템 동기화가 필요한 경우 중심으로 사용하고 계산 가능한 값을 effect로 복제하지 않는다.
- key, memoization, callback 최적화는 실제 필요/기존 pattern 근거 없이 남발하지 않는다.

## 접근성 기본선

`dev-ui-ux`가 없어도 다음은 보호 영역이다.

- semantic element를 우선한다.
- keyboard로 핵심 동작이 가능해야 한다.
- focus indicator를 대체 없이 제거하지 않는다.
- icon-only control은 accessible name을 제공한다.
- form label/error 관계를 유지한다.
- 상태를 color 하나에만 의존해 전달하지 않는다.

## API / Error

- 기존 API client와 auth/error 처리 체계를 재사용한다.
- backend response를 UI component 곳곳에서 임의 reshape하지 않는다.
- API contract 변경은 `dev-api-contract` 적용 여부를 검토한다.
- loading/empty/error/success 상태를 요구사항과 기존 UX pattern에 맞게 처리한다.

## Verification / Evidence

프로젝트 script와 기존 test stack을 우선한다.

```text
typecheck/lint
affected component/unit test
필요 시 page/e2e test
build
```

Handoff:

```text
Skill: dev-frontend-guidelines
Detected React/UI stack
State/Data fetching convention
Styling/Component convention
Accessibility impact
Verification
```
