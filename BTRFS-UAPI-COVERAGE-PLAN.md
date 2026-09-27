# Btrfs defrag UAPI coverage plan

Date: 2026-09-27. Scope: online btrfs-progs defrag paths and their Linux UAPI, with emphasis on --nocomp and compression levels. This is a focused gap analysis, not a claim to audit every btrfs-progs command. Thirteen independently useful cases follow; the existing whole-file conversion test is not counted. Performance findings below are hypotheses until measured, not promises of bugs.

## Baselines and duplication audit

* Working fstests: /home/dhruva/workspace/fstests, branch dg/nocmp-test-1, HEAD 5c9f93fedd00ba797f381966b163937ea352154f. Preserve this branch and its untracked AGENTS.md/maildir. Existing tests/btrfs/354 checks whole-file conversion, FIEMAP ENCODED removal and checksum after remount under compress=zlib. Its tracked remote branch has a different history; do not reset/rebase it as part of this work.
* Fresh upstream fstests HEAD fetched September 27: 3e1ee800e52a0f53d7d9a7809be1ffc80ec1788f. Searches of tests/, common/, src/ for nocomp, DEFRAG_RANGE and defrag level use found no new flag/level coverage. The upstream delta has no defrag test addition.
* Kernel source: /home/dhruva/workspace/linux-next, 3f2425f5b5bbbdd991ca9cdfd5502e68d8895998 (next-20260918). Fresh origin/master was subsequently fetched as f5f84daefcd92d7a630066635ecea1433ed5eac7 (next-20260925). Reviewed the delta: defrag.c, compression.c and the UAPI header are unchanged; inode.c/ioctl.c differ only in const mnt_idmap annotations. The coverage conclusions apply to that newer head too. The checked-out branch was preserved.
* btrfs-progs checkout: /home/dhruva/btrfs-progs at 232a882f0228d26e3e77cede700c5731b0ba0846. Fresh devel is 4d02beef4badde9a5ba00081b4d4a35ae9ae2d05; its two additional changes concern zones, not defrag. No nocomp/defrag-step/defrag-level tests found in its tests tree.
* New tmux session: btrfs-coverage. Attach with `tmux attach -t btrfs-coverage`. User explicitly requested a new session, overriding workspace guidance to reuse codex.
* Existing overlapping coverage: btrfs/005 (legacy defrag ranges); 256 (tiny-file termination); 257 (ordinary defrag skips prealloc); 258/263 (autodefrag holes and unnecessary rewrites); 259 (ordinary defrag skips maximal compressed extents); 260 (recompression, holes/prealloc); 280/281 (FIEMAP sharing); 325 (merging adjacent extent items); generic/018 and 324 (ordinary defrag layouts). These cover shared machinery but never request the new no-compression mode. Reuse their helpers; do not market their existing assertions as new.

Mailing-list checks and exclusions:

1. Your v2 basic test has Qu Wenruo's Reviewed-by on September 20, 2026: https://marc.info/?l=fstests&m=178994089778774&w=4 ; message ID 0090e23b-bbc5-45e0-a46e-9a5b2eb2dc72@gmx.com. Do not duplicate it.
2. Filipe Manana's September 15 patch expands `_btrfs_stress_defrag()` to all algorithms: https://marc.info/?l=fstests&m=178948907773481&w=4 ; message ID 97cbd58be421a2b35567031d58002f73493b3316.1789486109.git.fdmanana@suse.com. Do not propose merely adding zstd to that helper. Its `nocompress` argument means ordinary defrag, NOT --nocomp.
3. Original kernel flag patch: https://lore.kernel.org/linux-btrfs/20250709142917.23293-1-dsterba@suse.com/ . An archived copy exists in local maildir. Kernel commit 009b2056cb25 introduces the mode; 173431b274a9 validates unknown flags.
4. Additional pending inline test found in local maildir: Filipe Manana, September 15, 2026, `[PATCH v2] btrfs: test that we don't create pointless compressed inline extents`, https://lore.kernel.org/linux-btrfs/5acebd19e4e5b9b825497947ef32527cc2103147.1789484528.git.fdmanana@suse.com/ . It asserts that inline compression saves space; T03 instead exercises explicit no-compression conversion and eligibility. It also proposes ID354, so all local IDs are provisional and need renumbering on submission.

