#!/usr/bin/env python3
"""Derive tempo columns from the (Claude-rescued) hud_timeline playclock lane.

PLAN-snap-anchoring.md A7 (2026-09-09): this script used to OVERWRITE snap_t
with its own run[-1]-based estimate, which lands up to several seconds LATE
(21 of 29 film dirs had snap_t overwritten this way, some by +4-5s median —
see references/calibration-history.md). It no longer writes snap_t at all.
snap_t's single source of truth is now frames.py/snap_times.py's sub-second
refined estimate (snap_src=preplay-chip/motion-sustained/playclock-bracket),
already in plays_charted.csv via assemble.py. This script only computes
sec_since_prev_snap and tempo from that existing snap_t.

Patches plays_charted.csv: sec_since_prev_snap, tempo (snap_t / snap_src /
playclock_at_snap are left untouched).
Usage: timeline_snaps.py GAMEDIR
"""
import csv
import os
import sys

GAMEDIR = sys.argv[1]

path = os.path.join(GAMEDIR, "plays_charted.csv")
rows = list(csv.DictReader(open(path)))

if rows and "snap_src" not in rows[0]:
    print(f"timeline_snaps: NOTE — {path} has no snap_src column. This game "
          f"was charted before PLAN-snap-anchoring.md A2-A6 shipped; snap_t "
          f"is the old coarse (integer-second, early-biased) estimate and "
          f"has not been re-cut. See references/calibration-history.md "
          f"'known debt' list. tempo columns below are still computed from "
          f"whatever snap_t is present.", file=sys.stderr)

prev = {"poss": None, "snap": None}
patched = 0
missing_snap_t = 0
for row in rows:
    snap_str = (row.get("snap_t") or "").strip()
    if not snap_str:
        missing_snap_t += 1
        continue
    try:
        snap = float(snap_str)
    except ValueError:
        missing_snap_t += 1
        continue
    if prev["snap"] is not None and row["poss"] == prev["poss"] and row["poss"]:
        gap = round(snap - prev["snap"], 1)
        row["sec_since_prev_snap"] = str(gap)
        row["tempo"] = "hurry-up" if gap < 20 else ("slow" if gap > 34 else "normal")
        patched += 1
    prev = {"poss": row["poss"], "snap": snap}

with open(path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

print(f"timeline_snaps: tempo computed for {patched}/{len(rows)} plays "
      f"({missing_snap_t} had no snap_t to anchor on)")
