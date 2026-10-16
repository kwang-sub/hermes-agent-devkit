# Hermes Lite 마이그레이션 (dev에서 병행 운영)

> 범위: Hermes CLI에서 직접 개발하면서 기존 데이터, Windows Workspace/외부 bind, 개발 툴체인과 개발 스킬을 재사용한다. Standard Flow는 **삭제하지 않고 미사용**한다.

## 현재 Devkit 구조에서 확인된 사실

- 호스트 공식 업데이트 스크립트는 `update-devkit.ps1`이며, 기본 운영 브랜치는 `dev`다. `updatekit.sh`라는 기존 진입점은 없다.
- `compose.yml`은 기본 `hermes-dev` 컨테이너와 **`hermes-dev-data` named volume**을 `/opt/data`에 붙인다. `D:/workspace` → `/workspace`, `custom-skills` → `/opt/custom-skills`, `shared` → `/opt/data/shared` bind도 제공한다.
- `shared/AGENTS.common.md`과 루트 `AGENTS.md`는 Coder의 Kanban task 선행·Orchestrator/Reviewer 강제 규칙을 포함한다. 두 파일은 Standard 계약을 유지하고, Lite는 별도 `lite/AGENTS.md` 및 `dev-lite-session` 자동 로딩 스킬로 실행 정책을 분리한다.
- Standard Coder·Reviewer 스킬 중 `dev-implement-plan`, `dev-code-review`와 관련 handoff/worker gate는 독립 실행에 적합하지 않다. `custom-skills/shared`의 언어·프레임워크·검증 capability는 재사용 가능하다.
- `init-profiles.ps1`는 Standard 전용 세 프로필을 초기화한다. **Lite에서 재실행하지 않는다.** default 프로필의 기존 인증·메모리·세션을 재사용한다.
- Devkit Dockerfile에는 Kanban 보조 패치/알림 서비스가 이미 포함되어 있다. 첫 실험에서는 원격 이미지나 Dockerfile을 변경하지 않는다. 런타임 가벼움은 다단계 위임·정책 로딩을 줄여 먼저 평가한다.

## 전환 범위와 보존 경계

| 대상 | Lite 정책 | 확인 |
|---|---|---|
| 코드 | 현재 개발 프로젝트 Git/Workspace는 건드리지 않음 | Lite/Standard는 같은 Devkit `dev` 브랜치에서 전환 |
| Hermes 기본 프로필 | 모델·OAuth·메모리·세션은 그대로 유지 | `/opt/data` |
| Kanban | DB/보드/카드는 보존, 필요한 내용만 수동 기록 | `/opt/data/kanban*` |
| Standard 역할 프로필 | 유지하되 Lite에서 호출하지 않음 | `/opt/data/profiles/*` |
| Lite 전용 프로필 조정 | default `config.yaml`의 skill/toolset/auto_load 목록만 비파괴적으로 조정 (기존 사용자 스킬·설정은 복원) | 선행 백업 및 복원 |
| 스킬 | `custom-skills/shared` 재사용, Lite용 검토 스킬 추가 | read-only bind |
| 빌드 도구 | JDK 8/17/21, Maven·Gradle·Node/pnpm, 캐시 경로 유지 | 기존 image/volume |
| 외부 마운트 | compose가 정의한 경로 그대로 유지 | docker inspect |
| 알림 | 기존 Kanban 알림 구성값 유지, 자동 생성/위임은 하지 않음 | 기존 옵션 유지 |

### 두 가지 별도 개념

**Git branch**는 Devkit 소스 버전을 관리한다. PR #188이 `dev`에 병합되었으므로 **Lite/Standard 모드 전환에 Git branch 교체는 필요 없다.** **Hermes default 프로필**은 영속 메모리/인증/세션의 소유자이며, 모드 전환 시 필요한 프로필 설정만 바꾼다.

**실행 정책**에서 Lite는 Kanban 카드 없는 작업을 허용한다. Kanban은 사용자가 기록을 요청하거나 기존 카드를 참조할 때만 사용한다. 기존 Standard에서 실행 중인 worker는 자동으로 Lite 작업으로 이전하지 않는다.

## 최소 실행 절차

