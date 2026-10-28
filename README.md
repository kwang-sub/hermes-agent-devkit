# Hermes Agent DevKit — Lite

Windows 11 + Docker Desktop에서 Hermes **default 프로필의 직접 개발**을 사용하는 환경이다. 사용자가 현재 세션에서 분석·구현·테스트·수정을 요청한다. DevKit의 Orchestrator/Coder/Reviewer 역할, Direct/Standard 분류·승인·자동 위임은 제거했다. Hermes 자체의 일반 프로필 기능을 제거하거나 사용자 정의 프로필을 일괄 삭제하지는 않는다.

```text
사용자 ↔ default Hermes 세션
           ├─ 기존 프로젝트 규칙 + 필요한 개발 스킬
           ├─ 구현 → 위험 기반 테스트 → 자체 검토 → 반복 수정
           ├─ Worktree / Git 게시 (요청 시)
           └─ Kanban 기록 (요청 시, 실행 Gate 아님)
```

## 유지되는 기능

Java/Kotlin/Spring/JPA, TypeScript/React/Next.js, API·DBML·DB migration·SQL·성능·Infrastructure·Figma/화면 검증을 필요한 때에만 로드한다. 기존 프로젝트 패턴·버전·의존성·테스트 프레임워크를 우선한다. 모든 작업에 UI 검증이나 package build를 강제하지 않는다.

JDK 8/17/21, Git 상대 Worktree, Maven·Gradle·Node/pnpm의 Linux 내부 캐시/산출물 격리, 실행 timeout·자식 프로세스 종료·유효한 PASS 증거 재사용, 영어 코드 로그·Secret 보호 규칙을 유지한다. 자체 검토는 독립 Reviewer 승인과 다르다.

| 요청 | 스킬 |
|---|---|
| 분리된 작업 공간 생성 / 제거 | `dev-worktree-create` / `dev-worktree-remove` |
| Git 커밋·푸시·PR 게시 | `git-pr-publish` |
| 병합 후 Worktree·브랜치 정리 | `git-workspace-cleanup` |
| 기능 논의·문서화·진행 상태 확인 | `dev-feature-docs` |
| 프로젝트 구조·패턴 분석 | `dev-project-pattern` |
| 선택적 프로젝트 툴체인·설정 보안 준비 | `dev-project-setup` |
| Jira 요구사항 읽기 | `dev-work-intake` |
| 변경사항 자체 리뷰 | `dev-lite-review` |

`dev-lite-session`만 기본 자동 로드한다. 스킬 전체 본문을 매번 로드하지 않는다. 별도 Managed Project 등록, Board 생성, 모델 등급 선택, Worker 소유권 검사는 없다.

## 변경 작업 전 계획과 스킬 확인

논의·설계 비교·원인 분석에서는 기존처럼 자유롭게 대화한다. 실제 코드·문서·설정 등을 변경할 시점에만 `dev-lite-session`이 **`# 구현 계획` → `# 사용 스킬`**을 한 번 보여주고 사용자 승인을 기다린다. 스킬은 본문을 실제 읽은 근거가 있을 때만 확인 완료로 표시한다.

승인은 기본 Hermes CLI의 선택 화면으로 받는다: **작업 진행 / 작업 보류 / 추가 요구사항**. 3번을 선택하면 즉시 입력 모드로 바뀌며, 추가 입력은 승인이 아니라 계획 수정 요청이다. 취소·빈 입력·미지원 UI는 자동 승인하지 않는다.

이미 공개한 동일 계획을 승인했다면 다시 묻지 않고 구현·테스트·동일 범위의 수정을 이어간다. 범위나 위험이 실질적으로 커질 때만 변경분을 재승인받는다. 별도 Kanban/Worker/Reviewer나 승인 저장소는 추가하지 않는다. 이 규칙은 에이전트 동작 정책이며 파일 쓰기 도구를 차단하는 런타임 잠금은 아니다.

최신 코드 적용 후에는 새 Hermes 세션에서 자동 로드된 정책을 확인한다. 열려 있던 세션이 이미 읽은 스킬 내용은 자동 갱신됐다고 가정하지 않는다. 대화 예시와 수동 검증 기준은 `docs/lite-session-approval.md`를 참고한다.

## 설치

Docker Desktop, Git, Windows PowerShell 5.1 이상이 필요하다. 저장소의 운영 브랜치는 `dev`다. 아직 병합되지 않은 변경은 일반 `dev` 업데이트에 적용되지 않는다.

```powershell
git clone https://github.com/kwang-sub/hermes-agent-devkit.git
cd hermes-agent-devkit
git switch dev
if (Test-Path .env) { throw '.env exists; preserve it and edit explicitly.' }
Copy-Item sample.env .env
notepad .env
```

Dashboard 인증 값, 호스트 Workspace, Git 작성자 이름·이메일 등을 `.env`에 지정한다. API 키·OAuth·실제 `.env`는 저장소에 커밋하지 않는다. 기존 `.env`를 sample로 덮어쓰지 않는다.

