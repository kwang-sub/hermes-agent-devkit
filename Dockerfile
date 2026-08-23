FROM nousresearch/hermes-agent:latest

# Hermes 공식 이미지의 s6-overlay 초기화는 root로 시작해야 한다.
USER root

ARG GIT_VERSION=2.55.0

# Upstream update_cmd.py contains ``venv\Scripts`` in a normal docstring, which
# is an invalid Python escape. Patch the source rather than suppressing warnings.
COPY scripts/patch_hermes_syntax_warning.py /tmp/patch_hermes_syntax_warning.py
RUN python3 /tmp/patch_hermes_syntax_warning.py /opt/hermes/hermes_cli/update_cmd.py \
    && rm /tmp/patch_hermes_syntax_warning.py

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

# Hermes CLI를 스크립트/인터랙티브 셸에서도 `hermes` 명령으로 호출할 수 있도록
# 안정적인 PATH 엔트리를 보장한다.
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
