# 승인 화면과 테스트 표시 이름

## 계획 출력: Hermes 기본 답변과 동일한 경로

변경 계획은 Clarify 호출 직전의 interim assistant message로 도착할 수 있다. 이전 CLI의 agent setup은 interim callback을 연결하지 않아 이 메시지가 `_emit_print` / status 출력으로 흘렀고, 일반 답변의 테마·Markdown·테두리가 적용되지 않았다.

`devkit_approval_presentation`은 `구현 계획`과 `사용 스킬`이 순서대로 있는 계획 본문만 기본 채팅 표시 방식으로 연결한다. 코드 블록 안의 양식 예시나 일반 진행 메시지는 변환하지 않는다.

- Classic: 현재 skin의 response label / response_border / banner_text와 native Rich Panel을 사용한다.
- Modern: native answer_label / closing_separator와 동일 본문 렌더러를 사용한다.
- Markdown render/strip/raw 설정과 밝은 화면 색상 매핑을 유지한다. 새 고정 흰색/노란색 팔레트를 만들지 않는다.
- 이미 로컬에서 스트리밍으로 표시한 본문은 중복 출력하지 않는다. 일반 상태 메시지와 headless 단일 질의는 기존 경로를 유지한다.
- 승인 선택 화면도 실제 native 행과 입력 조작을 유지하면서 승인용 질문에 한해 같은 테마 색상을 사용한다. 일반 Clarify의 색상·내용·동작은 변경하지 않는다.
- 작업 진행/보류/추가 요구사항, 즉시 입력, Esc, 입력 출처 검증은 PR197의 기존 규칙 그대로다. 출력 개선은 승인이나 쓰기 권한을 부여하지 않는다.

기존 이미지에 파일만 추가해도 설치되는 기능은 아니다. 병합 후 `update-devkit.ps1`로 이미지를 갱신하고 새 Hermes 세션에서 확인한다. 컨테이너/볼륨/인증을 수동 초기화하지 않는다.

## Java/Kotlin 테스트 이름

Canonical: `shared/references/junit-display-name-policy.md`의 `JUNIT_KOREAN_DISPLAY_NAME_V1`.
새로 작성하거나 수정하는 JUnit Jupiter 테스트에 한글 `@DisplayName`을 반드시 작성한다. Java/Kotlin 언어 스킬, Spring 테스트 스킬, Lite 자체 리뷰에서 같은 공통 기준 문서를 참조한다. 메서드명은 기존 관례를 유지하며 운영 로그 영어 규칙은 그대로다.

공통 Kotlin 레퍼런스의 기존 테스트 22개와 테스트 클래스 4개에도 조건·기대 결과를 설명하는 한글 표시 이름을 붙였다. 실제 검증 코드는 바꾸지 않는다. JUnit 4 등 미지원 프레임워크를 자동 업그레이드하지 않으며, 무관한 사용자 프로젝트 테스트를 일괄 수정하지 않는다.

## 검증 범위

- 정적/순수 Python 검사: 본문 구분, patch idempotence/anchor fail-closed, 선택 UI 테마 범위, 스킬 연결 및 샘플의 한글 이름.
- Native 검사: upstream 실제 렌더러/agent setup/Clarify 메서드를 추출하여 실행. Classic/Modern × render/strip/raw에서 정상 답변과 계획 본문의 실제 console 출력을 비교한다. 테마/밝은 모드/무색 출력/중복 방지도 확인한다.
- 별도 CI에서 기존 native 승인 테스트를 함께 실행하고, 실제 Kotlin 샘플 컴파일/테스트와 Windows updater/마운트 회귀, 최신 이미지 통합 검증을 수행한다.

모델·전체 Gateway 서버·Windows Terminal IME를 실행한 end-to-end 검증과는 다르다. 정적 규칙 검사만으로 모든 모델 응답이 한글 DisplayName을 준수한다고 주장하지 않는다. 기존 출력 설정/승인/데이터 보존 경계는 그대로다.
