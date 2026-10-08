# Kanban / Execution Responsibility Boundary

정책 ID: `KANBAN_EXECUTION_BOUNDARY_V1`

Hermes Agent DevKit에서 Kanban은 **무엇을 수행해야 하는지(WHAT)** 와 **현재 작업 상태가 무엇인지(STATE)** 의 source of truth다. 실제 command/process를 **어떻게 실행할지(HOW)** 는 Workflow/role Skill/공통 Execution 계층이 책임진다.

이 정책은 Standard / Direct / Recovery / CHANGES_REQUESTED와 Coder / Reviewer worker에 공통 적용한다. 새로운 승인 Gate를 만들지 않으며 기존 승인 Gate, Work Unit, Verification Contract, Parent/Child, Recovery 계약을 완화하지 않는다.

## 1. Kanban이 소유하는 WHAT / STATE

Kanban Task와 durable comment는 다음 실행 관계와 승인된 작업 계약을 보존한다.

- Task ID, title, goal, requirement / acceptance criteria
- Work Unit Class / Boundary / Current Deliverable
- Project / approved Workspace / Version Control / Branch / Base SHA snapshot
- assignee / lane / approved Coder model/provider snapshot
- lifecycle status: blocked / ready / running / review / changes requested / done 등
- 구조적 Parent/Child 관계
- 실행 선행 관계: `Execution Ordering / Depends On Task IDs`
- approved Recovery Revision / Retry contract
- 승인된 Verification **의도와 요구사항**
  - Target
  - Method 또는 승인 수준의 command/goal
  - Provider
  - Environment Dependency / Required Environment
  - Lifecycle / Fallback Policy
- Coder/Reviewer 결과, blocker, verification evidence, Session History 같은 추적 결과

Parent/Child 관계와 실행 선행 관계는 서로 다른 상태다. Parent 상태 자체로 Child의 실행 여부를 결정하지 않는다.

## 2. Kanban이 소유하지 않는 HOW

다음은 Task status/body/comment를 runtime configuration source로 사용하지 않는다.

- 실제 executable / launcher / wrapper 경로
- build-tool adapter 선택 세부 (현재 DevKit 지원: Maven / Gradle / pnpm)
- timeout 기본값과 phase별 timeout
- idle / stuck detection 방식
- retry 횟수, retry delay, 동일 command 재실행 정책
- process group TERM/KILL/reap 방식
- cache / repository / store / temporary directory 경로
- log capture / diagnostic dump / evidence storage 내부 경로
- Session History DB 저장/재시도 구현
- runtime diagnostic helper의 내부 command
- 공통 process execution 구현 세부

이 항목의 source of truth는 역할 Skill, Project Profile/Toolchain, shared runtime reference, 그리고 공통 Process Execution 계층이다.

승인된 Verification Contract에 `mvn verify`, `./gradlew test`, `pnpm test` 같은 command/goal이 포함될 수 있다. 이는 **검증 의도와 범위**의 승인 evidence이지 raw executable 실행 지시가 아니다. Worker는 현재 role Skill과 canonical adapter를 통해 동일 의도를 관리형 실행으로 변환한다.

## 3. Worker startup adapter

Kanban worker startup adapter는 다음만 수행한다.

1. 할당된 Task만 수행하도록 제한한다.
2. 첫 `kanban_show` 결과를 기준으로 현재 역할 Skill을 load하도록 안내한다.
3. 공통 Session History / Worker Context / Workspace Gate를 role Skill에 따라 수행하도록 안내한다.
4. `KANBAN_EXECUTION_BOUNDARY_V1`을 적용하도록 안내한다.

startup adapter가 Maven/Gradle/Node launcher path, timeout, cache, retry, verification helper path를 직접 지정하지 않는다. 해당 HOW가 바뀌어도 Kanban dispatcher patch를 수정하지 않는 것이 목표다.

### Legacy Reviewer Skill Pin 호환

기존 Kanban Task에 남은 `sdlc-review`는 Reviewer 전용 호환 Skill이다.
구버전 Task가 이를 Coder에게도 `--skills`로 전달하면 Hermes가
`kanban_show` 전에 `Unknown skill(s): sdlc-review`로 종료할 수 있다.

