# 상세 정책 보존본

이 문서는 compact entrypoint 이전의 `custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md` 전체 내용을 보존한다. compact 문서가 지시하는 상황에 필요한 절만 적용한다. 아래 원본의 YAML frontmatter는 참조 정보이며 중첩 skill 선언이 아니다.

---

---
name: dev-workflow-orchestrate
description: Jira 티켓 또는 자유 텍스트 요청을 받아 프로젝트 결정, 사용자 승인, Breakdown 승인, Workspace Dispatch까지 전체 개발 흐름을 조정하는 orchestrator 전용 Skill.
version: 0.1.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, workflow, orchestrator, intake, resolve, approval, breakdown, dispatch, kanban]
    related_skills:
      - dev-work-intake
      - dev-project-resolve
      - dev-project-bootstrap
      - dev-breakdown
      - dev-workspace-dispatch
      - dev-worktree-cleanup
---

# dev-workflow-orchestrate

개발 요청의 최상위 진입점이다.

사용자는 Jira 티켓 또는 자연어 텍스트로 작업을 시작할 수 있다.

예:

```text
DSB-39 처리해줘.
```

```text
mini-calculator 프로젝트에 제곱 기능 추가해줘.
Task Key: CALC-002
```

```text
계산기 프로젝트에서 나눗셈 오류 메시지를 개선해줘.
```

이 Skill은 직접 코드를 구현하지 않는다.

역할:

```text
요청 분류
→ Common Work Item 확보
→ 프로젝트 결정
→ Human Approval Gate
→ dev-breakdown
→ Human Plan Approval Gate
→ dev-workspace-dispatch
→ coder/reviewer로 인계
```

---

# 1. 절대 규칙

Orchestrator는 다음을 직접 수행하지 않는다.

```text
애플리케이션 코드 수정
테스트 코드 구현
리팩터링
Git commit
Git push
PR 생성
코드 리뷰
Workspace 강제 정리
```

실제 구현은 `coder`, 리뷰는 `reviewer`가 담당한다.

---

# 2. Human Approval Gate

두 개의 승인 Gate를 강제한다.

## Gate #1 — Project Approval

다음 경우에만 필요하다.

```text
Agent 또는 dev-project-resolve가 프로젝트를 추론한 경우
```

Resolver 결과가 하나여도 자동 승인하지 않는다.

```text
RESOLVED_SINGLE != PROJECT_APPROVED
RESOLVED_MULTI  != PROJECT_APPROVED
```

반대로 사용자가 처음부터 정확한 프로젝트를 직접 명시한 경우에는
사용자 선택 자체를 프로젝트 승인으로 본다.

## Gate #2 — Plan Approval

모든 작업에서 필수다.

```text
dev-breakdown = READY
```

여도 자동 Dispatch하지 않는다.

사용자에게 계획을 보여주고 명시적 승인을 받은 뒤에만
`dev-workspace-dispatch`를 실행한다.

---

# 3. 전체 상태 머신

```text
START
  ↓
SOURCE_CLASSIFIED
  ↓
WORK_ITEM_READY
  ↓
PROJECT_DECISION
  ├─ 사용자가 프로젝트 명시
  │       ↓
  │   PROJECT_APPROVED
  │
  └─ 프로젝트 미명시
          ↓
    dev-project-resolve
          ↓
  WAITING_PROJECT_APPROVAL
          ↓ 사용자 승인
    PROJECT_APPROVED
          ↓
      dev-breakdown
          ↓
        READY
          ↓
   WAITING_PLAN_APPROVAL
          ↓ 사용자 승인
      PLAN_APPROVED
          ↓
 dev-workspace-dispatch
          ↓
       DISPATCHED
          ↓
    coder ↔ reviewer
          ↓
      DONE/BLOCKED
```

`WAITING_PROJECT_APPROVAL`과 `WAITING_PLAN_APPROVAL`에서는
반드시 그 턴을 종료한다.

같은 턴에서 다음 단계를 실행하지 않는다.

---

