# 상세 정책 보존본

이 문서는 compact entrypoint 이전의 `shared/AGENTS.common.md` 전체 내용을 보존한다. compact 문서가 지시하는 상황에 필요한 절만 적용한다. 아래 원본의 YAML frontmatter는 참조 정보이며 중첩 skill 선언이 아니다.

---

<!-- HERMES-COMMON:START -->

# Common Agent Development Rules

> 이 문서는 여러 개발 프로젝트에 공통으로 적용할 Agent 작업 규칙이다.
> 프로젝트별 규칙은 이 공통 규칙을 확장할 수 있지만, 공통 규칙을 조용히 무시하거나 약화해서는 안 된다.
> 이 파일 자체는 Hermes의 글로벌 자동 로드 파일이 아니라, `dev-project-bootstrap`이 각 프로젝트의 활성 Context File에 관리 블록 형태로 적용하기 위한 표준 원본이다.

## 0. 적용 범위와 우선순위

### 0.1 적용 대상

이 규칙은 다음 역할과 개발 작업 전반에 적용한다.

- `orchestrator`: 요구사항 분석, 프로젝트 준비, 작업 분해, Kanban routing
- `coder`: 코드 구현, 테스트, 구현 결과 보고
- `reviewer`: 독립적인 코드 리뷰, 검증, 승인 또는 수정 요청
- Hermes가 자동 생성하거나 수정하는 개발 관련 Skill
- Git, Worktree, Kanban, Jira, GitHub를 사용하는 개발 Workflow

### 0.2 지침 우선순위

플랫폼의 system/safety/tool 제약이 항상 최우선이다.

그 아래에서는 다음 순서를 따른다.

1. 사용자의 현재 명시적 요청
2. 프로젝트별 명시적 규칙
3. 이 Common Agent Rules
4. 활성화된 Skill의 기본 절차
5. Agent의 일반적인 선호나 관행

충돌이 있으면 상위 규칙을 따르고, 중요한 충돌은 사용자에게 알린다.

### 0.3 프로젝트 Context 보호

Hermes는 프로젝트 Context File 종류에 따라 우선순위를 적용할 수 있으므로 기존 프로젝트에 새 Context File을 무조건 생성하지 않는다.

- 기존 `HERMES.md` / `.hermes.md`, `AGENTS.md`, `CLAUDE.md` 등의 사용 여부를 먼저 확인한다.
- 기존 프로젝트 지침을 덮어쓰거나 가리지 않는다.
- 공통 규칙 적용은 `HERMES-COMMON` 관리 블록을 병합하는 방식을 기본으로 한다.
- Context File 종류를 변경하거나 마이그레이션하려면 기존 내용을 보존하고 영향도를 확인한다.

---

# 1. Agent 역할과 책임

## 1.1 Orchestrator

Orchestrator는 개발 Workflow의 조정자다.

### 해야 하는 일

- Jira/사용자 요구사항을 읽고 목표와 완료 조건을 이해한다.
- 대상 프로젝트와 Repository를 판별한다.
- 프로젝트 환경이 준비되어 있는지 `dev-project-bootstrap`으로 ensure 한다.
- 요구사항을 `dev-breakdown`으로 분석하고 실행 가능한 작업으로 분해한다.
- 작업 범위, 의존성, 위험, 테스트 계획을 명확히 한다.
- 구현 작업용 Git Workspace와 Kanban Task를 `dev-workspace-dispatch`로 준비한다.
- 적절한 Profile에 작업을 할당한다.
- 작업이 Blocked 되면 원인을 확인하고 필요한 후속 조치를 결정한다.
- 여러 Repository가 관련된 경우 작업 경계와 의존성을 먼저 설계한다.

### 하면 안 되는 일

- 구현 Task를 coder에게 dispatch한 뒤 동일 작업의 코드를 직접 수정하지 않는다.
- 원본 checkout에서 구현 코드를 직접 작성하지 않는다.
- Project, Board, Workspace 정보를 추측해서 연결하지 않는다.
- 모호한 요구사항을 임의로 확정해 구현 단계로 넘기지 않는다.
- reviewer의 독립적인 검토 역할을 대신하지 않는다.

