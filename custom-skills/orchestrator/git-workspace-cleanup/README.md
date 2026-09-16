# git-workspace-cleanup

Repository의 linked Git worktree 목록을 보여주고, 사용자가 하나를 선택한 뒤 안전 검증과 승인 범위에 따라 worktree와 작업 branch를 정리하는 Orchestrator Skill입니다.

```text
/git-pr-publish
→ 사용자가 GitHub에서 PR merge
→ /git-workspace-cleanup
→ Worktree 목록
→ Worktree 선택
→ 정리 Preview
→ 삭제 예정 Branch 이름 확인
→ 승인
→ cleanup
```

## 기본 동작

현재 worktree가 feature branch를 checkout 중이면 해당 branch의 merge 상태를 검증해 worktree + local branch, 선택 시 remote branch까지 정리합니다.

PR merge 후 worktree가 이미 `dev`/`main` 같은 base branch로 전환된 경우에는 base branch를 삭제하지 않습니다. 대신 worktree HEAD reflog의 최근 checkout 기록에서 이전 작업 branch를 추적합니다.

예:

```text
checkout: moving from feature/ui-dashboard-investment to dev
```

추적된 branch가 실제 local ref로 존재하고, 다른 worktree에서 사용되지 않으며, open PR이 없고, `origin/dev` 등에 완전히 merge되었다는 evidence가 확인되면 삭제 후보로 표시합니다.

## Preview / 승인

```text
[Worktree 정리 Preview]
Worktree: ui-dashboard-investment
Current Branch: dev
Tracked Previous Branch: feature/ui-dashboard-investment
Tracked Merge Evidence: git-ancestor

삭제 예정:
- Worktree: ui-dashboard-investment
- Local Branch: feature/ui-dashboard-investment
- Remote Branch: origin/feature/ui-dashboard-investment

보존:
- dev
- origin/dev
```

승인 선택지는 다음과 같습니다.

```text
- Worktree + 추적 로컬/원격 Branch 정리
- Worktree + 추적 로컬 Branch만 정리
- Worktree만 정리
- 취소
```

삭제될 branch 이름은 mutation 전에 반드시 Preview/Gate에 표시합니다. reflog 후보가 없거나 merge/open PR/다른 worktree 사용 여부를 안전하게 증명할 수 없으면 branch 삭제는 제공하지 않고 worktree-only 정리만 허용합니다.

## 안전 정책

- primary worktree 삭제 금지
- dirty/untracked worktree cleanup 금지
- open PR branch 삭제 금지
- base branch local/remote 삭제 금지
- `git worktree remove --force`, `git branch -D`, force push, reset/restore/clean/stash 금지
- local branch 삭제는 승인된 exact SHA를 사용하는 `git update-ref -d`만 사용
- remote branch 삭제 직전 `git ls-remote` SHA 재검증
- global `safe.directory` 자동 변경 금지

## Helper

```text
scripts/list_worktrees.py      # linked worktree 목록
scripts/prepare_cleanup.py     # read-only cleanup / previous branch preflight
scripts/cleanup_workspace.py   # 승인된 범위 mutation
scripts/worktree_only.py       # base worktree + 이전 작업 branch 추적
```

회귀 테스트:

```bash
python3 custom-skills/orchestrator/git-workspace-cleanup/tests/test_workspace_cleanup.py
python3 custom-skills/orchestrator/git-workspace-cleanup/tests/test_tracked_branch_cleanup.py
python3 scripts/check_workspace_cleanup_contract.py
```
