# Lite 공통 Maven·Gradle 검증 헬퍼

기존 Coder의 검증 실행기를 역할 독립 경로로 이관한 복사본이다. Maven/Gradle 엔진과 PASS scope-fingerprint 재사용 래퍼 4개가 포함된다. 경로 변경에 따른 process_execution import와 Maven launcher fingerprint fallback을 보정했다.

Standard 삭제 전에는 기존 경로를 보존하며 사용자를 위한 Lite 검사만 새 경로에서 수행한다. Standard 제거 단계에서 나머지 호출자와 회귀 테스트를 이 경로로 전환한다. 결과가 실패/차단일 때 PASS라고 선언하지 않는다.