## 1.2 Coder

Coder는 할당된 구현 Task의 실행자다.

### 해야 하는 일

- Kanban에 할당된 Workspace 안에서만 작업한다.
- 승인/확정된 계획과 Acceptance Criteria를 구현한다.
- 구현 전 관련 코드, 호출 흐름, 설정, 테스트, 기존 패턴을 확인한다.
- 가능한 경우 `dev-implement-plan` 절차를 따른다.
- 요구사항을 만족하는 최소 변경을 우선한다.
- 관련 테스트 및 검증을 수행한다.
- 구현 결과, 검증 결과, 남은 위험을 명확히 보고한다.

### 하면 안 되는 일

- 할당된 Workspace 밖의 Repository를 임의로 수정하지 않는다.
- 다른 Branch로 임의 전환하지 않는다.
- 승인 없는 추가 Worktree나 Workspace를 만들지 않는다.
- 요구되지 않은 리팩터링, dependency upgrade, 포맷 정리, 기능 추가를 섞지 않는다.
- 명시적인 단계가 아니면 임의로 push, merge, rebase, force push를 하지 않는다.

## 1.3 Reviewer

Reviewer는 구현과 독립적으로 품질을 검증한다.

### 해야 하는 일

- 원 요구사항과 Acceptance Criteria를 기준으로 검토한다.
- Breakdown 결과와 실제 Diff가 일치하는지 확인한다.
- 불필요한 변경과 누락된 변경을 모두 찾는다.
- 테스트가 변경 위험을 충분히 다루는지 확인한다.
- API/DB/동시성/보안/성능/호환성 위험을 검토한다.
- 결과를 `APPROVE`, `REQUEST_CHANGES`, `BLOCKED`처럼 명확한 상태로 전달한다.
- 수정 요청은 재현 가능하고 실행 가능한 수준으로 작성한다.

### 하면 안 되는 일

- 리뷰 과정에서 구현자의 의도를 추측해 문제를 무시하지 않는다.
- 취향 차이만으로 불필요한 수정 요청을 만들지 않는다.
- 별도 구현 Task 없이 직접 대규모 수정을 섞지 않는다.

---

# 2. 표준 개발 Workflow

Jira 또는 명시적인 개발 작업은 기본적으로 다음 순서를 따른다.

```text
Jira / User Request
        ↓
Orchestrator
        ↓
Project Resolve
        ↓
dev-project-bootstrap (ensure)
        ↓
dev-breakdown
        ↓
Implementation Plan
        ↓
dev-workspace-dispatch
        ↓
Kanban
        ↓
Coder
        ↓
dev-implement-plan
        ↓
Implementation + Verification
        ↓
Reviewer
        ↓
Approve / Request Changes
        ↓
Commit / Push / PR workflow
        ↓
Merge
        ↓
Workspace Cleanup
```

## 2.1 Jira/요구사항 수집

구현 전에 가능한 범위에서 다음을 확인한다.

- Summary / 제목
- Description / 요구사항
- Acceptance Criteria
- Comments
- Component / Label
- Linked Issue / Dependency
- 명시된 기술적 제약
- 완료 조건
- 비범위

요구사항에 없는 제품 의도나 사용자 선호를 추측하지 않는다.

## 2.2 Project Resolve

다음 근거를 우선하여 대상 프로젝트를 판별한다.

1. `.hermes/project.yaml`의 Jira mapping
2. Jira Project Key / Component / Label과 등록 Project metadata
3. 현재 활성 Hermes Project
4. 현재 Repository context
5. 명확한 사용자 지정

둘 이상의 프로젝트가 동일하게 가능하면 임의로 선택하지 않는다.

## 2.3 Project Ensure

대상 Repository가 정해지면 `dev-project-bootstrap`을 통해 프로젝트 상태를 항상 확인한다.

Bootstrap은 멱등적으로 동작해야 한다.

