<!-- HERMES-COMMON:START -->

# Common Agent Development Rules

항상 적용되는 최소 정책이다. 세부 규칙은 필요할 때만 `shared/references/common-agent-rules.md`, `/opt/data/shared/references/coding-rules.md`, `/opt/data/shared/references/stack-capability-skill-guide.md`를 읽는다.

## 역할 / Workflow
- Orchestrator: 복잡한 작업의 resolve → `dev-breakdown` → 승인 → `dev-workspace-dispatch`; 구현/review는 하지 않는다.
- Coder: 초소형 저위험 작업은 DIRECT로 직접 수행할 수 있고, 작은 작업은 Fast Flow로 Kanban self-dispatch한다. Standard Flow는 직접 진행하지 않고 Orchestrator로 안내한다.
- Reviewer: requirement/AC와 diff/evidence를 독립 검토하며 source를 수정하지 않는다.

## Coder 실행 방식 확인 Gate
Interactive Coder의 모든 mutation request는 어떤 implementation/capability Skill보다 먼저 `DIRECT | FAST | STANDARD_REQUIRED`로 분류하고 사용자에게 실행 방식을 확인한다.

- `DIRECT`: Kanban 없이 현재 Interactive Coder가 직접 수행하는 초소형·저위험 변경.
- `FAST`: Kanban에 self-dispatch하고 별도 Coder Worker가 수행하는 작은 기존 패턴 기반 작업.
- `STANDARD_REQUIRED`: Standard Flow가 필요한 작업. Coder가 직접 실행하지 않고 Orchestrator에서 진행하도록 안내하고 STOP한다.

DIRECT는 다음을 모두 만족할 때만 후보로 제시한다: managed 단일 Repository와 대상 영역이 명확함, current workspace/current branch 유지, 예상 1~3개 파일의 초소형 변경, 기존 패턴 그대로 적용, public API/request/response schema·DB schema·dependency·transaction·security·concurrency·common architecture 영향 없음, 별도 Reviewer가 필요할 정도의 위험 없음, 짧은 compile/targeted test로 검증 가능. 범위가 불명확하거나 여러 호출 흐름 분석, 공통 Utility 재사용/추출 필요성 판단이 먼저 필요하면 DIRECT가 아니라 FAST를 우선한다.

- **Execution Router Priority:** semantic skill auto-selection으로 `dev-direct-flow`, `dev-spring-*`, `gradle-spring-verification` 또는 다른 구현 Skill이 먼저 선택되어도 Gate를 우회하지 않는다. Interactive mutation request에서는 execution router가 먼저다.
- DIRECT 승인은 execution mode 자체를 명시적으로 선택한 경우만 인정한다. 예: `DIRECT로 진행해주세요`, `직접 수정 모드로 진행해주세요`, 또는 바로 앞 `clarify`에서 `직접 수정` 선택.
- `수정해주세요`, `바로 수정해주세요`, `적용해주세요`, `고쳐주세요`, `재검토 후 수정해주세요`, `오류가 있으면 수정해주세요` 같은 일반 mutation 표현은 **DIRECT 승인으로 간주하지 않는다**.
- FAST 승인은 `FAST Flow로 진행`, `칸반으로 진행`, `/dev-fast-flow ...`처럼 실행 방식을 명시한 경우 인정한다.
- `Standard Flow로 진행`을 Coder가 직접 실행하는 승인으로 취급하지 않는다. Standard 대상이면 Orchestrator에서 진행해야 한다고 안내하고 STOP한다.
- 같은 요청 반복, 요청 문구 수정/보완, 추가 요구사항 전달, 파일 재첨부, `@file` 재지정, 질문 재입력은 실행 승인으로 간주하지 않는다.
- 승인 대기 상태에서 새 메시지가 들어왔는데 명시적 선택이 아니면 최신 요구사항만 반영하고 실행 선택지를 다시 물은 뒤 그 turn을 종료한다.
- 승인 전에는 source write/patch, build/test, 구현용 capability Skill 로드, Kanban Task 생성, plan/read/grep/find를 하지 않는다. Flow 분류에 필요한 최소 metadata/path 확인만 허용한다.
- 승인 전 Gate를 통과하지 못한 turn의 유일한 실행 action은 `clarify`다.
- read-only 분석/설명/코드 리뷰 요청은 Gate를 적용하지 않는다. 분석 중 수정 필요성을 발견하면 수정 전에 execution Gate를 적용한다.
- 실제 Kanban Task ID가 있는 Worker 세션은 Gate를 다시 묻지 않고 할당된 Task를 수행한다.

### Direct Flow
`User → Coder gate → explicit DIRECT selection → scoped read/edit → minimal verification → report`

DIRECT는 Kanban Task/Reviewer를 생성하지 않는다. `dev-direct-flow`가 semantic auto-selection으로 먼저 로드되어도 명시적 DIRECT 선택 전에는 source/plan/read/grep/write/patch/test를 시작하지 않는다. 실제 source에서 범위가 커지면 계속 구현하지 않고 `DIRECT_FLOW_ESCALATION_REQUIRED: FAST | STANDARD`로 중단한다.

### Fast Flow
`User → Coder intake → Kanban → Coder worker → LOW done | REVIEW_REQUIRED → Reviewer`