`DEVKIT_LEGACY_REVIEW_PIN_SKIP_V1`은 실제 Worker startup argv 경계에서
**Coder의 `sdlc-review` 사전 로드 인자만** 제외한다.
- Kanban의 승인된 `task.skills` 기록·Task ID·workspace·branch·run ownership은 수정하지 않는다.
- Coder는 `dev-implement-plan`을 사용하고 Reviewer는
  `custom-skills/reviewer/sdlc-review` shim을 통해 `dev-code-review`를 수행한다.
- 알 수 없는 다른 Skill, 새 Task의 잘못된 pin, 역할/승인 오류는 무시하지 않는다.
- Direct/Standard/Recovery/CHANGES_REQUESTED 및 새/재개 Worker에서 동일하게 적용한다.
- 별도 검증 provider 전환, 재할당, 자동 unblock이나 Reviewer 생략을 허용하지 않는다.

## 4. Workflow / Execution 계층

Workflow는 승인된 WHAT을 실행 가능한 contract로 전달하되 runtime implementation detail을 Task에 복제하지 않는다.

Role Skill / Execution 계층은 다음을 결정한다.

```text
Kanban Task / State
        │
        ▼
Role Workflow
        │
        ├─ Project / Toolchain adaptation
        ├─ Verification intent 해석
        ▼
Execution Policy
        │
        ├─ Gradle adapter
        ├─ Maven adapter
        └─ Node adapter
        │
        ▼
Execution Result / Evidence
        │
        ├─ Kanban lifecycle 결과 반영
        └─ Session / diagnostic trace
```

실행 결과는 Kanban 상태를 변경할 수 있지만, Kanban 상태가 launcher/timeout/cache 같은 실행 구현을 역으로 정의하지 않는다.

## 5. Blocking 경계

Kanban과 Workflow가 계속 blocking해야 하는 항목:

- 승인되지 않은 scope / Requirement Delta
- 잘못된 Task / Workspace / Branch / Base SHA
- Work Unit boundary 위반
- Parent/dependency 실행 순서 위반
- 승인된 Verification Provider/환경 요구 미충족
- 실제 build/test/review failure
- Recovery contract 불일치
- 잘못된 lifecycle transition

다음 자체는 Kanban blocker가 아니다.

- runtime helper 내부 구현이 Task body와 동일한 문자열이 아님
- launcher path / timeout / cache 위치가 Task에 기록되지 않음
- Session History의 best-effort 추적 오류

단, 공통 Execution helper 자체가 실행 불가능하여 승인된 검증을 수행할 수 없으면 그 **실행 결과**를 verification capability blocker로 보고한다.

## Task Artifact / Scratch 책임

Project `.hermes/tasks/<task-id>`의 Snapshot과 task artifact는 Recovery/감사 증적이다.
Worker가 범용 JSON parser, Git scope/EOL 검사기, Handoff validator를 매번
새 `*.py`로 생성하지 않는다. Canonical DevKit helper를 우선한다.

일회성 실행 코드가 불가피하면 `/opt/devkit/bin/task_artifacts.py scratch`가
발급한 `/opt/data/devkit/task-scratch` 경로를 사용한다. DONE 상태가 Kanban DB로
확정된 후 notifier/housekeeping 계층만 DevKit 소유 marker를 검사하고 정리한다.
완료 Task의 원본 source, before Snapshot, 최종 verification receipt, Session History,
BLOCKED/REVIEW/CHANGES_REQUESTED 작업 자료는 정리 대상이 아니다.
컨테이너 종료 중 놓친 DONE 정리는 notifier startup reconcile에서 수행한다.

## 6. 변경 규칙

실행정책 변경은 가능한 한 shared execution/reference에서 수행한다. Maven/Gradle/Node마다 동일한 process policy를 Kanban/worker startup에 중복 기록하지 않는다.

새 build tool을 추가할 때 기본 순서는 다음이다.

1. Project/toolchain detection
2. tool adapter 추가
3. 공통 Process Execution 정책 연결
4. role Skill에서 canonical 사용법 정의
5. Kanban에는 승인된 검증 의도와 결과만 기록

Kanban schema/dispatcher patch를 새 실행 도구의 timeout/cache/launcher 설정 저장소로 확장하지 않는다.
