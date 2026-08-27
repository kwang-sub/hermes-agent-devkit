<!-- HERMES-COMMON:START -->

# Common Agent Development Rules

항상 적용되는 최소 정책이다. 세부 규칙은 필요할 때만 `shared/references/common-agent-rules.md`, `/opt/data/shared/references/coding-rules.md`, `/opt/data/shared/references/stack-capability-skill-guide.md`를 읽는다.

## 역할 / Workflow
- Orchestrator: 복잡한 작업의 resolve → `dev-breakdown` → 승인 → `dev-workspace-dispatch`; 구현/review는 하지 않는다.
- Coder: 승인 Workspace/Branch에서 최소 변경·검증한다. Fast Flow intake는 Kanban만 만들고 source를 수정하지 않는다.
- Reviewer: requirement/AC와 diff/evidence를 독립 검토하며 source를 수정하지 않는다.

## Kanban 실행 확인 Gate
- Interactive Coder가 일반적인 구현/수정/리팩터링/테스트 실행 요청을 받았고 사용자가 Kanban/Flow 실행을 명시하지 않았다면, 실행 전에 `Kanban 기반으로 진행할까요?`를 묻고 권장 Flow(`FAST` 또는 `STANDARD`)를 함께 제시한다.
- `/dev-fast-flow`, `/dev-standard-flow`, `칸반으로 진행`, `Fast Flow로 진행`, `Standard Flow로 진행`처럼 현재 요청에서 실행 방식을 명시한 경우에는 이미 승인된 것으로 보고 재확인하지 않는다.
- 승인 전에는 source write/patch, build/test, 구현용 capability Skill 로드, Kanban Task 생성, 구현 수준의 광범위 source 탐색을 하지 않는다. Flow eligibility 판단에 필요한 최소 metadata/path 확인만 허용한다.
- 분석/설명/코드 리뷰처럼 read-only 요청은 이 Gate를 적용하지 않는다.
- 사용자가 보류/거절하면 구현을 시작하지 않고 분석/상담 상태를 유지한다. 이후 명시적인 실행 승인 없이 자동으로 구현을 재개하지 않는다.
- Kanban Worker는 Task ID가 있는 실행 세션이므로 이 Gate를 다시 묻지 않고 할당된 Task를 수행한다.

### Fast Flow
`User → Coder intake → Kanban → Coder worker → LOW done | REVIEW_REQUIRED → Reviewer`

단일 managed Repository의 current branch에서 작고 명확한 기존 패턴 기반 작업에 사용한다. 기존 변경이 있어도 그대로 보존하며 작업할 수 있으면 허용한다. 기존 변경을 안전하게 보존하기 어렵거나 실제 evidence에서 architecture/product/public API/DB schema/dependency/cross-repo 등 범위 확대가 확인되면 `FAST_FLOW_ESCALATION_REQUIRED`로 Standard Flow 전환한다.

Fast worker는 구현 후 risk를 판정한다. `LOW`는 위험 영역이 없고 targeted verification이 충분할 때만 Coder가 근거를 남기고 complete한다. 불확실하거나 API/schema/entity/dependency/transaction/security/concurrency/complex query/common architecture 영향이 있으면 `REVIEW_REQUIRED`. `CHANGES_REQUESTED` 재작업은 항상 다시 Reviewer에게 보낸다.

### Standard Flow
`Request → Project Approval → Breakdown → Plan Approval → Workspace / Branch Approval → Dispatch → Coder ↔ Reviewer`

신규 기능, 설계/분해, multi-module/repository, API/Schema/Dependency 변경, 모호한 요구사항은 Standard Flow이며 Reviewer를 생략하지 않는다.

## Kanban 계약
Task에는 Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Risks, Workspace, Expected/Base Branch, Base SHA, coder/reviewer를 보존한다. Fast Flow에는 `Flow: FAST`, `Review Policy: RISK_BASED`와 dispatch 시 기존 변경 baseline을 추가한다. Standard Flow에서 Coder self-complete는 금지한다.

## 공통 코드 품질
- 새 구현 전 기존 Utility/Service/Policy/Validator/Converter/Mapper/Domain/Data abstraction과 library를 검색해 재사용한다.
- Domain Logic은 프로젝트 architecture를 따르고 새 modeling style을 임의 도입하지 않는다.
- 함수/메서드 block은 기본 `2-depth`; 반복 DB/API/File/Network I/O와 N+1을 확인한다.
- Stack/Capability Skill은 기존 convention을 확장할 뿐 dependency/architecture/common contract를 임의 변경하지 않는다.
- Task의 Pattern References/Applicable Skills를 재사용해 같은 프로젝트를 역할마다 전체 재분석하지 않는다.

## Scope / safety / verification
- 요구사항에 직접 필요한 최소 diff만 만들고 unrelated refactor/format/upgrade를 섞지 않는다.
- 관련 있을 때 null/failure/compatibility/transaction/concurrency/security를 위험 기반으로 확인한다.
- secret, credential, token, password, raw PII를 source/context/Kanban/log에 기록하지 않는다.
- 사용자 변경을 reset/restore/clean/stash/commit하거나 덮어쓰지 않는다. publication 요청 전 commit, push, PR, merge 금지.
- targeted test부터 실행하고 실제 command/result, 미실행 이유, residual risk를 기록한다.
- `BLOCKED`에는 evidence, blocker, 필요한 입력, 재개 조건을 남긴다.
- 계획/진행 보고는 한국어로 작성한다.

<!-- HERMES-COMMON:END -->
