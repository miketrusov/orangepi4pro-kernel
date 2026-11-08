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
If repository policy prevents PR creation, it opens a candidate-ready issue
with a compare link for manual PR creation. It does not expand repository-wide
approval permissions or introduce a privileged personal token.
The CI updater never merges the PR, connects to the LAN, modifies SPI or
reboots a board. A separate enrolled-board controller pulls candidate releases
and independently trials and promotes them. With no new release it rebuilds the current default branch.

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
pinned and build identity is fixed. Two independent GitHub-hosted builds of
`3cd18207e19d4011010c76b7425d2a226d3fda0a` produced identical manifests and all
12 checksummed outputs: [default build](https://github.com/miketrusov/orangepi4pro-kernel/actions/runs/42373053872)
and [weekly rehearsal](https://github.com/miketrusov/orangepi4pro-kernel/actions/runs/42373368728).
This demonstrates reproducibility for that pinned CI setup, not arbitrary
toolchains or Debian initramfs generation. The build has zero errors or MODPOST
warnings; 24 nonfatal compiler warnings remain in the imported BSP source.
These are candidate artifacts, not Debian packages. After a successful weekly
build, a trusted publisher verifies the exact source and all manifest checksums,
then publishes `opi4pro-v6.18.N-SHA12` as a prerelease. The release stays draft
until the update bundle, identity, corresponding source and build/debug evidence
are uploaded. Published candidates are never overwritten. Actions artifacts
expire after 30 days; release assets supply the durable public pull feed.

## Recovery and promotion

Preserve a complete original recovery kernel, DTB, initramfs and module tree.
The board-side controller stages an inactive A/B boot set, consumes the trial
request before handoff and leaves an in-progress marker. A finite Linux
watchdog takeover deadline covers initramfs stalls; PID1 then owns the 16-second
sunxi watchdog. A separate 120-second userspace health deadline handles a live
PID1 with an unhealthy boot. Only matching kernel/assets/modules, NVMe root,
wired LAN, SSH and local service health permit promotion.

A pending marker surviving reset selects the previous good set at most once,
then original recovery. File/CRC/state failures fall back in the same boot.
Unknown state never authorizes a candidate. Failed source IDs are quarantined;
original recovery pauses automatic installs by default. The poll timer needs
no GitHub token or incoming LAN access. Its allowed repository, 6.18 channel
and watchdog implementation are pinned by Ansible. Kernel and firmware changes
outside that qualified contract require explicit review.

On 2026-11-08, exact watchdog source `795a17b351bd53b5c2ffd3953d541b67e6ba898e`
passed healthy PID1 adoption, pre-kernel stall, initramfs stall and runtime panic
on one Orange Pi 4 Pro. All three faults reset to original recovery without an
external power cycle. Sixteen real U-Boot Hush sandbox cases passed for the A/B
selector. The migrated v2 bootstrap passed a live canary/next-recovery check.
Managed slot A passed enrollment and health promotion; deliberately masking SSH
in inactive slot B caused automatic rollback to A with the SSH health failure
persisted in the journal. No external power cycle was needed for that rollback.
The external Tapo supervisor remains a development rescue, not a requirement
for these qualified native watchdog paths. Cloud compilation alone does not
qualify a candidate for other boards or peripherals.

The complete [hosted rehearsal](https://github.com/miketrusov/orangepi4pro-kernel/actions/runs/42423057232)
passed preparation, build, publication and reporting. On the reference board,
[release a5488081141c](https://github.com/miketrusov/orangepi4pro-kernel/releases/tag/opi4pro-v6.18.62-a5488081141c)
was anonymously pulled, validated, staged into inactive B, booted and promoted
locally with A retained as previous-good. It then passed clean shutdown, verified
outlet OFF/ON and cold-boot health promotion. PID1 owns the active 16-second
watchdog; there are no failed services. Hourly public polling is enabled, and a
repeat pull correctly reported up-to-date without rebooting. This qualifies that
exact artifact on one headless reference board, not every board/peripheral.
The operator-specific controller is managed through separate Ansible playbooks;
this kernel fork does not supply a generic disk installer or board enrollment.
Retired local candidate/module/input trees are retained; staging checks free
space and stops safely rather than pruning unowned files. Automatic retention
cleanup and measured idle power/sustained load qualification remain future work.

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
Issues must be enabled in repository settings; they are enabled on this fork.
On 2026-11-07 the intentional probe created
[issue #1](https://github.com/miketrusov/orangepi4pro-kernel/issues/1), and a
successful result report commented and closed it. This verifies issue delivery
and recovery handling. The owner confirmed receiving the failure emails on
2026-11-08.
The report job runs trusted default-workflow code with limited write permissions;
build jobs have read-only tokens, no LAN credentials and no deployment secrets.
Repository-wide PR approval permissions remain unchanged.

Enable GitHub Actions email notifications for failed workflows at
<https://github.com/settings/notifications>. Scheduled notifications go to the
user who last changed the cron entry (or re-enabled it), subject to their email
settings. Issue creation and a red workflow do not prove email delivery.
GitHub can delay/drop scheduled runs and disable schedules after 60 days of
repository inactivity. A separate heartbeat alarm is still needed to detect a
job that never starts; it is not supplied by this repository's own schedule.
Automatic agent repairs remain a separate future change.

## Optional agent-assisted repairs

Keep repair attempts separate from deterministic update/build/publish jobs.
A future monthly workflow can consume the existing failure issue and exact log,
give Copilot CLI one bounded repair attempt, rebuild and open a draft PR
(or a compare-link issue where repository PR policy requires it).
Do not let the repair job alter the recovery/qualification gates or merge its
own changes. Copilot CLI programmatic mode is available on Free, but the hosted
issue-assigned cloud agent requires a paid plan. Personal-allowance CLI runs
need a dedicated Copilot token; usage and authentication must be checked before
enabling. A monthly schedule limits attempts, not token consumption.
No agent repair workflow is enabled here yet. The weekly signed-stable build
schedule remains unchanged. See the current [Actions CLI setup](https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/automate-with-actions)
and [plan comparison](https://github.com/features/copilot/plans) before enabling;
keep its credentials and write step separate from untrusted repair execution.

Board-side rollback emails use the separate `board-failure.yml` dispatch
workflow. The board needs a dedicated fine-grained token restricted to this
repository with Actions read/write permission. Without that credential,
rollback/quarantine is automatic but board failure reporting remains local;
CI build/merge/publication emails work independently. The Ansible controller
accepts the token as `vault_orangepi_kernel_notify_token` in encrypted
`ansible/secrets/orangepi-kernel.yml` and installs it root-only. Do not put the
token in source control or paste it into issues/logs. Each acknowledged source
report is recorded locally to suppress repeated notifications.

The optional notification workflow passed a deliberate red-state probe on
2026-11-08: [callback test](https://github.com/miketrusov/orangepi4pro-kernel/actions/runs/42453238912).
The reference board still has no callback credential; this probe validates the
workflow, not unattended authenticated delivery from the board.
