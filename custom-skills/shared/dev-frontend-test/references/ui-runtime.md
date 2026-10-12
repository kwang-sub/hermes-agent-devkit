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
