---
name: dev-typescript-guidelines
description: TypeScript 구현에서 대상 프로젝트의 실제 version·tsconfig·framework/tooling contract를 우선하고 공식 Handbook/TSConfig/Performance 기준의 strictness·module·type modeling·build 성능 최적화를 적용하는 공통 capability skill.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, typescript, frontend, guidelines, convention, strict, narrowing, discriminated-union, performance, ts7, project-references]
    related_skills: [dev-implement-plan, dev-project-pattern, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract]
    requires_tools: [terminal]
---

# dev-typescript-guidelines

TypeScript 작업에 추가 적용하는 공통 규칙이다. `coding-rules.md`, `implementation-decision-rules.md`, 대상 프로젝트 convention을 반복하거나 대체하지 않는다.

상세 공식 근거와 version별 판단은 필요할 때만 `references/official-typescript-practices.md`를 읽는다.

## 우선순위

```text
사용자/Task 명시 정책
→ 실제 TypeScript version / framework / build tool / tsconfig
→ 기존 project convention / generated types / lint/typecheck contract
→ 이 Skill의 TypeScript 전용 correctness/performance 규칙
→ 공식 TypeScript 권장사항
```

최신 TypeScript 기능이나 compiler option을 쓰기 위해 package/tsconfig를 자동 upgrade하지 않는다.

## 작업 전 확인

- `package.json`, lockfile, 실제 TypeScript version
- framework/runtime(Next.js/Vite/Node/Bun 등)과 build tool
- compiler API/plugin을 직접 사용하는 tooling 여부
- `tsconfig*.json`의 `strict`, `strictNullChecks`, `useUnknownInCatchVariables`, `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`, `noUncheckedSideEffectImports`
- `module`, `moduleResolution`, `target`, `rootDir`, `types`, `paths`, legacy option 여부
- `incremental`, `composite`, project references, declaration emit 여부
- `skipLibCheck` 사용 여부
- type/interface/type alias/enum/discriminated union/conditional type 사용 패턴
- import alias와 barrel export 사용 여부
- nullable/optional data 표현
- API type 생성/수동 선언 방식 및 runtime validation boundary
- lint/format/test/typecheck/build script

## Version Gate

먼저 version lane을 확정한다.

```text
TS5
→ 기존 semantics 유지

TS6_TRANSITION
→ 7.0 migration 영향과 deprecated option 점검

TS7_NATIVE
→ native compiler / changed defaults / removed options / parallel controls 확인
```

TypeScript 7 migration은 framework/plugin/build tool compatibility를 먼저 닫는다. compiler API를 직접 사용하는 tooling이 있으면 CLI 성공만으로 upgrade 가능하다고 판단하지 않는다.

## TypeScript 7 Gate

TypeScript 7 프로젝트에서는 다음을 명시적으로 확인한다.

```text
strict default
module / target default
noUncheckedSideEffectImports
types default scope
rootDir default
stableTypeOrdering
removed/deprecated legacy options
```

특히 다음 legacy 설정은 migration hotspot이다.

```text
target: es5
moduleResolution: node/node10/classic
AMD/UMD/SystemJS/none
baseUrl
downlevelIteration
outFile
esModuleInterop: false
allowSyntheticDefaultImports: false
```

현재 runtime/bundler에 맞춰 `nodenext` 또는 `bundler` 등 실제 project contract를 따른다.

## Strictness Gate

```text
신규 프로젝트
→ strict baseline 후보
→ strictNullChecks 적극 권장

기존 TS5/6 프로젝트에서 strict OFF
→ unrelated Task에서 자동 활성화 금지
→ 별도 migration 영향 분석

exactOptionalPropertyTypes / noUncheckedIndexedAccess
→ correctness 이점 큼
→ 기존 프로젝트에는 opt-in migration으로 취급
```

추가 safety option은 프로젝트 성격에 맞게 검토한다.

```text
useUnknownInCatchVariables
noUncheckedSideEffectImports
noImplicitReturns
noFallthroughCasesInSwitch
noImplicitOverride
noPropertyAccessFromIndexSignature
```

전체 codebase surface를 넓게 바꾸는 option은 local feature/fix와 섞지 않는다.

## `unknown` vs `any`

