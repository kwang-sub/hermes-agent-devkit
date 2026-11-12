# 문서·UI 디자인 플러그인 최초 도입

이 단계는 `tabella`, `mock-review`, `hardlight-ui`의 설치 진입점과 로컬 검토 보드를 제공합니다. 기존 문서 작성 스킬, 프론트엔드 스킬, 모델, OAuth, Discord, Gateway 구성은 대체하지 않습니다. 공통 디자인 엔진, 자동 시안 생성 파이프라인, 외부 게시, Discord 자동 재개, 모바일 어댑터는 포함하지 않습니다.

## 고정한 공급원

2026-11-12 확인한 Hermes **community** 카탈로그의 커밋을 사용합니다. Nous Research 직접 유지보수나 보안 코드 감사 완료를 뜻하지 않습니다.

| 플러그인 | 버전 | 고정 커밋 | 역할 |
|---|---|---|---|
| tabella | 2.0.7 | `e6e53da87b7a2d6ed81dc675c578dafd72a01b0c` | 문서 생성·읽기·지원 경로의 변환 |
| mock-review | 1.2.0 | `4ec3b90d63ef82efa2c91c6e62845e1f16f66d88` | 로컬 시안 비교·의견 저장·조회 |
| hardlight-ui | 0.2.0 | `2254efe3ba6df2fa5962cd8ed352b5fad80306d4` | 웹 디자인 지침과 제한된 소스·대비·탐색 검사 |

`shared/design-plugins/hermes-pack.yaml`이 공급원과 기본 설정의 기준입니다. 기본 설치 함수는 이 선언을 읽어 Hermes의 `plugins install --ref ... --no-enable`, `plugins validate`, `config set`, `plugins enable`을 사용합니다. 직접 Git clone/소스 덮어쓰기/강제 설치/스캐너 비활성화를 하지 않습니다. `repo + ref` 형식을 쓰므로 Hermes에는 custom source로 표시될 수 있지만 커밋 자체는 위 카탈로그에서 확인한 값입니다. 카탈로그 이동에 따라 자동 갱신하지 않습니다.

## 실행 환경과 보존 범위

Windows PowerShell 5.1 이상 + 기존 `hermes-dev` Docker 환경에서 실행합니다. `-Container`로 다른 컨테이너 이름을 지정할 수 있습니다. 스크립트는 `docker inspect`에서 실제 bind mount를 읽어 호스트 경로를 변환합니다. `/workspace`나 `D:\workspace`를 경로 변환의 고정값으로 쓰지 않으며 Docker Desktop의 `/run/desktop/mnt/host/<drive>` 표기도 처리합니다.

Hermes의 최소 버전은 0.22.0입니다. 설치된 CLI가 `--ref`, `--no-enable`, Agent Plugins v1, 해당 플러그인 등록 기능을 지원하는지도 실제 설치/검증 단계에서 확인합니다. 버전 숫자만으로 전체 호환성을 보장하지 않습니다.

플러그인과 설정은 활성 기본 환경의 `HERMES_HOME`에 저장됩니다. 이 값이 영속 `/opt/data` 아래가 아니거나 기본 설정 파일이 없으면 설치하지 않습니다. 컨테이너의 `hermes` 사용자로 실행하며 root 설치를 금지합니다.

기존 같은 이름의 플러그인이 다른 공급원·커밋이거나 수정되어 있으면 덮어쓰지 않습니다. 명시적으로 비활성화된 플러그인과 기존 `mock-review` 충돌 설정도 보존하고 중단합니다. 다른 플러그인 설정, 모델, 인증 값은 수정하지 않습니다. 설치 중 설정 변경 전 `HERMES_HOME/devkit-state/design-plugins/<실행 식별자>/config.yaml`에 원본 바이트를 권한 0600으로 보관합니다. 이 백업에는 인증정보가 들어 있을 수 있으므로 외부에 공유하지 마세요.

## 최초 실행

먼저 진행 중인 작업을 정상 종료한 상태에서 **기존 업데이트 절차**로 변경된 Compose 설정을 적용합니다. 설치 스크립트는 컨테이너를 재시작·재생성하지 않습니다.

```powershell
# 원격에 반영된 브랜치를 사용할 때는 평소 업데이트 절차를 따릅니다.
.\update-devkit.ps1

# 아직 커밋되지 않은 적용 패치를 검증하는 경우에는 이 명령을 먼저 실행하지 않습니다.
# updater는 깨끗한 checkout을 요구하므로, 패치 검토/게시 절차와 런타임 적용을 구분하세요.
```

`compose.yml`에 추가되는 포트는 `127.0.0.1:8790:8790`입니다. 기존 볼륨, bind mount, Gateway 명령, Dashboard/API 공개 범위는 바꾸지 않습니다. 8790 포트를 이미 사용하는 프로그램이 있으면 임의 종료하거나 다른 포트로 자동 전환하지 않고 충돌을 먼저 해결합니다.

