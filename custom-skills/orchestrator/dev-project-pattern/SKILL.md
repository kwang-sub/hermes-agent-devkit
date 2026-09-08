---
name: dev-project-pattern
description: 개발 계획 전에 Bootstrap 기술 스택 캐시와 대상 Repository의 기존 구조·코드·UI·테스트 패턴을 근거로 수집하고 유지해야 할 convention과 적용할 capability skill을 식별한다.
version: 0.4.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, pattern, convention, project-analysis, stack, frontend, figma, cache]
    related_skills: [dev-project-bootstrap, dev-tech-dispatch, dev-breakdown, dev-java-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-api-docs, dev-frontend-feature, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-figma-design, dev-ui-ux]
    requires_tools: [terminal, skill_view]
---

# dev-project-pattern

복잡한 작업에서 `dev-breakdown` 전에 대상 프로젝트의 기존 패턴을 읽어 새 코드가 현재 프로젝트와 최대한 동일한 방식으로 작성되도록 기준을 만드는 planning Skill이다.

```text
/opt/data/shared/references/project-pattern-rules.md
/opt/data/shared/references/coding-rules.md
/opt/data/shared/references/implementation-decision-rules.md
```

을 공통 Foundation으로 적용한다.

## 실행 순서

1. managed project repository/workspace identity와 `.hermes/project.yaml`을 확인한다.
2. instruction/AGENTS, 실제 Task와 관련된 source root를 읽는다.
3. `stack_cache.py`를 한 번 실행해 Bootstrap 기술 스택 캐시를 검증한다.
4. `STACK_CACHE=reused`면 저장된 technology metadata를 그대로 사용한다.
5. manifest fingerprint가 달라 `created|updated`가 나오면 detector가 재실행한 최신 stack 결과를 사용한다.
6. 요청과 가장 유사한 기존 구현을 1~3개 찾는다.
7. backend/frontend/data/UI/test convention을 evidence와 함께 요약한다.
8. 실제 Task affected area와 stack 결과를 합쳐 runtime entry capability와 lazy capability hint를 결정한다.
9. Figma URL이 있으면 Design Source/Status를 분리한다.
10. 기존 패턴과 사용자 정책 충돌은 조용히 덮지 않고 최소 변경 방향과 Improvement Candidate로 전달한다.

## Technology cache

Bootstrap이 생성한 `.hermes/project.yaml`의 `technology:` section이 canonical project-level stack cache다.

```bash
python3 /opt/custom-skills/orchestrator/dev-project-bootstrap/scripts/stack_cache.py \
  --repo "<managed repository>"
```

예:

```text
STACK_CACHE=reused
DETECTOR_VERSION=2
STACK_FINGERPRINT=sha256:...
STACK_INPUTS=backend/build.gradle,frontend/package.json,frontend/tsconfig.json
STACKS=java,spring,typescript,react,nextjs
BACKEND_SKILLS=dev-java-guidelines,dev-spring-guidelines
FRONTEND_ENTRY=dev-frontend-feature
FRONTEND_HINTS=dev-typescript-guidelines,dev-frontend-guidelines,dev-nextjs-feature,dev-frontend-test
STATUS=pass
```

`STACK_CACHE=reused`에서는 full stack detector를 다시 실행하지 않는다. Fingerprint는 build/dependency manifest만 대상으로 하므로 일반 source 변경은 cache invalidation 원인이 아니다.

manifest 변경 또는 detector version 변경 시에만 stack을 다시 계산하고 Bootstrap-managed local metadata의 `technology:` section을 갱신한다. `.hermes/`는 Bootstrap `.gitignore` 정책으로 Git 추적에서 제외되므로 application source/config 변경으로 취급하지 않는다.

기존 Bootstrap Repository가 `technology:` section이 없으면 최초 Standard Flow에서 자동 생성될 수 있지만, DevKit 업데이트 직후에는 다음 명시적 migration을 우선 권장한다.

```bash
python3 /opt/custom-skills/orchestrator/dev-project-bootstrap/scripts/bootstrap.py \
  --repo "<managed repository>" \
  --refresh-stack
```

여러 Repository는 `refresh_stacks.py --root <root>`로 일괄 갱신할 수 있다.

## Stack Detection != Skill Loading

Technology cache는 Repository가 사용할 수 있는 stack/capability 후보를 저장할 뿐 이번 Task가 Frontend/Backend/Full-stack인지 결정하지 않는다.

```text
Repository Stack
+ 사용자 요구사항
+ 실제 affected area
= Task Capability
```

Repository에 Spring + Next.js가 함께 있어도 Backend-only Task에는 frontend entry를 적용하지 않는다. Frontend-only Task에도 backend skill을 자동 적용하지 않는다.

## Backend capability

```text
Java → dev-java-guidelines
Spring → dev-spring-guidelines
Controller/Service/DTO/Validation/Exception → dev-spring-feature
JPA/Repository/DataJPA/QueryDSL/Converter/Paging → dev-spring-data
Spring/JPA test → dev-spring-test
OpenAPI/Swagger/Postman → dev-api-docs
```

## Frontend canonical entry

실제 Task가 TypeScript/React/Next.js UI 또는 browser 동작을 변경하면 runtime entry는:

```text
→ dev-frontend-feature
```

하위 전문 Skill은 `Frontend Capability Hints`로만 전달한다.

```text
TypeScript → dev-typescript-guidelines
React component/state/form/browser → dev-frontend-guidelines
Next.js router/server-client/cache/metadata → dev-nextjs-feature
frontend spec/e2e → dev-frontend-test
backend↔frontend contract → dev-api-contract
visual/interaction/responsive/accessibility/chart → dev-ui-ux
승인된 Figma → dev-figma-design
```

React/Next.js가 repository에 있다는 이유만으로 frontend entry나 UI/UX를 자동 적용하지 않는다. Task affected area가 frontend일 때만 적용한다.

## Figma Design Source

Task에 Figma URL이 있으면 다음을 구분한다.

```text
Design Source: FIGMA
Design Status: DRAFT | APPROVED
Figma URL: <selected frame/component URL>
```

- `APPROVED`: FIGMA_DRIVEN 구현 source of truth 후보.
- `DRAFT`: 계획/비교 참고자료. 구현 source of truth로 확정하지 않는다.
- status가 불명확한데 구현 방향을 바꿀 수 있으면 Open Question으로 남긴다.
- file-level URL보다 selected frame/component `node-id` URL을 우선한다.

## 필수 출력

```text
Project Pattern Summary
- Language / Framework / Persistence / Build / Test
- Technology Cache Status / Fingerprint
- Detected Stacks
- Pattern References
- Package / Naming
- Response Contract
- Error / Validation Contract
- Data Access Convention
- Frontend Component/State/Style Convention (해당 시)
- Design System Reference (해당 시)
- Design Source / Status / Figma URL (해당 시)
- Test Convention
- Applicable Skills
- Frontend Capability Hints
- Pattern Conflicts
- Improvement Candidates (not auto-applied)
```

## 불변식

- application source/build dependency를 수정하지 않는다.
- `technology:` cache 갱신 외 project metadata를 planning 단계에서 변경하지 않는다.
- 새 architecture/library/common contract를 제안 없이 확정하지 않는다.
- 기존 패턴을 Public Skill/Figma 추천으로 광범위하게 교체하지 않는다.
- `dev-tech-dispatch`는 detector이며 runtime pinned skill이 아니다.
- frontend 하위 capability를 전부 runtime pin하지 않고 `dev-frontend-feature`를 canonical entry로 사용한다.
