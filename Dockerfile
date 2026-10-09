ARG HERMES_BASE_IMAGE=nousresearch/hermes-agent:latest

FROM eclipse-temurin:8-jdk-jammy AS jdk8
FROM eclipse-temurin:17-jdk-jammy AS jdk17
FROM eclipse-temurin:21-jdk-jammy AS jdk21

# Upstream-sensitive DevKit patches live in their own stage so CI can validate
# nousresearch/hermes-agent:latest without paying the full Git/JDK runtime build cost.
FROM ${HERMES_BASE_IMAGE} AS hermes-upstream-patched

USER root

# Keep reasoning dim while making user-input surfaces visually distinct: cyan for
# Clarify interaction and green for the recommended choice / recommendation label.
COPY scripts/patch_hermes_tui_semantic_input.py /tmp/patch_hermes_tui_semantic_input.py
RUN python3 /tmp/patch_hermes_tui_semantic_input.py --self-test \
    && python3 /tmp/patch_hermes_tui_semantic_input.py --search-root /opt/hermes \
    && python3 /tmp/patch_hermes_tui_semantic_input.py --check-only --search-root /opt/hermes \
    && rm /tmp/patch_hermes_tui_semantic_input.py

# Keep every skill directly invokable and visible to runtime/management, but allow
# DevKit internal skills to opt out of user input slash suggestions.
COPY scripts/patch_hermes_skill_slash_suggest.py /tmp/patch_hermes_skill_slash_suggest.py
RUN python3 /tmp/patch_hermes_skill_slash_suggest.py --self-test \
    && python3 /tmp/patch_hermes_skill_slash_suggest.py --hermes-root /opt/hermes \
    && rm /tmp/patch_hermes_skill_slash_suggest.py

# Legacy Hermes has Tirith; newer Hermes retired it in favor of core approval guards.
# Enforce one of the known contracts, never silently skip security checks.
COPY scripts/patch_hermes_tirith_profile_guard.py /tmp/patch_hermes_tirith_profile_guard.py
COPY scripts/check_hermes_security_contract.py /tmp/check_hermes_security_contract.py
RUN python3 /tmp/patch_hermes_tirith_profile_guard.py --self-test \
    && python3 /tmp/check_hermes_security_contract.py --self-test \
    && if test -f /opt/hermes/tools/tirith_security.py; then \
         python3 /tmp/patch_hermes_tirith_profile_guard.py /opt/hermes/tools/tirith_security.py; \
       fi \
    && /opt/hermes/.venv/bin/python /tmp/check_hermes_security_contract.py --root /opt/hermes \
    && rm /tmp/patch_hermes_tirith_profile_guard.py /tmp/check_hermes_security_contract.py

# Read-only verification of the live multiplex Gateway, separate from s6 service status.
COPY --chmod=0755 scripts/devkit_gateway_readiness.py /opt/devkit/bin/devkit_gateway_readiness.py
RUN /opt/hermes/.venv/bin/python /opt/devkit/bin/devkit_gateway_readiness.py --self-test

COPY scripts/devkit_worker_startup.py /opt/hermes/hermes_cli/devkit_worker_startup.py
RUN python3 -m py_compile /opt/hermes/hermes_cli/devkit_worker_startup.py

COPY scripts/devkit_session_affinity.py /opt/hermes/hermes_cli/devkit_session_affinity.py
RUN python3 /opt/hermes/hermes_cli/devkit_session_affinity.py --self-test

COPY scripts/patch_hermes_kanban_session_affinity.py /tmp/patch_hermes_kanban_session_affinity.py
RUN python3 /tmp/patch_hermes_kanban_session_affinity.py --self-test \
    && python3 /tmp/patch_hermes_kanban_session_affinity.py --search-root /opt/hermes/hermes_cli \
    && rm /tmp/patch_hermes_kanban_session_affinity.py

# Reviewer DEFAULT / Coder approved-model transitions must run inside the claim-bound
# Kanban lifecycle tool path, not in Codex native shell where ownership env is scrubbed.
COPY scripts/patch_hermes_kanban_model_transition.py /tmp/patch_hermes_kanban_model_transition.py
RUN python3 /tmp/patch_hermes_kanban_model_transition.py --self-test \
    && python3 /tmp/patch_hermes_kanban_model_transition.py /opt/hermes/tools/kanban_tools.py \
    && grep -q 'def _devkit_run_flow_model_transition' /opt/hermes/tools/kanban_tools.py \
    && rm /tmp/patch_hermes_kanban_model_transition.py

