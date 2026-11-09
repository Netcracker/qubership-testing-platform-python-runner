FROM python:3.14-alpine3.22

ENV HOME_EX=/app
ENV HOME=/app
ENV PATH="/app/venv/bin:$PATH"

RUN echo "https://dl-cdn.alpinelinux.org/alpine/v3.22/community/" >/etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/v3.22/main/" >>/etc/apk/repositories && \
    apk add --update --no-cache --no-check-certificate \
        git=2.49.1-r0 \
        curl=8.14.1-r4 \
        wget=1.25.0-r1 \
        bash=5.2.37-r0 \
        unzip=6.0-r15 \
        nano=8.4-r0 \
        inotify-tools=4.23.9.0-r0 \
        jq=1.8.2-r0 \
        build-base=0.5-r3 \
        python3-dev=3.12.16-r0 \
        musl-dev=1.2.5-r13 \
        libffi-dev=3.4.8-r0 \
        py3-requests=2.33.1-r0 \
        py3-urllib3=1.26.20-r1 \
        py3-certifi=2026.10.23-r0 && \
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

RUN python -m venv "$HOME_EX/venv"

COPY requirements.txt $HOME_EX/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt \
        --timeout=120

# Pytest plugin bundled with this image, not published to PyPI: it registers itself via the
# "pytest11" entry point, so every test suite this runner executes picks it up automatically.
COPY pytest-plugins/atp-b3-trace pytest-plugins/atp-b3-trace
RUN pip install --no-cache-dir --no-deps pytest-plugins/atp-b3-trace && \
    rm -rf pytest-plugins

COPY --chown=runner:runner scripts/ /scripts/
COPY --chown=runner:runner scripts/runtimes/python-setup.sh scripts/runtime-setup.sh
COPY --chown=runner:runner --chmod=755 entrypoint.sh $HOME_EX/entrypoint.sh

# chgrp 0 + g=u supports OpenShift restricted-v2 (arbitrary UID, member of gid 0)
# while Kubernetes can still run the container as USER 1007 via owner permissions.
# Group-writable /etc/passwd lets the entrypoint register the arbitrary UID.
RUN chown -R runner:runner /app /scripts \
    && chgrp -R 0 /app /scripts \
    && chmod -R g=u /app /scripts \
    && chmod g+rx /app /scripts \
    && chgrp 0 /etc/passwd \
    && chmod g=u /etc/passwd

USER 1007

ENTRYPOINT ["/app/entrypoint.sh"]

