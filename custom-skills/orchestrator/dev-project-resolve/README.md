# dev-project-resolve v0.2.1

Normalized Work Item을 **`.hermes/project.yaml`이 있는 Managed Project만** 대상으로 Resolve합니다.

## 핵심 정책

```text
/workspace 전체 Source Scan ❌
Unmanaged Repository 탐색 ❌
.worktrees 탐색 ❌

/workspace/*/.hermes/project.yaml ✅
```

그리고 이번 Workflow 계약상:

```text
RESOLVED_SINGLE / RESOLVED_MULTI
→ Project Candidate
→ 사용자 승인 필수
→ 그 다음 dev-breakdown
```

사용자가 처음부터 정확한 Managed Project를 직접 지정한 경우에는 Resolver를 생략할 수 있습니다.

Project Key(`DSB` 등)는 단독 Repository 결정 근거가 아닙니다.