# Show DevKit tracking parent/child mapping directly on Kanban cards without
# creating Hermes native task_links (those are execution dependencies). The preview
# derives relationships from Child task body metadata and never links/unlinks cards.
COPY scripts/patch_hermes_kanban_relation_preview.py /tmp/patch_hermes_kanban_relation_preview.py
RUN python3 /tmp/patch_hermes_kanban_relation_preview.py --self-test \
    && python3 /tmp/patch_hermes_kanban_relation_preview.py --hermes-root /opt/hermes \
    && python3 /tmp/patch_hermes_kanban_relation_preview.py --check-only --hermes-root /opt/hermes \
    && /opt/hermes/.venv/bin/python -m py_compile /opt/hermes/plugins/kanban/dashboard/plugin_api.py \
    && rm /tmp/patch_hermes_kanban_relation_preview.py

# Normalize explicitly declared tracking relationships to the exact multiline
# Parent Tracking body contract on real Kanban create/edit/dashboard PATCH writes.
# Native dependency links and existing task lifecycle are left untouched.
COPY --chmod=0755 scripts/parent_tracking_body.py /opt/devkit/bin/parent_tracking_body.py
COPY scripts/parent_tracking_body.py /opt/hermes/hermes_cli/devkit_parent_tracking.py
COPY scripts/patch_hermes_parent_tracking_body.py /tmp/patch_hermes_parent_tracking_body.py
RUN python3 /tmp/patch_hermes_parent_tracking_body.py --self-test \
    && python3 /tmp/patch_hermes_parent_tracking_body.py --hermes-root /opt/hermes \
    && python3 /tmp/patch_hermes_parent_tracking_body.py --check-only --hermes-root /opt/hermes \
    && /opt/hermes/.venv/bin/python -m py_compile \
         /opt/hermes/hermes_cli/devkit_parent_tracking.py \
         /opt/hermes/hermes_cli/kanban_db.py \
         /opt/hermes/plugins/kanban/dashboard/plugin_api.py \
    && rm /tmp/patch_hermes_parent_tracking_body.py

# Style user-visible Recovery Plan in the normal assistant response renderer.
# Reasoning and durable Recovery Revision comments are deliberately unchanged.
COPY scripts/devkit_recovery_plan_style.py /opt/hermes/hermes_cli/devkit_recovery_plan_style.py
COPY scripts/patch_hermes_recovery_plan_style.py /tmp/patch_hermes_recovery_plan_style.py
RUN python3 /tmp/patch_hermes_recovery_plan_style.py --self-test \
    && python3 /tmp/patch_hermes_recovery_plan_style.py --hermes-root /opt/hermes \
    && python3 /tmp/patch_hermes_recovery_plan_style.py --check-only --hermes-root /opt/hermes \
    && /opt/hermes/.venv/bin/python -m py_compile \
         /opt/hermes/hermes_cli/devkit_recovery_plan_style.py \
         /opt/hermes/hermes_cli/cli_render.py \
         /opt/hermes/hermes_cli/cli_stream_mixin.py \
    && rm /tmp/patch_hermes_recovery_plan_style.py
# Fail the upstream compatibility stage immediately if a patched Hermes module no
# longer compiles or the canonical CLI entry point disappears.
RUN test -x /opt/hermes/.venv/bin/hermes \
    && /opt/hermes/.venv/bin/hermes --help >/dev/null \
    && grep -q 'DEVKIT_SLASH_SUGGEST_V1' /opt/hermes/agent/skill_commands.py \
    && grep -q 'DEVKIT_SLASH_SUGGEST_V1' /opt/hermes/hermes_cli/commands_completion.py \
    && grep -q 'DEVKIT_SLASH_SUGGEST_V1' /opt/hermes/tui_gateway/methods_tools.py \
    && /opt/hermes/.venv/bin/python -m py_compile \
       /opt/hermes/tools/approval_detection.py \
       /opt/hermes/tools/approval_floors.py \
       /opt/hermes/tools/kanban_tools.py \
       /opt/hermes/hermes_cli/devkit_session_affinity.py \
       /opt/hermes/agent/skill_commands.py \
       /opt/hermes/hermes_cli/commands_completion.py \
       /opt/hermes/tui_gateway/methods_tools.py

# The production DevKit image continues from the exact upstream-patched stage
# validated by CI, then adds local Git/JDK/build tooling.
FROM hermes-upstream-patched AS hermes-devkit-runtime

USER root