1. Devkit checkout이 깨끗한지 확인한다. 실제 작업 중인 Standard worker가 있으면 완료·안전 중단시킨다.
2. `git switch dev && git pull --ff-only origin dev`로 **병합된** Lite 스크립트를 가져온다. 삭제된 `experiment/hermes-lite` 원격 브랜치를 checkout하지 않는다.
3. Windows PowerShell에서 `.\updatekit_lite.ps1`를 실행한다. Git Bash/WSL에서는 `./updatekit_lite.sh`를 실행한다. `.\updatekit_lite.ps1 -SelfTest`로 Git 실행 인수 전달을 Docker 없이 사전 확인할 수 있다.
4. 기존 `hermes-dev`가 실행 중이면 이미지 빌드/컨테이너 재생성 없이 기존 volume과 mount를 검증하고 Lite 프로필 설정을 적용한다.
5. 컨테이너가 없다면 기존 `.\update-devkit.ps1 -Branch dev`로 최초 부트스트랩한 후 Lite 스크립트를 실행한다.
6. `docker exec -it --user hermes --workdir /workspace/hermes-agent-devkit/lite hermes-dev /opt/hermes/.venv/bin/hermes -p default`로 default 프로필에서 직접 작업한다. 필요 시 `/model`로 모델을 선택한다.
7. Standard 복귀는 **같은 `dev` 브랜치에서** `.\updatekit_lite.ps1 -Mode standard`로 수행한다. 기존 세션·Kanban은 유지하며, 전체 이미지/Standard 프로필 재정합이 필요한 경우에만 `.\update-devkit.ps1`를 별도 실행한다. 과거 로컬 Lite 브랜치가 남아 있다면 복원 후 `dev`로 이동할 수 있다.

> 초기 적용은 Windows PowerShell 권장. Bash 래퍼는 Windows PowerShell을 호출한다. 기존 `update-devkit.ps1`의 전체 자동 재빌드·재생성 정책을 Lite의 매 전환에 사용하지 않는다.


> Lite 세션은 개발 대상 프로젝트에서 `AGENTS.md`를 찾더라도 auto-load된 `dev-lite-session`으로 직접 협업 기준을 유지합니다. Devkit 자체를 수정할 때는 별도 `lite/AGENTS.md`가 있는 경로에서 시작하여 Standard의 루트 `AGENTS.md`와 충돌하지 않도록 합니다. Standard 모드로 복귀하면 Lite의 auto-load 목록 변경을 복원합니다.

## 주의해야 할 실패 경로

- 시작 전에 dirty Devkit worktree, 잘못된 Docker named volume, 지원하지 않는 branch, running Kanban task가 발견되면 **fail-closed**한다.
- `/opt/data` 전체 삭제, volume 교체, `docker compose down -v`, `git reset/clean/stash`, 기존 Kanban 카드 상태 갱신은 금지한다.
- 기존 데이터 폴더와 프로젝트 소스 디렉터리는 수정을 대상으로 삼지 않는다. profile 편집은 **default config.yaml 내 skills.external_dirs, skills.auto_load, toolsets 항목으로 한정**한다.
- Lite 실행 중 사용자가 profile 스킬·toolset·autoload 목록을 직접 바꿨다면 복귀 시 덮어쓰지 않고 충돌을 표시한다. 백업은 `/opt/data/devkit-lite/`에 남긴다.
- 기존 컨테이너가 자동으로 새로운 AGENTS를 재로딩한다고 가정하지 않는다. **새 CLI 대화 세션**을 시작해 Lite 정책 적용을 확인한다.
- 로컬 PC의 Docker/container 세션은 이 브랜치 변경만으로 실행되지 않는다. 실제 마운트·OAuth 상태·모델 동작은 사용자의 Docker 환경에서 별도 smoke 테스트한다.

## 커밋/승격 경계

1. 이관 조사 및 경계 명세 (원래 실험 브랜치에서 수행, PR #188로 dev 병합 완료)
2. Lite 개발 지침 전환 (Standard 실행 규칙 격리)
3. Lite 프로필 구성 및 updatekit 스크립트
4. Coder/Reviewer capability 재사용
5. 선택적 Kanban 및 복귀 정책
6. 자동 정적 계약 테스트/문서/CI

실사용 후 동일 난이도의 작업을 Codex CLI, Hermes Lite, 기존 Standard와 비교한다. 완료 시간, 개입 용이성, 품질, 재개 가능성, Kanban/데이터 보존을 확인한 뒤에만 Lite 표준 승격/Standard 제거를 결정한다.
