# 애플리케이션 설정·Secret 보존

기존 프로젝트의 설정 위치·로딩 순서와 실제 배포 환경을 우선한다. 기존 secret 의심 항목은 위치·유형만 보고하고 값은 노출하지 않는다. 기존 경고 때문에 무관한 기능 구현을 차단하거나 사용자 파일을 자동 수정하지 않는다.

새로 작성하거나 수정하는 설정에서는 비밀번호, 개인키, 토큰, 개인 데이터가 Git tracked 파일·Dockerfile·Compose·샘플·로그에 들어가지 않도록 한다. 환경변수 또는 기존 Secret 공급 경로를 참조하며 값이 없는 `.env.example`만 문서화한다. 공개키와 실제 개인키·keystore를 구분한다.

`dev-project-setup`의 `ensure_config_security.py`, `ensure_gitignore.py`는 사용자가 설정 준비를 요청한 범위에서만 실행한다. 기존 ignore 규칙과 사용자 `.env.example`을 전체 교체하지 않는다. 이미 추적되는 파일을 사용자 승인 없이 untrack/delete하지 않는다. 정적 분석 결과를 실제 비밀값의 부재 보장이라고 표현하지 않는다.

Java/Spring 설정의 `${ENV_VAR}`·프로필 로딩, Next.js의 공개 환경변수 prefix 및 서버/브라우저 번들 경계를 구분한다. 비밀값을 클라이언트 번들에 노출하는 새 변경은 완료하지 않는다. 빌드/테스트 결과와 별도로 설정·Secret 위험을 설명한다.
