# Hermes Agent Docker 운영 및 초기화 가이드

이 문서는 Windows + Docker Desktop 환경에서 Hermes Agent 컨테이너를 실행하고, 컨테이너에 접속하며, `orchestrator`, `coder`, `reviewer` 프로필을 사용하는 기본 방법을 설명한다.

또한 필요한 경우에만 Hermes 데이터를 완전히 삭제하고 처음부터 다시 구성하는 **완전 초기화 절차**를 별도로 설명한다.

> **중요**
>
> 일반적인 실행, 중지, 재시작을 위해 `hermes-dev-data` 볼륨을 삭제할 필요는 없다.  
> `docker compose down -v`는 Profile, OAuth 인증, Session 등 Hermes의 영속 데이터를 삭제하는 **완전 초기화용 명령**이므로 필요한 경우에만 사용한다.

---

## 1. 구성 개요

현재 Hermes Docker 환경은 다음과 같은 형태로 사용한다.

```text
Windows Host
│
├─ D:\docker\hermes-agent
│  ├─ compose.yml
│  ├─ Dockerfile
│  ├─ init-profiles.ps1
│  ├─ custom-skills
│  └─ shared
│
└─ D:\workspace
   └─ 개발 프로젝트
        │
        ▼
Docker Container : hermes-dev
│
├─ /workspace
├─ /opt/custom-skills
├─ /opt/data/shared
└─ /opt/data
      └─ hermes-dev-data Docker Volume
```

주요 저장 위치는 다음과 같다.

| 구분 | 위치 | 특징 |
|---|---|---|
| 개발 프로젝트 | `D:\workspace` → `/workspace` | Bind Mount |
| Custom Skill | `custom-skills` → `/opt/custom-skills` | Bind Mount |
| 공통 Agent 설정 | `shared` → `/opt/data/shared` | Bind Mount |
| Profile / OAuth / Session | `/opt/data` | `hermes-dev-data` Volume |

`/workspace`, `custom-skills`, `shared`는 호스트 파일을 Bind Mount하므로 컨테이너를 삭제해도 호스트 파일은 유지된다.

반면 `/opt/data`는 `hermes-dev-data` Docker Volume에 저장되며 Profile, OAuth 인증 정보, Session 등 Hermes의 영속 데이터를 보관한다.

---

## 1.1 환경별 `.env` 설정

`compose.yml`과 `init-profiles.ps1`은 저장소 루트의 `.env`를 공통 runtime 계약으로 사용한다. `.env`가 없거나 non-secret runtime key가 비어 있으면 현재 문서와 동일한 기본값으로 동작한다. Canonical 예시는 `sample.env`이며, 이전 오타 파일명 `smaple.env`는 사용하지 않는다.

새 환경에서만 다음과 같이 예시를 복사한다. 이 명령은 기존 `.env`를 덮어쓰지 않는다.

```powershell
if (Test-Path .env) { throw ".env already exists; update it manually instead of overwriting it." }
Copy-Item sample.env .env
notepad .env
```

최소한 다음 그룹을 환경에 맞게 확인한다.

- Docker identity: `HERMES_COMPOSE_PROJECT_NAME`, `HERMES_CONTAINER_NAME`, `HERMES_IMAGE_NAME`, `HERMES_IMAGE_TAG`, `HERMES_DATA_VOLUME_NAME`
- Mount: `HERMES_HOST_WORKSPACE_PATH`, `HERMES_CONTAINER_WORKSPACE_PATH`, custom-skills/shared host 및 container path. Runtime data target은 공식 이미지 계약에 따라 `/opt/data`로 고정하고 `HERMES_DATA_VOLUME_NAME`으로 volume identity만 변경한다.
- Network/locale: bind address, Dashboard/Gateway host/container port, `HERMES_TIMEZONE`
- Application: Dashboard, Jira, work-item 설정

다른 사용자의 Windows workspace를 연결하려면 `.env`의 host path만 변경한다.

```dotenv
HERMES_HOST_WORKSPACE_PATH=C:/Users/example/source
```

