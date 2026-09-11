---
name: dev-nextjs-feature
description: Next.js 구현에서 실제 version/router를 감지하고 Server/Client boundary·bundle·navigation·cache·asset·Turbopack·build 성능을 공식 version-aware 기준으로 최적화하는 capability skill.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, nextjs, performance, bundle, navigation, cache, image, font, script, turbopack, server-component]
    related_skills: [dev-typescript-guidelines, dev-frontend-guidelines, dev-frontend-test, dev-api-contract, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-nextjs-feature

Next.js 전용 구현/성능 capability다. React 렌더링 최적화는 `dev-frontend-guidelines`, TypeScript compiler 최적화는 `dev-typescript-guidelines`가 담당한다. 최신 Next.js 기능을 기계적으로 도입하지 않고 실제 version/router/config/배포 환경과 측정 근거를 우선한다.

상세 공식 근거는 필요할 때 `references/official-nextjs-practices.md`를 읽는다.

## 우선순위

```text
사용자/Task 정책
→ 실제 Next.js/React version + Router/config + 배포 환경
→ 기존 project rendering/data/cache/component convention
→ production 성능 evidence
→ 이 Skill의 version-aware Next.js 규칙
→ 공식 Next.js 권장사항
```

Next.js/React/Turbopack/Compiler/Cache Components migration을 unrelated Task에 자동 포함하지 않는다.

## Version Lane

작업 전 실제 `next` version을 확인한다.

```text
Next.js <= 15
→ 해당 version의 router/cache/bundler contract 유지
→ 16.x API/기본값 자동 이식 금지

Next.js 16.0 ~ 16.2
→ Turbopack/Cache Components/Proxy 등 해당 minor의 공식 contract 확인

Next.js 16.3+
→ 16.3 navigation/build/cache/memory 개선을 사용할 수 있는지 확인
→ experimental option은 별도 evidence가 있을 때만
```

production은 프로젝트 정책과 공식 support 상태에 맞는 stable/LTS patch를 우선하고 canary를 성능 이유만으로 사용하지 않는다.

## 작업 전 확인

- `next`, `react`, `react-dom` 실제 version
- App Router / Pages Router / 혼합
- `next.config.*`
- dev/build bundler: Turbopack / webpack
- React Compiler 설정
- Cache Components / `use cache`
- route/layout/loading/Suspense/prefetch convention
- Client Component boundary
- image/font/script usage
- dynamic import / heavy client dependency
- CI `.next/cache` persistence
- build/test/e2e/Web Vitals 또는 기존 observability

## Measure First

Next.js 성능 변경은 가능한 한 측정 후 적용한다.

사용자 체감 성능:

```text
production build
→ production-like server/runtime
→ Lighthouse / Web Vitals / route interaction
```

개발/빌드 성능:

```text
next dev startup / Fast Refresh
next build duration
peak memory / OOM 여부
bundle analyzer
```

- development mode Lighthouse를 production 성능 근거로 사용하지 않는다.
- 최적화 전/후 같은 route/interaction/build 조건을 비교한다.
- 단일 synthetic 숫자만으로 architecture를 변경하지 않는다.

## Server / Client Boundary and Client JS Budget

App Router에서는 Server Component 경계를 기본 후보로 본다.

- browser API/event/client state/Effect가 필요한 최소 영역에만 `"use client"`를 둔다.
- 상위 layout/page에 편의상 `"use client"`를 올려 client module graph를 넓히지 않는다.
- server-only secret/resource code를 client graph로 넘기지 않는다.
- markdown/syntax transform/data shaping 등 상호작용이 필요 없는 무거운 작업은 server에서 처리 가능한지 먼저 본다.
- 동일 데이터를 server와 client에서 이유 없이 이중 fetch하지 않는다.

Client JS가 성능 병목이면 dependency를 임의 교체하기 전에 bundle evidence를 확보한다.

## Bundle Analysis / Package Optimization

Next.js가 제공하는 현재 version의 bundle analyzer를 우선 사용한다.

```text
bundle size 문제
→ route/client bundle 분석
→ 큰 dependency/import path 확인
→ client boundary 축소
→ lazy loading / package import 최적화 검토
→ 필요할 때만 dependency 교체
```

### `optimizePackageImports`

export 수가 매우 많은 package가 실제 import/build 병목일 때 검토한다.

- 프로젝트/Next version 지원 확인
- 임의 package 전체를 목록에 추가하지 않는다.
- 기존 direct import/tree shaking이 충분하면 변경하지 않는다.

### `serverExternalPackages`

server dependency를 Next server bundling에서 제외해야 하는 compatibility/native/cold-start 근거가 있을 때만 사용한다.

성능 옵션처럼 무조건 추가하지 않는다.

## Lazy Loading / Dynamic Import

Server Components는 framework가 code splitting하므로 Client Component/브라우저 전용 무거운 dependency를 중심으로 lazy loading을 검토한다.

```text
사용자 interaction 후 필요한 Client Component
→ next/dynamic 또는 React.lazy 후보

초기 route에 필요 없는 heavy browser library
→ dynamic import 후보
```

- `ssr: false`는 Client Component 경계에서만 사용한다.
- Server Component를 dynamic import했다고 server execution 자체가 일반 client lazy chunk처럼 늦춰진다고 가정하지 않는다.
- critical above-the-fold UI를 단순 bundle 크기 때문에 과도하게 lazy-load하지 않는다.
- lazy boundary 추가 후 loading UX와 layout shift를 확인한다.

## Navigation / Prefetch / Streaming

navigation 최적화는 실제 Router/version과 route 특성을 기준으로 한다.

기본 확인:

- `loading.tsx` / Suspense boundary
- shared layout/static shell
- `<Link>` prefetch 동작
- dynamic segment/data latency
- back/forward state 기대

### Next.js 16.3+ Instant Navigation

현재 프로젝트가 Cache Components 기반이고 해당 version을 사용할 때 partial/instant navigation 최적화를 검토할 수 있다.

- existing cache model을 먼저 확인한다.
- static/cached shell과 dynamic content의 boundary를 명확히 한다.
- per-link `prefetch` 정책을 network/data 특성에 맞게 조정한다.
- 모든 route에 aggressive prefetch를 자동 활성화하지 않는다.
- navigation 성능은 실제 warm/cold cache 조건을 구분해 검증한다.

experimental prefetch/chunk option은 공식 stable default보다 우선하지 않는다.

## Data Fetching / Waterfall

```text
독립 요청
→ 병렬 실행 가능성 검토

선행 결과가 필요한 요청
→ dependency waterfall 허용

server-only data
→ server boundary 우선

interactive client cache
→ 기존 client data layer 사용
```

- 순차 `await`가 실제 dependency가 아닌데 waterfall을 만드는지 확인한다.
- 같은 resource를 여러 layer에서 중복 호출하지 않는다.
- Suspense/streaming은 데이터 dependency와 UX에 맞게 배치한다.

## Cache / Revalidation / Cache Components

cache는 performance option이면서 freshness contract다.

- 현재 `fetch` cache, `use cache`, `cacheLife`, `cacheTag`, route rendering mode를 확인한다.
- Cache Components는 프로젝트가 이미 사용하거나 명시 migration Task일 때 적용한다.
- mutation 후 stale 범위에 맞춰 가장 좁은 invalidation을 사용한다.
- `revalidatePath`, `revalidateTag`, `updateTag`는 version/current contract를 확인한다.
- 전체 route/cache 무효화를 편의상 반복하지 않는다.
- dynamic/user-specific data를 장기 cache하는 오류를 만들지 않는다.

## Mutation / Server Action / Route Handler

Server Action은 기본 API 대체재로 강제하지 않는다.

사용 시:
- input validation
- authentication/authorization
- narrow revalidation/redirect/error handling
- secret/internal error 비노출

Route Handler/API contract가 생기면 `dev-api-contract` 적용 여부를 확인한다.

기존 backend가 소유한 business logic을 Next server layer에 중복 구현하지 않는다.

## Image Optimization

이미지 성능은 Core Web Vitals와 client bandwidth에 직접 영향을 줄 수 있으므로 기존 asset pattern을 먼저 본다.

`next/image` 사용 시:
- 실제 layout에 맞는 width/height 또는 `fill` contract 유지
- responsive/fill 이미지에는 실제 viewport layout을 반영한 `sizes` 검토
- `sizes` 누락으로 과도하게 큰 image candidate가 내려가지 않는지 확인
- LCP 이미지만 preload/eager/fetch priority를 검토
- 모든 이미지 preload 금지
- Next 16에서는 legacy `priority` 사용 여부와 현재 권장 API를 version 기준으로 확인
- remote image config/security boundary 유지

이미지 품질/format config를 unrelated feature에서 일괄 변경하지 않는다.

## Font Optimization

`next/font` 또는 프로젝트 font strategy를 우선한다.

- 실제 사용하는 font family/weight/style만 로드한다.
- 필요한 subset만 preload한다.
- 여러 weight/font를 편의상 모두 preload하지 않는다.
- layout shift와 fallback behavior를 확인한다.

기존 design system font를 성능 이유만으로 임의 교체하지 않는다.

## Third-party Script Optimization

`next/script` 또는 기존 script loader contract를 확인한다.

```text
critical interaction 전 필요
→ 기존 before/afterInteractive 근거 확인

초기 화면과 무관한 analytics/widget
→ lazyOnload 후보
```

- third-party script를 일반 `<script>`로 되돌려 최적화를 잃지 않는다.
- `worker` strategy는 현재 Router/version의 stable 지원 여부를 확인한다.
- App Router에서 지원되지 않는/experimental script strategy를 production 기본으로 쓰지 않는다.

## React Compiler Integration

React Compiler 성능 정책은 `dev-frontend-guidelines`를 따른다.

Next.js 측에서는:
- `reactCompiler` 설정 및 Next/framework 지원 확인
- Compiler가 build time에 미치는 영향도 측정
- existing manual memoization을 무조건 제거하지 않음
- Compiler 도입을 unrelated Next feature와 묶지 않음

Next/Turbopack의 experimental Rust React Compiler는 stable production default로 취급하지 않는다.

## Turbopack Dev / Build Performance

Next 16+에서 Turbopack이 현재 project default인지 확인한다.

- 기존 webpack-specific plugin/loader compatibility를 무시하고 강제 전환하지 않는다.
- dev startup/Fast Refresh/build 성능은 실제 command로 비교한다.
- filesystem cache가 활성화된 version에서는 cache directory persistence가 실제 환경에서 유지되는지 확인한다.

### CI `.next/cache`

CI가 ephemeral이면 `.next/cache`를 적절히 persist/restore할 수 있는지 확인한다.

- cache key는 lockfile/config/source 변화 정책과 맞춘다.
- stale artifact correctness보다 cache hit를 우선하지 않는다.
- 이미 CI/platform이 Next cache를 관리하면 중복 layer를 만들지 않는다.

### Experimental Turbopack options

다음은 measured diagnostic/migration Task에서만 검토한다.

```text
turbopack memory eviction
experimental chunking
Rust React Compiler
prefetch-related experimental switches
```

공식 stable default보다 먼저 production에 적용하지 않는다.

## Memory Investigation

build/dev OOM 또는 높은 memory가 실제 문제일 때만 진단한다.

순서:

```text
큰 dependency / client bundle 확인
→ bundle analyzer
→ Next memory diagnostics
→ Node heap profile 필요 여부
→ experimental memory option 검토
```

Next가 제공하는 `--experimental-debug-memory-usage` 또는 현재 version의 memory diagnostic을 사용할 수 있다.

메모리 문제 없이 experimental eviction을 미리 활성화하지 않는다.

## Proxy / Middleware

- 현재 version의 `proxy` / `middleware` contract를 확인한다.
- broad matcher로 모든 request에 불필요한 server work를 추가하지 않는다.
- auth/authz는 Proxy 하나에만 의존하지 않는다.
- redirect/rewrite/header 변경이 cache/navigation에 주는 영향도 검토한다.

## Environment / Secrets

- public/server env 경계를 유지한다.
- secret을 Client Component props/client bundle에 전달하지 않는다.
- build-time/runtime env 차이를 실제 deployment 기준으로 확인한다.

## Review Hotspots

```text
version/router 추측
production 성능을 dev mode로 측정
불필요한 use client 확장
큰 dependency가 client bundle에 유입
bundle evidence 없는 dependency rewrite
lazy loading이 critical UI를 지연
ssr:false를 Server Component에서 오용
server/client 중복 fetch 또는 불필요한 waterfall
과도한 prefetch / cache invalidation
현재 version과 다른 cache/navigation API
responsive image의 sizes 누락
모든 image/font preload
third-party script eager loading
CI .next/cache 미보존 또는 stale cache 오용
experimental Turbopack option의 production 기본화
React Compiler/Rust compiler 상태 혼동
memory evidence 없는 eviction tuning
```

## Verification / Performance Evidence

기존 project script를 우선한다.

```text
typecheck/lint
affected unit/component test
route/page/integration test
필요 시 e2e
next build / project build
```

성능 변경이면 가능한 범위에서 다음을 남긴다.

```text
Next.js / React version
Router mode
Bundler: Turbopack | webpack
React Compiler mode
Production route/interaction measured
Web Vitals / Lighthouse evidence
Client bundle finding / before-after
Build duration / dev startup (해당 시)
.next/cache persistence
Navigation/prefetch/cache model
Image/font/script decision
Memory evidence (해당 시)
Experimental options: none | list + reason
Residual risk
```

routing/cache/navigation/bundle/client-boundary 변경은 정적 검사만으로 완료 판단하지 않는다.

## Handoff

```text
Skill: dev-nextjs-feature
Detected Next.js / React version lane
Router / Bundler / Compiler mode
Server/Client boundary
Bundle/Lazy-loading decision
Data fetching / waterfall decision
Cache/Revalidation model
Navigation/Prefetch strategy
Image/Font/Script decision
Build/CI cache decision
Memory/Turbopack tuning
Security/Auth boundary
Verification / performance evidence
```
