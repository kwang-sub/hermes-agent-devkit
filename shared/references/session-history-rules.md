# Kanban Session History Rules

Kanban Task와 Hermes 대화 세션의 연결은 **append-only execution history**로 보존한다. Session ID는 Task/Parent 관계의 primary key가 아니라 과거 대화 추적과 context recovery를 위한 보조 인덱스다.

## 적용 대상

- Parent 없는 일반 Standard/Direct 실행 카드
- `[자식]` 실행 카드
- `[부모]` tracking 카드

실행 카드와 Parent는 의미가 다르다.

## 실행 카드 Session History

일반 단일 카드와 `[자식]` 카드는 Coder/Reviewer worker가 시작될 때 현재 Hermes session을 실제 profile `state.db`에서 확인한 뒤 다음 marker를 durable comment로 남긴다.

```text
TASK_SESSION_HISTORY
- Session ID: <actual session id>
- Profile: coder | reviewer
- Mode: NEW | RESUME | UNKNOWN
```

동일 `task_id + profile + session_id`는 한 번만 comment로 기록한다. 같은 session 재개는 중복 comment를 만들지 않는다.

한 Task가 여러 세션에서 수행될 수 있으므로 단일 `Session ID` 필드로 덮어쓰지 않는다.

```text
Task
├─ coder session A
├─ reviewer session B
└─ coder session C
```

## Session ID 확인

`scripts/task_session_history.py capture`를 사용한다.

이 helper는 다음을 임의 추측하지 않는다.

- session id
- profile
- task id
- workspace

Dispatcher가 제공한 Kanban context와 Hermes profile `state.db`의 실제 `source=kanban` session/message를 대조한다.

```text
HERMES_KANBAN_TASK
HERMES_KANBAN_WORKSPACE
HERMES_KANBAN_DB
HERMES_PROFILE
HERMES_HOME
HERMES_KANBAN_SESSION_MODE
```

실제 session을 찾지 못하면 `SESSION_HISTORY_STATUS=unavailable`, `SESSION_ID=UNAVAILABLE`로 종료한다. 임의 session을 기록하지 않는다.

## DevKit append-only store

Helper는 기존 `devkit-session-affinity.db`에 별도 `task_session_history` table을 사용한다.

```text
PRIMARY KEY (task_id, profile, session_id)
```

기존 `session_affinity` table의 최신 resume binding은 변경하지 않는다. History 저장은 affinity 선택 실패를 유발해서는 안 된다.

## 카드 comment 기록

worker 시작 시:

```text
kanban_show
→ task_session_history.py capture
→ SESSION_HISTORY_NEW=true 이면 kanban_comment(marker)
→ 기존 구현/review 흐름
```

`SESSION_HISTORY_NEW=false`면 동일 marker를 다시 comment하지 않는다.

History comment 실패는 작업 코드 mutation 전에 capability blocker로 처리한다. Session History가 enabled된 DevKit에서 기록 없이 구현을 진행하지 않는다.

## Parent 카드

`[부모]`는 `Execution: NON_DISPATCH`이므로 자체 Coder/Reviewer execution session이 없다.

Parent는 다음 두 종류만 저장한다.

1. **Management Session History**
   - Orchestrator의 실제 Session ID가 runtime에서 안정적으로 확인 가능한 경우에만 생성/계획수정 session을 기록한다.
   - 안정적인 ID가 없으면 `UNAVAILABLE`을 명시하고 추측하지 않는다.
2. **Child Session Summary**
   - 완료된 `[자식]` 카드의 `TASK_SESSION_HISTORY` marker에서 실제 Session IDs를 읽어 Parent Completed Work에 요약한다.

예:

```text
Completed Work:
- Task ID: t_child
- Job ID: j_123
- Title: [자식] 회원가입 UI 구현
- Session IDs: s_coder_1, s_review_1
- Result: DONE
- Implementation Summary: ...
```

Parent가 child 상세 session metadata 전체를 복제하지 않는다. 상세 profile/mode chronology는 child card가 source of truth다.

## 일반 단일 카드

Parent가 없는 카드도 동일하게 `TASK_SESSION_HISTORY` comment를 가진다. 따라서 몇 달 뒤 Kanban 카드만 알아도 해당 작업이 수행된 Hermes session들을 역추적할 수 있다.

## Context Recovery

새 Orchestrator session에서 과거 작업을 이어갈 때 기본 순서는 다음이다.

```text
Kanban Task/Parent
→ Implementation Summary
→ TASK_SESSION_HISTORY / Child Session Summary
→ 필요 시 해당 Hermes session 조회
→ 현재 repository/workspace 상태 검증
```

Session History가 없어도 Task/Work Unit/Workspace 계약은 유효해야 한다. Session History는 실행 관계를 대체하지 않는다.

## 불변식

- Session ID를 Parent/Child 관계 key로 사용하지 않는다.
- Session ID를 Task ID/Job ID 대신 사용하지 않는다.
- 여러 session을 마지막 값 하나로 덮어쓰지 않는다.
- 발견되지 않은 Session ID를 추측하지 않는다.
- Parent는 worker execution session을 가지지 않는다.
- Parent의 상세 child chronology source of truth는 각 child card다.