- shape가 확인되지 않은 외부 값은 `unknown`을 우선 검토한다.
- `unknown`은 narrowing/validation 근거를 둔다.
- `any`는 편의상 추가하지 않는다.
- legacy JS/third-party declaration 결함 등 불가피하면 좁은 adapter/boundary에 격리한다.
- domain/component/service 내부로 `any`를 퍼뜨리지 않는다.

## Narrowing

TypeScript control-flow narrowing을 우선한다.

```text
typeof
instanceof
in
literal equality
null/undefined check
user-defined type predicate
assertion function
```

- `as` assertion이나 non-null assertion(`!`)로 narrowing을 건너뛰지 않는다.
- truthiness narrowing은 `""`, `0`, `false`가 실제 유효값인지 확인한다.
- 외부 데이터는 compile-time annotation만으로 신뢰하지 않는다.

## Discriminated Union / Exhaustiveness

고정된 상태 집합은 literal discriminant union을 우선 검토한다.

```text
loading/success/error UI state
async result
reducer action
domain/API result variant
finite workflow state
```

- variant별 required field가 다르면 discriminated union으로 불가능한 상태를 줄인다.
- exhaustive check가 중요하면 `never` 기반 검사를 검토한다.
- 기존 public API enum/schema를 style 이유로 바꾸지 않는다.
- member가 매우 많은 union이 checker hotspot이면 공통 base type/subtype 구조를 검토할 수 있다.

## Type Assertion / Non-null Assertion

`as T`와 `!`는 runtime validation이 아니다.

금지에 가까운 사용:

```text
API response mismatch 숨김
nullable state 확인 없이 !
as unknown as T
compile error 제거용 광범위 assertion
```

bounded DOM/library invariant처럼 실제 runtime 근거가 명확할 때만 최소 범위로 사용한다.

## `satisfies`

project version이 지원하면 configuration object, route/meta registry, literal mapping, finite state mapping 등에 검토한다.

단순 `as` replacement로 기계 적용하지 않는다.

## Optional / null / undefined

- `prop?: T`, `prop: T | undefined`, `prop: T | null`을 동일 의미로 취급하지 않는다.
- backend/API contract의 field omission과 explicit `null`을 구분한다.
- generated client/schema type이 있으면 hand-written duplicate type을 만들지 않는다.
- `exactOptionalPropertyTypes`가 켜진 프로젝트에서는 property 부재와 explicit `undefined` 차이를 보존한다.

## Type Design Performance

성능 문제 증거가 있을 때만 compiler-friendly type refactor를 적용한다.

### Interface vs Intersection

복합 object composition에서 큰 intersection보다 `interface extends`가 relationship caching에 유리할 수 있다.

```text
trace/diagnostic에서 intersection hotspot 확인
→ interface hierarchy 후보
```

style 이유로 전체 codebase를 interface로 바꾸지 않는다.

### Named Complex Types

반복되는 거대한 conditional/mapped type expression은 이름 있는 alias로 추출해 compiler가 관계 결과를 재사용하게 할 수 있다.

### Huge Union

수십~수백 member의 union이 실제 checker hotspot이면 공통 base type 구조를 검토한다. 작은 discriminated union은 유지한다.

### Targeted Return Type Annotation

exported API/declaration emit에서 거대한 anonymous inferred type 계산이 hotspot이면 명시적 return type을 검토한다.

모든 함수에 annotation을 추가하는 blanket optimization은 금지한다.

## Module / Import

- 현재 runtime/bundler에 맞는 `module` / `moduleResolution`을 사용한다.
- framework가 공식/recommended tsconfig를 관리하면 그것을 우선한다.
- TypeScript 7에서는 `baseUrl` migration을 점검한다.
- 기존 path alias와 import ordering을 따른다.
- barrel export를 사용하지 않는 프로젝트에 새 `index.ts` 체계를 도입하지 않는다.

### `verbatimModuleSyntax`

module semantics가 framework/bundler와 정합할 때 type/runtime import를 명확히 하는 후보가 될 수 있다.

```text
package.json type + bundler + tsconfig module semantics 확인
→ 정합하면 검토
→ 불명확하면 자동 활성화 금지
```

## Build Performance

### Incremental