# 4. 최초 입력 Source 판별

## Jira

다음처럼 Jira Issue Key가 작업의 주 입력인 경우:

```text
DSB-39 처리해줘
JQCX-278 작업 진행해줘
Jira DSB-39 확인해서 개발해줘
```

`dev-work-intake`를 사용한다.

```text
Jira
→ dev-work-intake
→ normalized Common Work Item
```

Jira Project Key만으로 Repository를 결정하지 않는다.

## Text

일반 자연어 요청은 Text Work Item으로 취급한다.

```text
mini-calculator 프로젝트에 제곱 기능 추가해줘.
```

Text 요청은 사용자의 원문을 보존한다.

요구사항, Acceptance Criteria, 제약을 임의로 추가하지 않는다.

Text 입력에 Task Key가 있으면 그대로 사용한다.

예:

```text
Task Key: CALC-002
```

Task Key가 없으면 Dispatch 전에 사용자에게 확인 가능한 Local Task Key를 제안한다.

권장 형태:

```text
LOCAL-YYYYMMDD-HHMMSS
```

사용자가 다른 Task Key를 지정하면 사용자의 값을 우선한다.

---

# 5. 프로젝트가 사용자에 의해 명시된 경우

예:

```text
mini-calculator 프로젝트에 제곱 기능 추가해줘.
```

정확한 managed project가 확인되면:

```text
dev-project-resolve 생략
Gate #1 생략
```

단, 반드시 확인한다.

```text
<repo>/.hermes/project.yaml 존재
project.id / repository 일치
Git repository 유효
```

Git Repository는 존재하지만 아직 managed project가 아니면
자동 Bootstrap하지 않는다.

사용자에게:

```text
해당 저장소는 아직 Hermes managed project가 아닙니다.
dev-project-bootstrap으로 등록할까요?
```

라고 묻고 STOP한다.

사용자가 승인한 뒤에만 `dev-project-bootstrap`을 실행한다.

---

# 6. 프로젝트가 명시되지 않은 경우

`dev-project-resolve`를 사용한다.

Resolver는 managed project metadata만 대상으로 한다.

```text
/workspace/*/.hermes/project.yaml
```

다음은 하지 않는다.

```text
/workspace 전체 source scan
unmanaged repository 검색
.worktrees 검색
Git history 기반 추론
```

Resolver 결과 후 반드시 Gate #1로 이동한다.

---

# 7. Gate #1 사용자 출력 형식

## RESOLVED_SINGLE

예:

```text
작업 대상 프로젝트 후보를 확인했습니다.

작업:
- DSB-39: ...

Resolver 결과:
- Project: xcomm-server-jre17
- Repository: /workspace/xcomm-server-jre17

매칭 근거:
- alias: XCommServer
- module: XCommServer

이 프로젝트를 작업 대상으로 사용할까요?
```

여기서 STOP한다.

사용자의 명확한 승인 후에만 다음 단계로 진행한다.

## RESOLVED_MULTI

모든 후보와 근거를 번호로 보여준다.

예:

```text
1. xcomm-server-jre17
2. approval-push-api-jre17
3. daishinbank-sso
```

사용자의 명시적 선택을 기다린다.

### v0.1.x 제한

한 Workflow 실행은 기본적으로 하나의 Repository를 대상으로 한다.

사용자가 여러 프로젝트를 동시에 승인하면 자동 Dispatch하지 않는다.

다음 중 하나를 요청한다.

```text
- 우선 진행할 프로젝트 하나 선택
- 프로젝트별 Work Item으로 분리
```

---

# 8. 프로젝트 승인 후 Breakdown

승인된 프로젝트에 대해 `dev-breakdown`을 실행한다.

최소 입력:

```text
Task Key
Approved Project
Original Work Item
Description
Acceptance Criteria
Comments
Constraints
Source reference
```

`dev-breakdown`은 구현을 수행하면 안 된다.

결과:

```text
BLOCKED
```

이면 사유를 사용자에게 보고하고 종료한다.

결과:

