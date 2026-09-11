# Next.js Official Practices

Next.js 공식 문서와 release guidance를 기준으로 Hermes에서 사용할 version-aware 구현/성능 판단 근거를 정리한다. 최신 기능을 모든 프로젝트에 강제하지 않는다. 항상 실제 `next`/React version, App/Pages Router, bundler, caching/rendering 설정, 배포·CI 환경, 기존 convention과 측정 근거를 먼저 따른다.

## Project Convention First

```text
사용자/Task 정책
→ 실제 Next.js / React version + Router / bundler / deployment
→ 기존 project rendering/data/cache/component convention
→ production performance evidence
→ 이 문서의 해당 version 공식 최적화 기준
```

Next.js/React/Turbopack/React Compiler/Cache Components migration은 unrelated feature/fix에 자동 포함하지 않는다.

## Current Version / Support Gate

2026년 9월 기준 공식 문서의 current 16.x line을 사용할 수 있지만 Hermes는 latest 문법을 version 확인 없이 적용하지 않는다.

```text
Next.js <= 15
→ 해당 major의 router/cache/build contract 유지
→ 16.x default/API 자동 이식 금지

Next.js 16.0 ~ 16.2
→ 해당 minor의 Turbopack/Cache Components/Proxy contract 확인

Next.js 16.3+
→ 최신 navigation/build/cache/memory 개선 사용 가능 여부 확인
→ experimental API는 별도 opt-in으로 취급
```

production에서는 프로젝트 정책과 공식 support 상태에 맞는 stable/LTS patch를 우선한다. canary를 성능 개선 기대만으로 production baseline에 사용하지 않는다.

## Measure in Production Mode

Next.js 성능은 development mode가 아니라 production 조건에서 확인하는 것을 기본으로 한다.

```text
next build
→ next start 또는 production-equivalent runtime
→ Lighthouse / Core Web Vitals / 실제 route interaction
```

개발 생산성 문제는 별도로 측정한다.

```text
next dev startup
Fast Refresh latency
next build duration
memory / OOM
```

- Lighthouse 한 번의 점수만으로 구조를 바꾸지 않는다.
- 같은 route/device/network 조건에서 before/after를 비교한다.
- 실제 Web Vitals/observability가 있으면 synthetic measurement보다 우선한다.

## Server and Client Components

App Router에서는 Server Component 경계를 기본 후보로 본다.

- browser API/event/client state/Effect가 필요한 경우에만 Client Component를 둔다.
- `"use client"`는 해당 파일뿐 아니라 그 import graph를 client boundary로 만들 수 있으므로 상위 layout/page까지 편의상 확장하지 않는다.
- server-only secret/data code를 client graph로 넘기지 않는다.
- 상호작용이 필요 없는 markdown parsing, syntax transformation, data shaping, formatting 등 무거운 작업은 server에서 수행 가능한지 먼저 확인한다.
- Client Component props는 현재 React/Next serialization contract를 따른다.

Client JS가 줄어들면 hydration/download/parse cost와 browser main-thread work를 줄일 수 있으므로 bundle 문제에서는 boundary부터 확인한다.

## Bundle Analysis

Next.js가 제공하는 현재 bundler의 analyzer를 우선 사용한다.

Turbopack 기반 current Next에서는 Next Bundle Analyzer를 사용할 수 있다.

```text
next experimental-analyze
```

분석 결과는 `.next/diagnostics/analyze` 등 현재 version의 output contract를 확인한다.

기본 순서:

```text
route/client bundle 확인
→ 큰 package/module 확인
→ Server Component로 이동 가능한 work 확인
→ import path / lazy loading 확인
→ package optimization 확인
→ 그래도 필요할 때 dependency 교체
```

bundle 크기만 보고 기능적으로 안정된 dependency를 자동 교체하지 않는다.

## Package Import Optimization

### `optimizePackageImports`

많은 named export를 가진 package에서 import 분석 비용 또는 bundle 문제가 실제로 확인될 때 검토한다.

- current Next version에서 지원하는지 확인한다.
- 모든 dependency를 등록하지 않는다.
- direct import/tree shaking이 이미 충분하면 추가 설정하지 않는다.
- before/after build/bundle evidence를 남긴다.

