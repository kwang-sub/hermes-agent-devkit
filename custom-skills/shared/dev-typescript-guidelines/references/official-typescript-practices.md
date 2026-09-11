# TypeScript Official Practices

TypeScript 공식 Handbook, TSConfig Reference, release notes와 Microsoft TypeScript 공식 Performance Wiki를 기준으로 Hermes에서 사용할 판단 근거를 정리한다. 최신 문법/설정을 기계적으로 강제하는 문서가 아니다. 항상 대상 프로젝트의 TypeScript version, framework/runtime, tsconfig, build pipeline, lint/typecheck toolchain과 기존 convention을 먼저 따른다.

## Project Convention First

```text
사용자/Task 정책
→ 현재 TypeScript version + framework/build tool + tsconfig
→ 기존 project convention / generated types / lint/typecheck contract
→ 이 문서의 version-specific safety/performance guidance
→ 공식 TypeScript 일반 권장사항
```

TypeScript upgrade, compiler option migration, project-reference 분할, 새로운 build mode 도입은 feature/fix와 분리 가능한 변경이면 자동 수행하지 않는다.

## Version Gate: 5.x / 6.x / 7.x

TypeScript는 version에 따라 compiler defaults와 지원 option이 크게 다르므로 먼저 실제 package version을 확정한다.

```text
5.x
→ 기존 compiler semantics 유지
→ 6/7 전용 default나 제거 option을 강제하지 않음

6.x
→ 7.0 전환 release
→ deprecated option과 7.0 hard-error 후보 점검

7.x
→ native compiler + parallel type-check/build
→ 6.0 deprecated option은 제거/hard error로 간주
→ 7.0 compiler defaults와 programmatic API 제약 확인
```

최신 version을 이유만으로 자동 upgrade하지 않는다. 현재 framework/plugin/linter/build tool이 compiler API를 사용하는지 확인한다.

## TypeScript 7.0 Native Compiler

TypeScript 7.0은 Go 기반 native compiler로 전환되었으며 공식 발표 기준 대규모 프로젝트 full build에서 일반적으로 TypeScript 6 대비 약 8~12배 수준의 향상을 보였다. 이는 프로젝트 코드를 무조건 변경해야 얻는 최적화가 아니라 compiler 자체 교체에서 오는 이점이다.

Hermes 정책:

```text
현재 TS 7.x
→ native compiler 성능을 baseline으로 사용

현재 TS 6.x 이하
→ upgrade가 Task 범위인지 먼저 판단
→ framework/tooling compatibility 확인
→ compatibility가 닫히지 않으면 별도 migration candidate
```

TypeScript 7.0은 7.1 이전까지 안정적인 programmatic compiler API가 없다. TypeScript compiler API를 직접 소비하는 tooling, language-server plugin, embedded language integration이 있으면 `tsc` CLI만 보고 upgrade 가능하다고 판단하지 않는다.

필요 시 TypeScript 6 compatibility package와 TypeScript 7 CLI를 side-by-side로 검증할 수 있지만, 이를 자동 package 변경으로 적용하지 않는다.

## TypeScript 7.0 Default / Migration Gate

7.0에서는 6.0의 여러 default 변경이 실제 기본값으로 적용되고, 6.0에서 deprecated였던 다수 option이 제거 또는 hard error가 된다.

### 주요 default 확인

```text
strict = true
module = esnext
target = 현재 stable ECMAScript 이전 세대
noUncheckedSideEffectImports = true
rootDir = ./
types = []
stableTypeOrdering = true (off 불가)
```

특히 `types = []` default는 workspace의 모든 `@types` package를 global scope에 자동 주입하지 않는다. 필요한 global type만 명시적으로 선택하는 것은 예측 가능성과 build performance에 도움이 된다.

```json
{
  "compilerOptions": {
    "types": ["node", "jest"]
  }
}
```

실제 프로젝트가 Jest를 쓰지 않는데 편의를 위해 전역 type을 추가하지 않는다.

### 7.0에서 제거/비지원으로 보는 대표 설정

