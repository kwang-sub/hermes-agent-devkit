---
name: dev-typescript-guidelines
description: TypeScript 구현에서 대상 프로젝트의 TypeScript version·tsconfig·strictness·type 배치·import·nullability convention을 우선하고 공식 Handbook/TSConfig 기준의 narrowing·union·assertion·strictness 규칙을 적용하는 공통 capability skill.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, typescript, frontend, guidelines, convention, strict, narrowing, discriminated-union, satisfies]
    related_skills: [dev-implement-plan, dev-project-pattern, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract]
    requires_tools: [terminal]
---

# dev-typescript-guidelines

TypeScript 작업에 추가 적용하는 공통 규칙이다. `coding-rules.md`, `implementation-decision-rules.md`, 대상 프로젝트 convention을 반복하거나 대체하지 않는다.

상세 공식 근거와 compiler option별 판단은 필요할 때만 `references/official-typescript-practices.md`를 읽는다.

## 우선순위

```text
사용자/Task 명시 정책
→ 대상 프로젝트의 TypeScript version / tsconfig / 기존 convention
→ 이 Skill의 TypeScript 전용 규칙
→ 공식 TypeScript Handbook/TSConfig 권장사항
```

최신 TypeScript 기능이나 stricter compiler option을 쓰기 위해 package/tsconfig를 자동 upgrade하지 않는다.

## 작업 전 확인

- `package.json`, lockfile, 실제 TypeScript version
- `tsconfig*.json`의 `strict`, `strictNullChecks`, `noImplicitAny`, `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`
- module/target/moduleResolution/path alias 및 TypeScript 6.0 deprecated option 여부
- type/interface/type alias/enum/discriminated union 사용 패턴
- import alias와 barrel export 사용 여부
- nullable/optional data 표현
- API type 생성/수동 선언 방식 및 runtime validation boundary
- lint/format/test/typecheck script

## Strictness Gate

```text
신규 프로젝트
→ `strict: true` 기본 후보
→ 최소한 `strictNullChecks` 적극 권장

기존 프로젝트에서 strict/strictNullChecks OFF
→ 현재 Task에서 자동 활성화 금지
→ migration 영향 분석이 필요한 별도 결정

exactOptionalPropertyTypes / noUncheckedIndexedAccess
→ 별도 opt-in strictness
→ 기존 프로젝트에 자동 활성화 금지
```

compiler option 변경은 codebase 전체 compile surface에 영향을 줄 수 있으므로 단순 local refactor로 취급하지 않는다.

## `unknown` vs `any`

- shape가 확인되지 않은 외부 값은 `unknown`을 우선 검토한다.
- `unknown`은 사용 전에 narrowing/validation 근거를 둔다.
- `any`는 타입 검사를 opt-out하고 downstream으로 전파되므로 편의상 추가하지 않는다.
- legacy JS/third-party declaration 결함 등 `any`가 불가피하면 좁은 adapter/boundary에 격리한다.
- domain/component/service 내부로 `any`를 퍼뜨리지 않는다.

## Narrowing

TypeScript의 control-flow narrowing을 우선한다.

```text
typeof
instanceof
in
literal equality
null/undefined check
user-defined type predicate
assertion function
```

- `as` assertion이나 postfix non-null assertion(`!`)로 narrowing을 건너뛰지 않는다.
- truthiness narrowing은 `""`, `0`, `false`가 실제로 유효한 값인지 확인한다.
- runtime validation이 필요한 외부 데이터는 compile-time type annotation만으로 신뢰하지 않는다.

## Discriminated Union / Exhaustiveness

고정된 상태 집합을 boolean flag 여러 개로 표현하기보다 literal discriminant를 가진 union을 우선 검토한다.

후보:

```text
loading/success/error UI state
async result
reducer action
domain/API result variant
finite workflow state
```

- variant별 required field가 다르면 discriminated union으로 불가능한 상태를 줄일 수 있다.
- exhaustive `switch`가 중요한 경우 `never` 기반 exhaustive check를 검토한다.
- 기존 public API enum/schema를 단순 style 이유로 union으로 바꾸지 않는다.

## Type Assertion / Non-null Assertion

`as T`와 `!`는 runtime validation이 아니다.

금지에 가까운 사용:

```text
API response mismatch 숨김
nullable state 확인 없이 `!`
`as unknown as T`로 임의 변환
compile error 제거용 광범위 assertion
```