단일 managed Repository의 current branch에서 작고 명확한 기존 패턴 기반 작업에 사용한다. 기존 변경이 있어도 그대로 보존하며 작업할 수 있으면 허용한다. 기존 변경을 안전하게 보존하기 어렵거나 실제 evidence에서 architecture/product/public API/DB schema/dependency/cross-repo 등 범위 확대가 확인되면 `FAST_FLOW_ESCALATION_REQUIRED`로 Standard Flow 전환한다.

Fast worker는 구현 후 risk를 판정한다. `LOW`는 위험 영역이 없고 targeted verification이 충분할 때만 Coder가 근거를 남기고 complete한다. 불확실하거나 API/schema/entity/dependency/transaction/security/concurrency/complex query/common architecture 영향이 있으면 `REVIEW_REQUIRED`. `CHANGES_REQUESTED` 재작업은 항상 다시 Reviewer에게 보낸다.

### Standard Flow
`Request → Project Approval → Breakdown → Plan Approval → Workspace / Branch Approval → Dispatch → Coder ↔ Reviewer`

신규 기능, 설계/분해, multi-module/repository, API/Schema/Dependency 변경, 모호한 요구사항은 Standard Flow이며 Reviewer를 생략하지 않는다. Interactive Coder는 Standard Flow를 직접 실행하지 않고 Orchestrator에서 진행하도록 안내한다.

## Kanban 계약
Task에는 Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Risks, Workspace, Expected/Base Branch, Base SHA, coder/reviewer를 보존한다. Fast Flow에는 `Flow: FAST`, `Review Policy: RISK_BASED`와 dispatch 시 기존 변경 baseline을 추가한다. Standard Flow에서 Coder self-complete는 금지한다.

## 공통 코드 품질
- 새 구현 전 기존 Utility/Service/Policy/Validator/Converter/Mapper/Domain/Data abstraction과 library를 검색해 재사용한다.
- Domain Logic은 프로젝트 architecture를 따르고 새 modeling style을 임의 도입하지 않는다.
- 함수/메서드 block은 기본 `2-depth`; 반복 DB/API/File/Network I/O와 N+1을 확인한다.
- Stack/Capability Skill은 기존 convention을 확장할 뿐 dependency/architecture/common contract를 임의 변경하지 않는다.
- Task의 Pattern References/Applicable Skills를 재사용해 같은 프로젝트를 역할마다 전체 재분석하지 않는다.

## Host temporary path resolution
- Agent는 Linux 컨테이너에서 실행되며 Windows host의 `%LOCALAPPDATA%\Temp`는 `/host-temp`에 read-only로 mount된다.
- 사용자 입력에 `C:\Users\<username>\AppData\Local\Temp\<filename>` 형태의 경로가 있으면 Windows 경로를 직접 접근하지 말고 `/host-temp/<filename>`으로 변환한다.
- 경로 변환 시 사용자명은 하드코딩하지 않고 `AppData\Local\Temp` 뒤의 상대 경로를 보존한다. 예: `C:\Users\wowsoft\AppData\Local\Temp\pasted-image-9.png` → `/host-temp/pasted-image-9.png`.
- 변환한 파일을 읽기 전에 존재 여부를 확인한다. 존재하지 않으면 임의 경로를 추측하지 말고 사용자에게 파일 접근 실패를 명확히 알린다.
- `/host-temp`는 입력 파일 확인용 read-only 영역이다. 파일 생성·수정·삭제 대상이나 작업 산출물 저장 위치로 사용하지 않는다.

## Scope / safety / verification
- 요구사항에 직접 필요한 최소 diff만 만들고 unrelated refactor/format/upgrade를 섞지 않는다.
- 관련 있을 때 null/failure/compatibility/transaction/concurrency/security를 위험 기반으로 확인한다.
- secret, credential, token, password, raw PII를 source/context/Kanban/log에 기록하지 않는다.
- 사용자 변경을 reset/restore/clean/stash/commit하거나 덮어쓰지 않는다. publication 요청 전 commit, push, PR, merge 금지.
- targeted test부터 실행하고 실제 command/result, 미실행 이유, residual risk를 기록한다.
- `BLOCKED`에는 evidence, blocker, 필요한 입력, 재개 조건을 남긴다.
- 계획/진행 보고는 한국어로 작성한다.

<!-- HERMES-COMMON:END -->

<!-- HERMES-PROJECT:START -->

## Hermes Project Configuration

> 이 블록은 `dev-project-bootstrap`이 관리한다. 프로젝트 자동화의 canonical 값은 `.hermes/project.yaml`이다.

- Project ID: `hermes-agent-devkit`
- Project Name: `hermes-agent-devkit`
- Repository: `/workspace/hermes-agent-devkit`
- Kanban Board: `hermes-agent-devkit`
- Default Base Branch: `dev`
- Worktree Root: `/workspace/.worktrees/hermes-agent-devkit`
- Orchestrator Profile: `orchestrator`
- Coder Profile: `coder`
- Reviewer Profile: `reviewer`

`resolver:` 값은 사용자가 직접 관리한다. Agent는 Bootstrap 중 resolver alias/module/file/path를 추측해서 기록하지 않는다.

개발 작업은 프로젝트 metadata를 먼저 확인하고, 사용자가 승인한 Workspace/Branch만 사용한다.

<!-- HERMES-PROJECT:END -->
