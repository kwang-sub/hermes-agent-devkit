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
              required=["AC-form", "AC-visual"], scope="approved product component fixture")
browser = HermesBrowser(task_id=task_id, allowed_origins=[approved_origin])
try:
    page = browser.open(approved_origin + "/accounts", ready="!!document.querySelector('main')")
    def form_check():
        page.fill(Locator(label="이름"), "SAMPLE")
        page.click(Locator(role="button", name="저장"))
        return page.wait("!!document.querySelector('[role=status]')") is True
    suite.check("AC-form", "functional", form_check)
    suite.check("AC-visual", "visual", lambda: page.screenshot(suite.directory))
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
