# 공통 샘플 카탈로그

샘플은 복사·설치 템플릿이 아니라 책임 분리와 동작 계약을 보여주는 참고 코드다. 기존 프로젝트 구현이 우선이며 동일 책임의 클래스를 중복 생성하지 않는다. 언어가 다르면 대상 언어·프레임워크 관례로 옮기고 해당 환경에서 검증한다.

- [Spring/Kotlin 구현 예시](spring/README.md): JPA 필드 암복호화, 명시적 Argon2 해싱, ErrorCode 기반 오류 응답, OpenAPI 오류 예시 확장.
- [프로젝트·언어 적용 원칙](spring/ADAPTATION.md): Java/Python을 포함한 언어 독립적인 판단 기준.

DevKit 기본 mount 기준 위치는 `/opt/data/shared/references/samples/`다. 공유 mount를 사용자 정의했다면 실제 mount 위치를 사용한다. 추가 마운트·스킬 등록·전체 샘플 자동 로드는 하지 않는다. 스킬의 레퍼런스 안내를 따라 현재 작업에 필요한 파일만 읽는다.
