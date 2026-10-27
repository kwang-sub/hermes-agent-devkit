---
name: dev-project-pattern
description: Hermes Lite에서 현재 프로젝트의 언어·빌드·도메인·코드·테스트·UI·DB 패턴을 필요한 범위만 조사해 안전한 최소 변경을 돕는다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, lite, project-analysis, patterns, architecture, stack, conventions]
    related_skills: [dev-java-guidelines, dev-kotlin-guidelines, dev-spring-guidelines, dev-frontend-feature, dev-data-feature]
    requires_tools: [terminal]
---

# Lite 프로젝트 패턴 탐색

새 프로젝트 진입 또는 구조·계약을 바꾸는 복잡한 요청일 때 사용한다. 작은 기존 패턴 기반 수정에서는 관련 파일만 확인하고 스킬 전체를 매번 실행하지 않는다. Orchestrator, Managed Project 등록, Kanban, 승인 snapshot, worker dispatch를 전제로 하지 않는다.

## 읽기 전용 조사
1. 사용자가 지정한 현재 프로젝트 경로와 `AGENTS.md`, package/build manifest, 실제 target framework/JDK/DBMS 버전을 확인한다. 데이터나 프로젝트 메타데이터를 쓰지 않는다.
2. affected code와 가장 가까운 기존 implementation/test/config/DTO/repository 등을 제한적으로 확인한다. 대형 repository 전체 scan 대신 좁은 경로와 manifest를 우선한다.
3. 기존 naming, package, validation, error/response, data access, transaction, test, build convention을 근거 파일과 함께 정리한다.
4. Frontend는 현재 화면 구조와 디자인 시스템, 승인 이미지/Figma, component/state/style/breakpoint, Storybook/Playwright 도입 현황을 확인한다.
5. DB는 기존 DBML/ERD/migration, PK/FK/index naming 및 실제 DB vendor/version 근거를 구분한다.
6. 기술 스택 자동 감지가 필요한 경우 기존 읽기 전용 `scripts/detect_capabilities.py`를 사용하되 결과를 truth가 아닌 후보로 해석한다. 프로젝트의 기존 도구·버전 우선, 추가 의존성 자동 설치 금지.
7. 해당 언어·프레임워크의 `/opt/custom-skills/shared` capability만 필요한 때에 로딩한다.

공통 판정 기준: `/opt/data/shared/references/project-pattern-rules.md`, `coding-rules.md`, `implementation-decision-rules.md`, `data-design-rules.md`.

## 산출물
- 변경과 직접 관계된 프로젝트 패턴, 실제 근거 파일, 기술/버전 정보
- 유지할 convention과 충돌·미확정 사항
- 필요한 shared capability 후보 및 최소 수정·테스트 방향
- 추론을 확정된 요구사항으로 전환하지 않으며 프로젝트 전체를 자동 마이그레이션하지 않는다.

복잡한 작업의 계획 요청은 `references/planning.md`를 필요할 때만 읽는다. 프로젝트 등록이나 별도 승인 단계는 만들지 않는다.
