# Btrfs NOCOMPRESS coverage implementation status

Date: 2026-09-27. Branch: `dg/nocomp-uapi-coverage`, based on
`5c9f93fedd00ba797f381966b163937ea352154f`. The existing btrfs/354 was
preserved. This branch has local signed commits only; it has not been pushed.

| Plan case | Test | Commit | Assertion focus |
|---|---|---|---|
| T01 | btrfs/355 | c18d7915656f | Middle-range conversion, unaffected sentinels, EOF/empty-file cases |
| T02 | btrfs/356 | af7bd9d93f4a | Written islands, hole, unwritten and beyond-EOF preallocation |
| T03 | btrfs/357 | 30794b37889b | Inline eligibility, regular conversion with max_inline=0, short tails |
| T04 | btrfs/358 | 148b9815ef57 | Compression policy after conversion under mount, force and file property modes |
| T05 | btrfs/359 | 31406c603512 | Reflink/snapshot isolation and reference cleanup |
| T06 | btrfs/360 | 518c62319431 | Fsynced conversion and overwrite across dm-flakey log replay |
| T07 | btrfs/361 | e9bdad8239bf | Bounded concurrent writes/punching, deterministic quiescent result |
| T08 | btrfs/362 | 4d1d8e491ffd | Space-constrained expansion, partial progress and retry |
| T09 | btrfs/363 | a2f2b234d30c | Raw flag errors, no side effects, valid transitions, EROFS |
| T10 | btrfs/364 | aa8e024fd7f8 | CLI and raw level boundaries including signed zstd values |
| T13 | btrfs/365 | 28ce4db2b782 | Stepped range must stop at requested end; deliberately outside auto |

The shared shell and C ioctl helper are in `common/btrfs_nocomp` and
`src/btrfs_defrag_range.c`, committed as `0d428b70fd41`. It probes the feature
on nonempty data and skips only recognized unsupported results; subsequent
unexpected ioctl errors fail. The helper reports symbolic errno and accepts
numeric flags, start, length, type and signed level. This allows T09/T10 to
submit requests that the userspace CLI cannot express. The helper's ABI layout
was checked with a local ioctl interposer for flags 5, zstd type 3, level -15
and length 131072.

T11/T12 remain measurements rather than auto regressions. The opt-in tool
`tools/btrfs-nocomp-perf.py` was committed as `b6979c69483b`; its instructions
are `BTRFS-PERFORMANCE-PROBES.md` (`514bdc46fc16`). The full coverage plan is
`BTRFS-UAPI-COVERAGE-PLAN.md` (`52219131f3ca`), and the VM handoff is
`BTRFS-VM-HANDOFF.md` (`1295ebda33db`). The latter lists required disposable
device runs and result capture. Commit `72a92acb132f` normalizes source and
Markdown file modes to match nearby fstests files.

Local validation completed: `bash -n` for btrfs/355-365 and the shared shell
helper; direct `gcc -Wall -Wextra -Werror` compilation of the new C helper;
raw ABI interposer check; `tools/mkgroupfile` parsing of all new group tags;
Python syntax check of the performance probe; and staged whitespace checks
before each commit. The performance tool's non-Btrfs mount guard was exercised
against a host temporary directory. `tests/btrfs/group.list` was regenerated
with `tools/mkgroupfile` and is not a tracked change.

Full `make` stopped before configure because this WSL installation lacks
`libtoolize`; `./check -n` then stopped because `fsstress` is not built. No
device-backed test was run: this authoring environment has no explicitly
disposable scratch device. There are no claimed kernel pass results for
btrfs/355-365 and no T11/T12 performance measurements. VM validation must
confirm fixture eligibility, remount/replay behavior, error-path reliability,
and the on-disk effect of T13 before these tests are proposed upstream.

The T13 userspace range construction issue was reproduced separately with an
ioctl recorder on the locally built btrfs-progs v7.1: a 1MiB start, 384KiB
length and 256KiB step produced requests [1048576, 1310720) and
[1310720, 1572864), overshooting the requested end by 128KiB. This is
userspace evidence, not a Btrfs filesystem result. The reviewed kernel
baseline was linux-next `3f2425f5b5bbbdd991ca9cdfd5502e68d8895998`;
the fresher next-20260925 commit `f5f84daefcd92d7a630066635ecea1433ed5eac7`
was fetched for comparison without changing the checkout. The btrfs-progs
checkout was `232a882f0228d26e3e77cede700c5731b0ba0846`; fetched devel
was `4d02beef4badde9a5ba00081b4d4a35ae9ae2d05`.

The local `AGENTS.md` and `maildir/` were not staged or modified by this work.
