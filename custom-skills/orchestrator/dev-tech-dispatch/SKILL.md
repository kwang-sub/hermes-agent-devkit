---
name: dev-tech-dispatch
description: managed Repository의 bounded build/dependency manifest에서 Java/Spring/TypeScript/React/Next.js stack과 fingerprint를 감지하고 backend capability와 frontend canonical entry/hint를 반환하는 orchestrator 전용 resolver.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, stack, capability, java, spring, typescript, react, nextjs, frontend, fingerprint, monorepo]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-breakdown, dev-java-guidelines, dev-spring-guidelines, dev-frontend-feature, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-figma-design, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-tech-dispatch

기술 감지와 capability name resolution만 담당한다. Workflow/source/dependency/Kanban을 수정하지 않는다.

일반 Standard Flow에서는 이 detector를 직접 매번 실행하지 않고 `dev-project-bootstrap/scripts/stack_cache.py`가 관리하는 `.hermes/project.yaml technology:` cache를 우선 사용한다.

## Canonical detector

```bash
python3 /opt/custom-skills/orchestrator/dev-tech-dispatch/scripts/detect_capabilities.py \
  --repo "<managed repository>"
```

예:

```text
DETECTOR_VERSION=2
STACK_FINGERPRINT=sha256:...
STACK_INPUTS=backend/build.gradle,frontend/package.json,frontend/tsconfig.json
STACKS=java,spring,typescript,react,nextjs
BACKEND_SKILLS=dev-java-guidelines,dev-spring-guidelines
FRONTEND_ENTRY=dev-frontend-feature
FRONTEND_HINTS=dev-typescript-guidelines,dev-frontend-guidelines,dev-nextjs-feature,dev-frontend-test
UI_SKILL_CANDIDATE=dev-ui-ux
CROSS_STACK_SKILL_CANDIDATE=dev-api-contract
STATUS=pass
```

Fingerprint만 필요하면:

```bash
python3 /opt/custom-skills/orchestrator/dev-tech-dispatch/scripts/detect_capabilities.py \
  --repo "<managed repository>" \
  --fingerprint-only
```

## 탐지 범위

Repository 전체 source를 읽지 않는다. root 및 최대 3단계 하위에서 build/dependency manifest만 확인하고 generated/vendor 디렉터리는 제외한다.

대표 input:

```text
build.gradle / build.gradle.kts / settings.gradle*
pom.xml / gradle.properties / libs.versions.toml
package.json / package-lock.json / pnpm-lock.yaml / pnpm-workspace.yaml
yarn.lock / bun.lock*
tsconfig*.json
```

따라서 `backend/` + `frontend/` 형태의 작은 monorepo도 감지할 수 있고 일반 `.java`, `.ts`, `.tsx` source 변경은 stack fingerprint를 바꾸지 않는다.

## 적용 규칙

- `BACKEND_SKILLS`는 Task affected area가 backend일 때 기존 방식대로 applicable 후보가 된다.
- `FRONTEND_ENTRY`는 Task affected area가 frontend일 때 canonical runtime entry다.
- `FRONTEND_HINTS`는 하위 lazy capability 후보이며 시작부터 모두 runtime pin하지 않는다.
- `UI_SKILL_CANDIDATE`는 실제 visible UI/interaction 변경에만 사용한다.
- `CROSS_STACK_SKILL_CANDIDATE`는 backend/frontend API contract를 실제로 함께 건드릴 때만 사용한다.
- Figma는 repository stack이 아니라 Task design source이므로 detector가 자동 추측하지 않는다. Figma URL/Design Status는 `dev-project-pattern`/`dev-breakdown`이 판단한다.

## Stack Detection != Skill Loading

Repository에 Spring + Next.js가 함께 있어도 Backend-only Task에는 frontend entry를 적용하지 않는다. Frontend-only Task에도 backend skill을 자동 적용하지 않는다.

## 불변식

- project source 전체 scan 금지.
- 비슷한 Skill 이름 자동 대체 금지.
- dependency 설치/architecture 선택 금지.
- `dev-tech-dispatch` 자체는 Coder/Reviewer runtime pinned skill이 아니다.
- cache 정책은 `dev-project-bootstrap/scripts/stack_cache.py`가 소유한다.

## 회귀 검증

```bash
python3 custom-skills/orchestrator/dev-tech-dispatch/tests/test_detect_capabilities.py
```
