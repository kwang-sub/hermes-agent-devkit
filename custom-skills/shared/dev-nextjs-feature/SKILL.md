---
name: dev-nextjs-feature
description: Next.js 구현에서 실제 version/router를 감지하고 공식 version-aware 기준으로 Server/Client boundary, data fetching, cache/revalidation, Server Action, Route Handler, routing·metadata를 기존 프로젝트 패턴에 맞게 적용하는 capability skill.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, nextjs, react, app-router, server-component, cache, server-action, route-handler, proxy]
    related_skills: [dev-typescript-guidelines, dev-frontend-guidelines, dev-frontend-test, dev-api-contract, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-nextjs-feature

Next.js 전용 capability다. React/TypeScript 공통 규칙을 반복하지 않는다. 최신 Next.js 문법을 기계적으로 강제하지 않고 대상 프로젝트의 실제 version/router/config를 기준으로 판단한다.

상세 version별 근거는 필요할 때만 `references/official-nextjs-practices.md`를 읽는다.

## 우선순위

```text
사용자/Task 정책
→ 실제 Next.js/React version + Router/config + 기존 project convention
→ 이 Skill의 Next.js 전용 규칙
→ 해당 version 공식 Next.js 권장사항
```

Next.js/React/Turbopack/React Compiler/Cache Components를 unrelated Task에서 자동 upgrade하거나 도입하지 않는다.

## 작업 전 확인

- `next`, `react`, `react-dom` 실제 version
- App Router(`app/`) / Pages Router(`pages/`) / 혼합 여부
- `next.config.*`와 compiler/bundler 관련 설정
- Server/Client Component 사용 패턴
- Route Handler/API Route/Server Action 사용 여부
- data fetching/cache/revalidation 방식
- Cache Components/`use cache` 사용 여부
- middleware/proxy 사용 여부와 version
- layout/loading/error/not-found/metadata convention
- image/font/env 및 auth/security boundary
- build/test/e2e script

Router와 version을 추측하지 않는다.

## Version / Request API Gate

- `params`, `searchParams`, `cookies()`, `headers()` 등은 Next major version에 따라 contract가 달라질 수 있으므로 현재 version 기준으로 사용한다.
- 최신 예제를 오래된 프로젝트에 그대로 적용하지 않는다.
- migration Task가 아니면 version migration을 feature/fix와 섞지 않는다.
- deprecation을 숨기기 위한 근거 없는 cast/shim을 추가하지 않는다.

## Server / Client Boundary

- App Router에서 Client Component가 필요하지 않으면 `"use client"`를 자동 추가하지 않는다.
- browser API, client state/event handler 등 client boundary가 필요한 근거를 확인한다.
- client boundary를 상위 layout/page까지 불필요하게 확장하지 않는다.
- server-only secret/data access를 client bundle로 이동하지 않는다.
- Client Component props는 대상 version의 serialization contract를 유지한다.
- third-party client-only component는 필요한 최소 wrapper/boundary로 격리한다.

## Data Fetching

```text
server-only resource / DB / internal service
→ Server Component 또는 기존 server boundary 우선 검토

browser interaction 후 client cache가 필요
→ 기존 client data library/pattern 검토

외부 consumer도 필요한 HTTP contract
→ Route Handler/API/backend contract 검토
```

- 같은 데이터를 server와 client에서 불필요하게 중복 fetch하지 않는다.
- 독립 요청은 network waterfall을 만들지 않도록 병렬화 가능성을 검토한다.
- Suspense/streaming/loading boundary는 실제 UX와 기존 프로젝트 패턴을 따른다.
- 새 data library를 단순 선호로 추가하지 않는다.

## Cache / Revalidation

Caching은 대상 version과 project 설정을 기준으로 판단한다.

- Next.js 16의 Cache Components/`use cache` 모델을 기존 프로젝트에 자동 이식하지 않는다.
- 현재 `fetch` cache option, `use cache`, cache tag/lifetime, static/dynamic rendering contract를 먼저 확인한다.
- mutation 후 stale 되는 데이터에 맞춰 가장 좁은 revalidation 범위를 사용한다.
- `revalidatePath`, `revalidateTag`, `updateTag` 등은 해당 version 지원 여부와 기존 contract를 확인한다.
- 캐시 무효화 누락으로 stale UI를 만들지 않으며, 반대로 모든 mutation에서 전체 cache를 광범위하게 무효화하지 않는다.
- caching 의미 변경은 performance뿐 아니라 data freshness contract 변경으로 취급한다.

## Mutation / Server Action

Server Action을 기본값으로 강제하지 않는다. 기존 application/API boundary를 우선한다.

사용 시:

- action input을 신뢰하지 않고 validation을 수행한다.
- authentication/authorization을 실제 server mutation boundary에서 확인한다.
- UI에서 control을 숨긴 것만으로 authorization을 대체하지 않는다.
- mutation 후 필요한 revalidation/redirect/error path를 명시한다.
- secret/internal error detail을 client에 노출하지 않는다.
- 외부 client도 필요한 contract라면 Route Handler 또는 별도 backend API를 검토한다.

## Route Handler / API Boundary

- method/path/payload/error/auth contract가 생기면 `dev-api-contract` 적용 여부를 확인한다.
- input은 runtime validation 책임을 확인하고 TypeScript type만 신뢰하지 않는다.
- server secret/resource를 client bundle로 이동시키지 않는다.
- browser HTTP caching과 Next application data caching을 동일하게 취급하지 않는다.
- 기존 backend가 소유한 business logic을 Route Handler에 중복 구현하지 않는다.

## Proxy / Middleware

- 현재 Next.js version과 실제 `middleware`/`proxy` convention을 확인한다.
- Next.js 16의 Proxy 명칭을 오래된 프로젝트에 unrelated Task로 자동 rename하지 않는다.
- auth/authz를 Proxy/Middleware 하나에만 의존하지 않고 data/action/route boundary에서도 검증한다.
- broad matcher로 모든 request에 불필요한 처리를 추가하지 않는다.

## Routing / State / Metadata

- dynamic segment, search param, navigation API는 현재 router convention을 따른다.
- URL로 표현돼야 할 filter/search/page state는 기존 search-param/router pattern을 우선한다.
- 같은 값을 URL state와 local state에 중복 source of truth로 만들지 않는다.
- loading/error/not-found boundary는 실제 UX/recovery 요구와 기존 배치 방식을 따른다.
- metadata/SEO 요구가 있으면 현재 Router의 Metadata/head convention을 재사용한다.
- image/font 설정 migration을 unrelated feature에 섞지 않는다.

## React Compiler / Turbopack

- 이미 설정된 React Compiler/Turbopack contract가 있으면 유지한다.
- 미설정 프로젝트에 현재 Task와 무관하게 자동 도입하지 않는다.
- manual memoization 또는 bundler workaround 전에 현재 compiler/bundler 설정을 확인한다.

## Environment / Secrets

- server-only env와 browser-exposed env의 경계를 유지한다.
- secret을 Client Component props나 client bundle로 넘기지 않는다.
- build-time/runtime env 차이는 실제 배포 환경과 기존 convention을 따른다.

## Review Hotspots

```text
version/router 추측
불필요한 `use client` 확장
server-only code/secret client 유출
server/client 중복 fetching 또는 waterfall
현재 version과 맞지 않는 cache API
mutation revalidation 누락/과도한 invalidation
Server Action input/authz 검증 누락
Route Handler와 backend business logic 중복
middleware/proxy version mismatch
auth를 UI/Proxy에만 의존
URL state와 local state 중복
unrelated Next/React/compiler/bundler upgrade
```

## Verification

기존 package script를 우선한다.

```text
typecheck/lint
affected component/unit test
route/page/integration test
필요 시 e2e
next build 또는 프로젝트 build
```

routing, server/client boundary, cache/revalidation, mutation, auth 변경은 정적 검사만으로 완료 판단하지 않는다.

Handoff:

```text
Skill: dev-nextjs-feature
Detected Next.js / React version
Router mode
Request API/version notes
Server/Client boundary
Data fetching convention
Cache/Revalidation model
Server Action / Route Handler boundary
Proxy/Middleware mode
Compiler/Bundler mode
Security/Auth boundary
Verification
```
