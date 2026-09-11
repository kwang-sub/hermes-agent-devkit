# TypeScript Official Practices

TypeScript 공식 Handbook, TSConfig Reference, release notes를 기준으로 Hermes에서 사용할 판단 근거를 정리한다. 최신 문법/설정을 기계적으로 강제하는 문서가 아니다. 항상 대상 프로젝트의 TypeScript version, tsconfig, framework/runtime, 기존 convention을 먼저 따른다.

## Project Convention First

```text
사용자/Task 정책
→ 현재 TypeScript version + tsconfig
→ 기존 project convention / generated types / lint contract
→ 공식 TypeScript 권장사항
```

TypeScript 6.0은 TypeScript 7.0 native compiler 전환을 준비하는 transition release다. 기존 프로젝트를 6.0/7.0으로 자동 upgrade하거나 deprecated option을 unrelated 작업에서 일괄 정리하지 않는다.

## strict / strictNullChecks

- `strict`는 strict family 옵션을 활성화하는 상위 플래그이며 TypeScript가 향후 더 엄격한 검사를 추가할 수 있다.
- `strictNullChecks`가 켜지면 `null`/`undefined`는 별도 타입으로 다뤄져 사용 전에 narrowing이 필요하다.
- 신규 프로젝트에서는 `strict`를 기본 후보로 보고, 최소한 `strictNullChecks`를 강하게 권장한다.
- 기존 프로젝트에서 `strict` 또는 `strictNullChecks`가 꺼져 있으면 Task 범위 밖에서 자동 활성화하지 않는다. 활성화는 migration 영향 분석이 필요한 별도 결정이다.

## unknown vs any

공식 Handbook 기준:

- `any`는 타입 검사를 사실상 opt-out하며 property/function 접근이 전파된다.
- `unknown`은 어떤 값도 받을 수 있지만 사용 전 narrowing을 요구한다.

따라서 JSON parse 결과, postMessage, storage, untyped library, catch/boundary data 등 **shape가 확인되지 않은 외부 값**에는 `unknown`을 우선 검토한다.

`any` 허용 후보:
- 프로젝트의 기존 declaration/legacy JS interoperability
- 타입 시스템으로 현실적으로 표현하기 어려운 bounded adapter
- third-party type 결함을 격리하는 좁은 boundary

`any`를 domain/component 내부로 전파하지 않는다.

## Narrowing

TypeScript의 control-flow analysis와 다음 narrowing을 우선 사용한다.

```text
typeof
instanceof
in operator
literal equality
truthiness (의미가 정확할 때만)
user-defined type predicate
assertion function
```

`as` assertion이나 non-null assertion(`!`)으로 narrowing을 건너뛰지 않는다.

## Discriminated Union

고정된 UI/request 상태, async result, reducer action 등에는 공통 literal discriminant를 가진 union을 적극 검토한다.

예:

```ts
type LoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: Data }
  | { status: "error"; error: Error };
```

이 방식은 boolean flag 조합으로 불가능한 상태를 만들지 않게 하고 `switch`/if narrowing을 돕는다.

exhaustiveness가 중요한 domain/UI state에서는 `never` 기반 exhaustive check를 검토한다.

## Type Assertion / Non-null Assertion

`as SomeType`과 postfix `!`는 runtime validation이 아니다.

허용 후보:
- DOM/library API의 실제 contract를 compiler가 표현하지 못하지만 runtime invariant가 명확함
- 테스트 fixture / bounded adapter에서 명시적이고 안전한 contract가 있음

금지에 가까운 패턴:
- API response mismatch 숨김
- nullable 상태를 확인하지 않고 `!`
- `as unknown as T`로 임의 변환
- compile error를 없애기 위한 광범위 assertion

외부 데이터는 assertion보다 runtime schema/guard/decoder의 기존 project pattern을 우선한다.

## satisfies

`satisfies`는 값이 특정 타입 계약을 만족하는지 검사하면서 원래 값의 더 구체적인 inferred type을 유지할 때 유용하다.

