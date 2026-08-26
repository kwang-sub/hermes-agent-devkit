ARG HERMES_BASE_IMAGE=nousresearch/hermes-agent:v2026.8.16.2

# Keep project JDKs independent from the Hermes base image. Temurin images expose
# their JDK under /opt/java/openjdk; copying the trees avoids apt repository
# differences and keeps Java 8/17/21 available on both amd64 and arm64 builds.
FROM eclipse-temurin:8-jdk-jammy AS jdk8
FROM eclipse-temurin:17-jdk-jammy AS jdk17
FROM eclipse-temurin:21-jdk-jammy AS jdk21

FROM ${HERMES_BASE_IMAGE}

# Hermes 공식 이미지의 s6-overlay 초기화는 root로 시작해야 한다.
USER root

ARG GIT_VERSION=2.55.0

# Upstream Hermes releases have historically contained a normal-docstring
# venv\Scripts SyntaxWarning. The helper patches the known old form, accepts an
# already-fixed upstream form, and always performs a strict compile check.
COPY scripts/patch_hermes_syntax_warning.py /tmp/patch_hermes_syntax_warning.py
RUN python3 /tmp/patch_hermes_syntax_warning.py /opt/hermes/hermes_cli/update_cmd.py \
    && rm /tmp/patch_hermes_syntax_warning.py

# DevKit baseline tools. Gradle/Maven are intentionally not installed globally:
# repositories use gradlew/mvnw so the build-tool version remains project-owned.
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

# Java 17 is the DevKit default. Project bootstrap detects the repository target
# and writes .hermes/toolchain.env; `hermes-java <command...>` then executes with
# the selected project JDK without modifying the repository build files.
ENV JAVA_HOME_8=/opt/jdks/temurin-8
ENV JAVA_HOME_17=/opt/jdks/temurin-17
ENV JAVA_HOME_21=/opt/jdks/temurin-21
ENV JAVA_HOME=/opt/jdks/temurin-17
ENV PATH="/opt/jdks/temurin-17/bin:${PATH}"

# Login shells in the upstream image may rebuild PATH and drop JAVA_HOME/bin.
# Stable /usr/local/bin links keep the DevKit default JDK available regardless of
# shell startup behavior. Project-specific builds still use hermes-java.
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

# Hermes CLI를 스크립트/인터랙티브 셸에서도 `hermes` 명령으로 호출할 수 있도록
# 안정적인 PATH 엔트리를 보장한다. Runtime scripts should still prefer the
# immutable /opt/hermes/.venv/bin/hermes path when reproducibility matters.
RUN if ! command -v hermes >/dev/null 2>&1; then \
      set -eu; \
      for candidate in \
        /usr/local/bin/hermes \
        /opt/hermes/bin/hermes \
        /opt/hermes/.venv/bin/hermes \
        /opt/hermes-agent/.venv/bin/hermes \
        /opt/data/hermes-agent/.venv/bin/hermes \
        /root/.local/bin/hermes \
        /home/hermes/.local/bin/hermes; do \
        if [ -x "$candidate" ]; then \
          ln -sf "$candidate" /usr/local/bin/hermes; \
          break; \
        fi; \
      done; \
    fi \
    && command -v hermes \
    && hermes --help >/dev/null

WORKDIR /workspace

# 중요:
# USER hermes 로 변경하지 않는다.
# 컨테이너 시작 시 s6-overlay/root bootstrap이 /opt/data 및 프로필을 초기화한 뒤
# Hermes 서비스 자체가 필요한 사용자 권한으로 실행된다.
USER root