```text
READY
```

이면 Gate #2로 이동한다.

---

# 9. Gate #2 — Plan Approval

모든 작업에 적용한다.

사용자에게 최소 다음을 보여준다.

```text
Task Key
Project
Goal
Affected Areas
Implementation Tasks
Acceptance Criteria
Test Plan
Dependencies
Known Risks
Open Questions
Status = READY
```

그리고 반드시 묻는다.

```text
위 계획으로 구현을 진행할까요?
```

여기서 STOP한다.

승인 예:

```text
진행해
승인
이 계획으로 해
좋아 진행
```

다음은 승인으로 처리하지 않는다.

```text
테스트는?
이 파일도 포함돼?
조금 수정해줘
```

Plan이 수정되면 수정된 Plan에 대해 다시 Gate #2 승인을 받는다.

---

# 10. Workspace / Branch 규칙

Plan 승인 후 바로 Dispatch하지 않고, 먼저 Git Workspace / Branch Approval Gate를 수행한다.

사용자에게 최소 다음을 보여준다.

```text
Project
Repository
Current Workspace
Current Branch
Git Status: clean / dirty
Base Branch
Suggested New Branch: feature/<TASK-KEY>
```

사용자는 다음 중 하나를 선택한다.

```text
1. 현재 workspace + 현재 branch 사용
2. 현재 workspace + 새 branch 생성
3. 사용자가 지정한 별도 workspace + 현재 branch 사용
4. 사용자가 지정한 별도 workspace + 새 branch 생성
```

기존 변경이 있으면 `git status --short --untracked-files=all` 결과를 보여주고, 해당 dirty 상태를 작업에 포함해도 된다는 승인을 받은 뒤에만 Dispatch한다.

새 Branch 기본 제안은 다음이다.

```text
feature/<TASK-KEY>
```

다만 현재 branch 사용을 승인받은 경우에는 현재 branch를 Expected Branch로 보존한다.

Task 제목이나 설명을 Branch에 덧붙이지 않는다.

금지:

```text
feature/calc-001-python-cli-calculator
```

---

# 11. Task Key 안전 규칙

허용 기본 패턴:

```text
[A-Za-z0-9][A-Za-z0-9._-]*
```

다음은 거부한다.

```text
/
\
..
공백
경로 separator
Shell meta character
```

예:

```text
DSB-39
CALC-001
LOCAL-20260814-174500
```

---

# 12. Dispatch 결과 검증

`dev-workspace-dispatch` 결과를 그대로 신뢰하지 않는다.

반드시 확인한다.

```text
Project
Board
Assignee = project.yaml profiles.coder
Reviewer = project.yaml profiles.reviewer
Status = ready
Base Branch = project.yaml git.default_base_branch
Base SHA = helper output BASE_SHA
Workspace = user-approved workspace
Kanban workspace = dir:<Workspace>
Branch Mode = current/create
Expected Branch = helper output BRANCH
```

Branch가 Helper 출력 `BRANCH`와 다르면 coder 실행으로 넘기지 않고 BLOCK한다.

Orchestrator가 Branch를 임의로 rename하여 우회하지 않는다.

# 13. Dispatch 이후

정상 Dispatch 이후에는 구현/리뷰에 개입하지 않는다.

```text
coder
  ↓
dev-implement-plan
  ↓
kanban_request_review
  ↓
reviewer
  ↓
dev-code-review
  ├─ CHANGES_REQUESTED
  │      ↓
  │    coder
  │      ↓
  │   reviewer
  │
  └─ APPROVED
         ↓
        Done
```

정상적인 coder ↔ reviewer 수정 루프에서는 사용자 승인을 다시 요구하지 않는다.

다만 reviewer가 `BLOCKED` 또는 human input 상태로 전환하면
사용자에게 원인과 필요한 결정을 보고한다.

---

# 14. Git/PR 미연동 상태

현재 Workflow 범위에는 포함하지 않는다.

```text
commit
push
PR create
merge
```

