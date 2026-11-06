#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
src=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
export ARCH=arm64
export CROSS_COMPILE=${CROSS_COMPILE:-aarch64-linux-gnu-}
export KBUILD_BUILD_TIMESTAMP='Fri Nov 6 00:00:00 UTC 2026'
export KBUILD_BUILD_USER=builder KBUILD_BUILD_HOST=orangepi-kernel KBUILD_BUILD_VERSION=1
unset KBUILD_MODPOST_WARN KBUILD_MODPOST_NOFINAL
out=${O:-"$src/../out-orangepi-6.18"}
mkdir -p "$out"
out=$(CDPATH= cd -- "$out" && pwd)
test "$out" != "$src"
make -C "$src" O="$out" orangepi_4_pro_defconfig
for symbol in AW_BSP AW_PCIE_RC AW_CADENCE_COMBOPHY BLK_DEV_NVME EXT4_FS AW_MMC AW_STMMAC_ETH MOTORCOMM_PHY AW_THERMAL AW_CPUFREQ_DT ARM_PSCI_CPUIDLE AW_REGULATOR_AXP2101; do
    grep -qx "CONFIG_${symbol}=y" "$out/.config" || {
        echo "Required built-in feature missing: $symbol" >&2
        exit 1
    }
done
make -C "$src" O="$out" -j"${JOBS:-8}" Image modules allwinner/sun60i-a733-orangepi-4-pro.dtb
