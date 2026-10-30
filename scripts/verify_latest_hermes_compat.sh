#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
BASE_IMAGE="${HERMES_BASE_IMAGE:-nousresearch/hermes-agent:latest}"
RUN_ID="$(python3 -c 'import uuid;print(uuid.uuid4().hex[:12])')"
IMAGE_NAME="hermes-devkit:devkit-ci-$RUN_ID"
BUILT=0
cleanup() { if [ "$BUILT" = 1 ]; then docker image rm "$IMAGE_NAME" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT
# The full runtime inherits the exact patched upstream stage. Pull latest only once.
docker build --pull --build-arg "HERMES_BASE_IMAGE=$BASE_IMAGE" --target hermes-devkit-runtime --tag "$IMAGE_NAME" .
BUILT=1
docker run --rm --entrypoint /bin/sh \
    --mount "type=bind,source=$REPO_ROOT/custom-skills,target=/opt/custom-skills,readonly" \
    --mount "type=bind,source=$REPO_ROOT/shared,target=/opt/data/shared,readonly" \
    "$IMAGE_NAME" -ceu '
        /opt/hermes/.venv/bin/hermes --help >/dev/null
        /opt/hermes/.venv/bin/hermes kanban boards list --json >/tmp/kanban-boards.json
        test "$(/usr/local/bin/git --version)" = "git version 2.55.0"
        test "$(/usr/local/bin/git config --system --bool --get worktree.useRelativePaths)" = "true"
        test "$(/usr/local/bin/pnpm --version)" = "12.5.1"
        /opt/hermes/.venv/bin/python /opt/devkit/bin/devkit_gateway_readiness.py --self-test
        /opt/hermes/.venv/bin/python /opt/devkit/bin/devkit_kanban_notifier.py --self-test
        /opt/hermes/.venv/bin/python /opt/devkit/scripts/verification/maven_verification_cached.py --help
        /opt/hermes/.venv/bin/python /opt/devkit/scripts/verification/gradle_verification_cached.py --help
        test ! -e /opt/hermes/hermes_cli/devkit_worker_startup.py
        test ! -e /opt/hermes/hermes_cli/devkit_session_affinity.py
        test ! -e /etc/cont-init.d/018-devkit-kanban-boot-recovery
        for version in 8 17 21; do /opt/jdks/temurin-$version/bin/java -version; done
        runtime_smoke=/tmp/devkit-pnpm-runtime-smoke
        runtime_home=/tmp/devkit-pnpm-home
        mkdir -p "$runtime_smoke" "$runtime_home"
        cat > "$runtime_smoke/package.json" <<"JSON"
{
  "name": "devkit-pnpm-runtime-smoke",
  "private": true,
  "scripts": {
    "runtime-smoke": "node --version"
  },
  "devEngines": {
    "runtime": {
      "name": "node",
      "version": "22.23.2",
      "onFail": "download"
    },
    "packageManager": {
      "name": "pnpm",
      "version": ">=12.0.0 <13.0.0",
      "onFail": "download"
    }
  }
}
JSON
        (
          cd "$runtime_smoke"
          export PNPM_HOME="$runtime_home"
          export PATH="$PNPM_HOME:/usr/local/bin:$PATH"
          echo "[PNPM_SMOKE] install lockfile"
          /usr/local/bin/pnpm install --lockfile-only
          echo "[PNPM_SMOKE] verify lockfile"
          test -f pnpm-lock.yaml || { echo "[FAIL] pnpm install did not create lockfile" >&2; exit 1; }
          echo "[PNPM_SMOKE] set strict dependency build policy"
          /usr/local/bin/pnpm config set --location=project --json strictDepBuilds true
          echo "[PNPM_SMOKE] set allow-all-builds=false"
          /usr/local/bin/pnpm config set --location=project --json dangerouslyAllowAllBuilds false
          echo "[PNPM_SMOKE] verify pnpm-workspace.yaml"
          test -f pnpm-workspace.yaml || { echo "[FAIL] pnpm config set did not create workspace policy" >&2; exit 1; }
          echo "[PNPM_SMOKE] inspect effective build policy"
          /opt/hermes/.venv/bin/python \
            /opt/custom-skills/shared/dev-node-dependencies/scripts/pnpm_build_policy.py \
            --workspace "$runtime_smoke" > /tmp/devkit-pnpm-build-policy.out
          echo "[PNPM_SMOKE] assert build policy output"
          grep -q "^PNPM_BUILD_POLICY=PASS$" /tmp/devkit-pnpm-build-policy.out || { cat /tmp/devkit-pnpm-build-policy.out >&2; exit 1; }
          grep -q "^PNPM_BUILD_POLICY_SOURCE=pnpm-workspace.yaml$" /tmp/devkit-pnpm-build-policy.out || { cat /tmp/devkit-pnpm-build-policy.out >&2; exit 1; }
          echo "[PNPM_SMOKE] check pinned Node runtime"
          runtime_version="$(/usr/local/bin/pnpm --silent run runtime-smoke | tail -n 1)"
          test "$runtime_version" = "v22.23.2" || { echo "[FAIL] expected Node v22.23.2, got: $runtime_version" >&2; exit 1; }
          echo "[PNPM_SMOKE] pass"
        )
        rm -rf "$runtime_smoke" "$runtime_home"

    '
docker run --rm --user hermes --entrypoint /opt/hermes/.venv/bin/python \
    --mount "type=bind,source=$REPO_ROOT,target=/opt/devkit-tests,readonly" \
    "$IMAGE_NAME" /opt/devkit-tests/scripts/smoke_maven_runtime.py \
        --launcher-dir /usr/local/bin --extension-source-root /usr/local/share/hermes-maven-output \
        --verifier /opt/devkit/scripts/verification/maven_verification.py
python3 scripts/smoke_devkit_image.py --image "$IMAGE_NAME"
printf '[PASS] Latest Hermes, JDK/Git/pnpm/Maven, actual DevKit boot and persistent data safety.\n'