Reviewer가 APPROVED하여 Kanban이 Done이 되어도 Workspace를 자동 정리하지 않는다.

현재는 다음 상태가 정상이다.

```text
Review = APPROVED
Kanban = Done
Workspace = 유지
Working tree = dirty 가능
```

Git publication 단계가 추가된 뒤에:

```text
APPROVED
→ commit
→ push
→ PR
→ merge
→ dev-worktree-cleanup
```

으로 확장한다.

---

# 15. dev-worktree-cleanup 호출 조건

현재 Git/PR 단계가 없으므로 Workflow가 자동 호출하지 않는다.

사용자가 cleanup을 명시적으로 요청한 경우에만 별도 실행을 고려한다.

`dev-worktree-cleanup`의 안전 규칙을 유지한다.

```text
dirty/untracked legacy Worktree → 삭제 거부
clean legacy Worktree → terminal task 확인 후 삭제 가능
```

---

# 16. Bootstrap 경계

`dev-project-bootstrap`은 다음 조건에서만 사용한다.

```text
사용자가 정확한 Git Repository를 명시
AND
해당 Repository가 아직 managed project가 아님
AND
사용자가 Bootstrap을 명시적으로 승인
```

Resolver가 발견하지 못했다고 unmanaged Repository들을 자동 Bootstrap하지 않는다.

`/workspace` 전체에 Bootstrap을 적용하지 않는다.

---

# 17. 사용자 진행 상태 표시

각 주요 단계에서 짧은 상태를 보여준다.

예:

```text
Workflow: DSB-39

Source        ✅ Jira
Work Item     ✅
Project       ⏳ 사용자 승인 대기
Breakdown     -
Plan Approval -
Dispatch      -
Coder         -
Reviewer      -
```

Plan 승인 대기:

```text
Workflow: CALC-001

Source        ✅ Text
Work Item     ✅
Project       ✅ mini-calculator
Breakdown     ✅ READY
Plan Approval ⏳ 사용자 승인 대기
Dispatch      -
Coder         -
Reviewer      -
```

---

# 18. BLOCKED 조건

다음은 추측하지 않고 BLOCK 또는 사용자 확인을 요청한다.

```text
Jira Intake 실패
explicit project가 여러 managed project와 모호하게 일치
managed project가 아닌 repo의 자동 등록이 필요한 상황
Resolver 결과 없음
Resolver 후보 사용자 승인 없음
Breakdown BLOCKED
Task Key가 안전하지 않음
Plan 승인 없음
Dispatch branch가 사용자 승인 Expected Branch와 불일치
Workspace 검증 실패
Kanban 생성/할당 실패
reviewer가 human input 필요 상태로 종료
```

---

# 19. 하위 Skill 계약

이 Skill은 다음 계약을 기대한다.

```text
dev-work-intake
- Jira → Common Work Item

dev-project-resolve
- managed .hermes/project.yaml only
- RESOLVED_SINGLE / RESOLVED_MULTI / BLOCKED
- 자동 source scan 금지

dev-project-bootstrap
- managed project ensure
- resolver user-managed

dev-breakdown
- 구현 금지
- READY / BLOCKED
- Implementation Plan 생성

dev-workspace-dispatch
- Plan 승인 이후에만 실행
- user-approved Git Workspace
- current/create branch mode와 expected branch 보존
- coder/reviewer 정보 보존

dev-worktree-cleanup
- dirty legacy Worktree 삭제 금지
```

하위 Skill 계약이 맞지 않으면 Orchestrator가 임의 보정하지 않고 BLOCK한다.

---

# 20. 완료 범위

v0.1.x의 범위:

```text
Jira/Text 요청
→ Work Item
→ Project 확정
→ Project Approval Gate
→ Breakdown
→ Plan Approval Gate
→ Dispatch
→ coder/reviewer 상태 추적
→ APPROVED/Done 보고
```

아직 범위 밖:

```text
Git commit/push
PR
merge
자동 cleanup
multi-repository 동시 실행
Notion adapter
Slack adapter
```
