# 선택적 Kanban 알림

`HERMES_KANBAN_NOTIFY_ENABLED`, platform, target은 기존 `.env` 설정을 따른다. disabled 상태에서는 메시지를 보내지 않는다. 활성화 시 Hermes `send` 경로로 새 이벤트를 전달하며 과거 이벤트를 임의 재전송하지 않는다.

이 bridge는 작업 실행기가 아니다. Task/Board 데이터는 읽기 전용이며 자신의 delivery cursor만 영속화한다. 워커 실행·프로필 변경·claim 복구·프로젝트 파일 삭제는 하지 않는다. 기존 기록의 역할명은 역사적 정보로 표시할 수 있다.

default의 native notifier/auto-subscribe는 중복 발송 방지를 위해 꺼 두고, native dispatcher도 비활성화한다. 알림이 일반 Lite 개발의 필수 조건이 되지 않는다. 정확한 기록 경계는 `lite-kanban-policy.md`를 참고한다.
