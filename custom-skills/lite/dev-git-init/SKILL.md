---
name: dev-git-init
description: Git이 없는 작업공간에 로컬 Git(dev)을 안전하게 초기화하고 Java·Node·Python·IDE .gitignore와 표준 최초 커밋을 승인 범위에서 생성한다.
version: 0.1.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [git, lite, init, workspace, gitignore, java, kotlin, node, python, idea]
    related_skills: [dev-lite-session, dev-project-setup, dev-project-pattern, git-pr-publish]
    requires_tools: [terminal]
---

# dev-git-init — 로컬 작업공간 Git 초기화

사용자가 현재 폴더를 Git으로 관리하거나 초기화해 달라고 요청할 때만 사용한다. JAR, XLSX, ZIP 등 바이너리/문서 산출물을 포함한 일반 작업 공간에서도 사용할 수 있다. GitHub 인증·저장소 생성·remote·push·PR은 범위 밖이다.

## 고정 규격

- 새 로컬 브랜치: dev (git init -b dev). 기존 Git 저장소의 브랜치를 임의 변경하지 않는다.
- 최초 커밋 메시지: chore(init): initialize workspace.
- 기본 .gitignore: 이 스킬의 templates/.gitignore. 운영 컨테이너에서는 /opt/custom-skills/lite/dev-git-init/templates/.gitignore.
- 템플릿: Java/Kotlin, Gradle, Node.js/npm/pnpm/Yarn, Python, IntelliJ IDEA/PyCharm/WebStorm, VS Code, Eclipse, OS 및 대표적인 로컬 비밀정보.
- 기존 프로젝트의 .gitignore 규칙을 우선한다. 원본 파일을 덮어쓰거나 재정렬하지 않고, 필요한 승인된 규칙만 추가한다. 이미 추적하는 파일을 .gitignore 만으로 소급 제외할 수 없다.
- JAR/XLSX/ZIP, Gradle wrapper 및 package-lock.json/pnpm-lock.yaml 같은 lockfile은 일괄 제외하지 않는다. build/, target/, dist/, out/ 등은 산출물인지 확인한 뒤 제외 여부를 결정한다.
- 기본 포맷은 새 Git 저장소만을 위한 시작점이며 모든 프로젝트에 같은 제외 패턴을 강제하지 않는다.

## 실행 전 조사 — 읽기 전용

1. pwd -P 및 사용자가 지정한 대상 경로를 확인한다. 실재하지 않는 경로·작업 디렉터리 밖·권한 없는 위치를 추정하거나 생성하지 않는다.
2. git -C "$WORKSPACE" rev-parse --show-toplevel, git -C "$WORKSPACE" rev-parse --git-common-dir, git -C "$WORKSPACE" status --short로 현재 폴더 또는 상위 디렉터리의 Git 저장소 여부와 Worktree 여부를 확인한다. Git 루트인 경우 중복 초기화하지 않고, 상위 저장소 내부라면 임의로 중첩 저장소를 만들지 않는다.
3. 자식 폴더의 .git 디렉터리/파일, Git 경계를 넘어가는 심볼릭 링크, 기존 .gitignore/AGENTS.md, 크기가 큰 바이너리 및 비밀정보로 의심되는 파일명을 확인한다. nested Git, 외부 경로, 인증·개인정보 파일은 최초 커밋 전에 별도 판단한다. 비밀값 원문을 출력하지 않는다.
4. 초기화 대상 경로, .gitignore 신규/추가 패턴, 추적/제외/보류할 구체적 상대 파일 경로를 미리 제시한다. JAR/XLSX를 최종 결과물인 경우 보존할 수 있게 확인하고 큰 바이너리에는 용량 및 Git LFS 선택지를 설명하되 자동 도입하지 않는다.
5. dev-lite-session의 기존 # 구현 계획 / # 사용 스킬 및 사용자 선택 승인 UI를 사용한다. 계획에는 Git 초기화와 최초 커밋을 각각 명시한다. 사용자가 초기화만 승인했으면 최초 커밋은 하지 않는다. 승인 전에는 init/add/commit이나 .gitignore 파일 쓰기를 하지 않는다.

## 승인 후 실행

1. 직전 확인한 작업 루트와 Git 부재 상태를 재조회한다. 다른 프로세스가 Git을 생성했거나 검토한 파일 목록이 달라졌다면 중단·재확인한다.
2. .gitignore가 없을 때만 템플릿을 복사한다. 이미 있으면 줄바꿈/인코딩/주석/기존 규칙을 보존하며, 승인된 누락 항목만 보강한다. 기존 파일을 포맷하거나 덮어쓰지 않는다. dev-project-setup의 ensure_gitignore.py는 기존 저장소 보안 보강용으로 필요할 때만 사용하며 초기화 전 선행조건이 아니다.
3. git -C "$WORKSPACE" init -b dev 실행. 원격 연결이나 global Git 설정 변경은 하지 않는다.
4. git check-ignore -v, git status --short --untracked-files=all로 실제 포함·제외를 확인한다. 미리 승인한 경로만 git add -- <approved-relative-paths>로 스테이징한다. git add -A 또는 git add . 같은 일괄 추가는 하지 않는다.
5. git diff --cached --name-only, git diff --cached --stat, git diff --cached --check로 실제 staged 파일 목록을 승인된 목록과 비교한다. 비밀정보·예상치 못한 파일·중첩 저장소 등 문제가 있으면 커밋을 중단하고 사용자에게 알린다.
6. 최초 커밋까지 승인됐고 staged 파일이 검증됐을 때만 git -C "$WORKSPACE" commit -m "chore(init): initialize workspace" 실행. Git 작성자 이름/이메일이 없으면 중단한다. global config를 임의 설정하지 않는다.
7. git status --short, git log -1 --format='%h %s', git branch --show-current, git remote -v로 결과 확인. 포함/제외 목록·최초 커밋 SHA·남은 위험·미실행 항목을 보고한다.

## 금지와 경계

- 기존 파일 삭제/강제 변경, reset, restore, stash, clean, 무단 원격 작업, 브랜치 재설정, 다른 Worktree 변경을 하지 않는다.
- 최초 커밋 승인은 remote 추가·GitHub 게시·push·PR·tag 또는 LFS 설치의 승인이 아니다.
- dev-project-setup은 이미 구성된 프로젝트의 설정 준비용, git-pr-publish는 원격 게시용이다. dev-git-init은 신규 **로컬 Git 초기화**만 소유한다.
- 테스트 통과나 Git 초기화만으로 사용자 작업공간의 비밀정보가 전부 보호되었다고 주장하지 않는다.
