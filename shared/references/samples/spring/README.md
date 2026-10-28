# 공통 Spring 패턴 샘플

사용자가 지정한 기존 Kotlin 코드에서 업무 이름과 개인 설정을 제거하고 일반화한 예시다. **대상 프로젝트의 기존 구성·명명·응답·저장값 계약이 샘플보다 우선한다.** 기존 코드가 충분하면 샘플을 복사하지 않는다. 이 모듈은 애플리케이션 라이브러리나 강제 프로젝트 템플릿이 아니다.

## 먼저 읽을 문서

1. [ADAPTATION.md](ADAPTATION.md): 프로젝트 우선, 언어별 재구현, 범위·승인 기준.
2. [compatibility.md](compatibility.md): 검증 기준 버전과 지원하지 않는 가정.
3. 필요한 영역만 [crypto-jpa.md](crypto-jpa.md), [error-handling.md](error-handling.md), [openapi.md](openapi.md).
4. [SOURCE.md](SOURCE.md): 원본 저장소·고정 커밋과 의도적인 변경 목록.

## 코드 위치

실제 코드는 `kotlin/src/main/kotlin/com/example/samples/` 아래에 한 벌만 보관한다.

| 영역 | 코드 | 담당 스킬 |
|---|---|---|
| crypto | `AesGcmEncryptor`, `EncryptedStringConverter`, `Argon2Hasher` | `dev-spring-data`, `dev-spring-test` |
| error | `ErrorCode`, `BusinessException`, `ApiErrorResponse`, `FieldViolation`, `GlobalExceptionHandler` | `dev-spring-feature` |
| security | `ApiAuthenticationEntryPoint`, `ApiAccessDeniedHandler` | 기존 인증/인가 구성이 관련될 때만 |
| openapi | `ApiErrorExamples`, `ErrorCodeOperationCustomizer` | `dev-api-docs` |
| example | `SampleConfiguration`, `SampleResourceController` | 연결 방법 확인용; 실제 업무에 복사 금지 |

Kotlin은 한 구현 예시다. Java에는 기존 Java/Spring 구조로, Python에는 기존 웹 프레임워크·ORM·모델 규칙으로 같은 책임과 동작을 재구현한다. Python에 JPA/Spring 계층을 강제하지 않는다. 별도 Java/Python 실행 샘플은 아직 없으며 검증됐다고 표시하지 않는다.

## 선택적 검증

DevKit는 이를 자동 설치·실행하지 않는다. CI 또는 승인된 임시 검증 공간에서만 실행한다. `pom.xml`은 이 샘플의 고정 회귀 기준이며 대상 프로젝트의 의존성 파일을 교체하는 근거가 아니다.

```bash
mvn --batch-mode -f shared/references/samples/spring/kotlin/pom.xml \
  -Dmaven.repo.local=/tmp/devkit-sample-m2 \
  -Dsample.build.directory=/tmp/devkit-sample-target verify
```

샘플 CI는 실제 Kotlin 컴파일, AES/Argon2, H2/Hibernate 저장·재조회, MockMvc 오류 응답, 생성된 `/v3/api-docs` 파싱과 응답 예시 검증을 수행한다. 보고서는 `reference-sample-evidence` artifact다. 경로/지침 정합성은 별도 Python 정적 테스트로 확인하며 둘을 혼동하지 않는다. 운영 DB·실제 키·사용자 설정을 읽지 않는다.

## 적용 전 기록

기존 승인 포맷의 `사용 스킬` 안에 읽은 샘플 경로, 재사용할 기존 파일, 다른 점과 이유, 대상 언어·버전의 실제 검증 방법을 기록한다. 새로운 승인 절차를 추가하거나 모든 레퍼런스를 한 번에 읽지 않는다. 샘플을 조회하는 것과 대상 파일을 변경하는 것은 별개의 동작이다.
