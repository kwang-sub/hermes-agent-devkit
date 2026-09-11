---
name: dev-design-reference
description: 승인된 이미지 또는 Figma 디자인 자료를 Frontend 구현용 Normalized Design Evidence로 변환하고 GitHub Reference Package 계약을 관리하는 shared capability skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, design, image, screenshot, figma, reference, specification]
    related_skills: [dev-frontend-feature, dev-figma-design, dev-ui-ux, dev-frontend-test]
    requires_tools: [terminal, skill_view]
---

# dev-design-reference

Frontend 구현 전에 디자인 자료를 **provider 독립적인 Design Evidence**로 정규화하는 capability다.

이 Skill은 화면 source를 직접 구현하지 않는다. 이미지/Figma에서 확인 가능한 사실과 추론/미확정 정보를 분리해 `dev-frontend-feature`와 Reviewer에 전달한다.

## Design Source

```text
IMAGE
- PNG/JPG/JPEG/WEBP
- ChatGPT 생성 시안
- 디자이너 전달 이미지
- 기존 서비스 Screenshot
- Wireframe capture

FIGMA
- selected frame/component URL
- provider는 dev-figma-design
```

기존 구현 자체를 기준으로 하는 경우 이 Skill이 아니라 `CODE_DRIVEN` 경로를 사용한다.

## Design Status

```text
DRAFT
→ planning/reference only
→ 구현 source of truth 아님

REFERENCE
→ 분위기/구조/시각 방향 참고
→ exact conformance 대상 아님

APPROVED
→ 구현 기준으로 사용 가능
```

`DRAFT` 또는 `REFERENCE`를 Coder가 임의로 `APPROVED`로 승격하지 않는다.

## Fidelity

```text
STRUCTURE
→ 정보 구조/영역/배치 중심

VISUAL
→ layout/spacing/typography/color/visual hierarchy까지 반영

HIGH
→ 승인 reference와 높은 시각적 일치를 요구하되, 이미지에서 알 수 없는 exact CSS 값을 사실처럼 만들지 않음
```

`pixel-perfect` PASS 같은 증명 불가능한 표현을 기본 계약으로 사용하지 않는다.

## Reference Package

프로젝트에 기존 UI 문서 규칙이 없고 `IMAGE + APPROVED`이면 기본 위치는 다음이다.

```text
docs/ui/screens/<screen>/
├─ reference.png
└─ screen-spec.md
```

추가 viewport가 승인돼 있으면 프로젝트 convention에 맞춰 예를 들어:

```text
reference.mobile.png
reference.tablet.png
```

처럼 둘 수 있다.

이미지는 **보이는 계약**, `screen-spec.md`는 **보이지 않는 동작 계약**이다.

`screen-spec.md` 권장 template은 `references/screen-spec-template.md`를 사용한다.

## Screen Specification 최소 정보

```text
screen
status
source
reference
fidelity
viewport
화면 목적
주요 영역
states: loading / empty / error / populated 등
responsive behavior
interaction/navigation
API/dependency
existing component/token reuse
unknown/open question
acceptance criteria
```

모든 화면에 모든 상태를 기계적으로 추가하지 않는다. 실제 화면 behavior에 필요한 상태만 문서화한다.

## IMAGE Provider

이미지 입력은 task에 첨부됐거나 workspace에서 실제 접근 가능한 파일만 사용한다.

이미지 분석 결과를 반드시 다음으로 나눈다.

```text
OBSERVED
- 이미지에서 직접 확인 가능한 내용

INFERRED
- 시각적으로 합리적으로 추정한 내용
- exact token/CSS 값으로 확정하지 않음

UNKNOWN
- 이미지에서 확인할 수 없는 내용
```

예:

```text
OBSERVED
- summary card 4개
- 우측 donut chart
- positive/negative color 구분

INFERRED
- card gap 약 16px
- desktop two-column layout

UNKNOWN
- mobile layout
- loading/error state
- hover/focus state
- exact design token
```

이미지를 읽을 수 없는 runtime이면 `CAPABILITY` blocker로 종료하고 내용을 추측하지 않는다.

## FIGMA Provider

Figma면 `skill_view("dev-figma-design")`을 사용해 selected node를 bounded read한다.

Figma provider가 반환한 exact layout/component/style metadata는 `OBSERVED`로 취급할 수 있다. Figma에 없는 responsive/state/product behavior는 여전히 `UNKNOWN`일 수 있다.

## Normalized Design Evidence

Provider 종류와 무관하게 다음 구조로 전달한다.

```text
Design Source: IMAGE | FIGMA
Design Status: DRAFT | REFERENCE | APPROVED
Design Fidelity: STRUCTURE | VISUAL | HIGH
Reference: <repo path | selected Figma URL>
Screen Spec: <repo path | none>
Viewport: <width>x<height> | UNKNOWN

Observed:
- ...

Inferred:
- ...

Unknown:
- ...

Existing Component / Token Reuse:
- ...

Design Conflicts:
- ...
```

## 우선순위

`APPROVED` Reference에서는:

```text
사용자/Task 명시 요구
→ 승인 reference의 OBSERVED evidence
→ project Design System/component/token/convention
→ INFERRED evidence
→ dev-ui-ux quality guardrail
→ 일반 best practice
```

따라서 이미지에서 radius가 대략 11~13px로 보이고 project card token이 12px이면 project token을 재사용한다.

## 이미지에 없는 상태

```text
Reference에 있음
→ OBSERVED evidence

Reference에 없음 + project pattern 있음
→ project pattern

둘 다 없음 + UX상 반드시 필요
→ dev-ui-ux 최소 제안

product 의미 결정 필요
→ UNKNOWN / Open Question
```

보이지 않는 상태를 임의의 새로운 product behavior로 확정하지 않는다.

## Reference Package Guard

```bash
python3 /opt/custom-skills/shared/dev-design-reference/scripts/screen_spec_guard.py \
  --spec "docs/ui/screens/<screen>/screen-spec.md"
```

이 helper는 frontmatter와 reference 접근성만 확인하는 lightweight guard다. 이미지 내용/디자인 품질 검증이나 full Markdown parser를 가장하지 않는다.

## Reviewer 계약

Reviewer는 Coder가 남긴 Normalized Design Evidence를 먼저 재사용한다.

원본 Reference를 다시 읽는 경우:

```text
- fidelity finding 판단에 원본이 필요함
- Coder evidence와 실제 diff가 모순됨
- Approved reference 변경 여부 확인이 필요함
```

단순 확신 확보를 위해 같은 이미지/Figma를 반복 분석하지 않는다.

## 불변식

- 이미지의 추정치를 exact design fact로 기록하지 않는다.
- UNKNOWN을 조용히 임의 결정하지 않는다.
- 승인 reference 일치를 이유로 unrelated global token/component migration을 하지 않는다.
- IMAGE workflow를 위해 Figma를 강제하지 않는다.
- Figma를 IMAGE보다 우월한 필수 source로 취급하지 않는다.
