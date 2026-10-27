# 관리형 브라우저의 네이티브 대화상자 검증

## 수정 대상과 근거

Hermes의 `browser.dialog_policy=must_respond`와, Chromium을 실행하는 `agent-browser`의
자동 응답 정책은 별개의 계층이다. agent-browser는 기본적으로 `alert`와 `beforeunload`를
`accept=true`로 처리하고 `confirm`/`prompt`는 명시적 응답을 기다린다.
따라서 Supervisor 설정만 확인해 하위 자동 승인을 배제해서는 안 된다.

DevKit 이미지의 `patch_hermes_browser_dialog_policy.py`는
`tools/browser_tool_session.py::_agent_browser_command_env`에서 PM 환경 구성이 끝난 후,
상위 정책이 `must_respond` 또는 `auto_dismiss`이면
`AGENT_BROWSER_NO_AUTO_DIALOG=1`을 하위 실행 환경에 전달한다.
명시적인 상위 `auto_accept` 설정은 변경하지 않는다. 상위 명시적 응답 정책이
충돌하는 하위 `AGENT_BROWSER_NO_AUTO_DIALOG=0`보다 우선한다.

기존 Chromium, Browser Harness, Playwright/Node 의존성, application source,
window.confirm/beforeunload listener는 수정하지 않는다. 이미 떠 있는 daemon은 환경변수를
다시 읽지 않을 수 있으므로 신규 관리형 세션에서 검증한다. 작업 중인 다른 세션을 일괄 종료하지 않는다.
upstream 함수나 설치 anchor가 바뀌면 이미지를 추측으로 패치하지 않고 빌드를 실패시킨다.

## 실행 계층 통합

기존 `browser_runtime_adapter.py`가 임시 HTTP fixture와 실측 Probe의 시작·준비·시간제한·종료를 관리한다.
새 진입점은 다음과 같다. 이 명령은 UI 구현을 수정하거나 Kanban 카드를 unblock하지 않는다.

```bash
/opt/hermes/.venv/bin/python /opt/devkit/bin/verify_browser_dialog_runtime.py \
  --profile-home /opt/data/profiles/coder \
  --artifact-dir /opt/data/browser-verification
```

위 경로의 실행 파일은 이미지 재빌드 후 설치된다. 저장소 스크립트를 직접 검사할 때는
`/workspace/hermes-agent-devkit/scripts/verify_browser_dialog_runtime.py`를 사용할 수 있지만,
실제 Hermes 모듈에 패치가 설치되지 않았으면 의도적으로 `BLOCKED`가 된다.

Probe는 설치된 `browser_exec`를 통해 **관리형 Chromium을 기동**한다.
`BU_CDP_*`로 직접 기동한 Chrome을 끼워 넣지 않는다. `browser_dialog`와
`SUPERVISOR_REGISTRY`는 같은 Python process와 task ID를 사용한다.
Supervisor를 fixture origin과 이번 검사 표식으로 focus한 뒤 pending dialog ID로만 응답한다.
별도 CDP 연결은 관찰 및 결과 조회용이며 Hermes 모드에서 이탈 거절을 대신하지 않는다.
외부 CDP/cloud/real-profile 설정이 있으면 임의 provider 전환 없이 중단한다.

## 검사 항목

`beforeunload`의 새로고침/문서 이동 각각에 대해 승인·거절을 검사하고,
일반 confirm의 승인·거절도 함께 검사한다. 총 6개 조합이 모두 확인되어야 capability PASS다.

거절은 기존 문서 ID와 입력값이 유지되어야 한다. 승인은 실제 문서 ID 변경을 확인해야 한다.
사용자 활성화, dirty 상태, 실제 opening/closed 이벤트, 응답 시각·주체·성공,
같은 session/frame, 최종 값, cleanup 상태를 함께 검증한다.
Hermes가 confirm을 bridge로 처리한 경우 `Hermes.dialogPending`으로 구분하며
가짜 `Page.javascriptDialogOpening` 이벤트를 만들지 않는다.

`managed_dialog_evidence.py`는 직접 CDP 응답, 정책 모델, 누락된 시각,
다른 frame의 종료, 불완전한 조합, cleanup 실패를 공식 경로의 PASS로 인정하지 않는다.
원본 제품 UI의 AC 검증은 capability PASS 이후 별도로 필요하다.

## 검증 범위와 재시도

`probe_managed_dialog.py --mode agent-browser`는 실제 설치된 CLI의 하위 정책 비교용이다.
`--mode policy-model --offline-fixture`는 개발 머신의 실제 Chromium에서 공개 소스와 같은
자동 응답 정책을 재현하는 보조 실험이다. 이것을 실제 agent-browser/Hermes E2E로 보고하지 않는다.
정책 모델의 성공이나 출력 JSON 형식 검사만으로 제품 구현 단계를 재개하지 않는다.

Browser metadata/정책/검사 실패 단계가 같으면 같은 제품 작업을 다시 시도하지 않는다.
새 이미지와 **신규 관리형 세션**에서 공식 응답 Probe의 결과를 확보한 후 기존 승인·Recovery 계약을 따른다.

## 근거

- agent-browser 공식 README의 Dialogs: `--no-auto-dialog`, `AGENT_BROWSER_NO_AUTO_DIALOG`
- vercel-labs/agent-browser PR #1075의 native `start_dialog_handler`: `accept=true`
- Hermes `browser_tool_session.py`의 관리형 Chromium 실행 환경 구성
- A~E 독립 진단은 raw Chromium/CDP 경로였으므로 관리형 launcher 정책의 검증과 구분

## Run 93 이후 대상 확인 간소화

페이지 제목은 대상 확인 조건으로 사용하지 않는다. Browser Harness가 제목 앞에 `🐴 `를
붙이거나 제목이 비어 있어도 검사 결과에 영향을 주지 않는다.

대상 확인은 **검사용 주소와 이번 실행의 표식**만 필수로 유지한다. 주소는 scheme/host/port/path와
검사용 query 값으로 비교한다. 일반 query의 추가·순서 변경, URL fragment, 루트 경로의 빈 슬래시는
허용한다. 다른 origin·port·path, 누락/변경/중복된 실행 표식은 허용하지 않는다.
같은 origin의 다른 탭은 무시하지만, 이번 표식에 해당하는 탭이 여러 개면 임의로 선택하지 않는다.

고정 meta 값, HTML 태그 종류, `readyState=complete`, 사전 `docId` 존재 같은 중복 조건은
대상 확인에 추가하지 않는다. 클릭/입력에 필요한 요소는 제한시간 안에서 기다린다.
사용자 활성화·dirty 입력 및 승인/거절 후 문서·입력 보존은 기존 동작 검사에서 확인한다.
완화한 것은 준비 단계의 부수적인 조건이지 실제 UI 완료 기준이나 공식 응답 경로가 아니다.

준비 단계에서 중단되면 요약에 `failed_phase`와 `failed_case`를 남긴다.
`FIXTURE_TARGET_UNCONFIRMED`(대상 미확인)와 `FIXTURE_NOT_READY`(필수 요소 준비 실패)를
`INCOMPLETE_DIALOG_MATRIX`와 구분하며, 이 결과로 제품 결함이나 beforeunload 재발을 단정하지 않는다.
공식 응답·이벤트 순서·입력 보존·전체 검사 조합의 PASS 기준은 변경하지 않는다.
