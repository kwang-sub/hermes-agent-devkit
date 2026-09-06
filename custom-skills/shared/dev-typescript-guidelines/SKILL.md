---
name: dev-typescript-guidelines
description: TypeScript 구현에서 대상 프로젝트의 tsconfig·strictness·type 배치·import·nullability convention을 감지하고 기존 프로젝트 패턴을 우선하는 공통 capability skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, typescript, frontend, guidelines, convention]
    related_skills: [dev-implement-plan, dev-project-pattern, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract]
    requires_tools: [terminal]
---

# dev-typescript-guidelines

TypeScript 작업에 추가 적용하는 공통 규칙이다. `coding-rules.md`, `implementation-decision-rules.md`, 대상 프로젝트 convention을 반복하거나 대체하지 않는다.

## 우선순위

```text
사용자/Task 명시 정책
→ 대상 프로젝트의 기존 TypeScript convention
→ 이 Skill의 TypeScript 전용 규칙
→ 일반 TypeScript 관례
```

## 작업 전 확인

- `package.json`, lockfile, TypeScript version
- `tsconfig*.json`의 `strict`, module/target/path alias
- type/interface/type alias/enum 사용 패턴
- import alias와 barrel export 사용 여부
- nullable/optional data 표현
- API type 생성/수동 선언 방식
- lint/format/test script

## 타입 규칙

- `any`를 편의상 추가하지 않는다. 기존 코드가 허용하더라도 현재 값의 실제 shape를 알 수 있으면 구체 타입을 우선한다.
- 외부 입력은 compile-time type만 믿지 않고 runtime validation 책임이 기존 어디에 있는지 확인한다.
- `unknown`을 사용하면 narrowing 근거를 코드에 둔다.
- 같은 business/API 의미의 타입이 이미 있으면 새 타입을 중복 생성하지 않는다.
- `as` assertion으로 실제 contract mismatch를 숨기지 않는다.
- optional(`?`)과 `null`을 기존 API/상태 convention과 일치시킨다.

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
- type-only import convention(`import type`)은 기존 lint/compiler 설정을 따른다.

## Verification / Evidence

가능하면 기존 script를 우선한다.

```text
typecheck
lint
affected test
build
```

새 npm package를 검증 편의를 위해 추가하지 않는다.

Handoff에는 필요할 때 다음을 남긴다.

```text
Skill: dev-typescript-guidelines
Detected TypeScript version
tsconfig/strictness
Type placement convention
API type strategy
Verification
```
