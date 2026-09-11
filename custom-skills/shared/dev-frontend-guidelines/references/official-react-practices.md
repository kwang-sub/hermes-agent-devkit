# React Official Practices

React 공식 문서의 Rules of React, Learn, Hooks Reference, React Compiler, React 19.2 release guidance를 기준으로 Hermes에서 사용할 React 판단 근거를 정리한다. 최신 API를 모든 프로젝트에 기계적으로 적용하지 않는다. 항상 대상 프로젝트의 React version, framework/runtime, compiler/lint 설정, 기존 component/state/data-fetching convention과 실제 performance evidence를 먼저 따른다.

## Project Convention First

```text
사용자/Task 정책
→ 현재 React/framework version + build/compiler/lint 설정
→ 기존 project component/state/data-fetching/style convention
→ 실제 Profiler/Performance evidence
→ 이 문서의 version-specific React 최적화 기준
→ 일반 React 권장사항
```

React/framework/package/Compiler upgrade는 unrelated feature/fix에 자동 포함하지 않는다.

## Version Gate: React 17/18 / 19 / 19.2+

React 최적화 API는 version에 따라 사용할 수 있는 기능이 다르므로 먼저 실제 installed version을 확인한다.

```text
React 17/18
→ 기존 concurrent/rendering semantics와 framework 지원 범위 유지
→ React 19/19.2 API 자동 사용 금지
→ React Compiler는 별도 runtime target 설정과 compatibility 확인 후 후보

React 19.x
→ React 19 API 사용 가능 여부를 framework와 함께 확인
→ React Compiler default config 후보

React 19.2+
→ useEffectEvent / Activity / Performance Tracks 후보
→ 실제 use case가 있을 때만 적용
```

React version만 보고 framework-owned rendering/data APIs를 React core API로 교체하지 않는다.

## Components and Hooks must be pure

React 자동 최적화의 전제는 Component와 Hook의 render 계산이 순수해야 한다는 것이다.

- 같은 props/state/context 입력에 대해 render 결과가 예측 가능해야 한다.
- render 중 외부 상태를 변경하거나 side effect를 실행하지 않는다.
- props/state/shared object를 직접 mutate하지 않는다.
- Hook에 전달한 값이나 JSX에 전달한 값을 render 이후 임의 mutate하지 않는다.
- Component 함수를 일반 함수처럼 직접 호출하지 않고 JSX/React 렌더링 경계를 사용한다.
- module/global mutation을 render 중 수행하지 않는다.

이 규칙은 correctness뿐 아니라 React Compiler가 안전하게 자동 memoization할 수 있는 기반이다.

## Rules of Hooks and the `use` Exception

일반 Hook은 function component 또는 custom Hook의 top level에서 동일 순서로 호출한다.

금지:
- 조건문/반복문 내부의 일반 Hook 호출
- nested function/event handler의 Hook 호출
- early return 이후 Hook 호출
- 일반 utility/module scope에서 Hook 호출

### `use` Hook 예외

React의 `use` API는 일반 Hook과 달리 **조건문과 반복문에서 호출할 수 있다.**

다만 다음 제한은 유지한다.

- Component 또는 Hook 내부에서만 호출한다.
- `try/catch` 안에서 Promise를 읽는 용도로 사용하지 않는다.
- 일반 callback/event handler로 빼지 않는다.
- React/framework version 지원을 먼저 확인한다.

따라서 lint 오류를 피하기 위해 `use()`를 일반 Hook처럼 무조건 top-level로 옮기지 않는다.

## State Structure / Ownership

state는 최소한의 canonical source만 보관한다.

```text
props/state에서 계산 가능
→ derived value

사용자 interaction/time에 따라 독립 변화
→ state 후보

여러 component가 동일 값을 제어
→ 가장 가까운 공통 owner로 lift

application 전체가 실제 공유
→ 기존 Context/store 후보
```

피할 패턴:
- 서로 모순되는 여러 boolean state
- props/다른 state에서 계산 가능한 redundant state
- 동일 entity의 duplicate state
- 불필요하게 상위로 lift한 transient state
- hover/form draft 같은 local interaction을 global store로 이동

React 공식 performance guidance는 transient state를 가능한 local하게 유지하는 것을 권장한다. 상위 state가 바뀔 때 거대한 subtree가 불필요하게 다시 render되는 구조를 먼저 줄인다.

## Preserving and Resetting State

React state는 render tree의 component identity와 연결된다.

