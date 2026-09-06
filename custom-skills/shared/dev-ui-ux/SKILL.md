---
name: dev-ui-ux
description: 승인된 Figma/프로젝트 Design System을 우선하면서 UI/UX Pro Max의 검증된 우선순위와 접근성·반응형·interaction·chart 가이드를 adapter 형태로 적용하는 UI capability skill.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, ui, ux, accessibility, responsive, figma, design-system, chart]
    related_skills: [dev-frontend-feature, dev-figma-design, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract]
    requires_tools: [terminal]
---

# dev-ui-ux

보이는 UI/interaction을 설계·구현·리뷰할 때만 사용하는 quality capability다. UI/UX Pro Max 전체 runtime을 복제하지 않고 upstream의 안정적인 원칙을 프로젝트 우선 adapter로 사용한다.

## 우선순위

FIGMA_DRIVEN:

```text
사용자/Task 명시 요구
→ APPROVED Figma frame / Design System
→ 프로젝트 기존 component/token/convention
→ 같은 화면/도메인의 기존 UI pattern
→ dev-ui-ux baseline
→ 일반 UI best practice
```

CODE_DRIVEN:

```text
사용자/Task 명시 요구
→ 프로젝트 기존 Design System/component/token
→ 같은 화면/도메인의 기존 UI pattern
→ dev-ui-ux baseline
→ 일반 UI best practice
```

Public Skill 추천 때문에 기존 UI를 자동 redesign하지 않는다. 접근성/correctness 문제로 승인 디자인과 충돌하면 조용히 바꾸지 않고 `Design Conflict`로 보고한다.

## 적용 대상

```text
layout/page/component visual
interaction/navigation/form UX
responsive
accessibility
typography/color/spacing
chart/data visualization
loading/empty/error state
```

pure backend/API/DB/DevOps에는 적용하지 않는다.

## UI/UX baseline

1. Accessibility
2. Touch & Interaction
3. Performance / layout stability
4. Approved/project style consistency
5. Layout & Responsive
6. Typography & Color
7. Animation / reduced motion
8. Forms & Feedback
9. Navigation
10. Charts & Data

상세 checklist는 `references/baseline.md`를 필요할 때만 읽는다.

## Financial/Data UI 추가 확인

금액·수익률·차트처럼 데이터 밀도가 높은 화면에서는 다음을 확인한다.

```text
색상만으로 positive/negative 의미 전달 금지
숫자/단위/소수점/기준일 일관성
긴 금액과 작은 viewport overflow
chart legend/tooltip/accessible color
loading/empty/error와 stale data 구분
```

## Dependency 통제

```text
기존 component/library
→ framework/platform 기본
→ 이미 설치된 dependency
→ 그래도 부족할 때만 새 dependency 제안
```

## Evidence

```text
Skill: dev-ui-ux
Frontend Mode
Design Source / Status
Existing Component/Token references
Accessibility impact
Responsive states
Interaction/loading/error states
Chart semantics
Design Conflicts
Verification
```
