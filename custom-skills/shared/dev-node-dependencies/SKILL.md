---
name: dev-node-dependencies
description: Node.js 프로젝트의 Frontend 실행 전 pnpm toolchain 환경 Gate와 dependency 추가·삭제·복원, pnpm-lock.yaml 검증, Tirith security preflight를 제공하는 공통 capability skill.
version: 0.2.4
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, node, pnpm, dependency, package-manager, lockfile, runtime, tirith, security, headless]
    related_skills: [dev-frontend-feature, dev-typescript-guidelines, dev-nextjs-feature, dev-frontend-test]
    requires_tools: [terminal]
---

# dev-node-dependencies

Hermes Agent DevKit의 Node package manager는 **pnpm 하나만 사용한다**. Node runtime과 pnpm version의 source of truth는 별도 Hermes 설정 파일이 아니라 프로젝트의 기존 필수 manifest인 `package.json`이다.

## Canonical Toolchain Contract

Node 프로젝트는 다음 계약을 가진다.

```json
{
  "devEngines": {
    "runtime": {
      "name": "node",
      "version": "<project Node version/range>",
      "onFail": "download"
    },
    "packageManager": {
      "name": "pnpm",
      "version": "<project pnpm version/range>",
      "onFail": "download"
    }
  }
}
```

역할:

```text
package.json devEngines.runtime
→ 프로젝트가 실제 개발/검증에서 사용할 Node runtime

package.json devEngines.packageManager
→ 프로젝트가 사용할 pnpm version

pnpm-lock.yaml
→ dependency graph + pnpm/runtime resolution 재현성
```

pnpm standalone은 DevKit image에 존재하고 Node는 image에 고정하지 않는다. `pnpm install`이 `devEngines.runtime`을 해석해 필요한 Node를 내려받고, resolved runtime/version checksum을 lockfile에 기록한다.

추가 Node version file을 표준으로 만들지 않는다.

```text
.nvmrc        → DevKit canonical source 아님
.node-version → DevKit canonical source 아님
volta.node    → DevKit canonical source 아님
```

## pnpm-only Migration Gate

다음 lockfile이 존재하면 호환 실행하지 않고 migration blocker로 처리한다.

```text
package-lock.json
npm-shrinkwrap.json
yarn.lock
bun.lock
bun.lockb
```

Node 프로젝트의 canonical lockfile은 오직:

```text
pnpm-lock.yaml
```

이다.

기존 npm/yarn/bun 프로젝트를 Agent가 임의로 병행 지원하지 않는다. 프로젝트 migration Task에서 `package.json` toolchain 선언과 `pnpm-lock.yaml`을 만든 뒤 정상 Node workflow로 진입한다.

## Frontend Environment Gate

모든 Node/Frontend Task는 dependency mutation 여부와 관계없이 **첫 Node command 전에** 환경 Gate를 실행한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_environment_gate.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root relative to workspace>"]
```

PASS 조건:

```text
package.json devEngines.runtime = node
package.json devEngines.packageManager = pnpm
top-level packageManager가 있으면 pnpm
legacy npm/yarn/bun lockfile 없음
pnpm-lock.yaml 존재
DevKit pnpm runtime 사용 가능
```

PASS evidence:

```text
FRONTEND_ENVIRONMENT_GATE=PASS
BLOCKER_CLASS=NONE
PACKAGE_MANAGER=pnpm
NODE_REQUIREMENT
PNPM_REQUIREMENT
CANONICAL_LOCKFILE
SOURCE_VERIFICATION_POLICY=FORBIDDEN
VERIFICATION_RUNTIME=node_runtime.py
```

npm/yarn/bun project, legacy lockfile, pnpm contract 미완성은:

```text
FRONTEND_ENVIRONMENT_GATE=BLOCKED
BLOCKER_CLASS=PROJECT_TOOLCHAIN_MIGRATION_REQUIRED
SOURCE_VERIFICATION_POLICY=FORBIDDEN
```

으로 즉시 중단한다. 이 상태에서 worker가 검증을 계속하기 위해 source worktree에서 다음 fallback을 실행하면 안 된다.

```text
npm test / npm run ...
npx ...
next ...
tsc ...
pnpm run ...  # source worktree 직접 실행
```

프로젝트 toolchain migration은 현재 기능 구현의 암묵적 부수 작업으로 수행하지 않는다. 별도 승인된 migration scope에서 pnpm 계약을 준비한 뒤 원래 Task를 재개한다. Gate가 BLOCKED이면 source worktree의 `.next`, `node_modules`, `dist`, `build`를 새로 만들거나 권한을 수선하며 검증을 강행하지 않는다.

## pnpm Standard Build Policy

dependency의 `preinstall/install/postinstall` 실행 권한은 Hermes 전용 파일이 아니라 **pnpm 표준 project config인 `pnpm-workspace.yaml`의 `allowBuilds`**를 유일한 source of truth로 사용한다.

기본 보안 계약:

```yaml
strictDepBuilds: true
dangerouslyAllowAllBuilds: false