4a. Historical compressed-extent CPU/I/O test discussion: https://marc.info/?r=1&t=164326271200002&w=2 . This is existing ordinary-defrag coverage, not a new proposal.
5. Search performed across linux-btrfs/fstests indexed archives for nocomp, NOCOMPRESS, defrag compression level, defrag step and September 2026 defrag patches. Direct lore query pages were inaccessible through the web tool; indexed MARC messages, local maildir and fresh upstream source were used. No matching proposed tests found beyond the above, but this is a bounded search, not proof of absence from all in-flight mail. Repeat subject/body searches before posting each series.

Primary source links: https://github.com/kdave/btrfs-progs ; https://kernel.googlesource.com/pub/scm/linux/kernel/git/kdave/btrfs-progs/+/HEAD/Documentation/btrfs-filesystem.rst ; https://git.kernel.org/pub/scm/fs/xfs/xfstests-dev.git/ . Pin source hashes above when reproducing observations.

## Kernel contract and shared implementation rules

`include/uapi/linux/btrfs.h:617-625` defines COMPRESS=1, START_IO=2, COMPRESS_LEVEL=4, NOCOMPRESS=8. `fs/btrfs/ioctl.c:btrfs_ioctl_defrag()` rejects unknown bits with EOPNOTSUPP and COMPRESS|NOCOMPRESS with EINVAL; it adds START_IO and overrides the extent threshold for either conversion mode. `fs/btrfs/defrag.c:btrfs_defrag_file()` sets transient inode defrag compression policy; `inode.c:inode_need_compress()` recognizes BTRFS_DEFRAG_DONT_COMPRESS. `defrag_collect_targets()` still skips holes, prealloc, inline extents within max_inline, delalloc and extents under writeback. Therefore do not assert that one call converts dirty or inline data that is deliberately excluded.

Use `./new btrfs` to allocate IDs; the T labels below are plan IDs, not reserved upstream test numbers. Expected stdout should be only the QA header plus `Silence is golden` unless an ABI errno matrix is intentionally printed. Keep detailed extent maps, raw errors and checksums in .full. Check every fixture/write/defrag return status. FIEMAP absence of ENCODED is insufficient by itself: require a nonempty written mapping, correct range and preserved contents. Use fresh files per matrix row. Compare checksums after remount as well as before; capture size and relevant inode attributes. Avoid exact physical addresses or exact compressed sizes in .out.

Feature gating: require the command option, then probe the ioctl on a nonempty file. Only a recognized unsupported result should skip; unexpected errors fail. A raw helper can return symbolic errno and exit 77 for EOPNOTSUPP/ENOTTY during the explicit probe. Do not convert any arbitrary defrag failure into a skip. Older kernels predating flag validation can ignore flags; document that semantic tests then fail. `_wants_kernel_commit` records intent, it is not a substitute for feature detection.

Use sector-aligned fixtures; where exact byte layouts assume 4K, explicitly require 4K sectors. Exercise 64K-page/4K-sector VMs separately for subpage coverage. `--nocomp` is not chattr +m and should not permanently disable future compression. START_IO starts writeback, not a promise of crash durability: sync/fsync before mapping/durability assertions.

## T01 — Bounded conversion and EOF arithmetic (P0, quick)

Path: `cmds/filesystem.c:cmd_filesystem_defrag()` -s/-l -> `btrfs_defrag_file()` range clipping/sector alignment -> `defrag_one_cluster()`.

Create a 4MiB compressed file in 128KiB writes. Convert the middle aligned 512KiB using --nocomp -s 1M -l 512K. Assert ENCODED disappears inside, while distant prefix/suffix extents remain encoded and retain mappings; verify full-file checksum and size after remount. Separate subcases cover a final partial sector, len=0 (to EOF), oversized len (clipped to EOF), start at EOF on a nonempty file (EINVAL via raw helper), and an empty file (success). For unaligned boundaries, allow sector rounding and only inspect distant sentinels, not a guessed byte-exact physical extent split.

