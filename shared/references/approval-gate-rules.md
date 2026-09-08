# Standard Flow 승인 Gate 공통 규칙

이 문서는 Standard Flow에서 사용자 승인을 요청하는 모든 Orchestrator 단계의 canonical UI/대화 계약이다.

## 핵심 원칙

1. **한 번의 사용자 확인에서는 하나의 의사결정만 요청한다.**
2. Project, Requirement Delta, Workspace, Branch, 기존 변경 보존, Coder Model, Plan을 한 질문에 합치지 않는다.
3. 승인 선택은 일반 텍스트 번호 목록이 아니라 Hermes 내장 `clarify` tool의 `choices`를 사용한다.
4. TUI/CLI에서는 `clarify` choice picker의 ↑/↓ 이동 + Enter 선택 UX를 사용한다. 숫자 입력을 기본 UX로 요구하지 않는다.
5. 선택지는 질문 본문에 `1.`, `2.`, `3.`으로 직접 나열하지 않고 반드시 `clarify`의 `choices` 인자로 전달한다.
6. `clarify`가 자동 제공하는 `Other (type your answer)` 행을 추가 요구사항/자유 입력 경로로 사용한다.
7. 다른 후보 지정, 수정 요청, 추가 요구사항은 승인으로 간주하지 않는다. 반영 후 **같은 Gate를 다시 `clarify`로 승인**받는다.
8. 현재 Gate가 승인되기 전에는 다음 Gate를 같은 turn에서 묻지 않는다.
9. 이전 Gate에서 승인된 값은 이후 Gate에서 다시 선택시키지 않는다.
10. Reviewer Model은 별도 선택 Gate 없이 항상 Reviewer profile DEFAULT를 사용한다.
11. **Plan Gate까지 모두 승인되면 Kanban 생성/dispatch는 승인된 실행의 일부다.** `Kanban 카드를 등록할까요?`, `Coder/Reviewer로 배정해도 될까요?` 같은 추가 승인 질문을 하지 않고 즉시 dispatch한다.
12. **이미 승인된 Plan/Task에 사용자가 추가 요구사항·롤백·범위 교체·목표 변경을 제시한 문장 자체는 승인으로 간주하지 않는다.** 먼저 `Requirement Delta`를 정규화해 명시적으로 확인받고, 그 뒤 갱신된 Plan을 다시 승인받아야 한다.

## clarify 사용 계약

각 Gate는 독립된 `clarify` call 하나를 사용한다. 서로 의존하는 Gate를 batch `questions` 한 번에 묶지 않는다.

```text
clarify
  questions:
    - question: "[Workspace 선택]\n현재 제안: <workspace>"
      choices:
        - "제안된 Workspace 사용"
        - "다른 Workspace 지정"
```

Hermes `clarify`는 첫 번째 choice를 Recommended로 표시하므로 현재 Agent가 권장하는 선택을 첫 번째에 둔다. 모델 Gate는 작업 위험도에 따라 `DEFAULT` 또는 `PREMIUM` 중 권장 Tier를 첫 번째에 둔다.

`Other`에서 자유 입력이 반환되면 해당 텍스트를 추가 요구사항으로 처리한다. `다른 Workspace 지정`, `다른 Branch 지정`처럼 별도 값이 필요한 choice를 선택한 경우에는 open-ended `clarify`로 값을 받은 뒤 후보를 갱신하고 같은 선택 Gate를 다시 표시한다.

## Standard Flow Gate 순서

신규 요청:

```text
PROJECT_APPROVAL
→ dev-breakdown READY
→ WORKSPACE_APPROVAL
→ BRANCH_APPROVAL
→ EXISTING_CHANGES_APPROVAL (필요한 경우)
→ CODER_MODEL_APPROVAL
→ PLAN_APPROVAL
→ AUTO_DISPATCH
```

기존 카드/승인 이후 요구사항 변경:

```text
EXISTING_TASK_INSPECTED
→ REQUIREMENT_DELTA_READY
→ REQUIREMENT_DELTA_APPROVAL
→ REQUIRED 기존 Gate 각각 승인 또는 REUSE
→ PLAN_REBUILT
→ PLAN_APPROVAL
→ AUTO_DISPATCH | SAME_TASK_RESUME
```

기존 카드 재작업에서는 승인 증거가 있는 Gate만 `REUSE`한다. `REQUIRED`가 여러 개여도 하나씩 위 순서대로 수행한다.

## Gate R — Requirement Delta

다음 중 하나라도 발생하면 이 Gate는 **필수**다.

- 이미 Plan이 승인된 뒤 새 요구사항이 들어옴
- 이미 Kanban 카드가 생성된 뒤 목표/범위가 바뀜
- 완료/리뷰 완료 카드의 구현을 되돌리고 다른 방식으로 교체함
- Acceptance Criteria, 주요 구현 방식, 롤백 범위, 금지 작업이 바뀜
- 기존 카드 대신 대체/후속 카드를 만들 계획임

사용자의 새 요청 문장을 그대로 승인으로 보지 말고 먼저 아래 형식으로 정규화해 일반 메시지로 충분히 보여준다.

```text
[추가 요구사항 확인]

Requirement Delta:
- 변경 요구사항: <what changes>
- 유지 요구사항: <what remains>
- 롤백/제거 범위: <what is reverted or removed>
- 금지 작업: <must not do>
- 재검토 범위: <what must be revalidated>
- 기존 Task 처리: SAME_TASK_RESUME | REPLACEMENT_TASK | FOLLOW_UP_TASK
```

그 직후 별도 `clarify`를 호출한다.

```text
question:
  [추가 요구사항 확인]
  위 Requirement Delta를 새 작업 범위로 확정할까요?
choices:
  - 요구사항 확정
  - 보류
```

처리 규칙:
- `요구사항 확정`: `requirement_delta_approved = true`.
- `보류`: dispatch/카드 생성 금지.
- `Other`: 수정/추가 입력으로 처리하고 Requirement Delta를 다시 정규화한 뒤 **같은 Gate를 재출력**한다.
- 사용자가 `진행해주세요`, `그렇게 해주세요`, `롤백하고 X만 해주세요`처럼 자연어로 요구를 전달한 것만으로 `requirement_delta_approved=true`로 만들지 않는다.
- Requirement Delta 승인 뒤에는 영향받는 기존 승인만 REUSE/REQUIRED 판정하고, **갱신된 Implementation Plan을 반드시 별도로 다시 승인**받는다.

Requirement Delta가 승인되기 전에는 `prepare_dispatch.py`, `kanban_create`, `kanban_unblock`, same-task resume/migration을 실행하지 않는다.

## Gate 0 — Project

```text
question:
  [Project 선택]
  Project: <project>
  Repository: <repository>
  Base Branch: <base-branch>
choices:
  - 제안된 프로젝트 사용
  - 다른 프로젝트 지정
```

제안 사용 시 승인한다. 다른 프로젝트 또는 Other 입력은 resolve 후 같은 Gate를 다시 표시한다.

## Gate 1 — Workspace

```text
question:
  [Workspace 선택]
  현재 제안: <workspace>
choices:
  - 제안된 Workspace 사용
  - 다른 Workspace 지정
```

제안 사용 시 승인한다. 다른 Workspace 또는 Other 입력은 후보를 갱신한 뒤 같은 Gate를 다시 표시한다.

## Gate 2 — Branch

```text
question:
  [Branch 선택]
  Branch mode: <current | create>
  Branch: <branch>
  Base Branch: <base-branch>
choices:
  - 제안된 Branch 사용
  - 다른 Branch 지정
```

Workspace와 Branch는 서로 다른 Gate다. 다른 Branch 또는 Other 입력은 후보를 갱신한 뒤 같은 Gate를 다시 표시한다.

## Gate 3 — Existing Changes