`HERMES_CONTAINER_WORKSPACE_PATH`의 기본값 `/workspace`는 managed project metadata의 repository path와 일치한다. 이 container path를 변경하면 기존 `.hermes/project.yaml`을 그대로 재사용하지 말고 새 경로에서 project bootstrap을 다시 실행해 managed metadata를 재생성한다. Runtime data mount target `/opt/data`는 공식 이미지의 `HOME` 및 dashboard 실행 경로와 연결되어 있으므로 변경 가능한 `.env` key로 노출하지 않는다.

기존 `.env`에는 credential이 있을 수 있으므로 파일 내용을 `Get-Content`, 로그 또는 채팅에 출력하지 않는다. `sample.env`의 **non-secret runtime block만** 텍스트 편집기로 기존 `.env`에 추가하고 Dashboard/Jira credential 값은 유지한다. `.env`와 인증 파일은 공유하거나 commit하지 않는다.

`init-profiles.ps1` loader는 process environment를 `.env`보다 우선하며, 단순 `KEY=VALUE`, 빈 줄, full-line comment와 value 전체를 감싼 single/double quote만 지원한다. Docker Compose 전용 interpolation, inline comment 또는 복잡한 escape가 필요한 값은 process environment로 전달한다. Container 이름을 바꾼 경우에도 초기화 스크립트는 같은 `.env`를 읽는다. Docker 명령에서 container를 직접 지정해야 할 때는 이름을 하드코딩하는 대신 다음처럼 Compose service에서 ID를 얻을 수 있다.

```powershell
$Container = docker compose ps -q hermes
docker exec --user hermes $Container hermes profile list
```

# 일반 사용

## 2. 작업 디렉터리 이동

PowerShell에서 Hermes Docker 구성 디렉터리로 이동한다.

```powershell
cd D:\docker\hermes-agent
```

현재 상태를 확인한다.

```powershell
docker compose ps
docker volume ls
```

---

## 3. Hermes 컨테이너 실행

### 3.1 일반 실행

이미 Docker 이미지가 준비되어 있고 Dockerfile을 변경하지 않았다면 다음 명령으로 실행한다.

```powershell
docker compose up -d
```

`-d` 옵션은 컨테이너를 백그라운드에서 실행한다.

상태를 확인한다.

```powershell
docker compose ps
```

정상적인 경우 다음과 같이 `hermes-dev`가 `Up` 상태로 표시된다.

```text
NAME         IMAGE              STATUS
hermes-dev   hermes-dev:0.1.0   Up
```

### 3.2 Dockerfile 변경 후 실행

Dockerfile 또는 이미지에 포함되는 패키지 구성을 변경했다면 이미지를 다시 빌드한다.

```powershell
docker compose up -d --build
```

일반적인 실행 때마다 `--build`를 사용할 필요는 없다.

재빌드 후에는 컨테이너 내부에서 Hermes CLI가 PATH에 연결되고 실행 가능한지 확인한다.

```powershell
docker exec --user hermes hermes-dev sh -lc 'command -v hermes && hermes --help > /dev/null && echo HERMES_CLI_OK'
```

성공하면 Hermes 실행 파일 경로와 `HERMES_CLI_OK`가 출력된다. 이 명령은 CLI 가용성만 확인하며 Token, Password 또는 `.env` 내용을 출력하지 않는다.

#### Hermes CLI `SyntaxWarning` 패치 범위

공식 이미지의 `/opt/hermes/hermes_cli/update_cmd.py`에는 Windows 경로를 설명하는 일반 docstring의 ``venv\Scripts``가 포함되어 있다. Python은 `\S`를 유효하지 않은 escape sequence로 해석하므로 CLI 시작 시 `SyntaxWarning`을 출력한다.

이 저장소의 Dockerfile은 이미지 빌드 중 해당 문자열을 ``venv\\Scripts``로 한 번 보정하고 `SyntaxWarning`을 오류로 취급하는 strict compile을 실행한다. helper는 원본 상태와 이미 보정된 상태만 허용하므로 재실행에 안전하며, upstream 내용이 예상과 달라지면 경고를 숨기지 않고 빌드를 실패시킨다. 이 변경은 빌드된 Docker 이미지에만 적용되며 host에 별도로 설치된 `/opt/hermes`는 수정하지 않는다. 따라서 host CLI에서 같은 경고가 보이면 Docker 이미지를 다시 빌드해 확인해야 하며 host 설치 자체의 경고가 즉시 사라지는 것은 아니다.

