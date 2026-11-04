# 스택별 선택적 개발 스킬

실제 target 버전·프로젝트 관례가 우선이다. 필요한 스킬만 읽고 모든 하위 스킬을 자동 로드하지 않는다.

- `backend`: `dev-spring-feature`
- `backend-data`: `dev-spring-data`
- `frontend`: `dev-frontend-feature`
- `data`: `dev-data-feature`
- `data-migration`: `dev-db-migration`
- `infrastructure`: `dev-infrastructure`
- `api-specification`: `dev-api-spec`
- `api-contract`: `dev-api-contract`

Java/Kotlin/TypeScript는 각 language guideline, 기술 버전 확인은 `dev-official-docs-context`, 선택적 전체 자체 검토는 `dev-review`를 사용한다.

에러 로그·코드 동작·두 구현의 차이를 일정한 형식으로 설명하는 요청에는 `dev-analysis-report`를 사용한다. 기술 동작의 공식 근거가 필요하면 `dev-official-docs-context`로 대상 버전의 문서를 확인하고, 보고에 공식 URL과 그 근거가 뒷받침하는 판단을 함께 적는다.
