# UI/UX Baseline

UI/UX Pro Max의 공개 가이드에서 DevKit에 적합한 안정적인 품질 항목만 추려 사용한다. 프로젝트의 기존 디자인 시스템과 충돌하면 프로젝트 규칙이 우선이다.

## Accessibility

- 일반 본문 text contrast는 WCAG 기준을 만족하도록 확인한다.
- focus indicator를 대체 없이 제거하지 않는다.
- keyboard로 핵심 기능을 사용할 수 있어야 한다.
- image/content 의미에 맞는 alt 처리 또는 decorative 처리를 한다.
- icon-only control은 accessible name을 가진다.
- 정보/상태를 color 하나로만 전달하지 않는다.
- form label, description, error 관계를 보존한다.

## Touch & Interaction

- touch target은 모바일에서 충분한 크기와 간격을 확보한다.
- hover만으로 핵심 정보를 제공하지 않는다.
- 비동기 동작에는 loading/disabled/progress feedback을 제공한다.
- destructive action은 프로젝트 기존 confirm/undo pattern을 따른다.

## Layout & Responsive

- 기존 breakpoint/token을 우선한다.
- 작은 화면에서 horizontal overflow가 생기지 않는지 확인한다.
- 고정 폭을 남발하지 않는다.
- text zoom/브라우저 zoom을 막지 않는다.
- long text, localization, 숫자 길이 증가를 확인한다.

## Typography & Color

- component 내부 raw color를 새로 남발하지 않고 기존 semantic token을 우선한다.
- body text를 지나치게 작게 만들지 않는다.
- line-height와 hierarchy를 기존 typography scale에 맞춘다.
- dark mode가 있으면 양쪽 theme contrast를 확인한다.

## Animation

- motion은 상태/공간 변화 이해에 도움될 때 사용한다.
- layout thrashing을 유발하는 animation을 피한다.
- `prefers-reduced-motion` 또는 프로젝트 reduced-motion 정책을 존중한다.
- 단순 장식 때문에 과도한 animation dependency를 추가하지 않는다.

## Forms & Feedback

- placeholder만 label로 사용하지 않는다.
- field error는 해당 field와 가깝게 전달한다.
- submit 실패/성공/중복 submit 상태를 명확히 한다.
- 처음부터 모든 optional 입력을 노출하기보다 기존 progressive disclosure pattern을 따른다.

## Navigation

- back/deep-link 동작이 현재 router와 일관되어야 한다.
- mobile navigation item을 과도하게 늘리지 않는다.
- 현재 위치와 선택 상태를 시각적으로만이 아니라 semantic하게도 표현한다.

## Charts & Data

- chart type은 질문에 맞게 선택한다.
- legend/tooltip/axis/unit을 필요한 수준으로 제공한다.
- gain/loss, category 등을 color 하나로만 구분하지 않는다.
- table/summary 등 accessible fallback 또는 equivalent information을 프로젝트 요구에 맞게 제공한다.
- 금액/수익률/날짜 단위가 API/domain contract와 일치해야 한다.

## Pre-delivery

```text
[ ] 기존 component/token 재사용
[ ] mobile/tablet/desktop 주요 상태
[ ] loading/empty/error/success
[ ] keyboard/focus
[ ] contrast/color-only 의미
[ ] long text/overflow
[ ] reduced motion (motion이 있을 때)
[ ] chart unit/legend/accessibility (chart가 있을 때)
[ ] affected frontend test/typecheck/lint/build
```
