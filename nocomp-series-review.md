# Review and VM test report: btrfs NOCOMPRESS defrag series (btrfs/355-357)

Branch `codex/nocomp-mail-series`, series range `56c410ad..3ad46116` (3 patches).
Review date 2026-10-05. Reviewed with the Sashiko-style protocol, run inline because the series is small.

| Patch | Subject | Adds |
|---|---|---|
| `35427ac1` | btrfs: exercise NOCOMPRESS range and EOF handling | `common/btrfs_nocomp`, `src/btrfs_defrag_nocomp.c`, `src/Makefile` entry, `btrfs/355` |
| `ecefee0e` | btrfs: check NOCOMPRESS preserves holes and preallocation | `btrfs/356` |
| `3ad46116` | btrfs: cover NOCOMPRESS inline eligibility and short tails | `btrfs/357` |

## Verdict

Valid and useful, with no bugs found. Two low-severity convention misses should be fixed before it goes to
fstests@vger.kernel.org. All three tests pass in a VM on the latest mainline kernel available here (v7.3-rc3).

## Validity against the kernel

Checked against v6.17 sources:

- `BTRFS_DEFRAG_RANGE_NOCOMPRESS` is 8, which matches the `1ULL << 3` fallback in `src/btrfs_defrag_nocomp.c`.
- The feature commit `009b2056cb25` ("btrfs: defrag: add flag to force no-compression") landed in v6.17-rc1,
  and `_wants_kernel_commit` uses the right id.
- `fs/btrfs/defrag.c:1379` rejects `start >= isize` with `-EINVAL`, which is what `btrfs/355` asserts.
- `fs/btrfs/ioctl.c:2553` rejects unknown flags with `-EOPNOTSUPP`. `_nc_probe` relies on this to turn old
  kernels into `_notrun`.
- The FIEMAP flag decoding in the awk is correct: `0x8` is ENCODED, `0x200` is DATA_INLINE, `0x800` is
  UNWRITTEN, and `0x6` (UNKNOWN/DELALLOC) is treated as a failure.
- `bash -n` is clean on all four shell files, `gcc -Wall -Wextra` is clean on the C helper, and the diff has no
  trailing whitespace.

## Use case and benefit

- Upstream has no coverage of the new `NOCOMPRESS` defrag uAPI. Tests that rely on the userspace `btrfs` tool
  alone cannot tell a kernel regression from a btrfs-progs one.
- The raw-ioctl helper tests errno behaviour directly, without btrfs-progs translating it.
- `_nc_check_range` requires full mapping coverage and inspects every overlapping extent. A hole or a
  half-converted range therefore cannot pass.
- Covered corner cases:
  - partial tail sectors
  - zero and oversize `len`
  - `start == EOF`
  - the empty file
  - `KEEP_SIZE` preallocation beyond EOF
  - the inline `max_inline` transition
  - results re-checked after a remount
- Using FIEMAP instead of `dump-tree` keeps the tests stable across btrfs-progs versions.
- Feature gating is correct. The tests require 4K sectorsize, no nodatacow/nodatasum/autodefrag, and
  inline-extent creation support where needed.

## Coding-standards compliance

The project's written rules are the README ("SUBMITTING PATCHES") and the `./new` skeleton.

| Area | Result |
|---|---|
| SPDX line, `_begin_fstest` with valid groups (`auto quick defrag compress fiemap prealloc`), `.out` files | OK |
| `Signed-off-by`, `btrfs:` subject prefix, commit messages that explain what is checked and why | OK |
| `_fail` for failures (412 existing tests use it), gawk `strtonum`/`and()` (already used in `common/punch`) | OK |
| `LINUX_TARGETS` entry, same as `btrfs_ioctl` | OK |
| `quick` group fit (the VM runs took about 3-4 s each) | OK |
| `.gitignore` entry for the new binary | MISSING |
| `# FS QA Test NNN` / `# Copyright` header | MISSING |

## Findings (no Critical/High/Medium)

1. **Low**: `.gitignore` had no `/src/btrfs_defrag_nocomp`. Every other `src/` binary has one (for example
   `/src/btrfs_ioctl`). Fixed in a follow-up commit; squash it into `35427ac1` before sending.
2. **Low**: the test headers of 355-357 lacked the `# FS QA Test NNN` and `# Copyright (c) YEAR NAME` lines that
   `./new` generates. Fixed in the follow-up commit "btrfs/355-357: add standard test headers".
