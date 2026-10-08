# Standard Flow Parent Tracking Rules

Standard Flow의 Parent Task는 **실행 계층이 아니라 연속 작업을 추적하는 durable context card**다. 기존 Kanban/Work Unit 실행 모델은 그대로 유지하고 실제 구현은 항상 개별 Standard Task가 담당한다.

## 목적

Parent Task는 여러 Standard Task가 하나의 큰 목표를 이어서 수행할 때 다음 정보를 보존한다.

- 전체 목표와 현재 계획
- 연결된 하위 Task ID
- 실제 실행 Job ID
- 완료 상태와 구현 요약
- 다음 작업이 이어갈 최소 context
- 완료된 자식 Task의 실제 Hermes Session IDs

Parent 자체는 Coder/Reviewer에 dispatch하지 않는다.

## 제목 식별 규칙

사용자가 Kanban 목록에서 관계를 즉시 식별할 수 있도록 제목에는 다음 접두어를 사용한다.

```text
[부모] <전체 작업 제목>
[자식] <실제 Standard Task 제목>
```

예:

```text
[부모] 회원가입 기능 구현
[자식] 회원가입 UI 및 입력 검증 구현
[자식] Supabase 회원가입 연동
```

접두어는 표시용 식별자다. Parent/Child 관계의 authoritative key는 제목 문자열이 아니라 `Parent Task ID`다. 제목 수정 시에도 ID 관계는 유지한다.

## Tracking Mode

Standard Flow는 `dev-breakdown` 이후, 실제 dispatch 전에 다음 값을 확정한다.

```text
Parent Tracking Mode:
- NONE
- NEW_PARENT
- LINK_EXISTING_PARENT
- PROMOTE_TO_PARENT
```

- `NONE`: 단건 Task. Parent 없음.
- `NEW_PARENT`: 새 Parent tracking card를 만든 뒤 현재 Standard Task를 연결.
- `LINK_EXISTING_PARENT`: 기존 Parent에 새 Standard Task를 추가하거나 기존 연결 Task를 수정.
- `PROMOTE_TO_PARENT`: Parent 없이 시작한 기존 단건/연속 작업을 새 Parent로 묶고 기존 Task 이력을 첫 항목으로 연결.

Parent 생성/연결 여부는 자동 mutation하지 않는다. 필요 시 `[작업 관리 방식 승인]` Gate에서 사용자가 승인한다.

## Parent 생성 권장 기준

다음 중 하나가 명확하면 `NEW_PARENT`를 권장한다.

- 둘 이상의 후속 Standard Task가 예상됨
- 여러 세션에 걸쳐 작업할 가능성이 높음
- DESIGN → IMPLEMENTATION/MIGRATION처럼 Work Unit이 연속됨
- 현재 Task 완료 후 별도 follow-up이 이미 알려져 있음
- 사용자가 큰 기능/전환/마이그레이션/구축 단위의 연속 작업을 요청함

작은 버그 수정, 설정 변경, 문구 변경, 단일 bounded 구현은 기본적으로 `NONE`이다.

## Parent Card Contract

Parent는 일반 Kanban card를 tracking 용도로 사용하며 특수 서버 schema를 요구하지 않는다.

```text
Title: [부모] <전체 작업 제목>
Parent Tracking: true
Execution: NON_DISPATCH
Goal: <전체 목표>
Plan: <현재 알려진 후속 작업 요약>
```

Parent는 worker에 unblock/dispatch하지 않는다. child hierarchy/status propagation/자동 progress 계산을 요구하지 않는다.

## Child Task Contract

실제 Standard Task body에는 Parent가 있을 때만 다음을 추가한다.

```text
Title: [자식] <현재 Work Unit 제목>

Parent Tracking:
- Parent Task ID: <task-id>
- Parent Title: [부모] <title>
- Relation: CHILD_WORK_UNIT
```

실제 Task는 기존 Standard Flow의 Work Unit/Workspace/API/Verification/Model 계약을 그대로 사용한다.

## Parent Tracking 실제 개행 강제 — PARENT_TRACKING_NEWLINE_V1

