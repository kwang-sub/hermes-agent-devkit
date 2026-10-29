# JUnit 한글 DisplayName 규칙

Canonical policy: `JUNIT_KOREAN_DISPLAY_NAME_V1`.
Java와 Kotlin의 **새로 작성하거나 이번 변경에서 수정하는 JUnit Jupiter 테스트**에는 한글 `@DisplayName`을 반드시 작성한다. 기존 테스트 이름이 영어여도 이번에 작성·수정하는 테스트의 표시 이름은 한글로 지정한다. 이는 사용자가 명시한 표시 규칙이며 프로젝트의 패키지·클래스 구조·메서드명·테스트 프레임워크를 바꾸라는 뜻이 아니다.

## 적용 범위

- `@Test`, `@ParameterizedTest`, `@RepeatedTest`, `@TestFactory`, `@TestTemplate` 테스트 메서드에 의미 있는 한글 `org.junit.jupiter.api.DisplayName`을 명시한다.
- 새 테스트 클래스와 새 `@Nested` 테스트 클래스에도 한글 표시 이름을 작성한다. 기존 클래스에서는 수정 범위와 함께 보완하되 무관한 파일을 일괄 수정하지 않는다.
- 메서드명은 프로젝트 관례(영문 camelCase, Kotlin 백틱 등)를 유지한다. Kotlin 백틱 한글 메서드명만으로 `@DisplayName`을 생략하지 않는다.
- 이름은 **조건과 기대 결과**를 설명한다. `"테스트 1"`처럼 의미 없는 한글이나 단순 식별자 반복은 피한다. API·클래스명 같은 기술 식별자는 한글 문장 안에 유지할 수 있다.
- 파라미터화·반복 테스트는 한글 `@DisplayName`과 함께 `name = "{displayName} [{index}]"` 또는 `name = "{displayName} [{currentRepetition}/{totalRepetitions}]"` 등 실행별 구분을 제공한다. 매개변수 원문·비밀번호·토큰을 표시 이름에 넣지 않는다.
- 동적 테스트는 팩토리의 `@DisplayName` 외에도 `DynamicTest.dynamicTest("한글 조건과 기대 결과", ...)`의 실행 표시 이름을 한글로 작성한다.
- `@BeforeEach`, `@AfterEach`, fixture/helper 함수는 테스트 케이스가 아니므로 이 규칙 때문에 어노테이션을 붙이지 않는다.
- `@DisplayNameGeneration`이나 프로젝트의 합성 어노테이션만 존재하는 것을 개별 테스트의 한글 `@DisplayName` 확인으로 대신하지 않는다. 신규·수정 케이스에서 명시적으로 확인한다.

## 언어별 적용 예시

아래는 메서드 선언 발췌이며 클래스·fixture·assertion은 대상 프로젝트의 기존 방식을 따른다.

```java
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

@Test
@DisplayName("설정값이 없으면 기본 암호화 방식을 사용한다")
void usesDefaultWhenConfigurationIsMissing() {
    // 기존 fixture를 이용해 기본값을 검증한다.
}
```

```kotlin
import org.junit.jupiter.api.DisplayName
import org.junit.jupiter.api.Test

@Test
@DisplayName("설정값이 없으면 기본 암호화 방식을 사용한다")
fun `uses default when configuration is missing`() {
    // 기존 fixture를 이용해 기본값을 검증한다.
}
```

## 프레임워크 호환성

JUnit Jupiter(5/6)의 실제 의존성을 확인한다. JUnit 4에는 이 어노테이션이 없으므로 **JUnit 4 프로젝트에 Jupiter import만 추가하거나 의존성을 자동 업그레이드하지 않는다.** 미지원 사실과 대안을 보고하고 프레임워크 전환 또는 대체 표시 방식의 명시적 결정을 받는다. 미지원 상태를 규칙 적용 완료로 보고하지 않는다.

Kotest/Spock/Python 등 다른 프레임워크에는 JUnit 어노테이션을 주입하지 않는다. 기존 프레임워크의 이름·설명 방식과 사용자 요구를 확인한다. 운영 로그 메시지 영어 규칙은 그대로 유지하며, 한글 테스트 표시 이름은 운영 로그가 아니다.

## 변경 범위 검증

구현·자체 검토에서 새로 추가하거나 수정한 테스트의 `@DisplayName` 누락, 한글 여부, 조건/기대 결과 설명을 점검한다. 컴파일과 실제 테스트 실행 결과를 따로 기록한다. DevKit의 문서 정적 검사 통과가 사용자의 모든 프로젝트 테스트를 검사하거나 모델의 규칙 준수를 보장하지 않는다.

공식 근거: JUnit Jupiter User Guide의 Display Names / Parameterized Tests / Repeated Tests / Dynamic Tests.
https://docs.junit.org/5.11.1/user-guide/index.html#writing-tests-display-names