```text
target: es5
moduleResolution: node / node10
moduleResolution: classic
module: amd / umd / systemjs / none
baseUrl
downlevelIteration
outFile
esModuleInterop: false
allowSyntheticDefaultImports: false
alwaysStrict: false
legacy namespace/module syntax 일부
import assertion의 asserts 문법
```

대체 방향:

```text
Node 직접 실행
→ moduleResolution: nodenext 후보

bundler/Next.js/Vite/Bun
→ moduleResolution: bundler 후보

paths + baseUrl
→ TS7에서는 baseUrl 제거 후 project root 기준 paths migration 검토
```

기존 framework가 tsconfig를 생성/관리한다면 framework 공식 config가 우선이다.

## strict / strictNullChecks

- `strict`는 strict family 옵션을 활성화하는 상위 플래그다.
- `strictNullChecks`가 켜지면 `null`/`undefined`는 별도 타입으로 다뤄져 사용 전에 narrowing이 필요하다.
- TypeScript 7에서는 `strict`가 기본 `true`다.
- TypeScript 5/6 기존 프로젝트에서 `strict` 또는 `strictNullChecks`가 꺼져 있으면 unrelated Task에서 자동 활성화하지 않는다.
- strict migration은 codebase 전체 compile surface와 외부 declaration 영향을 함께 평가한다.

## Additional Safety Options

다음 option은 프로젝트 성격에 따라 유용하지만 기존 프로젝트에 무조건 활성화하지 않는다.

### `useUnknownInCatchVariables`

`strict` 아래에서는 catch variable을 `unknown`으로 다루어 error shape 확인을 강제한다.

```text
외부/throw 값
→ unknown
→ instanceof / guard / decoder로 narrowing
```

catch convenience를 이유로 `any`로 되돌리는 패턴을 확산하지 않는다.

### `noUncheckedSideEffectImports`

side-effect-only import가 실제로 resolve되는지 확인한다.

```ts
import "./styles.css";
```

CSS/asset loader처럼 bundler가 처리하는 import는 module declaration 또는 framework toolchain과 함께 검증한다. TypeScript 7에서는 기본 `true`이므로 upgrade 시 asset import 오류가 새로 드러날 수 있다.

### `noImplicitReturns`

모든 code path가 명시적으로 값을 반환해야 하는 함수에서 누락을 잡는다. 기존 프로젝트에 활성화하면 광범위한 오류가 생길 수 있으므로 신규 프로젝트 baseline 또는 별도 strictness migration 후보로 본다.

### `noFallthroughCasesInSwitch`

의도하지 않은 `switch` fallthrough를 잡는다. finite state/reducer/domain code에서 유용하지만 기존 style과 intentional empty case를 확인한다.

### `noImplicitOverride`

class inheritance가 많은 codebase에서 base member와 override의 drift를 줄인다. React/functional frontend처럼 class 사용이 거의 없으면 우선순위가 낮다.

### `noPropertyAccessFromIndexSignature`

index signature에서 실제 선언된 property와 dynamic key 접근 의도를 구분한다. dynamic dictionary 사용이 많은 프로젝트에서는 migration 비용이 있을 수 있다.

### `exactOptionalPropertyTypes` / `noUncheckedIndexedAccess`

- 둘 다 강한 correctness 옵션이지만 legacy codebase에서 오류 surface가 크다.
- 기존 프로젝트에 자동 활성화하지 않는다.
- 신규 프로젝트/별도 strictness migration에서는 API/nullability semantics와 함께 검토한다.

## `unknown` vs `any`

공식 Handbook 기준:

- `any`는 타입 검사를 사실상 opt-out하며 downstream으로 전파된다.
- `unknown`은 어떤 값도 받을 수 있지만 사용 전 narrowing을 요구한다.

따라서 JSON parse 결과, postMessage, storage, untyped library, catch/boundary data 등 shape가 확인되지 않은 외부 값에는 `unknown`을 우선 검토한다.

`any` 허용 후보:
- legacy JS/third-party declaration interoperability
- 타입 시스템으로 현실적으로 표현하기 어려운 bounded adapter
- 외부 type defect를 격리하는 좁은 boundary

`any`를 domain/component/service 내부로 전파하지 않는다.

## Narrowing

TypeScript의 control-flow analysis와 다음 narrowing을 우선 사용한다.