저장소 루트에서 다음 명령을 실행합니다.

```powershell
# 설치 대상과 로컬 정책 조회만 수행합니다. Docker가 없어도 실행됩니다.
.\scripts\design-plugins.ps1 -Mode plan

# 기본 설치·설정. native 보안 확인이 나오면 내용을 확인하세요.
.\scripts\design-plugins.ps1 -Mode install

# 고정 커밋·활성화 설정 및 렌더링 도구 존재 여부를 확인합니다.
.\scripts\design-plugins.ps1 -Mode status
```

설치는 GitHub/PyPI 접근이 필요할 수 있습니다. `tabella`의 문서 라이브러리는 플러그인의 자체 가상환경에서 첫 사용 시 준비됩니다. Hermes 공용 Python에 문서 라이브러리를 강제로 설치하지 않습니다. 별도 HTTP MCP 서버나 8602 포트는 활성화하지 않습니다. Pandoc, TeX, OCR, LibreOffice, 브라우저 등 시스템 의존성을 자동 설치하지 않습니다. 없는 기능은 미검증/미지원으로 구분합니다.

플러그인 활성화는 열려 있는 모든 세션의 로드 완료와 다릅니다. 작업을 저장하고 설치된 Hermes 버전의 지원 reload/새 세션 경로로 로드 상태를 확인하세요. 필요하더라도 이 스크립트가 Gateway나 활성 작업을 강제 재시작하지는 않습니다.

## 미리보기와 의견 저장

별도 PowerShell 창 하나에서 서버를 실행합니다.

```powershell
.\scripts\design-plugins.ps1 -Mode serve
```

이 창은 서버 실행용입니다. `Ctrl+C`로 종료합니다. 백그라운드 데몬, 새로운 s6 서비스, 자동 시작, 피드백 재시도 워커를 추가하지 않습니다.

다른 창에서 기본 샘플을 만듭니다.

```powershell
.\scripts\design-plugins.ps1 -Mode sample
```

플러그인이 반환한 **실제 URL과 검토 ID**를 사용합니다. 고정된 가짜 리뷰 링크를 안내하지 않습니다. 샘플은 단순 HTML 배치 2개를 비교하는 테스트이며 실제 PPT를 렌더링한 결과가 아닙니다. 샘플만 무브랜드(`--no-design`)로 생성하고 실제 사용자 시안의 디자인 규칙은 임의 해제하지 않습니다.

브라우저에서 Change와 구분 가능한 테스트 의견(예: `local-review-check-01`)을 입력하고 Send로 저장합니다. 그런 다음 실제 ID로 조회합니다.

```powershell
.\scripts\design-plugins.ps1 -Mode feedback -ReviewId '<실제 검토 ID>'
```

조회 결과에 저장한 의견이 있는지 확인하세요. 프로그램이 자동으로 사용자 피드백을 만들어 넣거나 검토 완료를 대신 표시하지 않습니다.

자신이 준비한 decisions JSON을 사용하는 경우:

```powershell
.\scripts\design-plugins.ps1 -Mode create -Decisions 'D:\workspace\my-project\design\decisions.json'
```

이것은 플러그인의 기본 JSON 형식에 연결하는 도구일 뿐, 문서나 소스 코드에서 자동으로 시안을 만드는 기능은 아닙니다. `create`는 DevKit 작업 디렉터리를 기본 프로젝트 컨텍스트로 사용합니다. 프로젝트별 디자인 프로필을 명시적으로 사용해야 한다면 해당 프로젝트에서 native `hermes mockreview create --project ...`를 이용하고 아래 로컬·no-wake 규칙을 유지하세요.

사용자는 이후 같은 Hermes 세션에서 “이 검토 ID의 피드백을 읽고, 승인한 범위만 반영해줘”라고 요청합니다. 저장 버튼만으로 CLI가 자동 재개되거나 파일이 바뀌지 않습니다. 피드백은 작업 자료이지 임의 명령·배포·Git 게시 승인으로 취급하지 않습니다.

## 로컬·권한 경계

컨테이너 내부 서버는 Docker 포트 연결을 위해 `0.0.0.0:8790`으로 수신하지만 **Windows 호스트의 게시 주소는 127.0.0.1로 고정**합니다. 같은 Docker 네트워크에 접근 가능한 다른 컨테이너까지 격리하는 인증 수단은 아닙니다. 검토 보드는 로그인이 없으므로 신뢰하지 않는 컨테이너와 네트워크를 공유하지 마세요.