Gap: 005 exercises legacy ranges, 354 converts the whole file. Benefit/bugs: catches loss of start/len, off-by-one EOF handling, overflow interpretation, extent-range corruption and unintended decompression of unrelated data. Groups: auto quick defrag compress fiemap.

## T02 — Sparse and preallocated islands (P0, quick)

Path: --nocomp -> `defrag_collect_targets()` hole/prealloc filters and `defrag_one_range()` reservations.

Construct compressed written islands separated by a hole and by an unwritten fallocated range. Sync compressed data BEFORE fallocate so the inode PREALLOC flag does not invalidate setup. Confirm each fixture state. Convert all; require all written islands become unencoded, hole interiors remain unmapped, and prealloc interiors remain unwritten at their original mapping. Verify zero reads and pattern checks after remount. Include preallocation beyond EOF without extending logical size.

Gap: 257 tests ordinary mode; 260 requests another compression algorithm. Benefit/bugs: catches accidental allocation of holes, loss of unwritten reservations, stale zero data, leaks and conversion-mode bypass of prealloc guards. Groups: auto quick defrag compress prealloc fiemap.

## T03 — Inline conversion eligibility and short tails (P1, quick)

Path: --nocomp -> `defrag_collect_targets()` inline/max_inline guard, folio preparation and EOF.

Create verified 2048-byte compressed inline data with max_inline=4096 on a 4KiB-sector filesystem. The extent map length is sectorsize (file-item.c:btrfs_extent_item_to_extent_map), so max_inline=2048 would not exercise the skip branch even for a 2048-byte file. First show --nocomp leaves an eligible-to-stay-inline extent alone (current source contract). Remount with max_inline=0, then convert the same data and require regular uncompressed storage. Include lengths 1, sector-1, sector+1 and 128KiB+1 using separate files; only demand conversion where setup proves a convertible compressed extent. Check size, complete content and zero tail behavior after remount. Use offline dump-tree for inline/type proof rather than infer inline from tiny stat blocks.

Gap: 256 checks tiny-file termination; 354's tiny file is only a flag probe. Benefit/bugs: exposes hangs, wrong inline eligibility, tail corruption and assumptions that no ENCODED automatically means conversion. Groups: auto quick defrag compress.

## T04 — Compression policy resumes after conversion (P0, quick)

Path: `btrfs_defrag_file()` temporary defrag_compress reset -> `inode_need_compress()`/writeback, btrfs property set/get.

Matrix: compress=zlib; compress-force=zstd; per-file compression property with mount compression disabled. Write/sync compressed region, --nocomp it, verify unencoded. Then append fresh highly compressible data in a new aligned range, sync and assert it compresses under the original policy; the converted region stays uncompressed. Verify property and inode compression flags did not change. Add sequence -czstd/-L followed by --nocomp followed by an ordinary append to expose stale level/type state. Use a supported algorithm probe rather than silently accepting a missing fixture.

Gap: 354 does no post-defrag write. Benefit/bugs: catches persistent no-compression state, ignored force/property precedence and compression-level leakage. This also protects storage efficiency after maintenance. Groups: auto quick defrag compress.

## T05 — Reflink and snapshot isolation (P0, quick)

Path: --nocomp -> COW/ordered extents/delayed references; subvolume snapshot and clone paths.

Create compressed data, reflink a second file and snapshot its subvolume. Prove initial sharing. Convert one writable file; verify its data is unencoded but clone and snapshot remain encoded, unchanged and readable. Overwrite the converted copy, verify other copies remain unchanged, then remove a copy and scrub or remount to exercise reference cleanup. Check sharing only where mappings prove it; do not demand defrag preserve sharing (it intentionally breaks it).

Gap: 280/281 test sharing reports without this mode; 354 has no shared extents. Benefit/bugs: catches cross-inode corruption, incorrect backrefs, premature extent release and wrong checksum accounting. Groups: auto quick defrag compress clone snapshot fiemap.

## T06 — fsync log replay after conversion and overwrite (P1)

Path: --nocomp conversion -> ordered extents -> fsync tree logging and recovery.