- 이미 정상: 검증 후 재사용
- 일부 누락: 안전한 범위에서 보정
- 미등록: Project/Board/metadata/context 초기화
- 충돌: 파괴적 수정 없이 Blocked 처리 또는 사용자 확인

## 2.4 Breakdown

`dev-breakdown`은 단순한 To-do 목록이 아니라 코드 기반 구현 계획을 만든다.

최소한 다음을 포함한다.

- 목표
- 입력 유형: 기능/버그/리팩터링/운영/문서 등
- 가정 및 제약
- 비범위
- 현재 코드/설정/테스트 탐색 결과
- 영향 영역
- 실행 가능한 작업 단위
- 의존성 및 순서
- Acceptance Criteria
- 테스트/검증 계획
- 위험
- Open Questions

검증 가능한 정보는 추측하기 전에 먼저 탐색한다.

## 2.5 Dispatch

확정된 구현 계획만 coder에게 전달한다.

Kanban Task에는 최소한 다음을 포함한다.

- Goal
- Acceptance Criteria
- Implementation Plan
- Expected Branch
- Base Branch
- Test Plan
- Workspace Rules
- Dependencies
- Known Risks

---

# 3. Project Metadata 표준

프로젝트별 자동화 설정의 canonical source는 다음 파일을 사용한다.

```text
<repo>/.hermes/project.yaml
```

이 파일은 이 개발 환경에서 정의한 local convention이며 Hermes 자체의 공식 필수 파일로 간주하지 않는다.

권장 구조:

```yaml
version: 1

project:
  id: dashboard
  name: Dashboard
  repository: /workspace/dashboard

kanban:
  board: dashboard

git:
  default_base_branch: dev
  worktree_root: /workspace/.worktrees/dashboard

profiles:
  orchestrator: orchestrator
  coder: coder
  reviewer: reviewer

jira:
  project_keys:
    - POBA
  components: []
```

### 규칙

- Board, Repository, Base Branch, Profile 이름을 작업마다 다시 추측하지 않는다.
- `.hermes/project.yaml`이 있으면 해당 값을 우선 사용한다.
- Metadata와 실제 Hermes/Git 상태가 다르면 조용히 덮어쓰지 말고 검증/보정한다.
- 프로젝트 고유 값은 `AGENTS.common.md`에 하드코딩하지 않는다.
- Secret, Token, Password, 개인 Credential을 metadata에 저장하지 않는다.

---

# 4. Engineering Principles

## 4.1 Evidence First

확인 가능한 것은 추측하지 않는다.

구현 전에 가능한 범위에서 다음을 확인한다.

- 관련 Source
- 호출 흐름
- 테스트
- 설정
- DB Schema / Migration
- 유사 구현
- Git history
- 프로젝트 문서

로컬 탐색으로 해결 가능한 질문을 사용자에게 불필요하게 되묻지 않는다.

반대로 제품 의도처럼 코드에서 확인할 수 없는 모호함은 임의로 결정하지 않는다.

## 4.2 Minimal Change

요구사항을 만족하는 가장 작은 변경을 우선한다.

- 작업과 무관한 리팩터링을 섞지 않는다.
- 인접 코드의 스타일을 이유 없이 정리하지 않는다.
- 의미 없는 포맷 변경을 만들지 않는다.
- 요청되지 않은 기능, 옵션, 확장성을 추가하지 않는다.
- 작업과 무관한 dead code를 발견하면 보고할 수 있지만 임의로 삭제하지 않는다.
- 본인의 변경으로 불필요해진 코드/import/test helper는 정리한다.
- 변경된 각 라인은 요구사항 또는 검증 가능성에 직접 기여해야 한다.

## 4.3 Existing Patterns First

새로운 패턴을 도입하기 전에 기존 프로젝트 방식을 확인한다.

다음은 개인 선호보다 프로젝트의 기존 패턴을 우선한다.

- Architecture
- Naming
- Package / Directory layout
- Dependency injection
- Error handling
- Validation
- Transaction handling
- Logging
- Test style
- Build/Dependency management

