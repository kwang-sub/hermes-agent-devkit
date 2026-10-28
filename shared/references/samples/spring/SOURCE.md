# 샘플 출처와 의도적 변경

사용자가 지정한 원본: `kwang-sub/level-up-backend-gpt`
기준 브랜치: `dev`의 추출 시점 고정 커밋 `432b29df219783eac8cfad4aa1f0ca46bc9c4fa6`
모듈 경로: `level2-book-management-system/src/main/kotlin/org/example/level2bookmanagementsystem/`

원문 13개를 별도 추출해 blob SHA 일치를 확인한 자료를 바탕으로 일반화했다. 아래 코드는 원문과 바이트 동일하지 않으며 명명·동작·검증 보완이 포함된 DevKit 샘플이다. 원본 저장소는 수정하지 않았다. 원문 계정·연락처·서비스 정보·설정 비밀값은 복사하지 않았다. 별도의 제3자 라이선스나 모든 용도의 재배포 권한을 이 문서에서 부여하지 않는다.

| 원본 (위 모듈 기준) | 샘플 대응 |
|---|---|
| `security/util/CryptoUtil.kt` | `crypto/AesGcmEncryptor.kt`, `crypto/Argon2Hasher.kt` |
| `security/converter/AesGcmEncryptConverter.kt` | `crypto/EncryptedStringConverter.kt` |
| `security/converter/Argon2HashConverter.kt` | 직접 채택하지 않음; 명시적 Argon2Hasher 경계로 변경 |
| `swagger/constant/ErrorCode.kt` | `error/ErrorCode.kt` |
| `swagger/exception/CustomBadRequestException.kt`, `EntityNotFoundException.kt` | `error/BusinessException.kt`와 ErrorCode |
| `base/dto/response/ErrorResponse.kt`, `ErrorDetailResponse.kt` | `error/ApiErrorResponse.kt`, `FieldViolation.kt` |
| `swagger/controller/advice/GlobalExceptionHandler.kt` | `error/GlobalExceptionHandler.kt` |
| `security/core/CustomAuthenticationEntryPoint.kt`, `CustomAccessDeniedHandler.kt` | `security/ApiAuthenticationEntryPoint.kt`, `ApiAccessDeniedHandler.kt` |
| `swagger/config/SwaggerConfig.kt` | `openapi/ApiErrorExamples.kt`, `ErrorCodeOperationCustomizer.kt`, `example/SampleConfiguration.kt` |
| `swagger/controller/BookController.kt` | `example/SampleResourceController.kt` (업무 동작 제거) |

원본 링크 기준: https://github.com/kwang-sub/level-up-backend-gpt/tree/432b29df219783eac8cfad4aa1f0ca46bc9c4fa6/level2-book-management-system

주요 원문 blob SHA: CryptoUtil `46b792722c5ab068adc4f33124f3e501761a463b`, AesGcmEncryptConverter `9ca63d01e79f9b68ffa2bdab9925908b68ad004a`, Argon2HashConverter `2aa78703ddfc59503f0f3fdf326576867a7ed821`, ErrorCode `b53ce7417c7f4781e5977d060c57ec6b2f35c7e2`, SwaggerConfig `5b9dfb96a27e166c1c57d7a21c2b9c16653d36d3`.

## 원문과 달라진 부분

- 도서·대출·토큰 등 업무 이름을 중립적인 예제 이름으로 변경하고 패키지를 `com.example.samples`로 분리.
- AES와 Argon2 책임 분리, Argon2HashConverter 제외, 예외 경로에서도 CharArray를 finally에서 정리.
- 암호문 최소 길이·버전·무결성 실패를 안전한 오류로 처리. 암호 키의 기본값/실제 값 없음.
- 오류 코드 중복과 HTTP 상태 불일치 제거. 명시적인 업무 예외 및 framework 오류 상태 보존.
- validation/JSON 오류에서 rejected value와 내부 예외 메시지 노출 제거.
- OpenAPI description/schema 보강, 기존 응답을 교체하지 않는 제한적 병합, 고정 timestamp 및 안정적인 예시 식별자.
- 별도 컴파일 가능한 검증용 모듈과 실제 persistence/API/OpenAPI 테스트 추가.

기존 시스템에 이 변경을 자동 적용하지 않는다. 원본 암호문/오류 계약에 대한 무조건적 호환성을 보장하지 않으며 기존 데이터 fixture와 실제 클라이언트 기준으로 따로 검증한다.
