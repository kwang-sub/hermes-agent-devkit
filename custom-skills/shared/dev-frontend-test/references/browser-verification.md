# Browser Verification Contract V1

Applies to Direct, Standard, Recovery and CHANGES_REQUESTED frontend work.
이 문서는 실행 정책이며 새 브라우저 Provider나 프로젝트 테스트 프레임워크가 아니다.
실행 코드와 사용법은 `ui-runtime.md`, 네이티브 대화상자는 `managed-dialog-policy.md`를 참조한다.

## 검증 선택과 범위

승인된 Verification Provider/Method/Environment와 프로젝트의 기존
Playwright/Cypress/Storybook/Testing Library/test scripts를 우선한다.
새 dependency 설치·Provider 전환·production 인증/DB 변경은 기존 승인 절차를 따른다.
Node 명령은 기존 node_environment_gate.py, node_verification_cached.py, node_runtime.py를 사용한다.

Screen Spec의 F/UI/AC와 **이번 작업에 필요한 capability만** 연결한다.
일반 화면에서 beforeunload·다운로드·클립보드 전체를 필수 사전 검사로 돌리지 않는다.
기능, 접근성, 반응형, 캡처 생성, 디자인 일치, 시각 회귀는 서로 대체하지 않는 결과다.
기존 View Strategy와 승인된 대표 viewport/breakpoint를 사용하며 모든 device catalog를 순회하지 않는다.

## 공통 실행

`ui_runtime`은 기존 Provider 위의 얇은 실행부다. 페이지 대상·대기·입력·캡처·증적·정리를
작업마다 다시 구현하지 않는다. UI별 선택자·기대 결과만 승인된 제품 테스트 코드에 둔다.
부수적인 제목·readyState·HTML 구조·query 순서로 정상 페이지를 거절하지 않는다.
작업 소유 target/session과 승인 origin은 유지하고, 기존 사용자 탭을 일괄 조작하지 않는다.

서버 생존 응답과 제품 화면 준비를 구분한다. native dialog 유발은 비동기로 예약하고
pending 대화상자 ID에 대해 공식 응답을 보낸다. 막힌 페이지 JS에서 응답 준비를 기다리지 않는다.
`beforeunload`는 실제 사용자 활성화·dirty 입력·명시적 응답·문서 및 입력 보존을 확인한다.
A~E 독립 CDP PASS, 정책 모델 PASS, 새 카드 생성, 파일 수정 시각은 제품 동작 PASS의 대체물이 아니다.
공식 관리형 응답 경로는 `verify_browser_dialog_runtime.py`, 일반 UI 연결은
`verify_ui_browser_runtime.py`로 검증한다. fixture PASS 뒤 제품 AC는 별도로 검사한다.

검사 결과를 즉시 저장하고 독립 검사를 분리한다. 캡처 실패가 입력·키보드·정적 검사의
선행 실패가 되지 않도록 한다. 세션이 정상인 경우 독립 검사는 계속하며 세션이 죽으면
그 세션을 사용하는 검사만 NOT_RUN으로 남긴다. Node workspace lock은 우회하지 않는다.
필수 시각/동작 검증이 남아 있으면 최종 완료나 Reviewer 인계는 보류한다.

## 결과·증적

AC 결과는 `PASS | FAIL | NOT_RUN`으로 유지한다. 실행 환경 결과는 별도로
`PASS | FAIL | BLOCKED_ENV | UNSUPPORTED | INCONCLUSIVE | NOT_RUN`으로 기록한다.
도구 실행 실패나 미지원은 제품 결함이 아니다. 실행했고 기대값과 다른 결과는 해당 검사 FAIL이다.
검증 준비 단계 실패와 실제 대화상자/화면 오류를 구분하고 `failed_phase`를 보존한다.

`browser_verification_v1`은 기존 task_id/provider/session/verified_at/capabilities/
acceptance_criteria/cleanup 형식을 유지하며 `scripts/browser_verification_evidence.py`로 검사한다.
형식 PASS는 완료 PASS가 아니다. `--required-acs`로 승인된 필수 목록을 함께 제공해야
최종 완료를 평가한다. 빈 목록, 빈 PASS 근거, 필수 미실행, 정리 미확인을 완료로 바꾸지 않는다.
신규 공통 suite는 `ui_verification_v1`에 scope/required/checks/cleanup을 기록한다.

시도별 디렉터리·검사별 결과·캡처 파일을 보존한다. 같은 파일로 이전 실패 증적을 덮어쓰지 않는다.
소스/검증 runtime 버전·viewport·검증 범위를 자동 기록하고 수작업 전사를 피한다.
비밀번호·쿠키·CDP 토큰·인증 헤더·실계좌번호·개인정보를 증적에 남기지 않는다.
콘솔 경고/예상된 요청 실패는 진단 정보이며 자동으로 제품 FAIL을 만들지 않는다.

## 반복·정리·복구

`browser_dialog_trace.py`는 **오프라인 이벤트 분석기**다. raw CDP trace 성공을 공식
browser_dialog 경로 성공으로 해석하지 않는다. 새 Provider나 응답 클라이언트를 실행하지 않는다.
같은 Provider/capability/failure signature를 근거 없이 반복하지 않는다. 오류 그룹 Fingerprint와
runtime/설정 변경에 따른 재시도 Fingerprint는 별개이며 새 세션 이름만으로 해결됐다고 보지 않는다.
캡처의 명시적 복구 재시도는 원인 조치와 정상 세션 확인 후 1회까지이며 범위를 바꾸지 않는다.
제출·삭제·저장 같은 동작을 일반 retry loop로 재실행하지 않는다.

공용 Adapter는 canonical process_execution을 재사용하고 자기 서버/Probe 그룹만 종료한다.
브라우저는 자기 target/context/task 세션을 정리하며 모든 브라우저를 종료하지 않는다.
부모 프로세스 종료나 세션 이름 검색 부재만으로 전체 정리 PASS를 선언하지 않는다.
Probe와 서버 정리 경고를 합산하고 최종 상태·다음 행동·오류 식별값을 일관되게 계산한다.
오류를 숨기기 위한 불필요한 config 변경·보안 검사 해제·전역 permission 허용을 하지 않는다.

필수 AC 미확인 상태로 Kanban unblock / Reviewer handoff / 완료 처리하지 않는다.
기존 PASS는 원래 scope/시각과 함께 보존하되 이번 제품 검증으로 자동 승격하지 않는다.
검증 Runtime 수리와 제품 UI 변경은 승인된 작업 범위를 유지한다.

## Handoff

Browser Provider: <approved project runner | Hermes browser_exec | NOT_REQUIRED>
Browser Capability Gate: PASS | BLOCKED | NOT_REQUIRED
Browser Capability Evidence: <validated JSON path | NONE>
Browser Execution Status: PASS | FAIL | BLOCKED_ENV | UNSUPPORTED | INCONCLUSIVE | NOT_RUN
Browser Cleanup: PASS | WARNING | NOT_RUN
Required AC Outstanding: <AC IDs | NONE>
Browser Recovery Fingerprint: <provider/capability/signature | NONE>
Verification Scope: <fixture | product component | service integration>