allowBuilds:
  'unrs-resolver@1.12.2': true
```

정책:

```text
strictDepBuilds=true
→ 검토되지 않은 dependency build script가 있으면 fail-closed

dangerouslyAllowAllBuilds=false
→ 현재/미래 모든 transitive dependency의 script 자동 허용 금지

allowBuilds['package@exact-version']=true
→ 해당 package/version은 프로젝트에서 승인됨
→ 이후 동일 matcher는 재승인 없이 pnpm 표준 동작으로 통과

새 package 또는 새 version
→ 기존 exact matcher가 적용되지 않음
→ ERR_PNPM_IGNORED_BUILDS
→ 새 1회 검토 대상
```

`pnpm-workspace.yaml`이 아직 없고 승인/거부 기록도 없으면 pnpm 12의 안전한 기본값(`strictDepBuilds=true`, `dangerouslyAllowAllBuilds=false`)을 사용하므로 Gate는 통과할 수 있다. **최초 build-script 결정이 생기는 시점부터** project config를 Git에 기록한다.

현재 정책 확인:

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/pnpm_build_policy.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root>"]
```

사용자가 build script를 승인한 뒤 정책 변경 계획 생성:

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/pnpm_build_policy.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root>"] \
  --approve "unrs-resolver@1.12.2"
```

거부:

```bash
.../pnpm_build_policy.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root>"] \
  --deny "package@1.2.3"
```

helper는 직접 project config를 수정하거나 dependency script를 실행하지 않는다. 기존 `allowBuilds`를 읽고 pnpm 공식 `config set --location=project --json` 기반의 exact `POLICY_UPDATE_COMMAND_<N>`을 출력한다. **사용자 승인 이후** Coder가 해당 명령을 source package root에서 Hermes terminal guard를 통해 실행한다.

DevKit 기본 승인 matcher는 registry dependency의 **`package@exact-version`** 이다. bare package 전체, version range, 모든 package 전역 승인은 자동 승인하지 않는다. 더 넓은 범위가 실제로 필요하면 별도 명시적 정책 결정으로 취급한다.

### Build Policy Bootstrap Batch Gate

pnpm toolchain migration 또는 새 lockfile을 처음 안정화할 때 build-script approval을 dependency마다 하나씩 묻지 않는다. **첫 isolated restore에서 발견 가능한 미검토 build package 전체를 한 batch로 수집한 뒤 한 번만 사용자 결정을 요청한다.**

초기 흐름:

```text
pnpm toolchain + pnpm-lock.yaml 준비
→ isolated frozen restore 1회
→ 성공: build approval 없음, 그대로 검증
→ ERR_PNPM_IGNORED_BUILDS:
   1. 해당 restore 출력에서 package@version 전체 수집
   2. 같은 RESTORE_WORKDIR에서 read-only `pnpm ignored-builds` 1회 실행
   3. 이미 allowBuilds=true/false인 matcher 제외
   4. 남은 미검토 matcher 전체를 하나의 REVIEW_BATCH로 제시
   5. 사용자에게 batch 승인/거부 1회 요청
```

`pnpm ignored-builds`는 pnpm 공식 read-only 진단 명령으로만 사용한다. source worktree 검증 fallback이나 dependency mutation으로 취급하지 않으며 **실패한 isolated restore의 `RESTORE_WORKDIR`에서만** pending build 목록 확인에 사용한다.

사용자가 여러 항목을 한 번에 결정하면 helper에 여러 `--approve` / `--deny`를 전달한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/pnpm_build_policy.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root>"] \
  --approve "unrs-resolver@1.12.2" \
  --approve "esbuild@0.25.9" \
  --deny "example-package@1.0.0"
```

batch evidence:

```text
PNPM_BUILD_POLICY_DECISION_MODE=BATCH
PNPM_BUILD_POLICY_DECISION_COUNT=<N>
PNPM_BUILD_POLICY_APPROVAL_COUNT=<N>
PNPM_BUILD_POLICY_DENIAL_COUNT=<N>
PNPM_BUILD_POLICY_BATCH_APPROVALS=<...|NONE>
PNPM_BUILD_POLICY_BATCH_DENIALS=<...|NONE>
```

승인/거부를 `pnpm-workspace.yaml > allowBuilds`에 한 번 반영한 뒤 dependency preflight와 isolated frozen restore를 **한 번만 재시도**한다. 동일 package graph에서 두 번째 restore가 새로운 미검토 matcher를 추가로 발견하면 자동 반복 승인 루프를 만들지 않고 `PNPM_BUILD_POLICY_DISCOVERY_INCOMPLETE`로 BLOCK하여 왜 첫 batch에 포함되지 않았는지 조사한다. package.json/pnpm-lock.yaml이 중간에 변경되어 dependency graph 자체가 바뀐 경우에만 새 batch로 취급한다.

일반 기능 Task에서 이미 Git에 결정된 build policy가 있으면 이 bootstrap batch를 다시 실행하지 않는다.

### ERR_PNPM_IGNORED_BUILDS 처리

isolated `pnpm install --frozen-lockfile`에서 이 오류가 발생하면 dependency restore 실패와 application source 오류를 구분한다.

```text
ERR_PNPM_IGNORED_BUILDS
→ pnpm output + isolated `pnpm ignored-builds`로 미검토 package@version 전체 수집
→ PNPM_BUILD_POLICY_REVIEW_REQUIRED
→ REVIEW_BATCH 1개로 사용자에게 한 번에 승인/거부 요청
→ 승인/거부 exact matcher 전체를 allowBuilds에 한 번 기록
→ dependency preflight 재실행
→ isolated frozen restore 1회 재실행
→ test/lint/typecheck/build 재개
```

이미 `allowBuilds`에서 `true` 또는 `false`로 결정된 matcher는 다시 묻지 않는다. pnpm이 자동으로 생성한 `"set this to true or false"` placeholder 또는 기타 non-boolean 값은 미검토 상태로 분류하고 Gate에서 차단한다.

사용자 승인 없이 다음 우회는 금지한다.

```text
dangerouslyAllowAllBuilds=true
strictDepBuilds=false
--ignore-scripts
pnpm approve-builds --all
bare package 전체를 true로 자동 확장
Hermes 전용 allowlist 파일 생성
```

`pnpm-workspace.yaml`은 dependency fingerprint에 포함된다. 따라서 build policy 변경 후 기존 isolated `node_modules`를 그대로 정상 상태로 간주하지 않고 frozen restore를 다시 수행한다. pnpm의 side-effects cache는 별도 정책 변경 없이 그대로 활용하므로 동일 package build 결과의 재사용은 pnpm 표준 동작에 맡긴다.

## Dependency Preflight

package mutation 전에 다음 helper를 정확히 1회 실행한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_dependency_preflight.py \
  --workspace "<Task Workspace>" \
  [--package-root "<relative package root>"] \
  --dependency-type "prod|dev" \
  --package "<package-or-spec>" \
  [--package "<package-or-spec>" ...]
```

검증 범위:

```text
package root
→ nearest pnpm toolchain root
→ package.json devEngines.runtime
→ package.json devEngines.packageManager
→ pnpm standalone availability
→ legacy lockfile absence
→ pnpm-lock.yaml
→ manifest/node_modules state
→ exact pnpm mutation command
```

PASS evidence:

```text
PACKAGE_ROOT
PACKAGE_MANAGER_ROOT
PACKAGE_MANAGER=pnpm
PACKAGE_MANAGER_SOURCE=package.json devEngines.packageManager
PACKAGE_MANAGER_VERSION
PACKAGE_MANAGER_REQUIRED_VERSION
NODE_VERSION=managed-by-pnpm
NODE_REQUIREMENT
NODE_REQUIREMENT_SOURCE=package.json devEngines.runtime
CANONICAL_LOCKFILE
LOCKFILE_PRESENT
DEPENDENCY_<N>_MANIFEST_STATE
DEPENDENCY_<N>_NODE_MODULES_STATE
INSTALL_REQUIRED
DEPENDENCY_FINGERPRINT
DEPENDENCIES_READY
RESTORE_REQUIRED
INSTALL_COMMAND
RESTORE_COMMAND
RESTORE_MARK_COMMAND
BUILD_REVIEW_MODE
BUILD_REVIEW_COMMAND
BUILD_REVIEW_WORKDIR
INSTALL_TIMEOUT_SECONDS
STATUS=pass
```

`STATUS=blocked`이면 dependency command를 실행하지 않는다.

## Manifest / node_modules Contract

`node_modules`는 source of truth가 아니다.

상태:

```text
DECLARED_PROD
DECLARED_DEV
DECLARED_PEER
DECLARED_OPTIONAL
ABSENT
```

node_modules 상태:

```text
PRESENT_DECLARED
EXTRANEOUS_PRESENT
ABSENT
```

예:

```text
package.json에 없음
node_modules에는 존재
→ EXTRANEOUS_PRESENT
→ install 완료로 간주하지 않음
```

## Tirith Security Preflight

Node package mutation은 실제 exact command를 대상으로 security preflight를 수행한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/tirith_package_preflight.py \
  --command "<exact pnpm command>"
```

