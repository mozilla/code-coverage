FROM python:3.12-slim

# Add worker user
RUN mkdir -p /builds/worker/artifacts && \
    groupadd --gid 1000 worker && \
    useradd --uid 1000 --gid worker --home-dir /builds/worker --shell /bin/bash worker && \
    chown -R worker:worker /builds/worker

# Install build deps (needed for mercurial, grcov setup)
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        git \
        gcc \
        curl \
        bzip2 \
        python3-dev \
        libgoogle-perftools4 \
        libatomic1 && \
    rm -rf /var/lib/apt/lists/*

# Install mercurial
RUN pip install --disable-pip-version-check --quiet --no-cache-dir mercurial==7.2

# Install grcov
RUN curl -sL https://github.com/mozilla/grcov/releases/download/v0.10.5/grcov-x86_64-unknown-linux-gnu-tc.tar.bz2 | tar -C /usr/bin -xjv && \
    chmod +x /usr/bin/grcov

# Clone version-control-tools
RUN hg clone -r 5b6e8298d035 https://hg.mozilla.org/hgcustom/version-control-tools /src/version-control-tools/ && \
    rm -rf /src/version-control-tools/.hg \
           /src/version-control-tools/ansible \
           /src/version-control-tools/docs \
           /src/version-control-tools/testing

# %include-run-task

# Cleanup build-only deps
RUN apt-get purge -y gcc curl bzip2 python3-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

ENV SHELL=/bin/bash \
    HOME=/builds/worker \
    PATH=/builds/worker/.local/bin:$PATH

VOLUME /builds/worker/checkouts
VOLUME /builds/worker/.cache

CMD ["/bin/bash"]
