# 공통 화면 검증 실행

이 실행부는 기존 Playwright/Cypress/프로젝트 runner를 대체하지 않는다.
그 도구가 있으면 그대로 사용하고, Hermes 경로에서만 반복되는 실행 코드를 재사용한다.
제품 소스·인증·dependency·Provider를 검증 편의로 변경하지 않는다.

## 실행 안정성

`ui_runtime.suite.Suite`는 승인된 필수 AC ID 목록을 받아 검사별 결과를 즉시 저장한다.
의존성을 명시한 검사만 선행 실패로 NOT_RUN이 된다. 캡처와 무관한 기능·키보드 검사를
캡처의 dependent로 묶지 않는다. 브라우저 세션이 죽었으면 그 세션을 쓰는 검사만 중단한다.
Node typecheck/lint/test는 기존 node_runtime과 workspace lock을 따르며, 같은 격리
workspace의 서버를 종료한 뒤 실행한다. 동시 실행을 위해 잠금을 해제하지 않는다.

캡처는 소유한 탭을 활성화하고 별도 60초 예산을 사용한다. Hermes 호출은 내부보다
15초 긴 외부 예산을 사용한다. 모든 CDP 명령의 제한을 늘리지 않는다.
full-page/viewport 범위는 검사 중 변경하지 않는다. 캡처 생성은 시각 검토 PASS가 아니다.
의미 있는 복구 조치와 정상 세션 확인 없이 재시도하지 않으며 명시적 재시도도 1회까지다.

Adapter는 canonical process_execution의 프로세스 그룹 종료를 사용하고 살아 있는
자식을 재확인한다. 서버와 Probe 정리 경고를 합산한다. 상태 변경 시 다음 행동과
오류 식별값도 다시 계산한다. 변경된 runtime/설정의 재시도 식별값은 오류 그룹과 별개다.
매 시도는 독립 디렉터리에 저장한다. 최상위 보고서는 최신 결과를 가리키는 사본일 뿐이다.

## 형식 검사와 완료 판정

기존 `browser_verification_evidence.py`의 종료 코드 0은 증적 **형식**이 유효하다는 뜻이다.
`--required-acs approved-ac-ids.json`을 지정한 경우에만 승인된 필수 AC 목록과 대조해
완료를 판정한다. 빈 목록·미실행 AC·정리 미확인은 완료가 아니다.
`ui_verification_v1`도 필수 ID 목록과 각 체크를 대조한다. 부수적인 캡처나 optional
검사의 실패는 기록하되 승인된 필수 범위를 임의로 확대하지 않는다.

운영 로그는 영어 식별자만 사용하고 URL의 인증값·쿠키·실계좌번호·개인정보를 저장하지 않는다.
의도한 제품 결과 불일치는 FAIL, 도구 오류는 INCONCLUSIVE/BLOCKED_ENV, 미지원은
UNSUPPORTED, 선행 조건으로 미실행은 NOT_RUN으로 구분한다. 검사 FAIL만으로 제품
코드가 원인이라고 단정하지 않고 검사 범위(공용 fixture/제품 컴포넌트/실서비스)를 기록한다.

## 동작 검증 API

`ui_runtime.hermes.HermesBrowser`는 설치된 `browser_exec`를 사용한다. 별도 CDP Provider로
전환하지 않는다. 응답 JSON은 실행별 임시 파일로 교환해 큰 캡처의 stdout 잘림을 피한다.
동일 프로세스의 공식 `browser_dialog`만 대화상자에 응답한다. 관찰 연결을 응답 우회로 쓰지 않는다.

```python
from pathlib import Path
from ui_runtime.hermes import HermesBrowser
from ui_runtime.browser import Locator
from ui_runtime.suite import Suite

# 승인된 실제 주소·AC·선택자로 교체한다. 테스트 서버는 기존 node_runtime으로 준비한다.
suite = Suite(Path(task_artifacts), task_id=task_id,
              required=["AC-form", "AC-capture-artifact"], scope="approved product component fixture")
browser = HermesBrowser(task_id=task_id, allowed_origins=[approved_origin])
try:
    page = browser.open(approved_origin + "/accounts", ready="!!document.querySelector('main')")
    def form_check():
        page.fill(Locator(label="이름"), "SAMPLE")
        page.click(Locator(role="button", name="저장"))
        return page.wait(approved_success_predicate) is True
    suite.check("AC-form", "functional", form_check)
    suite.check("AC-capture-artifact", "visual", lambda: page.screenshot(suite.directory))
finally:
    report = suite.finish(browser.close())
```

예제의 캡처 체크는 **캡처 생성**만 검사한다. 디자인 일치 AC는 승인 기준과 실제 캡처를
비교한 프로젝트 matcher 또는 수동 리뷰 근거를 별도 체크로 연결해야 한다.
label/role 선택은 기본 HTML·aria-label만 지원하는 얇은 adapter다. 복잡한 accessible-name
계산이나 shadow component에는 프로젝트 runner를 우선하며 임의 DOM id를 추가하지 않는다.

- `navigate(url, ready=...)`, `wait_route(path, ready=...)`: 예상 경로와 해당 동작 결과 대기.
- `click`, `fill`, `press`, `select`, `checked`: 실제 CDP 포인터/키보드 입력. DOM `.click()`이나
  `.value=`로 사용자 동작 성공을 대신하지 않는다. 제출/삭제 동작을 자동 재실행하지 않는다.
- `viewport(width,height,mobile=False,touch=False)`: 화면 폭 검사와 모바일·터치 에뮬레이션 구분.
- `focused`, `accessibility_snapshot`, `layout_observation`: 키보드/접근성/잘림 검사의 관찰값.
  자동 WCAG 전체 통과나 모든 장치의 통과로 확대하지 않는다.