상태:

```text
TIRITH_PREFLIGHT=allow
→ actual terminal guard까지 진행

TIRITH_PREFLIGHT=approval_required
→ headless worker에서 실행 금지, Kanban BLOCK

TIRITH_PREFLIGHT=unavailable
→ actual Hermes terminal guard를 그대로 사용
```

`analysis_incomplete`만 존재할 때만 기존 bounded daemon recheck 계약을 적용한다. 실제 malware/warn/block finding은 retry로 가리지 않는다.

금지:

```text
TIRITH_ENABLED=0
approval/yolo bypass
fail-open 강제
preflight allow를 actual guard bypass token으로 사용
command 문자열 변형으로 scanner 회피
```

actual Hermes terminal guard가 최종 authority다.

## Dependency Mutation

preflight PASS + Tirith 허용 이후 exact package manager command를 **정확히 1회** 실행한다. Source package에서는 `--lockfile-only`를 사용해 `package.json`과 `pnpm-lock.yaml`만 갱신하고 Windows bind workspace의 `node_modules`는 생성·변경하지 않는다.

```text
prod → pnpm add --lockfile-only <pkg...>
dev  → pnpm add --lockfile-only -D <pkg...>
```

terminal timeout:

```text
timeout=600
```

shell `timeout` wrapper를 사용하지 않는다.

timeout/exit 124이면 자동 반복하지 않고:

```text
DEPENDENCY_INSTALL_FAILURE_CLASS=TIMEOUT
```

으로 BLOCK한다.

기존 dependency tree 복원은:

```text
pnpm-lock.yaml 있음
→ pnpm install --frozen-lockfile

초기 migration/lock 생성 Task
→ pnpm install
```

을 사용한다.

## Hermes Runtime Isolation

test/lint/typecheck/build 같은 검증은 Windows bind-mounted source에서 직접 실행하지 않는다. 현재 package source를 Linux named volume의 격리 workspace로 동기화한 뒤 그 복사본에서 실행한다. 격리 상태 경로는 실행 사용자(정상 운영에서는 `hermes`)가 소유해야 하며 root/다른 UID 소유 경로가 발견되면 자동 chown으로 숨기지 않고 환경 오류로 BLOCK한다.

격리 workspace 준비:

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_workspace.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root>"]
```

출력의 `NODE_ISOLATED_PACKAGE_ROOT`가 실제 Hermes Node execution root다.

동기화 정책:

```text
source code / package.json / pnpm-lock.yaml
→ Windows bind workspace에서 Linux isolated workspace로 동기화

Windows node_modules / .next / dist / build / coverage / *.tsbuildinfo
→ 복사하지 않음

Linux isolated node_modules
→ package.json + pnpm-lock.yaml fingerprint가 동일할 때만 검증 간 유지

package.json / pnpm-lock.yaml / pnpm-workspace.yaml fingerprint 변경
→ 기존 isolated node_modules 폐기
→ frozen restore 재요구

Linux .next / dist / build / coverage / *.tsbuildinfo
→ 각 검증 시작 전에 제거
```

따라서 host에서 `next dev`가 실행 중이거나 `.next/dev/types`가 남아 있어도 Hermes typecheck/build 입력에 포함되지 않는다.

dependency가 이미 manifest/lockfile에 있고 isolated `node_modules`가 없으면 exact command를 **isolated workdir**에서 Tirith actual guard를 거쳐 실행한다.

```text
RESTORE_COMMAND=pnpm install --frozen-lockfile
RESTORE_WORKDIR=<NODE_ISOLATED_PACKAGE_ROOT>
RESTORE_MARK_COMMAND=python3 .../node_workspace.py --workspace ... --cwd ... --mark-restored
```

restore가 성공한 뒤 `RESTORE_MARK_COMMAND`를 실행해 현재 `package.json + pnpm-lock.yaml + pnpm-workspace.yaml` fingerprint를 기록한다. source manifest/lockfile/build policy가 restore 이후 바뀌었으면 mark를 거부하고 preflight부터 다시 수행한다.

검증:

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_runtime.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root>"] \
  -- pnpm run <script>
```

