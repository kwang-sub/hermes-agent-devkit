# 암복호화·해싱·JPA 적용 예시

먼저 [ADAPTATION.md](ADAPTATION.md)를 적용한다. 소스 경로는 `kotlin/src/main/kotlin/com/example/samples/crypto/`다.

## 양방향 암복호화

`AesGcmEncryptor`는 암호 연산, `EncryptedStringConverter`는 속성 저장/조회 변환만 담당한다. `SampleConfiguration`은 Spring/Hibernate에서의 주입 연결 예시다. JPA 일반 규격만으로 Spring constructor injection이 보장된다고 가정하지 않는다.

- 기존 암호 서비스·키 주입·암호문 포맷·provider 설정이 있으면 그대로 재사용한다. 새 CryptoUtil을 중복 생성하지 않는다.
- 샘플 envelope는 Base64(version 1바이트 + random IV 12바이트 + ciphertext/tag), AES-256-GCM이다. 태그 검증 실패·잘못된 키·지원하지 않는 버전·잘린 데이터는 실패한다. 평문 fallback이나 오류를 null로 숨기는 처리 금지.
- `@Converter(autoApply=false)`와 해당 필드의 명시적 `@Convert`를 사용한다. 모든 String 자동 암호화 금지. ID/version/연관관계/이미 다른 매핑이 있는 필드에 기계적으로 적용하지 않는다.
- null은 null, 빈 문자열은 별도 값으로 유지한다. 필드 길이는 Base64/IV/tag 오버헤드를 고려한다.
- 같은 값도 매번 다른 IV를 사용하므로 원문 조건의 equality/LIKE/index 검색이 그대로 동작한다고 가정하지 않는다. 검색 설계와 데이터 migration은 별도 판단이며 고정 IV로 해결하지 않는다.
- AAD는 양쪽에서 동일한 값이어야 한다. Converter는 행/tenant 전체 맥락을 알 수 없으므로 row-bound AAD가 필요하면 프로젝트의 서비스 계층 방식을 검토한다.
- 현재 샘플은 key ID/rotation/KMS를 구현하지 않는다. 기존 ciphertext를 샘플 키로 바꿔 읽거나 자동 재암호화하지 않는다.
- 키는 외부에서 필수 주입하며 기본값·실제 키·토큰·개인정보를 소스/문서/로그에 넣지 않는다. JVM String 전체 삭제를 보장하지 않는다.

## Argon2는 명시적인 단방향 처리

`Argon2Hasher.hash(rawChars)`는 신규 원문 저장 경계에서만 호출하고 `matches(storedHash, rawChars)`로 검증한다. Argon2HashConverter는 권장 샘플에 포함하지 않는다. 조회한 해시를 다시 저장할 때 자동 재해시하는 패턴을 복제하지 않는다. 두 함수는 전달된 CharArray를 성공·실패와 관계없이 finally에서 비우며 호출자가 이를 알아야 한다.

기존 PasswordEncoder나 인증 서비스가 있으면 우선 재사용한다. Argon2 인자·네이티브 의존성·리소스 비용은 대상 환경에서 확인한다. 토큰을 해시 저장할지, 어떤 별도 lookup ID로 찾을지도 실제 인증 설계의 일부이며 샘플만으로 정하지 않는다.

## 검증

`CryptoSamplesTest`: Unicode/빈 값, fresh IV, tampering/wrong key/AAD/format/version, 키 검증, null, Argon2 검증·배열 정리.
`JpaConverterTest`: 실제 Hibernate bean 통합, DB ciphertext 확인, flush/clear 후 재조회, 비암호화 필드 변경 뒤 재조회, null→값 갱신.

대상 프로젝트에서는 기존 암호문 fixture, 실제 DBMS/컬럼 길이, rollback 및 실제 등록된 Converter 경로를 추가 검증한다. Python 등에서는 기존 ORM/저장 계층의 같은 경계를 검증하며 JPA를 도입하지 않는다.
