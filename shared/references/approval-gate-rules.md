# Standard Flow 승인 Gate 공통 규칙

이 문서는 Standard Flow에서 사용자 승인을 요청하는 모든 Orchestrator 단계의 공통 UI/대화 계약이다.

## 핵심 원칙

1. **한 번의 사용자 확인에서는 하나의 의사결정만 요청한다.**
2. Workspace, Branch, 기존 변경 보존, Coder Model, Plan을 하나의 질문에 합치지 않는다.
3. 각 Gate는 제목, 현재 제안/대상, 번호 선택지를 같은 순서로 보여준다.
4. 자유형 `진행할까요?`, `사용하겠습니다?`, `이대로 할까요?`만 단독으로 출력하지 않는다.
5. 사용자는 번호 대신 자연어 요구사항을 입력할 수 있다.
6. `추가 요구사항`, 수정 요청, 다른 값 제시는 해당 Gate 승인으로 간주하지 않는다.
7. 요구사항을 반영하거나 후보를 바꾼 뒤에는 **같은 Gate를 다시 출력하고 재승인**받는다.
8. 현재 Gate가 승인되기 전에는 다음 Gate를 같은 turn에서 함께 묻지 않는다.
9. 이전 Gate에서 승인된 값은 이후 Gate에서 다시 선택시키지 않는다. 필요한 경우 read-only 요약만 보여준다.
10. Reviewer Model은 사용자 선택 Gate를 만들지 않고 항상 Reviewer profile DEFAULT를 사용한다.

## Standard Flow Gate 순서

`dev-breakdown READY` 이후 신규 Standard Flow의 사용자 결정은 다음 순서로 진행한다.

```text
WORKSPACE_APPROVAL
→ BRANCH_APPROVAL
→ EXISTING_CHANGES_APPROVAL (필요한 경우)
→ CODER_MODEL_APPROVAL
→ PLAN_APPROVAL
→ DISPATCH
```

기존 카드 재작업에서는 승인 증거가 있는 Gate만 `REUSE`할 수 있다. `REQUIRED`인 Gate는 위 순서에서 해당 Gate만 다시 수행하며, 여러 REQUIRED Gate를 한 질문으로 합치지 않는다.

## Gate 1 — Workspace

```text
[Workspace 선택]

작업에 사용할 Workspace를 확인해주세요.

현재 제안:
- Workspace: <workspace>

1. 제안된 Workspace 사용
2. 다른 Workspace 지정
3. 추가 요구사항 입력

번호 또는 요구사항을 입력해주세요.
```

처리 규칙:
- `1`: Workspace 승인 후 다음 Gate로 이동한다.
- `2`: 다른 Workspace를 입력받고 후보를 갱신한 뒤 같은 Gate를 다시 출력한다.
- `3` 또는 자연어 요구사항: 요구사항을 반영한 뒤 같은 Gate를 다시 출력한다.

## Gate 2 — Branch

```text
[Branch 선택]

작업에 사용할 Branch를 확인해주세요.

현재 제안:
- Branch mode: <current | create>
- Branch: <branch>
- Base Branch: <base-branch>

1. 제안된 Branch 사용
2. 다른 Branch 지정
3. 추가 요구사항 입력

번호 또는 요구사항을 입력해주세요.
```

처리 규칙:
- `1`: Branch mode/name 승인 후 다음 Gate로 이동한다.
- `2`: current/create 전략 또는 branch 이름을 입력받고 같은 Gate를 다시 출력한다.
- `3` 또는 자연어 요구사항: 요구사항 반영 후 같은 Gate를 다시 출력한다.

Workspace와 Branch는 서로 다른 Gate다. `Workspace <x>, Branch <y>를 사용하겠습니다?`처럼 한 질문으로 합치지 않는다.

## Gate 3 — Existing Changes

기존 변경 보존 여부가 아직 승인되지 않은 경우에만 사용한다.

```text
[기존 변경 보존 확인]

현재 Workspace의 기존 변경 처리 방식을 확인해주세요.

기본 정책:
- reset/restore/stash/clean 금지
- 기존 변경 전체 보존

1. 기존 변경을 모두 보존하고 진행
2. 상태 확인 후 다시 결정
3. 추가 요구사항 입력

번호 또는 요구사항을 입력해주세요.
```

처리 규칙:
- `1`: preservation approved로 기록하고 `prepare_dispatch.py --confirmed-dirty` fast path를 사용한다.
- `2`: 허용된 full classification을 수행한 뒤 결과를 보여주고 같은 Gate를 다시 출력한다.
- `3` 또는 자연어 요구사항: 요구사항 반영 후 같은 Gate를 다시 출력한다.

## Gate 4 — Coder Model

```text
[Coder 모델 선택]

이번 작업에서 Coder가 사용할 모델 등급을 선택해주세요.

1. PREMIUM
2. DEFAULT
3. 추가 요구사항 입력

번호 또는 요구사항을 입력해주세요.
```

처리 규칙:
- `1`: `PREMIUM` 승인.
- `2`: `DEFAULT` 승인.
- `3` 또는 자연어 요구사항: 요구사항을 반영하되 모델 승인으로 간주하지 않고 같은 Gate를 다시 출력한다.

실제 provider/model은 승인된 Tier를 `flow_model_policy.py resolve`로 해석해 snapshot으로 고정한다. Reviewer는 별도 선택지를 만들지 않고 `DEFAULT`다.

`PREMIUM 모델을 사용하겠습니다?`, `<실제 모델명>을 사용하시겠습니까?` 같은 자유형 단일 질문은 금지한다.

## Gate 5 — Plan

```text
[작업 계획 승인]

다음 작업 계획을 확인해주세요.

<Implementation Plan>

1. 승인
2. 차단
3. 수정 또는 추가 요구사항 입력

번호 또는 요구사항을 입력해주세요.
```

처리 규칙:
- `1`: Plan 승인. 모든 선행 Gate가 승인된 경우에만 Dispatch 가능하다.
- `2`: 현재 작업을 BLOCKED로 유지하고 자동 진행하지 않는다.
- `3` 또는 자연어 수정 요청: `dev-breakdown` 계획을 갱신한 뒤 **같은 Plan Gate를 다시 출력**한다.

계획 수정 후 자동 dispatch하거나, 수정 요청을 승인으로 간주하지 않는다.

## 승인 상태

신규 Standard Flow는 최소 다음 상태를 독립적으로 추적한다.

```text
workspace_approved = false
branch_approved = false
existing_changes_approved = false | not_required
model_approved = false
plan_approved = false
```

Dispatch 조건:

```text
workspace_approved
AND branch_approved
AND (existing_changes_approved OR existing_changes_not_required)
AND model_approved
AND plan_approved
```

하나라도 충족되지 않으면 `prepare_dispatch.py`, `kanban_create`, `kanban_unblock`, worker dispatch를 실행하지 않는다.

## 재승인

승인 뒤 다음 값이 바뀌면 해당 Gate부터 다시 승인한다.

```text
Workspace 변경 → Workspace Gate부터
Branch mode/name 변경 → Branch Gate부터
기존 변경 처리 정책 변경 → Existing Changes Gate부터
Coder Model Tier/Provider/Model 변경 → Coder Model Gate부터
Goal/Acceptance Criteria/주요 구현 계획 변경 → Plan Gate 재승인
```

재승인 시에도 한 Gate에서 여러 결정을 묶지 않는다.
