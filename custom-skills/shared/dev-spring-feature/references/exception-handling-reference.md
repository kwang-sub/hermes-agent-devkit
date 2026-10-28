# 예외·ErrorCode 참고 코드 적용

업무 예외·validation·공통 오류 응답이 실제 변경 범위일 때만 읽는다. 동일 책임의 기존 클래스와 오류 계약을 먼저 확인한다.

공통 root `/opt/data/shared/references/samples/spring/`에서 `ADAPTATION.md`, `compatibility.md`, `error-handling.md` 순으로 필요한 내용을 읽는다. 소스는 `kotlin/src/main/kotlin/com/example/samples/error/`다. 인증 필터 오류가 범위일 때만 `security/`를 추가 확인한다.

샘플 이름을 표준으로 강제하지 않는다. 기존 ServiceException/ErrorCode/ProblemDetail/응답 wrapper를 재사용하며 API 필드·상태·직렬화 계약을 유지한다. Python 등에는 Spring advice를 복제하지 않고 기존 중앙 예외 처리에 동일 책임을 반영한다.

필수 검토: 코드 유일성, 오류 정의와 실제 HTTP/body 상태의 일치, 예외 등록 대상, framework 405 등 기존 상태/헤더 보존, rejected value·exception message 비노출, 401/403의 MVC와 필터 경계 구분. Kotlin 샘플 테스트 성공을 다른 언어/실제 SecurityFilterChain 검증으로 간주하지 않는다.

참조 경로·기존 코드와의 차이·검증 범위를 기존 `dev-lite-session` 변경 승인에 포함한다. 별도 승인 절차·보드·Worker를 만들지 않는다.