이미지 빌드 후 strict compile과 CLI stderr를 확인할 수 있다.

```powershell
docker exec --user hermes hermes-dev sh -lc 'PYTHONPYCACHEPREFIX=/tmp/hermes-pycache python3 -W error::SyntaxWarning -m py_compile /opt/hermes/hermes_cli/update_cmd.py && hermes --help >/tmp/hermes-help 2>/tmp/hermes-help.err && test ! -s /tmp/hermes-help.err && echo HERMES_SYNTAX_WARNING_OK'
```

Hermes 공식 이미지는 컨테이너 시작 시 s6-overlay의 `/init`을 root로 실행해 `/opt/data`와 Profile을 bootstrap한다. 따라서 Dockerfile이나 Compose 서비스에 `USER hermes` 또는 `user: hermes`를 지정하지 않는다. 일상적인 Shell 접속과 Hermes 대화형 명령은 아래 예시처럼 `docker exec --user hermes`로 실행한다.

### 3.3 Healthcheck와 실행 상태 확인

Compose healthcheck는 컨테이너 내부에서 gateway의 `127.0.0.1:8642` 포트에 연결할 수 있는지만 확인한다. `healthy`는 gateway port readiness를 뜻하며 Profile, OAuth, 외부 Provider 연결 등 Hermes 기능 전체의 정상 동작을 보장하지 않는다.

```powershell
docker compose ps
docker inspect --format '{{json .State.Health}}' hermes-dev
```

`docker compose ps`의 STATUS에서 `healthy` 여부를 확인하고, 필요할 때 두 번째 명령으로 최근 healthcheck 결과를 확인한다. 기능 수준 검증은 이어지는 Profile 및 `hermes status` 확인 절차를 별도로 수행한다.

---

## 4. 컨테이너 중지 및 재시작

### 일시 중지

```powershell
docker compose stop
```

다시 실행:

```powershell
docker compose start
```

### 컨테이너 재시작

```powershell
docker compose restart
```

### 컨테이너와 Compose 네트워크 제거

```powershell
docker compose down
```

`docker compose down`은 컨테이너와 Compose 네트워크를 제거하지만 `hermes-dev-data` Named Volume은 유지한다.

따라서 다시 실행하면 기존 Profile 및 OAuth 정보를 그대로 사용할 수 있다.

```powershell
docker compose up -d
```

> `docker compose down`과 `docker compose down -v`는 다르다.  
> `-v`를 붙이면 Hermes 데이터 Volume까지 삭제되므로 주의한다.

---

## 5. Hermes 컨테이너 접속

### 5.1 Shell로 접속

Hermes 사용자로 컨테이너 Shell에 접속한다.

```powershell
docker exec -it --user hermes hermes-dev sh
```

접속 후 현재 사용자를 확인한다.

```sh
whoami
```

정상적인 경우:

```text
hermes
```

작업 공간으로 이동한다.

```sh
cd /workspace
```

컨테이너 Shell에서 빠져나오려면:

```sh
exit
```

### 5.2 Shell 접속 없이 명령 실행

```powershell
docker exec --user hermes hermes-dev hermes profile list
```

단순 조회 명령은 이 방식을 사용하는 것이 편리하다.

---

## 6. Hermes Agent 실행

현재 구성에서는 역할별로 다음 Profile을 사용한다.

```text
orchestrator  작업 접수, 분해, 작업 흐름 관리
coder         실제 코드 구현
reviewer      코드 리뷰 및 검증
```

### Orchestrator 실행

```powershell
docker exec -it --user hermes hermes-dev hermes -p orchestrator chat
```

### Coder 실행

```powershell
docker exec -it --user hermes hermes-dev hermes -p coder chat
```

### Reviewer 실행

```powershell
docker exec -it --user hermes hermes-dev hermes -p reviewer chat
```

`-p` 옵션은 사용할 Hermes Profile을 지정한다.

```text
hermes -p orchestrator chat
       │
       └─ orchestrator Profile로 대화 세션 실행
```