Child body의 관리용 관계는 **물리적으로 서로 다른 줄**에 작성한다.
대시보드는 `Parent Tracking:` 독립 줄과 바로 이어지는 `- ` bullet 필드를
파싱한다. 다음은 유효한 최소 계약이다.

```text
Parent Tracking:
- Parent Task ID: t_0e028558
- Relation: CHILD_WORK_UNIT

<기존 Task 본문을 변경 없이 유지>
```

`- Parent Title: [부모] <title>`은 ID와 Relation 사이의 선택 필드다.
이 블록을 기존 본문에 추가할 때는 본문과 **빈 줄로 구분**한다.
한 문장에 `Parent Task ID: t_... (tracking only)`만 삽입하거나,
문자 `\\n`을 실제 줄바꿈 대신 넣는 방식은 허용하지 않는다.

- 신규 Child의 생성, 기존 Child의 Parent 참조 추가, Parent 승격/연결 모두 같은 계약을 적용한다.
- 실행 의존성이 없는 **참조만 추가**하는 경우에도 위 최소 블록이 필요하며 native `task_links`/`kanban_create.parents`를 수정하지 않는다.
- DevKit의 canonical `/opt/devkit/bin/parent_tracking_body.py`는 기존 본문을 보존하면서 올바른 개행 블록을 만들고, `--check-only --parent-id <task-id>`로 검증한다.
- `--parent-id`를 명시한 기존 카드 갱신 시 다른 Parent Task ID가 발견되면 자동 재연결하지 않고 오류를 반환한다.
- Hermes의 Kanban create/edit/dashboard PATCH 실행 경로도 명시적인 Parent 관계를 동일 형식으로 정규화하며, 필수 ID/Relation이 손상된 기존 블록은 실패로 처리한다.
- 수정 후 `kanban_show` read-back으로 저장된 **실제** `body`의 Parent ID와 Relation이 서로 다른 독립 줄인지 확인한다. 주석만 추가하거나 부모 댓글만 작성한 것은 관계 성립으로 간주하지 않는다.
- 비관련 Task의 본문, 기존 Work Unit/검증 증적, Task 상태, 실행 선행 관계는 유지한다. 기존 전체 Kanban 카드에 대한 무단 일괄 변경은 하지 않는다.

기존 카드 참조만 추가할 때는 원본 전체 body를 작업용 파일에 준비한 뒤:

```bash
python3 /opt/devkit/bin/parent_tracking_body.py \
  --input-file "<existing-body.txt>" \
  --parent-id "t_0e028558" \
  --output-file "<updated-body.txt>"

# 공식 Kanban edit 경로로 full body 저장 후 다시 읽은 body를 확인한다.
python3 /opt/devkit/bin/parent_tracking_body.py \
  --input-file "<readback-body.txt>" \
  --parent-id "t_0e028558" \
  --check-only
```

기존 카드의 제목, 승인/진행 상태, Session History, native 실행 dependency를
변경하지 않은 채 본문에 관계 메타데이터만 추가해야 한다.

## Parent 관계와 실행 순서 분리

Parent/Child 관계와 Work Unit 실행 순서는 서로 다른 계약이다.

```text
Structural Parent:
- Parent Task ID: <approved-parent-task-id | NONE>
- Relation: CHILD_WORK_UNIT

Execution Ordering:
- Mode: INDEPENDENT | SEQUENTIAL
- Depends On Task IDs: <task-id[, ...] | NONE>
```

규칙:

