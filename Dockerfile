FROM python:3.14-alpine3.22

ENV HOME_EX=/app

RUN echo "https://dl-cdn.alpinelinux.org/alpine/v3.22/community/" >/etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/v3.22/main/" >>/etc/apk/repositories && \
    apk add --update --no-cache --no-check-certificate \
        curl=8.14.1-r2 \
        wget=1.25.0-r1 \
        bash=5.2.37-r0 \
        unzip=6.0-r15 \
        nano=8.4-r0 \
        inotify-tools=4.23.9.0-r0 \
        jq=1.8.1-r0 \
        build-base=0.5-r3 \
        python3-dev=3.12.12-r0 \
        musl-dev=1.2.5-r10 \
        libffi-dev=3.4.8-r0 \
        py3-requests=2.32.5-r0 \
        py3-urllib3=1.26.20-r1 \
        py3-certifi=2025.4.26-r0 && \
    rm -rf /var/lib/apt/lists/*

RUN wget -q -O /tmp/s5cmd.tar.gz \
    https://github.com/peak/s5cmd/releases/download/v2.3.0/s5cmd_2.3.0_Linux-64bit.tar.gz && \
    tar -xzf /tmp/s5cmd.tar.gz -C /tmp && \
    mv /tmp/s5cmd /usr/local/bin/ && \
    chmod +x /usr/local/bin/s5cmd && \
    rm -rf /tmp/s5cmd*

RUN addgroup -g 1007 runner && \
    adduser -u 1007 -G runner -D -h "$HOME_EX" runner && \
    mkdir -p "$HOME_EX" && \
    chown -R runner:runner "$HOME_EX"

WORKDIR $HOME_EX

RUN pip install --no-cache-dir --break-system-packages -r requirements.txt \
        --timeout=120

COPY requirements.txt $HOME_EX/requirements.txt

COPY scripts/ $HOME_EX/scripts/
COPY scripts/runtimes/python-setup.sh $HOME_EX/scripts/runtime-setup.sh

COPY --chown=runner:runner --chmod=755 entrypoint.sh $HOME_EX/entrypoint.sh

USER 1007

ENTRYPOINT ["/app/entrypoint.sh"]

