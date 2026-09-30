# Standard Flow Parent Tracking Rules

Standard Flow의 Parent Task는 **실행 계층이 아니라 연속 작업을 추적하는 durable context card**다. 기존 Kanban/Work Unit 실행 모델은 그대로 유지하고 실제 구현은 항상 개별 Standard Task가 담당한다.

## 목적

Parent Task는 여러 Standard Task가 하나의 큰 목표를 이어서 수행할 때 다음 정보를 보존한다.

- 전체 목표와 현재 계획
- 연결된 하위 Task ID
- 실제 실행 Job ID
- 완료 상태와 구현 요약
- 다음 작업이 이어갈 최소 context

Parent 자체는 Coder/Reviewer에 dispatch하지 않는다.

## 제목 식별 규칙

사용자가 Kanban 목록에서 관계를 즉시 식별할 수 있도록 제목에는 다음 접두어를 사용한다.

```text
[부모] <전체 작업 제목>
[하위] <실제 Standard Task 제목>
```

예:

```text
[부모] 회원가입 기능 구현
[하위] 회원가입 UI 및 입력 검증 구현
[하위] Supabase 회원가입 연동
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
Title: [하위] <현재 Work Unit 제목>

Parent Tracking:
- Parent Task ID: <task-id>
- Parent Title: [부모] <title>
- Relation: CHILD_WORK_UNIT
```

실제 Task는 기존 Standard Flow의 Work Unit/Workspace/API/Verification/Model 계약을 그대로 사용한다.

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
- Title: [하위] <task title>
- Result: DONE
- Implementation Summary: <완료 구현 요약>
```

Job ID를 runtime에서 확인할 수 없으면 추측하지 않고 `UNKNOWN`으로 기록한다.

Parent 이력은 작업 결과 추적용이다. Child의 상세 Plan/Verification 전체를 복제하지 않는다.

## 기존 Parent에 작업 추가/수정

사용자가 기존 Parent에 새 작업을 추가하거나 연결된 작업을 수정하려 하면 Standard Flow를 그대로 사용한다.

```text
Parent 선택/확정
→ 현재 Work Unit breakdown
→ 필요한 Requirement Delta
→ Workspace/Branch/Model/Plan Gate
→ [하위] Task 생성 또는 기존 Task 수정/재개
```

Parent가 있다는 이유로 Child의 Standard Flow 승인 계약을 생략하지 않는다.

## 단건 → 묶음 전환

처음 Parent 없이 시작했어도 이후 범위 확대나 사용자의 명시 요청으로 `PROMOTE_TO_PARENT`가 가능하다.

승인 후:

1. 새 `[부모]` tracking card 생성
2. 기존 Task를 첫 이력/연결 작업으로 기록
3. 이후 새 Standard Task는 `[하위]` 접두어와 Parent Task ID를 가진다

기존 Task를 복제하지 않는다.

## 불변식

- Parent는 실행/dispatch하지 않는다.
- Parent 존재 여부가 Work Unit Boundary 규칙을 완화하지 않는다.
- 실제 변경은 항상 개별 Standard Task에서 수행한다.
- Follow-up Task를 현재 Plan 승인만으로 자동 생성하지 않는다.
- Child 완료 후 다음 Child를 자동 dispatch하지 않는다.
- 새 Child 추가/수정은 새 Standard Flow 요청으로 처리한다.
- Parent/Child 관계는 제목이 아니라 Task ID가 authoritative다.
