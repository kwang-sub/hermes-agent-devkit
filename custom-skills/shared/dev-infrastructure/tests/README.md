# Infrastructure lifecycle tests

이 디렉터리의 테스트는 Infrastructure canonical capability의 runtime/platform/vendor/endpoint 탐지와 transition planning을 검증한다.

핵심 회귀 범위:
- evidence 없는 신규 프로젝트는 Observed `UNKNOWN`을 유지하고 `INITIAL_CONFIGURATION`으로 분류
- `NEXT_PUBLIC_SUPABASE_URL`/`SUPABASE_URL`만으로 프로젝트 DB를 Supabase로 확정하지 않음
- 실제 Supabase DB endpoint/local config는 강한 DB evidence로 사용
- `Dockerfile.*`, `compose.*.yml`, `docker-compose.*.yaml` 변형 탐지
- host/port 단독 변경은 `HOST_CHANGE`
- runtime + endpoint 변경은 `COMBINED_CHANGE`
- vendor 변경은 Data Migration Gate 유지
