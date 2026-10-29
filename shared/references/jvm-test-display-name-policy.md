# Java·Kotlin JUnit 한글 표시명 정책

Canonical policy: `JVM_KOREAN_DISPLAY_NAME_V1`.

## 적용 범위와 우선순위

Java와 Kotlin에서 새로 작성하거나 동작을 수정하는 JUnit 테스트는 **한글 표시명 필수**다. Spring 사용 여부와 무관하다. 이는 명시적 DevKit 사용자 정책이므로 기존 영어 표시명 관례만을 이유로 생략하지 않는다. 단, 기존 언어/JDK/테스트 엔진, method/class 이름, 패키지, 빌드·실행 명령은 유지한다. 관계없는 기존 테스트를 일괄 이름 변경하지 않는다.

## JUnit Jupiter (JUnit 5/6)

- `org.junit.jupiter.api.DisplayName`을 사용해 신규 테스트 클래스와 `@Nested` 그룹, 신규/변경 테스트 메서드에 `@DisplayName("한글 설명")`을 명시한다. 기존 클래스의 해당 테스트만 수정하는 경우 기존 표시명 일괄 변경은 하지 않는다.
- `@Test`, `@ParameterizedTest`, `@RepeatedTest`, `@TestTemplate`, `@TestFactory` 모두 적용한다. 조건·행위·기대 결과가 드러나는 한글 문장으로 작성하고, "테스트 1" 같은 무의미한 이름은 피한다.
- Java 메서드의 camelCase, Kotlin의 기존 메서드/backtick 규칙은 보존한다. **Kotlin 한글 backtick 메서드명이나 `@DisplayNameGeneration`만으로 명시적 `@DisplayName`을 대신하지 않는다.**
- Parameterized/Repeated 테스트의 개별 실행 표시명은 `name = "{displayName} ..."` 등 해당 엔진이 지원하는 placeholder로 한글 표시명을 포함한다. 기존 식별 정보는 유지하고 password/token/PII를 `{arguments}`로 노출하지 않는다.
- `@TestFactory`에서 생성하는 `DynamicTest` / `DynamicContainer`는 factory 표시명과 별개로 **생성 항목의 표시명도 한글**로 지정한다.
- UTF-8 소스·보고서에서 한글이 보존되는지 현재 프로젝트의 targeted test로 확인한다. 표시명 검사 성공은 실제 테스트 실행 성공을 대신하지 않는다.

### Java 예시

```java
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

@DisplayName("설정값 기본 처리")
class SettingValueTest {
    @Test
    @DisplayName("설정값이 비어 있으면 기본값을 사용한다")
    void usesDefaultWhenEmpty() {
        String configured = "";
        String effective = configured.isEmpty() ? "default" : configured;
        assertEquals("default", effective);
    }
}
```

### Kotlin 예시

```kotlin
import org.junit.jupiter.api.DisplayName
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.assertEquals

@DisplayName("설정값 기본 처리")
class SettingValueTest {
    @Test
    @DisplayName("설정값이 비어 있으면 기본값을 사용한다")
    fun usesDefaultWhenEmpty() {
        val configured = ""
        assertEquals("default", configured.ifEmpty { "default" })
    }
}
```

## 기존 JUnit 4 / 비Jupiter 환경

JUnit 4에는 Jupiter `@DisplayName` 적용을 강제하지 않는다. 지원하지 않는 annotation·의존성을 추가하거나 JUnit 5/6으로 임의 업그레이드하지 않는다. 기존 runner가 지원하는 한글 테스트명 또는 parameterized 표시명으로 의도를 표현하고 **`@DisplayName 미지원: JUnit 4`와 대체 방식**을 결과에 남긴다. 명시적 `@DisplayName` 적용이 반드시 필요한 요구라면 테스트 엔진 변경은 별도 승인 범위다. Kotest 등 다른 엔진도 현재 DSL의 한글 테스트 설명을 사용하며 JUnit annotation을 억지로 붙이지 않는다.

## 자체 검토와 완료 증거

변경한 테스트마다 한글 표시명과 실제 테스트 의미를 확인한다. 누락·영문 전용 표시명은 이 정책의 미충족 사항이며 수정한다. `Test stack`, `Korean display names`, `Unsupported engine / alternative`, `Actual command and result`를 보고한다. 자동 검사가 정적 문구만 확인한 경우 실제 JUnit 실행이나 모델의 정책 준수까지 보장했다고 주장하지 않는다.

표시명은 사용자에게 보여주는 테스트 설명이지 운영 로그가 아니다. 한글 `@DisplayName` 정책과 기존 **코드 운영 로그 영어 작성** 규칙을 혼동하지 않는다.

## 공식 근거

- JUnit Jupiter display names: https://docs.junit.org/5.10.0/user-guide/index.html#writing-tests-display-names
- Parameterized display names: https://docs.junit.org/5.10.0/user-guide/index.html#writing-tests-parameterized-tests-display-names

위 링크는 API 동작 근거이며 프로젝트에 특정 버전을 설치하라는 지시가 아니다.