```powershell
.\update-devkit.ps1
```

신규 데이터 볼륨도 이미지의 서비스 시작 전 초기화가 default 설정과 스킬을 구성한다. `init-profiles.ps1`는 필요하지 않으며 제공하지 않는다. 모델·OAuth는 default에서 사용자 본인이 설정한다.

```powershell
docker exec -it --user hermes --workdir /workspace/hermes-agent-devkit hermes-dev /opt/hermes/.venv/bin/hermes -p default model
docker exec -it --user hermes --workdir /workspace/hermes-agent-devkit hermes-dev /opt/hermes/.venv/bin/hermes -p default
```

다른 프로젝트 작업은 실제 bind 경로에 대응하는 `--workdir`를 사용한다. `/workspace`와 `hermes-dev`는 기본값이며 환경설정이 다르면 맞게 지정한다. Lite 폴더에서 대화를 시작할 필요는 없다.

## 업데이트와 기존 Standard 환경 전환

업데이트 전에 진행 중인 CLI·빌드·개발 작업을 안전하게 끝낸다. 업데이트는 컨테이너 재시작을 포함한다. 실행 중인 Kanban `running/review` 기록이 있으면 첫 전환을 차단하며 카드나 claim을 자동 변경하지 않는다. 죽은 Worker로 의심되는 과거 카드도 임의 완료 처리하지 않는다.

```powershell
.\update-devkit.ps1
# 운영 브랜치 외에서 승인한 개발 버전을 검증할 때만:
# .\update-devkit.ps1 -Branch <현재-브랜치> -NoPull
```

순서:

```text
깨끗한 DevKit checkout 확인 → Git fast-forward
→ 실제 Docker mount 확인·보존 override 생성
→ 기존 데이터를 readonly로 마이그레이션 계획 검증
→ 최신 Hermes 이미지 build --pull (한 번)
→ 재검증 → 기존 컨테이너 정상 정지 → 정지 상태 재검증
→ 같은 mounts로 컨테이너 재생성
→ 서비스 시작 전 default 전환·역할 프로필 보관
→ mount 동일성·default·live Gateway·툴체인·Git 검증
```

기존 `/opt/data`가 named volume이든 영속 host bind든 그대로 사용한다. 외부 bind, 읽기 전용 여부, 사용자 정의 volume 이름도 보존한다. 알 수 없는 mount 유형, subpath, 중복 대상이나 Compose와 기존 Workspace의 불일치는 자동 변환하지 않고 중단한다. 실제 `/opt/data`를 새 빈 볼륨으로 교체하지 않는다.

빌드 실패 시 기존 컨테이너를 교체하지 않는다. 전환/부팅 오류가 발생한 뒤 반복 재생성으로 덮지 않는다. 정지 이후 재검증에서 동시 작업을 발견하면 기존 컨테이너는 정지 상태로 보존되며 원인을 확인해야 한다. `-SkipVerify`도 mount/default 안전 검사는 생략하지 못한다. `-SkipProfileInit`은 폐기되어 오류로 종료한다. `-NoRepair`는 호환 인수이며 자동 repair는 사용하지 않는다.

루트에서 실행할 PowerShell 스크립트는 `update-devkit.ps1` 하나만 제공한다. 과거 `updatekit_lite.ps1` / `updatekit_lite.sh` 호환 진입점은 제거했다. Git 모드 전환이나 Standard 재생성 경로는 없다.

기존 이미지가 새 빌드 후 Docker 로컬 이미지 저장소에서 사라져도 정상 이관 검사를 계속할 수 있도록, 빌드 전에는 사용 가능한 로컬 이미지를 사용하고 빌드 후·정지 후에는 **새로 빌드한 이미지 ID**로 고정해 사전 검사를 수행한다. 빌드 전 사용 가능한 이미지가 없을 때에는 빌드 후 검사를 필수로 수행하며, 기존 컨테이너는 사전 검사 성공 전에 정지하지 않는다.

### 마운트 진단 이력

