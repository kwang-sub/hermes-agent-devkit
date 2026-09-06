---
name: dev-ui-ux
description: 기존 프로젝트 Design System을 최우선으로 유지하면서 UI/UX Pro Max의 검증된 우선순위와 frontend 접근성·반응형·interaction·chart 가이드를 adapter 형태로 적용하는 UI capability skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, ui, ux, accessibility, responsive, design-system, chart]
    related_skills: [dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract]
    requires_tools: [terminal]
---

# dev-ui-ux

보이는 UI/interaction을 설계·구현·리뷰할 때만 사용하는 capability다.

이 Skill은 UI/UX Pro Max를 DevKit에 그대로 복제하지 않는다. upstream의 안정적인 원칙을 **프로젝트 우선 adapter**로 사용한다. 출처와 pinned audit 정보는 `references/upstream.md`에 기록한다.

## 우선순위

```text
사용자/Task 명시 요구
→ 프로젝트의 기존 Design System / token / component library
→ 같은 화면/도메인의 기존 UI pattern
→ 이 Skill의 UI/UX baseline
→ 일반 UI best practice
```

Public Skill 추천 때문에 기존 UI를 자동 redesign하지 않는다.

## 적용 대상

```text
layout / page / component visual change
interaction / navigation / form UX
responsive behavior
accessibility
typography / color / spacing
chart / data visualization
loading / empty / error visual state
```

pure backend/API/DB/DevOps 작업에는 적용하지 않는다.

## UI/UX baseline

우선순위:

1. Accessibility
2. Touch & Interaction
3. Performance / layout stability
4. Existing style consistency
5. Layout & Responsive
6. Typography & Color
7. Animation / reduced motion
8. Forms & Feedback
9. Navigation
10. Charts & Data

상세 checklist는 `references/baseline.md`를 필요할 때만 읽는다.

## 프로젝트 Design System

프로젝트에 이미 token/theme/component system이 있으면 그것이 source of truth다.

새 프로젝트/화면에서 디자인 방향을 문서화해야 한다면 repository가 추적하는 위치에 다음과 유사한 구조를 사용할 수 있다.

```text
docs/design-system/MASTER.md
docs/design-system/pages/<page>.md
```

단, 기존 프로젝트 문서 구조가 있으면 그 위치를 우선한다. `.hermes/`는 DevKit 로컬 관리 경로이므로 버전 관리할 프로젝트 디자인 원본 위치로 사용하지 않는다.

## Dependency 통제

아이콘, chart, animation, form, component library를 추천할 때:

```text
기존 component/library
→ platform/framework 기본
→ 이미 설치된 dependency
→ 그래도 부족할 때만 새 dependency 제안
```

새 dependency가 필요한 경우 Standard Flow/승인 규칙을 따른다.

## Evidence

```text
Skill: dev-ui-ux
Existing Design System / UI references
Accessibility impact
Responsive states checked
Interaction/loading/error states
Chart semantics (해당 시)
Intentional deviations
Verification
```
