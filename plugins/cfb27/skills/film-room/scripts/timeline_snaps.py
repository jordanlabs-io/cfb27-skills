#!/usr/bin/env python3
"""Derive per-play snap times from the (Claude-rescued) hud_timeline playclock lane.

CFB 27 hides the play clock at the snap, so within a play window the snap is the
last second with a readable, counting play clock before it vanishes or resets
upward. This replaces frames.py's motion-heuristic snap_est for the tempo columns.

Patches plays_charted.csv: snap_t, playclock_at_snap, sec_since_prev_snap, tempo.
Usage: timeline_snaps.py GAMEDIR
"""
import csv
import os
import sys

GAMEDIR = sys.argv[1]
tl = {}
for r in csv.DictReader(open(os.path.join(GAMEDIR, "seg/hud_timeline.csv"))):
    t = int(float(r["t"]))
    pc = r.get("playclock", "")
    tl[t] = int(pc) if pc.strip().isdigit() else None

path = os.path.join(GAMEDIR, "plays_charted.csv")
rows = list(csv.DictReader(open(path)))
prev = {"poss": None, "snap": None}
fixed = 0
for row in rows:
    # window bounds from seg/plays.csv columns already merged? plays_charted lacks
    # t_first/t_last, so re-read from seg/plays.csv by n.
    pass

wins = {r["n"]: (float(r["t_first"]), float(r["t_last"]))
        for r in csv.DictReader(open(os.path.join(GAMEDIR, "seg/plays.csv")))}

for row in rows:
    w = wins.get(row["n"])
    if not w:
        continue
    t0, t1 = int(w[0]), int(w[1])
    snap, pc_at = None, ""
    run = []   # consecutive readable pc values
    for t in range(t0 - 2, t1 + 7):
        pc = tl.get(t)
        if pc is None:
            if len(run) >= 2:
                # vanished after counting -> snap at last readable second
                snap, pc_at = run[-1]
                # require it actually counted down (not a static misread)
                vals = [v for _, v in run[-4:]]
                if len(set(vals)) == 1 and len(vals) >= 3:
                    snap = None
                    run = []
                    continue
                break
            run = []
            continue
        if run and pc > run[-1][1] + 3:
            if len(run) >= 3:
                snap, pc_at = run[-1]   # reset upward = next play armed
                break
            run = []
        run.append((t, pc))
    else:
        if len(run) >= 3:
            snap, pc_at = run[-1]
    if snap is None:
        continue
    fixed += 1
    row["snap_t"] = str(float(snap))
    row["playclock_at_snap"] = str(pc_at)
    gap = ""
    if prev["snap"] and row["poss"] == prev["poss"] and row["poss"]:
        gap = round(float(snap) - prev["snap"], 1)
        row["sec_since_prev_snap"] = str(gap)
        row["tempo"] = "hurry-up" if gap < 20 else ("slow" if gap > 34 else "normal")
    prev = {"poss": row["poss"], "snap": float(snap)}

with open(path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

pcs = sorted(float(r["playclock_at_snap"]) for r in rows if r["playclock_at_snap"])
med = pcs[len(pcs) // 2] if pcs else -1
print(f"timeline snaps: {fixed}/{len(rows)} plays patched; median playclock_at_snap={med}")
