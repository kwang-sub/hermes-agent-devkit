# Hermes Agent Devkit — Lite Experiment

이 브랜치는 **Hermes CLI의 default 프로필에서 직접 개발하는 Lite 실행 모드**이다. 신규 작업에 Orchestrator → Kanban → Coder → Reviewer 절차를 강제하지 않는다.

## 핵심 정책

- 사용자 요청을 현재 CLI 세션에서 분석·수정·테스트·반복 개선한다.
- 기존 컨테이너, \`/opt/data\` named volume, OAuth, 모델 설정, 메모리, 세션, Kanban DB를 보존한다.
- Kanban은 명시적 요청 또는 장기 미완료 작업에 대한 사용자 동의가 있을 때만 사용한다. 신규 작업은 자동 카드 생성/위임하지 않는다.
- Standard에서 이미 진행 중인 worker/카드를 임의 점유하거나 상태 전환하지 않는다.
- 기존 개발 스킬은 관련 변경에만 선택 로딩하고 독립 Reviewer/worker gate는 필수가 아니다.
- 프로젝트 관례·사용자 변경·실제 검증을 우선한다. 위험 작업은 승인 후 변경한다.
- 상세 규칙: \`shared/AGENTS.common.md\`. 런타임·개발 스킬 원본: \`custom-skills/shared\`.

## Devkit workspace

- Project ID: \`hermes-agent-devkit\`
- Repository: \`/workspace/hermes-agent-devkit\`
- Container: \`hermes-dev\`
- Expected branch: \`experiment/hermes-lite\`
- Default source of Devkit runtime configuration: \`compose.yml\` / \`update-devkit.ps1\`
- Lite entry: \`updatekit_lite.ps1\` (\`updatekit_lite.sh\` from Git Bash/WSL)
- Standard source branch remains \`dev\`; Standard settings and data are never deleted.

일반 프로젝트 작업 시 별도 \`.hermes/project.yaml\`/Kanban 카드가 없어도 직접 개발할 수 있다. Git과 실제 파일이 현재 상태의 기준이다.
