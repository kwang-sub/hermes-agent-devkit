---
name: dev-fast-flow
description: 명확하고 작은 단일 Repository 작업을 Coder 대화에서 접수해 Kanban에 self-dispatch하고 coder→reviewer 흐름으로 처리한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, fast-flow, kanban, review, intake]
    related_skills: [dev-implement-plan, dev-code-review, dev-review-cycle]
    requires_tools: [terminal, clarify]
---

# dev-fast-flow

사용자가 **coder 프로필에 직접** 작고 명확한 개발 작업을 요청했을 때 Orchestrator 계획 단계를 생략하고 Kanban 기반 `coder → reviewer` 흐름으로 진입한다.

이 Skill의 Coder 대화 세션은 **intake/router**다. 직접 source를 수정하지 않는다. Fast Flow가 성립하면 Kanban Task를 `coder`에게 생성하고 멈춘다. Gateway dispatcher가 같은 `coder` 프로필의 worker를 실행해 `dev-implement-plan`으로 실제 구현한다.

```text
User
  ↓
Coder interactive chat / dev-fast-flow
  ↓
Kanban Task 생성 (assignee=coder)
  ↓
Gateway dispatcher
  ↓
Coder worker / dev-implement-plan
  ↓
Reviewer / dev-code-review
  ↓
Approve | Request Changes | Block
```

## 1. Fast Flow 적용 조건

다음을 모두 만족할 때만 Fast Flow를 사용한다.

- 대상 managed project가 하나로 명확하다.
- 단일 Repository 작업이다.
- Goal과 완료 조건을 짧게 명시할 수 있다.
- 수정 범위가 작고 기존 패턴을 따르는 구현이다.
- Architecture/Product 설계 결정이 필요하지 않다.
- Public API contract 또는 DB Schema 변경이 필요하지 않다.
- Dependency upgrade/addition이 핵심 작업이 아니다.
- Cross-repository 의존성이 없다.
- 현재 Git workspace가 clean이다.
- 현재 branch에서 작업해도 되는 간단한 작업이다.
- Reviewer 검증 기준을 명확히 작성할 수 있다.

대표적인 Fast Flow 후보:

```text
작은 버그 수정
null/edge-case 처리
기존 패턴 기반 validation 추가
로그/메시지 수정
작은 설정 수정
단순 query/repository 수정
작은 테스트 보완
오타/문서/주석 수정
명확한 소규모 리팩터링
```

## 2. Standard Flow로 보내야 하는 조건

다음 중 하나라도 해당하면 Kanban Task를 Fast Flow로 만들지 않는다.

- 대상 project/repository가 모호함
- workspace가 dirty임
- 새 branch/worktree 선택이 필요함
- 신규 기능의 설계가 필요함
- 여러 module/repository에 걸친 변경
- DB migration/schema 변경
- Public API contract 변경
- dependency 추가/업그레이드
- architecture/transaction/concurrency 정책 결정
- 요구사항 해석이 둘 이상 가능함
- 구현 전에 `dev-breakdown` 수준의 계획이 필요함

이 경우 사용자에게 짧게 다음을 알린다.

```text
이 작업은 Fast Flow 범위를 벗어납니다.
Orchestrator의 Standard Flow로 진행해야 합니다.
이유: <구체적인 이유>
```

Coder가 Orchestrator 역할을 대신해 큰 작업을 임의로 계획하지 않는다.

## 3. 대상 Project / Workspace 확인

사용자가 정확한 project path를 주지 않았으면 현재 context와 `/workspace`의 managed project metadata를 제한적으로 확인한다.

Fast Flow는 `<repo>/.hermes/project.yaml`이 있고 `dev-project-bootstrap` 관리 marker가 있는 repository만 사용한다.

둘 이상의 project가 가능하면 추측하지 말고 project 하나만 확인한다.

파일 수정 전에 최소한 다음을 확인한다.

```bash
git -C "<repo>" status --short --untracked-files=all
git -C "<repo>" branch --show-current
git -C "<repo>" rev-parse HEAD
```

Fast Flow는 clean workspace + current branch만 지원한다. dirty workspace, detached HEAD, branch 생성 요구는 Standard Flow로 보낸다.