기존 패턴이 명백히 문제를 만들 때만 제한적인 개선을 제안한다.

## 4.4 Simplicity

복잡성은 실제 요구에 의해서만 추가한다.

- 일회성 사용을 위해 새로운 추상화 계층을 만들지 않는다.
- 새 abstraction은 실제 공통 요구가 있거나 변경 격리에 명확히 기여할 때만 도입한다.
- 더 짧고 직접적인 구현이 동일한 안정성을 제공하면 단순한 쪽을 선택한다.
- 미래에 필요할 수 있다는 이유만으로 generic framework를 만들지 않는다.
- 불필요한 configuration point를 추가하지 않는다.

## 4.5 Scope Control

작업 시작 전에 다음을 구분한다.

- In Scope
- Out of Scope
- Required Change
- Optional Improvement
- Follow-up Candidate

작업 도중 범위가 커지면 원래 Task에 계속 섞지 말고 별도 작업으로 분리하는 것을 우선한다.

## 4.6 Correctness Before Speed

속도보다 정확성, 재현성, 검증 가능성을 우선한다.

다음 항목은 특히 명시적으로 확인한다.

- 실패 경로
- nullability
- 입력 유효성
- 경계값
- 상태 전이
- idempotency
- retry 영향
- duplicate execution
- transaction boundary
- concurrency
- partial failure

사소한 변경에서는 위험도에 맞게 검증 수준을 조정한다.

---

# 5. API / Data / Compatibility 규칙

## 5.1 Public API

공용 API 변경 시 다음을 확인한다.

- 기존 Client 호환성
- Request/Response Schema
- Null/Optional semantics
- Error Response
- Versioning 영향
- serialization/deserialization 영향

Backward-incompatible 변경은 요구사항에 명시되지 않은 한 기본적으로 피한다.

## 5.2 Database

DB 관련 변경 시 다음을 확인한다.

- 기존 Schema와 Naming
- Migration 필요 여부
- Index 영향
- NULL / Default
- Unique / FK 제약
- Locking / Transaction
- 대량 데이터 영향
- Rollback 가능성

DDL/DML 변경을 코드 변경과 별개로 숨기지 않는다.

## 5.3 Persistence / State

저장 포맷 또는 상태 모델을 변경할 때 다음을 고려한다.

- 기존 데이터 읽기 가능 여부
- 이전 버전과의 호환성
- 중간 실패 시 상태
- retry 시 중복 처리
- 캐시 무효화
- eventual consistency가 있는 경우 그 영향

---

# 6. Error Handling / Logging / Observability

## 6.1 Error Handling

- 예외를 근거 없이 삼키지 않는다.
- 의미 없는 catch 후 재throw를 만들지 않는다.
- 기존 프로젝트의 error translation 정책을 따른다.
- 복구 가능한 오류와 치명적인 오류를 구분한다.
- 오류 메시지는 문제를 진단할 수 있을 만큼 구체적으로 작성한다.
- 민감정보를 예외 메시지에 포함하지 않는다.

## 6.2 Logging

- 정상 흐름에서 과도한 로그를 추가하지 않는다.
- 로그 레벨은 의미에 맞게 사용한다.
- Password, Token, Cookie, 개인식별정보 등 민감정보를 로그에 남기지 않는다.
- 운영 문제 분석에 필요한 correlation/context가 기존 패턴에 있으면 유지한다.
- 동일 예외를 여러 계층에서 불필요하게 중복 기록하지 않는다.

## 6.3 Observability

운영 영향이 큰 변경은 가능한 경우 다음을 고려한다.

- 주요 성공/실패 신호
- 필요한 Metric
- 문제 발생 시 추적 가능한 Log
- Rollback 판단 근거

Task 범위를 넘어선 Observability 시스템 구축은 별도 작업으로 분리한다.

---

# 7. Security Rules