DOM/library contract처럼 compiler가 충분히 표현하지 못하는 bounded case에서는 실제 runtime invariant가 명확할 때만 최소 범위로 사용한다.

## `satisfies`

프로젝트 TypeScript version이 지원하면 `satisfies`는 객체가 특정 contract를 만족하는지 검사하면서 literal/inferred type을 유지할 때 검토한다.

적합 후보:

```text
configuration object
route/meta registry
literal mapping
finite state mapping
```

단순 `as` 대체 문법으로 기계적으로 사용하지 않는다.

## Optional / null / undefined

- `prop?: T`, `prop: T | undefined`, `prop: T | null`을 동일 의미로 취급하지 않는다.
- backend/API contract가 field omission과 explicit `null` 중 무엇을 사용하는지 확인한다.
- generated OpenAPI/client type이 있으면 hand-written duplicate type으로 재정의하지 않는다.
- `exactOptionalPropertyTypes`가 켜진 프로젝트에서는 optional property의 **부재**와 explicit `undefined` 차이를 보존한다.

## `noUncheckedIndexedAccess`

- 활성화된 프로젝트에서는 index signature/array-style access 결과의 `undefined` 가능성을 실제로 처리한다.
- `!` 또는 assertion으로 옵션 효과를 상쇄하지 않는다.
- 비활성 기존 프로젝트에 unrelated 작업으로 자동 활성화하지 않는다.

## Interface / Type Alias / Enum

- `interface`와 `type`은 기존 project convention을 우선한다.
- union/intersection/conditional/mapped type에는 `type`이 자연스럽다.
- object contract extension을 interface로 운영하는 프로젝트라면 유지한다.
- `enum`과 literal union은 runtime emission/API serialization 요구가 다르므로 style만으로 상호 변환하지 않는다.

## TypeScript 6.0 Transition

TypeScript 6.0+ 프로젝트에서는 7.0 준비를 위한 deprecated compiler option/module 방식을 확인할 수 있다.

예:

```text
target: es5
moduleResolution: node/node10/classic
AMD/UMD/SystemJS
baseUrl
downlevelIteration
legacy namespace/module 설정
```

- migration Task라면 영향과 대체 방식을 검토한다.
- unrelated feature/fix에서 자동 정리하지 않는다.
- 단순히 경고를 숨기기 위해 `ignoreDeprecations`를 자동 추가하지 않는다.

## 타입 배치

```text
한 component/module 내부 구현 세부
→ local type 검토

여러 component/use case에서 공유
→ 프로젝트의 shared/domain/api type 위치 재사용

Backend API contract를 표현
→ dev-api-contract와 기존 client/schema generation 방식 확인
```

새 `types/` 디렉터리를 편의상 만들지 않는다.

## Import / Module

- 기존 path alias와 import ordering을 따른다.
- 프로젝트가 barrel export를 사용하지 않으면 새 `index.ts` 체계를 도입하지 않는다.
- `import type`은 기존 lint/compiler 설정과 TypeScript version을 따른다.
- TypeScript 6.0 deprecated module option을 발견해도 unrelated 작업에서 module system을 자동 migration하지 않는다.

## Review Hotspots

TypeScript diff에서는 필요할 때 다음을 우선 확인한다.

```text
신규 `any` 또는 any propagation
runtime validation 없는 외부 data assertion
`as unknown as T`
nullable 값에 대한 근거 없는 `!`
boolean flag로 표현된 불가능한 state 조합
exhaustiveness 누락
optional / null / undefined contract mismatch
exactOptionalPropertyTypes semantics 무시
noUncheckedIndexedAccess를 assertion으로 우회
unrelated strict/compiler option/package upgrade
TypeScript 6.0 deprecated option 자동 변경
```

## Verification / Evidence

가능하면 기존 script를 우선한다.

```text
typecheck
lint
affected test
build
```

`tsconfig` strictness/compiler option 변경은 전체 compile surface에 영향을 주므로 project-wide typecheck/build 영향 범위를 확인한다.

Handoff에는 필요할 때 다음을 남긴다.

```text
Skill: dev-typescript-guidelines
Detected TypeScript version
tsconfig/strictness
strictNullChecks: on | off
exactOptionalPropertyTypes: on | off
noUncheckedIndexedAccess: on | off
Runtime Validation Boundary
Type / State Modeling Decision
Type placement convention
API type strategy
Intentional deviations
Verification
```
