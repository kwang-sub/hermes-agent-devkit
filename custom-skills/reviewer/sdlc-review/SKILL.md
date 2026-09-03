---
name: sdlc-review
description: 프로필 경량화 이전에 생성된 기존 Kanban Task의 legacy pinned skill 재개만 지원하는 Reviewer 호환 shim. 신규 Task에서는 사용하지 않는다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [compatibility, legacy, reviewer, kanban]
    related_skills: [dev-code-review]
---

# sdlc-review compatibility shim

이 Skill은 **프로필 경량화 이전에 이미 생성된 Kanban Task가 `sdlc-review`를 pinned skill로 보유한 경우에만** worker 시작 실패를 막기 위한 호환 계층이다.

새로운 Task의 `Applicable Skills` 또는 `task.skills`에는 이 이름을 추가하지 않는다. 신규 리뷰는 `dev-code-review`를 사용한다.

기존 Task를 재개한 경우 즉시 `dev-code-review`를 로드하고 그 실행 계약을 따른다. 이 shim 자체는 별도 review 규칙을 정의하지 않는다.
