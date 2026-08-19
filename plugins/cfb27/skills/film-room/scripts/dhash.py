#!/usr/bin/env python3
"""dHash dedup for Lane C menu-screen captures (see references/data-dump.md).

A menu capture cannot be sampled by stride: every scroll position is different rows.
Dedup by perceptual hash instead, and transcribe every survivor.

Usage:
  dhash.py hashes  <framedir> <out.tsv> [--crop x0,y0,x1,y1]
  dhash.py calib   <hashes.tsv> [lo hi]                       # RUN THIS BEFORE dedupe
  dhash.py dedupe  <hashes.tsv> <out.json> [--thresh 3] [--window 25]

Pipeline order is hashes -> calib -> dedupe. `calib` prints the distance histogram
for consecutive frames; pick a threshold from the valley between the "same screen"
cluster and the "screen changed" cluster. Skipping calib and taking the default is
how a wrong crop degrades dedup silently.

`dedupe` writes <out.json> (full ledger) and <out.json>.keep (one filename per line).
**The .keep file is the contract**: tier-2 must transcribe exactly it, and
dump_reconcile.py gates on that. Never hand-assemble a survivor set — the 2027-w9
capture did, and its 1,552 transcribed frames are not reproducible from any
(threshold, window) pair, so its coverage ledger records what happened without
recording a decision anyone can re-derive.

Needs Pillow: run with the film venv python.
"""
import sys, os, glob, json
from PIL import Image

# Derived on 1920x1080 CFB27 menu screens: the table panel only, excluding the
# animated background and the right-hand player card. Both move on their own and
# would make a static table look "new" every frame.
DEFAULT_CROP = (80, 165, 1440, 950)
DEFAULT_THRESH = 3
DEFAULT_WINDOW = 25   # seconds; see references/data-dump.md


def dhash(path, crop, size=16):
    im = Image.open(path).convert("L").crop(crop).resize((size + 1, size), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for r in range(size):
        row = px[r * (size + 1):(r + 1) * (size + 1)]
        for c in range(size):
            bits = (bits << 1) | (1 if row[c] < row[c + 1] else 0)
    return bits


def sec_of(p):   # f_0720.jpg -> 719  (ffmpeg frame 1 = second 0)
    return int(os.path.basename(p).split("_")[1].split(".")[0]) - 1


def check_crop(first_frame, crop):
    w, h = Image.open(first_frame).size
    x0, y0, x1, y1 = crop
    if x1 <= w and y1 <= h:
        return
    sys.exit(
        f"ERROR: crop {crop} does not fit frames of {w}x{h}.\n"
        f"The default crop was derived on 1920x1080. Pass --crop x0,y0,x1,y1 sized for\n"
        f"these frames, then re-run `calib` before `dedupe`. A crop that spills off the\n"
        f"frame silently degrades dedup, and bad dedup is how frames go unread."
    )


def cmd_hashes(framedir, out, crop):
    fs = sorted(glob.glob(os.path.join(framedir, "f_*.jpg")))
    if not fs:
        sys.exit(f"ERROR: no f_*.jpg frames in {framedir}")
    check_crop(fs[0], crop)
    with open(out, "w") as fh:
        for p in fs:
            fh.write(f"{os.path.basename(p)}\t{sec_of(p)}\t{dhash(p, crop):x}\n")
    print(f"hashed {len(fs)} frames (crop={crop}) -> {out}")
    print("next: dhash.py calib " + out)


def load(tsv):
    rows = []
    for line in open(tsv):
        n, s, h = line.rstrip("\n").split("\t")
        rows.append((n, int(s), int(h, 16)))
    return rows


def cmd_calib(tsv, lo=None, hi=None):
    rows = load(tsv)
    if lo is not None:
        rows = [r for r in rows if lo <= r[1] <= hi]
    ds = [bin(rows[i][2] ^ rows[i - 1][2]).count("1") for i in range(1, len(rows))]
    if not ds:
        print("no data"); return
    edges = [(0, 0), (1, 2), (3, 5), (6, 10), (11, 20), (21, 40), (41, 10 ** 9)]
    labels = ["  0 (identical)", "  1-2", "  3-5", "  6-10", " 11-20", " 21-40", " 41+"]
    print(f"consecutive-frame dhash distances over {len(ds)} pairs (range {lo}-{hi}):")
    for (a, b), lab in zip(edges, labels):
        n = sum(1 for d in ds if a <= d <= b)
        if n:
            print(f"{lab:>16} | {'#' * min(60, n)} {n}")
    srt = sorted(ds)
    print(f"  median={srt[len(srt)//2]}  p90={srt[int(len(srt)*.9)]}  max={max(ds)}")
    print("pick --thresh from the valley between the low cluster (same screen) and the high one.")


def cmd_dedupe(tsv, out, thresh, window):
    """Windowed rule: keep a frame unless it is within `thresh` bits of a frame already
    kept within the last `window` seconds. A screen revisited minutes later is new
    evidence — its values may have changed — so it is never deduped against a distant twin.
    """
    rows = load(tsv)
    kept_recent = []            # [(sec, hash)] pruned to the window
    kept, ledger = [], []
    for n, s, h in rows:
        kept_recent = [(ks, kh) for ks, kh in kept_recent if s - ks <= window]
        dup = next((ks for ks, kh in kept_recent if bin(h ^ kh).count("1") <= thresh), None)
        if dup is None:
            kept.append(n)
            kept_recent.append((s, h))
            ledger.append({"frame": n, "sec": s, "status": "kept"})
        else:
            ledger.append({"frame": n, "sec": s, "status": "duplicate", "of_sec": dup})
    json.dump({"total_frames": len(rows), "kept": len(kept), "threshold": thresh,
               "window_sec": window, "rule": "windowed", "ledger": ledger},
              open(out, "w"), indent=1)
    open(out + ".keep", "w").write("\n".join(kept) + "\n")
    print(f"total={len(rows)} kept={len(kept)} dup={len(rows)-len(kept)} "
          f"thresh={thresh} window={window}s")
    print(f"-> {out} and {out}.keep")
    print("next: build tier-2 batches from the .keep file (dump_batches.py), and transcribe")
    print("      EVERY line in it. dump_reconcile.py gates on exactly that set.")


def _opt(argv, flag, default, cast=int):
    return cast(argv[argv.index(flag) + 1]) if flag in argv else default


if __name__ == "__main__":
    a = sys.argv
    if len(a) < 2:
        sys.exit(__doc__)
    c = a[1]
    if c == "hashes":
        crop = tuple(int(x) for x in a[a.index("--crop") + 1].split(",")) if "--crop" in a else DEFAULT_CROP
        cmd_hashes(a[2], a[3], crop)
    elif c == "calib":
        pos = [x for x in a[2:] if not x.startswith("--")]
        cmd_calib(pos[0], *(int(x) for x in pos[1:3]))
    elif c == "dedupe":
        cmd_dedupe(a[2], a[3], _opt(a, "--thresh", DEFAULT_THRESH), _opt(a, "--window", DEFAULT_WINDOW))
    else:
        sys.exit(__doc__)
