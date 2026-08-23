# dev-work-intake v0.1.3

Jira Cloud Issue를 Read-only로 조회해 Source-independent Work Item으로 정규화하는 Orchestrator Skill입니다.

## 현재 지원

```text
Jira Cloud ✅
Text        → dev-workflow-orchestrate에서 직접 처리
Notion      미래 Adapter
Slack       미래 Adapter
```

## 설정 우선순위

```text
Docker Compose .env
→ Container Environment
→ optional /opt/data/profiles/orchestrator/.env fallback
```

## 연결 확인

```bash
python3 "${HERMES_SKILL_DIR}/scripts/jira_intake.py" --check
```

## Issue 정규화

```bash
python3 "${HERMES_SKILL_DIR}/scripts/jira_intake.py" --issue DSB-39
```

Jira Project Key는 Repository 결정값이 아니라 Project Hint입니다. 실제 Project는 `dev-project-resolve`가 Managed Metadata에서 후보를 찾고, 사용자가 승인합니다.

이번 버전은 문서/Workflow 계약 한글화이며 Jira 조회 Script의 핵심 로직은 변경하지 않았습니다.
