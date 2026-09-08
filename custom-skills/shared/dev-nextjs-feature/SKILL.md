---
name: dev-nextjs-feature
description: Next.js 구현에서 실제 version/router를 감지하고 Server/Client Component, route, data fetching, metadata와 rendering boundary를 기존 프로젝트 패턴에 맞게 적용하는 capability skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, nextjs, react, app-router, server-component]
    related_skills: [dev-typescript-guidelines, dev-frontend-guidelines, dev-frontend-test, dev-api-contract, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-nextjs-feature

Next.js 전용 capability다. React/TypeScript 공통 규칙을 반복하지 않는다.

## 작업 전 확인

- `next` version
- App Router(`app/`) / Pages Router(`pages/`) / 혼합 여부
- Server/Client Component 사용 패턴
- route handler/server action 사용 여부
- data fetching/cache/revalidation 방식
- layout/loading/error/not-found/metadata convention
- image/font/env 사용 방식

Router와 version을 추측하지 않는다.

## Server / Client Boundary

- App Router에서 Client Component가 필요하지 않으면 `"use client"`를 자동 추가하지 않는다.
- browser API, client state/event handler 등 client boundary가 필요한 근거를 확인한다.
- client boundary를 상위 layout/page까지 불필요하게 확장하지 않는다.
- server-only secret/data access를 client bundle로 이동하지 않는다.
- serialization 가능한 props contract를 유지한다.

## Data Fetching / Mutation

- 대상 version과 프로젝트의 cache/revalidation pattern을 따른다.
- 같은 데이터를 server와 client에서 불필요하게 중복 fetch하지 않는다.
- server action/route handler/API client 중 어느 방식을 쓸지는 기존 구조를 우선한다.
- framework upgrade나 새 data library 도입을 Task에 섞지 않는다.

## Routing / Metadata

- dynamic segment, search param, navigation API는 현재 router convention을 따른다.
- loading/error/not-found boundary를 기존 배치 방식에 맞춘다.
- metadata/SEO 요구가 있는 경우 기존 layout/page metadata 체계를 재사용한다.

## Verification

기존 package script를 우선한다.

```text
typecheck/lint
affected test
next build 또는 프로젝트 build
필요한 경우 route/page smoke/e2e
```

Handoff:

```text
Skill: dev-nextjs-feature
Detected Next.js version
Router mode
Server/Client boundary
Data/cache convention
Verification
```
