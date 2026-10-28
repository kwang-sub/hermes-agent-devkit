# ErrorCode 기반 OpenAPI 예시

먼저 [ADAPTATION.md](ADAPTATION.md)를 적용한다. `kotlin/src/main/kotlin/com/example/samples/openapi/`와 `example/SampleResourceController.kt`를 읽는다.

`ApiErrorExamples → ErrorCodeOperationCustomizer → 상태별 responses/application/json/examples`가 기준 흐름이다. Swagger UI 모양 자체가 아니라 실제 런타임 오류와 문서의 의미 계약이 목적이다.

## 기존 응답 보존

- 새로운 응답에 필수 description과 실제 ApiErrorResponse 구조의 inline schema를 추가한다. 기존 description/headers/links/schema/examples는 교체하지 않는다.
- 같은 상태의 여러 오류는 enum 이름으로 구분한다. 같은 이름의 기존 예시는 보존하며 반복 호출로 누적하지 않는다.
- response `$ref`, 다른 응답 wrapper/schema, `application/problem+json` 같은 기존 미디어 타입, 단일 `example`은 임의 변환하지 않는다. sample 예시를 맞지 않는 schema에 붙이는 것보다 해당 추가를 생략한다.
- 기존 JSON schema 없는 examples도 그 의미를 추측해 바꾸지 않는다. 이 경우 자동 추가가 생략됐다는 사실을 검토 결과에 남기고, 실제 프로젝트 모델 기반의 수정은 승인 범위에서 수행한다.
- 공통 components를 덮어쓰지 않기 위해 샘플은 inline schema를 쓴다. 기존 프로젝트의 component `$ref` 방식이 있다면 유지·재사용하고 실제 schema/example 일치를 테스트한다.
- 어노테이션은 문서화 입력일 뿐 예외 발생이나 권한 검증을 구현하지 않는다. 실제 발생 가능한 오류만 선언한다.
- 예시 timestamp는 고정 값으로 재생성 diff를 안정화한다. 실제 응답 timestamp는 현재 시각이다.

## 언어·프레임워크 대응

Java/Spring에서는 기존 annotation/customizer 및 실제 springdoc 버전을 따른다. Python은 기존 OpenAPI 생성/response model/exception handler를 이용한다. Kotlin용 Config·Controller·Enum을 억지로 복제하지 않는다. 모델의 필드와 오류 의미는 일치해야 한다.

`ErrorAndOpenApiIntegrationTest`는 실제 `/v3/api-docs`를 생성하고 Swagger parser로 읽어 오류가 없는지, endpoint의 HTTP 상태·예시가 실제 ErrorCode와 일치하는지 확인한다. `OpenApiMergeTest`는 응답 보존·중복 실행·foreign schema/ref/media type의 처리 범위를 확인한다. 단순 컴파일만으로 문서 정확성을 주장하지 않는다.