3. **Low**: `_scratch_mount ... || _fail "mount failed"` was redundant, because `_scratch_mount` already aborts
   on failure. The same applied to `_scratch_cycle_mount ... || _fail "remount failed"`. Fixed in the follow-up
   commit "btrfs/355-357: drop redundant mount failure checks".
4. **Low (style)**:
   - The `_nc_` helper prefix is cryptic next to `_require_btrfs_*` and `_btrfs_*`.
   - A dedicated 133-line `common/btrfs_nocomp` for three tests is heavier than precedent, so a reviewer may
     ask for the helpers in `common/btrfs`.
   - The variable named `tail` in 355 shadows a command name.
5. **Process**: the numbers 355-357 are provisional. Upstream already has 350-353, and maintainers renumber on
   merge. Rebase onto current upstream and add a cover letter with a version before sending.

## Follow-up commits (on top of the 3 series patches)

Kept as separate commits so the review fixes are easy to see and squash into the series before sending.

| Commit subject | Change |
|---|---|
| `gitignore: add btrfs_defrag_nocomp` | Adds `/src/btrfs_defrag_nocomp` next to `/src/btrfs_ioctl` (finding 1). |
| `btrfs/355-357: add standard test headers` | Adds the `# Copyright (c) 2026 <holder>.  All Rights Reserved.` and `# FS QA Test NNN` lines that `./new` generates, with the holder written in the same form as the existing headers in the tree, keeping each test's one-line description (finding 2). |
| `btrfs/355-357: drop redundant mount failure checks` | Removes the extra `_fail "mount failed"` / `_fail "remount failed"` fallbacks after `_scratch_mount` and `_scratch_cycle_mount`, since both helpers already call `_fail` (finding 3). 8 lines changed, no behaviour change. |

Finding 4 (the `_nc_` prefix, the dedicated helper file, the `tail` variable name) is left as is: it is a
judgement call for the list reviewers, not a defect.

The follow-up commits were re-tested: 355-357 pass 3/3 on v7.3-rc3 with all of them applied (Appendix A).

## VM test results

All runs used QEMU VMs running fstests, with 4K-sectorsize scratch devices and a btrfs-progs build that supports
`defragment --nocomp`.

| Kernel | Runs | Result |
|---|---|---|
| **v7.3-rc3** (mainline, plus 313 commits, 2026-09-17), series patches only | 355-357 once, then 5 more iterations of each across 5 VMs | **18/18 PASS**, 0 skip, 0 fail |
| **v7.3-rc3**, branch HEAD (series + all follow-up commits) | 355-357, twice (the second run also captured the `.full` logs) | **6/6 PASS** |
| 6.16 (pre-feature) | 355-357 once | 3/3 `[not run] kernel does not support NOCOMPRESS` (gating works) |

Environment notes, for reproducibility:

- The kernel was built from a mainline checkout with the `olddefconfig` of an existing config and gcc 11.5.
  There was no network, so a newer tree could not be fetched.
- The guest's distribution `btrfs` is too old, so with it all three tests SKIP ("too old (must support
  filesystem defragment --nocomp)"). The passing runs put a btrfs-progs build first in `PATH`:
  v7.1 plus 14 commits.
- `src/btrfs_defrag_nocomp` was compiled directly with `gcc`, because the build host lacks the fstests dev
  libraries. The `src/Makefile` target itself was not exercised.
- These runs cover pass/skip behaviour on two kernels. No fault-injection (mutation) run was done to prove
  that each assertion can fail.

The full output of every run is in the appendix at the end of this file.

## Suggested follow-up

1. Squash the `.gitignore` follow-up commit into `35427ac1`.
2. Squash the header and redundant-`_fail` follow-up commits into the matching series patches.
3. Rebase onto current upstream, renumber if needed, add a cover letter, and send.
4. Drop this file from the series before sending. It is a local report, not part of the patches.

## Appendix: raw test logs

Each block is the verbatim output of `./check <test>` run inside the VM (`exit` is the harness exit status, `dur` the
wall-clock seconds). For the final run it also includes the per-test `.full` log (mkfs output, every FIEMAP dump the
assertions parsed) and the tool versions. The `btrfs-progs v6.7` banner at the top of each `.full` is the guest distribution's
`mkfs.btrfs`; the defragment commands under test ran with the newer `btrfs` listed under `===VERSIONS===`. In `.full`, a first-extent flag of `0x8` is ENCODED (compressed), `0x0` is a
regular uncompressed extent, `0x800`/`0x801` is UNWRITTEN (preallocated), and `0x9` is ENCODED+LAST.

