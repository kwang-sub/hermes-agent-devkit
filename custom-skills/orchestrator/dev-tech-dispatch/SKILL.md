---
name: dev-tech-dispatch
description: managed Repository의 bounded build/dependency manifest에서 Java/Kotlin/Spring/TypeScript/React/Next.js stack과 fingerprint를 감지하고 backend capability와 frontend canonical entry/hint를 반환하는 orchestrator 전용 resolver.
version: 0.4.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, stack, capability, java, kotlin, spring, typescript, react, nextjs, frontend, fingerprint, monorepo]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-breakdown, dev-java-guidelines, dev-kotlin-guidelines, dev-spring-guidelines, dev-frontend-feature, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-figma-design, dev-ui-ux]
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

Kotlin + Spring 예:

```text
DETECTOR_VERSION=3
STACK_FINGERPRINT=sha256:...
STACK_INPUTS=backend/build.gradle.kts
STACKS=kotlin,spring
BACKEND_SKILLS=dev-kotlin-guidelines,dev-spring-guidelines
STATUS=pass
```

Java + Kotlin mixed Spring 예:

```text
STACKS=java,kotlin,spring
BACKEND_SKILLS=dev-java-guidelines,dev-kotlin-guidelines,dev-spring-guidelines
```

Frontend가 함께 있으면 기존처럼 `FRONTEND_ENTRY`, `FRONTEND_HINTS`, `CROSS_STACK_SKILL_CANDIDATE`를 추가한다.

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

일반 `.java`, `.kt`, `.ts`, `.tsx` source 변경은 stack fingerprint를 바꾸지 않는다.

## JVM 언어 판정

Kotlin 근거:

```text
kotlin("jvm")
org.jetbrains.kotlin.jvm
org.jetbrains.kotlin.plugin.spring
org.jetbrains.kotlin.plugin.jpa
kotlin-maven-plugin
```

Kotlin 근거가 없는 Gradle/Maven JVM build는 기존 호환성을 위해 Java로 판정한다. Kotlin이 명시된 build에서 Java도 함께 반환하려면 `java` plugin 또는 `maven-compiler-plugin` 같은 manifest 근거가 있어야 한다. Source tree를 훑어서 mixed 여부를 추측하지 않는다.

```text
Kotlin only           → STACKS=kotlin
Kotlin + Spring       → STACKS=kotlin,spring
Java + Kotlin + Spring→ STACKS=java,kotlin,spring
```

Capability mapping:

```text
Java   → dev-java-guidelines
Kotlin → dev-kotlin-guidelines
Spring → dev-spring-guidelines
```

## 적용 규칙

- `BACKEND_SKILLS`는 Task affected area가 backend일 때 applicable 후보가 된다.
- mixed project에서도 실제 Java diff에는 Java 규칙, Kotlin diff에는 Kotlin 규칙을 적용한다.
- `FRONTEND_ENTRY`는 Task affected area가 frontend일 때 canonical runtime entry다.
- `FRONTEND_HINTS`는 하위 lazy capability 후보이며 시작부터 모두 runtime pin하지 않는다.
- `UI_SKILL_CANDIDATE`는 실제 visible UI/interaction 변경에만 사용한다.
- `CROSS_STACK_SKILL_CANDIDATE`는 backend/frontend API contract를 실제로 함께 건드릴 때만 사용한다.
- Figma는 repository stack이 아니라 Task design source이므로 detector가 자동 추측하지 않는다.

## Stack Detection != Skill Loading

Repository에 Kotlin/Spring + Next.js가 함께 있어도 Backend-only Task에는 frontend entry를 적용하지 않는다. Frontend-only Task에도 backend skill을 자동 적용하지 않는다.

## 불변식

- project source 전체 scan 금지.
- 비슷한 Skill 이름 자동 대체 금지.
- dependency 설치/architecture 선택/언어 version upgrade 금지.
- Kotlin 프로젝트를 Gradle/Maven이라는 이유만으로 Java로 중복 분류하지 않는다.
- `dev-tech-dispatch` 자체는 Coder/Reviewer runtime pinned skill이 아니다.
- cache 정책은 `dev-project-bootstrap/scripts/stack_cache.py`가 소유한다.

## 회귀 검증

```bash
python3 custom-skills/orchestrator/dev-tech-dispatch/tests/test_detect_capabilities.py
```
