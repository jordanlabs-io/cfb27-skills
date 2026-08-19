#!/usr/bin/env python3
"""Split a Lane C survivor list into per-agent batch manifests (see references/data-dump.md).

Usage:
  dump_batches.py <keep-file> <outdir> [--size 14] [--prefix batch] [--exclude <file> ...]

<keep-file> is the `.keep` written by `dhash.py dedupe` — one frame filename per line.
Writes <outdir>/<prefix>_NN.txt, one filename per line, **in time order** so a single
agent sees a whole scroll and can merge it into one table. Out-of-order batching is why
a scrolled table arrives as fragments nobody can reassemble.

--exclude takes manifests (or keep-files) whose frames are already transcribed; use it to
build a sweep that reads only what an earlier pass missed. Excluded frames are reported,
never silently dropped.

Batch size: ~14 frames is what one vision agent reads reliably in a single turn. Larger
batches start dropping frames near the end without saying so.
"""
import sys, os, re


def read_list(p):
    return [l.strip() for l in open(p) if l.strip()]


def sec_of(n):
    m = re.search(r"f_(\d+)", n)
    return int(m.group(1)) if m else 0


def main(argv):
    keep_file, outdir = argv[1], argv[2]
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 14
    prefix = argv[argv.index("--prefix") + 1] if "--prefix" in argv else "batch"
    excl = set()
    if "--exclude" in argv:
        for p in argv[argv.index("--exclude") + 1:]:
            if p.startswith("--"):
                break
            excl |= set(read_list(p))

    frames = read_list(keep_file)
    skipped = [f for f in frames if f in excl]
    frames = sorted({f for f in frames if f not in excl}, key=sec_of)
    if not frames:
        sys.exit("ERROR: nothing to batch (every survivor was excluded)")

    os.makedirs(outdir, exist_ok=True)
    n = 0
    for i in range(0, len(frames), size):
        n += 1
        with open(os.path.join(outdir, f"{prefix}_{n:02d}.txt"), "w") as fh:
            fh.write("\n".join(frames[i:i + size]) + "\n")

    print(f"{len(frames)} frames -> {n} batches of <={size} in {outdir}/{prefix}_NN.txt")
    if skipped:
        print(f"excluded {len(skipped)} already-transcribed frames "
              f"({skipped[0]}..{skipped[-1]})")
    print(f"every one of these {len(frames)} frames must come back transcribed; "
          f"dump_reconcile.py gates on it.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv)