기존 변경 보존 승인이 아직 없을 때만 사용한다.

```text
question:
  [기존 변경 보존 확인]
  기본 정책: reset/restore/stash/clean 금지, 기존 변경 전체 보존
choices:
  - 기존 변경을 모두 보존하고 진행
  - 상태 확인 후 다시 결정
```

보존 승인 시 `prepare_dispatch.py --confirmed-dirty` fast path를 사용한다. 상태 확인을 선택하면 full classification 결과를 보여준 뒤 같은 Gate를 다시 표시한다. Other 입력도 동일하게 재승인한다.

## Gate 4 — Coder Model

```text
question:
  [Coder 모델 선택]
  이번 작업에서 Coder가 사용할 모델 등급을 선택해주세요.
choices:
  - <권장 Tier: DEFAULT 또는 PREMIUM>
  - <나머지 Tier>
```

선택 가능한 논리 Tier는 `DEFAULT | PREMIUM`뿐이다. 권장 Tier를 첫 번째 choice에 둔다. Other 입력은 자동 승인하지 않는다. Reviewer는 항상 DEFAULT다. 실제 provider/model은 승인 Tier를 `flow_model_policy.py resolve`로 정확히 한 번 해석해 snapshot으로 고정한다.

## Gate 5 — Plan

Implementation Plan 본문은 일반 메시지로 먼저 보여주고 이어서 `clarify`를 호출한다.

```text
question:
  [작업 계획 승인]
  위 Implementation Plan을 어떻게 처리할까요?
choices:
  - 승인
  - 차단
```

`승인`은 Plan 승인이다. 모든 선행 Gate가 승인되었으면 **추가 질문 없이 AUTO_DISPATCH**한다. `차단`은 BLOCKED 유지다. Other 입력은 수정/추가 요구사항으로 처리해 계획을 갱신한 뒤 같은 Plan Gate를 다시 표시한다.

Plan Gate에서 `Other`로 새로운 목표/범위 변경이 들어오면 단순 문구 수정으로 처리하지 않는다. 그 입력이 Requirement Delta에 해당하면 `requirement_delta_approved=false`, `plan_approved=false`로 무효화하고 Gate R부터 다시 수행한다.

## 승인 상태 및 자동 Dispatch

```text
project_approved = false
requirement_delta_approved = true | false | not_required
workspace_approved = false
branch_approved = false
existing_changes_approved = false | not_required
model_approved = false
plan_approved = false
```

신규 요청은 `requirement_delta_approved=not_required`다. 기존 승인 이후 요구사항 변경은 반드시 `true`여야 한다.

모두 승인되는 순간 다음 경로를 즉시 실행한다.

```text
NO_EXTRA_KANBAN_CONFIRMATION
→ prepare_dispatch.py
→ skill preflight
→ kanban_create
→ kanban_show
→ notification subscribe
→ registration notification enqueue
→ kanban_unblock
→ worker dispatch
```

다음 추가 질문은 금지한다.

```text
Kanban 작업 카드를 등록할까요?
Coder/Reviewer 흐름으로 배정해도 될까요?
이제 실제 작업을 시작할까요?
```

하나라도 승인되지 않았다면 `prepare_dispatch.py`, `kanban_create`, `kanban_unblock`, worker dispatch를 실행하지 않는다.

## 재승인

```text
추가 요구사항/롤백/범위 교체 → Requirement Delta Gate + Plan Gate 재승인
Project 변경 → Project Gate부터
Workspace 변경 → Workspace Gate부터
Branch mode/name 변경 → Branch Gate부터
기존 변경 처리 정책 변경 → Existing Changes Gate부터
Coder Model Tier/Provider/Model 변경 → Coder Model Gate부터
Goal/Acceptance Criteria/주요 구현 계획 변경 → Requirement Delta Gate + Plan Gate 재승인
```

재승인 시에도 `clarify` 선택 UI를 사용하고 서로 다른 Gate를 한 질문에 묶지 않는다.