### `serverExternalPackages`

server dependency를 Next server bundle 밖에서 native/runtime dependency로 유지해야 할 compatibility 또는 cold-start 근거가 있을 때 검토한다.

일반 성능 플래그처럼 사용하지 않는다.

## Lazy Loading and Dynamic Import

Next는 route/server 구조를 자동 code split하므로 lazy loading은 주로 Client Component와 browser-only dependency에 집중한다.

```text
초기 화면에 필요 없음 + interaction 후 필요
→ next/dynamic / React.lazy 후보

무거운 browser-only library
→ dynamic import 후보
```

- `ssr: false`는 Client Component에서만 사용한다.
- Server Component에서 `ssr: false`를 사용하지 않는다.
- Server Component를 `next/dynamic`으로 감쌌다고 server work 자체가 client lazy chunk처럼 지연된다고 가정하지 않는다.
- critical above-the-fold UI를 bundle 숫자만 보고 lazy-load하지 않는다.
- loading fallback과 CLS/layout stability를 확인한다.

## Data Fetching and Waterfalls

독립 요청은 병렬화를 우선 검토한다.

```text
const [a, b] = await Promise.all([...])
```

실제 data dependency가 있으면 순차 호출이 맞다.

- server/client에서 같은 resource를 중복 fetch하지 않는다.
- request waterfall이 layout/page/component tree 때문에 생기는지 확인한다.
- Suspense/streaming boundary를 사용해 static/cached shell과 느린 dynamic data를 분리할 수 있는지 검토한다.
- client data library는 기존 프로젝트 pattern과 interactive cache 필요성에 따라 사용한다.

## Cache Components / Caching / Revalidation

Next 16의 Cache Components와 `use cache`는 explicit caching model을 제공하지만 기존 app의 caching semantics를 자동 migration하지 않는다.

확인 항목:

```text
cacheComponents config
`use cache`
cacheLife
cacheTag
fetch cache semantics
route/static/dynamic behavior
revalidatePath / revalidateTag / updateTag
```

- cache hit ratio만 최적화 목표로 삼지 않는다.
- user-specific/dynamic data freshness와 authorization boundary를 먼저 보장한다.
- mutation 후 실제 stale 범위에 맞춰 가장 좁게 invalidate한다.
- 모든 mutation에서 전체 route/cache invalidation 금지.
- cache strategy 변경은 behavior/consistency change로 테스트한다.

## Navigation / Prefetch / Streaming

빠른 navigation은 단순 route bundle 크기뿐 아니라 prefetch, cached shell, loading boundary와 관련된다.

기본 확인:

- shared layout
- `loading.tsx`
- Suspense boundary
- `<Link>` prefetch
- dynamic segment/data latency
- cache warm/cold state

### Instant Navigation (Next.js 16.3+)

공식 current guidance에서 Instant Navigation은 static/cached/fallback UI를 즉시 보여주고 나머지를 stream하여 perceived navigation latency를 줄이는 패턴이다.

현재 version/project가 Cache Components를 사용하고 있다면 partial prefetching/instant navigation을 검토할 수 있다.

- App Shell을 의미 있게 구성한다.
- cached/static shell과 uncached dynamic content를 Suspense로 분리한다.
- link별 `prefetch` 요구를 확인한다.
- 모든 link를 aggressive prefetch하여 network/CPU를 낭비하지 않는다.
- warm-cache navigation과 cold navigation을 구분해 검증한다.
- 공식 E2E helper/Playwright integration이 프로젝트에 적합하면 navigation 즉시성 regression에 사용할 수 있다.

experimental prefetch option은 stable behavior보다 우선하지 않는다.

## Image Optimization

`next/image`는 image sizing, optimization, lazy loading, responsive source selection을 지원한다.

