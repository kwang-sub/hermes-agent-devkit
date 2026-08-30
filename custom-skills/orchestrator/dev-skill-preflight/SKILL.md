---
name: dev-skill-preflight
description: Kanban dispatch 전에 대상 Hermes profile에 실제 존재하는 pinned skill만 선별해 unknown skill worker crash를 차단하는 orchestrator 공통 검증 skill.
version: 1.0.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, kanban, dispatch, skill, preflight, validation]
    related_skills: [dev-workspace-dispatch, dev-workflow-orchestrate, dev-breakdown]
    requires_tools: [terminal]
---

# dev-skill-preflight

Standard/Fast/Review Flow에서 Kanban Task에 `skills`를 pin하기 직전에 재사용하는 공통 검증 계층이다. 계획의 `Applicable Skills`를 실행 가능한 skill 목록으로 오해해 그대로 `kanban_create.skills`에 전달하지 않도록 한다.

## 1. 책임

이 Skill은 다음만 수행한다.

1. 대상 profile의 현재 skill source를 확인한다.
2. 요청된 pinned skill 이름을 exact match로 검증한다.
3. 모든 대상 profile에서 존재하는 skill만 `VALIDATED_SKILLS`로 반환한다.
4. 하나라도 누락된 skill은 `REJECTED_SKILLS`로 반환한다.
5. profile/config 자체를 읽을 수 없으면 fail-closed로 종료한다.

하지 않는 일:

- 어떤 capability가 필요한지 새로 판단하지 않는다.
- 비슷한 이름의 skill을 자동 대체하지 않는다.
- skill을 설치/수정하지 않는다.
- project/source를 분석하지 않는다.
- Kanban Task를 만들거나 dispatch하지 않는다.

## 2. 왜 Coder와 Reviewer를 같이 확인하는가

Standard Flow의 같은 Task가 구현 후 Reviewer로 넘어갈 수 있으므로 Coder에서만 존재하는 pinned skill도 안전하지 않다. Task에 pin할 skill은 기본적으로 `coder`와 `reviewer` 모두에서 사용할 수 있어야 한다.

따라서 Standard Flow 기본 검증 대상은 project metadata의 다음 두 profile이다.

```text
profiles.coder
profiles.reviewer
```

Reviewer를 사용하지 않는 Flow라면 실제 dispatch 대상 profile만 지정할 수 있다.

## 3. Helper 실행

예:

```bash
python3 /opt/custom-skills/orchestrator/dev-skill-preflight/scripts/validate_skills.py \
  --profile coder \
  --profile reviewer \
  --skill dev-spring-data \
  --skill dev-spring-test \
  --skill java-project-conventions
```

예상 출력:

```text
PROFILES=coder,reviewer
REQUESTED_SKILLS=dev-spring-data,dev-spring-test,java-project-conventions
VALIDATED_SKILLS=dev-spring-data,dev-spring-test
REJECTED_SKILLS=java-project-conventions
MISSING_CODER=java-project-conventions
MISSING_REVIEWER=java-project-conventions
STATUS=pass
```

`REJECTED_SKILLS`가 있어도 기본 모드는 성공 종료한다. 이는 capability 후보를 안전하게 제외하고 Flow를 계속하기 위한 동작이다. 해당 이름은 task body의 `Rejected Pinned Skills`에 근거와 함께 남기되 `task.skills`에는 절대 넣지 않는다.

profile config 누락, 파싱 불가 등 preflight 자체가 신뢰할 수 없는 상태이면 exit code 2로 종료하며 Kanban 생성/dispatch를 중단한다.

필수 pinned skill처럼 누락을 즉시 차단해야 하는 호출자는 `--strict`를 사용할 수 있다. 이 경우 rejected skill이 하나라도 있으면 exit code 3이다.

## 4. Dispatch 계약

`dev-workspace-dispatch`는 다음 순서를 지켜야 한다.

```text
Approved Applicable Skills
        ↓
dev-skill-preflight
        ↓
VALIDATED_SKILLS / REJECTED_SKILLS
        ↓
kanban_create.skills = VALIDATED_SKILLS 전체
        ↓
kanban_show로 생성 결과 재검증
        ↓
Dispatch
```

불변식:

- `Applicable Skills`를 `kanban_create.skills`로 직접 복사하지 않는다.
- 배열의 첫 skill만 전달하지 않는다.
- `REJECTED_SKILLS`를 임의 rename/대체하지 않는다.
- `task.skills`는 `VALIDATED_SKILLS`와 정확히 같아야 한다.
- post-create 검증이 다르면 dispatch하지 않는다.
- validated skill이 0개면 `skills=[]`를 허용한다.

`Applicable Skills`는 여전히 Coder가 작업 맥락에서 어떤 capability를 참고해야 하는지 설명하는 canonical handoff다. `task.skills`는 worker 시작 시 Hermes가 강제로 로드할 pinned skill만 의미하며 두 개념을 구분한다.

## 5. 회귀 검증

```bash
python3 custom-skills/orchestrator/dev-skill-preflight/tests/test_validate_skills.py
```

검증 범위:

- Coder/Reviewer 공통 설치 skill만 통과
- 한쪽 profile에만 존재하는 skill 제외
- 존재하지 않는 skill 제외
- strict 모드 차단
- profile-local skill 인식
- profile config 누락 시 fail-closed
