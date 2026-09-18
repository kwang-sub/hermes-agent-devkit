<!-- HERMES-COMMON:START -->

# Common Agent Development Rules

항상 적용되는 최소 정책이다. 세부 규칙은 필요할 때만 `shared/references/common-agent-rules.md`, `/opt/data/shared/references/coding-rules.md`, `/opt/data/shared/references/stack-capability-skill-guide.md`를 읽는다.

## 역할 / Workflow
- Orchestrator: 모든 새 mutation request의 실행 진입점이다. 요청을 `DIRECT | STANDARD`로 분류하고 승인/dispatch를 담당하며 구현/review는 하지 않는다.
- Coder: **Kanban에 할당된 Task만** 구현한다. Interactive Coder가 새 요청을 직접 수정하거나 self-dispatch하지 않는다.
- Reviewer: Direct/Standard 모두 requirement/AC와 diff/evidence를 독립 검토하며 source를 수정하지 않는다.

## Orchestrator 실행 방식 Gate
새 mutation request는 implementation/capability Skill보다 먼저 Orchestrator가 `DIRECT | STANDARD`로 분류한다.

### Direct Flow
`Request → Orchestrator → Direct eligibility → Flow/Model/Compact Plan 승인 → dev-workspace-dispatch → Coder → Reviewer`

Direct는 planning shortcut이지 구현 shortcut이 아니다. 다음을 모두 만족할 때만 후보가 된다.

- managed 단일 Project와 current workspace/current branch가 명확함
- 하나의 `IMPLEMENTATION | REFACTOR` Work Unit, `SINGLE_UNIT`
- 작은 기존 패턴 기반 변경이며 요구사항 해석이 하나임
- API Spec Gate가 필요하지 않고 Infrastructure Impact가 없음
- DB schema/data migration, dependency, security/authz, transaction/concurrency, architecture/common contract 결정이 없음
- cross-repository/의미 있는 multi-module 변경이 없음
- scope 판정을 위해 broad source 분석이 필요하지 않음
- bounded compile/targeted test로 검증 가능

애매하거나 위 조건 하나라도 벗어나면 Standard다. Direct도 Kanban Task를 생성하고 Coder→Reviewer를 반드시 거친다. Coder self-complete와 Reviewer 생략은 금지한다.

Direct는 current workspace/current branch 고정 경로다. 다른 workspace/새 branch 또는 기존 변경 처리의 별도 판단이 필요하면 Standard로 전환한다. Direct Task에는 `Flow: DIRECT`, `Review Policy: REQUIRED`, `Work Unit Boundary: SINGLE_UNIT`을 기록한다.

### Standard Flow
`Request → Project Approval → Breakdown → Work Unit/API/Workspace/Branch/Model/Plan Approval → Dispatch → Coder ↔ Reviewer`

신규 기능/설계, DESIGN/MIGRATION, multi-module/repository, API/Schema/Dependency/Infrastructure 변경, security/transaction/concurrency/architecture 결정, 모호한 요구사항은 Standard Flow다. Standard Work Unit 계약을 적용하며 독립 승인 artifact가 다음 mutation phase의 authoritative input이면 Task를 분리한다.

### 실행 Gate 불변식
- 실행 방식 승인과 Coder 모델 승인은 서로 다른 Gate다.
- Direct 후보라도 사용자가 `Standard Flow`를 선택하면 Standard 계약을 따른다.
- `수정해주세요`, `적용해주세요`, `바로 해주세요` 같은 일반 mutation 표현은 Direct 실행 승인 자체로 간주하지 않는다.
- 승인 전에는 source mutation, build/test, Kanban 생성으로 넘어가지 않는다.
- read-only 분석/설명/코드 리뷰 요청은 실행 Gate 대상이 아니다. 분석 중 수정 필요성이 생기면 mutation 전에 Orchestrator Flow Gate로 돌아간다.
- 실제 Kanban Task ID가 있는 Worker 세션은 Flow Gate를 다시 묻지 않고 할당 Task를 수행한다.
- 지원하는 mutation 실행 경로는 Direct Flow와 Standard Flow뿐이다.

## Kanban 계약
Direct/Standard Task 모두 Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Risks, Work Unit Contract, Workspace, Expected/Base Branch, Base SHA, Coder model snapshot, Reviewer DEFAULT를 보존한다. 구현 완료 후 Coder는 항상 Reviewer에게 인계한다.