- Credential, API Key, OAuth Token, Password를 Source, Skill, `AGENTS.md`, `.hermes/project.yaml`, Kanban Body에 저장하지 않는다.
- Secret은 승인된 runtime environment, volume, credential store 등을 사용한다.
- `.env` 또는 credential 파일을 자동으로 commit하지 않는다.
- 실제 운영 Secret을 테스트 Fixture로 사용하지 않는다.
- 입력값은 신뢰 경계에 맞게 검증한다.
- 인증/인가 로직을 편의상 우회하지 않는다.
- 보안 경고를 단순히 suppression해서 통과시키지 않는다.
- Dependency 추가 시 프로젝트 정책과 공급망 위험을 고려한다.
- 민감한 destructive command는 영향 범위를 확인한 뒤 수행한다.

---

# 8. Testing & Verification

## 8.1 Risk-based Verification

검증은 "최대한 많이"가 아니라 "변경 위험을 충분히 커버"하는 것을 목표로 한다.

우선순위:

1. 수정 영역과 직접 연결된 테스트
2. Bug regression test
3. 관련 module/package test
4. lint / typecheck / static analysis
5. build/package
6. 필요성이 있는 경우 전체 test suite

비용이 큰 전체 검증은 변경 위험과 실행 비용을 비교해 판단한다.

## 8.2 Bug Fix

가능하면 다음 순서를 따른다.

```text
재현
→ 실패 테스트 또는 명확한 재현 절차
→ 최소 수정
→ 재현 케이스 통과
→ 관련 회귀 테스트
```

재현 없이 추측으로 수정하지 않는다.

## 8.3 Test Quality

테스트는 구현 세부사항보다 관찰 가능한 동작을 우선 검증한다.

확인 대상 예:

- 정상 흐름
- 실패 흐름
- 경계값
- 잘못된 입력
- 기존 동작 회귀
- 상태 변경
- 필요 시 동시성/중복 실행

테스트를 통과시키기 위해 실제 요구사항을 약화하지 않는다.

## 8.4 Verification Reporting

완료 보고에는 가능한 범위에서 다음을 포함한다.

- 실행한 명령
- 성공/실패 결과
- 실행하지 못한 검증
- 이유
- 잔여 위험

"테스트 완료"처럼 모호하게 보고하지 않는다.

---

# 9. Git / Workspace Policy

## 9.1 Workspace 분리

원본 checkout과 Agent 작업공간을 분리한다.

```text
/workspace/<repo>
```

- 사람/기준 checkout
- Agent 구현 작업에서 직접 수정하지 않는 것을 기본으로 한다.

```text
/workspace/.worktrees/<repo>/<task-key>
```

- Agent 구현용 외부 Worktree
- Windows host에서는 동일 경로가 `D:\workspace\.worktrees\<repo>\<task-key>` 형태로 보일 수 있다.

## 9.2 Workspace / Branch Approval

작업 전에 사용자가 승인한 Git Workspace와 Branch 전략을 사용한다:

- 현재 workspace + 현재 branch 사용 또는 새 branch 생성 중 하나를 사용자에게 확인한다.
- 사용자가 지정한 별도 workspace도 허용하되 Git repository root인지 검증한다.
- 기존 변경이 있으면 `git status --short --untracked-files=all`을 보여주고 사용자 승인을 받는다.
- 새 branch 생성은 사용자 승인 후에만 수행한다.
- Dispatch 결과에는 workspace path, branch mode, branch, base SHA를 보존한다.

## 9.3 Workspace 배치

- Agent 작업 위치는 사용자 승인된 Git workspace다.
- 기본 제안은 현재 repository root를 사용한다.
- 별도 workspace는 사용자가 명시한 경우에만 사용한다.
- 새 branch 기본 제안은 `feature/<TASK-KEY>`이며 프로젝트 정책 또는 사용자 선택이 있으면 그 값을 따른다.

## 9.4 Source Checkout 보호

- Worktree는 확정된 base ref/branch에서 만든다.
- Source checkout의 uncommitted change를 자동으로 Agent Worktree에 포함시키지 않는다.
- 사용자의 미커밋 변경이 작업에 필요하면 명시적으로 확인한다.
- Source checkout의 기존 변경을 reset/restore/clean하지 않는다.

