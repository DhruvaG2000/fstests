# Muse 1.3 prompt: validate the Btrfs NOCOMPRESS coverage series

You are Muse 1.3 acting as a Linux filesystem test engineer on my real testing
infrastructure. I am the maintainer and have disposable VMs that can boot custom
kernels and run Btrfs fstests. Execute the work below; do not merely describe how
to do it. Return an evidence bundle that another reviewer can use to reproduce
both passing and failing results without access to your session history.

## 1. Objective and working rules

Validate the new tests and their assumptions, investigate the suspected defects,
and measure the two kernel performance hypotheses. Distinguish test defects,
kernel defects, btrfs-progs defects, unsupported configurations, and infrastructure
failures. A successful shell exit or an expected failure is not automatically a
passing fstest. Do not invent successful runs, build flags, traces, or timings.

Use the existing VM orchestration, console access and disposable storage setup.
Discover paths and tools instead of assuming this machine matches the authoring
PC. Proceed with available primary configurations before optional ones. Ask only
for information you cannot discover that actually blocks work, such as which
unidentified disks are disposable or how to access the intended VM. Existing
explicit scratch-device designations are sufficient; do not ask again per test.
Never infer that a disk is disposable merely from its name or lack of a mount.

Read applicable AGENTS.md files and repository instructions. Preserve unrelated
changes. Use tmux or the infrastructure's persistent job runner for long work;
keep the serial console and logs outside the devices the tests reformat. Do not
run two test jobs against the same scratch device. Do not push, send mailing-list
messages, or publish artifacts. Keep evidence locally for the maintainer.

First run the original series unchanged. If a test or tool needs repair, retain
its original failing run, make the smallest separate patch on a derived local
validation branch, and repeat the same configuration. Do not alter golden output,
skip checks, weaken assertions, or add feature skips simply to get green results.
Do not amend/rebase the supplied authoring branch. Include all diagnostic and
candidate-fix patches in your return bundle; do not imply they are accepted fixes.

## 2. Inputs and provenance

Locate the fstests branch `dg/nocomp-uapi-coverage`. Before this prompt was added,
its head was `93c9fadfa2ee4682c8bb2918006c2863536ea388`, based on
`5c9f93fedd00ba797f381966b163937ea352154f`. The latter contains the maintainer's
existing btrfs/354 basic NOCOMPRESS conversion test, which must remain intact.
The branch was local and not pushed at authoring time. If it is absent, inspect
any supplied `btrfs-uapi-coverage-series.mbox` and the available base repository;
do not pretend a remote branch exists. Ask for the series only if no copy exists.
Record the actual commit containing this prompt and the actual source under test.
A transferred patch series can have different commit IDs: record that mapping.

Read these files before running:

- BTRFS-UAPI-COVERAGE-PLAN.md
- BTRFS-IMPLEMENTATION-STATUS.md
- BTRFS-VM-HANDOFF.md
- BTRFS-PERFORMANCE-PROBES.md
- common/btrfs_nocomp and src/btrfs_defrag_range.c
- tests/btrfs/354 through tests/btrfs/365, including their .out files
- tools/btrfs-nocomp-perf.py

Reviewed source snapshots, useful for reproducing the original observations:

| Component | Commit |
|---|---|
| Kernel checkout | 3f2425f5b5bbbdd991ca9cdfd5502e68d8895998, next-20260918 |
| Fresher kernel compared | f5f84daefcd92d7a630066635ecea1433ed5eac7, next-20260925 |
| btrfs-progs checkout | 232a882f0228d26e3e77cede700c5731b0ba0846 |
| btrfs-progs devel compared | 4d02beef4badde9a5ba00081b4d4a35ae9ae2d05 |
| Upstream fstests compared | 3e1ee800e52a0f53d7d9a7809be1ffc80ec1788f |

The compared newer kernel had unchanged defrag.c, compression.c and Btrfs UAPI
header; ioctl.c/inode.c differences were const annotations. Recheck this if you
use an even newer tree. Record dates and full hashes, not just "latest". Fetching
new refs must not silently replace the baseline. Check the supplied mailing-list
audit before proposing an upstream test; refresh it if investigating a new fix.