- DevKit의 **구조적 Parent Tracking은 Task body metadata만 사용**한다. `Parent Task ID` + `Relation: CHILD_WORK_UNIT`이 authoritative relationship이다.
- `kanban_create.parents` / Hermes native `task_links`는 실행 dependency 의미를 가지므로 **구조적 Parent Tracking에 사용하지 않는다**. Parent Tracking Child 생성 시 `parents` 인자는 생략하거나 빈 목록으로 둔다.
- 직전 Task, 이전 완료 Task, 선행 Work Unit, Reviewer 대상 Task도 DevKit이 native `parents`로 연결하지 않는다. 실행 순서는 Task body의 `Execution Ordering` 계약으로만 기록한다.
- `Mode: SEQUENTIAL`이고 `Depends On Task IDs`가 있으면 Orchestrator가 해당 Task 상태를 확인해 모두 `DONE`일 때만 현재 Child를 unblock/dispatch한다.
- `Mode: INDEPENDENT`이면 실행 선행 Task가 없으며 Parent 상태와 무관하게 일반 dispatch 계약을 따른다.
- Parent는 `Execution: NON_DISPATCH` tracking card이므로 Parent의 `BLOCKED`/`READY` 상태를 Child의 실행 선행 조건으로 사용하지 않는다.
- Task 생성 후 read-back에서 Child body의 `Parent Task ID` / `Relation`이 승인 계약과 다르면 `PARENT_TRACKING_METADATA_MISMATCH`로 처리하고 unblock/dispatch하지 않는다.
- read-back에서 DevKit이 만들지 않은 native parent link가 현재 새 Child에 존재하면 `NATIVE_PARENT_LINK_PRESENT`로 처리하고 자동 unlink/우회하지 않는다.

예:

```text
[부모] P
├─ [자식] A   Execution Ordering: INDEPENDENT
├─ [자식] B   Execution Ordering: SEQUENTIAL, Depends On: A
└─ [자식] C   Execution Ordering: SEQUENTIAL, Depends On: B

관리 관계(metadata): P → A, P → B, P → C
실행 순서(body): A → B → C
native task_links: NONE
금지 관계: P → A → B → C 를 Hermes native parents로 표현
```

## Legacy native parent link 처리

이 정책 적용 전에 DevKit이 구조적 Parent를 `kanban_create.parents`로 생성한 기존 Child는 `LEGACY_NATIVE_PARENT_LINK`로 본다.

- 신규 Standard Flow/dispatch는 같은 방식을 반복하지 않는다.
- 기존 카드의 native link를 unrelated 작업에서 자동 unlink하지 않는다.
- 기존 Task를 재개해야 하면 사용자가 직접 정리하거나 승인된 Recovery/Requirement Delta에서만 native link 제거를 수행한다.
- Parent/Child 목록 표시는 native `task_links`가 아니라 Child body의 Parent Tracking metadata를 사용하므로 기존/신규 UI tracking은 실행 dependency와 분리한다.
- legacy 카드에 body metadata가 이미 있으면 그것을 관리 관계의 source of truth로 사용한다. metadata가 없으면 제목만으로 관계를 추측하지 않는다.

## Parent 생성 시점

신규 요청에서는 `dev-breakdown`이 Work Unit과 follow-up을 분석한 뒤 Parent 필요성을 판정한다.

```text
Project 승인
→ dev-breakdown
→ Parent Tracking Mode 판정
→ [작업 관리 방식 승인] (REQUIRED일 때)
→ 나머지 Standard Flow Gate
→ Parent 생성/선택
→ 현재 Task dispatch
```

`NONE`이 명백한 단건 작업에는 Gate를 추가하지 않는다.

## 작업 관리 방식 승인 Gate

Parent 생성/전환/기존 Parent 연결처럼 durable tracking 구조를 바꾸는 경우에만 사용한다.

```text
question:
  [작업 관리 방식 승인]
  이번 작업의 연속 작업 관리 방식을 승인할까요?

choices 예:
- 새 부모 작업으로 묶어서 진행
- 단건 작업으로 진행
```

기존 Parent 연결 시:

```text
choices:
- 제안된 부모 작업에 연결
- 단건 작업으로 진행
- 다른 부모 작업 지정
```

단건 → 묶음 승격 시:

```text
choices:
- 부모 작업을 생성해 기존 작업부터 연결
- 현재처럼 단건 작업 유지
```

이 Gate는 Parent tracking 결정만 승인하며 Workspace/Branch/Model/Plan 승인을 대신하지 않는다.

## Lazy Child Creation

Parent에 전체 하위 카드를 미리 생성하지 않는다.

```text
Parent Plan
→ 현재 Standard Task만 생성
→ 완료
→ Parent history append
→ 다음 요청에서 새 Standard Flow
→ 다음 Child 생성
```

따라서 앞 Task의 결과로 후속 계획이 바뀌어도 아직 생성되지 않은 카드를 수정/삭제할 필요가 없다.

## Parent History Append

연결된 Child가 DONE되면 Orchestrator는 Parent에 최소 다음 durable 이력을 append한다.

