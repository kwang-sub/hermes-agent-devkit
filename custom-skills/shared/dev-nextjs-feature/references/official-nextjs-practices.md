# Next.js Official Practices

Next.js 공식 문서를 기준으로 Hermes에서 사용할 version-aware 구현 판단 근거를 정리한다. 이 문서는 최신 Next.js 기능을 모든 프로젝트에 강제하지 않는다. 항상 대상 프로젝트의 실제 `next` version, App/Pages Router, React version, caching/rendering 설정, 배포 환경과 기존 convention을 먼저 따른다.

## Project Convention First

```text
사용자/Task 정책
→ 실제 Next.js / React version + Router mode
→ 기존 project rendering/data/cache/auth convention
→ 이 문서의 해당 version 공식 권장사항
```

최신 Next.js, React, Turbopack, React Compiler, Cache Components를 사용하기 위해 unrelated Task에서 package/config를 자동 upgrade하지 않는다.

## Version and Router Gate

작업 전에 최소 다음을 확인한다.

- `next` / `react` / `react-dom` 실제 version
- App Router(`app/`) / Pages Router(`pages/`) / 혼합 여부
- `next.config.*` 관련 설정
- Server/Client Component 사용 패턴
- 기존 caching/revalidation 방식
- Server Action / Route Handler / API Route 사용 여부
- middleware/proxy 사용 여부와 version
- build/dev script와 bundler 설정

App Router의 현재 문법을 Pages Router에 기계적으로 적용하거나 그 반대도 하지 않는다.

## Server and Client Components

App Router에서는 Server Component가 기본 경계다.

- browser API, event handler, client state/Effect가 필요한 경우에만 Client Component 경계를 둔다.
- `"use client"`를 편의상 page/layout 상단까지 확장하지 않는다.
- Client Component로 import되는 module graph는 client bundle 경계에 포함될 수 있으므로 server-only secret/data code를 넘기지 않는다.
- server에서 가능한 data fetching/secure resource access를 단순 습관 때문에 client Effect로 이동하지 않는다.
- Client Component에 넘기는 props는 해당 React/Next version의 serialization contract를 만족해야 한다.
- third-party client-only component는 필요한 최소 wrapper/boundary로 격리한다.

## Request APIs and Version Differences

Next.js는 major version에 따라 request-time API contract가 바뀔 수 있다.

- `params`, `searchParams`, `cookies()`, `headers()` 등의 sync/async 여부를 현재 version 공식 문서에서 확인한다.
- 최신 예제를 오래된 프로젝트에 그대로 복사하지 않는다.
- migration Task가 아니면 version migration을 기능 구현과 섞지 않는다.
- deprecation warning을 숨기기 위한 임시 cast나 compatibility shim을 근거 없이 추가하지 않는다.

## Data Fetching

App Router에서는 Server Component에서 필요한 데이터를 직접 읽을 수 있는지 먼저 검토한다.

```text
server-only resource / DB / internal service
→ Server Component 또는 server boundary

browser interaction 후 client cache가 필요한 데이터
→ 기존 client data library/pattern 검토

외부 consumer도 필요한 HTTP contract
→ Route Handler/API/backend contract 검토
```

- 동일 데이터를 server와 client에서 이유 없이 중복 fetch하지 않는다.
- 독립적인 요청은 waterfall을 만들지 않도록 기존 구조 안에서 병렬화 가능성을 검토한다.
- Suspense/streaming/loading boundary는 실제 UX와 프로젝트 패턴을 기준으로 둔다.
- data library를 단순 최신 관례 때문에 추가하지 않는다.

## Caching and Revalidation

Caching은 **현재 Next.js version과 project 설정**을 기준으로 판단한다.

Next.js 16 계열에서는 Cache Components와 `use cache` 기반 모델을 사용할 수 있지만, 기존 프로젝트가 이전 caching 모델을 사용한다면 자동 전환하지 않는다.

확인 항목:

```text
Cache Components 사용 여부
fetch/cache option
`use cache`
cacheLife / cacheTag
revalidatePath / revalidateTag / updateTag
route/static/dynamic rendering contract
```

- cached/uncached 여부를 추측하지 않는다.
- mutation 후 어떤 데이터가 stale 되는지 기준으로 가장 좁은 revalidation 범위를 사용한다.
- 캐시 무효화를 누락해 stale UI를 만들지 않는다.
- 반대로 모든 mutation마다 전체 route/cache를 광범위하게 무효화하지 않는다.
- caching 의미 변경은 성능뿐 아니라 data freshness contract 변경으로 취급한다.

## Mutations and Server Actions

Server Action은 HTTP/API 설계를 무조건 대체하는 기본값이 아니다. 기존 프로젝트 경계를 우선한다.

사용 시:

- server-only 실행을 전제로 한다.
- 모든 action input을 신뢰하지 않고 validation/authentication/authorization을 수행한다.
- UI에서 버튼을 숨긴 것만으로 authorization을 대체하지 않는다.
- mutation 후 필요한 revalidation/redirect/error path를 명시한다.
- error message에 secret/internal detail을 노출하지 않는다.
- action module 배치는 기존 project convention을 따른다.

외부 client/mobile/다른 backend도 contract를 사용해야 하면 Route Handler 또는 별도 backend API가 더 적절할 수 있다.

## Route Handlers / API Boundary

- method/path/response/error/auth contract가 생기면 `dev-api-contract` 적용 여부를 확인한다.
- Route Handler에서 secret/server resource를 client bundle로 이동시키지 않는다.
- body/query/path input을 runtime validation 없이 타입만 믿지 않는다.
- browser caching과 application data caching을 같은 것으로 취급하지 않는다.
- 기존 backend API가 책임을 가진다면 Next Route Handler로 중복 business logic을 만들지 않는다.

## Proxy / Middleware

Next.js 16에서는 기존 `middleware` 명칭이 `proxy` 방향으로 변경되었으므로 현재 version과 프로젝트 파일명을 확인한다.

- 기존 버전 프로젝트의 `middleware.ts`를 unrelated Task에서 자동 rename하지 않는다.
- auth/authz를 Proxy/Middleware 하나에만 의존하지 않고 실제 data/action/route boundary에서도 검증한다.
- broad matcher로 모든 request에 불필요한 비용을 추가하지 않는다.
- redirect/rewrite/header 변경은 기존 routing/security contract를 확인한다.

## Routing, Layout, Loading, Error

- route segment와 layout ownership은 현재 App/Pages Router convention을 따른다.
- `loading`, `error`, `not-found` boundary는 실제 UX와 error recovery 요구에 맞춘다.
- error boundary를 단순 예외 은폐 용도로 쓰지 않는다.
- URL로 표현되어야 할 filter/search/page state는 기존 router/search-param pattern을 우선한다.
- component local state와 URL state를 중복 source of truth로 만들지 않는다.

## Metadata / Image / Font

- 기존 Metadata API 또는 Pages Router head convention을 유지한다.
- SEO/social 요구가 있는 경우 canonical/title/description/OG 등의 기존 체계를 따른다.
- `next/image`와 font optimization은 현재 version과 프로젝트 설정을 따른다.
- unrelated feature에서 image/font config migration을 섞지 않는다.

## React Compiler and Turbopack

Next.js 16은 React Compiler 통합과 Turbopack 기본 사용 등 최신 기능을 제공하지만 Hermes는 이를 자동 도입하지 않는다.

```text
이미 설정됨
→ 현재 config/build/lint contract 유지

미설정
→ 현재 Task 요구가 아니면 도입하지 않음
```

manual memoization이나 bundler-specific workaround를 추가하기 전에 현재 compiler/bundler 설정을 확인한다.

## Environment and Secrets

- server-only secret과 browser-exposed environment variable 경계를 유지한다.
- public env prefix/프로젝트 convention을 확인한다.
- secret 값을 Client Component props 또는 client bundle에 넣지 않는다.
- build-time/runtime env 차이를 배포 환경 기준으로 확인한다.

## Review Hotspots

Next.js diff에서는 필요할 때 다음을 확인한다.

```text
version/router 추측
불필요한 `use client` 확장
server-only code/secret의 client bundle 유출
server/client 중복 fetching
waterfall 또는 불필요한 client Effect fetching
현재 version과 맞지 않는 cache API 사용
mutation 후 revalidation 누락 또는 과도한 invalidation
Server Action input/authz 검증 누락
Route Handler와 backend business logic 중복
middleware/proxy version mismatch
auth를 UI/Proxy에만 의존
URL state와 local state 중복
unrelated Next/React/compiler/bundler upgrade
```

## Verification

프로젝트 script를 우선한다.

```text
typecheck / lint
→ affected unit/component test
→ route/page/integration test
→ 필요 시 e2e
→ `next build` 또는 프로젝트 build
```

routing, server/client boundary, caching, mutation/revalidation, auth 변경은 정적 검사만으로 완료 판단하지 않는다.

## Primary Official Sources

- Next.js Docs: App Router / Pages Router
- Next.js Docs: Server and Client Components
- Next.js Docs: Fetching Data / Mutating Data
- Next.js Docs: Caching / Revalidating / Cache Components
- Next.js Docs: Route Handlers
- Next.js Docs: Error Handling
- Next.js Docs: Metadata
- Next.js Docs: Proxy / Upgrading
- Next.js Docs: Authentication / Data Security
- Next.js 16 release and upgrade documentation