Windows 래퍼는 실제 게시 포트를 조회하여 누락, `0.0.0.0`, IPv6 전체 주소, 중복 게시, 다른 포트를 거부합니다. Dashboard의 `HERMES_PORT_BIND_ADDRESS`를 넓혀도 이 포트에는 적용되지 않습니다. 원격 Docker context의 localhost는 사용자 Windows가 아닐 수 있으므로, 실제 context/DOCKER_HOST가 로컬 Windows named pipe인 경우에만 진행합니다. TCP·SSH·다른 호스트의 named pipe 등 원격 또는 미확인 endpoint는 거부합니다.

각 신규 검토는 `--mode local --no-wake --no-allow-live-demo --footer-button send`로 만듭니다. 다음 기본값도 저장합니다.

- `autostart=false`, `wake_required=false`, `wake_toolsets=[]`: 자동 실행·권한 확대 없음.
- `default_host=local`, `footer_button=send`: 공개 게시나 Build 자동 실행 없음.
- `auto_close_idle_days=0`, `keep_closed_days=0`: 기존 검토 기록을 자동 정리하지 않음.

`hermes mockreview setup`은 webhook 설정을 만들 수 있으므로 이 최초 도입에서는 호출하지 않습니다. here.now, Tailscale 공유, Discord 전달, 자동 재개는 별도 범위입니다. Native 플러그인의 모든 명령을 보안 샌드박스로 봉쇄한 것은 아니므로, 별도 요청 없이 `publish`, `setup`, `--wake`를 실행하지 않습니다.

## 문서·웹 검증

문서는 **실제 PPTX/DOCX/PDF에서 렌더링한 이미지**와 HTML 디자인 방향 예시를 구분해야 합니다. 렌더러 실행 파일이 있다는 사실만으로 문서 렌더링이 검증된 것은 아닙니다. `status`는 도구 존재 여부만 반환하고 실제 렌더링을 `NOT_CHECKED`로 보고합니다.

신규 Hermes 세션에서 실제 기능을 확인할 최소 사례는 다음과 같습니다.

1. `tabella` 도구로 임시 폴더에 한글 DOCX/PPTX를 생성하고 다시 읽어 내용 보존을 확인합니다. 실제 설치 경로에서 번들 스킬·도구 스키마를 읽고 실행합니다. 생성 경로는 사용자 작업 폴더/영속 데이터 경로 안으로 제한합니다.
2. 렌더링 도구가 사용 가능하면 실제 문서 렌더링을 수행하고 한글·줄바꿈·이미지를 확인합니다. 없으면 결과는 생성 성공/렌더링 미검증으로 나눕니다.
3. `hardlight_contrast`로 흰색과 검정색의 대비를 확인하고, 임시 HTML 파일에 `hardlight_inspect`를 실행합니다. 제한된 검사 결과를 전체 접근성 인증이라고 표현하지 않습니다.
4. 샘플 검토 링크를 Windows 브라우저에서 열고 의견 저장 → native 피드백 조회까지 확인합니다.

각 단계가 성공하기 전에는 최초 런타임 도입이 완료됐다고 판정하지 않습니다. 설치/활성화 설정, CLI 가용성, 실제 도구 호출, 문서 렌더링, Windows 브라우저, 피드백 왕복을 따로 기록합니다.

## 회귀 검증과 실패 시 처리

```bash
python scripts/test_design_plugins.py
python -m py_compile scripts/design_plugins.py scripts/test_design_plugins.py
```

```powershell
.\scripts\test_design_plugins.ps1
```

전용 GitHub Actions는 Python 오프라인 계약과 Windows PowerShell 경로·포트 계약을 실행합니다. 기존 `Verify DevKit`의 updater/mount 테스트도 그대로 유지합니다. 오프라인 테스트가 실제 플러그인 설치나 Windows 브라우저 검증을 대신하지는 않습니다.

설치 실패 시 앞에서 설치된 플러그인과 백업을 자동 삭제하지 않습니다. 설정을 일괄 되돌리지도 않습니다. 중단 지점과 실제 상태를 확인한 후, 동일 커밋의 깨끗한 설치는 재사용하고 필요한 작업만 다시 수행합니다. 커밋이나 설정 충돌은 강제로 덮어쓰지 않습니다.

## 원문 근거

- Hermes 플러그인 설치·pin·pack·동의: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins/
- 카탈로그: https://github.com/NousResearch/hermes-agent/tree/main/plugin-catalog
- Mock Review 설정: https://github.com/apelabs-dev/hermes-mock-review/blob/4ec3b90d63ef82efa2c91c6e62845e1f16f66d88/plugin.yaml
- Mock Review CLI: https://github.com/apelabs-dev/hermes-mock-review/blob/4ec3b90d63ef82efa2c91c6e62845e1f16f66d88/docs/cli.md
- Tabella 자체 환경: https://github.com/dyiapanis/tabella/blob/e6e53da87b7a2d6ed81dc675c578dafd72a01b0c/scripts/setup.sh
- Hardlight UI: https://github.com/nosliwhtes/hardlight-ui/tree/2254efe3ba6df2fa5962cd8ed352b5fad80306d4
