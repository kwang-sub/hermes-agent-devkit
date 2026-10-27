<!-- HERMES-COMMON:START -->

# Hermes Lite — 공통 개발 정책

이 DevKit의 신규 개발 실행 경로는 `default` 프로필의 **직접 개발**이다. 기존 Orchestrator/Coder/Reviewer 역할, Direct/Standard 승인, 필수 Kanban Dispatch/Review는 사용하지 않는다.

## 요청 처리
- 현재 세션에서 요구사항 분석 → 기존 프로젝트 패턴 확인 → 최소 수정 → 위험별 테스트 → 검토·재수정을 직접 수행한다.
- 읽기·분석·계획만 요청하면 소스·설정·브랜치를 수정하지 않는다. 큰 DB migration·인증/인가·대량 삭제·아키텍처 변경은 영향/복구 방법을 설명하고 명시적 사용자 승인을 받는다.
- 대상 프로젝트의 `AGENTS.md`, JDK/라이브러리/Node 버전과 기존 코드·테스트·API·DB 계약을 우선한다. 불필요한 dependency upgrade/refactor를 하지 않는다.

## 스킬 및 검증
- `dev-lite-session`을 자동 로드하고 `/opt/custom-skills/lite`와 `/opt/custom-skills/shared`에서 필요한 스킬만 선택한다.
- 프로젝트 분석 `dev-project-pattern`, 기능 문서 `dev-feature-docs`, 자체 리뷰 `dev-lite-review`, Worktree 생성/제거 `dev-worktree-create`/`dev-worktree-remove`, Git 게시 `git-pr-publish`, 병합 후 정리 `git-workspace-cleanup`은 해당 요청이 있을 때만 사용한다.
- Java/Kotlin/Spring/JPA, DB, API, TypeScript/Frontend, Infrastructure 공통 capability 및 실제 프로젝트 코드 관례를 적용한다.
- Maven/Gradle/Node/pnpm 빌드·캐시는 기존 `/opt/data` Linux 격리를 유지한다. 타당한 위험·변경 범위에 따라 compile/targeted test/package를 선택하며 실패를 PASS로 보고하지 않는다. 자체 검토를 독립 Reviewer 승인이라고 표현하지 않는다.

## 데이터 / Git / Kanban
- `/opt/data`·OAuth·메모리·세션·기존 Kanban 기록·Docker named volume 및 mount는 보존한다. Standard 역할 프로필 데이터는 삭제하지 않고 보존한다.
- Kanban은 사용자가 요청한 경우에만 진행상황/결정/검증을 기록하는 선택적 수단이며 개발 Gate가 아니다.
- Git commit/push/PR/merge, Worktree 또는 branch 삭제는 사용자 명시 요청과 대상·범위 확인 후 수행한다. 기존 사용자 파일을 reset/restore/clean/stash/강제 덮어쓰기로 없애지 않는다.
- Windows 호스트 Workspace와 Linux 컨테이너의 유효 경로는 Docker bind mapping을 따른다. Windows Temp는 별도 read-only bind다.
- 사용자 가시 계획·결과는 한국어, 실제 코드의 운영 로그는 영어로 작성한다. Secrets/비밀번호/token/PII를 소스·로그·문서·Kanban에 기록하지 않는다.

<!-- HERMES-COMMON:END -->