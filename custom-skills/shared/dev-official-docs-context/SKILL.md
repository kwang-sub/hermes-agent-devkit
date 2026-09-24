---
name: dev-official-docs-context
description: 외부 library/framework/SDK/API 작업에서 프로젝트의 실제 설치 버전을 먼저 확정하고 Context7 공식 문서, 공식 upstream source, 설치된 local types/source를 계층적으로 확인해 version-aware 구현 evidence를 만드는 공통 capability skill.
version: 0.1.2
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, docs, context7, official-docs, version, sdk, api, dependency, compatibility]
    related_skills: [dev-frontend-feature, dev-nextjs-feature, dev-typescript-guidelines, dev-node-dependencies, dev-spring-feature, dev-spring-guidelines, dev-api-contract]
    requires_tools: [terminal]
---

# dev-official-docs-context

외부 기술의 API·설정·타입·버전 호환성을 기억이나 임의 예제로 결정하지 않고 **현재 프로젝트의 실제 버전과 공식 evidence**로 결정하는 공통 capability다. Context7은 공식 문서 retrieval provider이며 compiler/typecheck/test/build를 대체하지 않는다.

## Evidence 우선순위

```text
사용자 / Task 명시 정책
→ 대상 프로젝트의 실제 설치·resolved version
→ 해당 version의 공식 문서(Context7 우선)
→ 공식 upstream repository / release note / source
→ 설치된 package의 local source / type declaration
→ compiler / typecheck / test / build 결과
```

문서가 맞아도 현재 설치 조합이 compile되지 않으면 완료로 간주하지 않는다. 반대로 compiler 오류를 감추기 위해 문서 evidence 없이 버전·strictness를 임의 변경하지 않는다.

## Documentation Required Gate

다음이면 구현 전에 이 Skill을 적용한다.

```text
외부 SDK/library 신규 도입 또는 사용 API 추가
외부 API/인증/OAuth/Supabase/Firebase 등 연동
framework/library의 version-sensitive API 또는 config 변경
library/framework major/minor upgrade
Deprecated API 교체
외부 dependency의 .d.ts / compiler compatibility 오류
Coder가 외부 API signature 또는 현재 version 동작에 확신이 없음
```

다음만 있는 Task에서는 기계적으로 호출하지 않는다.

```text
순수 domain/business logic
프로젝트 내부 DTO/mapper/service 변경
외부 API surface를 건드리지 않는 단순 refactor
이미 검증된 기존 project pattern의 반복 구현
```

내부 Gate이며 사용자 승인 질문을 새로 만들지 않는다.

```text
DOCUMENTATION_REQUIRED=yes|no
DOCUMENTATION_READY=pass|partial|blocked
```

Context7 장애만으로 즉시 `blocked`로 만들지 않는다. 공식 upstream 또는 local types/source로 충분히 증명 가능하면 `partial` 또는 `pass`로 진행한다.

## 1. Version First

문서 조회 전에 실제 project evidence로 version을 확정한다.

Node package는 helper를 우선 사용한다.

```bash
python3 /opt/custom-skills/shared/dev-official-docs-context/scripts/detect_dependency_versions.py \
  --workspace "<Task Workspace>" \
  [--package-root "<relative package root>"] \
  --package "next" \
  --package "typescript" \
  --package "@supabase/supabase-js"
```

여러 `package.json`이 있고 하나로 확정할 수 없으면 임의 root를 선택하지 않고 `--package-root`를 명시한다.

JVM/Spring은 현재 project의 Gradle/Maven dependency evidence, wrapper/JDK, plugin/BOM version을 우선한다. version을 추측해 최신 공식 문서를 현재 project 문서로 취급하지 않는다.

Version source 예:

```text
package-lock resolved version
pnpm/yarn/bun canonical lock evidence
package.json exact declaration
Gradle dependency/BOM/plugin
Maven dependencyManagement/plugin
installed local package metadata
```

## 2. Context7 Hosted MCP Provider

Context7 문서는 REST API를 직접 호출하지 않고 공식 Hosted MCP endpoint를 사용한다.

```text
Endpoint: https://mcp.context7.com/mcp
Transport: Streamable HTTP
Default auth: anonymous
Allowed tools:
- resolve-library-id
- query-docs
```

익명 access가 정상 기본값이며 `CONTEXT7_API_KEY`는 **필수값이 아니다**. 값이 있는 경우에만 higher rate limit용 Bearer header를 사용한다. 값이 비어 있으면 Authorization header 자체를 보내지 않는다.

DevKit helper는 Hermes runtime에 이미 포함된 MCP Python SDK를 사용하므로 Context7 조회를 위해 `npx`, npm global package, pip package를 설치하지 않는다.

### Library resolve

```bash
/opt/hermes/.venv/bin/python \
  /opt/custom-skills/shared/dev-official-docs-context/scripts/context7_docs.py resolve \
  --library "Next.js" \
  --version "16.3.5" \
  --query "production build TypeScript generated route types"
```

내부적으로 Hosted MCP의 `resolve-library-id`를 다음 contract로 호출한다.

```text
libraryName: <library name>
query: <single focused concept>
```

resolve 결과에서 공식/primary package를 우선한다. 결과의 library ID, available version, source reputation, benchmark score를 evidence로 사용한다. 정확한 version ID가 있으면 `/org/project/version`을 선택한다.

### Documentation query

```bash
/opt/hermes/.venv/bin/python \
  /opt/custom-skills/shared/dev-official-docs-context/scripts/context7_docs.py query \
  --library-id "/vercel/next.js/v16.3.5" \
  --query "production build TypeScript generated route types"
```

내부적으로 Hosted MCP의 `query-docs`를 다음 contract로 호출한다.

```text
libraryId: /org/project[/version]
query: <single focused concept>
```