Use existing dm-flakey log-replay infrastructure. Commit a compressed baseline; convert a middle range, overwrite a separate range, fsync the file (and parent for any newly created name), simulate power loss by the established flakey drop-writes sequence, remount/replay. Compare with independently constructed expected data and size. Require persisted target mappings be unencoded where that representation is guaranteed by completed writeback; the primary mandatory crash oracle is acknowledged data durability. Repeat with a reflink source kept intact. Do not use clean unmount as a crash substitute or assume START_IO alone implies durability.

Gap: existing log tests cannot submit NOCOMPRESS. Benefit/bugs: stale logged extents, missing checksum replay, wrong replacement ranges or lost acknowledged writes. Groups: auto log recovery defrag compress, after checking group names.

## T07 — Conversion racing dirty writes and hole punching (P1)

Path: --nocomp -> target revalidation under extent lock, delalloc/writeback skips, folio locking.

Bounded worker rewrites fixed-pattern regions and alternately punches/refills another region while a worker runs range conversion. Track worker statuses; stop and reap all workers in cleanup. After joining, write a deterministic final pattern, sync, perform one final quiescent --nocomp pass, remount and verify contents, holes and mappings. Do not require transient concurrent data to be uncompressed, since dirty ranges can be skipped by design. Check kernel log through the normal harness and enforce a generous hang watchdog rather than a throughput limit.

Gap: existing common stress does ordinary defrag/recompression, not transient DONT_COMPRESS state. Benefit/bugs: reservation/folio deadlocks, stale target lists after punching, data loss, incomplete policy reset and hangs. Groups: auto stress defrag compress punch.

## T08 — ENOSPC expansion and recovery (P1)

Path: compressed-to-uncompressed expansion -> `btrfs_delalloc_reserve_space()` and partial-progress cleanup.

On a small dedicated scratch filesystem write a compressible payload whose uncompressed size exceeds remaining allocatable space, retain a known removable filler, sync, then request --nocomp. Record ioctl and subsequent fsync errors. Do not insist on ENOSPC at one specific syscall: partial progress or delayed allocation errors are permitted. Assert no corruption and no kernel hang; verify the filesystem remains usable. Remove only the test filler, sync, retry conversion and require success and original data. Append a fresh compressible range to prove policy restoration also on the error path. Include unmount/check after freeing space if supported by harness.

Gap: no conversion-specific decompression expansion test. Benefit/bugs: leaked reservations, false successful completion with missing data, stale defrag policy, error masking after partial progress, permanent ENOSPC. Groups: auto enospc defrag compress. Avoid quick until measured.

## T09 — Raw defrag ABI validation and no side effects (P0, quick)

Path: `btrfs_ioctl_defrag()` flag validator and `btrfs_defrag_file()` parameter validation. CLI checks cannot cover malformed UAPI combinations.

Add a small C helper using a fixed-size zero-initialized `btrfs_ioctl_defrag_range_args`; permit flags, start, len, type, level and return symbolic errno. On nonempty files test COMPRESS|NOCOMPRESS => EINVAL, an unknown high flag => EOPNOTSUPP, valid NOCOMPRESS => success, and legacy COMPRESS => success. Repeat invalid requests with START_IO and prove data/mappings/policy unchanged. COMPRESS_LEVEL without COMPRESS is currently ignored; do not invent a rejection contract. Read-only subvolume/mount => EROFS is useful secondary coverage, while unrelated permission matrices are not the focus.

Gap: no current src helper submits these flag combinations. Benefit/bugs: ABI validation regressions, incorrect precedence and writes despite rejected requests. Groups: auto quick defrag compress.

## T10 — Compression-level ABI boundaries and signedness (P0, quick)

Path: CLI -c/-L -> union fields in defrag args -> `btrfs_compress_level_valid()` and compressor selection.

On fresh nonempty files exercise zlib 1/9/0 and invalid -1/10; zstd -15/-1/0/1/15 and invalid -16/16; lzo's source-defined accepted levels 0 and 1, with 2 rejected. Explicit raw COMPRESS_LEVEL with zlib level 0 is rejected; the CLI -L0 succeeds because it omits the level flag and uses the default. Keep those cases distinct. Raw helper cases separately exercise signed s8 and invalid algorithm IDs, so userspace clipping/atoi cannot hide kernel bugs. Valid operations must preserve data and produce compressed extents from highly compressible input; invalid cases must return EINVAL without rewriting. Do not assert exact compressed length proves level selection: there is no per-extent stored level. A separate instrumented run may verify effective compressor levels, but do not call FIEMAP alone a level-selection oracle.