- intrinsic image면 width/height로 aspect ratio를 고정한다.
- responsive/fill image에는 실제 layout에 맞는 `sizes`를 제공한다.
- `sizes`가 없어서 browser가 100vw로 가정하며 너무 큰 image candidate를 다운로드하지 않는지 확인한다.
- 실제 LCP image만 preload/eager/fetch priority를 검토한다.
- 모든 image preload 금지.
- current Next 16에서는 legacy `priority`와 current preload/fetch-priority guidance 차이를 version 기준으로 확인한다.
- remote image allowlist/security와 cache config를 유지한다.

## Font Optimization

`next/font`는 self-hosting/preload 최적화를 제공한다.

- 실제 사용하는 font family/weight/style만 로드한다.
- 필요한 subset만 지정한다.
- 여러 subset/weight를 습관적으로 preload하지 않는다.
- fallback/font-display/layout shift를 확인한다.
- design system font를 성능만으로 임의 교체하지 않는다.

## Third-party Scripts

`next/script`의 strategy를 script 중요도에 맞춘다.

```text
초기 hydration 이후 필요
→ afterInteractive 후보

초기 화면과 무관한 analytics/chat/widget
→ lazyOnload 후보
```

- critical dependency가 아닌 third-party script를 eagerly block하지 않는다.
- `worker` strategy는 current official support와 Router 제약을 확인한다.
- App Router에서 지원되지 않거나 experimental인 strategy를 production default로 사용하지 않는다.
- script 수/실행 시간이 Core Web Vitals에 미치는 영향도 확인한다.

## React Compiler

Next.js의 `reactCompiler` integration은 React skill의 Compiler policy와 함께 적용한다.

- framework-supported config를 우선한다.
- build time 증가 여부를 측정한다.
- manual memoization을 즉시 전부 삭제하지 않는다.
- compiler diagnostics/lint/test coverage를 확인한다.
- unrelated feature에서 compiler migration을 넣지 않는다.

Next 16.3 계열의 experimental Rust React Compiler path는 production stable default로 간주하지 않는다. 실험적 성능 평가 Task에서만 사용한다.

## Turbopack

Next 16에서는 Turbopack이 주요 dev/build path로 사용된다. 실제 project script/config를 확인한다.

- webpack plugin/loader가 필요한 프로젝트는 compatibility를 먼저 본다.
- Turbopack 전환을 unrelated Task에 강제하지 않는다.
- build/dev performance는 실제 command로 비교한다.

### File System Cache

16.x current line은 Turbopack filesystem cache를 dev/build에서 활용할 수 있다.

중요한 것은 cache option 존재보다 **실제 `.next/cache` persistence**다.

```text
local dev
→ 동일 workspace에서 cache 유지 확인

CI
→ ephemeral runner이면 .next/cache restore/save 여부 확인
```

cache key는 lockfile, Next config, relevant source/build inputs와 정합해야 한다. platform-managed cache가 이미 있으면 중복 cache layer를 만들지 않는다.

### Memory

Next 16.3+에는 dev/build memory 개선이 포함되어 있지만 특정 project OOM은 별도 진단한다.

공식 memory diagnostics 후보:

```text
next build --experimental-debug-memory-usage
Node heap profile
bundle analyzer
```

대형 dependency/bundle부터 확인하고 memory tuning을 진행한다.

### Experimental Memory Eviction

`turbopackMemoryEviction` 같은 experimental control은 실제 dev memory pressure가 있고 filesystem cache가 동작할 때만 검토한다.

baseline memory 문제가 없으면 자동 활성화하지 않는다.

### Experimental Chunking / Prefetch Tuning

experimental chunking/prefetch option은 initial load와 navigation trade-off를 바꿀 수 있다.

- analyzer/navigation measurement 없이 사용하지 않는다.
- production stable default보다 우선하지 않는다.
- route-specific regression을 E2E/measurement로 검증한다.

## Build Performance / CI Cache

CI에서 `.next/cache`가 보존되지 않으면 이전 build cache의 이점을 얻지 못할 수 있다.

Hermes는 build가 느릴 때 다음 순서로 본다.

```text
현재 bundler/version 확인
→ CI .next/cache persistence 확인
→ bundle/dependency 확인
→ build profiling/memory 확인
→ experimental tuning은 마지막
```

CI cache 최적화는 build correctness와 dependency freshness를 깨지 않아야 한다.

