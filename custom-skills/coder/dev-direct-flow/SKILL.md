---
name: dev-direct-flow
description: Kanban 없이 Interactive Coder가 현재 workspace/current branch에서 초소형 저위험 변경을 직접 구현하고 최소 검증한다.
version: 0.1.0
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
User → Coder execution gate → DIRECT → scoped read/edit → minimal verification → report
```

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
- 신규 기능/설계 또는 복수 해석 요구사항
- API/schema/dependency/DB/transaction/security/concurrency/common architecture 영향
- 여러 module/repository 영향
- 위험이나 범위가 불명확한 작업

DIRECT 여부가 애매하면 FAST를 우선한다.

## 실행 승인
Interactive Coder는 사용자가 `직접 수정`, `DIRECT로 진행`, `바로 수정`처럼 현재 메시지에서 DIRECT 실행을 명시적으로 승인한 뒤에만 구현한다.

실행 승인 전에는 source write/patch, build/test, 구현 capability Skill 로드, 광범위 source 탐색을 하지 않는다.

## 실행 절차
승인 후 다음 순서로 수행한다.

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
- DIRECT는 Kanban을 생성하지 않는다.
- DIRECT는 Reviewer를 자동 호출하지 않는다.
- 사용자 변경을 덮어쓰거나 정리하지 않는다.
- 범위가 커졌는데 Interactive Coder가 계속 구현하지 않는다.
- 테스트 성공을 확인하지 않았으면 성공했다고 보고하지 않는다.