Only local authoring checks were done: shell parsing, helper compilation with
warnings treated as errors, ABI interception, group parsing, and Python syntax.
Full authoring-machine build stopped at missing libtoolize; fsstress was not
built. There are no real Btrfs pass results or performance numbers to trust yet.

## 3. Create a persistent evidence workspace

Create a uniquely named campaign directory on a control/results filesystem,
separate from TEST_DEV, SCRATCH_DEV, their mounts, and the VM disks that will be
replaced. Use UTC timestamps and a run ID for every invocation. Copy or stream
results off the guest after each test, before another run can overwrite them.

Use this structure, adapting paths but keeping the same information:

```
CAMPAIGN/
  REPORT.md
  results.json
  manifest.json
  commands/                 # exact commands, start/end, status, working directory
  sources/                  # refs, status, patches, source checksums
  environment/              # guest, host/hypervisor if accessible, disk topology
  builds/kernel-CONFIG/
  builds/progs-VERSION/
  builds/fstests/
  runs/KERNEL-PROGS-CONFIG/TEST/REPETITION/
    console.log
    command.txt
    exit-status.txt
    results/                # complete fstests result directory for this invocation
    kernel-before.log
    kernel-after.log
    serial.log              # or a documented console-log reference
    run.json
  investigations/365-step/
  investigations/sparse-scan/
  investigations/rewrite-amplification/
  patches/                  # test fixes and experimental kernel/progs changes
  CHECKSUMS.sha256
```

Keep original logs unfiltered; make filtered summaries as additional files.
Preserve .full, .out.bad, .notrun, check.log, check.time, XML/JUnit and other files
actually emitted by this version. Preserve stdout AND stderr. Preserve the
underlying command's status when using tee. A logging wrapper may use this Bash
pattern, with log paths outside scratch:

```bash
run_logged() (
    set +e
    set -o pipefail
    log=$1
    shift
    mkdir -p "$(dirname "$log")" || exit 125
    printf '%q ' "$@" > "$log.command"
    printf '\n' >> "$log.command"
    date -u +%FT%TZ > "$log.started"
    "$@" 2>&1 | tee "$log"
    statuses=("${PIPESTATUS[@]}")
    printf 'command=%s tee=%s\n' "${statuses[0]}" "${statuses[1]}" > "$log.status"
    date -u +%FT%TZ > "$log.finished"
    (( statuses[0] == 0 )) || exit "${statuses[0]}"
    exit "${statuses[1]}"
)
```

Call failing tests in a conditional so an outer errexit does not discard later
collection. Capture collector failures too; a missing log must not become a
PASS. Record explicit skips and unavailable evidence with reasons. Do not dump
an entire environment containing credentials: collect only relevant build/test
variables. Do not bundle private SSH keys, tokens, unrelated home files or mail.

## 4. Inventory the actual environment

Collect before building and again after each kernel boot as appropriate:

- `uname -a`, `uname -r`, `/proc/version`, `/proc/cmdline`, boot ID, guest UTC
  time, distribution release, page size (`getconf PAGESIZE`), architecture,
  endianness, CPU count/model, guest RAM and swap, cgroup memory/CPU limits.
- VM/hypervisor version and launch/configuration details if accessible: CPU
  model, vCPU topology, memory, acceleration, storage controller, virtual disk
  format and backing chain, disk cache and discard modes, host filesystem and
  storage medium. State UNKNOWN for inaccessible host details rather than guess.
- Whether the guest or host is under CPU/memory/storage contention, guest steal
  time, frequency governor/turbo policy if observable, and any CPU pinning.
- `lsblk` with sizes, filesystem types, mount points, logical/physical sector
  sizes; `findmnt`; block-device major:minor numbers; mapping/loop/backing-file
  topology. Record the explicit disposable-device designation, distinguishing
  TEST_DEV from SCRATCH_DEV and the results disk. Include dm target versions.
