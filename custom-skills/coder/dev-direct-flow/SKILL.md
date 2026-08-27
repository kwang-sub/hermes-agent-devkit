---
name: dev-direct-flow
description: 사용자가 Coder execution gate에서 DIRECT를 명시적으로 선택한 뒤에만 Interactive Coder가 수행하는 초소형 저위험 변경 실행 계약.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, direct, micro, interactive]
    related_skills: [dev-fast-flow, dev-implement-plan]
    requires_tools: [terminal, clarify]
---

# dev-direct-flow

Kanban worker를 띄울 필요가 없는 **초소형·저위험 변경**을 현재 Interactive Coder가 직접 수행하는 실행 모드다.

```text
User → Coder execution gate → explicit DIRECT selection → scoped read/edit → minimal verification → report
```

## DIRECT ENTRY GUARD — MUST RUN FIRST
이 Skill이 semantic auto-selection으로 먼저 로드되더라도 상위 execution gate를 우회하지 않는다.

1. 실제 Kanban Worker Task ID가 있는 세션이면 DIRECT가 아니라 할당 Task 계약을 따른다.
2. Interactive Coder라면 **현재 요청 이전 또는 현재 turn의 execution gate에서 사용자가 DIRECT를 명시적으로 선택했는지** 먼저 확인한다.
3. DIRECT 승인으로 인정하는 것은 execution mode 자체를 명확히 선택한 경우뿐이다.
   - `DIRECT로 진행해주세요`
   - `직접 수정 모드로 진행해주세요`
   - 바로 앞 `clarify`에서 `직접 수정` 선택
4. 다음 일반적인 mutation 표현은 DIRECT 승인이 아니다.
   - `수정해주세요`
   - `바로 수정해주세요`
   - `적용해주세요`
   - `고쳐주세요`
   - `재검토 후 수정해주세요`
   - `오류가 있으면 수정해주세요`
5. 명시적 DIRECT 선택이 없으면 source/plan/grep/read/write/patch/build/test를 시작하지 않는다. Spring/Gradle/구현 capability Skill도 로드하지 않는다.
6. Gate가 아직 수행되지 않았다면 `dev-fast-flow` execution router로 돌아가 `DIRECT | FAST | STANDARD_REQUIRED`를 판정하고 사용자 선택을 받은 뒤 STOP한다.

## DIRECT eligibility
다음을 모두 만족할 때만 DIRECT 후보로 제시한다.

- managed 단일 Repository와 대상 파일/영역이 명확함
- 현재 workspace/current branch에서 그대로 작업 가능
- 예상 변경이 대체로 1~3개 파일 이내의 초소형 변경
- 기존 프로젝트 패턴을 그대로 적용하며 새로운 설계 판단이 불필요함
- public API/request/response schema, DB schema, dependency 변경 없음
- transaction/security/concurrency/common architecture/complex query 정책 영향 없음
- 별도 Reviewer가 필요할 정도의 위험이 없음
- compile 또는 짧은 targeted test로 충분히 검증 가능

대표 후보: 오타/Javadoc/주석, 로그/메시지, 명백한 null/조건문 오류, 작은 validation, 작은 테스트/Markdown 수정.

다음은 DIRECT가 아니다.

- 여러 호출 흐름을 먼저 분석해야 변경 범위를 알 수 있는 작업
- 기존/신규 흐름 비교, 공통 Utility 재사용 여부 판단처럼 source 확인 전 scope가 불명확한 작업
- 신규 기능/설계 또는 복수 해석 요구사항
- API/schema/dependency/DB/transaction/security/concurrency/common architecture 영향
- 여러 module/repository 영향
- 위험이나 범위가 불명확한 작업

DIRECT 여부가 애매하면 FAST를 우선한다.

## 실행 절차
명시적 DIRECT 선택과 eligibility가 모두 확인된 뒤에만 다음 순서로 수행한다.

1. 대상 Repository/workspace/current branch가 요청과 일치하는지 최소 확인한다.
2. 기존 사용자 변경을 보존한다. reset/restore/clean/stash하지 않는다.
3. 정확한 대상 파일/심볼부터 bounded read 한다. repository-wide 탐색은 피한다.
4. 기존 패턴을 따르는 최소 diff만 만든다.
5. 변경 위험에 맞는 최소 compile/targeted test를 실행한다.
6. 변경 파일, 검증 command/result, 남은 risk를 간결하게 보고한다.

DIRECT에서는 Kanban Task 생성, Reviewer 인계, branch/worktree 생성, commit/push/PR/merge를 하지 않는다.

## Escalation
실제 source를 확인한 결과 DIRECT 범위를 벗어나면 구현을 확대하지 않는다.

- 작은 기존 패턴 기반 작업이면 `DIRECT_FLOW_ESCALATION_REQUIRED: FAST`로 중단하고 FAST Flow를 제안한다.
- API/schema/dependency/DB/architecture 등 Standard 영역이면 `DIRECT_FLOW_ESCALATION_REQUIRED: STANDARD`로 중단하고 Orchestrator에서 진행하도록 안내한다.

## 불변식
- DIRECT는 execution gate의 **명시적 DIRECT 선택 후에만** 실행한다.
- semantic skill auto-selection은 DIRECT 승인으로 간주하지 않는다.
- 일반적인 `수정/적용/고쳐주세요` 표현은 DIRECT 승인으로 간주하지 않는다.
- DIRECT는 Kanban을 생성하지 않는다.
- DIRECT는 Reviewer를 자동 호출하지 않는다.
- 사용자 변경을 덮어쓰거나 정리하지 않는다.
- 범위가 커졌는데 Interactive Coder가 계속 구현하지 않는다.
- 테스트 성공을 확인하지 않았으면 성공했다고 보고하지 않는다.
