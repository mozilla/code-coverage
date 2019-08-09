#!/bin/bash -ex
GRCOV_VERSION="v0.5.3"
MERCURIAL_VERSION="4.8"

apt-get update
apt-get install --no-install-recommends -y mercurial=4.8.* curl lcov bzip2

# Setup grcov
curl -L https://github.com/mozilla/grcov/releases/download/$GRCOV_VERSION/grcov-linux-x86_64.tar.bz2 | tar -C /usr/bin -xjv
chmod +x /usr/bin/grcov

# Setup mercurial with needed extensions
hg clone https://hg.mozilla.org/hgcustom/version-control-tools /src/version-control-tools/
ln -s /src/bot/ci/hgrc $HOME/.hgrc

# Cleanup
apt-get autoremove -y
rm -rf /src/version-control-tools/.hg
