---
name: dev-project-setup
description: 선택한 프로젝트의 JVM toolchain·Gitignore·설정 보안을 필요 시 준비한다. 역할 프로필·Kanban 등록은 하지 않는다.
version: 1.0.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, lite]
    related_skills: [dev-project-pattern, dev-java-guidelines, dev-node-dependencies]
    requires_tools: [terminal]
---

# dev-project-setup

이 스킬은 사용자가 개발 환경 준비를 요청하거나 실제 빌드 설정 부재를 확인했을 때만 사용한다. 프로젝트 등록, 전체 작업장 탐색, AGENTS 덮어쓰기, 패키지 템플릿 강제 적용은 하지 않는다.

## 준비 절차
1. 명시한 프로젝트와 실제 build manifest, JDK target/runtime을 확인한다. 기존 변경을 보존한다.
2. 읽기 전용 확인은 `scripts/bootstrap_preflight.py --help`의 옵션과 프로젝트 구조를 따라 수행한다. 이름에 bootstrap이 남아 있지만 이 helper는 프로젝트·프로필·보드를 등록하지 않는다.
3. `.hermes/toolchain.env` 작성이 필요한 경우 변경을 설명하고 요청 범위에서 `scripts/ensure_workspace_toolchain.py --workspace <path>`를 실행한다. 다른 worktree에 메타데이터를 쓰지 않는다.
4. `.gitignore`·`.gitattributes`·환경설정 수정은 명시된 준비 요청 범위 안에서만 수행한다. `ensure_gitignore.py`, `ensure_config_security.py`의 안전한 부분 갱신을 사용하고 기존 secret을 출력하지 않는다. 기존 `.env.example` 및 사용자 규칙은 덮어쓰지 않는다.
5. 이미 준비된 프로젝트에서는 반복적인 전체 scan이나 등록 절차를 요구하지 않는다.
6. Git을 사용하지 않는 폴더의 초기화·최초 커밋 요청은 `dev-git-init`으로 구분한다. 이 환경 준비 스킬은 `git init`을 자동 실행하거나 최초 커밋을 만들지 않는다.

검증: 이 디렉터리의 `tests/` 및 공통 Maven·Gradle launcher 테스트. 실제 source/test 실행은 기존 `hermes-java`/`hermes-maven` 계약을 유지한다.
