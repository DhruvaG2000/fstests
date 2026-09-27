# Running the opt-in performance probes

These implement the measurement portions of plan T11 and T12. They are not in
fstests' auto group and do not claim that a performance defect is already proven.
Use the maintainer's normal disposable Btrfs VM scratch filesystem, already
mounted. The tool never formats a device and retains its uniquely named fixtures
and JSON results. Snapshot fixtures require the usual Btrfs privileges.

From the fstests repository:

```sh
sudo python3 tools/btrfs-nocomp-perf.py sparse --scratch-dir "$SCRATCH_MNT" \
    --btrfs /path/to/new/btrfs | tee /tmp/nocomp-sparse.jsonl
sudo python3 tools/btrfs-nocomp-perf.py rewrite --scratch-dir "$SCRATCH_MNT" \
    --btrfs /path/to/new/btrfs | tee /tmp/nocomp-rewrite.jsonl
```

Optionally add `--block-stat /sys/class/block/vdb/stat` for the device actually
backing scratch. Do not blindly use vdb: resolve the device in your VM. Counters
include metadata and other device traffic. A dedicated quiet device is needed;
stacked devices can double-count if you sum multiple layers. Task CPU time does
not include Btrfs worker-thread CPU. Do not present these fields as exact total
filesystem work.

## T11: structural count alongside timing

Add `--pause`; the probe prints its PID immediately before each defrag operation.
On a kernel exposing the function to kprobes, run in a second terminal, replacing
12345 with that printed PID:

```sh
sudo bpftrace -e 'kprobe:defrag_one_cluster /pid == 12345/ { @clusters = count(); }'
```

Press Enter in the probe terminal, wait for the JSON sample and next pause, then
stop bpftrace and save its count with that gap size. Restart tracing for the next
sample. The sparse mode uses a raw whole-file NOCOMPRESS ioctl, so userspace step
splitting is excluded. Check function availability first (`bpftrace -l
'kprobe:*defrag_one_cluster*'`); LTO/inlining/configurations may prevent this
probe. If unavailable, report timing as exploratory and add an equivalent
private function trace or temporary kernel counter in your test build. Lack of
instrumentation is not a filesystem failure.

The three files contain the same 256KiB of written data with gaps of 64MiB,
1GiB and 16GiB. Record cluster counts and CPU versus gap size. About 256, 4096,
and 65536 hole-related cluster iterations would support the source-derived
linear-scan hypothesis. A skip-ahead implementation should not need one call
per hole cluster. Do not use those approximate counts as a fixed golden output:
there are extra calls around data and alignment. Compression fixtures and hole
preservation are checked independently. On a slow debug VM, use an external
watchdog such as `timeout 300s`; a timeout is an investigation result, not proof
of a generic regression or a kernel hang.

## T12: rewrite amplification and snapshot retention

The tool creates two 32MiB uncompressed written files in a new subvolume and a
read-only snapshot. It compares ordinary defrag with two NOCOMPRESS calls. Each
sample includes pre/post FIEMAP, CPU/wall time, optional device sectors and
`btrfs filesystem du` output. Checksums of both live files and snapshot copies
are verified after each operation.

Inspect the initial extent layout: if the file is fragmented, some rewrite may
be useful. For an already contiguous layout, changed physical mappings and
large write counts on every NOCOMPRESS invocation support unnecessary rewrite
work. The first rewrite can pin the old snapshot extents; without another
snapshot between passes, the second rewrite need not pin a second extra copy.
The tool makes no claim that allocated bytes must monotonically increase after
every pass. Distinguish logical extent item splits from physical contiguity.
No-compression does not currently promise physical idempotence, so discuss any
eligibility optimization before turning this into a mandatory regression test.

The mixed compressed/uncompressed variant and cold-cache/remount variants in
the plan remain follow-up experiments; this initial tool implements the
minimal controlled cases. No trace setup or global cache dropping is performed
by the script.

## Interpretation and retention

Exit 0 means the experiment finished and its data invariants held; it does NOT
mean performance was good. Exit 77 reports an unsupported operation. Other
failures include a missing fixture, data mismatch, tool failure or ioctl error;
keep the complete error and fixture for diagnosis. `metadata.json` records
kernel, progs and mount options. Store source hashes from the plan alongside
results, and record compiler/configuration for instrumented kernels.

All created paths are printed. Remove them with normal Btrfs subvolume cleanup
on the disposable VM after collecting results; the tool deliberately does not
remove subvolumes or data automatically.