- Actual test configuration: HOST_OPTIONS/local.config/selected sections,
  FSTYP, TEST_DEV/TEST_DIR, SCRATCH_DEV/SCRATCH_MNT, scratch pools, mount and mkfs
  options, exclusions, loop/dm setup. Redact irrelevant secrets only.
- Btrfs sectorsize, nodesize, incompat features, data/metadata profiles, logical
  filesystem size, quotas/qgroups if enabled, and effective mount options for
  the fixture. Capture superblock/tree information on an unmounted scratch
  filesystem when doing authoritative on-disk inspection; label live snapshots
  of metadata as potentially inconsistent.
- Versions and resolved executable paths for btrfs, mkfs.btrfs, xfs_io, fsstress,
  gcc/clang, linker, make, Python, bash, awk/gawk, autoconf/automake/libtoolize,
  util-linux, e2fsprogs/lsattr, dmsetup, strace, perf and bpftrace when used.

For each repository, save full HEAD, describe output, remotes without embedded
credentials, git status, tracked diff and relevant untracked source files. Save
submodule states if applicable. Dirty source must have a patch and checksums.

## 5. Build and prove which artifacts run

Install missing build dependencies inside the designated disposable build VM
using its normal package manager and project documentation. Record package names
and versions. Do not bypass a failing full build with only a compiled helper and
then claim the suite built. Preserve the first build failure and the corrected
build log. Choose parallelism appropriate to the VM's memory and record it.

### Kernel

Use an out-of-tree build directory and a configuration compatible with the VM's
boot/storage/rootfs. Save the complete final .config, its SHA-256, the seed config
and scripts/diffconfig output for changes. Record exact make commands and all
nondefault variables: ARCH, CROSS_COMPILE, CC, HOSTCC, LD, LLVM/LLVM_IAS, KCFLAGS,
KCPPFLAGS, LDFLAGS, O=, LOCALVERSION, KBUILD_BUILD_* and instrumentation flags.
Capture verbose compiler commands (V=1), tool versions, build duration and exit
status. Save vmlinux/System.map/build ID or sufficient symbol artifacts for
symbolization; save debug artifacts separately if too large for the main bundle.

Verify Btrfs and the VM's storage, compression and device-mapper dependencies.
For replay tests verify CONFIG_BLK_DEV_DM and CONFIG_DM_FLAKEY; also verify loop
support if using loop devices. Record effective relevant CONFIG_* values rather
than merely requesting them in a fragment. For a separate debug run consider
CONFIG_BTRFS_DEBUG, CONFIG_BTRFS_ASSERT, CONFIG_BTRFS_FS_RUN_SANITY_TESTS,
CONFIG_PROVE_LOCKING/LOCKDEP, and KASAN or KFENCE where supported. Save config
warnings and changed defaults. Do not enable every expensive debug option in
performance comparisons. Optional tracing builds need their actual ftrace,
kprobe, BPF/perf and symbol support recorded; verify probe availability at run time.

Boot using the existing disposable-VM mechanism. Then prove the running release,
config/build ID, boot ID and loaded Btrfs module match the intended build; save
module filename, vermagic and hash where modular. Merely compiling a kernel is
not evidence you booted it. Preserve full boot/serial logs, including any Btrfs
sanity-test failures. Note initramfs/module mismatches before testing.

### btrfs-progs and fstests

Follow each repository's build instructions. Save configure invocation,
config.log/config.status, generated config headers/builddefs where applicable,
compiler/linker options, library versions, feature selections and complete
verbose build output. Record whether LZO/ZSTD, experimental, zoned and other
relevant options were enabled. Save hashes of btrfs, mkfs.btrfs, xfs_io and the
new src/btrfs_defrag_range executable actually used. Do not impose arbitrary
CFLAGS on the baseline; record real flags, and keep special builds separate.

Build all of fstests (`make V=1` on this tree), not only src/btrfs_defrag_range.
Confirm ltp/fsstress and required helpers exist. Regenerate Btrfs group metadata
via the documented make target. Run bash parsing and staged/source whitespace
checks as supplementary checks. Full make success remains a separate result.