## 4. 최소 작업 계약 작성

Orchestrator의 full breakdown은 생략하지만 Kanban에는 최소 계약을 남긴다.

필수 입력:

```text
Title
Goal
Acceptance Criteria (1개 이상)
Implementation Tasks
Test Plan
Known Risks
Workspace
Expected Branch
Base SHA
Reviewer Profile
Flow: FAST
```

Implementation Tasks는 상세 설계서가 아니라 작은 변경을 안전하게 수행할 최소 단계만 작성한다.

예:

```text
Goal:
UserService의 null 입력에서 발생하는 예외를 방지한다.

Acceptance Criteria:
- null 입력에서 기존 NPE가 발생하지 않는다.
- 정상 입력의 기존 동작은 유지된다.
- 관련 테스트가 통과한다.

Implementation Tasks:
- 관련 service와 기존 null 처리 패턴을 확인한다.
- 최소 변경으로 null 처리한다.
- 해당 동작의 회귀 테스트를 추가/수정한다.

Test Plan:
- 관련 unit test
- git diff --check
```

## 5. Kanban self-dispatch

직접 `hermes kanban ...` 명령을 조립하지 않는다. 이 Skill의 deterministic helper를 사용한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/create_fast_task.py" \
  --workspace "<MANAGED_REPO_ROOT>" \
  --title "<TITLE>" \
  --goal "<GOAL>" \
  --acceptance "<AC-1>" \
  --acceptance "<AC-2>" \
  --implementation "<STEP-1>" \
  --implementation "<STEP-2>" \
  --test "<TEST-1>"
```

Helper는 다음을 다시 검증한다.

- workspace가 Git root인지
- `.hermes/project.yaml`이 managed metadata인지
- metadata repository와 실제 path가 일치하는지
- workspace가 clean인지
- current branch가 존재하는지
- dispatch Base SHA가 현재 HEAD인지
- board/coder/reviewer profile metadata가 존재하는지

성공 시 Hermes CLI를 argument-array 방식으로 호출해 다음 계약의 Task를 생성한다.

```text
board      = project metadata kanban.board
assignee   = project metadata profiles.coder
workspace  = dir:<repo-root>
skill      = dev-implement-plan
created-by = coder-fast-flow
```

중복 실행은 idempotency key로 방지한다.

## 6. Task 생성 후 행동

Task 생성이 성공하면 **현재 interactive coder 세션에서 source를 수정하지 않는다.**

다음만 사용자에게 알려주고 멈춘다.

```text
Fast Flow Kanban 등록 완료
- Project: ...
- Task: ...
- Branch: ...
- Coder: ...
- Reviewer: ...

Gateway dispatcher가 coder worker를 실행하고 구현 후 reviewer에게 인계합니다.
```

Gateway가 실행 중이면 dispatcher가 ready task를 가져간다. Dashboard에서 상태를 추적할 수 있다.

## 7. Worker 단계의 Fast Flow escalation

Kanban worker가 실제 source를 확인한 뒤 다음을 발견하면 scope를 넓혀 구현하지 않는다.

```text
요구사항 모호성
Architecture 결정 필요
Public API/DB Schema 변경 필요
Cross-repo 작업 필요
Dependency 변경 필요
예상보다 큰 scope
```

`dev-implement-plan`은 다음 reason으로 `kanban_block`한다.

```text
FAST_FLOW_ESCALATION_REQUIRED
```

Block에는 발견한 evidence와 Standard Flow에서 결정해야 할 내용을 남긴다.

## 8. 불변식

- Fast Flow intake 세션은 구현 코드를 직접 수정하지 않는다.
- Kanban 기록과 Reviewer 단계는 생략하지 않는다.
- Fast Flow 때문에 기존 dirty workspace를 자동 stash/reset/clean하지 않는다.
- branch/worktree를 Fast Flow에서 자동 생성하지 않는다.
- credential/secret/raw config value를 Kanban body에 기록하지 않는다.
- commit/push/PR/merge는 구현/review 단계와 분리한다.
- Fast Flow가 애매하면 속도보다 Standard Flow escalation을 우선한다.