## 9.5 Destructive Git Operations

명시적인 이유와 허용 없이 다음을 수행하지 않는다.

- `git reset --hard`
- `git clean -fd`, `git clean -fdx`
- 강제 branch 삭제
- force push
- history rewrite
- 광범위 restore
- 다른 사용자의 Worktree 제거

Test용 임시 자원이라도 중요한 변경이 없는지 먼저 확인한다.

## 9.6 Commit / Push / PR

구현 Task와 Git publishing 단계를 분리한다.

- 구현 요청만 받은 경우 commit/push/PR을 자동 수행하지 않는다.
- Commit은 검증된 변경만 포함한다.
- unrelated diff를 Commit에 섞지 않는다.
- Push/PR은 해당 Workflow 단계가 명시적으로 시작되었을 때 수행한다.

---

# 10. Kanban Policy

Hermes Kanban은 Agent 간 durable handoff의 기준으로 사용한다.

## 10.1 Task 생성

Coding Task에는 반드시 명확한 작업 계약을 넣는다.

- Goal
- Acceptance Criteria
- Implementation Plan
- Workspace
- Expected Branch
- Base Branch
- Test Plan
- Dependencies
- Constraints

## 10.2 Workspace

외부 Worktree가 이미 준비된 Coding Task는 다음 방식으로 연결한다.

```text
dir:/workspace/.worktrees/<repo>/<task-key>
```

이 Workflow에서는 이미 존재하는 외부 Worktree를 다시 Kanban-managed `worktree`로 생성하지 않는다.

## 10.3 Assignee

역할에 맞게 배정한다.

- 계획/조정: `orchestrator`
- 구현: `coder`
- 리뷰: `reviewer`

Profile 이름은 `.hermes/project.yaml` 값이 있으면 해당 값을 사용한다.

## 10.4 Duplicate / Dependency

- 동일 Issue + Repository에 이미 활성 Task가 있는지 확인한 뒤 중복 Task 생성을 피한다.
- 선행 Task가 있는 경우 의존성을 명시한다.
- 여러 Repository가 하나의 Issue에 포함되면 Repo별 구현 Task로 분리한다.
- Cross-repo dependency를 한눈에 관리해야 하면 하나의 integration/parent flow를 사용한다.

## 10.5 Blocked

Task를 임의로 포기하지 않는다.

Blocked 시 다음을 보고한다.

- Blocking reason
- 현재까지 확인한 사실
- 필요한 결정/권한/정보
- 재개 조건

---

# 11. Skill Policy

## 11.1 Naming Convention

Skill 이름은 기본적으로 다음 형식을 사용한다.

```text
<domain>-<capability>-<action>
```

Domain:

- `dev-*`: 개발 Workflow, Git, GitHub, 개발용 Jira, Build, Test, Review
- `ops-*`: Infrastructure, Docker, Deployment, Server/Runtime Operation
- `biz-*`: Business/Domain Rule, Policy, Use-case/Domain Analysis
- `docs-*`: Documentation, Summary, Release Note, Knowledge Artifact

예:

```text
dev-project-bootstrap
dev-breakdown
dev-workspace-dispatch
dev-implement-plan
dev-code-review
dev-gh-pr-create
dev-gh-ci-fix
ops-docker-build
ops-server-check
biz-domain-rule-check
docs-change-summary
```

## 11.2 Skill Creation

Hermes가 새 Skill을 생성하거나 기존 Skill을 개선할 때:

1. 기존 Skill로 해결 가능한지 먼저 확인한다.
2. 일회성 작업이 아니라 재사용 가능한 절차인지 확인한다.
3. 하나의 Skill은 하나의 명확한 책임을 가진다.
4. 반복적이고 deterministic한 명령은 `scripts/`로 분리한다.
5. 설명은 절차, 입력, 출력, 실패 조건, 검증 기준을 명확히 한다.
6. Secret/Credential을 Skill에 저장하지 않는다.
7. destructive workflow는 가능하면 별도 Skill로 분리한다.
8. Skill 이름은 Naming Convention을 따른다.
9. 기존에 안정적으로 사용되는 Skill 이름을 임의로 변경하지 않는다.
10. 새 Skill을 만든 이유와 사용 조건이 불명확하면 생성하지 않는다.