This harness resolves many tools from PATH. Inspect common/config and the Btrfs
initialization code instead of assuming an exported BTRFS_UTIL_PROG survives
configuration loading. Arrange the intended tools in PATH for the root test
process, verify mkfs.btrfs too, and record effective resolved paths. sudo can
replace PATH: show the resolution from the SAME root environment used by check.
If needed capture a one-off execve trace or add an isolated diagnostic wrapper
that logs the actual executable. Do not mix progs builds within a matrix cell.

## 6. Run matrix, in priority order

Finish the primary cell before attempting optional platform expansion. Keep
kernel/progs/config changes one at a time so failures are attributable.

| Priority | Cell | Purpose |
|---|---|---|
| P0 | Reviewed next-20260925 or a precisely identified newer kernel, reviewed/new progs, conventional 4KiB-page/4KiB-sector Btrfs | Main semantic validation |
| P0 | Same source on a separate debug/lockdep build | Diagnose races, replay, reservations and assertions |
| P0 | Same ordinary non-debug build on a quiet VM | Performance measurements |
| P1 | Kernel with original NOCOMPRESS support, e.g. a suitable 6.17 lineage, same new progs | Compatibility with initial supported behavior |
| P1 | Kernel lacking NOCOMPRESS but containing unknown-flag validation, same new progs | Unsupported flag must skip, not falsely pass |
| P1 | New kernel with progs lacking --nocomp | Userspace feature prerequisite behavior |
| P1 | 64KiB-page/4KiB-sector supported VM, same feature-capable sources | Subpage/folio behavior |
| P2 | Other supported sector/profile combinations and newest upstream versions | Broaden only after primary conclusions |

Determine feature presence from source/backports and actual probes, not release
numbers alone. Very old kernels predating unknown-flag validation may ignore
unknown flags: report resulting semantic failures distinctly, not as proof of
a modern-kernel regression. Some tests require 4KiB sectors; respect the declared
prerequisite instead of overriding it. Not all cells need the full expensive
repetition count. Report unavailable cells and why, without blocking P0 work.

Run tests separately initially to isolate results and establish runtime. Include
btrfs/354 as a baseline, then 355-364. Run 365 in a separate invocation: it is
intentionally outside auto and expected to expose a progs boundary defect.
Confirm exact test selection using `./check -n` first. Do not accidentally run
an unrestricted auto group or dangerous harness selftests.

Illustrative invocation, after choosing actual paths and confirming the root
process honors the selected config/results directory:

```bash
# CONFIG: absolute path to this VM's established disposable fstests config.
# TOOLS_PATH: the intended btrfs-progs directory plus required system tool paths.
# RUN: unique results directory outside all test/scratch filesystems.
mkdir -p "$RUN"
if run_logged "$RUN/console.log" sudo env PATH="$TOOLS_PATH" \
    HOST_OPTIONS="$CONFIG" RESULT_BASE="$RUN/results" \
    ./check btrfs/355; then
    rc=0
else
    rc=$?
fi
printf '%s\n' "$rc" > "$RUN/exit-status.txt"
# Now collect kernel/serial logs and the complete actual result directory.
```

Use the infrastructure's existing equivalent if configuration sections or remote
execution require it. Confirm where the harness really wrote results; a config
file can override environment choices. Do not rely on one big tee log alone.

On the primary cell, aim for three clean independent runs of 354-359 and 363-364,
ten each of 360-362, and at least three runs of 365 to establish behavior. Each
invocation must preserve its own results. After a repeatable first failure,
triage rather than blindly spending all repetitions on the same broken fixture.
After repair, repeat enough runs to establish stability and report the exact
numerator/denominator. On secondary cells start with one run per relevant test.
Report wall times and whether declared quick/auto runtime groups are realistic.

## 7. Mandatory per-test evidence and fixture audit

Treat these draft tests as code under review. Verify their prerequisites and
oracles; do not assume the authoring environment established their correctness.

