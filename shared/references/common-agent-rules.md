# 공통 개발 기준

실행 정책의 유일한 기준은 루트 `AGENTS.md`와 `shared/AGENTS.common.md`다. default 프로필에서 직접 개발하고 필요한 공통 스킬만 로드한다.

품질: `coding-rules.md`, `project-pattern-rules.md`, `implementation-decision-rules.md`.
데이터: `data-design-rules.md`, `development-contract.md`.
검증: `verification-level-policy.md`, `maven-runtime.md` 및 실제 프로젝트 CI.

모든 변경은 사용자 범위를 따르고 기존 파일·미커밋 수정·환경설정·비밀정보를 보존한다. Git publication/cleanup은 각각 명시적 사용자 요청이 필요하다.