- 같은 위치/type/key면 기본적으로 state를 보존한다.
- 다른 type/key는 state reset을 유발할 수 있다.
- form/editor를 의도적으로 reset할 때 key를 사용할 수 있다.
- component 정의를 다른 component 안에 중첩해 매 render 새 component type을 만들지 않는다.
- list key를 index/warning 제거용 값이 아니라 identity 계약으로 본다.

`static-components` lint가 지적하는 매-render component 재생성도 같은 맥락에서 검토한다.

## Events vs Effects

Effect는 React 외부 system과 동기화하는 escape hatch다.

Effect가 기본 해법이 아닌 경우:

```text
render용 데이터 변환
→ render에서 계산

사용자 click/submit
→ event handler

props/state를 다른 state로 그대로 복제
→ derived state / ownership 재검토

Effect에서 동기 setState 후 다시 render
→ 실제 external synchronization인지 재검토
```

React 공식 guidance는 불필요한 Effect와 Effect에서 시작하는 state-update chain이 React 성능 문제의 주요 원인이 될 수 있음을 강조한다.

Effect를 사용할 때:
- setup/cleanup을 대칭적으로 구성한다.
- dependency suppression으로 문제를 숨기지 않는다.
- object/function dependency 때문에 반복 실행되면 생성 위치/구조를 먼저 검토한다.
- state update → dependency change → Effect rerun cycle을 경계한다.
- async/network Effect는 stale result/race/cleanup에 대한 기존 project pattern을 따른다.

## `useEffectEvent` (React 19.2+)

`useEffectEvent`는 Effect 내부의 **비반응적 event logic**이 최신 props/state를 읽되 Effect 자체를 다시 연결할 필요가 없을 때 사용한다.

적합 후보:
- connection callback에서 최신 theme/setting 읽기
- interval/listener가 최신 값을 읽되 timer/listener를 재설치할 필요가 없음
- Effect lifecycle과 event-like callback의 dependency를 분리해야 함

금지:
- dependency array에서 값을 숨기기 위한 용도
- 일반 click handler 대체
- child에 callback prop으로 전달
- render 중 호출

Effect Event 함수는 stable identity를 보장하지 않으며 dependency array에 넣지 않는다. 프로젝트의 `eslint-plugin-react-hooks`가 해당 규칙을 이해하는 version인지 확인한다.

## Refs

ref는 DOM, imperative handle, timer/subscription handle처럼 render 결과에 직접 필요하지 않은 mutable value에 사용하는 escape hatch다.

- 화면에 보여야 하는 값은 state를 우선한다.
- render 중 일반 UI 계산을 `ref.current` read/write로 우회하지 않는다.
- application state management 대체재로 확장하지 않는다.
- imperative DOM 조작은 React ownership과 충돌하지 않는 좁은 boundary에서 사용한다.

Compiler lint의 `refs` 진단이 있으면 suppression보다 구조 수정을 우선한다.

## Measure First: React DevTools / Profiler / Performance Tracks

React 성능 변경은 가능하면 측정 근거를 먼저 확보한다.

우선순위:

```text
React DevTools Profiler
→ 느린 interaction의 commit/component 확인
→ React 19.2+이면 Chrome Performance의 React Performance Tracks 확인
→ 필요 시 <Profiler>로 programmatic measurement
```

`<Profiler>`의 `actualDuration`과 `baseDuration`을 비교하면 memoization이 실제 rerender 비용을 줄이는지 판단하는 데 도움이 된다.

주의:
- profiling 자체에 overhead가 있다.
- micro benchmark 하나만으로 architecture를 변경하지 않는다.
- 개발 환경 Strict Mode의 추가 render와 production performance를 구분한다.
- 최적화 전/후는 같은 interaction과 가능한 한 같은 환경에서 비교한다.

## Manual Memoization

`memo`, `useMemo`, `useCallback`은 correctness 도구가 아니라 performance optimization이다.

기본 순서:

```text
불필요한 state lift / Effect chain / broad Context update 제거
→ component ownership 정리
→ Profiler로 hotspot 확인
→ 필요한 곳만 manual memoization
```

- blanket `memo/useMemo/useCallback`을 적용하지 않는다.
- `useCallback`은 memoized child prop 또는 다른 Hook dependency처럼 identity가 실제로 필요한 경우 중심으로 사용한다.
- `useMemo`는 비싼 계산 또는 reference identity가 실제 성능 경계일 때 사용한다.
- memoization이 없어도 correctness는 유지되어야 한다.
- dependency 하나가 매번 새 값이면 memoization 전체가 무효화될 수 있음을 확인한다.

