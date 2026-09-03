# Shared Custom Skills

`custom-skills/shared`는 `orchestrator`, `coder`, `reviewer`가 공통으로 참조하는 Hermes Custom Skill 원본 디렉터리입니다.

## 관리 원칙

- 역할 전용 Skill은 기존처럼 `custom-skills/orchestrator`, `custom-skills/coder`, `custom-skills/reviewer`에서 관리합니다.
- 둘 이상의 프로필이 동일한 규칙/기능을 사용해야 하면 이 디렉터리에 한 벌만 둡니다.
- 각 프로필은 자신의 역할별 디렉터리와 `/opt/custom-skills/shared`를 함께 `skills.external_dirs`로 참조합니다.
- 동일한 Skill을 역할별 디렉터리에 복제하지 않습니다.
- 공통 규칙은 가능한 한 `/opt/data/shared/references/coding-rules.md`에 두고, 언어/프레임워크 특화 규칙만 capability Skill로 분리합니다.
- 기존 Profile local Skill을 공통으로 승격할 때는 현재 공통 규칙/기존 capability와 중복 여부를 먼저 확인하고, 중복은 합친 뒤 고유 규칙만 canonical shared Skill로 유지합니다.

## Java 공통 가이드

기존 Orchestrator Profile local의 `java-project-conventions`는 DevKit가 관리하는 canonical Skill이 아니었으며 Coder/Reviewer 공통 Skill도 아니었습니다.

Java 관련 공통 정책은 다음 구조로 정리합니다.

```text
shared/references/coding-rules.md
  → 언어 독립 코드 품질 규칙

custom-skills/shared/dev-java-guidelines
  → Java version/build/Lombok/type placement/JavaDoc 등 Java 전용 규칙

custom-skills/shared/dev-spring-*
  → Spring/JPA/API/Test 전용 규칙
```

따라서 새 Task에서는 legacy 이름 `java-project-conventions`를 runtime pinned skill 또는 Applicable Skill로 사용하지 않습니다. Java 프로젝트는 canonical `dev-java-guidelines`를 사용합니다.

기존 local 원본에 위 구조에 아직 반영되지 않은 고유 정책이 발견되면 내용을 그대로 복제하지 않고, 공통 규칙 또는 `dev-java-guidelines` 중 책임이 맞는 위치에 중복 없이 추가합니다.
