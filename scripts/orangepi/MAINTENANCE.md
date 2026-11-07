# Maintaining the 6.18 port

This is Linux 6.18 LTS plus selected, pinned Xunlong BSP (board support package)
source. The BSP is committed in this tree; builds do not download another driver
tree or substitute opaque driver binaries. Optional eMMC stays disabled in the
board DTS because there is no module available for debugging or testing. CI checks
that restriction and the qualified Ethernet clock/timing properties in the DTB.

## Weekly candidates

`Weekly Linux 6.18 candidate` runs on **Friday at 21:17 AEST** (11:17 UTC), and
can also be started manually. GitHub schedules are best-effort, not exact timers.
It resolves the latest non-RC `v6.18.N` tag once from the official stable tree,
fetches that exact object and verifies its signature against the pinned Greg
Kroah-Hartman/Sasha Levin keys. It rejects unrelated history, rollback and a
changed existing release. Public keys came from kernel.org WKD; fingerprints are
listed at <https://www.kernel.org/signature.html>. Key changes require review.

New stable releases are **merged**, preserving the port's public history and
tested commit identities. Conflicts stop the job; no automated agent resolves
them. The updater records the new upstream commit in `sources.json`, publishes a
uniquely named `codex/update-*` candidate branch and builds that exact commit in
the same workflow. A successful build gets an exact-commit check and a draft PR.
The updater never merges the PR, installs a kernel, modifies SPI or reboots a
board. With no new release it rebuilds the current default branch.

Vendor BSP branch drift creates a separate review issue; it is never silently
imported. Upstream stable fixes do not maintain BSP-only drivers automatically.
Other kernel series need separate branches and qualification.

## Shared build

The clean Git checkout, committed config/DTS and `build.sh` are the build inputs.
The container pins an amd64 Ubuntu image digest and the Ubuntu archive snapshot
`20261106T000000Z`. The snapshot service currently promises at least two years
of retention; review/refresh it before then. Build actions are commit-pinned.
Compilation runs with networking disabled and the source mounted read-only.
The same command works on an amd64 Linux host with Docker:

```sh
docker build --platform linux/amd64 -t opi-kernel-builder scripts/orangepi/ci
mkdir -p ../opi-ci-output
docker run --rm --network none --platform linux/amd64 \
  -v "$PWD:/src:ro" -v "$(cd ../opi-ci-output && pwd):/work" \
  -e JOBS=4 opi-kernel-builder bash /src/scripts/orangepi/ci-build.sh
```

Use a full checkout and an empty output directory for an independent build.
Artifacts include Image, DTB, modules, config, vmlinux/System.map, corresponding source
archive, package inventory, manifest, checksums and logs. Module link failures are
fatal. Each source commit gets a distinct kernel/module release. Inputs are
pinned and build identity is fixed; byte-for-byte reproducibility across hosts
has not yet been demonstrated. These are candidate artifacts, not Debian packages
or a binary release channel. GitHub retains them for 30 days; retain qualified
boot artifacts and their exact source independently.

## Recovery and promotion

Preserve a complete known-good kernel, DTB, initramfs and matching module tree.
Select candidates one boot at a time and consume the request before handoff, so
the next reset selects known-good. Boot-file load errors should fall back in the
same boot. A hung kernel still requires a reset: current hardware qualification
uses an external Mac/Tapo supervisor. Native watchdog handoff is unqualified.

SPI-to-NVMe boot can retain this design: SPI holds firmware, NVMe holds separate
known-good/candidate boot sets and the selection state, and SD is rescue media.
The existing implementation stores its selection state on SD. An NVMe selector,
SD boot priority/rescue and missing-image/hang/power-cycle recovery must be
fault-tested before removing that dependency. Do not describe the migration as
already qualified. Shared root/data and firmware corruption are outside kernel
fallback; kernel slots are not full OS A/B.

Only an exact artifact that passes supervised board checks can be qualified or
promoted. Preserve the previous known-good set when doing so. Successful cloud
compilation provides no hardware, eMMC or power qualification.

## Failure reporting

Build/merge failures open or update one failure issue with source IDs, failed
stage and a run/log link. A later successful cycle closes it. The manual
`failure_probe` input exercises reporting without updating or building a kernel.
The report job runs trusted default-workflow code with limited write permissions;
build jobs have read-only tokens, no LAN credentials and no deployment secrets.
Allow GitHub Actions to create PRs in this repository's Actions settings.

Enable GitHub Actions email notifications for failed workflows at
<https://github.com/settings/notifications>. Scheduled notifications go to the
user who last changed the cron entry (or re-enabled it), subject to their email
settings. Issue creation and a red workflow do not prove email delivery.
GitHub can delay/drop scheduled runs and disable schedules after 60 days of
repository inactivity. A separate heartbeat alarm is still needed to detect a
job that never starts; it is not supplied by this repository's own schedule.
Automatic agent repairs remain a separate future change.