```text
typeof
instanceof
in operator
literal equality
null/undefined check
truthiness (의미가 정확할 때만)
user-defined type predicate
assertion function
```

`as` assertion이나 non-null assertion(`!`)으로 narrowing을 건너뛰지 않는다.

## Discriminated Union / Exhaustiveness

고정된 UI/request 상태, async result, reducer action 등에는 공통 literal discriminant를 가진 union을 적극 검토한다.

```ts
type LoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: Data }
  | { status: "error"; error: Error };
```

이 방식은 boolean flag 조합으로 불가능한 상태를 줄이고 narrowing을 돕는다.

단, compiler performance 관점에서 수십~수백 개 member를 가진 거대한 union 또는 union 간 교차를 만드는 type-level design은 비용이 커질 수 있다. 대형 union이 실제 hotspot이면 공통 base type/subtype 모델을 검토한다.

## Type Assertion / Non-null Assertion

`as SomeType`과 postfix `!`는 runtime validation이 아니다.

금지에 가까운 패턴:
- API response mismatch 숨김
- nullable state 확인 없이 `!`
- `as unknown as T`로 임의 변환
- compile error를 없애기 위한 광범위 assertion

DOM/library contract처럼 compiler가 충분히 표현하지 못하는 bounded case에서는 runtime invariant가 명확할 때만 최소 범위로 사용한다.

## `satisfies`

`satisfies`는 값이 특정 contract를 만족하는지 검사하면서 더 구체적인 inferred type을 유지할 때 유용하다.

후보:
- configuration object
- route/meta map
- literal registry
- finite state mapping

프로젝트 version 지원 여부를 먼저 확인하며 단순 `as` replacement로 기계 적용하지 않는다.

## Optional Property / null / undefined

- `prop?: T`, `prop: T | undefined`, `prop: T | null`을 동일 의미로 취급하지 않는다.
- backend/API contract가 field omission과 explicit `null` 중 무엇을 사용하는지 구분한다.
- generated OpenAPI/client type이 있으면 hand-written duplicate type으로 재정의하지 않는다.
- `exactOptionalPropertyTypes`가 켜진 프로젝트에서는 property 부재와 explicit `undefined` 차이를 보존한다.

## Interface / Type Alias

언어 설계 관점에서는 `interface`와 `type` 모두 정상적인 도구이며 기존 project convention을 우선한다.

단, 공식 Performance Wiki 기준 compiler hotspot이 확인된 복합 object composition에서는 다음을 검토할 수 있다.

```text
interface Foo extends Bar, Baz
```

이 방식은 큰 intersection type보다 type relationship caching에 유리할 수 있다.

정책:
- 단순 object type을 style 이유로 모두 interface로 바꾸지 않는다.
- union/intersection/conditional/mapped type이 필요한 곳은 `type`이 자연스럽다.
- 성능 개선 목적 refactor는 trace/evidence가 있을 때 적용한다.

## Easy-to-Compile Type Design

공식 TypeScript Performance guidance에서 대규모 codebase의 checker 비용을 줄이는 후보로 제시하는 패턴을 필요할 때 적용한다.

### Named Complex Types

반복되는 복잡한 conditional/mapped type expression은 이름 있는 type alias로 추출하면 compiler가 관계 결과를 cache하기 쉬워질 수 있다.

```text
거대한 inline conditional type가 반복됨
→ named alias 후보
```

### Base Type over Huge Union

member가 매우 많은 union을 매 호출마다 비교해야 하는 구조는 비용이 커질 수 있다.

```text
거대한 exhaustive union
→ 공통 base interface + subtype 구조가 의미상 맞는지 검토
```

작은 discriminated union까지 성능 이유로 해체하지 않는다.

### Targeted Type Annotations

Type inference는 기본적으로 유지한다. 다만 declaration emit 또는 compiler trace에서 특정 exported function의 anonymous inferred type 계산이 hotspot이면 명시적 return type이 compiler work를 줄일 수 있다.

모든 local 변수/함수에 annotation을 추가하는 식의 blanket optimization은 하지 않는다.

## Module / Import Semantics

