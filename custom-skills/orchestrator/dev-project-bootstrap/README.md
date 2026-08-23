# dev-project-bootstrap v0.2.1

기존 Git Repository를 Hermes Managed Project로 idempotent하게 등록하는 Skill입니다.

## 유지되는 핵심 정책

- Project / Board / Profile Binding ensure
- `AGENTS.common.md` Managed Block 병합
- `.hermes/project.yaml` Core Metadata 관리
- Resolver는 Skeleton만 생성하고 값은 **사용자 직접 관리**
- 기존 Resolver / Jira / Custom Metadata 보존
- Application Source 수정 금지
- 초기 Commit이 없으면 임의 Commit하지 않고 중단

## 신규 프로젝트 기본 Resolver

```yaml
resolver:
  aliases: []
  modules: []
  files: []
  paths: []
```

## 실행

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap_project.py" \
  --repo /workspace/dashboard
```

이번 버전은 문서 한글화와 Workflow 승인 경계 설명만 추가했으며 Bootstrap Core 로직은 변경하지 않았습니다.
