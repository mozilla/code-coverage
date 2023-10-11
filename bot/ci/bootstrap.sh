#!/bin/bash -ex
GRCOV_VERSION="v0.7.1"
MERCURIAL_VERSION="6.5.2"
VERSION_CONTROL_TOOLS_REV="d0d8dd1934dd"

apt-get update
# libgoogle-perftools4 is currently required for grcov (until https://github.com/mozilla/grcov/issues/403 is fixed).
apt-get install --no-install-recommends -y gcc curl bzip2 python-dev-is-python3 libgoogle-perftools4

pip install --disable-pip-version-check --quiet --no-cache-dir mercurial==$MERCURIAL_VERSION

# Setup grcov
curl -L https://github.com/mozilla/grcov/releases/download/$GRCOV_VERSION/grcov-tcmalloc-linux-x86_64.tar.bz2 | tar -C /usr/bin -xjv
chmod +x /usr/bin/grcov

# Setup mercurial with needed extensions
hg clone -r $VERSION_CONTROL_TOOLS_REV https://hg.mozilla.org/hgcustom/version-control-tools /src/version-control-tools/
ln -s /src/bot/ci/hgrc $HOME/.hgrc

# Cleanup
apt-get purge -y gcc curl bzip2 python-dev-is-python3
apt-get autoremove -y
rm -rf /var/lib/apt/lists/*
rm -rf /src/version-control-tools/.hg /src/version-control-tools/ansible /src/version-control-tools/docs /src/version-control-tools/testing
