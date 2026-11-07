# SPDX-License-Identifier: GPL-2.0-only
# Reviewed amd64 Ubuntu 24.04 base and fixed Ubuntu archive snapshot.
FROM ubuntu:24.04@sha256:78d4744ead1f5b19b04d0df558ab182a5300903900755e515b2ca4d10eb2044d
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C TZ=UTC
# The minimal Ubuntu image has no CA bundle. Bootstrap from a checksum-pinned
# Ubuntu package using BuildKit's HTTPS fetch before apt accesses the snapshot.
ADD --checksum=sha256:641de77d8f142cfd62a1a6f964ba67b20754d3337c480efb529d086075a06c9a \
    https://snapshot.ubuntu.com/ubuntu/20261106T000000Z/pool/main/c/ca-certificates/ca-certificates_20240203_all.deb /tmp/ca-certificates.deb
RUN mkdir -p /tmp/ca /etc/ssl/certs \
    && dpkg-deb -x /tmp/ca-certificates.deb /tmp/ca \
    && cat /tmp/ca/usr/share/ca-certificates/mozilla/*.crt > /etc/ssl/certs/ca-certificates.crt \
    && rm -rf /tmp/ca /tmp/ca-certificates.deb
RUN printf 'APT::Snapshot "20261106T000000Z";\nAcquire::Retries "2";\n' > /etc/apt/apt.conf.d/50snapshot \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential gcc-13-aarch64-linux-gnu binutils-aarch64-linux-gnu \
       bc bison flex libssl-dev libelf-dev dwarves python3 python3-dev \
       rsync device-tree-compiler u-boot-tools kmod git ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s aarch64-linux-gnu-gcc-13 /usr/local/bin/aarch64-linux-gnu-gcc
WORKDIR /src