## React Compiler 1.0+

React Compiler 1.0은 stable/production-ready 자동 memoization compiler다. Component/Hook/value를 build time에 분석하여 수동 `memo`, `useMemo`, `useCallback`의 필요성을 크게 줄일 수 있다.

### 기존 프로젝트

자동 전면 도입보다 점진 도입을 우선한다.

후보:
- directory/Babel override 기반 제한 도입
- `compilationMode: 'annotation'` + `"use memo"`
- runtime `gating`을 통한 A/B rollout
- 문제가 있는 영역의 `"use no memo"` 임시 제외

### 신규 프로젝트

framework/template가 공식적으로 Compiler-enabled 설정을 제공하면 후보로 사용할 수 있다. 단, framework build tool 지원 방식이 우선이다.

### Compiler 도입 전 확인

```text
React version
framework/build tool 지원
eslint-plugin-react-hooks version
Rules of React violation 수
현재 manual memoization contract
unit/integration/e2e coverage
```

Compiler diagnostics가 있는 component는 전체 build를 실패시키기보다 해당 component/hook 최적화를 skip할 수 있으므로, 모든 lint를 한 번에 고치기보다 coverage를 점진적으로 높인다.

### Compiler와 manual memoization

- Compiler가 있더라도 기존 manual memoization을 무조건 삭제하지 않는다.
- `preserve-manual-memoization` lint와 behavior/performance evidence를 확인한다.
- 새 manual memoization은 Compiler가 최적화하지 못하는 이유와 실제 hotspot을 확인한 뒤 추가한다.
- compiler mode가 `infer/all/annotation` 중 무엇인지 확인한다.
- `"use memo"`는 annotation mode 또는 명시적 opt-in이 실제로 필요한 경우에만 사용한다.

### Compiler version pinning

E2E coverage가 충분하지 않은 기존 application에서는 compiler upgrade가 memoization behavior를 바꿀 수 있으므로 exact version pinning을 검토한다. compiler upgrade는 regression test와 함께 별도 검증한다.

## Compiler-aware ESLint

`eslint-plugin-react-hooks` 최신 계열은 기본 Rules of Hooks 외에도 React Compiler diagnostics를 제공하며 Compiler를 실제 설치하지 않아도 사용할 수 있다.

중요 진단 후보:

