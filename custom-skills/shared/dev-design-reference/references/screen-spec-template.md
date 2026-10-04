---
screen: <screen-id>
spec_version: 2
behavior_status: DRAFT
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

작성 규칙은 DevKit의 `dev-design-reference/references/screen-spec-contract.md`를 따른다.
`status`는 디자인 승인, `behavior_status`는 동작 승인이다. 예시 값을 실제 승인 상태로 바꾼다.
디자인이 승인되어도 동작 승인은 자동으로 부여하지 않는다. 기능 동작 변경 시 동작 승인만 다시 확인한다.

## 주요 영역

- <영역 1>
- <영역 2>

## 화면 기능 목록

이번 화면에서 제공하는 기능만 기록한다. 범위 밖 기능은 Unknown / Open Question에서 별도로 구분한다.
버튼 없는 자동 조회, 카드/그래프/안내문 같은 정보 표시 기능도 포함한다.

| 기능 ID | 기능명 | 사용자 목적 / 설명 | 연결 UI ID | 확정 상태 | 근거 |
| --- | --- | --- | --- | --- | --- |
| F-01 | <기능명> | <사용자가 할 수 있는 일> | UI-01 | PROPOSED | <사용자 요구, 승인 기록, 기존 구현 경로 등> |

## UI 요소 및 기능 연결

이미지에 보이는 의미 있는 조작/표시 요소와 기능을 양방향으로 확인한다.
단순 장식과 모든 내부 HTML 노드를 개별 등록하지 않는다. 여러 ID는 쉼표로 구분한다.

| UI ID | 요소 / 종류 / 표시명 | 위치 / 영역 | 연결 기능 ID | 노출 조건 | 활성화 / 표시 규칙 | 플랫폼 차이 |
| --- | --- | --- | --- | --- | --- | --- |
| UI-01 | <종류와 실제 라벨 또는 접근 가능한 이름> | <영역과 위치> | F-01 | <언제 보이거나 숨겨지는가> | <언제 활성/비활성인가, 표시값/형식은 무엇인가> | <웹/모바일 차이 또는 동일> |

## 기능별 동작 명세

### F-01 — <기능명>

| 항목 | 동작 명세 |
| --- | --- |
| 관련 UI | UI-01 |
| 실행 시점 | <클릭/선택 변경/Enter/화면 진입 등. 자동 실행 여부도 명시> |
| 사전 조건 / 입력 검증 | <권한, 필수값, 범위, 기본값. 해당 없으면 이유를 포함> |
| 정상 결과 | <어떤 데이터와 UI가 어떻게 바뀌는가> |
| 상태 / 예외 처리 | <실제 필요한 loading/empty/error/disabled 상태와 사용자 피드백> |
| 화면 이동 / 저장 | <이동 대상, 저장/초기화/유지 여부. 하지 않는 동작도 명시> |
| 플랫폼 차이 | <공통 동작과 웹/모바일 차이, 키보드/터치 대체 수단> |

필요한 기능에만 로딩 처리, 데이터 없음, 실패, 재시도 / 중복 방지, API 계약 참조,
포커스 / 닫기 / 취소 등의 행을 추가한다. 모든 기능에 모든 상태를 기계적으로 추가하지 않는다.
UI가 전혀 없는 자동 기능만 `관련 UI: NONE`을 허용하며 `미노출 사유` 행을 추가한다.

## 기능별 검증 조건

| 검증 ID | 기능 ID | 사전 조건 / 상태 | 사용자 조작 / 트리거 | 기대 결과 | 검증 방법 |
| --- | --- | --- | --- | --- | --- |
| AC-01 | F-01 | <검증 데이터/상태/viewport> | <구체적인 조작 또는 자동 실행 시점> | <관찰 가능한 결과> | <기존 테스트 또는 수동 검증 절차> |

복잡한 기능은 정상/노출·권한/입력 오류/빈 결과/실패·재시도 조건 중 해당하는 경우를 각각 추가한다.
문서에는 검증 기준을, 실행 handoff에는 AC ID별 실제 결과와 증거를 기록한다.

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

- 화면 공통 이동·키보드 규칙을 기록하고, 기능별 동작은 F-ID 명세를 참조한다.
- 기능 명세와 다른 동작을 이 항목에 중복 정의하지 않는다.

## 기존 Component / Token

- <재사용할 project component/token>

## API / Dependency

- <필요한 API 또는 NONE>

## Unknown / Open Question

- <reference만으로 확인할 수 없는 내용>

## Acceptance Criteria

- 기능 동작 검증은 위 AC-ID 표를 참조한다.
- 여기에 승인 디자인 일치, 반응형, 공통 접근성 등 화면 전체 검증 기준을 추가한다.