### A. Final run, v7.3-rc3, HEAD of this branch (3 tests, full `.full` logs)
#### btrfs/355 (#1, exit 0, dur 3.1s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/355           2s
Ran: btrfs/355
Passed all 1 tests

===FULL===
btrfs-progs v6.7 
See https://btrfs.readthedocs.io for more information.

Performing full device TRIM /dev/vdc (10.00GiB) ...
NOTE: several default settings have changed in version 5.15, please make sure
      this does not affect your deployments:
      - DUP for metadata (-m dup)
      - enabled no-holes (-O no-holes)
      - enabled free-space-tree (-R free-space-tree)

Label:              (null)
UUID:               dd67ba54-a03f-46ab-b72e-ab4d85d57101
Node size:          16384
Sector size:        4096
Filesystem size:    10.00GiB
Block group profiles:
  Data:             single            8.00MiB
  Metadata:         DUP             256.00MiB
  System:           DUP               8.00MiB
SSD detected:       no
Zoned device:       no
Incompat features:  extref, skinny-metadata, no-holes, free-space-tree
Runtime features:   free-space-tree
Checksum:           crc32c
Number of devices:  1
Devices:
   ID        SIZE  PATH    
    1    10.00GiB  /dev/vdc

wrote 131072/131072 bytes at offset 0
128 KiB, 1 ops; 0.0001 sec (1.197 GiB/sec and 9803.9216 ops/sec)
wrote 4194304/4194304 bytes at offset 0
4 MiB, 32 ops; 0.0029 sec (1.326 GiB/sec and 10858.5002 ops/sec)
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        26888..27143       256   0x8
   1: [256..511]:      26896..27151       256   0x8
   2: [512..767]:      26904..27159       256   0x8
   3: [768..1023]:     26912..27167       256   0x8
   4: [1024..1279]:    26920..27175       256   0x8
   5: [1280..1535]:    26928..27183       256   0x8
   6: [1536..1791]:    26936..27191       256   0x8
   7: [1792..2047]:    26944..27199       256   0x8
   8: [2048..2303]:    26952..27207       256   0x8
   9: [2304..2559]:    26960..27215       256   0x8
  10: [2560..2815]:    26968..27223       256   0x8
  11: [2816..3071]:    26976..27231       256   0x8
  12: [3072..3327]:    26984..27239       256   0x8
  13: [3328..3583]:    26992..27247       256   0x8
  14: [3584..3839]:    27000..27255       256   0x8
  15: [3840..4095]:    27008..27263       256   0x8
  16: [4096..4351]:    27016..27271       256   0x8
  17: [4352..4607]:    27024..27279       256   0x8
  18: [4608..4863]:    27032..27287       256   0x8
  19: [4864..5119]:    27040..27295       256   0x8
  20: [5120..5375]:    27048..27303       256   0x8
  21: [5376..5631]:    27056..27311       256   0x8
  22: [5632..5887]:    27064..27319       256   0x8
  23: [5888..6143]:    27072..27327       256   0x8
  24: [6144..6399]:    27080..27335       256   0x8
  25: [6400..6655]:    27088..27343       256   0x8
  26: [6656..6911]:    27096..27351       256   0x8
  27: [6912..7167]:    27104..27359       256   0x8
  28: [7168..7423]:    27112..27367       256   0x8
  29: [7424..7679]:    27120..27375       256   0x8
  30: [7680..7935]:    27128..27383       256   0x8
  31: [7936..8191]:    27136..27391       256   0x9
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        26888..27143       256   0x8
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [7936..8191]:    27136..27391       256   0x9
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2048..3071]:    583680..584703    1024   0x0
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        26888..27143       256   0x8
   1: [256..511]:      26896..27151       256   0x8
   2: [512..767]:      26904..27159       256   0x8
   3: [768..1023]:     26912..27167       256   0x8
   4: [1024..1279]:    26920..27175       256   0x8
   5: [1280..1535]:    26928..27183       256   0x8
   6: [1536..1791]:    26936..27191       256   0x8
   7: [1792..2047]:    26944..27199       256   0x8
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [3072..3327]:    26984..27239       256   0x8
   1: [3328..3583]:    26992..27247       256   0x8
   2: [3584..3839]:    27000..27255       256   0x8
   3: [3840..4095]:    27008..27263       256   0x8
   4: [4096..4351]:    27016..27271       256   0x8
   5: [4352..4607]:    27024..27279       256   0x8
   6: [4608..4863]:    27032..27287       256   0x8
   7: [4864..5119]:    27040..27295       256   0x8
   8: [5120..5375]:    27048..27303       256   0x8
   9: [5376..5631]:    27056..27311       256   0x8
  10: [5632..5887]:    27064..27319       256   0x8
  11: [5888..6143]:    27072..27327       256   0x8
  12: [6144..6399]:    27080..27335       256   0x8
  13: [6400..6655]:    27088..27343       256   0x8
  14: [6656..6911]:    27096..27351       256   0x8
  15: [6912..7167]:    27104..27359       256   0x8
  16: [7168..7423]:    27112..27367       256   0x8
  17: [7424..7679]:    27120..27375       256   0x8
  18: [7680..7935]:    27128..27383       256   0x8
  19: [7936..8191]:    27136..27391       256   0x9
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        26888..27143       256   0x8
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [7936..8191]:    27136..27391       256   0x9
wrote 135169/135169 bytes at offset 0
132 KiB, 2 ops; 0.0001 sec (1.134 GiB/sec and 18018.0180 ops/sec)
/mnt/scratch/partial:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [256..271]:      26624..26639        16   0x9
/mnt/scratch/partial:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [256..263]:      27152..27159         8   0x0
/mnt/scratch/partial:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [256..271]:      26632..26647        16   0x1
wrote 262144/262144 bytes at offset 0
256 KiB, 2 ops; 0.0002 sec (1.009 GiB/sec and 8264.4628 ops/sec)
/mnt/scratch/zero:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        27160..27415       256   0x8
   1: [256..511]:      26648..26903       256   0x9