이미 dispatch된 Task의 추가 요구사항은 Interactive Coder가 직접 반영하지 않는다. Orchestrator의 Requirement Delta/Work Unit 재평가 계약을 사용하고, 경계를 넘으면 새 Standard Flow로 분리한다.

## 사용자 가시 언어 정책
- 계획/진행 보고뿐 아니라 **Kanban Task 제목·본문, Requirement Delta, 대체/후속 작업 설명, Task comment, review/dispatch handoff의 자연어는 기본 한국어로 작성한다.**
- 사용자에게 보이는 자유 형식 섹션명을 `Task Key`, `Supersedes`, `Goal`, `Final ... Contract`, `Implementation Tasks`, `Test Plan`, `Known Risks`처럼 영어로 새로 만들지 않는다. 각각 `작업 키`, `대체 대상`, `목표`, `최종 ... 계약`, `구현 작업`, `테스트 계획`, `위험`처럼 한국어 제목을 사용한다.
- 예외는 자동화가 정확한 문자열로 파싱하는 고정 키(`Flow`, `Review Policy`, `Verification Mode`, `Coder Model Tier`, `Coder Model`, `Coder Provider`, `Reviewer Model`, `Model Escalation`, `Base SHA`, API/Data contract field), enum/status 값, 코드·클래스·메서드·API·SQL·경로·브랜치·명령어·모델명 등 기술 식별자다.
- 영어 Jira/문서/요구사항을 입력으로 받아도 의미를 보존해 한국어 계획으로 정규화한다. 정확한 원문 인용이 필요한 경우에만 영어 원문을 제한적으로 남긴다.

## JVM 언어 capability
- Java source 변경은 `dev-java-guidelines`, Kotlin source 변경은 `dev-kotlin-guidelines`를 적용한다.
- Java + Kotlin mixed project에서는 두 capability를 project 후보로 유지하되 실제 changed/affected source 언어에 맞춰 적용한다.
- Java 변경에서는 target Java와 기존 convention을 우선하고 Stable 기능만 기본 적용한다. Preview/Incubator 기능은 기존 프로젝트가 이미 명시적으로 사용 중인 경우 외에 신규 도입하지 않는다.
- Java Coder는 필요할 때 `skill_view("dev-java-guidelines")`로 record/sealed/pattern matching, Optional, collection ownership, Stream/parallelStream, exception, virtual thread 계약을 확인한다.
- Java Reviewer는 실제 Java diff 판단에 필요할 때 동일 `dev-java-guidelines`를 적용한다. 특히 unsupported/Preview/Incubator 문법, record의 JPA/framework compatibility, Optional field/parameter 남용 또는 Optional 자체 null, mutable collection/array 노출, Stream 내부 반복 I/O/N+1, 근거 없는 `parallelStream`, swallowed exception, CPU-bound 또는 runtime-context 검토 없는 virtual thread 도입을 확인한다.
- Java라는 이유만으로 Java/JDK/Gradle/Maven/Spring version을 자동 upgrade하지 않는다.
- Kotlin 변경에서는 프로젝트 Kotlin version/language level과 기존 convention이 우선이며, `Stable` 기능만 기본 허용한다. Beta/Experimental 신규 도입은 Task 근거 또는 사용자 승인 없이 하지 않는다.
- Kotlin Coder는 필요할 때 `skill_view("dev-kotlin-guidelines")`로 null-safety, data/value/sealed modeling, compiler plugin, annotation target, coroutine, KSP/kapt, Java interop 계약을 확인한다.
- Kotlin Reviewer는 실제 Kotlin diff 판단에 필요할 때 동일 `dev-kotlin-guidelines`를 적용한다. 특히 신규 `!!`, Entity `data class`, mutable collection 노출, platform type propagation, `GlobalScope`, blocking JPA/JDBC 위의 근거 없는 `suspend`/`Flow`, Experimental opt-in을 확인한다.
- Kotlin이라는 이유만으로 Kotlin/Spring/compiler plugin/KSP/Gradle version을 자동 upgrade하지 않는다.