Gap: 260 changes algorithms but does not test COMPRESS_LEVEL. Benefit/bugs: negative zstd levels interpreted unsigned, bounds errors, union compatibility mistakes and accepting unsupported types. Groups: auto quick defrag compress.

## T11 — Sparse-file traversal work scales with extents (P0 investigation, kernel performance)

Path: `btrfs_defrag_file()` cluster loop -> `defrag_one_cluster()` -> `defrag_collect_targets()` and last_scanned_ret.

Create otherwise identical sparse files with two 128KiB compressed islands and gaps of 64MiB, 1GiB, 16GiB; their allocated data is constant. Run raw whole-file NOCOMPRESS (not userspace --step). In a private tracefs instance count `defrag_one_cluster` calls restricted to the worker PID (function profiler/kprobe if available), record task CPU time and device read/write sectors; do not record global unrelated activity. Quiesce and sync before each run. Verify both islands convert and holes remain holes. Stop safely if the largest case exceeds an investigation time budget.

Source evidence: the initial `defrag_collect_targets(... false, ..., NULL)` cannot report the end of a skipped hole; with an empty target list `defrag_one_cluster()` advances by only start+len. This suggests approximately gap/256KiB iterations and avoidable CPU/metadata lookup work. A structural probe should distinguish linear growth from a skip-ahead implementation. Record counts and ratios, no fixed machine-dependent runtime golden output. This is not btrfs/258 or 263: those cover correctness/eligibility, not huge-hole traversal work in NOCOMPRESS.

Potential bug: O(logical file size) maintenance time on sparse VM images with little allocated data. Promote to an auto regression only after a kernel optimization and agreed stable count/progress oracle; before that deliver the reproducible experiment and baseline numbers, not a knowingly failing auto test.

## T12 — Avoidable repeated rewrite and COW amplification (P0 investigation, kernel performance)

Path: NOCOMPRESS -> `defrag_collect_targets(do_compress=true)` bypasses ordinary max-capacity and mergeability filters for all regular extents, including already uncompressed ones.

Create a large fully uncompressed, already contiguous file with compression disabled, sync, and retain a read-only snapshot. Save file extent items and physical mappings. Run --nocomp twice, syncing after each; capture bytes rewritten on the scratch device, new physical extents, snapshot retained bytes and CPU. Compare a control ordinary defrag on a separate identical file. A second matrix with mixed compressed/uncompressed islands tests whether only required conversion work can be selected. Verify data and snapshot integrity throughout. Keep metadata writes separate from data write amplification; raw device sector totals alone are approximate.

Potential gap: needless reads, writes, SSD wear and snapshot space inflation when administrators repeatedly request decompression. Existing 259/263 intentionally avoid waste in ordinary/autodefrag only. Current code appears to request unconditional regular-extent rewriting in conversion mode; this is therefore an optimization investigation, NOT an ABI guarantee that --nocomp must be idempotent physically. Discuss fragmented-extent merging semantics before changing eligibility. Once agreed, a deterministic test can compare physical mapping stability of an already optimal uncompressed region; until then do not add that assertion to auto.

## T13 — --step must respect the requested end (P0, userspace regression with Linux I/O benefit)

Path: `cmds/filesystem.c:defrag_range_in_steps()` and kernel range clipping. The source assigns each range.len = defrag_global_step without min(step, end-start).

Use a 4MiB compressed file; request --nocomp -s 1M -l 384K --step 256K. The final 128KiB of the second step lies beyond the requested end. Assert target bytes are converted but the distant aligned extent immediately past 1408KiB remains compressed and unchanged. Compare non-step execution on an identical file, and add step larger than len plus len=0 (whose CLI/kernel interaction needs explicit definition). Inspect the actual ioctl ranges with an optional interposer/strace to isolate userspace overshoot from a kernel alignment effect. All fixture boundaries are multiples of 128KiB to avoid ambiguous compressed-extent splits.