업데이터는 `%LOCALAPPDATA%\HermesAgentDevKit\update-history\<UTC 시각>-<GUID>\`에 실행별 `before.json`과 `after.json`을 기록하고 실제 저장 경로를 출력한다. `before.json`은 빌드 전에, `after.json`은 재생성 후 컨테이너를 조회했을 때 기록한다. 빌드나 사전 검사에서 중단되면 `before.json`만 남을 수 있다. 성공·실패 후에도 이력을 자동 삭제하거나 다음 실행으로 덮어쓰지 않는다.

기록에는 마운트 필드, 기존 비교 함수의 서명, 컨테이너·이미지 ID와 UTC 시각만 포함한다. `after.json`의 `comparison`에는 대소문자를 구분한 일치 여부와 `before_only` / `after_only` 차이가 들어가며 불일치 행은 콘솔에도 표시한다. 전체 inspect, 환경변수, 인증 값, Compose 설정은 저장하지 않는다. 마운트의 호스트 경로는 포함되므로 이력은 필요한 범위에서 공유한다.

저장 위치를 바꾸려면 실행할 PowerShell 세션에서 `HERMES_DEVKIT_UPDATE_HISTORY_ROOT` 환경변수에 절대 경로를 지정한다. 이력 저장 실패는 경고로 안내하며 기존 마운트 판정과 업데이트 성공·실패 처리는 그대로 유지한다. 이력 수집은 과거 실행의 마운트를 복원하거나 마운트 불일치를 자동 수정하지 않는다.

## 보존과 복구

| 데이터 | 처리 |
|---|---|
| default 모델·OAuth·메모리·세션 및 사용자 설정 | 관리 대상 필드 외 보존 |
| 기존 Kanban DB·카드·상태·사용자 프로젝트 | 수정/삭제하지 않음 |
| 기존 `profiles/orchestrator`, `coder`, `reviewer` | `devkit-lite/legacy-profiles/`로 보관 |
| 설정 및 이전 Lite overlay marker | `devkit-lite/backups/`에 보존 |
| named volume / host bind / 외부 mounts | 실제 식별자와 권한 유지 |

전환 전 데이터를 백업해 두는 것을 권장한다. 전환 도중 오류는 이 작업이 변경한 내용만 되돌린다. 프로세스 강제 종료·충돌로 `prepared` journal이 남았으면 자동 덮어쓰기/복구를 중단한다. 다음 부팅도 실패하도록 하여 부분 상태로 Worker가 시작되지 않게 한다.

복구는 컨테이너를 정지한 상태에서 journal의 backup과 실제 현재 데이터를 대조한 뒤 수행한다. 이후 사용자 변경이 있으면 오래된 config를 통째로 복원하지 않는다. 동명 active/archive가 동시에 존재해도 자동 병합·삭제하지 않는다. 과거 Standard 코드로 되돌리는 작업과 데이터 복구는 별개의 명시적 운영 작업이다. `docker compose down -v`, 볼륨 삭제, `git reset/clean/stash`로 문제를 우회하지 않는다.

상태 확인은 읽기 전용이다:

```powershell
.\scripts\init-lite.ps1 -Mode status
# 내부 진단 시에만 사용: 사용할 Docker 이미지 명시 필요
.\scripts\init-lite.ps1 -Mode plan -ImageReference 'hermes-dev:0.1.0'
.\scripts\verify-container-runtime.ps1
```

## Kanban과 Gateway

Hermes의 native Gateway transport를 유지하되 DevKit 개발 역할은 default만 사용한다. `HERMES_KANBAN_DISPATCH_IN_GATEWAY=false`와 default `kanban.dispatch_in_gateway=false`로 자동 Worker 실행을 끈다. 기존 ready/review 카드를 재실행하거나 역할 프로필을 다시 생성하지 않는다.

Kanban은 요청한 기록·조회 용도다. 선택적 알림 bridge는 이벤트와 자신만의 커서만 처리하며 작업 파일·handoff·scratch를 삭제하지 않는다. native notification 중복 구독은 기본에서 차단한다. 기존 부모·자식 관계 표시와 기록은 유지한다. 사용자 생성 다른 Hermes 프로필 데이터는 임의 변경하지 않는다.

## 검증

```bash
bash scripts/verify.sh
```

이 명령은 활성 스킬·참조·도메인 정책·빌드 격리·updater 구조 검사와 모든 보존된 Python 회귀 테스트를 실행한다. Linux 프로세스·Git fixture, Maven/Gradle 증거 캐시, Node 격리, UI adapter, 설정 보안, migration 실패·충돌·멱등성 등을 포함한다. 실제 사용자 DB나 프로젝트를 수정하지 않는다.

CI는 Linux 전체 회귀, Windows PowerShell 5.1 문법과 모의 Docker updater, 실제 Maven 두 버전, 최신 Hermes 이미지 빌드 및 격리 볼륨 부팅/재시작·이관·실패 차단을 검증한다. 실제 제품의 UI 검증은 선택적인 별도 browser smoke다. Windows PowerShell 모의 검사와 Linux Docker 검증이 사용자의 Windows Docker Desktop/OAuth/모델 응답을 대신하지는 않는다.

Maven/Gradle canonical 실행기는 `/opt/devkit/scripts/verification/`에 있다. Node/pnpm은 `dev-node-dependencies`의 기존 도구를 쓴다. 시간·외부 서비스에 의존하는 검증은 `--no-reuse`로 캐시를 우회한다. 실행되지 않은 테스트나 미확인 결과를 PASS라고 보고하지 않는다.

상세 전환 경계는 `docs/hermes-lite-migration.md`, 검증 이동 내역은 `docs/lite-validation.md`를 참고한다.