후보:
- configuration object
- route/meta map
- literal registry
- discriminated mapping

`as` assertion 대체용으로 무조건 사용하지 않고, 프로젝트 TypeScript version 지원 여부를 먼저 확인한다.

## exactOptionalPropertyTypes

`exactOptionalPropertyTypes`가 켜지면 `prop?: T`는 property가 없거나 `T` 값인 경우를 의미하고, `prop: undefined`를 자동 허용하지 않는다.

- 이 옵션은 `strict` family에 포함되지 않으며 별도 opt-in이다.
- `strictNullChecks`가 필요하다.
- absent와 explicit `undefined`를 구분하는 API/state에서는 의미가 크다.
- 기존 codebase에서는 대량 오류와 API type 의미 변경을 만들 수 있으므로 자동 활성화 금지.

## noUncheckedIndexedAccess

`noUncheckedIndexedAccess`를 켜면 index signature/array-style 접근 결과에 `undefined` 가능성이 추가되어 존재 여부 확인을 강제한다.

- dictionary/map-like data에 유용한 strictness 옵션이다.
- 기존 프로젝트에 자동 활성화하지 않는다.
- 신규 프로젝트에서는 project/framework compatibility를 확인하고 검토한다.

## Optional Property / null / undefined

- `prop?: T`와 `prop: T | undefined`는 완전히 같은 의미로 취급하지 않는다.
- backend contract가 `null`을 전달하는지, field omission을 사용하는지 구분한다.
- UI 내부 상태에서 `null`/`undefined` convention을 하나로 바꾸기 위해 unrelated migration을 하지 않는다.
- generated OpenAPI/client type이 있으면 임의로 hand-written shape를 재정의하지 않는다.

## Interface / Type Alias

공식 TypeScript는 `interface`와 `type`을 모두 정상적인 도구로 제공한다.

- 기존 project convention을 우선한다.
- union/intersection/conditional/mapped type이 필요하면 `type`이 자연스럽다.
- object contract/extension이 project convention상 interface이면 유지한다.
- 단순 취향으로 전체 codebase를 한 방식으로 변환하지 않는다.

## enum / Literal Union

`enum`과 string literal union은 runtime emission/interop 요구가 다르다.

- 기존 API/serialization/runtime enum 사용을 존중한다.
- 단순 finite UI state에는 literal union을 검토할 수 있다.
- public API contract의 enum representation을 style 목적으로 변경하지 않는다.

## TypeScript 6.0 Transition

TypeScript 6.0은 7.0 전환을 위해 여러 오래된 compiler option/module 방식을 deprecated 처리했다.

대표적으로:
- `target: es5`
- `moduleResolution: node` / `node10`
- `moduleResolution: classic`
- AMD/UMD/SystemJS module target
- `baseUrl`
- `downlevelIteration`
- 일부 legacy namespace/module option

Hermes 정책:

```text
발견
→ 현재 build가 정상인지 확인
→ upgrade/migration task라면 영향 분석
→ unrelated feature/fix에서는 자동 수정 금지
```

`ignoreDeprecations`를 단순히 경고 숨김용으로 자동 추가하지 않는다.

## Verification

프로젝트가 제공하는 script를 우선한다.

```text
npm/pnpm/yarn/bun run typecheck
→ lint
→ affected test
→ 필요 시 build
```

TypeScript 설정 변경은 전체 compile surface에 영향을 줄 수 있으므로 `tsconfig` strictness 변경 시 최소 affected test만으로 완료 판단하지 않는다.

## Primary Official Sources

- TypeScript Handbook: Everyday Types / Basic Types / Narrowing / Unions and Intersections
- TypeScript TSConfig Reference: `strict`, `strictNullChecks`, `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`
- TypeScript release notes: TypeScript 4.4 (`exactOptionalPropertyTypes`), TypeScript 4.9 (`satisfies`), TypeScript 6.0 transition/deprecations
