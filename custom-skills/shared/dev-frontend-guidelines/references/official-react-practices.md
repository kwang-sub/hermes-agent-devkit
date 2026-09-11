# React Official Practices

React 공식 문서의 Rules of React, Learn, Hooks Reference를 기준으로 Hermes에서 사용할 React 판단 근거를 정리한다. 이 문서는 최신 문법이나 새로운 React 기능을 모든 프로젝트에 강제하지 않는다. 항상 대상 프로젝트의 React version, framework/runtime, compiler/lint 설정, 기존 component/state/data-fetching convention을 먼저 따른다.

## Project Convention First

```text
사용자/Task 정책
→ 현재 React/framework version + build/compiler/lint 설정
→ 기존 project component/state/data-fetching/style convention
→ 이 문서의 React 공식 권장사항
```

React Compiler, 최신 Hook, 새로운 렌더링 기능을 사용하기 위해 React/framework/package를 unrelated Task에서 자동 upgrade하지 않는다.

## Components and Hooks must be pure

React의 핵심 전제는 Component와 Hook의 render 계산이 순수해야 한다는 것이다.

- 같은 props/state/context 입력에 대해 render 결과가 예측 가능해야 한다.
- render 중 외부 상태를 변경하거나 side effect를 실행하지 않는다.
- props와 state를 직접 mutate하지 않는다.
- Hook에 전달한 값이나 JSX에 전달한 값을 render 이후 임의 mutate하지 않는다.
- 화면 변경은 기존 값을 mutate하기보다 state setter나 프로젝트의 상태 변경 경계를 사용한다.
- Component 함수를 일반 함수처럼 직접 호출하지 않고 JSX/React 렌더링 경계를 사용한다.

local calculation을 위한 새 객체/배열 생성처럼 render 내부에서 생성되고 외부에 공유되지 않는 값은 mutation 자체가 목적이 아니라 계산 구현 세부로 볼 수 있다. 반대로 module/global/shared object를 render 중 변경하는 것은 피한다.

## Rules of Hooks

Hook은 일반 helper가 아니라 React render lifecycle에 연결된 호출이다.

- Hook은 function component 또는 custom Hook의 top level에서 호출한다.
- loop, condition, nested function, event handler, try/catch/finally 안에서 Hook 호출 순서를 바꾸지 않는다.
- 일반 utility 함수에서 Hook을 호출하지 않는다.
- Hook 자체를 일반 값처럼 전달하거나 동적으로 조합하는 패턴을 새로 만들지 않는다.
- 기존 lint 설정에 React Hooks 규칙이 있으면 우회하지 않는다.

조건부 동작이 필요하면 Hook 호출 자체를 조건부로 만들기보다 Hook 내부/반환값/렌더링 구조를 기존 패턴에 맞게 설계한다.

## State Structure

state는 최소한의 canonical source만 보관하고 계산 가능한 값은 render에서 파생하는 것을 우선한다.

```text
props/state로 계산 가능
→ derived value

사용자 입력이나 시간에 따라 독립적으로 변함
→ state 후보

여러 component가 같은 값을 함께 제어
→ 가장 가까운 공통 owner로 lift 검토
```

다음 상태 구조를 피한다.

- 서로 모순될 수 있는 여러 boolean/state flag
- props나 다른 state에서 바로 계산 가능한 redundant state
- 같은 entity/value의 duplicate state
- update가 어려운 불필요한 deep nesting
- object 전체를 state에 보관하면서 동일 entity의 다른 copy도 별도로 보관하는 구조

한 데이터 조각에는 가능한 한 하나의 source of truth를 둔다. 다만 모든 상태를 전역으로 올리라는 의미가 아니며 가장 가까운 실제 owner를 우선한다.

## Preserving and Resetting State

React state는 JSX 태그 문자열이 아니라 render tree에서 component의 위치/identity와 연결된다.

- 같은 위치와 component identity를 유지하면 state가 보존되는 것이 기본이다.
- 다른 component type이나 key 변경은 state reset을 유발할 수 있다.
- form/detail/editor reset이 요구되면 key를 명시적으로 사용하는 방법을 검토할 수 있다.
- component 정의를 다른 component 내부에 중첩해서 accidental reset을 만드는 패턴을 피한다.
- list key는 단순 warning 제거가 아니라 identity contract로 취급한다.

## Events vs Effects

Effect는 React 바깥의 external system과 동기화하기 위한 escape hatch로 취급한다.

Effect가 기본 해법이 아닌 경우:

```text
render용 데이터 변환
→ render에서 계산

사용자 click/submit 등 특정 interaction에 대한 작업
→ event handler

props/state 변화에 따라 다른 state를 그대로 복제
→ derived state / state structure 재검토
```

Effect가 적합한 후보:

- browser/non-React API와 subscription 동기화
- timer/listener/connection의 setup-cleanup
- project가 client Effect 기반으로 운영하는 외부 data synchronization
- third-party widget lifecycle 연결

Effect를 사용할 때:

- setup과 cleanup을 대칭적으로 구성한다.
- dependency를 숨기기 위해 lint rule을 무시하거나 임의 omission하지 않는다.
- object/function dependency 때문에 반복 실행된다면 먼저 component 구조와 dependency 생성 위치를 검토한다.
- Effect 안에서 state를 변경하고 그 state가 다시 Effect dependency를 바꾸는 cycle을 경계한다.
- async/network Effect는 stale result/race/cleanup에 대한 기존 project pattern을 따른다.

## Refs

ref는 렌더링에 직접 필요하지 않은 mutable value나 imperative handle에 사용하는 escape hatch다.

적합 후보:

- DOM element 접근
- timer/subscription handle
- render를 유발할 필요가 없는 외부 instance/reference

주의:

- 화면에 보여야 하는 값은 state를 우선한다.
- 일반 render flow에서 `ref.current`를 읽고 쓰며 UI 계산을 우회하지 않는다.
- ref를 state management 대체재처럼 확장하지 않는다.
- imperative DOM 조작은 React ownership과 충돌하지 않는 좁은 boundary에서 사용한다.

## Memoization and React Compiler

`memo`, `useMemo`, `useCallback`은 correctness 도구가 아니라 performance optimization으로 취급한다.

- memoization이 없어도 동작이 올바르게 유지되어야 한다.
- 단순히 모든 component/callback/value를 안정화하려고 blanket memoization하지 않는다.
- 실제 expensive calculation, child render pressure, dependency stabilization 같은 근거가 있을 때 적용한다.
- 기존 profiler/performance evidence가 있으면 우선 사용한다.

React Compiler가 설정된 프로젝트에서는 compiler가 값/함수/component 최적화를 담당할 수 있으므로 기존 compiler mode와 프로젝트 정책을 먼저 확인한다.

```text
Compiler configured
→ 기존 compiler mode/directive/eslint contract 유지
→ manual memoization 추가 필요성을 별도 판단

Compiler not configured
→ 현재 feature/fix를 이유로 자동 도입 금지
```

새 React Compiler 설정이나 directive를 단순 최적화 기대만으로 unrelated Task에 추가하지 않는다.

## Local State / Context / External Store

상태 도구 선택은 범위와 기존 프로젝트 구조를 따른다.

```text
component-local interaction
→ local state

가까운 subtree 공유
→ lift state / existing Context 검토

기존 application store가 이미 책임을 소유
→ 기존 store 재사용

새 global state library
→ 기존 수단으로 해결하기 어려운 근거가 있을 때만 제안
```

Context를 prop 전달 회피만을 이유로 모든 값을 전역화하는 수단으로 사용하지 않는다.

## Component Boundaries

component 분리는 line count가 아니라 책임과 UI/state ownership을 기준으로 판단한다.

분리 근거 후보:

- 독립된 UI 책임
- 명확한 재사용 경계
- state/effect ownership 분리
- 테스트 경계
- performance boundary

작은 component 수를 늘리는 것 자체를 품질로 보지 않는다.

## Strict Mode and Lint

React 공식 문서는 Rules of React 위반을 찾기 위해 Strict Mode와 React ESLint 규칙 사용을 권장한다.

Hermes 정책:

- 이미 설정된 Strict Mode와 eslint-plugin-react-hooks/React 관련 규칙을 유지한다.
- Strict Mode에서 개발 중 추가 render/setup-cleanup이 발생할 수 있음을 고려해 side effect 문제를 수정한다.
- 기존 프로젝트에 Strict Mode/lint plugin을 unrelated Task에서 자동 도입하지 않는다.
- lint warning을 없애기 위해 Effect dependency나 Hook 구조를 의미 없이 왜곡하지 않는다.

## Review Hotspots

React diff에서는 필요할 때 다음을 우선 확인한다.

```text
render 중 side effect / shared mutation
props/state 직접 mutation
conditional/dynamic Hook 호출
component 함수 직접 호출
redundant / duplicated / contradictory state
Effect로 render data 변환 또는 event 처리
Effect dependency 숨김 / cleanup 누락
state identity를 깨는 key/type 변경
render value를 ref로 우회
근거 없는 memo/useMemo/useCallback 남발
React Compiler 설정을 고려하지 않은 중복 최적화
불필요한 Context/global store 확대
```

## Verification

프로젝트가 제공하는 script와 기존 test stack을 우선한다.

```text
typecheck
→ lint
→ affected component/hook test
→ 필요한 integration/e2e
→ 필요 시 build
```

상태 보존/reset, Effect lifecycle, async interaction처럼 runtime behavior가 중요한 변경은 정적 typecheck/lint만으로 완료 판단하지 않는다.

## Primary Official Sources

- React Reference: Rules of React
- React Reference: Components and Hooks must be pure
- React Reference: Rules of Hooks
- React Learn: Keeping Components Pure
- React Learn: Choosing the State Structure
- React Learn: Sharing State Between Components
- React Learn: Preserving and Resetting State
- React Learn: You Might Not Need an Effect
- React Reference: `useEffect`
- React Reference: `useRef`
- React Reference: `useMemo`, `useCallback`, `memo`
- React Compiler Reference
