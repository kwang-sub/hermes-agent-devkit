# 호환성 및 검증 범위

## 고정된 샘플 회귀 기준

`kotlin/pom.xml`은 원본과 비교할 수 있도록 JDK 17, Kotlin 1.9.25, Spring Boot 3.5.3, springdoc-openapi 2.8.8, argon2-jvm 2.11로 고정했다. Hibernate/Jakarta Persistence/Spring Framework 버전은 Boot BOM을 따른다. H2는 테스트에서만 사용한다. OpenAPI 결과 검사는 swagger-parser-v3 2.1.27을 사용한다.

이 버전 목록은 **최신 버전 또는 운영 배포 권장 버전 목록이 아니다.** 샘플 때문에 기존 dependency를 변경하지 않는다. 운영 적용 시 실제 설치 버전, 지원 상태, 보안 공지와 패치 수준을 확인하고 버전 변경은 별도 승인 범위로 다룬다. Boot 2/javax, Boot 4/Jackson 3, WebFlux, 다른 JPA provider 및 Java/Python 구현은 이 모듈의 테스트 결과에 포함되지 않는다.

## 검증과 한계

- CI `Reference sample contracts`: Kotlin 컴파일 + AES/Argon2 + 실제 Hibernate Converter 생성·H2 저장·flush/clear·재조회 + MockMvc + 실제 `/v3/api-docs` 생성/파싱.
- Python `test_reference_samples.py`: 문서·경로·선택적 스킬 연결·샘플 범위의 정적 계약 검사. 실제 에이전트 행동 테스트가 아니다.
- 401/403 샘플은 처리기 호출·직렬화 단위 검사다. 운영 SecurityFilterChain 전체 인증 시나리오를 검증한 것은 아니다.
- Oracle/MSSQL/PostgreSQL 등 실제 운영 DB, 키 저장소/KMS, 키 교체·데이터 migration, 부하·성능, Java/Python 포팅은 프로젝트별 추가 검증이 필요하다.
- 테스트의 임시 AES 키는 실행 때 생성하며 테스트 내부에만 존재한다. 테스트 성공은 운영 키 관리가 완성됐다는 뜻이 아니다.

샘플 POM은 애플리케이션 의존성으로 배포하지 않는다. 루트 updater/Compose/모델 인증/스킬 auto_load 설정과 연결하지 않는다. 공유 디렉터리의 읽기 전용 mount에서는 빌드 산출물을 `/tmp` 또는 승인된 별도 경로로 지정한다.

## 확인한 공식 근거

- Jakarta Persistence 변환 계약: https://jakarta.ee/specifications/persistence/3.2/jakarta-persistence-spec-3.2.html (개념 참고; 샘플의 실제 provider/API 버전은 BOM과 CI 결과 기준)
- Oracle JDK 17 Cipher/GCM: https://docs.oracle.com/en/java/javase/17/docs/api/java.base/javax/crypto/Cipher.html
- Argon2 라이브러리와 배열 정리 예시: https://github.com/phxql/argon2-jvm
- Spring Security 비밀번호 저장: https://docs.spring.io/spring-security/reference/6.5/features/authentication/password-storage.html
- springdoc Boot 호환 표: https://springdoc.org/v2/faq.html
- OpenAPI 응답/미디어 타입/예시 규격: https://spec.openapis.org/oas/v3.1.1.html

CI 성공 여부는 해당 커밋의 run과 artifact를 확인한다. 이 문서 자체를 PASS 증거로 사용하지 않는다.