## 공통 코드 품질
- 새 구현 전 기존 Utility/Service/Policy/Validator/Converter/Mapper/Domain/Data abstraction과 library를 검색해 재사용한다.
- Domain Logic은 프로젝트 architecture를 따르고 새 modeling style을 임의 도입하지 않는다.
- 함수/메서드 block은 기본 `2-depth`; 반복 DB/API/File/Network I/O와 N+1을 확인한다.
- Stack/Capability Skill은 기존 convention을 확장할 뿐 dependency/architecture/common contract를 임의 변경하지 않는다.
- Task의 Pattern References/Applicable Skills를 재사용해 같은 프로젝트를 역할마다 전체 재분석하지 않는다.

## Host / container path resolution
- Agent는 Linux 컨테이너에서 실행된다. Windows host 경로를 사용할 때는 **실제 Docker bind mount mapping을 최우선**으로 적용한다.
- Workspace 경로는 `HERMES_HOST_WORKSPACE_PATH` → `HERMES_CONTAINER_WORKSPACE_PATH` mapping이 canonical이다. 예: `D:/workspace/product/oc/oc-dml` → `/workspace/product/oc/oc-dml`.
- `D:\workspace\...`처럼 backslash를 사용한 동일 경로도 위 workspace mapping을 적용한다.
- `/mnt/<drive>/...`는 모든 Windows 경로의 일반 변환 규칙이 아니다. Workspace host root를 기계적으로 `/mnt/<drive>/...`로 바꾼 값이 들어와도 실제 workspace bind mount와 일치하면 `/workspace/...`로 다시 canonicalize한다.
- Workspace mapping에 속하지 않는 Windows 경로는 임의로 `/mnt/<drive>/...`로 추측하지 않는다. 실제 mount 또는 tool이 제공한 경로를 확인한다.

## Host temporary path resolution
- `/mnt/<drive>/...` 규칙은 Windows host의 `%LOCALAPPDATA%\Temp` 입력 파일 접근을 위한 **별도 Temp mount 규칙**이다. Workspace repository 경로에 적용하지 않는다.
- Windows host의 `%LOCALAPPDATA%\Temp`는 `update-devkit.ps1`가 `LOCALAPPDATA`를 기준으로 계산한 동일한 `/mnt/<drive>/Users/<profile>/AppData/Local/Temp` 경로에 read-only로 mount한다.
- 사용자명이나 프로필 디렉터리명을 하드코딩하지 않는다. `LOCALAPPDATA`의 실제 drive/profile 경로가 canonical 값이다.
- Temp 입력 파일을 읽기 전에 존재 여부를 확인한다. 존재하지 않으면 임의 경로를 추측하지 말고 사용자에게 파일 접근 실패를 명확히 알린다.
- host Temp mount는 입력 파일 확인용 read-only 영역이다. 파일 생성·수정·삭제 대상이나 작업 산출물 저장 위치로 사용하지 않는다.

## Scope / safety / verification
- 요구사항에 직접 필요한 최소 diff만 만들고 unrelated refactor/format/upgrade를 섞지 않는다.
- 관련 있을 때 null/failure/compatibility/transaction/concurrency/security를 위험 기반으로 확인한다.
- secret, credential, token, password, raw PII를 source/context/Kanban/log에 기록하지 않는다.
- 사용자 변경을 reset/restore/clean/stash/commit하거나 덮어쓰지 않는다. publication 요청 전 commit, push, PR, merge 금지.
- Coder worker의 workspace/branch/base 검증은 `dev-implement-plan/scripts/verify_workspace.py`를 **단독 command로 1회** 실행한다. `STATUS=valid`이면 같은 terminal invocation의 추가 Git/toolchain probe나 별도 중복 workspace probe를 금지한다.
- Hermes container 내부의 모든 Gradle 실행은 raw `./gradlew ...` 또는 `gradle ...`을 직접 호출하지 않는다. 단순 bounded 진단은 `hermes-java ./gradlew ...`, COMPILE/TARGETED_TEST 검증은 `dev-implement-plan/scripts/gradle_verification_cached.py`를 canonical 경로로 사용한다.
- canonical helper가 `hermes-java`를 통해 `/opt/data/gradle`의 project cache/build output/workspace lock 격리를 적용하도록 유지한다. `GRADLE_STATUS=BLOCKED`이면 timed-out primary command, `compileJava`, `--info` 변형, background wait를 임의 반복하거나 raw Gradle로 우회하지 않고 helper blocker evidence로 종료한다.
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