| Test | Evidence and questions to answer |
|---|---|
| 354 | Initial maximal compressed extents, flag support, complete conversion, checksum after remount. Does the baseline work before diagnosing later cases? |
| 355 | Before/after ranged FIEMAP and full checksums; unchanged distant mappings; zero/oversized lengths and EOF errno. The tail fixture is 136KiB: its final 8KiB can compress into a 4KiB sector, unlike a 4KiB final unit. Check actual compression before asserting range behavior. |
| 356 | Prove compressed islands before fallocate; holes remain unmapped; unwritten ranges and beyond-EOF preallocation remain type2; size unchanged. Preserve offline extent items and zero-content checks. |
| 357 | Prove initial compressed inline extent; max_inline=4096 matches the 4KiB extent-map length for the skip branch; max_inline=0 must yield regular type1/compression0. Save both offline tree inspections and all short-tail contents/sizes. |
| 358 | Record mount policy, property and inode flags before/after; converted data remains plain while later writes compress. Include force and per-file property modes; diagnose inherited flags or policy leakage. |
| 359 | Prove initial sharing and compressed clone/snapshot; converted source checksum must match before overwrite; compare modified source and untouched peers to independent expected data after remount. |
| 360 | Confirm tests mount the flakey mapper, baseline is committed, later work is fsynced/logged, drop-writes recovery actually occurs. Save dm tables, serial log and expected/actual content. A clean remount or unnoticed full transaction commit is not strong proof of log-replay coverage. If commit timing masks replay, explain and improve determinism separately. |
| 361 | Worker exit statuses, timeout details, kernel messages, independent expected final image, hole state and all checksums. Show workers actually overlapped conversion where practical. A final checksum taken only from potentially corrupted actual data is not a sufficient oracle. |
| 362 | Initial allocation/free-space/extent state; filler progress; ioctl AND fsync status; remaining encoded extents after partial success; content preservation and successful retry after freeing space. A successful ioctl after partial progress is allowed by the reviewed code. Establish genuine space pressure, not just a generic command error or skipped dirty extents. |
| 363 | Exact raw flags, range, symbolic errno and unchanged mapping/content for rejection. Confirm COMPRESS|NOCOMPRESS gives EINVAL, unknown bits EOPNOTSUPP, valid transitions work and readonly returns EROFS. |
| 364 | Actual CLI and raw type/level values and errors for every row; valid compression and content preservation; invalid requests leave mappings unchanged. Raw helper arguments are numeric bytes. CLI `-c` has an attached optional argument (`-czstd`), not `-c zstd`. CLI -L0 omits the level flag; raw zlib level0 with COMPRESS_LEVEL is a different case. FIEMAP cannot prove the effective compression level. |
| 365 | Exact userspace ioctl intervals, file extent boundaries, target conversion and compressed sentinels outside the request; content and size after remount. Separate request-construction proof from actual on-disk effect. |

For each FAIL/SKIP, retain the exact failing assertion and prerequisite result.
Where a helper's parsing may be wrong, preserve original xfs_io/dump-tree output,
locale, tool version and parsed result. Check pipelines for masked exit statuses.
Evaluate fresh files after sync and after remount; label page-cache-only checks.

## 8. Investigate the --step boundary defect (T13/365)

The authoring-machine ioctl interposer observed this with progs v7.1:

```
command: btrfs filesystem defragment --nocomp -s 1M -l 384K --step 256K FILE
requested interval: [1048576, 1441792)
submitted interval 1: [1048576, 1310720), flags 10
submitted interval 2: [1310720, 1572864), flags 10
excess: 131072 bytes
```

That interposer mocked filesystem type and ioctl success; it did NOT prove disk
changes. Reproduce on real Btrfs with the original progs binary and test365.
Capture strace/ioctl decoding if supported, or another narrowly scoped recorder
that preserves actual ioctl execution. Save precise tool arguments and return
values. Compare the non-stepped control, 256KiB steps, and a step larger than
len. Tests may stop at the first failure: use separately named diagnostic runs
for later subcases, without changing the original result.

