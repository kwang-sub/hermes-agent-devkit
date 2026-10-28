# JPA Converter 참고 코드 적용

Converter/암복호화가 실제 작업 범위일 때만 읽는다. 기존 프로젝트의 동일 구현과 저장값 계약이 먼저다. 일반 조회 작업에 암호화 샘플을 자동 도입하지 않는다.

공통 샘플 root: `/opt/data/shared/references/samples/spring/` (공유 mount를 변경했다면 실제 root 사용).

1. `ADAPTATION.md`로 기존 구성 우선·다른 언어로의 책임 중심 재구현 규칙 확인.
2. `compatibility.md`로 실제 대상 JPA/Hibernate/Spring/언어 버전과 비교.
3. `crypto-jpa.md`와 필요한 소스만 읽기: `kotlin/src/main/kotlin/com/example/samples/crypto/EncryptedStringConverter.kt`, `AesGcmEncryptor.kt`. 연결 방식이 필요할 때만 `example/SampleConfiguration.kt`와 JPA 테스트 읽기.
4. 해싱 요청이면 `Argon2Hasher.kt`의 명시적 저장/검증 경계를 참고. Argon2HashConverter를 자동 생성하지 않는다.

기존 CryptoUtil/Converter가 있으면 새 예제 클래스보다 재사용을 우선한다. Kotlin 예제를 Java로 직역하거나 Python에 JPA 계층을 복제하지 않는다. 실제 언어/ORM의 idiom에 맞추고 null·암호문·오류·주입 계약을 검증한다.

샘플은 자동 설치 템플릿이 아니다. 기본 키나 토큰을 추가하지 않고, autoApply 전체 적용·평문 fallback·고정 IV·자동 재암호화는 금지한다. 실제 읽은 샘플 경로, 유지할 기존 계약, 달라지는 부분과 이유, 테스트를 기존 승인 계획에 포함한다. 독립 승인 gate는 추가하지 않는다.
