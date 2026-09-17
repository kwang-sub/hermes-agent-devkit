# dev-direct-flow

작고 명확한 mutation request를 Orchestrator가 짧은 승인 절차로 현재 workspace/current branch에 dispatch하는 경로다.

핵심 원칙:

- Orchestrator는 구현하지 않는다.
- Interactive Coder 직접 수정 모드가 아니다.
- Fast Flow를 사용하지 않는다.
- Direct Task도 Kanban → Coder → Reviewer를 거친다.
- API/DB/Infrastructure/architecture/보안·트랜잭션·동시성 정책 변경이나 scope가 불명확한 작업은 Standard Flow로 전환한다.
- Dispatch/model/capability/notification 계약은 `dev-workspace-dispatch`와 기존 공통 정책을 재사용한다.