```text
exhaustive-deps
rules-of-hooks
component-hook-factories
error-boundaries
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

Hermes 정책:
- 기존 lint config/preset을 먼저 확인한다.
- unrelated feature에서 plugin major upgrade를 자동 수행하지 않는다.
- React optimization/migration Task에서는 `recommended` / `recommended-latest` 적용 가능성을 검토한다.
- lint suppression보다 Rules of React 위반 구조를 수정한다.
- Compiler가 특정 component 최적화를 skip한다고 해서 전체 앱이 unsafe하다고 판단하지 않는다.

## Transitions: `useTransition` / `startTransition`

Transition은 **비긴급 update를 non-blocking rendering으로 낮은 우선순위 처리**할 때 사용한다.

적합 후보:
- tab/content 전환에서 큰 subtree render
- chart/filter 결과처럼 즉시 input 반영보다 뒤에 와도 되는 화면 업데이트
- navigation-like interaction의 background render

주의:
- Transition은 계산 자체를 빠르게 만드는 것이 아니라 urgent update가 막히지 않게 한다.
- controlled text input의 state update 자체를 Transition으로 감싸지 않는다.
- pending UI가 필요하면 `useTransition`을 사용한다.
- async 이후 `setState`의 transition 범위는 현재 React limitation을 확인한다.
- 모든 state update를 Transition으로 감싸지 않는다.

## `useDeferredValue`

`useDeferredValue`는 prop/custom Hook 값에 따른 **느린 subtree update를 뒤로 미뤄 urgent UI를 responsive하게 유지**하는 데 적합하다.

대표 후보:
- 검색 input + 큰 result list
- slider/input + 무거운 chart
- 빠르게 변하는 value + 느린 visualization

주의:
- 느린 component의 계산 자체를 빠르게 만들지는 않는다.
- parent가 빠르게 rerender 가능해야 한다.
- slow subtree가 이전 value로 skip rerender할 수 있도록 component memoization/Compiler와 함께 의미가 있는지 확인한다.
- network debounce/throttle과 동일한 기능이 아니다.

## `<Activity>` (React 19.2+)

`<Activity>`는 UI를 hidden/visible 상태로 전환하면서 **state와 DOM을 보존**하고 hidden update를 낮은 우선순위로 처리할 수 있다.

적합 후보:
- 사용자가 곧 돌아올 가능성이 높은 tab/sidebar/page
- back navigation 시 입력/state 보존
- 다음 UI를 background pre-render하여 interaction latency 감소

hidden Activity는 시각적으로 숨겨지고 Effects가 unmount되므로 다음을 확인한다.
- hidden 상태에서도 반드시 살아 있어야 하는 subscription인지
- Effect cleanup/remount가 정상인지
- memory cost와 실제 navigation latency 개선이 균형적인지

단순 `display:none` 대체로 무조건 사용하지 않는다.

## Context / State Propagation

Context 값 변경은 해당 Context를 읽는 consumer render를 유발할 수 있으므로 performance 문제가 측정되면 provider 책임과 value identity를 확인한다.

우선순위:

```text
state를 더 local하게 둘 수 있는가
→ provider 범위를 줄일 수 있는가
→ 서로 다른 책임의 Context를 분리할 근거가 있는가
→ value object/function identity가 실제 hotspot인가
```

Context를 성능 이유만으로 여러 개로 기계 분할하거나 새 global store로 교체하지 않는다.

## Component Composition

wrapper component가 자체 state를 가지더라도 children JSX를 prop/children으로 받아 구조를 유지하면 불필요한 child rerender를 줄이는 데 도움이 될 수 있다.

- state owner를 가능한 낮게 둔다.
- visual wrapper가 unrelated child state까지 소유하지 않는다.
- component split은 line count가 아니라 ownership/render boundary 근거로 수행한다.

## Strict Mode

Strict Mode는 개발 환경에서 추가 render/setup-cleanup을 통해 impure render와 Effect cleanup 문제를 찾는 데 도움이 된다.

- Strict Mode 때문에 드러난 side effect bug를 memoization으로 숨기지 않는다.
- dev duplicate call과 production render count를 혼동하지 않는다.
- 기존 프로젝트에 unrelated Task로 강제 도입하지 않는다.

## Review Hotspots

React diff에서는 필요할 때 다음을 우선 확인한다.

```text
render 중 side effect/global/shared mutation
props/state 직접 mutation
일반 Hook의 conditional/dynamic 호출
use() 예외를 잘못 일반 Hook 규칙으로 수정
component 함수 직접 호출
매 render nested component 정의
redundant/duplicated/contradictory state
불필요한 state lifting / broad Context update
Effect로 render data 변환 또는 user event 처리
Effect dependency suppression / cleanup 누락
Effect 내부 synchronous setState chain
useEffectEvent를 dependency 숨김에 악용
key/type 변경에 따른 state reset
render value를 ref로 우회
Profiler 근거 없는 memo/useMemo/useCallback 남발
React Compiler와 중복되는 manual memoization
Compiler diagnostics / incompatible library 무시
Transition으로 controlled input update
useDeferredValue를 debounce 대체로 오해
Activity hidden Effect lifecycle 누락
```

## Verification / Performance Evidence

프로젝트 script와 기존 test stack을 우선한다.

```text
typecheck
lint
affected component/hook test
필요 시 integration/e2e
build
```

React performance Task에서는 가능하면 다음 evidence를 남긴다.

```text
React version
Framework/build tool
React Compiler: off | infer | all | annotation | gated
eslint-plugin-react-hooks version/preset
Measured interaction
Profiler/Performance Track finding
Before actualDuration 또는 user-visible latency
After actualDuration 또는 user-visible latency
Manual memoization decision
Transition/deferred/Activity decision
Residual risk
```

Compiler 도입/upgrade, Activity, Effect lifecycle 변경은 E2E 또는 실제 interaction regression을 포함한다.

## Primary Official Sources

- React Reference: Rules of React
- React Reference: Components and Hooks must be pure
- React Reference: Rules of Hooks (`use` exception 포함)
- React Learn: Choosing the State Structure / Sharing State / Preserving and Resetting State
- React Learn: You Might Not Need an Effect / Separating Events from Effects
- React Reference: `useEffect`, `useEffectEvent`, `useRef`
- React Reference: `memo`, `useMemo`, `useCallback`
- React Reference: `startTransition`, `useTransition`, `useDeferredValue`
- React Reference: `<Profiler>`, `<Activity>`
- React 19.2 release notes: Activity, useEffectEvent, Performance Tracks
- React Compiler 1.0 announcement
- React Compiler: Introduction / Incremental Adoption / Configuration / Directives
- React Reference: `eslint-plugin-react-hooks` compiler-aware lints
