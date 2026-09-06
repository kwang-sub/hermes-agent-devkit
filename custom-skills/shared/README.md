# Shared Custom Skills

`custom-skills/shared`는 `orchestrator`, `coder`, `reviewer`가 공통으로 참조하는 Hermes Custom Skill 원본 디렉터리입니다.

## 관리 원칙

- 역할 전용 Skill은 `custom-skills/orchestrator`, `custom-skills/coder`, `custom-skills/reviewer`에서 관리합니다.
- 둘 이상의 프로필이 동일한 규칙/기능을 사용해야 하면 이 디렉터리에 한 벌만 둡니다.
- 각 프로필은 자신의 역할별 디렉터리와 `/opt/custom-skills/shared`를 `skills.external_dirs`로 함께 참조합니다.
- 동일 Skill을 역할별 디렉터리에 복제하지 않습니다.
- 공통 규칙은 `/opt/data/shared/references/coding-rules.md`, `/opt/data/shared/references/implementation-decision-rules.md`에 두고 언어/프레임워크 특화 규칙만 capability Skill로 분리합니다.
- Profile local Hub Skill을 Standard Flow runtime pin 용도로 사용할 때는 coder/reviewer 양쪽 설치 여부를 `dev-skill-preflight`가 검증합니다.

## Canonical capability set

### Backend

```text
dev-java-guidelines
dev-spring-guidelines
dev-spring-feature
dev-spring-data
dev-spring-test
dev-spring-refactor
```

### Frontend

```text
dev-typescript-guidelines
dev-frontend-guidelines
dev-nextjs-feature
dev-frontend-test
dev-ui-ux
```

### Cross-stack

```text
dev-api-contract
dev-api-docs
```

## Public Skill 정책

Public Skill은 범용 전문 지식을 보완하는 용도로 사용할 수 있지만 다음을 지킵니다.

```text
우리 Foundation/Workflow 정책
→ 프로젝트 기존 pattern
→ audited shared adapter/capability
→ Public Skill recommendation
```

- 외부 Skill을 프로젝트 convention보다 우선하지 않습니다.
- Coder 한 profile에만 설치된 Skill을 Standard Flow의 필수 pinned skill로 간주하지 않습니다.
- 외부 plugin이 모든 LLM turn/profile에 전역 영향을 주는 경우 baseline으로 바로 활성화하지 않습니다.
- upstream source/version/license를 확인하고 자동 업데이트보다 review 가능한 pin/update 정책을 사용합니다.
- Claude/Cursor 등 특정 runtime 경로를 전제로 한 Skill은 Hermes에서 그대로 복제하지 않고 adapter를 둡니다.

`dev-ui-ux`는 UI/UX Pro Max의 안정적인 품질 우선순위를 참고한 adapter이며, upstream 전체 search dataset/engine을 vendor하지 않습니다.

## Java legacy 정리

기존 Orchestrator Profile local의 `java-project-conventions`는 canonical Skill이 아니었고 Coder/Reviewer 공통 Skill도 아니었습니다.

Java 관련 공통 정책은 다음 구조를 사용합니다.

```text
shared/references/coding-rules.md
shared/references/implementation-decision-rules.md
custom-skills/shared/dev-java-guidelines
custom-skills/shared/dev-spring-*
```

새 Task에서는 legacy 이름 `java-project-conventions`를 사용하지 않습니다.