## Web Vitals / Runtime Monitoring

Lighthouse는 local investigation에 유용하지만 production regression guard로는 실제 Core Web Vitals/observability를 함께 보는 것이 좋다.

확인 후보:

```text
LCP
INP
CLS
TTFB (server/rendering 변경 시)
route navigation latency
client JS size
```

프로젝트가 이미 analytics/APM/Web Vitals collector를 사용하면 그 source를 재사용한다.

## Server Actions / Route Handlers / Security

성능 최적화 때문에 server boundary correctness를 약화하지 않는다.

Server Action:
- runtime input validation
- authentication/authorization
- narrow invalidation
- safe error response

Route Handler/API:
- `dev-api-contract` 적용 여부 확인
- existing backend business logic 중복 금지
- HTTP cache와 Next application cache를 동일하게 취급하지 않음

## Proxy / Middleware

- current version의 Proxy/Middleware contract를 확인한다.
- broad matcher로 모든 request에 불필요한 latency를 추가하지 않는다.
- auth/authz를 Proxy에만 의존하지 않는다.
- rewrite/redirect/header logic이 CDN/cache/navigation에 미치는 영향을 확인한다.

## Environment and Secrets

- server-only env와 browser-exposed env를 구분한다.
- secret을 Client Component/client JS에 포함하지 않는다.
- build-time/runtime environment contract를 deployment와 맞춘다.

## Performance Investigation Order

성능 이슈에서 무작정 config를 추가하지 않는다.

```text
1. 실제 느린 route/interaction/build를 재현
2. Server/Client boundary와 request waterfall 확인
3. Bundle Analyzer로 client dependency 확인
4. navigation/cache/Suspense 구조 확인
5. image/font/script와 Core Web Vitals 확인
6. Turbopack/cache/build/memory 진단
7. experimental option은 마지막
```

## Review Hotspots

```text
version/router 추측
production 성능을 dev mode로 평가
상위 use client로 client graph 확장
heavy dependency client 유입
bundle analysis 없는 dependency rewrite
Server Component에 잘못된 ssr:false
over-lazy-loading으로 LCP/UX 악화
불필요한 request waterfall
server/client duplicate fetch
cache freshness 오류 / broad invalidation
aggressive prefetch network waste
responsive image sizes 누락
모든 image/font preload
third-party script eager 실행
CI .next/cache 미보존
stale CI cache correctness 문제
experimental Turbopack/Rust Compiler를 production default로 사용
memory evidence 없는 eviction/chunk tuning
React Compiler와 Next Compiler config 불일치
```

## Verification / Evidence

기존 project script를 우선한다.

```text
typecheck / lint
→ affected unit/component test
→ route/page/integration test
→ 필요 시 e2e
→ next build / project build
```

성능 변경이면 가능한 범위에서 다음 evidence를 남긴다.

```text
Next.js / React version
Router / Bundler / React Compiler
Production-like measurement environment
Web Vitals / Lighthouse / navigation finding
Bundle analyzer finding
Client JS before / after
Build duration / dev startup before / after
.next/cache persistence status
Cache Components / prefetch strategy
Image / Font / Script decision
Memory diagnostics (해당 시)
Experimental options: none | name + reason
Residual risk
```

## Primary Official Sources

- Next.js Docs: App Router / Pages Router
- Next.js Docs: Server and Client Components
- Next.js Docs: Lazy Loading / `next/dynamic`
- Next.js Docs: Package Bundling / Bundle Analyzer / `optimizePackageImports`
- Next.js Docs: Fetching Data / Caching / Revalidating / Cache Components
- Next.js Docs: Prefetching / Instant Navigation
- Next.js Docs: Image / `next/image`
- Next.js Docs: Font / `next/font`
- Next.js Docs: Script / `next/script`
- Next.js Docs: CI Build Caching
- Next.js Docs: Memory Usage / Turbopack FileSystem Cache
- Next.js Docs: React Compiler / Turbopack experimental configuration
- Next.js release guidance: 16.0 / 16.1 / 16.2 / 16.3
- Next.js Docs: Core Web Vitals / production performance measurement
