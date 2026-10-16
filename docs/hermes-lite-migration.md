# Hermes Lite 마이그레이션 (실험 브랜치)

> 범위: Hermes CLI에서 직접 개발하면서 기존 데이터, Windows Workspace/외부 bind, 개발 툴체인과 개발 스킬을 재사용한다. Standard Flow는 **삭제하지 않고 미사용**한다.

## 현재 Devkit 구조에서 확인된 사실

- 호스트 공식 업데이트 스크립트는 \`update-devkit.ps1\`이며, 기본 운영 브랜치는 \`dev\`다. \`updatekit.sh\`라는 기존 진입점은 없다.
- \`compose.yml\`은 기본 \`hermes-dev\` 컨테이너와 **\`hermes-dev-data\` named volume**을 \`/opt/data\`에 붙인다. \`D:/workspace\` → \`/workspace\`, \`custom-skills\` → \`/opt/custom-skills\`, \`shared\` → \`/opt/data/shared\` bind도 제공한다.
- \`shared/AGENTS.common.md\`과 루트 \`AGENTS.md\`는 Coder의 Kanban task 선행·Orchestrator/Reviewer 강제 규칙을 포함한다. Lite는 이 지침을 변경해야 **실제로** 직접 개발할 수 있다.
- Standard Coder·Reviewer 스킬 중 \`dev-implement-plan\`, \`dev-code-review\`와 관련 handoff/worker gate는 독립 실행에 적합하지 않다. \`custom-skills/shared\`의 언어·프레임워크·검증 capability는 재사용 가능하다.
- \`init-profiles.ps1\`는 Standard 전용 세 프로필을 초기화한다. **Lite에서 재실행하지 않는다.** default 프로필의 기존 인증·메모리·세션을 재사용한다.
- Devkit Dockerfile에는 Kanban 보조 패치/알림 서비스가 이미 포함되어 있다. 첫 실험에서는 원격 이미지나 Dockerfile을 변경하지 않는다. 런타임 가벼움은 다단계 위임·정책 로딩을 줄여 먼저 평가한다.

## 전환 범위와 보존 경계

| 대상 | Lite 정책 | 확인 |
|---|---|---|
| 코드 | 현재 개발 프로젝트 Git/Workspace는 건드리지 않음 | branch switch는 **Devkit 저장소에만** |
| Hermes 기본 프로필 | 모델·OAuth·메모리·세션은 그대로 유지 | \`/opt/data\` |
| Kanban | DB/보드/카드는 보존, 필요한 내용만 수동 기록 | \`/opt/data/kanban*\` |
| Standard 역할 프로필 | 유지하되 Lite에서 호출하지 않음 | \`/opt/data/profiles/*\` |
| Lite 전용 프로필 조정 | default \`config.yaml\`의 최소 skill/toolset 목록만 비파괴적 추가 | 선행 백업 및 복원 |
| 스킬 | \`custom-skills/shared\` 재사용, Lite용 검토 스킬 추가 | read-only bind |
| 빌드 도구 | JDK 8/17/21, Maven·Gradle·Node/pnpm, 캐시 경로 유지 | 기존 image/volume |
| 외부 마운트 | compose가 정의한 경로 그대로 유지 | docker inspect |
| 알림 | 기존 Kanban 알림 구성값 유지, 자동 생성/위임은 하지 않음 | 기존 옵션 유지 |

### 두 가지 별도 개념

**Git branch**는 Devkit 스크립트/지침 소스를 선택한다. **Hermes default 프로필**은 영속 메모리/인증/세션의 소유자다. Git branch 교체는 named volume 내용을 복제·초기화하지 않는다.

**실행 정책**에서 Lite는 Kanban 카드 없는 작업을 허용한다. Kanban은 사용자가 기록을 요청하거나 기존 카드를 참조할 때만 사용한다. 기존 Standard에서 실행 중인 worker는 자동으로 Lite 작업으로 이전하지 않는다.

## 최소 실행 절차

1. Devkit checkout이 깨끗한지 확인한다. 실제 작업 중인 Standard worker가 있으면 완료/일시 정지시킨다.
2. 최초 1회 \`git fetch origin && git switch --track -c experiment/hermes-lite origin/experiment/hermes-lite\`로 Lite 브랜치를 checkout한다.
3. Windows PowerShell에서 \`.\updatekit_lite.ps1\`를 실행한다. Git Bash/WSL에서는 \`./updatekit_lite.sh\`를 실행한다.
4. 기존 \`hermes-dev\` 실행 중이면 이미지 빌드/컨테이너 재생성 없이 같은 volume과 mount를 검증하고 Lite 설정을 적용한다.
5. 초기 컨테이너가 없다면 **명시적으로** 기존 \`update-devkit.ps1 -Branch experiment/hermes-lite\`로 부트스트랩한 후 Lite를 적용한다. 부트스트랩은 기존 이미지/역할 구성도 설치하므로 느릴 수 있다.
6. \`docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes\`로 default 프로필에서 직접 작업한다. 모델은 현재 default 프로필 설정을 따르며 필요하면 \`/model\`로 선택한다.
7. Standard로 복귀할 때는 **Lite 브랜치에서 먼저** \`.\updatekit_lite.ps1 -Mode standard\`를 실행한다. 이 명령은 Lite가 추가한 프로필 설정만 복원한 다음 \`dev\`로 전환한다. 마지막으로 기존 \`.\update-devkit.ps1\`로 Standard 구성 재정합(이미지 재빌드 포함)을 할 수 있다.

> 초기 적용은 Windows PowerShell 권장. Bash 래퍼는 Windows PowerShell을 호출한다. 기존 \`update-devkit.ps1\`의 전체 자동 재빌드·재생성 정책을 Lite의 매 전환에 사용하지 않는다.

## 주의해야 할 실패 경로

- 시작 전에 dirty Devkit worktree, 잘못된 Docker named volume, 대상 branch 부재, running Kanban task가 발견되면 **fail-closed**한다.
- \`/opt/data\` 전체 삭제, volume 교체, \`docker compose down -v\`, \`git reset/clean/stash\`, 기존 Kanban 카드 상태 갱신은 금지한다.
- 기존 데이터 폴더와 프로젝트 소스 디렉터리는 수정을 대상으로 삼지 않는다. profile 편집은 **default config.yaml 내 skills.external_dirs/toolsets 항목으로 한정**한다.
- Lite 실행 중 사용자가 profile 목록을 직접 바꿨다면 복귀 시 덮어쓰지 않고 충돌을 표시한다. 백업은 \`/opt/data/devkit-lite/\`에 남긴다.
- 기존 컨테이너가 자동으로 새로운 AGENTS를 재로딩한다고 가정하지 않는다. **새 CLI 대화 세션**을 시작해 Lite 정책 적용을 확인한다.
- 로컬 PC의 Docker/container 세션은 이 브랜치 변경만으로 실행되지 않는다. 실제 마운트·OAuth 상태·모델 동작은 사용자의 Docker 환경에서 별도 smoke 테스트한다.

## 커밋/승격 경계

1. 이관 조사 및 경계 명세
2. Lite 개발 지침 전환 (Standard 실행 규칙 격리)
3. Lite 프로필 구성 및 updatekit 스크립트
4. Coder/Reviewer capability 재사용
5. 선택적 Kanban 및 복귀 정책
6. 자동 정적 계약 테스트/문서/CI

실사용 후 동일 난이도의 작업을 Codex CLI, Hermes Lite, 기존 Standard와 비교한다. 완료 시간, 개입 용이성, 품질, 재개 가능성, Kanban/데이터 보존을 확인한 뒤에만 Lite 표준 승격/Standard 제거를 결정한다.
