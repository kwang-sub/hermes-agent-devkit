---
screen: <screen-id>
status: APPROVED
source: IMAGE
reference: ./reference.png
fidelity: VISUAL
viewport: 1440x1024
view_strategy: <SHARED | RESPONSIVE | HYBRID | SPLIT_VIEW>
---

# <화면 이름>

## 목적

이 화면이 해결하는 사용자 목적을 한두 문단으로 설명한다.

## 주요 영역

- <영역 1>
- <영역 2>

## 관찰된 디자인

- reference에서 직접 확인 가능한 layout/visual hierarchy를 기록한다.
- exact CSS 값이 아닌 경우 `추정`이라고 표시한다.

## 상태

- populated
- loading: <필요한 경우>
- empty: <필요한 경우>
- error: <필요한 경우>
- disabled/selected 등: <필요한 경우>

## View Strategy

- Strategy: <SHARED | RESPONSIVE | HYBRID | SPLIT_VIEW>
- Rationale: <정보 구조/interaction/state/data 차이 근거>
- Platform Scope: <DESKTOP | MOBILE | BOTH>
- Section Overrides: <section=strategy | NONE>

## 구현 구조

- Package / View Plan: <기존 project convention에 매핑한 구현 경로>
- Shared Implementation: <api/model/state/hooks/common UI>
- Split Implementation: <desktop/mobile 전용 presentation 또는 NONE>
- Responsive / Breakpoint Source: <project token/utility/CSS convention>
- API Impact: <NONE | SHARED_CONTRACT | CONTRACT_CHANGE>

## 반응형

- Desktop: reference 기준
- Tablet: <승인/기존 pattern/unknown>
- Mobile: <승인/기존 pattern/unknown>
- Verification Matrix: <viewport / state / expected view>

## Interaction / Navigation

- <클릭/탭/키보드/이동 동작>

## 기존 Component / Token

- <재사용할 project component/token>

## API / Dependency

- <필요한 API 또는 NONE>

## Unknown / Open Question

- <reference만으로 확인할 수 없는 내용>

## Acceptance Criteria

- <검증 가능한 조건>
