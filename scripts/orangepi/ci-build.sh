#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Run inside the pinned builder, with the source read-only and /work writable.
set -euo pipefail
src=$(cd -- "$(dirname -- "$0")/../.." && pwd)
git config --global --add safe.directory "$src"
export O=${O:-/work/out} JOBS=${JOBS:-4}
export ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
export LOCALVERSION="-g$(git -C "$src" rev-parse --short=12 HEAD)"
art=${ARTIFACTS:-/work/artifacts}
mkdir -p "$art"
exec > >(tee "$art/build.log") 2>&1
test ! -e "$O/.config" || { echo 'Use a fresh output directory for CI' >&2; exit 1; }
dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort > "$art/builder-packages.tsv"
aarch64-linux-gnu-gcc --version
bash "$src/scripts/orangepi/build.sh"
dtb="$O/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-4-pro.dtb"
test "$(fdtget "$dtb" /soc@3000000/sdmmc@4022000 status)" = disabled
test "$(fdtget "$dtb" /soc@3000000/ethernet@4500000 phy-mode)" = rgmii-id
phy=/soc@3000000/ethernet@4500000/mdio0@0/ethernet-phy@1
test "$(fdtget -tu "$dtb" "$phy" motorcomm,clk-out-frequency-hz)" = 125000000
test "$(fdtget -tu "$dtb" "$phy" rx-internal-delay-ps)" = 1900
test "$(fdtget -tu "$dtb" "$phy" tx-internal-delay-ps)" = 150
release=$(make -s -C "$src" O="$O" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
    LOCALVERSION="$LOCALVERSION" kernelrelease)
make -C "$src" O="$O" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
    INSTALL_MOD_PATH=/work/modules modules_install
rm -f "/work/modules/lib/modules/$release/build" "/work/modules/lib/modules/$release/source"
epoch=$(git -C "$src" show -s --format=%ct HEAD)
tar --sort=name --mtime="@$epoch" --owner=0 --group=0 --numeric-owner \
    -C /work/modules -cf - lib | gzip -n > "$art/modules.tar.gz"
cp "$O/arch/arm64/boot/Image" "$dtb" "$O/.config" "$O/System.map" "$O/Module.symvers" "$art/"
cp "$src/scripts/orangepi/sources.json" "$art/sources.json"
cp "$src/scripts/orangepi/ci/Dockerfile" "$art/builder.Dockerfile"
git -C "$src" archive --format=tar HEAD | gzip -n > "$art/source.tar.gz"
export KERNEL_SOURCE="$src" KERNEL_RELEASE="$release" KERNEL_ARTIFACTS="$art"
python3 - <<'PY'
import hashlib, json, os, pathlib, subprocess
src=pathlib.Path(os.environ['KERNEL_SOURCE']); art=pathlib.Path(os.environ['KERNEL_ARTIFACTS'])
manifest={'source_commit':subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip(),
          'kernel_release':os.environ['KERNEL_RELEASE'], 'boot_qualified':False,
          'emmc':'disabled; no hardware available for qualification',
          'outputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(art.iterdir())
                     if p.is_file() and p.name != 'build.log'}}
(art/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
PY
(cd "$art" && sha256sum Image sun60i-a733-orangepi-4-pro.dtb .config System.map \
    Module.symvers modules.tar.gz source.tar.gz sources.json builder.Dockerfile \
    builder-packages.tsv manifest.json > SHA256SUMS)
