<!-- HERMES-COMMON:START -->

# Hermes Lite — 직접 개발 공통 규칙

> 이 브랜치는 Devkit의 직접 개발 실험이다. Standard Flow는 **자동 실행하지 않는다.** 기존 Kanban 데이터·메모리·프로필·인증 정보는 보존한다.

## 상호작용 및 권한

- 사용자는 **현재 Hermes CLI의 default 프로필과 직접 대화**하면서 코드 분석, 구현, 테스트, 재수정, 최종 검토를 진행한다. 모든 mutation을 Orchestrator로 먼저 이관하거나 Coder/Reviewer worker를 자동 dispatch하지 않는다.
- 기존 Standard Flow 전용 \`dev-project-bootstrap\`, \`dev-breakdown\`, \`dev-workspace-dispatch\`, \`dev-implement-plan\`, \`dev-code-review\`, \`dev-review-cycle\`, \`dev-flow-model-policy\`, \`dev-task-recovery\`는 Lite 구현의 선행 계약이 아니다. **독립 실행/worker 소유권/승인 snapshot**을 현재 대화에 강제하지 않는다.
- 사용자가 기존 Standard 작업을 조회할 수는 있으나 실행 중인 Kanban 카드의 claim/status/assignee를 임의 변경하거나 worker를 되살리지 않는다.
- 사용자가 확인해야 하는 민감한 변경(인증·권한, 마이그레이션, 대량 삭제, 대규모 범위 변경)은 변경 영향/복구 방법을 먼저 설명하고 명시적 승인을 확인한다.
- 작업 범위가 명확한 일반 코드 수정은 현재 컨텍스트 안에서 직접 진행한다. 중간 지시나 반복 수정 요청은 같은 대화에서 우선 반영한다.

## Kanban = 선택적 기억, 실행 Gate 아님

- 새 개발 요청은 기본적으로 **Kanban 카드 없이** 처리한다. 작업 시작/완료를 위해 카드 생성·승인·dispatch·독립 reviewer 호출을 요구하지 않는다.
- 사용자가 “기억해 둬”, “남은 작업을 카드로”, “기존 카드 업데이트” 등을 요청할 때만 Kanban에 **목표·현재 상태·결정·미완료·다음 행동·검증 결과**를 간단히 기록한다.
- 기존 카드의 기록을 읽고 참고하는 것은 가능하다. Standard worker의 \`running\` 카드에 Lite가 새로운 owner로 개입하거나 \`done\`/unblock 전환을 자동 수행하지 않는다.
- 카드 조회/기록 실패가 코드 수정·테스트를 막지 않는다. 단, **사용자가 카드 기록 자체를 요청한 경우**에는 기록 실패를 명확하게 알린다.
- 오래 이어질 중요한 미완료 작업이라면 기록을 *제안*할 수 있지만, 사용자 동의 없이 모든 개발 요청에 자동 카드를 생성하지 않는다.
- 알림 서비스는 기존 설정대로 존치하고, 임의로 과거 이벤트를 다시 송신하거나 카드 상태를 변경하지 않는다.

## 스킬 적용 기준

- 공통 개발 스킬은 \`/opt/custom-skills/shared\`, Lite 전용 스킬은 \`/opt/custom-skills/lite\`에서 로드한다. 스킬 전체 본문을 항상 로딩하지 않고 실제 작업에 필요한 것을 선택한다.
- Java: \`dev-java-guidelines\`, Spring: \`dev-spring-guidelines\` / \`dev-spring-test\`, Kotlin: \`dev-kotlin-guidelines\`, TypeScript·Frontend: 해당 shared capability, DB: 해당 query/schema/performance capability를 활용한다.
- 공식 문서 확인이 필요한 경우 \`dev-official-docs-context\`; 구현 결과 검증을 원할 때 \`dev-lite-review\`를 선택적으로 사용한다. Lite의 자체 리뷰는 **독립 Reviewer 검증과 같다고 주장하지 않는다.**
- 프로젝트의 기존 패턴, 런타임/JDK/라이브러리 버전을 최우선으로 따르며 단순히 최신이라는 이유로 의존성을 업그레이드하지 않는다.
- 코드 작성 전에 기존 구현/유틸리티를 확인하고, 가장 작은 변경으로 요구사항을 충족한다.
- 필요한 테스트를 실제로 실행하고 명령/성공·실패·미실행 이유를 요약한다. 별도 Review 에이전트를 호출할 필요는 없다.

## 개발 환경 / 경로

- Windows workspace: \`HERMES_HOST_WORKSPACE_PATH\` ↔ \`HERMES_CONTAINER_WORKSPACE_PATH\`가 authoritative bind다. Windows 경로를 임의의 \`/mnt/<drive>\`로 변환하지 않는다.
- \`%LOCALAPPDATA%\Temp\`용 별도 읽기 전용 bind만 해당하는 \`/mnt/<drive>/...\` 경로를 사용하며 직접 파일을 쓰지 않는다.
- Maven/Gradle/Node 빌드·캐시는 기존 Devkit launcher/공통 runtime 계약을 유지한다. 필요 시 \`shared/references/maven-worker-runtime.md\` 및 관련 capability/헬퍼를 확인한다. 성능 최적화 때문에 실제 테스트 성공 여부를 생략하지 않는다.
- 외부 Workspace·Git 파일·데이터 볼륨은 명시적 요청 없는 정리/reset/stash/강제 덮어쓰기를 하지 않는다.

## 소통 / 안전

- 사용자 보고와 계획·검증 결과는 한국어를 기본으로 하고, 코드 내부 운영 로그는 영어로 작성한다.
- secret/credential/token/password/PII는 소스·Kanban·로그에 남기지 않는다.
- 사용자 파일과 미커밋 변경을 우선 보존한다. 코드 커밋·푸시·PR·병합은 사용자 요청이 있을 때에만 수행한다.
- 테스트 실패 또는 실행 불가능 상황은 실패 원인과 잔여 위험을 구분하여 기록한다.

<!-- HERMES-COMMON:END -->
