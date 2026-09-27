# VM validation handoff

Repository: /home/dhruva/workspace/fstests. Branch and commit list are in
BTRFS-IMPLEMENTATION-STATUS.md. The original btrfs/354 was preserved.

Build with the VM's normal fstests dependencies and use the established scratch
configuration. The new C helper is included in src/Makefile. Local authoring
checks do not replace these device-backed runs:

```sh
make
make -C tests/btrfs group.list
./check -n btrfs/{355..364}
sudo ./check btrfs/{355..364}
```

Use your normal configuration selection flags/environment with these commands.
Run the test that exercises the existing progs step-boundary bug separately:

```sh
./check -n btrfs/365
sudo ./check btrfs/365
```

365 intentionally omits the auto group. It is expected to expose the observed
request overshoot on the reviewed progs code; its real Btrfs effect still needs
VM confirmation. It is not appropriate to mark it passing because it failed as
expected: preserve the failure report, then rerun with a separately reviewed
progs fix.

| Test | Primary coverage |
|---|---|
| 355 | Range clipping, sector boundary and EOF behavior |
| 356 | Holes and unwritten/preallocated islands |
| 357 | Inline eligibility, conversion to regular storage and short tails |
| 358 | Transient policy restoration and future compression |
| 359 | Reflink and read-only snapshot isolation |
| 360 | Fsync and dm-flakey log replay |
| 361 | Concurrent writes, hole punching and conversion |
| 362 | Space-constrained expansion, partial progress and retry |
| 363 | Invalid raw flags, valid flag transitions and read-only rejection |
| 364 | Compression-level bounds and signed zstd levels |
| 365 | Userspace --step final-range protection |

Run the performance investigations using BTRFS-PERFORMANCE-PROBES.md. They
produce measurements rather than hardware-dependent pass/fail thresholds.

Record the kernel/progs/fstests hashes, compiler/config, page and sector sizes,
mkfs and mount options, .full logs, .out.bad/.notrun files and kernel messages.
Test at least the fetched next-20260925 source and an initial-support kernel;
use an older kernel to verify skip behavior. Test subpage configurations on
appropriate VMs. Repeat 360-362 to assess race, replay and ENOSPC stability.

The authoring environment could compile the new standalone C helper with
warnings treated as errors and parse shell/group metadata. Its full suite build
was blocked by missing libtoolize; check selection also requires built suite
binaries such as fsstress. No filesystem test or performance measurement was
reported as passed from that environment.