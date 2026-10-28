# 오류 처리 패턴

먼저 [ADAPTATION.md](ADAPTATION.md)를 적용한다. 소스는 `kotlin/src/main/kotlin/com/example/samples/error/`와 선택적 `security/`다.

`ErrorCode → BusinessException → 중앙 처리 → ApiErrorResponse`와 `ErrorCode → OpenAPI 예시`가 같은 상태·코드·공개 메시지를 참조한다. 예제의 이름·필드·응답 wrapper는 프로젝트 표준이 아니다. 기존 ErrorCode/ServiceException/공통 응답이 있으면 그대로 재사용한다.

- HTTP 상태와 코드 유일성은 테스트로 확인한다. 404 예외를 400으로 문서화하지 않는다.
- `BusinessException`은 상태를 별도 인자로 받아 enum과 어긋나지 않도록 한다. 내부 원인은 보존할 수 있지만 클라이언트에 내보내지 않는다.
- `GlobalExceptionHandler`는 ResponseEntityExceptionHandler의 framework 상태/headers를 보존한다. business/validation/unreadable JSON/unexpected failure를 구분한다.
- 잘못된 JSON 값, rejectedValue, SQL, exception.message, stacktrace를 응답에 포함하지 않는다. 샘플 validation 메시지는 값 보간을 피한 고정 문구다. 프로젝트의 안전한 현지화 메시지는 유지할 수 있다.
- unexpected error 로그는 영어 고정 메시지와 타입명만 사용한다. production observability는 프로젝트 정책으로 보강하며 secret/PII를 남기지 않는다.
- 401/403은 필터 계층의 `ApiAuthenticationEntryPoint`/`ApiAccessDeniedHandler` 예시도 제공한다. **기존 SecurityFilterChain에 명시적으로 연결할 때만** 사용한다. 이 샘플은 체인·로그인 방식·인가 규칙을 생성하거나 변경하지 않는다.
- WebFlux/Python 프로젝트에 Servlet advice를 이식하지 않는다. 해당 프레임워크의 기존 예외·응답 확장 지점으로 같은 책임만 옮긴다.

테스트는 MockMvc 실제 오류 응답, 405와 Allow header 보존, 정보 비노출, 인증/인가 adapter 직렬화, 코드 유일성을 확인한다. 프로젝트 전체의 모든 예외를 처리한다는 보장은 아니며 실제 적용 endpoint와 filter 경로에서 검증해야 한다.