---

## 7. Hermes 상태 확인

### 전체 Profile 목록

```powershell
docker exec --user hermes hermes-dev hermes profile list
```

### Profile 상세 확인

```powershell
docker exec --user hermes hermes-dev hermes profile show orchestrator
docker exec --user hermes hermes-dev hermes profile show coder
docker exec --user hermes hermes-dev hermes profile show reviewer
```

### Profile 상태 확인

```powershell
docker exec --user hermes hermes-dev hermes -p orchestrator status
```

### 모델 설정 확인

```powershell
docker exec --user hermes hermes-dev hermes -p orchestrator config get model --json
docker exec --user hermes hermes-dev hermes -p coder config get model --json
docker exec --user hermes hermes-dev hermes -p reviewer config get model --json
```

---

# 최초 구성

아래 절차는 `hermes-dev-data` Volume을 처음 생성했거나 완전 초기화한 뒤 Profile을 구성할 때 수행한다. 기존 환경의 Profile 및 External Skill 설정을 점검하거나 복구할 때도 동일한 스크립트를 다시 실행할 수 있다.

`init-profiles.ps1`은 재실행 가능하다. 기존 Profile은 다시 생성하지 않고 `[OK]`로 처리하며, `skills.external_dirs`가 이미 올바른 YAML list이면 config 파일을 변경하거나 백업을 추가로 만들지 않는다.

## 8. 초기 Profile 상태 확인

```powershell
docker exec --user hermes hermes-dev hermes profile list
```

Fresh 환경에서는 기본적으로 `default` Profile만 존재할 수 있다.

`orchestrator`, `coder`, `reviewer`가 이미 존재한다면 Profile 초기화가 완료된 환경이므로 다시 생성할 필요는 없다.

---

## 9. 초기화 전제 조건과 Bind Mount 확인

스크립트를 실행하기 전에 다음 조건이 필요하다.

- Docker CLI가 PATH에 있고 Docker Desktop daemon에 연결할 수 있다.
- `hermes-dev` 컨테이너가 실행 중이다.
- `/workspace`, `/opt/custom-skills`, `/opt/data/shared`가 Compose의 bind mount로 연결되어 있다.
- 컨테이너의 `hermes`, `python3`, PyYAML을 사용할 수 있다.
- 역할별 External Skill 디렉터리와 `/opt/data/shared/AGENTS.common.md`가 존재한다.

```powershell
docker compose ps
docker exec --user hermes hermes-dev sh -lc 'command -v hermes && command -v python3 && python3 -c "import yaml"'
docker exec hermes-dev ls -la /opt/custom-skills/orchestrator
docker exec hermes-dev ls -la /opt/custom-skills/coder
docker exec hermes-dev ls -la /opt/custom-skills/reviewer
docker exec hermes-dev ls -l /opt/data/shared/AGENTS.common.md
```

`init-profiles.ps1`도 실행 초기에 위 조건과 bind mount 유형/대상 경로를 확인하고, 충족되지 않으면 Profile 또는 config를 변경하기 전에 중단한다.

---

## 10. Profile 초기화

최초 구성 또는 기존 설정 점검 시 다음 스크립트를 실행한다. 같은 명령을 연속으로 실행해도 기존 Profile은 유지된다.

```powershell
.\init-profiles.ps1
.\init-profiles.ps1  # 재실행 검증: 기존 항목은 [OK]로 처리
```

스크립트는 다음 Profile을 구성한다.

```text
orchestrator
coder
reviewer
```

각 Profile별 External Skill 경로:

```text
orchestrator → /opt/custom-skills/orchestrator
coder        → /opt/custom-skills/coder
reviewer     → /opt/custom-skills/reviewer
```

각 `config.yaml`의 값은 scalar string이 아니라 다음과 같은 YAML list로 설정되고 검증된다.

```yaml
skills:
  external_dirs:
    - /opt/custom-skills/coder
```

기존 `config.yaml`에서 변경이 필요한 경우에만 같은 디렉터리에 타임스탬프가 포함된 백업을 먼저 만든다. 스크립트는 백업 경로만 알리고 config 또는 백업 내용을 출력하지 않으며, `skills.external_dirs` 외의 section은 유지한다.

