---
name: dev-project-pattern
description: 개발 계획 전에 대상 Repository의 기존 구조·코드·응답·테스트 패턴과 실제 stack을 근거로 수집하고 유지해야 할 convention과 적용할 capability skill을 식별한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, pattern, convention, project-analysis, stack, capability]
    related_skills: [dev-tech-dispatch, dev-breakdown, dev-java-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-api-docs, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-ui-ux]
    requires_tools: [terminal, skill_view]
---

# dev-project-pattern

복잡한 작업에서 `dev-breakdown` 전에 대상 프로젝트의 기존 패턴을 읽어 **새 코드가 현재 프로젝트와 최대한 동일한 방식으로 작성되도록 기준을 만드는 read-only Skill**이다.

상세 공통 규칙은 다음을 따른다.

```text
/opt/data/shared/references/project-pattern-rules.md
/opt/data/shared/references/coding-rules.md
/opt/data/shared/references/implementation-decision-rules.md
```

## 실행 순서

1. managed project의 repository와 현재 workspace를 확인한다.
2. project instruction/AGENTS, build/dependency file, source root를 읽는다.
3. 요청과 가장 유사한 기존 구현을 1~3개 찾는다.
4. 다음 convention을 evidence와 함께 요약한다.
   - language/framework/build/test
   - package/module 구조
   - naming
   - Controller/API boundary
   - Service/Application layer
   - Repository/Data access
   - Entity/Model/Domain
   - Request/Response DTO 또는 frontend API type
   - 공통 Response/Error 규격
   - Validation/Exception
   - UI component/state/style/design-system (해당 시)
   - Test framework/style
5. `dev-tech-dispatch`의 canonical detector로 project-level stack/baseline capability를 확인한다.
6. 실제 Task affected area와 detector 결과를 합쳐 필요한 capability skill을 추천한다.
7. 기존 패턴과 사용자의 명시 정책이 충돌하면 조용히 기존 패턴을 따르지 말고 충돌과 최소 변경 방향을 `dev-breakdown`에 전달한다.
8. 개선 필요점은 현재 Task에 필수인지 분리한다. 필수가 아니면 개선 제안으로 남기고 자동 적용하지 않는다.

## Stack detection

정상 경로에서는 다음 detector를 한 번 사용한다.

```bash
python3 /opt/custom-skills/orchestrator/dev-tech-dispatch/scripts/detect_capabilities.py \
  --repo "<managed repository>"
```

Detector는 build/dependency root evidence만 사용하며 project 전체 source scan을 대체하거나 유발하지 않는다.

### Java / Spring

```text
Java build
→ dev-java-guidelines

Spring Boot/Spring
→ dev-spring-guidelines

Controller/Service/DTO/Validation/Exception 기능 변경
→ dev-spring-feature

JPA Entity/Repository/DataJPA/QueryDSL/Converter/Paging 변경
→ dev-spring-data

Spring/JPA 관련 테스트 생성/변경
→ dev-spring-test

OpenAPI/Swagger/Postman
→ dev-api-docs
```

### TypeScript / React / Next.js

```text
TypeScript source/config
→ dev-typescript-guidelines

React component/hook/state/browser UI
→ dev-frontend-guidelines

Next.js App Router/Pages Router/Server·Client Component/route/metadata
→ dev-nextjs-feature

frontend test/spec/e2e 변경
→ dev-frontend-test

layout/visual/interaction/responsive/accessibility/chart 변경
→ dev-ui-ux
```

### Cross-stack API contract

Backend API와 frontend type/client가 같은 Task에서 함께 변경되거나 contract drift 위험이 있으면:

```text
→ dev-api-contract
```

OpenAPI/Postman 산출물이 요구되면 `dev-api-docs`도 추가한다.

## Public Skill / UI 지침

외부 Public Skill은 project pattern을 대체하지 않는다.

`dev-ui-ux`는 UI/UX Pro Max의 audited baseline adapter이며 다음 순서를 지킨다.

```text
사용자/Task
→ 기존 Design System/component/token
→ 같은 화면의 기존 pattern
→ dev-ui-ux baseline
```

React/Next.js가 존재한다는 이유만으로 `dev-ui-ux`를 자동 적용하지 않는다. 보이는 UI/interaction을 실제로 변경할 때만 적용한다.

## 필수 출력

`dev-breakdown`에 다음을 전달한다.

```text
Project Pattern Summary
- Language / Framework / Persistence / Build / Test
- Detected Stacks
- Pattern References
- Package / Naming
- Response Contract
- Error / Validation Contract
- Data Access Convention
- Frontend Component/State/Style Convention (해당 시)
- Design System Reference (해당 시)
- Test Convention
- Applicable Skills
- Pattern Conflicts
- Improvement Candidates (not auto-applied)
```

## 불변식

- source/config를 수정하지 않는다.
- 새 architecture/library/공통 규격을 제안 없이 계획에 확정하지 않는다.
- 기존 패턴을 최신 best practice나 Public Skill 추천으로 임의 교체하지 않는다.
- evidence가 부족하면 추측하지 않고 `dev-breakdown`의 Open Question으로 남긴다.
- `dev-tech-dispatch`는 planning resolver이며 Coder/Reviewer runtime pinned skill로 전달하지 않는다.
