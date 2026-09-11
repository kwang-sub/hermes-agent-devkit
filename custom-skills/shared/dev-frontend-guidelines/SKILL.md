---
name: dev-frontend-guidelines
description: React 기반 frontend 구현에서 대상 프로젝트의 React/version/framework/state/style/data-fetching convention을 우선하고 공식 React 기준의 purity·Hook·state·Effect·ref·memoization 규칙을 적용하는 공통 capability skill.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, react, component, state, hooks, effect, ref, memoization, accessibility, convention]
    related_skills: [dev-typescript-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-frontend-guidelines

React 계열 UI application의 공통 구현 규칙이다. framework-specific routing/rendering 규칙은 `dev-nextjs-feature`, TypeScript 세부 타입 규칙은 `dev-typescript-guidelines`, 시각/UX 판단은 `dev-ui-ux`가 담당한다.

상세 공식 근거와 예외 판단은 필요할 때만 `references/official-react-practices.md`를 읽는다.

## 우선순위

```text
사용자/Task 명시 정책
→ 대상 프로젝트의 React/framework version + 기존 convention
→ 이 Skill의 React 공통 규칙
→ 공식 React 권장사항
```

최신 React 기능, React Compiler, 새로운 state/data library를 사용하기 위해 dependency/framework를 unrelated Task에서 자동 upgrade하지 않는다.

## 작업 전 확인

- React 및 UI framework/version
- React Compiler/Strict Mode/React lint 설정 여부
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

```text
상태 관리 필요
→ local state로 충분한가
→ 가장 가까운 owner로 lift 가능한가
→ 기존 Context/store가 있는가
→ 이미 설치된 state library가 있는가
→ 그래도 부족할 때만 새 선택 제안

form 필요
→ 기존 form pattern/validator 확인
→ native/platform 기능 또는 설치된 library 재사용
```

Zustand, TanStack Query, React Hook Form, Zod, 새로운 UI library 등을 단순 선호로 추가하지 않는다.

## Purity / Mutation

Component와 Hook의 render 계산은 순수하게 유지한다.

- render 중 외부 system을 변경하거나 side effect를 실행하지 않는다.
- props/state/shared object를 직접 mutate하지 않는다.
- UI 변경은 state setter나 기존 application state boundary를 사용한다.
- component 함수를 일반 함수처럼 직접 호출하지 않고 JSX/React 렌더링 경계를 사용한다.
- render 내부 local 계산용 object/array 생성과 외부 shared mutation을 구분한다.

## Rules of Hooks

- Hook은 function component 또는 custom Hook의 top level에서 호출한다.
- 조건문/반복문/nested function/event handler/try-catch 안에서 Hook 호출 순서를 바꾸지 않는다.
- 일반 utility 함수에서 Hook을 호출하지 않는다.
- Hook을 일반 callback/value처럼 동적으로 전달·교체하는 구조를 새로 만들지 않는다.
- 기존 React Hooks lint 규칙을 suppression으로 우회하지 않는다.

조건부 동작은 Hook 호출 자체를 조건부로 만들기보다 Hook 내부 조건, 반환값 또는 component 구조를 검토한다.

## State Structure

- props/state에서 계산 가능한 값은 derived value로 두고 redundant state를 만들지 않는다.
- 서로 모순될 수 있는 boolean state 여러 개보다 실제 finite state 구조를 우선 검토한다.
- 같은 entity/value를 여러 state에 duplicate하지 않는다.
- 동일 데이터에는 가능한 한 하나의 source of truth를 둔다.
- 공유가 필요한 state는 무조건 global로 올리지 않고 가장 가까운 실제 owner로 lift한다.
- line count만으로 stateful component를 분리하지 않는다.

State reset/preserve가 중요한 경우 component identity와 `key`를 명시적으로 검토한다. nested component definition 때문에 accidental reset이 생기지 않게 한다.

## Events vs Effects

Effect는 외부 system과 동기화할 때 쓰는 escape hatch다.

Effect를 기본 해법으로 사용하지 않는 경우:

```text
render용 데이터 변환
→ render에서 계산

click/submit 등 특정 사용자 interaction
→ event handler

다른 props/state를 그대로 복제
→ derived state / state structure 재검토
```

Effect 적합 후보:

- browser/non-React API subscription
- timer/listener/connection setup-cleanup
- third-party widget lifecycle
- 프로젝트가 Effect 기반으로 관리하는 외부 data synchronization

Effect를 사용할 때:

- setup/cleanup을 대칭적으로 구성한다.
- dependency를 숨기기 위해 lint rule을 무시하거나 임의 omission하지 않는다.
- dependency 때문에 반복 실행되면 object/function 생성 위치와 component 구조를 먼저 검토한다.
- state update → dependency change → Effect 재실행 cycle을 경계한다.
- async/network Effect는 stale result/race/cleanup에 대한 기존 project pattern을 따른다.

## Refs

- ref는 DOM 접근, timer/subscription handle, render를 유발할 필요 없는 mutable reference 등 좁은 escape hatch에 사용한다.
- 화면에 보여야 하는 값은 state를 우선한다.
- 일반 render 흐름에서 `ref.current`로 UI state를 우회하지 않는다.
- ref를 application state management 대체재처럼 확장하지 않는다.
- imperative DOM manipulation은 React ownership과 충돌하지 않는 경계에서만 사용한다.

## Memoization / React Compiler

`memo`, `useMemo`, `useCallback`은 correctness가 아니라 performance 최적화다.

- memoization이 없어도 동작이 올바르게 유지되어야 한다.
- 모든 component/callback/value에 blanket memoization하지 않는다.
- expensive calculation, child render pressure, dependency stabilization 등 실제 근거가 있을 때 적용한다.
- profiler/performance evidence가 있으면 우선 사용한다.
- React Compiler가 설정된 프로젝트에서는 compiler mode/directive/eslint contract를 먼저 확인한다.
- Compiler 미설정 프로젝트에 unrelated Task로 자동 도입하지 않는다.

## Component 책임

- component를 단순히 line count 때문에 쪼개지 않는다.
- 독립된 UI 책임, 재사용, state/effect ownership, 테스트 경계, rendering 비용이 명확할 때 분리한다.
- business/domain 계산을 view component에 중복 구현하지 않는다.
- key와 component identity를 warning 제거 수준이 아니라 state ownership 계약으로 본다.

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

## Review Hotspots

React diff에서는 필요할 때 다음을 우선 확인한다.

```text
render 중 side effect/shared mutation
props/state 직접 mutation
conditional/dynamic Hook 호출
component 함수 직접 호출
redundant/duplicated/contradictory state
Effect로 render data 변환 또는 event 처리
Effect dependency suppression / cleanup 누락
key/type 변경에 따른 state reset
render value를 ref로 우회
근거 없는 memo/useMemo/useCallback 남발
React Compiler 설정과 충돌하는 수동 최적화
불필요한 Context/global store 확대
```

## Verification / Evidence

프로젝트 script와 기존 test stack을 우선한다.

```text
typecheck/lint
affected component/hook test
필요 시 page/e2e test
build
```

state preserve/reset, Effect lifecycle, async interaction처럼 runtime behavior가 중요한 변경은 typecheck/lint만으로 완료 판단하지 않는다.

Handoff:

```text
Skill: dev-frontend-guidelines
Detected React/UI stack
React version / framework
React Compiler / Strict Mode / Hooks lint
State/Data fetching convention
State ownership decision
Effect/external-system boundary
Ref usage
Memoization decision
Styling/Component convention
Accessibility impact
Verification
```