생성되는 설정 파일:

```text
/opt/data/profiles/orchestrator/config.yaml
/opt/data/profiles/coder/config.yaml
/opt/data/profiles/reviewer/config.yaml
```

초기화 후 Profile 목록을 확인한다.

```powershell
docker exec --user hermes hermes-dev hermes profile list
```

초기화가 실패하면 config나 인증 파일 내용을 출력하지 말고 다음 항목을 순서대로 확인한다.

1. `docker version`이 성공하고 `docker compose ps`에서 `hermes-dev`가 실행 중인지
2. Compose의 `/workspace`, `/opt/custom-skills`, `/opt/data/shared` bind mount가 누락되지 않았는지
3. 컨테이너에서 `command -v hermes`, `command -v python3`, `python3 -c "import yaml"`이 성공하는지
4. 역할별 `/opt/custom-skills/<profile>`과 `/opt/data/shared/AGENTS.common.md`가 존재하는지
5. 오류가 `config.yaml` YAML 구조를 가리키면 자동 수정하지 말고 해당 Profile의 최신 `.bak-<timestamp>` 백업 경로를 확인한 뒤 안전하게 복구할지 검토할 것

`.env`, `auth.json`, Token, Password, Secret 값은 문제 확인 과정에서도 읽거나 출력하지 않는다.

---

## 11. OpenAI Codex OAuth 및 모델 설정

Profile을 새로 생성한 경우 각 Profile별 OAuth 인증을 진행한다.

### Orchestrator

```powershell
docker exec -it --user hermes hermes-dev hermes -p orchestrator model
```

### Coder

```powershell
docker exec -it --user hermes hermes-dev hermes -p coder model
```

### Reviewer

```powershell
docker exec -it --user hermes hermes-dev hermes -p reviewer model
```

현재 구성 예:

```text
Provider : openai-codex
Model    : gpt-5.6-sol
```

OAuth 정보는 각 Profile의 `/opt/data/profiles/<profile>/auth.json`에 저장된다.

해당 파일들은 `hermes-dev-data` Volume에 저장되므로 일반적인 컨테이너 재시작이나 `docker compose down`으로는 삭제되지 않는다.

---

# 선택 사항: 완전 초기화

## 12. 언제 완전 초기화를 사용하는가

다음과 같은 경우에만 완전 초기화를 고려한다.

- Hermes 개발 환경을 처음부터 다시 검증하려는 경우
- Profile 설정을 모두 삭제하고 재구성하려는 경우
- OAuth 인증 정보를 모두 제거하려는 경우
- Session 및 Hermes 영속 데이터를 모두 제거하려는 경우
- 테스트용 환경을 완전히 Fresh 상태로 되돌리려는 경우

단순한 컨테이너 재시작이나 이미지 재빌드 목적이라면 완전 초기화가 필요하지 않다.

---

## 13. 완전 초기화 전 주의사항

> **WARNING - 데이터 삭제**
>
> 아래 명령은 `hermes-dev-data` Volume을 삭제한다.
>
> 삭제되는 주요 데이터:
>
> - `orchestrator`, `coder`, `reviewer` Profile 상태
> - Profile별 OpenAI Codex OAuth 인증 정보
> - Session 데이터
> - `/opt/data`에 저장된 Hermes 영속 데이터
>
> 초기화 후에는 `init-profiles.ps1` 실행과 Profile별 OAuth 인증을 다시 진행해야 한다.

다음 데이터는 Bind Mount이므로 호스트에 그대로 유지된다.

```text
D:\workspace
D:\docker\hermes-agent\custom-skills
D:\docker\hermes-agent\shared
```

`mssql-data`와 같이 Hermes와 관계없는 Docker Volume은 삭제하지 않는다.

---

## 14. Hermes 데이터까지 완전 삭제

완전 초기화가 필요한 경우에만 다음 명령을 실행한다.

```powershell
docker compose down -v
```

삭제 상태를 확인한다.

```powershell
docker compose ps -a
docker volume ls
```

다음 항목이 제거되었는지 확인한다.

