---
name: dev-fast-flow
description: Interactive Coder의 mutation request를 DIRECT/FAST/STANDARD_REQUIRED로 라우팅하고, 이미 dispatch된 FAST Task의 후속 요구사항은 기존 Kanban Task로 전달하는 execution router.
version: 0.6.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, fast-flow, direct, kanban, review, intake, follow-up, notification]
    related_skills: [dev-direct-flow, dev-implement-plan, dev-code-review, dev-review-cycle]
    requires_tools: [terminal, clarify]
---

# dev-fast-flow

Interactive Coder의 mutation request에 대한 **최상위 execution router**다. `dev-direct-flow`, `dev-spring-*`, Gradle verification 등 어떤 implementation/capability Skill보다 먼저 적용한다.

```text
User request
    ↓
Interactive Coder?
    ├─ NO, Kanban Worker → assigned Task 수행
    └─ YES
         ↓
Existing active FAST Task follow-up?
    ├─ YES → ACTIVE_TASK_FOLLOWUP → existing Task update/comment → STOP
    └─ NO  → DIRECT | FAST | STANDARD_REQUIRED
```

## EXECUTION SAFETY GATE — MUST RUN FIRST
1. 실제 `HERMES_KANBAN_TASK`가 있는 worker 세션인가?
   - YES: 할당 Task를 수행한다. Interactive Gate를 묻지 않는다.
   - NO: Interactive Coder로 간주한다.
2. 현재 요청이 이 대화에서 이미 dispatch한 FAST Task의 요구사항 추가/수정/방향 변경인가?
   - YES: `ACTIVE_TASK_FOLLOWUP`이다. **Interactive Coder가 구현하지 않는다.** 아래 Active Task Follow-up 계약을 적용한다.
   - NO: 새 mutation request로 보고 기존 DIRECT/FAST/STANDARD_REQUIRED Gate를 적용한다.
3. 새 mutation request라면 semantic skill auto-selection 결과와 무관하게 이 router를 먼저 적용한다.
4. 최소 정보만으로 `DIRECT | FAST | STANDARD_REQUIRED` 후보를 분류한다.
   - DIRECT: 대상이 명확한 초소형 저위험 변경. 대체로 1~3개 파일, 기존 패턴 그대로, API/schema/dependency/DB/transaction/security/concurrency/common architecture 영향 없음.
   - FAST: 단일 managed Repository/current branch의 작은 기존 패턴 기반 작업. 여러 호출 흐름 분석, 공통 코드 재사용 여부 판단, 기존/신규 흐름 비교처럼 source 확인 전 scope가 불명확하면 DIRECT보다 FAST를 우선한다.
   - STANDARD_REQUIRED: 신규 기능/설계, multi-module/repo, API/request/response schema, DB schema, dependency, transaction/security/concurrency/common architecture 정책 결정, 복수 해석 요구사항.
5. 현재 메시지 또는 바로 앞 execution-gate `clarify`에 명시적인 실행 방식 선택이 있는가?
   - DIRECT 승인: `DIRECT로 진행해주세요`, `직접 수정 모드로 진행해주세요`, 또는 바로 앞 `clarify`의 `직접 수정` 선택.
   - FAST 승인: `FAST Flow로 진행`, `칸반으로 진행`, `/dev-fast-flow ...`.
   - Standard 요청: Coder 직접 실행 승인이 아니다. Orchestrator에서 진행하도록 안내하고 STOP.
   - 명시적 선택이 없으면 `clarify` 후 즉시 STOP.
6. `수정해주세요`, `바로 수정해주세요`, `적용해주세요`, `고쳐주세요`, `재검토해주세요`, `오류가 있으면 수정해주세요`는 DIRECT 승인으로 간주하지 않는다.
7. 동일 요청 반복, 문구 보완, 추가 요구사항, 파일 재첨부, `@file` 재지정, 질문 재입력도 실행 승인으로 간주하지 않는다.
8. 승인 대기 중 이런 메시지가 오면 요구사항만 갱신하고 다시 `clarify` 후 STOP.
9. 승인 전 Interactive turn의 유일한 실행 action은 `clarify`다. plan/read/grep/find/write/patch/build/test/Kanban create 금지.
10. DIRECT 선택 시에만 `dev-direct-flow` 계약으로 전환한다. FAST 선택 시 canonical dispatch만 수행하고 STOP한다.

## ACTIVE_TASK_FOLLOWUP — 이미 dispatch된 FAST Task
FAST 승인은 **task-scoped, one-shot dispatch approval**이다. 이전 turn에서 FAST를 승인했다는 사실은 이후 Interactive Coder가 source를 직접 수정할 권한이 아니다.

다음과 같이 현재/방금/진행 중인 FAST 작업을 가리키며 요구사항을 변경하면 follow-up으로 본다.
- `현재 진행중인 작업에 반영해주세요`
- `방금 작업 방향을 이렇게 바꿔주세요`
- `그 작업에서 backend 말고 UI만 수정해주세요`
- `추가로 이것도 반영해주세요`
- `현재 작업에서는 A 대신 B로 해주세요`

