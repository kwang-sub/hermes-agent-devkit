# Shared Custom Skills

`custom-skills/shared`는 `orchestrator`, `coder`, `reviewer`가 공통으로 참조하는 Hermes Custom Skill 원본 디렉터리입니다.

## 관리 원칙

- 역할 전용 Skill은 기존처럼 `custom-skills/orchestrator`, `custom-skills/coder`, `custom-skills/reviewer`에서 관리합니다.
- 둘 이상의 프로필이 동일한 규칙/기능을 사용해야 하면 이 디렉터리에 한 벌만 둡니다.
- 각 프로필은 자신의 역할별 디렉터리와 `/opt/custom-skills/shared`를 함께 `skills.external_dirs`로 참조합니다.
- 동일한 Skill을 역할별 디렉터리에 복제하지 않습니다.
- 기존 Profile local Skill을 공통 Skill로 승격할 때는 원본 내용을 그대로 이관한 뒤, 각 프로필에서 `hermes --profile <profile> skills list`로 노출 여부를 검증합니다.

## `java-project-conventions` 이관

현재 실행 환경에서 `java-project-conventions` 원본은 Orchestrator Profile local 경로에만 존재할 수 있습니다.

```text
/opt/data/profiles/orchestrator/skills/software-development/java-project-conventions
```

원문을 임의로 재작성하지 말고 해당 디렉터리를 DevKit의 아래 위치로 그대로 이관합니다.

```text
custom-skills/shared/java-project-conventions
```

이관 후 `init-profiles.ps1`을 다시 실행하면 세 프로필 모두 동일한 공통 원본을 참조하게 됩니다.
