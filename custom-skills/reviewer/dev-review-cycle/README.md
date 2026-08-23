# dev-review-cycle v0.1.1

Coder와 Reviewer가 동일 Kanban Card와 동일 Worktree에서 수정/재검토를 반복하기 위한 공통 프로토콜입니다.

```text
coder → request_review → reviewer
                         ├─ request_changes → coder
                         └─ approved → done
```

Git/PR 단계가 아직 없으므로 승인 후에도 Worktree는 유지합니다.