COPY --chmod=0755 scripts/task_session_history.py /opt/devkit/bin/task_session_history.py
RUN /opt/hermes/.venv/bin/python /opt/devkit/bin/task_session_history.py --self-test

# Before normal s6 services start, reclaim only Kanban claims whose worker
# fingerprint belongs to a previous container/VM instantiation. The dispatcher
# remains the only component that creates the replacement worker.
COPY --chmod=0755 scripts/devkit_kanban_boot_recovery.py /opt/devkit/bin/devkit_kanban_boot_recovery.py
COPY --chmod=0755 docker/cont-init.d/018-devkit-kanban-boot-recovery /etc/cont-init.d/018-devkit-kanban-boot-recovery
RUN sed -i 's/\r$//' /etc/cont-init.d/018-devkit-kanban-boot-recovery \
    && sh -n /etc/cont-init.d/018-devkit-kanban-boot-recovery \
    && /opt/hermes/.venv/bin/python /opt/devkit/bin/devkit_kanban_boot_recovery.py --self-test

# DevKit notification bridge: one additional s6-supervised process in the same
# container. It reads Hermes Kanban task_events without modifying Hermes source,
# formats developer-facing messages, and delivers through the official
# `hermes send` scripting surface.
COPY --chmod=0755 scripts/task_artifacts.py /opt/devkit/bin/task_artifacts.py
COPY custom-skills/_lib/task_handoff.py /opt/devkit/bin/task_handoff.py
COPY --chmod=0755 scripts/devkit_kanban_notifier.py /opt/devkit/bin/devkit_kanban_notifier.py
COPY --chmod=0755 docker/cont-init.d/019-devkit-kanban-notifier-policy /etc/cont-init.d/019-devkit-kanban-notifier-policy
COPY --chmod=0755 docker/devkit-svscan.d/devkit-notifier/run /opt/devkit/svscan/devkit-notifier/run
RUN sed -i 's/\r$//' \
        /etc/cont-init.d/019-devkit-kanban-notifier-policy \
        /opt/devkit/svscan/devkit-notifier/run \
    && sh -n /etc/cont-init.d/019-devkit-kanban-notifier-policy \
    && sh -n /opt/devkit/svscan/devkit-notifier/run \
    && /opt/hermes/.venv/bin/python /opt/devkit/bin/devkit_kanban_notifier.py --self-test \
    && /opt/hermes/.venv/bin/hermes send --help >/dev/null

ARG GIT_VERSION=2.55.0
ARG PNPM_VERSION=12.5.1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        libcurl4-gnutls-dev \
        libexpat1-dev \
        gettext \
        zlib1g-dev \
        libpcre2-dev \
        curl \
        ca-certificates \
        xz-utils \
        unzip \
        zip \
        less \
        util-linux \
        gh \
    && curl -fsSL \
        "https://www.kernel.org/pub/software/scm/git/git-${GIT_VERSION}.tar.xz" \
        -o /tmp/git.tar.xz \
    && mkdir -p /tmp/git-src \
    && tar -xJf /tmp/git.tar.xz -C /tmp/git-src --strip-components=1 \
    && cd /tmp/git-src \
    && make NO_RUST=1 prefix=/usr/local all \
    && make NO_RUST=1 prefix=/usr/local install \
    && git --version \
    && gh --version \
    && mkdir -p /tmp/git-worktree-check \
    && git -C /tmp/git-worktree-check init -q \
    && git -C /tmp/git-worktree-check worktree repair --relative-paths \
    && git config --system worktree.useRelativePaths true \
    && test "$(git config --system --bool --get worktree.useRelativePaths)" = "true" \
    && rm -rf /tmp/git-src /tmp/git-worktree-check /tmp/git.tar.xz \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=jdk8 /opt/java/openjdk /opt/jdks/temurin-8
COPY --from=jdk17 /opt/java/openjdk /opt/jdks/temurin-17
COPY --from=jdk21 /opt/java/openjdk /opt/jdks/temurin-21

ENV JAVA_HOME_8=/opt/jdks/temurin-8
ENV JAVA_HOME_17=/opt/jdks/temurin-17
ENV JAVA_HOME_21=/opt/jdks/temurin-21
ENV JAVA_HOME=/opt/jdks/temurin-17
ENV PATH="/opt/jdks/temurin-17/bin:${PATH}"

