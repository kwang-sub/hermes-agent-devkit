---
name: dev-fast-flow
description: Interactive Coder의 모든 mutation request에서 가장 먼저 DIRECT/FAST/STANDARD_REQUIRED를 판정하고 FAST 선택 시 Kanban에 self-dispatch하는 execution router.
version: 0.4.2
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, fast-flow, direct, kanban, review, intake]
    related_skills: [dev-direct-flow, dev-implement-plan, dev-code-review, dev-review-cycle]
    requires_tools: [terminal, clarify]
---

# dev-fast-flow

Interactive Coder의 mutation request에 대한 **최상위 execution router**다. `dev-direct-flow`, `dev-spring-*`, Gradle verification 등 어떤 implementation/capability Skill보다 먼저 적용한다.

```text
User mutation request
        ↓
Coder execution gate
        ├─ DIRECT → explicit DIRECT selection 후 dev-direct-flow
        ├─ FAST → Kanban → Coder worker
        │                    ├─ Review Risk LOW → done
        │                    └─ REVIEW_REQUIRED → Reviewer
        └─ STANDARD_REQUIRED → Orchestrator 안내 → STOP
```

## EXECUTION SAFETY GATE — MUST RUN FIRST
1. 실제 Kanban Task ID가 있는 worker 세션인가?
   - YES: 할당 Task를 수행한다. Interactive Gate를 묻지 않는다.
   - NO: Interactive Coder로 간주한다.
2. mutation request라면 semantic skill auto-selection 결과와 무관하게 이 router를 먼저 적용한다.
   - `dev-direct-flow`가 먼저 선택되어도 DIRECT 실행을 시작하지 않는다.
   - `dev-spring-*`, `gradle-spring-verification`, 구현 capability Skill을 먼저 로드하지 않는다.
3. 최소 정보만으로 `DIRECT | FAST | STANDARD_REQUIRED` 후보를 분류한다.
   - DIRECT: 대상이 명확한 초소형 저위험 변경. 대체로 1~3개 파일, 기존 패턴 그대로, API/schema/dependency/DB/transaction/security/concurrency/common architecture 영향 없음.
   - FAST: 단일 managed Repository/current branch의 작은 기존 패턴 기반 작업. 여러 호출 흐름 분석, 공통 코드 재사용 여부 판단, 기존/신규 흐름 비교처럼 source 확인 전 scope가 불명확하면 DIRECT보다 FAST를 우선한다.
   - STANDARD_REQUIRED: 신규 기능/설계, multi-module/repo, API/request/response schema, DB schema, dependency, transaction/security/concurrency/common architecture 정책 결정, 복수 해석 요구사항.
4. 현재 메시지 또는 바로 앞 execution-gate `clarify`에 명시적인 실행 방식 선택이 있는가?
   - DIRECT 승인: `DIRECT로 진행해주세요`, `직접 수정 모드로 진행해주세요`, 또는 바로 앞 `clarify`의 `직접 수정` 선택.
   - FAST 승인: `FAST Flow로 진행`, `칸반으로 진행`, `/dev-fast-flow ...`.
   - Standard 요청: Coder 직접 실행 승인이 아니다. Orchestrator에서 진행하도록 안내하고 STOP.
   - 명시적 선택이 없으면 `clarify` 후 즉시 STOP.
5. 다음 일반 mutation 표현은 DIRECT 승인으로 간주하지 않는다.
   - `수정해주세요`
   - `바로 수정해주세요`
   - `적용해주세요`
   - `고쳐주세요`
   - `재검토해주세요`
   - `오류가 있으면 수정해주세요`
6. 동일 요청 반복, 문구 보완, 추가 요구사항, 파일 재첨부, `@file` 재지정, 질문 재입력도 실행 승인으로 간주하지 않는다.
7. 승인 대기 중 이런 메시지가 오면 요구사항만 갱신하고 다시 `clarify` 후 STOP.
8. **승인 전 Interactive turn의 유일한 실행 action은 `clarify`다.** plan/read/grep/find/write/patch/build/test/Kanban create 금지.
9. DIRECT 선택 시에만 `dev-direct-flow` 계약으로 전환한다. FAST 선택 시 아래 canonical dispatch만 수행하고 STOP한다.

## `clarify` 선택지
- DIRECT + FAST 모두 가능: `직접 수정`, `FAST Flow로 진행`, `분석만 진행`, `취소`.
- FAST만 가능: `FAST Flow로 진행`, `분석만 진행`, `취소`.
- STANDARD_REQUIRED: 선택을 묻지 않고 Orchestrator 안내 후 STOP.