/mnt/scratch/zero:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        27160..27415       256   0x8
/mnt/scratch/zero:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [256..511]:      27168..27423       256   0x1
wrote 262144/262144 bytes at offset 0
256 KiB, 2 ops; 0.0002 sec (1.115 GiB/sec and 9132.4201 ops/sec)
/mnt/scratch/huge:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        27424..27679       256   0x8
   1: [256..511]:      26656..26911       256   0x9
/mnt/scratch/huge:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        27424..27679       256   0x8
/mnt/scratch/huge:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [256..511]:      27432..27687       256   0x1
/mnt/scratch/range: OK
/mnt/scratch/partial: OK
/mnt/scratch/zero: OK
/mnt/scratch/huge: OK
/mnt/scratch/empty: OK
/mnt/scratch/range: OK
/mnt/scratch/partial: OK
/mnt/scratch/zero: OK
/mnt/scratch/huge: OK
/mnt/scratch/empty: OK
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2048..3071]:    583680..584703    1024   0x0
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        26888..27143       256   0x8
   1: [256..511]:      26896..27151       256   0x8
   2: [512..767]:      26904..27159       256   0x8
   3: [768..1023]:     26912..27167       256   0x8
   4: [1024..1279]:    26920..27175       256   0x8
   5: [1280..1535]:    26928..27183       256   0x8
   6: [1536..1791]:    26936..27191       256   0x8
   7: [1792..2047]:    26944..27199       256   0x8
/mnt/scratch/range:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [3072..3327]:    26984..27239       256   0x8
   1: [3328..3583]:    26992..27247       256   0x8
   2: [3584..3839]:    27000..27255       256   0x8
   3: [3840..4095]:    27008..27263       256   0x8
   4: [4096..4351]:    27016..27271       256   0x8
   5: [4352..4607]:    27024..27279       256   0x8
   6: [4608..4863]:    27032..27287       256   0x8
   7: [4864..5119]:    27040..27295       256   0x8
   8: [5120..5375]:    27048..27303       256   0x8
   9: [5376..5631]:    27056..27311       256   0x8
  10: [5632..5887]:    27064..27319       256   0x8
  11: [5888..6143]:    27072..27327       256   0x8
  12: [6144..6399]:    27080..27335       256   0x8
  13: [6400..6655]:    27088..27343       256   0x8
  14: [6656..6911]:    27096..27351       256   0x8
  15: [6912..7167]:    27104..27359       256   0x8
  16: [7168..7423]:    27112..27367       256   0x8
  17: [7424..7679]:    27120..27375       256   0x8
  18: [7680..7935]:    27128..27383       256   0x8
  19: [7936..8191]:    27136..27391       256   0x9
