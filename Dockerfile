ARG HERMES_BASE_IMAGE=nousresearch/hermes-agent:v2026.8.16.2

FROM eclipse-temurin:8-jdk-jammy AS jdk8
FROM eclipse-temurin:17-jdk-jammy AS jdk17
FROM eclipse-temurin:21-jdk-jammy AS jdk21

FROM ${HERMES_BASE_IMAGE}

USER root

ARG GIT_VERSION=2.55.0

COPY scripts/patch_hermes_syntax_warning.py /tmp/patch_hermes_syntax_warning.py
RUN python3 /tmp/patch_hermes_syntax_warning.py /opt/hermes/hermes_cli/update_cmd.py \
    && rm /tmp/patch_hermes_syntax_warning.py

COPY scripts/patch_hermes_kanban_terminal.py /tmp/patch_hermes_kanban_terminal.py
RUN python3 /tmp/patch_hermes_kanban_terminal.py --self-test \
    && python3 /tmp/patch_hermes_kanban_terminal.py /opt/hermes/agent/kanban_stop.py \
    && rm /tmp/patch_hermes_kanban_terminal.py

# DevKit baseline tools. Gradle itself is not installed globally; hermes-java
# prepares the exact project-owned distribution under the persistent /opt/data
# Gradle root on first use.
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
    && curl -fsSL \
        "https://www.kernel.org/pub/software/scm/git/git-${GIT_VERSION}.tar.xz" \
        -o /tmp/git.tar.xz \
    && mkdir -p /tmp/git-src \
    && tar -xJf /tmp/git.tar.xz -C /tmp/git-src --strip-components=1 \
    && cd /tmp/git-src \
    && make NO_RUST=1 prefix=/usr/local all \
    && make NO_RUST=1 prefix=/usr/local install \
    && git --version \
    && rm -rf /tmp/git-src /tmp/git.tar.xz \
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

# All Hermes Gradle state is persistent and outside bind-mounted source trees.
# Project Gradle versions still come from gradle-wrapper.properties.
ENV HERMES_GRADLE_ROOT=/opt/data/gradle
ENV HERMES_GRADLE_USER_HOME=/opt/data/gradle/user-home
ENV HERMES_GRADLE_DIST_ROOT=/opt/data/gradle/distributions
ENV HERMES_GRADLE_DOWNLOAD_ROOT=/opt/data/gradle/downloads
ENV HERMES_GRADLE_LOCK_ROOT=/opt/data/gradle/locks
ENV HERMES_GRADLE_PROJECT_CACHE_ROOT=/opt/data/gradle/project-cache
ENV GRADLE_USER_HOME=/opt/data/gradle/user-home

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
COPY --chmod=0755 scripts/hermes-diff-check.py /usr/local/bin/hermes-diff-check

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