```text
hermes-dev
hermes-dev-data
hermes-dev_default
```

---

## 15. 완전 초기화 후 재구성

컨테이너를 다시 생성한다.

```powershell
docker compose up -d --build
```

상태를 확인한다.

```powershell
docker compose ps
docker volume ls
```

`hermes-dev-data` Volume이 새로 생성되어야 한다.

초기 Profile 상태를 확인한다.

```powershell
docker exec --user hermes hermes-dev hermes profile list
```

이후 다음 순서로 다시 구성한다.

```text
1. docker compose up -d --build
        ↓
2. Bind Mount 확인
        ↓
3. .\init-profiles.ps1
        ↓
4. orchestrator OAuth / Model 설정
        ↓
5. coder OAuth / Model 설정
        ↓
6. reviewer OAuth / Model 설정
        ↓
7. Profile 상태 확인
```

---

# 저장소 검증

## 16. 통합 검증 스크립트 실행

저장소 루트에서 다음 스크립트를 실행하면 env contract, Custom Skill 컴파일, 주요 Orchestrator 회귀 테스트, Shell 문법 및 Docker Compose 구성을 한 번에 검증할 수 있다. Env contract 검사는 `sample.env`만 검사하며 실제 `.env`는 읽지 않는다.

```sh
bash scripts/verify.sh
```

스크립트는 첫 실패에서 0이 아닌 종료 코드로 중단한다. `pwsh` 또는 `powershell`이 있으면 `init-profiles.ps1` 문법과 임시 fixture 기반 `.env` helper self-test를 실행하고, 현재 Linux 환경처럼 PowerShell 실행기가 없으면 `[SKIP] PowerShell syntax`로 명확히 보고한다. Docker CLI, Compose 플러그인 또는 Docker daemon을 사용할 수 없는 환경에서는 Docker Compose 구성 검증만 `[SKIP]` 경고로 보고하고 나머지 검증을 계속한다.

Docker Compose 검증의 상세 출력은 환경변수에 포함된 Token이나 Password가 노출되지 않도록 표시하지 않는다. 실패 시에는 저장소를 로컬에서 직접 점검하되 진단 출력을 외부에 공유하기 전에 반드시 민감정보를 마스킹한다.

---

# 자주 사용하는 명령 요약

| 목적 | 명령 |
|---|---|
| 일반 실행 | `docker compose up -d` |
| 이미지 재빌드 후 실행 | `docker compose up -d --build` |
| 상태 확인 | `docker compose ps` |
| 일시 중지 | `docker compose stop` |
| 다시 시작 | `docker compose start` |
| 재시작 | `docker compose restart` |
| 컨테이너 제거, 데이터 유지 | `docker compose down` |
| 컨테이너 Shell 접속 | `docker exec -it --user hermes hermes-dev sh` |
| Profile 목록 | `docker exec --user hermes hermes-dev hermes profile list` |
| Orchestrator 실행 | `docker exec -it --user hermes hermes-dev hermes -p orchestrator chat` |
| Coder 실행 | `docker exec -it --user hermes hermes-dev hermes -p coder chat` |
| Reviewer 실행 | `docker exec -it --user hermes hermes-dev hermes -p reviewer chat` |
| 저장소 통합 검증 | `bash scripts/verify.sh` |
| **완전 초기화** | `docker compose down -v` |

---

# 보안 및 운영 주의사항

- `docker compose down -v`는 일반 종료 명령이 아니라 **완전 초기화 명령**으로 취급한다.
- `/workspace`처럼 Bind Mount된 호스트 프로젝트는 컨테이너 삭제와 별개로 유지된다.
- `mssql-data` 등 다른 서비스의 Docker Volume을 실수로 삭제하지 않는다.
- `docker compose config` 출력에는 환경변수의 Token 또는 Password가 표시될 수 있으므로 외부 공유 시 반드시 마스킹한다.
- `JIRA_API_TOKEN`, Dashboard Password/Secret 등의 인증정보를 Git 저장소나 README에 직접 기록하지 않는다.
- Profile별 OAuth 정보가 저장된 `hermes-dev-data` Volume을 삭제하면 각 Profile의 인증을 다시 해야 한다.
