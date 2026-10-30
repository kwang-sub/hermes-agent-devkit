# 프로젝트·언어 적응 원칙

## 우선순위

사용자가 명시적으로 승인한 요구사항 → 대상 프로젝트의 기존 구조·동작 계약 → 대상 언어·프레임워크 관례 → 샘플의 설계 의도 순이다. 안전성 결함이 확인되면 조용히 답습하거나 전면 교체하지 말고 근거·최소 대안·승인 범위를 먼저 확인한다.

## 기존 프로젝트 우선

- 같은 module의 Converter/암호화 서비스, ErrorCode/예외/Handler, 응답 DTO, OpenAPI 설정을 먼저 읽는다. 이미 역할을 수행하면 재사용·부분 보완한다.
- 클래스명, 패키지, DI, 예외 계층, JSON 필드/타입, HTTP 상태, 공통 응답 wrapper, 인증 방식, 암호문 포맷과 키 소스를 샘플에 맞춰 바꾸지 않는다.
- 새로운 공통 클래스·인터페이스·라이브러리를 불필요하게 추가하지 않는다. `ServiceException`이 있으면 `BusinessException`을 새로 만들지 않는다.
- `resultCode/resultMessage` 응답이면 `code/message`로 전환하지 않는다. 기존 `ProblemDetail`을 사용한다면 그 계약을 유지한다.
- 데이터가 있다는 이유만으로 재암호화·DDL·backfill·운영 키 교체를 실행하지 않는다. 각 작업은 별도 합의 범위다.
- 공통 응답·API·암호문 계약이 불명확하면 변경을 멈추고 필요한 결정만 요청한다. 샘플 버전·이름은 프로젝트 표준이 아니다.

## 언어 독립적으로 유지할 것

암호 연산과 영속성 변환의 책임 분리, 단방향 해싱과 복호화의 구분, 오류 식별자/상태/응답의 일관성, 실제 오류와 문서의 일치, null/빈 값 의미, 기존 데이터 호환성, 비밀값 비노출, 실패를 숨기지 않는 검증은 유지한다.

## 언어에 맞게 바꿀 것

| 목적 | Kotlin/Spring 예시 | Java 프로젝트 | Python 등 다른 환경 |
|---|---|---|---|
| 양방향 보호 | `AesGcmEncryptor` | 기존 암호 서비스·Java 암호 API | 기존 검증된 암호 라이브러리·키 관리 계층 |
| 저장값 변환 | JPA `AttributeConverter` | JPA 사용 시 기존 매핑/주입 방식 | 기존 ORM의 변환 확장 지점 또는 명시적 저장 경계 |
| 업무 오류 | enum + `BusinessException` | 기존 enum/interface/exception | 기존 오류 식별 방식·예외·응답 모델 |
| 오류 응답 | Kotlin data class + advice | 기존 DTO·exception handler | 기존 프레임워크의 중앙 예외 처리 |
| 문서 | annotation + `OperationCustomizer` | 실제 springdoc 버전에 맞는 확장 | 기존 OpenAPI 생성/확장 hook |
| 테스트 | JUnit/MockMvc/H2 | 기존 Java 테스트 stack | 기존 Python 테스트·DB fixture |

표의 Java/Python 열은 설계 매핑이며 실행 검증된 코드가 아니다. 예컨대 SQLAlchemy의 변환 타입 또는 Django의 모델 필드를 실제로 사용하는지는 프로젝트 근거를 먼저 확인한다. Kotlin `data class`를 사용했다는 이유로 Java Entity를 record로 만들거나 Python에 Controller/Service/Repository를 일대일 생성하지 않는다.

구현 모양을 억지로 맞추지 않는다. 대상 언어가 함수·데코레이터·데이터 모델을 더 자연스럽게 쓰면 그 방식을 사용한다. **최대한 비슷한 구조란 책임과 동작을 유지한다는 뜻이며 클래스 개수·문법을 복제한다는 뜻이 아니다.**

## 적용 흐름과 증거

1. 현재 프로젝트의 동일 책임 코드와 실제 dependency/version을 제한적으로 확인한다.
2. 그대로 재사용 / 부분 보완 / 신규 구현 중 최소 변경을 선택한다.
3. 해당 영역 레퍼런스와 필요한 샘플 파일만 실제 읽는다. 전체 Kotlin 모듈을 자동 복사하지 않는다.
4. 기존 `dev-session` 승인 정책에 맞춰 변경 직전에 대상·샘플·차이·검증을 공개한다. 논의 중 양식 반복 금지.
5. 승인 범위에서 대상 언어로 구현하고 실제 serialization, persistence, error, OpenAPI를 검증한다.
6. `기존 구현`, `읽은 샘플`, `유지한 계약`, `언어별 변경과 이유`, `실행 검증/미검증`을 보고한다.

스킬 파일을 읽은 사실은 샘플 적용의 정확성이나 대상 언어의 실행 성공을 증명하지 않는다. 테스트가 실패하면 원인을 해결하며 테스트 삭제·보안 가드 우회로 PASS를 만들지 않는다.
