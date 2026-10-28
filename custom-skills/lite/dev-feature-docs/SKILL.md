---
name: dev-feature-docs
description: Hermes Lite에서 사용자 아이디어와 요구사항을 기능 Markdown 문서로 기록하고 현재 코드·검증 근거로 진행 상태를 판단한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, lite, documentation, planning, feature, requirements]
    related_skills: [dev-lite-session, dev-project-pattern]
    requires_tools: [terminal]
---

# Lite 기능 문서 관리

기존 `docs/features/<descriptive-slug>.md` 기능 문서 체계를 재사용한다. **아이디어 논의는 파일 변경 승인이나 구현 승인에 해당하지 않는다.** 사용자가 문서 생성·수정을 요청하면 해당 범위만 반영한다. Kanban/Orchestrator/Reviewer를 호출하거나 구현을 자동 시작하지 않는다.

## 문서화
- 결정된 요구사항, 검토 중 제안, 미정 사항 및 이번 포함/제외/향후 범위를 구분한다.
- 목표, 사용자 동작·조건·기대 결과, Acceptance Criteria를 기술하되 확인되지 않은 일정·기술·KPI를 생성하지 않는다.
- 기존 문서·사용자 편집을 보존하며 수정 직전 파일을 재조회해 대상 섹션만 부분 변경한다. `docs/features/README.md`는 선택적 링크 목록이며 상태를 중복 저장하지 않는다.
- UI는 `docs/ui/screens/<screen>/screen-spec.md`, API는 실제 API Specification을 참조하여 중복 계약을 만들지 않는다. 템플릿은 `templates/feature.md`, `templates/index.md`를 참고한다.

## 선택적 탐색
명시적 파일 경로 → 이미 확인한 관련 문서 → `docs/features/README.md` → 프로젝트 안 개별 문서 순으로 찾는다. 선택적 읽기 전용 검색:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/find_feature_docs.py" --project-root "<PROJECT_ROOT>" --query "<KEYWORDS>"
```

제목 유사성만으로 임의 연결하지 않으며 프로젝트 바깥으로 탐색하지 않는다. 후보 검색 실패가 일반 구현을 차단하지 않는다.

## 상태와 근거
- `계획 중`: 문서 작성 또는 계획만 수립한 단계
- `진행 중`: 실제 코드 구현 착수를 확인했으나 합의 범위 일부가 남은 단계
- `구현 완료`: 현재 합의 범위 전체에 해당하는 실제 코드·검증 근거가 있는 단계

현재 대화에서 확인한 실제 변경 파일, 검증 명령·결과, 기존 코드만 근거로 사용한다. 카드 생성·승인·단일 테스트 PASS만으로 전체 완료 처리하지 않는다. 근거가 부족하면 상태를 함부로 승격하지 않고 미확인 범위를 설명한다. 구현 결과와 문서 반영 결과를 별개로 보고한다.

세부 안전 기준: `references/document-policy.md`. 정책 참고 출처: `references/sources.md`. 추가 watcher·registry·자동 감시 서비스를 만들지 않는다.

## 검증
```bash
python3 custom-skills/lite/dev-feature-docs/tests/test_find_feature_docs.py
```