/mnt/scratch/partial:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [256..271]:      26632..26647        16   0x1
/mnt/scratch/zero:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        27160..27415       256   0x8
/mnt/scratch/zero:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [256..511]:      27168..27423       256   0x1
/mnt/scratch/huge:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        27424..27679       256   0x8
/mnt/scratch/huge:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [256..511]:      27432..27687       256   0x1
===VERSIONS===
7.3.0-rc3-00313-g5dd1818b15d9
btrfs-progs v7.1
-EXPERIMENTAL -INJECT -STATIC +LZO +ZSTD +UDEV +FSVERITY +ZONED CRYPTO=builtin
```
#### btrfs/356 (#2, exit 0, dur 3.2s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/356           1s
Ran: btrfs/356
Passed all 1 tests

===FULL===
btrfs-progs v6.7 
See https://btrfs.readthedocs.io for more information.

Performing full device TRIM /dev/vdc (10.00GiB) ...
NOTE: several default settings have changed in version 5.15, please make sure
      this does not affect your deployments:
      - DUP for metadata (-m dup)
      - enabled no-holes (-O no-holes)
      - enabled free-space-tree (-R free-space-tree)

Label:              (null)
UUID:               d1941a9c-ea2a-4cbd-ab09-fa4fb8f9f2d8
Node size:          16384
Sector size:        4096
Filesystem size:    10.00GiB
Block group profiles:
  Data:             single            8.00MiB
  Metadata:         DUP             256.00MiB
  System:           DUP               8.00MiB
SSD detected:       no
Zoned device:       no
Incompat features:  extref, skinny-metadata, no-holes, free-space-tree
Runtime features:   free-space-tree
Checksum:           crc32c
Number of devices:  1
Devices:
   ID        SIZE  PATH    
    1    10.00GiB  /dev/vdc

wrote 131072/131072 bytes at offset 0
128 KiB, 1 ops; 0.0001 sec (1.185 GiB/sec and 9708.7379 ops/sec)
wrote 131072/131072 bytes at offset 0
128 KiB, 1 ops; 0.0001 sec (905.797 MiB/sec and 7246.3768 ops/sec)
wrote 131072/131072 bytes at offset 524288
128 KiB, 1 ops; 0.0001 sec (1.163 GiB/sec and 9523.8095 ops/sec)
wrote 131072/131072 bytes at offset 1048576
128 KiB, 1 ops; 0.0000 sec (1.246 GiB/sec and 10204.0816 ops/sec)
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        26888..27143       256   0x8
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [1024..1279]:    26896..27151       256   0x8
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2048..2303]:    26904..27159       256   0x9
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [512..767]:      26912..27167       256 0x800
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [512..767]:      26912..27167       256 0x800
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2560..2815]:    27168..27423       256 0x801
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2560..2815]:    27168..27423       256 0x801
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [512..767]:      26912..27167       256 0x800
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [512..767]:      26912..27167       256 0x800
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2560..2815]:    27168..27423       256 0x801
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2560..2815]:    27168..27423       256 0x801
/mnt/scratch/islands:
/mnt/scratch/islands:
/mnt/scratch/islands:
/mnt/scratch/islands:
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        27424..27679       256   0x0
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [1024..1279]:    27680..27935       256   0x0
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2048..2303]:    27936..28191       256   0x0
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [512..767]:      26912..27167       256 0x800
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [512..767]:      26912..27167       256 0x800
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2560..2815]:    27168..27423       256 0x801
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2560..2815]:    27168..27423       256 0x801
/mnt/scratch/islands:
/mnt/scratch/islands:
/mnt/scratch/islands:
/mnt/scratch/islands:
/mnt/scratch/islands: OK
/mnt/scratch/islands: OK
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [512..767]:      26912..27167       256 0x800
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [512..767]:      26912..27167       256 0x800
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2560..2815]:    27168..27423       256 0x801
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2560..2815]:    27168..27423       256 0x801
/mnt/scratch/islands:
/mnt/scratch/islands:
/mnt/scratch/islands:
/mnt/scratch/islands:
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        27424..27679       256   0x0
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [1024..1279]:    27680..27935       256   0x0
/mnt/scratch/islands:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [2048..2303]:    27936..28191       256   0x0
===VERSIONS===
7.3.0-rc3-00313-g5dd1818b15d9
btrfs-progs v7.1
-EXPERIMENTAL -INJECT -STATIC +LZO +ZSTD +UDEV +FSVERITY +ZONED CRYPTO=builtin
```
#### btrfs/357 (#3, exit 0, dur 4.1s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/357           2s
Ran: btrfs/357
Passed all 1 tests