runtime helper는 source를 다시 동기화한 후:

```text
pnpm home/store  → /opt/data/node
TMP/XDG cache    → /opt/data/node
execution cwd    → /opt/data/node/workspaces/<workspace-id>/packages/<package-id>/source
workspace command → lock으로 직렬화
```

를 적용한다. Next.js/Vite 등 framework-specific output 설정을 프로젝트에 추가로 강제하지 않는다. 격리의 경계는 framework output directory가 아니라 **execution workspace 자체**다.

## Mutation Verification

dependency 변경 후 최소 확인:

```text
package.json 반영
pnpm-lock.yaml 생성/갱신
legacy package-manager lockfile 없음
pnpm install/resolve 성공
project test/lint/typecheck/build 영향 범위 검증
```

## Handoff Evidence

```text
Node Dependency Preflight: PASS | BLOCKED
Package Root: ...
Package Manager Root: ...
Package Manager: pnpm
Package Manager Version: ...
Required Package Manager Version: ...
Node Runtime: managed-by-pnpm
Node Requirement: ...
Canonical Lockfile: .../pnpm-lock.yaml
Lockfile Present Before: true | false
Tirith Preflight: allow | approval_required | unavailable
Tirith Actual Guard: allow | approval_required | block | not_run
pnpm Build Policy: PASS | REVIEW_REQUIRED | DISCOVERY_INCOMPLETE | BLOCKED
Build Policy Review Mode: BATCH | NOT_REQUIRED
Build Policy Review Count: <N | 0>
pnpm Build Policy File: <.../pnpm-workspace.yaml | NOT_PRESENT>
Approved Builds: <package@version,... | NONE>
Denied Builds: <package@version,... | NONE>
Install Command: ... | NOT_REQUIRED
Install Workdir: ... | NOT_REQUIRED
Restore Command: ... | NOT_REQUIRED
Restore Workdir: ... | NOT_REQUIRED
Restore Mark Command: ... | NOT_REQUIRED
Build Review Mode: SINGLE_REVIEW_BATCH | NOT_REQUIRED
Build Review Command: pnpm ignored-builds | NOT_REQUIRED
Build Review Workdir: ... | NOT_REQUIRED
Dependency Fingerprint: ...
Dependencies Ready: true | false
Verification Package Root: ...
Install Timeout Seconds: 600 | NOT_REQUIRED
Manifest Updated: true | false | not_required
Lockfile Updated: true | false | not_required
Verification:
- ...
Residual Risk:
- ...
```

## 불변식

- 모든 Node/Frontend Task는 첫 Node command 전에 `node_environment_gate.py`를 통과한다.
- Gate BLOCKED 상태에서 source worktree 직접 npm/next/tsc/pnpm 검증으로 fallback하지 않는다.
- Node 프로젝트는 pnpm만 사용한다.
- `package.json`이 Node/pnpm toolchain source of truth다.
- `pnpm-lock.yaml`만 canonical lockfile로 사용한다.
- `node_modules`는 source of truth가 아니다.
- dependency build-script 결정은 pnpm 표준 `pnpm-workspace.yaml > allowBuilds`만 source of truth로 사용한다.
- 승인 `true`의 기본 matcher는 `package@exact-version`이다.
- `dangerouslyAllowAllBuilds=true`, `strictDepBuilds=false`, `pnpm approve-builds --all`을 자동 사용하지 않는다.
- 같은 approved/denied matcher를 반복 승인받지 않는다.
- 초기 pnpm 안정화에서 미검토 build dependency를 package별로 연속 BLOCK하지 않고 하나의 batch로 수집한다.
- 동일 dependency graph의 batch 승인 후 두 번째 신규 matcher가 나오면 자동 반복하지 않고 discovery incomplete로 BLOCK한다.
- dependency mutation은 Tirith actual guard를 우회하지 않는다.
- 동일 실패 command를 자동 반복하지 않는다.
- 별도 Hermes 전용 Node version 설정 파일을 만들지 않는다.