```text
Completed Work:
- Task ID: <task-id>
- Job ID: <job-id | UNKNOWN>
- Title: [자식] <task title>
- Session IDs: <child TASK_SESSION_HISTORY의 실제 session ids | UNAVAILABLE>
- Result: DONE
- Implementation Summary: <완료 구현 요약>
```

Job ID를 runtime에서 확인할 수 없으면 추측하지 않고 `UNKNOWN`으로 기록한다. Session IDs는 자식 카드의 `TASK_SESSION_HISTORY` durable comments에서 읽는다. 자식에 실제 Session ID가 없으면 `UNAVAILABLE`을 기록하며 추측하지 않는다.

Parent 이력은 작업 결과 추적용이다. Child의 상세 Plan/Verification 전체를 복제하지 않는다.

## Parent Session 추적

Parent는 `Execution: NON_DISPATCH`이므로 Coder/Reviewer 실행 Session을 직접 갖지 않는다.

Parent 자체의 생성/계획 수정에 대해서는 현재 Orchestrator Session ID가 runtime에서 **안정적으로 확인 가능한 경우에만** 다음 Management History를 comment로 남긴다.

```text
PARENT_MANAGEMENT_SESSION
- Session ID: <actual orchestrator session id>
- Action: CREATED | PLAN_UPDATED | CHILD_LINKED
```

Orchestrator Session ID를 신뢰할 수 있게 확인할 수 없으면 `Session ID: UNAVAILABLE`을 명시하고 임의 값을 만들지 않는다.

Parent에서 과거 구현 대화를 찾는 primary 경로는 Completed Work의 `Session IDs` → 해당 자식 카드의 상세 `TASK_SESSION_HISTORY`다.

## 기존 Parent에 작업 추가/수정

사용자가 기존 Parent에 새 작업을 추가하거나 연결된 작업을 수정하려 하면 Standard Flow를 그대로 사용한다.

```text
Parent 선택/확정
→ 현재 Work Unit breakdown
→ 필요한 Requirement Delta
→ Workspace/Branch/Model/Plan Gate
→ [자식] Task 생성 또는 기존 Task 수정/재개
```

Parent가 있다는 이유로 Child의 Standard Flow 승인 계약을 생략하지 않는다.

## 단건 → 묶음 전환

처음 Parent 없이 시작했어도 이후 범위 확대나 사용자의 명시 요청으로 `PROMOTE_TO_PARENT`가 가능하다.

승인 후:

1. 새 `[부모]` tracking card 생성
2. 기존 Task를 첫 이력/연결 작업으로 기록
3. 이후 새 Standard Task는 `[자식]` 접두어와 Parent Task ID를 가진다

기존 Task를 복제하지 않는다.

## 불변식

- Parent는 실행/dispatch하지 않는다.
- Parent 존재 여부가 Work Unit Boundary 규칙을 완화하지 않는다.
- 실제 변경은 항상 개별 Standard Task에서 수행한다.
- Follow-up Task를 현재 Plan 승인만으로 자동 생성하지 않는다.
- Child 완료 후 다음 Child를 자동 dispatch하지 않는다.
- 새 Child 추가/수정은 새 Standard Flow 요청으로 처리한다.
- Parent/Child 관계는 제목이 아니라 Task ID가 authoritative다.
- 구조적 Parent Tracking은 Child body의 `Parent Task ID` / `Relation: CHILD_WORK_UNIT` metadata만 사용한다.
- `kanban_create.parents` / native `task_links`를 구조적 Parent Tracking에 사용하지 않는다.
- 실행 순서는 `Execution Ordering / Depends On Task IDs`로 분리하며 선행 Task 완료 여부는 unblock/dispatch 전에 확인한다.
- Parent 상태는 Child 실행 선행 조건이 아니다.
- 생성 후 Parent Tracking metadata가 승인된 Parent Task ID와 다르면 `PARENT_TRACKING_METADATA_MISMATCH`로 중단한다.
- 기존 legacy native link는 unrelated 작업에서 자동 unlink하지 않는다.
- Parent의 자식 Session 요약은 실제 child `TASK_SESSION_HISTORY`만 사용하며 Session ID를 추측하지 않는다.