- 현재 runtime/bundler에 맞는 `module` / `moduleResolution`을 사용한다.
- TypeScript 7에서 Node 직접 실행은 `nodenext`, bundler 기반 app은 `bundler`를 우선 후보로 본다.
- 기존 framework가 generated/recommended tsconfig를 제공하면 그 구성이 우선이다.
- `baseUrl`은 TypeScript 7에서 비지원이므로 7.x migration 시 반드시 점검한다.

### `verbatimModuleSyntax`

`verbatimModuleSyntax`는 type-only import/export와 runtime import를 명확히 구분하고 emit semantics를 예측 가능하게 만들 수 있다.

그러나 third-party emitter/bundler가 TypeScript가 가정한 module kind와 다른 output을 만들면 부적합할 수 있다.

```text
framework/bundler config + package.json type + tsconfig module semantics가 정합
→ 검토 가능

정합성 불명확
→ 자동 활성화 금지
```

`import type`은 project lint/compiler convention과 실제 runtime side-effect 요구를 따른다.

## Build Performance: Incremental

`incremental`은 이전 compilation의 project graph 정보를 `.tsbuildinfo`에 저장해 후속 build 비용을 줄일 수 있다.

```text
이미 incremental 사용
→ 유지

반복 tsc/typecheck가 큰 프로젝트
→ build tool과 충돌하지 않는지 확인 후 후보
```

캐시 파일 위치와 CI cache 정책을 기존 project build 시스템과 맞춘다.

## Build Performance: Project References

Project references + `composite` + `tsc -b`는 큰 codebase/monorepo에서 typecheck/build memory와 시간을 줄이고 logical boundary를 강제할 수 있다.

하지만 프로젝트를 나누는 것 자체에도 비용이 있으므로 작은 단일 Next.js app에 자동 적용하지 않는다.

적용 후보:
- 실제 monorepo package graph가 존재
- client/server/shared처럼 독립 build boundary가 존재
- editor가 너무 많은 파일을 한 project로 로드
- compiler trace에서 project scale이 병목임이 확인됨

공식 performance guidance는 일반적인 multi-project workspace에서 과도하게 많은 project로 쪼개는 것도 비용이 있다고 설명한다. 실제 repository 구조를 따라 균형 있게 나눈다.

## TypeScript 7 Parallel Build Controls

TypeScript 7은 parsing/type-checking/emitting을 native multithreading으로 수행하며 추가 control을 제공한다.

```text
--checkers N
→ type-check worker 수
→ 증가 시 CPU 사용/속도 증가 가능, memory 증가 가능

--builders N
→ `tsc --build` project reference builder 병렬 수
→ checkers와 곱해져 concurrency가 커질 수 있음

--singleThreaded
→ debugging / 제한된 resource / 외부 orchestrator가 parallelism을 관리하는 경우
```

Hermes 정책:
- default 값을 먼저 baseline으로 측정한다.
- local/CI machine core와 memory를 모르는 상태에서 worker 수를 자동 증가하지 않는다.
- CI runner가 memory constrained면 checker 수 감소가 더 나을 수 있다.
- `checkers × builders`의 총 concurrency를 고려한다.
- tuning은 benchmark evidence와 함께 별도 performance change로 처리한다.

## `isolatedDeclarations`

`isolatedDeclarations`는 declaration emit을 병렬화 가능한 구조로 만들기 위한 기반이 될 수 있으며 TypeScript 7 project-reference build와 결합 시 잠재적 장점이 있다.

적합 후보:
- library/package가 `.d.ts`를 실제 산출
- 대규모 monorepo
- declaration build가 병목

일반 application/Next.js frontend에 단순 성능 이유로 자동 적용하지 않는다. annotation 증가 등 developer ergonomics trade-off가 있으므로 case-by-case로 판단한다.

## `skipLibCheck`

`skipLibCheck`는 `.d.ts` type checking을 생략해 compile time을 줄일 수 있지만 type-system accuracy를 희생한다.

정책:
- 이미 프로젝트에서 사용 중이면 유지하되 의미를 인지한다.
- duplicate/incompatible dependency types가 원인이면 가능한 경우 dependency resolution을 먼저 고친다.
- 성능 숫자 없이 `skipLibCheck: true`를 최적화 기본값으로 추가하지 않는다.
- strictness/correctness audit에서 이 옵션의 residual risk를 기록한다.

