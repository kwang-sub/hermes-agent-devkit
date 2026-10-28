# Spring OpenAPI Reference

대상 프로젝트의 기존 convention·공통 응답·annotation/customizer가 우선이다. 사용자가 지정한 소스에서 일반화한 샘플은 `/opt/data/shared/references/samples/spring/README.md`에 한 벌로 관리한다. 출처는 `SOURCE.md`, 프로젝트/언어 적용 기준은 `ADAPTATION.md`, 실제 환경 비교는 `compatibility.md`를 읽는다. 외부 저장소를 매 요청마다 조회하거나 원문을 자동 동기화하지 않는다.

## 선택적 샘플 읽기

ErrorCode 기반 문서화가 실제 범위일 때 `openapi.md`와 아래의 필요한 파일만 읽는다. 공통 root의 `kotlin/src/main/kotlin/com/example/samples/` 기준이다.

- `openapi/ApiErrorExamples.kt`: endpoint별 실제 발생 가능한 오류 선언.
- `openapi/ErrorCodeOperationCustomizer.kt`: HTTP status별 예시 생성, 기존 응답 보존.
- `error/ErrorCode.kt`, `ApiErrorResponse.kt`: 문서와 실제 오류 처리 사이의 공통 정의.
- `example/SampleResourceController.kt`: 중립적 사용 예시. 실제 업무 로직으로 복사하지 않는다.

예시의 클래스명·response 필드를 프로젝트 표준으로 강제하지 않는다. Java에는 현재 Java/Spring 버전·관례로, Python 등에는 해당 OpenAPI framework hook과 실제 응답 모델로 같은 목적을 구현한다. Kotlin/Spring 계층을 일대일 복제하지 않는다.

## Reference Pattern

`@Tag`는 실제 API/domain grouping, `@Operation`은 summary/description, `ApiErrorExamples`는 발생 가능한 오류의 선언 예시다. 실제 정의가 없는 오류를 문서에만 추가하지 않는다.

```text
Controller의 오류 선언
→ ErrorCodeOperationCustomizer
→ HTTP 상태별 그룹화
→ 실제 응답 모델과 같은 구조의 예시
→ responses / content / examples
```

## 기존 응답을 보존하는 병합

신규 응답에는 description과 schema를 제공한다. 기존 description, headers, links, schema, examples는 교체하지 않는다. 다른 wrapper/schema, response `$ref`, 단일 example, JSON 이외 representation은 자동 변환하지 않는다. 예시 추가를 생략했으면 그 사실을 보고하고 실제 계약을 확인한다. sample API 응답을 기존 응답으로 오인하지 않는다.

동일 HTTP 상태의 여러 오류는 안정적인 오류 식별자로 구분하고 중복 key를 덮어쓰지 않는다. timestamp 등 문서 예시 값은 고정하여 반복 생성이 불필요한 diff를 만들지 않게 한다. OpenAPI의 example/examples 규칙을 지킨다.

## GroupedOpenApi / SecurityScheme

기존 GroupedOpenApi가 있으면 group·path·package를 재사용한다. 그룹 customizer 등록 방식도 실제 프로젝트에 맞춘다. 샘플에 맞추기 위한 중복 bean이나 전역 security requirement를 추가하지 않는다. JWT bearer scheme은 실제 인증이 JWT일 때만 해당하며 Cookie/API key/OAuth2를 임의 교체하지 않는다.

## Verification Checklist

- 실제 route/method, Request/Response 타입, validation, 공통 wrapper와 문서 일치.
- ErrorCode의 HTTP 상태·코드와 실제 exception/filter 응답 일치.
- 기존 components/schema/headers/links/ref/examples 유지.
- 중복 error code, 멱등성, example/examples 충돌 확인.
- 해당 프로젝트 언어/버전에서 compile/test 및 실제 OpenAPI generation/parser 검증.
- 참조 경로·기존 코드 재사용·차이와 이유·미검증 범위를 기존 승인 계획과 결과에 기록.

샘플의 Kotlin CI 성공이 다른 언어·운영 인증·전체 API 문서 정확성까지 증명하는 것은 아니다.
