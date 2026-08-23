# dev-breakdown v0.2.0

Orchestrator가 실제 프로젝트 코드와 메타데이터를 Read-only로 분석해 구현 계획을 만드는 Skill입니다.

## 변경점

- 출력 Branch 제안을 `current approved branch 또는 feature/<TASK-KEY>`로 통일
- `READY`와 **사용자 Plan 승인**을 명확히 분리
- `READY` 이후 `dev-workflow-orchestrate`의 Human Gate #2를 거쳐야 Dispatch 가능
- 기존 Evidence-first 분석, 최대 7개 Task, Risk/Test/Block 규칙은 유지
- 문서 한글화

## 핵심

```text
Requirement
→ 실제 코드/테스트/설정 확인
→ Implementation Plan
→ READY/BLOCKED
→ 사용자 Plan 승인
→ dev-workspace-dispatch
```

이 Skill은 Source, Workspace, Branch, Kanban을 변경하지 않습니다.