반복 typecheck/build가 큰 프로젝트에서는 `incremental`과 `.tsbuildinfo` 재사용을 검토한다.

- 이미 사용하는 build tool cache와 충돌하지 않아야 한다.
- CI cache 정책과 파일 위치를 명시한다.

### Project References

큰 monorepo 또는 명확한 package/build boundary에서는 project references + `composite` + `tsc -b`를 검토한다.

적용 후보:

```text
실제 package graph 존재
client/server/shared boundary 존재
한 TS project가 지나치게 많은 파일 로드
compiler diagnostics에서 project scale 병목 확인
```

작은 단일 Next.js application을 성능 명분만으로 쪼개지 않는다.

### TypeScript 7 Parallelism

TS7에서 다음 control을 performance tuning 후보로 본다.

```text
--checkers N
--builders N
--singleThreaded
```

- default baseline을 먼저 측정한다.
- CPU/core/memory를 모르는 상태에서 worker 수를 자동 증가하지 않는다.
- `checkers × builders` 총 concurrency를 고려한다.
- memory constrained CI에서는 worker 감소가 더 나을 수 있다.

### `isolatedDeclarations`

library/monorepo에서 declaration emit이 실제 병목일 때만 검토한다. 일반 Next.js app에는 자동 적용하지 않는다.

### `skipLibCheck`

성능 이점과 정확성 trade-off가 있으므로 기본 최적화로 새로 켜지 않는다.

```text
현재 사용 중
→ 유지 가능, residual risk 기록

새로 도입 제안
→ dependency/type 문제를 먼저 해결 가능한지 확인
→ before/after 성능 근거 요구
```

### `types` Scope

불필요한 global `@types` inclusion을 줄인다.

- 실제 필요한 global type만 `compilerOptions.types`에 두는 방식을 검토한다.
- TypeScript 7 default 변화와 framework/test runtime 요구를 함께 확인한다.

## Performance Investigation

느린 typecheck를 추측으로 고치지 않는다.

우선 공식 compiler diagnostics를 사용한다.

```text
tsc --showConfig
tsc --extendedDiagnostics
tsc --listFilesOnly
tsc --explainFiles
tsc --traceResolution
tsc --generateTrace <dir>
```

진단 결과로 원인을 분류한다.

```text
잘못된 include/glob
→ tsconfig 범위 수정

과도한 global @types
→ types scope 제한

project 규모 병목
→ project references 검토

복잡 type checker hotspot
→ targeted type refactor

compiler 자체 병목 + tooling compatible
→ TypeScript 7 migration 후보
```

## Review Hotspots

```text
신규 any / any propagation
runtime validation 없는 외부 data assertion
as unknown as T
근거 없는 !
불가능한 state 조합
optional/null/undefined contract mismatch
strict option을 assertion으로 우회
side-effect import resolution 누락
TS7 제거 option
TS7 types/rootDir/default 영향 누락
baseUrl/node10/classic legacy module resolution
compiler API compatibility 확인 없는 TS7 upgrade
거대한 intersection/union/conditional type hotspot
불필요한 global @types inclusion
근거 없는 skipLibCheck
근거 없는 checkers/builders tuning
```

## Verification / Evidence

기존 script를 우선한다.

```text
typecheck
lint
affected test
build
```

compiler/tsconfig 변경이면 project-wide typecheck/build를 포함한다.

performance 변경이면 가능하면 같은 환경에서 before/after를 비교한다.

```text
TypeScript version
Version Lane
Typecheck command
Before / After duration
extendedDiagnostics 또는 memory evidence (가능한 경우)
Incremental / Project References
Parallel settings
```

Handoff에는 필요할 때 다음을 남긴다.

```text
Skill: dev-typescript-guidelines
Detected TypeScript version
Version Lane: TS5 | TS6_TRANSITION | TS7_NATIVE
Framework / TypeScript API Consumers
module / moduleResolution / target / rootDir / types
strict / strictNullChecks
useUnknownInCatchVariables
exactOptionalPropertyTypes
noUncheckedIndexedAccess
noUncheckedSideEffectImports
Runtime Validation Boundary
Type complexity/performance hotspots
Incremental / Project References
TS7 checkers/builders policy
skipLibCheck / residual risk
API type strategy
Intentional deviations
Verification / Performance evidence
```