## DIRECT 판정 기준
다음을 모두 만족할 때만 DIRECT를 제시한다.
- managed 단일 Repository와 대상 파일/영역이 명확함
- current workspace/current branch 유지 가능
- 예상 1~3개 파일의 초소형 변경
- 기존 패턴 그대로 적용 가능
- public API/request/response schema, DB schema, dependency 변경 없음
- transaction/security/concurrency/common architecture/complex query 영향 없음
- 별도 Reviewer가 필요할 정도의 위험 없음
- compile 또는 짧은 targeted test로 충분히 검증 가능

범위가 불명확하거나 여러 호출 흐름 비교/분석, 공통 utility 추출 필요성/재사용 가능성 검토가 먼저 필요하면 FAST를 우선한다.

## FAST 적용 조건
- managed 단일 Repository가 명확함
- 작은 기존 패턴 기반 변경
- current branch에서 작업 가능
- 기존 변경을 그대로 보존 가능
- architecture/product/public API/DB schema/dependency/cross-repo 결정 불필요
- 완료 조건과 검증 방법이 명확함

사용자가 `/dev-fast-flow`를 명시해도 eligibility를 우회하지 않는다. 요청 자체에 public API/schema/dependency/DB/architecture 변경이 명시되면 `STANDARD_REQUIRED`로 판정한다.

## Fast Intake Budget
FAST intake의 책임은 **구현 분석이 아니라 eligibility 판정과 dispatch**다.

- 승인 전 capability skill preload 금지.
- 사용자가 대상 파일/클래스를 명시했으면 repository-wide 탐색을 하지 않는다.
- 구현 세부사항, dependency 흐름, 테스트 내부 분석은 worker 책임이다.
- `create_fast_task.py`가 project.yaml, branch, Base SHA, effective dirty baseline을 계산하므로 수동 중복 검사를 하지 않는다.
- 정상 경로에서 `create_fast_task.py --help`, script source read, argument probe를 실행하지 않는다.
- dispatch 성공 후 추가 source 조사 없이 STOP한다.

## Canonical Fast Task CLI — EXACT CONTRACT
```bash
python3 /opt/custom-skills/coder/dev-fast-flow/scripts/create_fast_task.py \
  --workspace "<Workspace>" \
  --title "<Title>" \
  --goal "<Goal>" \
  --acceptance "<Acceptance Criteria>" \
  --implementation "<Implementation Tasks>" \
  --test "<Test Plan>" \
  --risk "<Known Risks>" \
  --verification-mode "<DOCS|COMPILE|TARGETED_TEST>"
```

반복 항목은 같은 option을 여러 번 사용할 수 있다.

허용 option:
- `--workspace`
- `--title`
- `--goal`
- `--acceptance`
- `--implementation`
- `--test`
- `--risk`
- `--verification-mode`

사용 금지/존재하지 않는 option:
- `--test-plan`
- `--risks`
- `--review-policy`
- `--reviewer`

`Review Policy: RISK_BASED`와 Reviewer Profile은 script가 자동 기록한다. 첫 호출에서 `--workspace`를 포함한 required option을 빠뜨리지 않는다.

## Verification Mode
- `DOCS`: 문서-only
- `COMPILE`: executable behavior 미변경 source
- `TARGETED_TEST`: 실행 로직 변경

변경 성격이 불분명하면 `TARGETED_TEST`를 선택한다.

## Fast Intake 계약
`<repo>/.hermes/project.yaml`, current branch, Base SHA, effective Git changes는 `create_fast_task.py`가 검증/계산한다. Windows bind mount의 CRLF/LF raw status noise는 dirty baseline으로 사용하지 않는다.

Kanban에는 Goal, AC, Implementation Tasks, Test Plan, Risks, Workspace, Branch/Base SHA, pre-existing effective changes, Reviewer Profile, `Review Policy: RISK_BASED`를 기록한다.

Task 생성 성공 후 Interactive Coder는 즉시 멈춘다.

## Worker 결과
- Fast 범위를 벗어나면 `FAST_FLOW_ESCALATION_REQUIRED`로 Block.
- LOW면 evidence를 남기고 `kanban_complete`.
- REVIEW_REQUIRED면 `kanban_request_review`.
- CHANGES_REQUESTED 재작업은 다시 Reviewer에게 보낸다.

## 불변식
- 일반 mutation request는 execution router를 우회할 수 없다.
- semantic skill auto-selection은 실행 승인이나 DIRECT 선택이 아니다.
- 일반적인 `수정/바로 수정/적용/고쳐주세요`는 DIRECT 승인 아님.
- 승인 대기 turn은 `clarify` 후 STOP.
- 승인 전 Spring/Gradle/implementation capability Skill preload 금지.
- DIRECT는 explicit DIRECT selection 이후에만 실행.
- Interactive FAST는 dispatch-only.
- STANDARD_REQUIRED는 Orchestrator 안내 후 STOP.
- Fast dispatch는 canonical CLI 1회 성공을 정상 경로로 한다.
- 기존 사용자 변경을 reset/restore/clean/stash하지 않는다.
- branch/worktree 생성, commit/push/PR/merge 금지.