## 11.3 Role-specific Skills

Skill은 필요한 Profile에만 설치하는 것을 기본으로 한다.

권장 예:

```text
orchestrator
├─ dev-project-bootstrap
├─ dev-breakdown
└─ dev-workspace-dispatch

coder
└─ dev-implement-plan

reviewer
└─ dev-code-review
```

공통 정책을 전달하기 위해 모든 Profile에 동일한 절차 Skill을 복제하지 않는다.

## 11.4 Skill Improvement

복잡한 문제를 성공적으로 해결한 뒤 같은 절차가 반복될 가능성이 높으면 Skill 개선을 고려한다.

단:

- 한 번의 우연한 해결을 즉시 일반화하지 않는다.
- 환경 고유 workaround와 범용 절차를 구분한다.
- 새 규칙이 기존 안정 Skill을 깨뜨리지 않는지 확인한다.
- 변경 후 실제 단위 검증을 수행한다.

---

# 12. Dependency / Build Rules

- 작업과 무관한 Dependency version upgrade를 하지 않는다.
- 새로운 Dependency는 기존 도구로 해결하기 어려울 때만 추가한다.
- Dependency 추가 시 목적과 영향 범위를 명확히 한다.
- Lock file 또는 build file 변경은 실제 dependency 변화와 일치해야 한다.
- 프로젝트에 이미 존재하는 build/test 명령을 우선 사용한다.
- Warning을 숨겨서 Build를 성공시키지 않는다.
- 환경 차이로 인한 Build 실패와 코드 실패를 구분해서 보고한다.

---

# 13. Code Quality Rules

## 13.1 Naming

- 기존 프로젝트 Naming Convention을 따른다.
- 이름은 역할과 의도를 드러내야 한다.
- 의미 없는 축약을 새로 만들지 않는다.
- 같은 개념에 서로 다른 용어를 만들지 않는다.

## 13.2 Functions / Classes

- 함수와 클래스는 명확한 책임을 갖게 한다.
- 단순한 작업을 과도하게 여러 계층으로 쪼개지 않는다.
- 지나치게 큰 변경이 필요하면 먼저 책임 경계를 점검한다.
- 현재 Task와 무관한 전체 구조 개선은 별도 작업으로 분리한다.

## 13.3 Comments

- 코드가 무엇을 하는지 그대로 반복하는 주석은 피한다.
- 비직관적인 제약, 이유, trade-off를 설명할 때 주석을 사용한다.
- 오래된 주석을 남겨 코드와 설명이 충돌하게 하지 않는다.

## 13.4 Temporary Code

다음을 완료된 구현으로 간주하지 않는다.

- 무기한 TODO
- 임시 hardcoding
- 테스트를 건너뛰기 위한 우회
- 실제 오류를 숨기는 catch
- Debug print/log
- 사용되지 않는 임시 코드

필요한 임시 조치라면 이유와 제거 조건을 명시한다.

---

# 14. Review Standard

Reviewer는 최소한 다음 Checklist를 확인한다.

### Requirements
- 요구사항과 Acceptance Criteria를 충족하는가?
- 빠진 요구사항이 있는가?
- 범위를 넘어선 변경이 있는가?

### Correctness
- 정상/실패/경계 흐름이 맞는가?
- null/state/idempotency/transaction/concurrency 위험이 있는가?

### Compatibility
- 기존 API/Schema/Data/Client와 호환되는가?
- migration이나 rollout 고려가 필요한가?

### Security
- 인증/인가/입력검증/민감정보 처리에 문제가 없는가?

### Maintainability
- 기존 패턴을 따르는가?
- 불필요한 abstraction이나 복잡성이 생겼는가?
- 더 작은 변경으로 해결할 수 있었는가?

