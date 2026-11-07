# SPDX-License-Identifier: GPL-2.0-only
# Reviewed amd64 Ubuntu 24.04 base and fixed Ubuntu archive snapshot.
FROM ubuntu:24.04@sha256:78d4744ead1f5b19b04d0df558ab182a5300903900755e515b2ca4d10eb2044d
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C TZ=UTC
RUN printf 'APT::Snapshot "20261106T000000Z";\nAcquire::Retries "2";\n' > /etc/apt/apt.conf.d/50snapshot \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential gcc-13-aarch64-linux-gnu binutils-aarch64-linux-gnu \
       bc bison flex libssl-dev libelf-dev dwarves python3 python3-dev \
       rsync device-tree-compiler u-boot-tools kmod git ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s aarch64-linux-gnu-gcc-13 /usr/local/bin/aarch64-linux-gnu-gcc
WORKDIR /src
