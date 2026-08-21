#!/usr/bin/env python3
"""Stage 3.5: derive per-play snap times from the play-clock lane.

Why this exists (calibration 2026-08-21, UNC at Rutgers): frames.py's motion
onset heuristic fired ~4s EARLY on 96% of windows on that film, because on
online H2H footage the camera is not static pre-snap -- the coach is still in
the play-call screen, and the first sustained motion is the UI, not the snap.
The result was frames cut around the call screen, so agents saw no football and
voided real plays as non-play.

The reliable signal is the play clock. CFB 27 FREEZES the play clock at the
snap; OCR then keeps reporting that same value until the clock resets to 40 for
the next play. So:

    snap = START of the terminal frozen/unreadable block before the reset

Not the END of that block -- timeline_snaps.py takes run[-1] and lands up to 4s
late, and it runs at stage 8 (after frames are already cut) so it only ever
patched tempo columns.

This reads seg/hud_timeline.csv, which after the Claude-sheet HUD rescue is far
more readable than a fresh OCR pass (measured 40% -> 87% on that film), and is
already on disk. Run it AFTER the rescue and BEFORE frames.py.

Usage: snap_times.py GAMEDIR  ->  GAMEDIR/seg/snaps.csv
Then:  frames.py video.mp4 seg/plays.csv film/ --snaps seg/snaps.csv
"""
import csv
import os
import statistics
import sys
from collections import Counter

GAMEDIR = sys.argv[1] if len(sys.argv) > 1 else "."

tl = {}
with open(os.path.join(GAMEDIR, "seg/hud_timeline.csv")) as f:
    for r in csv.DictReader(f):
        pc = (r.get("playclock") or "").strip()
        tl[int(float(r["t"]))] = int(pc) if pc.isdigit() else None


def snap_of(t0, t1):
    """-> (snap_t, playclock_at_snap) or (None, None)."""
    t0, t1 = int(float(t0)), int(float(t1))
    # 1. Find the play-clock RESET (a jump upward >3 = next play armed).
    #    A long window can span two clock cycles when a dead-ball period sits
    #    inside it, so take the LAST reset -- that is the one whose preceding
    #    snap caused this window's down-and-distance to change.
    resets, prev = [], None
    for t in range(t0, t1 + 9):
        v = tl.get(t)
        if v is None:
            continue
        if prev is not None and v > prev + 3:
            resets.append(t)
        prev = v
    end = (resets[-1] - 1) if resets else t1
    # 2. Terminal value = last readable second before that reset.
    tv = tv_t = None
    for t in range(end, t0 - 1, -1):
        if tl.get(t) is not None:
            tv, tv_t = tl[t], t
            break
    if tv is None:
        return None, None
    # 3. Walk back over the terminal block -- same value (frozen) or
    #    unreadable (hidden). Its START is the snap.
    s = tv_t
    t = tv_t - 1
    while t >= t0 and (tl.get(t) is None or tl.get(t) == tv):
        s, t = t, t - 1
    return s, tv


rows = []
with open(os.path.join(GAMEDIR, "seg/plays.csv")) as f:
    for r in csv.DictReader(f):
        s, pc = snap_of(r["t_first"], r["t_last"])
        rows.append({"n": r["n"], "dd": r["dd"], "t_first": r["t_first"],
                     "t_last": r["t_last"], "snap": s, "playclock_at_snap": pc,
                     "src": "playclock" if s is not None else ""})

# Guard: a snap outside its own window means the reset search escaped into a
# neighbouring play. Blank it rather than cutting frames from the wrong play.
out_of_window = 0
for r in rows:
    if r["snap"] is None:
        continue
    if not (float(r["t_first"]) - 1 <= r["snap"] <= float(r["t_last"]) + 1):
        r["snap"], r["src"], out_of_window = None, "", out_of_window + 1

with open(os.path.join(GAMEDIR, "seg/snaps.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

got = [r for r in rows if r["snap"] is not None]
pcs = [r["playclock_at_snap"] for r in got if r["playclock_at_snap"] is not None]
print(f"snap_times: {len(got)}/{len(rows)} windows from the play-clock lane "
      f"({out_of_window} dropped as out-of-window)")
if pcs:
    med = statistics.median(pcs)
    print(f"  median playclock_at_snap = {med:.0f} "
          f"(online H2H film normally lands ~18-24; a median <=5 means the "
          f"lane is reading the wrong band)")
if len(got) < len(rows):
    print(f"  {len(rows)-len(got)} window(s) have no play-clock snap -- "
          f"frames.py falls back to its motion estimate for those")