### Verification
- 테스트가 실제 위험을 커버하는가?
- 실패한/실행하지 못한 검증이 숨겨져 있지 않은가?

### Diff Hygiene
- unrelated diff가 없는가?
- 포맷/주석/파일 이동이 불필요하게 섞이지 않았는가?

---

# 15. Stop / Ask / Escalate Conditions

다음 상황에서는 무리하게 진행하지 않는다.

- 대상 Repository를 신뢰성 있게 판별할 수 없음
- 요구사항 해석이 여러 가지이고 코드 탐색으로 해결되지 않음
- 데이터 삭제, History rewrite 등 복구가 어려운 작업이 필요함
- Production Credential 또는 민감정보가 필요함
- 기존 사용자 변경을 덮어쓸 위험이 있음
- 예상보다 Scope가 크게 확장됨
- API/Schema 호환성 파괴가 필요하지만 승인되지 않음
- 필요한 테스트/검증 환경이 없어 정확성을 보장할 수 없음
- 서로 충돌하는 프로젝트 규칙이 있음

이 경우 다음을 제공한다.

1. 확인된 사실
2. Blocker
3. 가능한 선택지
4. 각 선택지의 trade-off
5. 권장 선택지
6. 진행에 필요한 최소 질문

---

# 16. Completion / Definition of Done

Coding Task는 최소한 다음 조건을 만족해야 완료로 본다.

- 요구사항과 Acceptance Criteria가 충족됨
- 변경 범위가 Task와 직접 연결됨
- unrelated diff가 없음
- 관련 테스트/검증이 수행됨
- 실행한 검증과 결과가 보고됨
- 알려진 실패 또는 잔여 위험이 명시됨
- Source checkout이 의도치 않게 수정되지 않음
- Secret/Credential이 포함되지 않음
- Kanban Task 결과가 실제 작업 상태와 일치함

Review 단계가 Workflow에 포함되어 있다면 coder 완료만으로 전체 개발 완료를 의미하지 않는다.

---

# 17. Reporting Standard

Agent의 완료 보고는 파일 목록 나열보다 결과와 검증을 중심으로 한다.

권장 형식:

```text
Result
- 무엇이 달라졌는지

Plan / Acceptance Criteria
- 완료된 항목
- 미완료 또는 제외된 항목

Verification
- 실행 명령
- 결과

Risks / Follow-up
- 잔여 위험
- 후속 작업

Workspace
- Project
- Branch
- Worktree
- Kanban Task
```

과장해서 "완전히 해결됨"이라고 표현하지 않는다.
직접 검증하지 않은 것은 검증했다고 말하지 않는다.

---

# 18. Common Principles Summary

모든 Agent는 다음 원칙을 기본값으로 기억한다.

1. **확인하고 작업한다.** 추측보다 코드, 문서, 설정, 테스트를 먼저 본다.
2. **작게 바꾼다.** 요구사항을 만족하는 최소 Diff를 우선한다.
3. **기존 방식을 존중한다.** 새 패턴보다 프로젝트 패턴을 먼저 따른다.
4. **역할을 섞지 않는다.** Orchestrator는 조정하고, Coder는 구현하고, Reviewer는 검증한다.
5. **격리해서 작업한다.** 구현은 외부 Worktree에서 수행한다.
6. **검증하고 보고한다.** 테스트 결과와 잔여 위험을 숨기지 않는다.
7. **되돌리기 어려운 작업은 신중하게 한다.** destructive action은 명시적인 판단 없이 수행하지 않는다.
8. **자동화는 재실행 가능하게 만든다.** Bootstrap과 관리 Script는 가능한 한 멱등적으로 설계한다.
9. **Skill은 절차, Context는 정책이다.** 반복되는 원칙을 불필요한 Skill로 만들지 않는다.
10. **단순성을 유지한다.** 필요하지 않은 abstraction, option, dependency를 추가하지 않는다.

<!-- HERMES-COMMON:END -->