## `types` Scope

불필요한 `@types` package를 global scope에 모두 포함하면 project loading/type checking 비용이 늘 수 있다.

```text
실제로 필요한 global types만 compilerOptions.types에 명시
```

TypeScript 7은 이를 기본 `[]`로 변경했다. 기존 5/6 project에서는 framework/test runtime 요구와 migration impact를 먼저 확인한다.

## Performance Investigation Before Refactoring

느리다는 이유만으로 type architecture를 먼저 바꾸지 않는다. 공식 TypeScript tooling으로 원인을 확인한다.

우선 후보:

```text
tsc --showConfig
→ 실제 merged tsconfig 확인

tsc --extendedDiagnostics
→ files/types/check time/memory 등 확인

tsc --listFilesOnly
→ 예상 밖 file 포함 여부 확인

tsc --explainFiles
→ file이 왜 project에 포함됐는지 확인

tsc --traceResolution
→ module/type resolution 병목 진단

tsc --generateTrace <dir>
→ compiler hotspot trace 생성
```

진단 결과에 따라:

```text
잘못된 include/glob
→ config 수정

과도한 global @types
→ types scope 제한

한 project가 지나치게 큼
→ project references 검토

복잡 type hotspot
→ interface/base type/named conditional type 등 targeted refactor

compiler 자체 병목 + compatible
→ TypeScript 7 migration 검토
```

## Review Hotspots

TypeScript diff에서는 필요할 때 다음을 우선 확인한다.

```text
신규 any / any propagation
runtime validation 없는 외부 data assertion
as unknown as T
nullable 값에 대한 근거 없는 !
불가능한 state 조합
exhaustiveness 누락
optional / null / undefined contract mismatch
exactOptionalPropertyTypes semantics 무시
noUncheckedIndexedAccess를 assertion으로 우회
side-effect import resolution 누락
TS7에서 제거된 compiler option
TS7 types/rootDir default 영향 누락
baseUrl / node10 / classic legacy module resolution
framework/tooling API 호환성 확인 없는 TS7 upgrade
거대한 intersection/union/conditional type hotspot
불필요한 global @types inclusion
근거 없는 skipLibCheck / parallel worker tuning
```

## Verification / Evidence

프로젝트가 제공하는 script를 우선한다.

```text
typecheck
lint
affected test
필요 시 build
```

compiler/tsconfig 변경이면 project-wide typecheck/build를 포함한다.

performance 변경이면 가능하면 before/after를 같은 환경에서 비교한다.

```text
TypeScript version
Typecheck command
Before duration / After duration
Peak memory 또는 extendedDiagnostics (가능한 경우)
Project references / incremental / parallel settings
```

## Handoff

필요할 때 다음을 남긴다.

```text
Skill: dev-typescript-guidelines
Detected TypeScript version
Version Lane: TS5 | TS6_TRANSITION | TS7_NATIVE
Framework / TypeScript API Consumers
Compiler defaults / migration risks
module / moduleResolution / rootDir / types
strict / strictNullChecks
useUnknownInCatchVariables
exactOptionalPropertyTypes
noUncheckedIndexedAccess
noUncheckedSideEffectImports
Additional safety option decisions
Runtime Validation Boundary
Type / State Modeling Decision
Type complexity/performance hotspots
Incremental / Project References
TS7 checkers/builders policy
skipLibCheck status / residual risk
API type strategy
Intentional deviations
Verification / Performance evidence
```

## Primary Official Sources

- TypeScript Handbook: Everyday Types / Narrowing / Unions and Intersections
- TypeScript TSConfig Reference
- TypeScript 6.0 Release Notes / Announcement
- TypeScript 7.0 Announcement
- TypeScript Handbook: Project References
- Microsoft TypeScript Wiki: Performance
- TSConfig references for `strict`, `strictNullChecks`, `useUnknownInCatchVariables`, `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`, `noUncheckedSideEffectImports`, `noImplicitOverride`, `noImplicitReturns`, `noFallthroughCasesInSwitch`, `noPropertyAccessFromIndexSignature`, `verbatimModuleSyntax`, `incremental`, `skipLibCheck`