Inspect `cmds/filesystem.c:defrag_range_in_steps()`. If the final step is not
clipped to remaining length, prepare a minimal candidate progs patch in a
separate worktree. Consider finite lengths, default/to-EOF length, zero length,
overflow, empty files and files changing size; do not assert a complete fix from
one min() expression without reviewing those semantics. Build it with recorded
flags, rerun identical fixtures, and supply before/after traces and results.
Classify this as a userspace defect unless evidence independently implicates the
kernel. Do not change Linux to compensate for a bad userspace range request.

## 9. Measure the two kernel performance hypotheses

Use the non-debug performance cell, a quiet dedicated scratch device and fixed
VM resources. Report instrumentation overhead and backend disk details. First
run the unmodified `tools/btrfs-nocomp-perf.py` sparse/rewrite modes with an
explicit `--btrfs` path. Preserve stdout JSONL, stderr, the generated metadata and
results JSON, and fixture directories until evidence has been copied elsewhere.
The tool never formats the device; ensure the intended scratch filesystem is
mounted before invoking it. Correctness tests can leave it unmounted.

The current probe implements only minimal controlled cases, not every proposed
matrix row. Its hardcoded ioctl encodings are restricted to listed architectures.
If porting it, verify constants and struct layouts against native compiled Linux
headers. A missing probe facility or unsupported architecture is not a Btrfs
failure. A zero probe exit status means data invariants held, not good performance.

### T11: sparse traversal

Each sample has two 128KiB compressed islands, with gaps of 64MiB, 1GiB and 16GiB.
The source suggests traversal work can scale with logical hole size because the
initial target collection cannot propagate the end of a skipped hole to the
cluster caller. This is a hypothesis, not a measured result.

Collect per-gap cluster-call counts, task CPU and wall time, allocation/mapping
state, and optional dedicated-device read/write counters. Prefer a count of
`defrag_one_cluster` filtered to the printed worker PID, following the companion
probe instructions and --pause support. Verify that the function is probeable;
account for inlining/LTO. Reset counts per sample. Do not count all processes or
userspace --step calls and call that kernel traversal work.

Repeat at least five fresh fixture runs, distinguishing warm/cold metadata state.
Do not drop global caches on a shared host. Use isolated VM resets or a documented
scratch-specific strategy for cold runs; identify what is actually cold. Compare
median, range and all raw samples; normalize by allocated bytes and gap size.
Approximate 256KiB-step scaling supports wasted hole traversal, but no fixed time
threshold proves a bug. Verify data, holes and the absence of compressed islands
afterward. Separate CPU/lookup growth from block I/O or hypervisor throttling.
If useful and feasible, test a small experimental kernel skip-ahead change on a
separate branch, preserving invariants and returning its patch and A/B evidence.

### T12: repeated rewrites and COW amplification

The probe compares ordinary defrag against two NOCOMPRESS calls on uncompressed
written files with a readonly snapshot. Capture pre/post physical FIEMAP,
checksums of live/snapshot copies, extent item counts when needed, device I/O,
CPU/wall time and Btrfs space/du accounting. Verify whether the initial file is
actually contiguous: useful consolidation of fragmented extents is not needless
rewriting. Distinguish extent-item splits from physical fragmentation.

Use five fresh runs. Add isolated diagnostic variants if baseline results merit
it: no snapshot, mixed compressed/plain islands, and a snapshot before every
repeat to expose retention. Do not expect each repeated rewrite to retain a new
snapshot copy if no new snapshot was created. Report data amplification relative
to bytes that actually needed decompression, separating metadata writes and
background traffic. Do not divide by zero and present infinity as a measured
ratio; for all-plain data, report absolute unnecessary rewrite bytes.

Device counters include other activity, and task CPU excludes asynchronous
Btrfs workers. Use appropriately scoped block tracing/perf for stronger attribution
where available. Save raw traces and the analysis method; do not infer total
filesystem CPU from the calling task alone. Current NOCOMPRESS does not promise
physical idempotence: a result can demonstrate an optimization opportunity
without violating ABI correctness. Report that distinction explicitly.

## 10. Failures, hangs and additional experiments

