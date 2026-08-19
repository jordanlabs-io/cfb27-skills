#!/usr/bin/env python3
"""Lane C stage 1: turn dynasty-MENU footage (or a folder of screenshots) into
a deduped, ordered set of screen frames for vision transcription.

Menu footage is scrolling through static screens — box scores, schedule/season
records, standings, award races, roster pages, recruiting boards. This script:
  1. samples frames (1 fps for video input; screenshots pass through),
  2. drops near-duplicate consecutive frames (perceptual difference below
     threshold — the user pausing on a screen produces dozens of identical
     frames),
  3. writes the survivors to OUTDIR/screens/scr0001.jpg... plus manifest.csv
     (frame, t, diff) for the transcription agents.

Screen-type classification and transcription are the vision agents' job
(SKILL.md Lane C): agents label each frame's screen type and transcribe
verbatim — numbers exactly as displayed, [sic] on garbles, never inferred.
Structured merge to dynasties/ follows dynasty-tracker conventions and is
validated by verify_dynasties.py, not by the chart validator.

Usage:
  menu_ingest.py VIDEO_OR_DIR OUTDIR [--fps 1] [--thresh 6.0]
"""
import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops, ImageStat

IMG_EXT = {".jpg", ".jpeg", ".png", ".heic"}


def frame_diff(a, b):
    """Mean absolute pixel difference on 128px thumbnails (0 = identical)."""
    ta = a.convert("L").resize((128, 96))
    tb = b.convert("L").resize((128, 96))
    return ImageStat.Stat(ImageChops.difference(ta, tb)).mean[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="menu-footage video OR a directory of screenshots")
    ap.add_argument("outdir")
    ap.add_argument("--fps", type=float, default=1.0)
    ap.add_argument("--thresh", type=float, default=6.0,
                    help="min mean-pixel diff vs the last KEPT frame")
    args = ap.parse_args()

    screens = os.path.join(args.outdir, "screens")
    os.makedirs(screens, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        if os.path.isdir(args.src):
            files = sorted(f for f in os.listdir(args.src)
                           if os.path.splitext(f)[1].lower() in IMG_EXT)
            frames = [(i / args.fps, os.path.join(args.src, f))
                      for i, f in enumerate(files)]
        else:
            r = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-i", args.src, "-vf", f"fps={args.fps}", "-q:v", "3",
                 os.path.join(td, "f%05d.jpg")],
                capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit(f"ffmpeg failed: {r.stderr[-300:]}")
            frames = [(i / args.fps, os.path.join(td, f))
                      for i, f in enumerate(sorted(os.listdir(td)))]
        if not frames:
            sys.exit("no frames found")

        kept, last_img = [], None
        for t, fp in frames:
            img = Image.open(fp).convert("RGB")
            d = frame_diff(last_img, img) if last_img is not None else 255.0
            if d >= args.thresh:
                idx = len(kept) + 1
                out = os.path.join(screens, f"scr{idx:04d}.jpg")
                shutil.copy(fp, out) if fp.startswith(args.src) else img.save(out, quality=88)
                kept.append({"frame": f"scr{idx:04d}.jpg", "t": round(t, 1),
                             "diff": round(d, 1)})
                last_img = img

    with open(os.path.join(args.outdir, "manifest.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["frame", "t", "diff"])
        w.writeheader()
        w.writerows(kept)
    print(f"{len(frames)} frames sampled -> {len(kept)} unique screens in {screens}")
    print("next: batch screens to vision agents for screen-type labelling + "
          "verbatim transcription (SKILL.md Lane C)")


if __name__ == "__main__":
    main()