한 질문/기술에 문서 query는 최대 3회로 제한하고 한 호출은 한 concept에 집중한다.

Context7 query에는 public 기술 정보만 보낸다. API key, password, token, 사용자 개인정보, proprietary source 전체, 내부 URL/credential을 넣지 않는다.

Provider가 anonymous rate limit/timeout/network 문제로 unavailable이면 API key 생성을 강제하거나 `npx` fallback을 수행하지 않는다. `CONTEXT7_STATUS=unavailable` evidence를 남기고 공식 upstream/local type source로 내려간다.

## 3. Version Match

반드시 다음 중 하나를 기록한다.

```text
EXACT
→ 실제 project version과 동일한 공식 docs/library ID

COMPATIBLE
→ 같은 지원 line/major-minor로 판단할 공식 근거가 있음

LATEST_ONLY
→ 현재 version 전용 문서를 찾지 못해 latest 문서만 확인

LOCAL_ONLY
→ remote 공식 문서보다 설치된 local type/source만 authoritative evidence로 사용

UNKNOWN
→ version 정합성을 증명하지 못함
```

`LATEST_ONLY` 또는 `UNKNOWN` 문서에서 나온 신규 API를 현재 version에 바로 이식하지 않는다.

## 4. Fallback Chain

```text
Context7 Hosted MCP version-matched official docs
→ vendor 공식 문서 / 공식 GitHub repository / release note
→ 설치된 node_modules/JAR/source/type metadata
→ compiler/typecheck/test/build
```

블로그/Stack Overflow/임의 gist는 공식 evidence보다 앞설 수 없다. community source는 공식 evidence를 찾기 위한 단서로만 사용한다.

## 5. Local Types / Source Gate

외부 API를 호출하거나 compiler compatibility 문제를 해결할 때 문서 예시만 복사하지 않는다.

Node/TypeScript:

```text
실제 package version
→ package exports / .d.ts / package source
→ 실제 tsconfig + TypeScript version/lib
→ typecheck
```

Spring/JVM:

```text
실제 Spring/JDK/dependency version
→ public API/Javadoc/source signature
→ compile/test
```

공식 문서와 local type signature가 다르면 **현재 설치된 version의 local signature**를 구현 계약으로 우선하고 version drift를 보고한다.

## 6. Compatibility 오류 분류

외부 package declaration과 compiler/runtime platform declaration이 충돌하면 다음으로 분류한다.

```text
DEPENDENCY_DECLARATION_COMPATIBILITY
```

최소 evidence:

```text
Dependency / Resolved Version
Compiler / Runtime Version
Error Code + declaration origin
Official Docs Match
Installed Local Type Evidence
Application Source Error: true|false
Generated Artifact Error: true|false
```

이 분류에서 자동으로 다음을 하지 않는다.

```text
skipLibCheck=true
strict=false
dependency 임의 downgrade/upgrade
patch-package 자동 도입/적용
node_modules 직접 patch
generated declaration 수동 수정
--force / --legacy-peer-deps
공식 근거 없는 compiler downgrade
```

필요한 버전 변경은 기존 Requirement Delta / dependency mutation 정책을 따른다. `DEPENDENCY_DECLARATION_COMPATIBILITY`는 현재 기능 구현과 자동으로 합쳐 해결하지 않는다. patch-package, dependency/compiler version 변경, framework config 우회가 필요하면 **별도 승인된 compatibility 해결 범위**로 분리하고 현재 Task에는 blocker/evidence만 남긴다.

## 7. Implementation / Verification

```text
version evidence
→ official docs evidence
→ local API/type evidence
→ 최소 변경 구현
→ compiler/typecheck
→ affected test
→ production build 또는 해당 기술의 canonical verification
```

문서 lookup 성공만으로 구현 성공을 선언하지 않는다.

## Handoff Evidence

```text
Documentation Required: yes | no
Documentation Ready: pass | partial | blocked
Technology: ...
Detected Version: ...
Version Source: ...
Context7 Transport: hosted_mcp | unavailable | not_required
Context7 Auth Mode: anonymous | bearer | not_required
Context7 Status: available | unavailable | not_required
Context7 Library ID: ... | NONE
Version Match: EXACT | COMPATIBLE | LATEST_ONLY | LOCAL_ONLY | UNKNOWN
Official Topics Checked:
- ...
Official/Upstream Source:
- ...
Installed Local Type/Source Evidence:
- ...
Compiler/Typecheck/Build Evidence:
- ...
Compatibility Class: NONE | DEPENDENCY_DECLARATION_COMPATIBILITY | ...
Residual Version Drift Risk:
- ...
```

## 불변식

- `Context7`는 provider이지 최종 correctness 판정자가 아니다.
- Hosted MCP anonymous access를 정상 기본값으로 취급하며 API key 생성을 사용자에게 강제하지 않는다.
- Hosted MCP 조회를 위해 `npx`, npm global install, pip install을 수행하지 않는다.
- `resolve-library-id`, `query-docs` 외 Context7 tool을 사용하지 않는다.
- actual installed/resolved version을 확인하기 전에 latest 문법을 도입하지 않는다.
- 공식 문서와 프로젝트 기존 convention이 충돌하면 Task 범위와 사용자 정책을 우선하고 차이를 evidence로 남긴다.
- 외부 기술 오류를 애플리케이션 source 오류로 성급하게 분류하지 않는다.
- `DEPENDENCY_DECLARATION_COMPATIBILITY`를 발견했다는 이유만으로 patch-package나 dependency/compiler version 변경을 자동 수행하지 않는다.
- provider 장애를 해결하려고 새로운 package manager/global tool을 설치하지 않는다.
- compiler/typecheck/test/build를 문서 조회로 대체하지 않는다.
