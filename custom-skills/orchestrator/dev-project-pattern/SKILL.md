---
name: dev-project-pattern
description: 개발 계획 전에 대상 Repository의 기존 구조·코드·응답·테스트 패턴을 근거로 수집하고 유지해야 할 convention과 적용할 capability skill을 식별한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, pattern, convention, project-analysis]
    related_skills: [dev-breakdown, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-api-docs]
    requires_tools: [terminal]
---

# dev-project-pattern

복잡한 작업에서 `dev-breakdown` 전에 대상 프로젝트의 기존 패턴을 읽어 **새 코드가 현재 프로젝트와 최대한 동일한 방식으로 작성되도록 기준을 만드는 read-only Skill**이다.

상세 공통 규칙은 `/opt/data/shared/references/project-pattern-rules.md`를 따른다.

## 실행 순서

1. managed project의 repository와 현재 workspace를 확인한다.
2. project instruction/AGENTS, build/dependency file, source root를 읽는다.
3. 요청과 가장 유사한 기존 구현을 1~3개 찾는다.
4. 다음 convention을 evidence와 함께 요약한다.
   - package/module 구조
   - naming
   - Controller/API boundary
   - Service/Application layer
   - Repository/Data access
   - Entity/Model/Domain
   - Request/Response DTO
   - 공통 Response/Error 규격
   - Validation/Exception
   - Test framework/style
5. stack/capability를 식별하고 필요한 전문 Skill을 추천한다.
6. 기존 패턴과 사용자의 명시 정책이 충돌하면 조용히 기존 패턴을 따르지 말고 충돌과 최소 변경 방향을 `dev-breakdown`에 전달한다.
7. 개선 필요점은 현재 Task에 필수인지 분리한다. 필수가 아니면 개선 제안으로 남기고 자동 적용하지 않는다.

## Spring/JPA 식별

다음 근거를 통해 Spring/JPA 관련 capability를 식별한다.

```text
Spring Boot plugin/dependency 또는 Spring source annotation
→ dev-spring-guidelines

Controller/Service/DTO/Validation/Exception 기능 변경
→ dev-spring-feature

JPA Entity/Repository/DataJPA/QueryDSL/Converter/Paging 변경
→ dev-spring-data

Spring/JPA 관련 테스트 생성/변경
→ dev-spring-test

OpenAPI/Swagger/Postman 문서화
→ dev-api-docs
```

`dev-tech-dispatch`는 아직 사용하지 않는다. 현재 evidence에서 필요한 Skill만 직접 식별한다.

## 필수 출력

`dev-breakdown`에 다음을 전달한다.

```text
Project Pattern Summary
- Language / Framework / Persistence / Build / Test
- Pattern References
- Package / Naming
- Response Contract
- Error / Validation Contract
- Data Access Convention
- Test Convention
- Applicable Skills
- Pattern Conflicts
- Improvement Candidates (not auto-applied)
```

## 불변식

- source/config를 수정하지 않는다.
- 새 architecture/library/공통 규격을 제안 없이 계획에 확정하지 않는다.
- 기존 패턴을 최신 best practice로 임의 교체하지 않는다.
- evidence가 부족하면 추측하지 않고 `dev-breakdown`의 Open Question으로 남긴다.