### Follow-up 처리 규칙
1. 직전 FAST dispatch 응답에 기록된 Task ID/Key를 우선 재사용한다. Task가 특정되지 않으면 구현을 시작하지 말고 어떤 Task인지 `clarify`한다.
2. 요구사항 변경 turn에서는 source `plan/read/grep/find/write/patch/build/test`를 금지한다. Task 상태 확인과 Kanban follow-up 전달만 허용한다.
3. 아래 helper를 정상 경로에서 정확히 1회 호출한다.

```bash
python3 /opt/custom-skills/coder/dev-fast-flow/scripts/update_fast_task.py \
  --workspace "<Workspace>" \
  --task "<Task ID>" \
  --instruction "<updated user direction>"
```

4. helper 결과가 `STATUS=updated`이면 Interactive Coder는 즉시 STOP한다. 새 Fast Task를 만들거나 직접 구현하지 않는다.
5. Task가 `review`이면 helper가 기존 review를 implementation으로 되돌린 뒤 direction-change comment를 기록한다.
6. Task가 `done`/`archived`이면 기존 Task를 수정하지 않는다. 새 작업으로 진행할지 사용자에게 묻는다.
7. `running` worker는 Hermes의 task comment injection을 통해 새 operator 지시를 받을 수 있으므로 worker 재생성/중복 Task 생성이 기본 경로가 아니다.
8. follow-up이 FAST 범위를 materially 벗어나 architecture/API/schema/dependency/cross-repo 결정이 되면 Task comment로 임의 확장하지 말고 Standard Flow 전환이 필요하다고 안내한다.

Task에 기록되는 comment 형식은 helper가 고정한다.

```text
USER_DIRECTION_CHANGE
- <latest user instruction>

Contract:
- Treat this as the latest requirement for the active FAST task.
- Re-evaluate the current implementation against this instruction.
- Preserve unrelated/pre-existing user changes.
```

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
FAST intake의 책임은 구현 분석이 아니라 eligibility 판정과 dispatch다.
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
허용 option: `--workspace`, `--title`, `--goal`, `--acceptance`, `--implementation`, `--test`, `--risk`, `--verification-mode`.
사용 금지/존재하지 않는 option: `--test-plan`, `--risks`, `--review-policy`, `--reviewer`.

`Review Policy: RISK_BASED`와 Reviewer Profile은 script가 자동 기록한다.

## Verification Mode
- `DOCS`: 문서-only
- `COMPILE`: executable behavior 미변경 source
- `TARGETED_TEST`: 실행 로직 변경
- 변경 성격이 불분명하면 `TARGETED_TEST`를 선택한다.

## Fast Intake 계약
`<repo>/.hermes/project.yaml`, current branch, Base SHA, effective Git changes는 `create_fast_task.py`가 검증/계산한다. Windows bind mount의 CRLF/LF raw status noise는 dirty baseline으로 사용하지 않는다.
Kanban에는 Goal, AC, Implementation Tasks, Test Plan, Risks, Workspace, Branch/Base SHA, pre-existing effective changes, Reviewer Profile, `Review Policy: RISK_BASED`를 기록한다.

Task 생성 성공 후 출력된 Kanban Task ID를 사용해 아래 공통 notification helper를 정확히 한 번 호출한다.

```bash
python3 /opt/data/shared/scripts/kanban_notify_subscribe.py --task-id "<KANBAN_TASK_ID>"
```

- `NOTIFY_STATUS=subscribed`: 정상 구독.
- `NOTIFY_STATUS=disabled` 또는 `warning`: 알림 없이 Fast Flow를 계속하며 Task를 Block하지 않는다.
- 알림 실패를 이유로 Task 재생성, retry loop, approval 대기, 구현 시작을 하지 않는다.
- 신규 Task에만 자동 구독하며 Active Task follow-up에서는 재구독하지 않는다.

알림 helper 호출 뒤 Interactive Coder는 즉시 멈춘다.

## Worker 결과
- Fast 범위를 벗어나면 `FAST_FLOW_ESCALATION_REQUIRED`로 Block.
- LOW면 evidence를 남기고 `kanban_complete`.
- REVIEW_REQUIRED면 `kanban_request_review`.
- CHANGES_REQUESTED 재작업은 다시 Reviewer에게 보낸다.

## 불변식
- 일반 mutation request는 execution router를 우회할 수 없다.
- semantic skill auto-selection은 실행 승인이나 DIRECT 선택이 아니다.
- FAST approval은 task-scoped one-shot이며 Interactive implementation approval이 아니다.
- Active FAST Task 관련 mutation follow-up은 기존 Task update/comment-only 후 STOP한다.
- Active FAST Task follow-up에서 Interactive Coder의 plan/read/grep/find/write/patch/build/test는 금지한다.
- 일반적인 `수정/바로 수정/적용/고쳐주세요`는 DIRECT 승인 아님.
- 승인 대기 turn은 `clarify` 후 STOP.
- 승인 전 Spring/Gradle/implementation capability Skill preload 금지.
- DIRECT는 explicit DIRECT selection 이후에만 실행.
- Interactive FAST는 dispatch/update-only.
- STANDARD_REQUIRED는 Orchestrator 안내 후 STOP.
- Fast dispatch는 canonical CLI 1회 성공을 정상 경로로 한다.
- 기존 사용자 변경을 reset/restore/clean/stash하지 않는다.
- branch/worktree 생성, commit/push/PR/merge 금지.
