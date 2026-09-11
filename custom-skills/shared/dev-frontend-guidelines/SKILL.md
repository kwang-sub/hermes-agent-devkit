---
name: dev-frontend-guidelines
description: React 기반 frontend 구현에서 대상 React/framework version과 기존 state/style/data-fetching convention을 우선하고 공식 React 기준의 purity·Hook·Effect·Compiler·transition·profiling 최적화 규칙을 적용하는 공통 capability skill.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, react, component, state, hooks, effect, compiler, profiler, transition, memoization, accessibility, performance]
    related_skills: [dev-typescript-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-frontend-guidelines

React 계열 UI application의 공통 구현/성능 규칙이다. framework-specific routing/rendering/data cache는 `dev-nextjs-feature`, TypeScript 규칙은 `dev-typescript-guidelines`, 시각/UX 판단은 `dev-ui-ux`가 담당한다.

상세 version별 근거는 필요할 때만 `references/official-react-practices.md`를 읽는다.

## 우선순위

```text
사용자/Task 명시 정책
→ 실제 React/framework/build/lint version
→ 기존 project component/state/data-fetching convention
→ 실제 Profiler/Performance evidence
→ 이 Skill의 React 규칙
→ 공식 React 권장사항
```

React/framework/Compiler/plugin upgrade를 unrelated Task에 자동 포함하지 않는다.

## 작업 전 확인

- React/framework 실제 version
- React 17/18 | 19.x | 19.2+ lane
- React Compiler 설치/version/compilationMode/gating 여부
- `eslint-plugin-react-hooks` version/preset
- Strict Mode
- component/state/Context/store 구조
- data-fetching/cache/form convention
- existing manual `memo/useMemo/useCallback`
- test/build script
- 성능 Task면 느린 interaction과 측정 근거

## Purity / Mutation

Component와 Hook의 render는 순수하게 유지한다.

- render 중 external/global/shared state mutation 금지
- props/state 직접 mutation 금지
- Component 함수를 일반 함수처럼 직접 호출하지 않는다.
- render 결과를 ref/global variable로 우회 저장하지 않는다.
- local calculation용 새 object/array와 shared mutation을 구분한다.

Purity는 correctness뿐 아니라 React Compiler 자동 최적화의 전제다.

## Rules of Hooks / `use` 예외

일반 Hook은 Component/custom Hook의 top level에서 동일 순서로 호출한다.

- 조건문/반복문/nested callback/event handler에서 일반 Hook 호출 금지
- early return 이후 Hook 호출 금지
- 일반 utility/module scope에서 Hook 호출 금지
- lint suppression으로 Rules of Hooks를 우회하지 않는다.

단, React의 `use()`는 공식 예외다.

```text
use(resource)
→ 조건문/반복문 호출 가능
→ Component/Hook 내부라는 경계는 유지
→ try/catch 안에서 Promise read 용도로 사용하지 않음
→ 실제 React/framework version 지원 확인
```

`use()`를 일반 Hook 규칙으로 기계적으로 top-level 이동하지 않는다.

## State Ownership

- props/state로 계산 가능한 값은 derived value로 둔다.
- contradictory boolean state를 줄이고 실제 finite state를 표현한다.
- 같은 entity/value를 여러 state에 복제하지 않는다.
- transient form/hover/input state를 필요 이상 상위/global로 올리지 않는다.
- 공유 state는 가장 가까운 실제 owner를 우선한다.
- nested component definition으로 state identity를 매 render 깨뜨리지 않는다.
- `key`는 warning 제거가 아니라 state identity 계약으로 본다.

## Events / Effects

Effect는 external system synchronization용 escape hatch다.

기본적으로 Effect가 아닌 것:

```text
render용 계산 → render/derived value
사용자 click/submit → event handler
props/state 복제 → state structure 재검토
```

Effect 사용 시:

- setup/cleanup 대칭
- dependency suppression 금지
- object/function dependency가 반복 실행을 만들면 구조/생성 위치 먼저 수정
- synchronous setState → rerender → Effect chain 경계
- async/network stale result/race/cleanup은 기존 project pattern 유지

## `useEffectEvent` (React 19.2+)

Effect 내부의 비반응적 event logic이 최신 props/state를 읽되 Effect를 재연결할 필요가 없을 때만 검토한다.

- dependency array 숨김 용도로 사용하지 않는다.
- 일반 UI event handler 대체 금지
- child callback prop 전달 금지
- render 중 호출 금지
- Effect Event 자체를 dependency에 넣지 않는다.
- project Hooks lint가 API를 이해하는 version인지 확인한다.

## Refs

- DOM/imperative handle/timer/subscription handle 등 narrow boundary에 사용한다.
- 화면에 보이는 값은 state를 우선한다.
- render 중 `ref.current` read/write로 UI state를 우회하지 않는다.
- ref를 global/application state 대체재로 사용하지 않는다.

## Measurement First

성능 최적화 전에 가능한 한 실제 bottleneck을 측정한다.

```text
React DevTools Profiler
→ 느린 commit/component 확인
→ React 19.2+이면 React Performance Tracks 확인
→ 필요 시 <Profiler> actualDuration/baseDuration 기록
```

- Strict Mode 개발용 추가 render와 production latency를 구분한다.
- 최적화 전/후 같은 interaction을 비교한다.
- micro benchmark 하나만으로 architecture를 변경하지 않는다.

## Manual Memoization

`memo`, `useMemo`, `useCallback`은 correctness가 아니라 measured performance optimization이다.

기본 순서:

```text
불필요한 state lifting / broad Context / Effect chain 제거
→ component ownership 정리
→ Profiler hotspot 확인
→ 필요한 곳만 memoization
```

- blanket memoization 금지
- memoization이 없어도 correctness 유지
- `useCallback`은 memoized child prop/Hook dependency처럼 identity가 실제 경계일 때 사용
- `useMemo`는 비싼 계산 또는 reference identity가 실제 hotspot일 때 사용
- 매 render 새 dependency 하나가 memoization 전체를 깨는지 확인

## React Compiler 1.0+

React Compiler 1.0은 stable production-ready 자동 memoization compiler다.

Compiler가 있는 프로젝트:
- `infer | all | annotation` mode와 `gating` 확인
- 기존 manual memoization을 무조건 삭제하지 않는다.
- `preserve-manual-memoization` 및 Compiler diagnostics 확인
- Compiler가 skip한 component를 전체 failure로 해석하지 않는다.
- 새 manual memoization은 compiler coverage/Profiler evidence를 확인한 뒤 추가한다.

기존 프로젝트에서 Compiler 신규 도입:
- framework/build tool 지원 확인
- Rules of React lint health 확인
- unit/integration/e2e coverage 확인
- directory/annotation/gating 기반 점진 도입 우선
- `"use memo"`는 annotation/명시 opt-in이 실제 필요한 경우만
- `"use no memo"`는 임시 escape hatch로만
- regression coverage가 약하면 Compiler exact version pinning 검토

unrelated feature/fix에서 Compiler를 자동 설치하지 않는다.

## Compiler-aware ESLint

`eslint-plugin-react-hooks`는 Compiler 미설치 프로젝트에서도 Rules/Compiler 관련 diagnostics를 제공할 수 있다.

React optimization Task에서는 기존 config를 기준으로 다음 hotspot을 확인한다.

```text
exhaustive-deps
rules-of-hooks
component-hook-factories
globals
immutability
incompatible-library
preserve-manual-memoization
purity
refs
set-state-in-effect
set-state-in-render
static-components
unsupported-syntax
use-memo
```

plugin major/preset 변경은 영향 범위를 확인하고 별도 migration으로 분리할 수 있다.

## Transition / Deferred Rendering

### `useTransition` / `startTransition`

큰 subtree update처럼 urgent하지 않은 render를 non-blocking으로 처리할 때 검토한다.

- controlled text input state 자체는 Transition으로 감싸지 않는다.
- pending UI가 필요하면 `useTransition`을 우선한다.
- Transition은 계산 자체를 빠르게 만드는 기능이 아니다.
- 모든 update를 Transition으로 감싸지 않는다.

### `useDeferredValue`

빠르게 변하는 값 때문에 느린 subtree가 urgent interaction을 막을 때 검토한다.

후보:
- 검색 input + 큰 result list
- input/filter + 무거운 chart

- debounce/throttle 대체로 오해하지 않는다.
- slow subtree가 이전 value로 skip render할 수 있도록 Compiler/memoization 구조와 함께 확인한다.

## `<Activity>` (React 19.2+)

state/DOM을 보존하면서 hidden UI update를 낮은 우선순위로 처리하고 다음 화면을 pre-render할 가치가 있을 때만 검토한다.

후보:
- 다시 돌아올 tab/sidebar/page
- back navigation state 보존
- 다음 화면 pre-render로 interaction latency 감소

주의:
- hidden 시 Effects가 unmount됨
- cleanup/remount correctness 확인
- memory cost와 실제 latency 개선 비교
- 단순 `display:none` 대체로 사용 금지

## Context / Component Boundary

Context performance 문제가 측정되면 다음 순서로 본다.

```text
state를 더 local하게 둘 수 있는가
→ provider 범위를 줄일 수 있는가
→ 책임별 Context 분리 근거가 있는가
→ value identity가 실제 hotspot인가
```

성능 이유만으로 새 global store 도입이나 Context 기계 분할을 하지 않는다.

component 분리는 line count보다 state/effect/render ownership, 재사용, 테스트, 성능 경계를 기준으로 한다.

## 접근성 기본선

- semantic element 우선
- keyboard 핵심 동작 보장
- focus indicator 제거 금지
- icon-only control accessible name
- form label/error 관계 유지
- color 하나만으로 상태 전달 금지

## API / Error

- 기존 API client/auth/error contract 재사용
- backend response를 component마다 ad-hoc reshape하지 않는다.
- API contract 변경은 `dev-api-contract` 검토
- loading/empty/error/success 상태를 기존 UX와 일치시킨다.

## Review Hotspots

```text
render side effect/global mutation
props/state mutation
일반 Hook의 conditional/dynamic 호출
use() 공식 예외를 잘못 수정
매 render nested component definition
redundant state / 과도한 state lifting / broad Context
Effect data transform/event handling/dependency suppression
Effect synchronous setState chain
useEffectEvent dependency 숨김 악용
ref로 render state 우회
Profiler 근거 없는 memoization
Compiler와 중복되는 manual memoization
Compiler diagnostics/incompatible library 무시
Transition controlled input 오용
useDeferredValue를 debounce로 오해
Activity hidden Effect lifecycle 누락
```

## Verification / Performance Evidence

프로젝트 script와 기존 test stack을 우선한다.

```text
typecheck/lint
affected component/hook test
필요 시 integration/e2e
build
```

React 성능 변경이면 가능하면 다음을 남긴다.

```text
React version / framework
React Compiler: off | infer | all | annotation | gated
Hooks lint version/preset
Measured interaction
Profiler/Performance Track finding
Before / After actualDuration 또는 user-visible latency
Manual memoization decision
Transition/deferred/Activity decision
Residual risk
```

Compiler 도입/upgrade, Activity, Effect lifecycle 변경은 E2E 또는 실제 interaction regression을 포함한다.

## Handoff

```text
Skill: dev-frontend-guidelines
Detected React/UI stack
React version lane
React Compiler / Hooks lint / Strict Mode
State/Data fetching convention
State ownership decision
Effect/useEffectEvent boundary
Profiler evidence
Manual memoization decision
Transition/deferred/Activity decision
Styling/Component convention
Accessibility impact
Verification / performance evidence
```
