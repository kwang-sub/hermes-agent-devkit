# Kanban Session History Rules

Kanban Task와 Hermes 대화 세션의 연결은 **append-only execution history**로 보존한다. Session ID는 Task/Parent 관계의 primary key가 아니라 과거 대화 추적과 context recovery를 위한 보조 인덱스다.

## 적용 대상

- Parent 없는 일반 Standard/Direct 실행 카드
- `[자식]` 실행 카드
- `[부모]` tracking 카드

실행 카드와 Parent는 의미가 다르다. **Standard / Direct / Recovery / CHANGES_REQUESTED**는 아래 공통 정책을 사용하며 Flow별 예외 구현을 만들지 않는다.

## 공통 정책 — SESSION_HISTORY_BEST_EFFORT_V1

Session History는 추적 메타데이터다. `unavailable`만으로 구현/review를 BLOCK하지 않는다. Worker Context, Task/Workspace/승인, Work Unit, Verification Provider의 필수 Gate는 그대로 유지한다. `VERIFICATION_PROVIDER_UNAVAILABLE`을 세션 경고로 바꾸지 않는다.

- `captured` (exit 0): 실제 ID를 기록하고 comment delivery를 확인한다.
- `unavailable` (exit 0): `TASK_SESSION_HISTORY_WARNING`과 원인을 남기고 계속한다. `SESSION_ID=UNAVAILABLE`을 실제 session row나 `TASK_SESSION_HISTORY` marker에 넣지 않는다.
- `error` (exit 3): DB 권한/손상/schema/helper 오류다. 시작 시에는 기존 capability 오류 처리로 구현/review mutation 전에 중단한다. 세션 미확인과 동일하게 삼키지 않는다.
- `error` (exit 0): state/history DB 조회·저장 같은 추적 계층 오류다. `TASK_SESSION_HISTORY_WARNING`과 sanitized error type을 남기고 구현/review를 계속한다. `SESSION_HISTORY_RECHECK_REQUIRED=true`를 유지하고 finalize에서 1회 보완한다.
- `invalid` / CLI 입력 오류 (exit 2): Task/Profile/Workspace 등 입력 계약을 수정해야 한다. 기존 context blocker를 유지한다.

`STATE_DB_MISSING`과 `SESSION_MATCH_NOT_FOUND`를 구분한다. 진단을 위해 raw 대화 내용, credential, 다른 프로젝트 DB를 수집하지 않는다. 조회가 이른 시점이라는 가정만으로 원인을 단정하지 않는다.

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

`/opt/devkit/bin/task_session_history.py capture`를 사용한다. Task ID/Workspace는 `kanban_show`에서 읽은 값을 명시적으로 전달하고, profile/profile-home은 현재 worker 역할에 맞게 전달한다.

이 helper는 다음을 임의 추측하지 않는다.

- session id
- profile
- task id
- workspace

Helper는 Hermes profile `state.db`의 실제 `source=kanban` session/message를 `Task ID + Workspace`와 대조한다. Kanban ownership ENV는 터미널 자식에서 scrub될 수 있으므로 lookup 입력으로 사용하지 않는다. History 자체는 persistent `/opt/data/devkit-task-session-history.db`에 저장한다.

실제 session을 찾지 못하면 `SESSION_HISTORY_STATUS=unavailable`, `SESSION_ID=UNAVAILABLE`로 종료한다. 임의 session을 기록하지 않는다.

## DevKit append-only store

Helper는 `/opt/data/devkit-task-session-history.db`의 `task_session_history` table을 사용한다. 별도 `task_session_history_comments` table은 카드 comment의 전달 확인만 저장한다. 기존 history row를 삭제하거나 다시 작성하지 않는다.

```text
PRIMARY KEY (task_id, profile, session_id)
```

기존 `devkit-session-affinity.db`와 분리된 append-only history DB를 사용하므로 최신 resume binding을 변경하지 않는다.

## 시작 capture — 제한 재시도

Worker 시작 시 `kanban_show`의 Task/Workspace와 현재 역할의 profile-home으로 `task_session_history.py capture --phase start`를 1회 호출한다. Helper 안에서만 **최대 3회 조회, 실패 사이 기본 0.5초**로 재시도한다. 성공 시 즉시 반환하고 error/invalid는 재시도하지 않는다. 외부 sleep/retry loop, 다른 profile 조회, 전체 `/workspace` 탐색으로 대체하지 않는다.

```text
kanban_show
→ task_session_history.py capture --phase start
→ captured: comment 전달 확인
→ unavailable: TASK_SESSION_HISTORY_WARNING + 계속
→ 기존 Worker Context / Workspace / 구현 / review Gate
```

Warning은 현재 Worker 실행에서 한 번만 comment한다. 상태/원인/역할/Task를 기록하고 `SESSION_HISTORY_RECHECK_REQUIRED=true`를 유지한다. Warning comment 자체가 실패해도 단순 미확인을 간접 BLOCK 사유로 바꾸지 않는다. 실패 근거를 최종 handoff/verdict에 남긴다. 반복 warning으로 카드를 채우지 않는다.