- `prepare_dialog` → `page.schedule(...)` → `respond_dialog` → 제품 기대 결과 확인:
  승인된 기존 dialog owner를 먼저 준비하고, SPA 이동은 경로/상태로 판정한다.
- `Diagnostics`: 해당 session의 오류 종류·HTTP 상태만 제한적으로 수집한다. 콘솔 인자,
  전체 URL/헤더/개인정보를 기록하지 않고 예상된 4xx나 경고를 일괄 FAIL로 처리하지 않는다.
- `timing_observation`: 진단값이며 별도 AC가 없으면 새 성능 점수 기준을 추가하지 않는다.

서버 준비·페이지 준비·시각 준비를 구분한다. `load`/`networkidle`/모든 폰트·이미지 로딩을
모든 동작의 필수 조건으로 묶지 않는다. 필요한 요소/결과만 기다린다.
레이아웃별 대표 viewport와 승인된 breakpoint 전후, 필요한 loading/empty/error 상태만
명시한다. 캡처·키보드·입력 오류 검사를 서로 불필요하게 종속시키지 않는다.

## 조건부 기능

`OptionalOperations(page, enabled=[...], owner=browser)`에 이번 AC가 요구하는 기능만 지정한다.
조건을 불필요하게 추가하려는 목록이 아니라 권한이나 파일 접근이 필요한 동작의 실행 범위다.

| 기능 | 실행 방식과 범위 |
| --- | --- |
| 업로드 | 승인한 입력 디렉터리의 파일만 DOM.setFileInputFiles로 전달. 파일 개수와 후속 제품 결과를 구분 |
| 다운로드 | 새로 소유한 browserContext에만 다운로드 디렉터리 설정. 파일 완료·크기·해시를 기록하고 내용 체크섬은 필요한 경우만 비교 |
| 팝업 | 부모 target의 openerId와 승인 주소로 새 탭을 연결. 생성한 탭만 정리하고 부모로 복귀 |
| iframe | same-process frame의 별도 execution context에서 조회·입력. OOPIF나 복잡한 프레임 체인은 기존 프로젝트 provider에 위임하며 UNSUPPORTED를 숨기지 않음 |
| 클립보드 | 명시적으로 허용된 disposable browser + owned context에서 가상 문자열을 쓰고 비교. 기존 클립보드를 먼저 읽지 않으며 공용 브라우저 권한을 변경하지 않음 |
| 시각 회귀 | 기존 matcher 우선. Pillow가 이미 있으면 compare_png로 승인 baseline·환경·threshold·mask 비교. baseline 자동 생성/갱신 없음 |

Hermes의 클립보드 동작은 기본 활성화하지 않는다. 전용 소유 브라우저임을 확인할 수 없는
경로는 UNSUPPORTED이며 새 브라우저·dependency·전역 permission을 자동 도입하지 않는다.
다운로드 파일 생성 PASS는 그 파일의 업무 내용 전체 PASS가 아니다. 필요하면 승인된
내용 검사 함수를 별도 functional 체크로 둔다. 캡처 파일 존재도 디자인 승인 근거가 아니다.

표·차트·검색·필터·긴 숫자·지역화·상태 복원은 별도의 브라우저 엔진 기능이 아니다.
기존 `click/fill/press/wait`와 결과 predicate로 해당 AC만 검증한다. 색상만으로 의미 전달,
단위/기준일, overflow, hover 대체 동작은 기존 `dev-ui-ux/references/baseline.md`를 재사용한다.
접근성 자동 snapshot을 전체 WCAG 준수 판정으로 사용하지 않는다. 성능 관찰값이 있다는
이유로 Lighthouse 등 별도 점수 기준을 새로 추가하지 않는다.

## 회귀 검증

기존 단위/계약 테스트에 더해 `.github/workflows/ui-verification.yml`이 UI 공통부 테스트를
실행한다. 실제 관리형 브라우저 연결은 수동 `workflow_dispatch`의 managed-smoke에서
`hermes-ui-smoke` 이미지로 검사한다. 사용자 profile·소스·비밀키를 마운트하지 않으며
모델/API 호출 없이 실제 browser_exec → 공식 dialog → viewport/capture → 정리를 실행한다.
Docker 빌드/실브라우저 접근이 불가능하면 NOT_RUN/BLOCKED로 보고하고 가짜 성공으로 바꾸지 않는다.

```bash
/opt/hermes/.venv/bin/python /opt/devkit/bin/verify_ui_browser_runtime.py \
  --profile-home /opt/data/profiles/coder \
  --artifact-dir /opt/data/browser-verification
```

필요한 기능만 추가할 때: `--features upload,download,popup,frame`.
이 명령은 임시 HTTP fixture만 검증한다. 기존 dialog 6개 조합 검사는
`verify_browser_dialog_runtime.py`를 유지한다. 둘의 PASS를 제품 UI 전체 AC PASS로 확대하지 않는다.
기존 Node Environment Gate와 승인된 실제 제품 harness에서 나머지 제품 AC를 별도로 진행한다.

개발 테스트용 `--mode cdp-test --chrome /path/to/existing/chromium`은 설치된 Chromium의
공통부를 검사하는 명시적 경로일 뿐, Hermes가 없을 때의 fallback이 아니다. 출력 Provider도
`cdp-test`이며 공식 Hermes capability 근거로 사용할 수 없다.

실브라우저 HTTP 이동이 머신 정책에 의해 차단된 경우 정책을 해제하지 않는다.
`DEVKIT_TEST_CHROME` + `DEVKIT_TEST_MEMORY=1` 테스트는 입력·캡처·DOM을 네트워크 없이
확인하는 보조 검사다. HTTP·인증·SPA 실제 라우팅·공식 Hermes E2E로 보고하지 않는다.