Gap: no progs step test and no fstests use of this combination found. Expected bug candidate: userspace rewrites beyond the requested logical range, wasting kernel COW work and breaking sharing unnecessarily. It is not itself proof of a Linux kernel bug. Put parser-only cases in btrfs-progs tests; retain end-to-end range protection in fstests if maintainers agree. A progs fix should cap the last step; do not silently alter the kernel to compensate. Add option-order conflict checks in progs separately: the current --nocomp branch checks compress_level rather than compress_type.

## Execution and acceptance

Implement T01-T10 as separate logical tests with shared helpers only where needed. Keep 354 unchanged. Implement T13 separately with the suspected existing failure clearly documented. T11/T12 remain opt-in measurement recipes until baselines justify a regression invariant; their benefit is detecting performance gaps, not inventing timing pass criteria.

Priority: T09 helper and T01/T02/T04/T05 first, T10 and T03 next, T06/T07/T08 after those. Review every expected errno against the source and use valid nonempty fixtures so early returns do not hide validation. Tests requiring a stable on-disk extent layout should unmount before dump-tree. The user subsequently authorized a new branch and separate explanatory commits with Dhruva Gole's existing author identity and explicit Signed-off-by. Sol will perform these commits with per-commit sanity checks. No push or mailing-list submission was requested.

VM matrix supplied by maintainer: reviewed linux-next (and today's newer tree after refreshing this audit), kernel with initial NOCOMPRESS support, older kernel for skip behavior; latest btrfs-progs; 4K pages/sectors and 64K pages/4K sectors where available. Use an established disposable scratch configuration. Build fstests with `make`, regenerate btrfs group metadata, inspect selection with `./check -n <explicit IDs>`, then run `sudo ./check <explicit IDs>` per suite configuration. Repeat race/error tests and inspect .full, .notrun, .out.bad and dmesg. A skip is not a semantic pass.

Regression strength: on a disposable kernel branch, remove NOCOMPRESS handling or its reset and verify relevant tests fail; remove invalid-flag validation for T09; alter signed level handling for T10. For T13 compare progs before/after final-step clipping. Do not mutate the maintainer's checked-out kernel to perform these checks. Record kernel/progs/fstests hashes and exact mount/mkfs options with every run.

Implementation status and assigned test IDs will be appended after Sol's implementation and review. VM results must be supplied by the external test infrastructure; local syntax/build verification is reported separately.
## Implementation review evidence (2026-09-27)

Sol was dispatched with 72% of the five-hour allowance remaining. T01-T10 were
allocated as btrfs/355-364; T13 is btrfs/365. The original 354 remains unchanged.
See BTRFS-IMPLEMENTATION-STATUS.md for implementation limits and checks. All
these IDs are local and provisional. Test365 deliberately omits auto because
it targets a currently observed progs request-construction defect.

T13 request-construction reproduction on the locally built btrfs-progs v7.1:

```
btrfs filesystem defragment --nocomp -s 1M -l 384K --step 256K fixture
requested interval: [1048576, 1441792)
observed ioctl 1: start=1048576 len=262144 flags=10 end=1310720
observed ioctl 2: start=1310720 len=262144 flags=10 end=1572864
```

This was measured with a process-local LD_PRELOAD ioctl recorder on a 4MiB
regular fixture; filesystem type was mocked and DEFRAG_RANGE returned success.
It proves 128KiB of excess requested range in userspace, not actual on-disk
conversion or a kernel failure. The test365 VM run verifies that latter effect.
The progs source at freshly fetched 4d02beef has the same range-splitting code.
No source fix to progs or Linux was made during this test-authoring task.

T11/T12 measurement tool: tools/btrfs-nocomp-perf.py. Companion instructions:
BTRFS-PERFORMANCE-PROBES.md. It implements the minimal sparse/contiguous cases;
the mixed-extent follow-up remains in the plan. ABI constants and struct sizes
were checked against C Linux headers on x86_64 (defrag 48 bytes, FIEMAP header
32, extent 56), Python compilation passes, and the non-Btrfs mount guard rejects
a host /tmp directory. No Btrfs performance measurements have been fabricated.