ENV HERMES_GRADLE_ROOT=/opt/data/gradle
ENV HERMES_GRADLE_USER_HOME=/opt/data/gradle/user-home
ENV HERMES_GRADLE_DIST_ROOT=/opt/data/gradle/distributions
ENV HERMES_GRADLE_DOWNLOAD_ROOT=/opt/data/gradle/downloads
ENV HERMES_GRADLE_LOCK_ROOT=/opt/data/gradle/locks
ENV HERMES_GRADLE_PROJECT_CACHE_ROOT=/opt/data/gradle/project-cache
ENV GRADLE_USER_HOME=/opt/data/gradle/user-home

ENV HERMES_MAVEN_ROOT=/opt/data/maven
ENV HERMES_MAVEN_REPO_ROOT=/opt/data/maven/repository
ENV HERMES_MAVEN_DIST_ROOT=/opt/data/maven/distributions
ENV HERMES_MAVEN_DOWNLOAD_ROOT=/opt/data/maven/downloads
ENV HERMES_MAVEN_LOCK_ROOT=/opt/data/maven/locks

# Node projects use pnpm as the only DevKit package manager. The standalone
# bootstrap is pinned for reproducibility; project Node/pnpm versions still come
# from package.json devEngines and are cached under the persistent /opt/data volume.
ENV PNPM_HOME=/opt/pnpm
ENV HERMES_NODE_ROOT=/opt/data/node
ENV PATH="/usr/local/bin:/opt/pnpm/bin:/opt/pnpm:${PATH}"

RUN mkdir -p "$PNPM_HOME" "$HERMES_NODE_ROOT" \
    && touch /tmp/pnpm-shrc \
    && curl -fsSL https://get.pnpm.io/install.sh -o /tmp/install-pnpm.sh \
    && env PNPM_VERSION="$PNPM_VERSION" PNPM_HOME="$PNPM_HOME" ENV=/tmp/pnpm-shrc SHELL="$(command -v sh)" sh /tmp/install-pnpm.sh \
    && pnpm_target="$(find "$PNPM_HOME" \( -type f -o -type l \) -name pnpm -perm -111 | head -n 1)" \
    && test -n "$pnpm_target" \
    && ln -sf "$pnpm_target" /usr/local/bin/pnpm \
    && test "$(/usr/local/bin/pnpm --version)" = "$PNPM_VERSION" \
    && rm -f /tmp/pnpm-shrc /tmp/install-pnpm.sh

RUN ln -sf /opt/jdks/temurin-17/bin/java /usr/local/bin/java \
    && ln -sf /opt/jdks/temurin-17/bin/javac /usr/local/bin/javac \
    && /opt/jdks/temurin-8/bin/java -version \
    && /opt/jdks/temurin-8/bin/javac -version \
    && /opt/jdks/temurin-17/bin/java -version \
    && /opt/jdks/temurin-17/bin/javac -version \
    && /opt/jdks/temurin-21/bin/java -version \
    && /opt/jdks/temurin-21/bin/javac -version \
    && /usr/local/bin/java -version \
    && /usr/local/bin/javac -version

COPY --chmod=0755 scripts/hermes-java /usr/local/bin/hermes-java
COPY --chmod=0755 scripts/hermes-maven /usr/local/bin/hermes-maven
RUN tr -d '\r' < /usr/local/bin/hermes-maven > /tmp/hermes-maven \
    && cat /tmp/hermes-maven > /usr/local/bin/hermes-maven \
    && rm /tmp/hermes-maven \
    && bash -n /usr/local/bin/hermes-maven
COPY scripts/hermes-diff-check.py /usr/local/lib/hermes-diff-check.py
RUN printf '%s\n' '#!/bin/sh' 'exec python3 /usr/local/lib/hermes-diff-check.py "$@"' > /usr/local/bin/hermes-diff-check \
    && chmod 0755 /usr/local/bin/hermes-diff-check \
    && /usr/local/bin/hermes-diff-check --help >/dev/null

RUN set -eu; \
    hermes_target=""; \
    for candidate in \
      /opt/hermes/.venv/bin/hermes \
      /opt/hermes/bin/hermes \
      /opt/hermes-agent/.venv/bin/hermes \
      /opt/data/hermes-agent/.venv/bin/hermes \
      /root/.local/bin/hermes \
      /home/hermes/.local/bin/hermes; do \
      if [ -x "$candidate" ]; then \
        hermes_target="$candidate"; \
        break; \
      fi; \
    done; \
    if [ -z "$hermes_target" ]; then \
      echo "Hermes CLI executable was not found in the base image" >&2; \
      exit 1; \
    fi; \
    ln -sf "$hermes_target" /usr/local/bin/hermes; \
    /usr/local/bin/hermes --help >/dev/null

WORKDIR /workspace

USER root