===FULL===
btrfs-progs v6.7 
See https://btrfs.readthedocs.io for more information.

Performing full device TRIM /dev/vdc (10.00GiB) ...
NOTE: several default settings have changed in version 5.15, please make sure
      this does not affect your deployments:
      - DUP for metadata (-m dup)
      - enabled no-holes (-O no-holes)
      - enabled free-space-tree (-R free-space-tree)

Label:              (null)
UUID:               e59289e4-1bae-4f8c-98d3-a1c2264d3242
Node size:          16384
Sector size:        4096
Filesystem size:    10.00GiB
Block group profiles:
  Data:             single            8.00MiB
  Metadata:         DUP             256.00MiB
  System:           DUP               8.00MiB
SSD detected:       no
Zoned device:       no
Incompat features:  extref, skinny-metadata, no-holes, free-space-tree
Runtime features:   free-space-tree
Checksum:           crc32c
Number of devices:  1
Devices:
   ID        SIZE  PATH    
    1    10.00GiB  /dev/vdc

wrote 131072/131072 bytes at offset 0
128 KiB, 1 ops; 0.0001 sec (1.141 GiB/sec and 9345.7944 ops/sec)
wrote 2048/2048 bytes at offset 0
2 KiB, 1 ops; 0.0000 sec (114.890 MiB/sec and 58823.5294 ops/sec)
/mnt/scratch/inline:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..7]:          0..7                 8 0x309
/mnt/scratch/inline:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..7]:          0..7                 8 0x309
/mnt/scratch/inline: OK
/mnt/scratch/inline:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..7]:          0..7                 8 0x309
/mnt/scratch/inline: OK
/mnt/scratch/inline:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..7]:          26624..26631         8   0x1
/mnt/scratch/inline: OK
wrote 1/1 bytes at offset 0
1.000000 bytes, 1 ops; 0.0000 sec (57.445 KiB/sec and 58823.5294 ops/sec)
/mnt/scratch/tail-1:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..7]:          26640..26647         8   0x1
wrote 4095/4095 bytes at offset 0
4 KiB, 1 ops; 0.0000 sec (186 MiB/sec and 47619.0476 ops/sec)
/mnt/scratch/tail-4095:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..7]:          26656..26663         8   0x1
wrote 4097/4097 bytes at offset 0
4 KiB, 1 ops; 0.0002 sec (13.068 MiB/sec and 3344.4816 ops/sec)
/mnt/scratch/tail-4097:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..15]:         26664..26679        16   0x9
/mnt/scratch/tail-4097:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..15]:         26672..26687        16   0x1
wrote 131073/131073 bytes at offset 0
128 KiB, 2 ops; 0.0004 sec (274.727 MiB/sec and 4395.6044 ops/sec)
/mnt/scratch/tail-131073:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..255]:        26688..26943       256   0x8
/mnt/scratch/tail-131073:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..263]:        583680..583943     264   0x1
/mnt/scratch/inline: OK
/mnt/scratch/tail-1: OK
/mnt/scratch/tail-4095: OK
/mnt/scratch/tail-4097: OK
/mnt/scratch/tail-131073: OK
/mnt/scratch/inline: OK
/mnt/scratch/tail-1: OK
/mnt/scratch/tail-4095: OK
/mnt/scratch/tail-4097: OK
/mnt/scratch/tail-131073: OK
/mnt/scratch/inline:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..7]:          26624..26631         8   0x1
/mnt/scratch/tail-1:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..7]:          26640..26647         8   0x1
/mnt/scratch/tail-4095:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..7]:          26656..26663         8   0x1
/mnt/scratch/tail-4097:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..15]:         26672..26687        16   0x1
/mnt/scratch/tail-131073:
 EXT: FILE-OFFSET      BLOCK-RANGE      TOTAL FLAGS
   0: [0..263]:        583680..583943     264   0x1
