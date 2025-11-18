FROM debian:trixie-slim

ENV HOME_EX=/app

RUN groupadd -g 1007 runner && \
    useradd -u 1007 -g runner -d "$HOME_EX" -s /bin/bash runner && \
    mkdir -p "$HOME_EX" && \
    chown -R runner:runner "$HOME_EX"

WORKDIR $HOME_EX

COPY requirements.txt $HOME_EX/requirements.txt

RUN set -eux; \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        curl=8.14.1-2 \
        wget=1.25.0-2 \
        bash=5.2.37-2+b5 \
        unzip=6.0-29 \
        nano=8.4-1 \
        inotify-tools=4.23.9.0-2+b1 \
        jq=1.7.1-6+deb13u1 \
        python3=3.13.5-1 \
        python3-pip=25.1.1+dfsg-1 \
        python3-requests=2.32.3+dfsg-5 \
        python3-urllib3=2.3.0-3 \
        python3-certifi=2025.1.31+ds-1 && \
    rm -rf /var/lib/apt/lists/*

RUN wget -q -O /tmp/s5cmd.tar.gz \
    https://github.com/peak/s5cmd/releases/download/v2.3.0/s5cmd_2.3.0_Linux-64bit.tar.gz && \
    tar -xzf /tmp/s5cmd.tar.gz -C /tmp && \
    mv /tmp/s5cmd /usr/local/bin/ && \
    chmod +x /usr/local/bin/s5cmd && \
    rm -rf /tmp/s5cmd*

RUN pip install --no-cache-dir --break-system-packages -r requirements.txt \
        --timeout=120

COPY scripts/ $HOME_EX/scripts/
COPY scripts/runtimes/python-setup.sh $HOME_EX/scripts/runtime-setup.sh

COPY --chown=runner:runner --chmod=755 entrypoint.sh $HOME_EX/entrypoint.sh

USER 1007

ENTRYPOINT ["/app/entrypoint.sh"]
