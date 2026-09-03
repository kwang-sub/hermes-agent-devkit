# Spring OpenAPI Reference

이 reference는 `kwang-sub/backend-lab-archive/level-up-backend-gpt/level2-book-management-system`에서 검증한 SpringDoc/OpenAPI 패턴을 Hermes 작업 중 반복적인 외부 조회 없이 재사용하기 위해 요약한 로컬 기준이다.

이 문서는 대상 프로젝트의 기존 convention을 대체하지 않는다. 실제 프로젝트에 동일 목적의 SpringDoc 설정이 있으면 기존 구현을 먼저 재사용한다.

## Reference Pattern

### Controller documentation

기본 패턴:

```kotlin
@Tag(name = "Book API", description = "도서 관련 API")
@RestController
@RequestMapping("/api/v1/books")
class BookController {

    @Operation(
        summary = "도서 단건 조회",
        description = "ID로 도서 정보를 조회합니다."
    )
    @SwaggerApiErrorCodeExample(
        value = [
            ErrorCode.NOT_FOUND_ENTITY,
            ErrorCode.INTERNAL_SERVER_ERROR,
        ]
    )
    @GetMapping("/{id}")
    fun getBook(...) { ... }
}
```

핵심 의미:

- `@Tag`: API/domain 단위 grouping 설명
- `@Operation`: endpoint summary + description
- API별 error annotation: 실제 발생 가능한 ErrorCode만 선언
- Pageable/condition 등 복합 query object는 프로젝트의 기존 SpringDoc annotation 패턴을 따른다.

Annotation 이름 자체가 프로젝트 표준은 아니다. 이미 비슷한 custom annotation이 있으면 그것을 재사용한다.

## Error Response Example Pattern

Reference 프로젝트는 custom annotation과 `OperationCustomizer`를 사용해 endpoint별 ErrorCode를 HTTP status별 OpenAPI response example로 만든다.

개념 구조:

```text
Controller method
  ↓
@SwaggerApiErrorCodeExample(ErrorCode...)
  ↓
OperationCustomizer
  ↓
ErrorCode들을 HTTP status별 그룹화
  ↓
ErrorResponse example 생성
  ↓
operation.responses에 application/json example 추가
```

새 프로젝트에서 반드시 같은 class 이름을 만들라는 의미가 아니다.

적용 순서:

1. 기존 error code / exception / handler 구조 확인
2. 기존 OpenAPI error example customizer 확인
3. 있으면 재사용
4. 없고 Task가 신규 문서 체계 도입을 승인한 경우에만 reference 패턴을 적용 검토

## GroupedOpenApi Pattern

Reference 프로젝트는 API domain별 `GroupedOpenApi` bean을 사용한다.

예시 개념:

```kotlin
GroupedOpenApi.builder()
    .group("book")
    .pathsToMatch("/api/v1/books/**")
    .packagesToScan("...book...")
    .addOperationCustomizer(customize())
    .build()
```

규칙:

- group 이름, package, path는 대상 프로젝트 구조를 따른다.
- 기존 grouping이 있으면 중복 bean을 만들지 않는다.
- bean 등록 순서가 UI 표시 순서에 영향을 주는 기존 convention이 있다면 유지한다.

## SecurityScheme Pattern

JWT bearer 인증을 실제 프로젝트가 사용할 때만 다음 의미의 scheme을 적용한다.

```text
type = HTTP
scheme = bearer
bearerFormat = JWT
```

기존 auth 방식(API Key, Cookie, OAuth2 등)이 다르면 reference의 bearer 설정을 복사하지 않는다.

## Common Response Contract Override

Reference 프로젝트 Controller는 일부 endpoint에서 다음과 같은 직접 응답 형태를 사용한다.

```text
ResponseEntity<BookResponse>
ResponseEntity<Page<BookSimpleResponse>>
```

**이 형태는 Hermes의 기본 응답 규격으로 복제하지 않는다.**

대상 프로젝트에 공통 응답 wrapper가 있으면 OpenAPI schema/example도 반드시 그 contract를 따른다.

예:

```text
ApiResponse<BookResponse>
CommonResponse<PageResponse<BookResponse>>
BaseResponse<T>
```

우선순위:

```text
대상 프로젝트 Common Response
→ 대상 프로젝트 기존 OpenAPI schema/example
→ 이 reference의 문서화 패턴
```

## Verification Checklist

```text
[ ] 실제 Controller route/method와 문서가 일치
[ ] Request DTO field/validation과 schema가 일치
[ ] 성공 응답이 실제 Common Response contract와 일치
[ ] ErrorCode example이 실제 exception flow와 일치
[ ] 인증 방식이 실제 Security 설정과 일치
[ ] 기존 GroupedOpenApi/customizer 중복 없음
[ ] 새로운 dependency/config 도입이 승인 범위인지 확인
[ ] compile/test 또는 OpenAPI generation 확인
```

## Source Provenance

Reference origin:

```text
Repository: kwang-sub/backend-lab-archive
Module: level-up-backend-gpt/level2-book-management-system
Relevant examples:
- swagger/controller/BookController.kt
- swagger/config/SwaggerConfig.kt
```

외부 reference가 변경되더라도 이 로컬 문서는 자동으로 바뀌지 않는다. 패턴을 의도적으로 갱신할 때만 source를 다시 비교하고 이 reference를 수정한다.