```text
TASK_SESSION_HISTORY_WARNING
- Task ID: <actual task id>
- Profile: coder | reviewer
- Status: unavailable
- Reason: STATE_DB_MISSING | SESSION_MATCH_NOT_FOUND
- Action: CONTINUE_WITH_WARNING
```

## 카드 comment 전달 확인

`SESSION_HISTORY_NEW`는 **DB row가 새로 생겼는지**만 뜻한다. `SESSION_HISTORY_NEW=false`를 comment 전달 성공의 증거로 사용하지 않는다.

`captured`이면 `SESSION_HISTORY_COMMENT_PENDING`을 확인한다.

1. `false`: 해당 tuple의 comment 전달이 확인됐으므로 중복 comment하지 않는다.
2. `true`: 현재 Task comments에 같은 실제 `Session ID + Profile`의 `TASK_SESSION_HISTORY`가 이미 있는지 확인한다. 초기 `kanban_show` 결과를 재사용하며, comment 응답 유실 등 결과가 불명확할 때만 한 번 read-back한다.
3. marker가 없을 때만 `kanban_comment(marker)`를 1회 호출한다. 성공 또는 정확한 기존 marker를 확인한 뒤 다음 receipt를 기록한다.

```bash
python3 /opt/devkit/bin/task_session_history.py ack-comment \
  --task-id "<Task ID>" --profile coder \
  --session-id "<verified actual Session ID>"
```

Reviewer는 `--profile reviewer`를 사용한다. capture에 별도 `--history-db`를 썼다면 ack에도 같은 경로를 전달한다. 실제 comment 성공/존재 확인 없이 ack하지 않는다. marker가 이미 있으면 ack만 하므로 기존 DB 업그레이드나 ack 재시도에서 중복 comment하지 않는다.

시작 시 captured marker 기록/receipt가 실패하면 `TASK_SESSION_HISTORY_WARNING`으로 남기고 mutation/review를 계속한다. 원인은 세션 미확인과 구분해 실제 추적 기록 오류로 보존하며 `SESSION_HISTORY_RECHECK_REQUIRED=true`를 유지한다. 성공한 receipt 뒤에만 `SESSION_HISTORY_RECHECK_REQUIRED=false`로 관리한다.

## 인계·종료 직전 보완 — SESSION_HISTORY_FINALIZE

미확인 또는 comment 미완료 상태일 때만 **현재 Worker가 제어권을 넘기기 직전** 같은 context로 `capture --phase finalize`를 1회 호출한다. finalize는 sleep 없이 1회 조회한다. 이미 완전히 기록됐으면 생략한다.

- Coder: 구현·검증과 handoff evidence 확정 후, `kanban_request_review` 직전.
- Reviewer: 판정 확정 후, `kanban_complete` 또는 `kanban_request_changes` 직전.
- 다른 원인으로 차단: `kanban_block` 직전. 잘못된 Task/Workspace/권한 context라면 잘못된 카드에 보완하지 않고 원래 context blocker를 유지한다.

이미 확인한 ID의 comment만 미완료라면 `--session-id "<verified ID>"`로 고정해 다른 세션으로 바뀌지 않게 한다. ID 자체가 미확인이면 ID를 추측해 인자로 넣지 않는다. 성공하면 같은 Task에 실제 이력을 추가하고 시작 경고가 보완됐음을 한국어로 남긴다. 시작 경고를 삭제하거나 덮어쓰지 않는다.

finalize의 미확인/추적 저장·comment 오류는 status/reason을 최종 handoff/verdict에 남기되, **세션 보완 실패만으로 기존 구현·검증·리뷰 판정/차단 사유를 바꾸지 않는다.** 잘못된 실행 context는 여전히 차단한다. 보완을 다시 호출하는 무한 루프나 terminal transition 후 도구 호출을 만들지 않는다.

```text
SESSION_HISTORY_FINALIZE (pending일 때만, 최대 1회)
→ captured: 같은 Task의 실제 marker/receipt 보완
→ unavailable/error: 최종 근거에 미완료 상태 보존
→ 원래 kanban_request_review / kanban_complete / kanban_request_changes / kanban_block
```

## Recovery와 역할 분리

Recovery/CHANGES_REQUESTED로 동일 Task가 재개되면 새 Worker의 시작 capture를 수행한다. 기본 unavailable 정책을 적용하기 위해 별도 best-effort 예외 승인을 추가하지 않는다. 기존 Recovery Revision, 승인 Gate, 동일 Task 유지 계약은 바꾸지 않는다. 기존 BLOCKED/TRIAGE Task를 이 기능이 자동 unblock하거나 대체 카드로 생성하지 않는다.

Coder 누락을 Reviewer ID로 대신 채우지 않는다. 새 Recovery 세션은 새로운 실행 이력이지 과거 미확인 세션을 복구했다는 증거가 아니다. 과거 ID를 임의로 역채우지 않는다. Task DONE 이후 백그라운드 수집기를 만들지 않는다.

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

Parent가 없는 카드도 동일한 정책으로 실제 세션이 확인되면 `TASK_SESSION_HISTORY` comment를 가진다. 끝까지 미확인이면 경고와 최종 추적 상태를 남긴다. 따라서 몇 달 뒤 Kanban 카드만 알아도 해당 작업이 수행된 Hermes session들을 역추적할 수 있다.

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
