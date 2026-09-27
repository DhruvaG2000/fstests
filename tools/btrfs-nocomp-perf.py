#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Opt-in T11/T12 experiments. Creates fixtures, never formats or removes them.

Run on a disposable, already mounted Btrfs scratch filesystem. Results describe
work and mapping changes, not pass/fail performance thresholds. See the plan.
"""
import argparse
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import time
import uuid

FIEMAP = 0xC020660B
DEFRAG = 0x40309410
HEADER = struct.Struct("=QQIIII")
EXTENT = struct.Struct("=QQQQQIIII")
RANGE = struct.Struct("=QQQII4I")
UNIT = 128 * 1024


def run(*args):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout.strip()


def mapping(path):
    result, start = [], 0
    with open(path, "rb", buffering=0) as file:
        while True:
            buf = bytearray(HEADER.size + 256 * EXTENT.size)
            HEADER.pack_into(buf, 0, start, (1 << 64) - 1 - start, 1, 0, 256, 0)
            fcntl.ioctl(file.fileno(), FIEMAP, buf, True)
            count = HEADER.unpack_from(buf)[3]
            if not count:
                break
            for i in range(count):
                row = EXTENT.unpack_from(buf, HEADER.size + i * EXTENT.size)
                result.append(dict(logical=row[0], physical=row[1],
                                   length=row[2], flags=row[5]))
            last = result[-1]
            end = last["logical"] + last["length"]
            if last["flags"] & 1 or end <= start:
                break
            start = end
    return result


def digest(path, islands=None):
    h = hashlib.sha256()
    with open(path, "rb") as file:
        if islands is not None:
            for offset, length in islands:
                file.seek(offset)
                data = file.read(length)
                if len(data) != length:
                    raise RuntimeError("short fixture read")
                h.update(data)
        else:
            while data := file.read(1024 * 1024):
                h.update(data)
    return h.hexdigest()


def device_sectors(path):
    if not path:
        return None
    fields = Path(path).read_text().split()
    return {"read_sectors": int(fields[2]), "written_sectors": int(fields[6])}


def measure(path, flags, args, label):
    before = mapping(path)
    if args.pause:
        print(f"{label}: worker PID {os.getpid()}; attach tracing then press Enter",
              file=sys.stderr, flush=True)
        input()
    sectors = device_sectors(args.block_stat)
    cpu = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.monotonic()
    with open(path, "rb", buffering=0) as file:
        # Whole-file raw UAPI: userspace --step cannot distort this experiment.
        buf = bytearray(RANGE.pack(0, (1 << 64) - 1, flags, 0, 0, 0, 0, 0, 0))
        fcntl.ioctl(file.fileno(), DEFRAG, buf, True)
        os.fsync(file.fileno())
    elapsed = time.monotonic() - wall
    used = resource.getrusage(resource.RUSAGE_SELF)
    after_sectors = device_sectors(args.block_stat)
    after = mapping(path)
    normalize = lambda rows: [(r["logical"], r["physical"], r["length"])
                              for r in rows]
    return {"label": label, "seconds": elapsed,
            "task_user_seconds": used.ru_utime - cpu.ru_utime,
            "task_system_seconds": used.ru_stime - cpu.ru_stime,
            "task_cpu_excludes_worker_threads": True,
            "device_sector_delta_includes_metadata_and_other_activity":
                ({k: after_sectors[k] - sectors[k] for k in sectors}
                 if sectors else None),
            "mapping_changed": normalize(before) != normalize(after),
            "before": before, "after": after}


def write_at(file, offset, count):
    file.seek(offset)
    for _ in range(count):
        if file.write(b"X" * UNIT) != UNIT:
            raise RuntimeError("short fixture write")
    os.fsync(file.fileno())


def sparse(args, root):
    results = []
    for gap_mib in (64, 1024, 16384):
        gap = gap_mib * 1024 * 1024
        path = root / f"sparse-{gap_mib}MiB"
        path.touch(exist_ok=False)
        run(args.btrfs, "property", "set", str(path), "compression", "zlib")
        islands = [(0, UNIT), (UNIT + gap, UNIT)]
        with open(path, "r+b", buffering=0) as file:
            for offset, _ in islands:
                write_at(file, offset, 1)
        before = mapping(path)
        for offset, _ in islands:
            if not any(r["logical"] <= offset < r["logical"] + r["length"]
                       and r["flags"] & 8 for r in before):
                raise RuntimeError("compressed island fixture not established")
        expected = digest(path, islands)
        sample = measure(path, 8, args, f"T11-gap-{gap_mib}MiB")
        sample["gap_bytes"] = gap
        after = sample["after"]
        # Skip a whole compression unit at each edge when checking holes.
        if any(r["logical"] < gap and r["logical"] + r["length"] > 2 * UNIT
               for r in after):
            raise RuntimeError("large hole unexpectedly mapped")
        if any(r["flags"] & 8 for r in after):
            raise RuntimeError("island still compressed after conversion")
        if digest(path, islands) != expected:
            raise RuntimeError("island data changed")
        if path.stat().st_size != gap + 2 * UNIT:
            raise RuntimeError("sparse file size changed")
        results.append(sample)
        print(json.dumps(sample), flush=True)
    return results


def rewrite(args, root):
    live, snapshot = root / "live", root / "baseline-ro"
    run(args.btrfs, "subvolume", "create", str(live))
    for name in ("ordinary", "nocomp"):
        path = live / name
        path.touch(exist_ok=False)
        run(args.btrfs, "property", "set", str(path), "compression", "no")
        with open(path, "r+b", buffering=0) as file:
            os.posix_fallocate(file.fileno(), 0, 32 * 1024 * 1024)
            write_at(file, 0, 256)
        if any(r["flags"] & (8 | 0x800) for r in mapping(path)):
            raise RuntimeError("uncompressed fully written fixture not established")
    run(args.btrfs, "filesystem", "sync", str(live))
    run(args.btrfs, "subvolume", "snapshot", "-r", str(live), str(snapshot))
    expected = {name: digest(live / name) for name in ("ordinary", "nocomp")}
    results = []
    for label, name, flags in (("T12-ordinary", "ordinary", 2),
                               ("T12-nocomp-first", "nocomp", 8),
                               ("T12-nocomp-repeat", "nocomp", 8)):
        sample = measure(live / name, flags, args, label)
        run(args.btrfs, "filesystem", "sync", str(live))
        sample["du_after"] = run(args.btrfs, "filesystem", "du", "-s",
                                  str(live), str(snapshot))
        for entry, checksum in expected.items():
            if digest(live / entry) != checksum or digest(snapshot / entry) != checksum:
                raise RuntimeError("live or snapshot data changed")
        results.append(sample)
        print(json.dumps(sample), flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("sparse", "rewrite"))
    parser.add_argument("--scratch-dir", required=True, type=Path,
                        help="existing directory on a disposable mounted Btrfs filesystem")
    parser.add_argument("--btrfs", default="btrfs")
    parser.add_argument("--block-stat", help="optional /sys/class/block/DEVICE/stat for dedicated scratch device")
    parser.add_argument("--pause", action="store_true", help="pause before each ioctl to allow PID tracing")
    args = parser.parse_args()
    if os.uname().machine not in ("x86_64", "aarch64", "riscv64", "i386", "i686"):
        parser.error("this probe uses asm-generic/x86 ioctl encodings; verify ABI on this architecture first")
    root = args.scratch_dir.resolve(strict=True)
    if run("findmnt", "-n", "-o", "FSTYPE", "-T", str(root)) != "btrfs":
        parser.error("scratch directory must be on Btrfs")
    if args.block_stat and not str(Path(args.block_stat).resolve()).startswith("/sys/"):
        parser.error("block stat must be a sysfs statistics file")
    root = root / ("nocomp-perf-" + uuid.uuid4().hex[:12])
    root.mkdir()
    print(f"Fixtures retained at {root}", file=sys.stderr, flush=True)
    meta = {"kernel": os.uname().release, "btrfs": run(args.btrfs, "version"),
            "mount": run("findmnt", "-n", "-o", "TARGET,OPTIONS", "-T", str(root)),
            "pid": os.getpid(), "fixture_dir": str(root), "mode": args.mode,
            "note": "Measurements, not performance pass/fail. No automatic cleanup."}
    (root / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta), flush=True)
    try:
        results = sparse(args, root) if args.mode == "sparse" else rewrite(args, root)
        (root / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    except OSError as error:
        if error.errno in (errno.EOPNOTSUPP, errno.ENOTTY):
            print(f"Unsupported operation: {error}", file=sys.stderr)
            return 77
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