===VERSIONS===
7.3.0-rc3-00313-g5dd1818b15d9
btrfs-progs v7.1
-EXPERIMENTAL -INJECT -STATIC +LZO +ZSTD +UDEV +FSVERITY +ZONED CRYPTO=builtin
```

### B. v7.3-rc3, series patches only (each test 5 times, 15 runs)
#### btrfs/355 (#1, exit 0, dur 3.3s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/355           2s
Ran: btrfs/355
Passed all 1 tests
```
#### btrfs/355 (#2, exit 0, dur 3.7s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/355           2s
Ran: btrfs/355
Passed all 1 tests
```
#### btrfs/355 (#3, exit 0, dur 2.4s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/355           1s
Ran: btrfs/355
Passed all 1 tests
```
#### btrfs/355 (#4, exit 0, dur 2.4s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/355           1s
Ran: btrfs/355
Passed all 1 tests
```
#### btrfs/355 (#5, exit 0, dur 2.1s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/355    1s ...  1s
Ran: btrfs/355
Passed all 1 tests
```
#### btrfs/356 (#6, exit 0, dur 3.6s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/356           2s
Ran: btrfs/356
Passed all 1 tests
```
#### btrfs/356 (#7, exit 0, dur 3.7s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/356           2s
Ran: btrfs/356
Passed all 1 tests
```
#### btrfs/356 (#8, exit 0, dur 2.2s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/356           1s
Ran: btrfs/356
Passed all 1 tests
```
#### btrfs/356 (#9, exit 0, dur 2.1s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/356           2s
Ran: btrfs/356
Passed all 1 tests
```
#### btrfs/356 (#10, exit 0, dur 2.1s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/356           1s
Ran: btrfs/356
Passed all 1 tests
```
#### btrfs/357 (#11, exit 0, dur 3.8s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/357           2s
Ran: btrfs/357
Passed all 1 tests
```
#### btrfs/357 (#12, exit 0, dur 2.5s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/357           2s
Ran: btrfs/357
Passed all 1 tests
```
#### btrfs/357 (#13, exit 0, dur 2.5s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/357           1s
Ran: btrfs/357
Passed all 1 tests
```
#### btrfs/357 (#14, exit 0, dur 2.5s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/357           2s
Ran: btrfs/357
Passed all 1 tests
```
#### btrfs/357 (#15, exit 0, dur 2.3s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 7.3.0-rc3-00313-g5dd1818b15d9 #1 SMP PREEMPT_DYNAMIC Mon Oct  5 10:44:49 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

btrfs/357    1s ...  2s
Ran: btrfs/357
Passed all 1 tests
```

### C. 6.16 (kernel without the feature): expected skips
#### btrfs/355 (#1, exit 0, dur 2.7s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 6.16.0 #1 SMP PREEMPT_DYNAMIC Thu Sep 17 09:19:29 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

_check_btrfs_filesystem: filesystem on /dev/vdb is inconsistent
(see /root/results/check.full for details)
btrfs/355          [not run] kernel does not support NOCOMPRESS
Ran: btrfs/355
Not run: btrfs/355
Passed all 1 tests
```
#### btrfs/356 (#2, exit 0, dur 2.7s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 6.16.0 #1 SMP PREEMPT_DYNAMIC Thu Sep 17 09:19:29 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

_check_btrfs_filesystem: filesystem on /dev/vdb is inconsistent
(see /root/results/check.full for details)
btrfs/356          [not run] kernel does not support NOCOMPRESS
Ran: btrfs/356
Not run: btrfs/356
Passed all 1 tests
```
#### btrfs/357 (#3, exit 0, dur 3.1s)

```
FSTYP         -- btrfs
PLATFORM      -- Linux/x86_64 localhost 6.16.0 #1 SMP PREEMPT_DYNAMIC Thu Sep 17 09:19:29 PDT 2026
MKFS_OPTIONS  -- /dev/vdc
MOUNT_OPTIONS -- /dev/vdc /mnt/scratch

_check_btrfs_filesystem: filesystem on /dev/vdb is inconsistent
(see /root/results/check.full for details)
btrfs/357          [not run] kernel does not support NOCOMPRESS
Ran: btrfs/357
Not run: btrfs/357
Passed all 1 tests
```