Preserve the first failure, then reproduce it on a fresh fixture and classify
it with a confidence level. For kernel warnings/oopses, keep the complete stack,
symbols/build ID, taint and preceding messages. For hangs, use out-of-band VM
console diagnostics, blocked-task stacks and lock information supported by that
VM; save evidence before recovery. Record timeouts as TIMEOUT, not PASS/FAIL by
assertion. Preserve the host serial log if the guest dies. Reboot only the
identified test VM when needed; log recovery and do not reuse an uncertain dirty
filesystem as a supposedly fresh baseline.

Prefer narrowly scoped `bash -x`, ioctl tracing, FIEMAP, stat/property reads and
offline tree inspection on diagnostic repeats. Tracing changes timing: retain an
untraced reproduction too. Do not run `btrfs check --repair` to hide corruption.
For an offline check, unmount and record exact read-only check invocation/status.
Retain a reproducible small image or image recipe if corruption is found; do not
include huge VM disks in the main bundle without a size justification.

If time permits after P0, perform meaningful negative controls on separate kernel
or progs branches: suppress NOCOMPRESS handling, suppress its policy reset, or
change a validation branch and verify the appropriate test fails. Return the
mutation patch and result. Never modify the principal source checkout or claim
coverage strength without actually observing the negative control. Do not
introduce broad kernel changes merely to exercise the testing workflow.

## 11. Required final report and machine-readable results

Deliver REPORT.md with:

1. A concise verdict: what really passed, what failed, what skipped, what timed
   out, which cells were unavailable, and what remains untested.
2. Full source/build/boot provenance, tool paths, effective flags/configuration,
   VM/storage details and exact reproduction commands.
3. A per-test/per-cell table with attempts, pass/fail/skip/timeout counts, wall
   times, failing assertions and links to raw evidence. Keep baseline and patched
   runs separate. State whether quick/auto grouping needs correction.
4. Each finding's classification, confidence, minimal reproducer, actual versus
   expected behavior, relevant source path/function, and candidate patch if any.
5. A before/after conclusion for test365 supported by real ioctl/mapping results.
6. T11/T12 raw sample tables and structural/I/O evidence, noise controls and
   measurement limitations. Say whether a kernel change is justified, only an
   optimization investigation is supported, or evidence is inconclusive.
7. A test-quality review: unreliable prerequisites, fragile output parsing,
   missing data/layout checks, misleading skips, weak race/replay coverage and
   any changes required before upstream submission.
8. A prioritized follow-up list with exact missing data needed by the reviewer.

Provide results.json with one record per invocation, not one aggregate per test.
Use null plus a reason for unavailable values. Include at least:

```
run_id, started_utc, finished_utc, guest_id, boot_id,
source {kernel_sha, kernel_dirty_patch, progs_sha, fstests_sha, test_patch},
build {kernel_config_sha256, kernel_build_id, compiler, flags_manifest,
       btrfs_binary_sha256, mkfs_binary_sha256, helper_sha256},
configuration {page_size, sectorsize, nodesize, profiles,
               mount_options, mkfs_options, host_options_path},
test_id, repetition, exact_command, command_exit_status,
status [PASS|FAIL|SKIP|TIMEOUT|INFRA_ERROR|NOT_RUN],
reason, wall_seconds, raw_result_directory, console_log,
kernel_log, serial_log, fixture_evidence, diagnostic_patch, notes
```

Store performance samples separately with the same provenance/run IDs and
explicit units. Keep authoritative files such as .config alongside summaries;
no selective config excerpt can replace the full config.

Generate checksums for all bundle files (excluding the checksum file itself),
then create a compressed archive of the evidence directory. Inspect the archive
listing and verify checksums after a test extraction. Save the archive's own
SHA-256 separately. Keep large symbols/traces in an indexed supplemental archive
if necessary. Do not auto-upload anything; return local artifact paths and sizes
so the maintainer can transfer the bundle back for review.

Before concluding, verify the report links resolve inside the bundle, every
reported PASS has its matching result files and boot/build identity, no SKIP was
counted as PASS, and every experimental patch is included. If resource limits
prevent finishing, deliver the collected evidence and a precise resumable work
list with next commands instead of replacing results with a proposed plan.
