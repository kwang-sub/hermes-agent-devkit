# DevKit Kanban 정책

기본 개발은 카드 없이 진행한다. 사용자가 요청한 작업 목표·현재 상태·결정·남은 작업·검증 결과만 선택적으로 기록한다. 기존 데이터는 읽고 참조할 수 있지만 자동 작업 분해·Dispatch·Reviewer 할당·Worker 재개를 실행하지 않는다.

Gateway의 native dispatcher는 환경과 default 설정에서 비활성화한다. 과거 카드의 assignee/status/claim을 단일 프로필로 대량 변경하지 않는다. running/review 기록이 남아 있으면 첫 전환을 차단하고 안전한 정리 판단을 요구한다.

알림 bridge는 선택적 delivery와 자신의 cursor만 관리한다. 이벤트가 completed여도 프로젝트 작업 파일이나 scratch/handoff를 정리하지 않는다. 부모/자식 관계는 표시·기록 용도이며 dependency link를 생성하지 않는다.

카드 조회/기록 실패가 일반 코드 변경·테스트를 중단시키지는 않는다. 단, 기록 자체를 요청받았다면 실패를 명확히 보고한다. 자동으로 카드를 생성하거나 완료했다고 주장하지 않는다.
