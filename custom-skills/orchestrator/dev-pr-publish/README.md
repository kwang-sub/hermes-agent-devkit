# dev-pr-publish

완료된 feature branch 또는 linked worktree를 사용자 승인 기반으로 GitHub에 게시하는 Orchestrator 후처리 Skill입니다.

흐름은 고정입니다.

```text
read-only preflight
→ 커밋 Preview
→ [커밋 승인]
→ commit + push
→ PR Preview
→ [PR 생성 승인]
→ PR 생성
→ STOP
→ 사용자가 GitHub에서 직접 review/merge
```

핵심 정책:

- commit/push 전 변경 파일·diff·commit message를 먼저 확인합니다.
- `커밋 및 Push 승인`은 commit과 정상 push를 하나의 승인으로 묶습니다.
- PR은 push 직후 자동 생성하지 않고 title/body를 다시 보여준 뒤 별도 승인받습니다.
- force push, PR approve/merge, branch 삭제, worktree cleanup은 하지 않습니다.
- 동일 base/head의 open PR이 이미 있으면 중복 생성하지 않습니다.
- 승인 뒤 working tree fingerprint가 달라지면 승인을 무효화하고 다시 Preview합니다.
- Commit message는 `feat: 한국어 설명` 형태의 Conventional Commits 규칙을 사용합니다.

주요 helper:

```text
scripts/prepare_publish.py   # read-only commit preview preflight
scripts/publish_commit.py    # fingerprint 검증 → commit → normal push
scripts/prepare_pr.py        # remote SHA / 중복 PR read-only 검증
scripts/create_pr.py         # 승인된 GitHub PR 생성만 수행
```

회귀 테스트:

```bash
python3 custom-skills/orchestrator/dev-pr-publish/tests/test_pr_publish.py
```
