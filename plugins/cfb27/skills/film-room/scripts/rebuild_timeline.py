#!/usr/bin/env python3
"""Merge Claude-vision rescue transcriptions into hud_timeline.csv and re-detect plays.

Reads every seg/rescue_json*/sheet*.json under GAMEDIR, patches hud_timeline rows
(agent value wins whenever non-empty; tesseract value kept when agent blank),
then re-runs segment.detect_plays and rewrites seg/plays.csv.
Backs up originals to *.pre_rescue on first run.

Usage: rebuild_timeline.py GAMEDIR
"""
import csv
import glob
import importlib.util
import json
import os
import shutil
import sys

GAMEDIR = sys.argv[1]
SEG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "segment.py")
spec = importlib.util.spec_from_file_location("seg", SEG)
seg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seg)

tl_path = os.path.join(GAMEDIR, "seg/hud_timeline.csv")
pl_path = os.path.join(GAMEDIR, "seg/plays.csv")
for p in (tl_path, pl_path):
    b = p + ".pre_rescue"
    if not os.path.exists(b):
        shutil.copy2(p, b)

patch = {}
n_files = 0
for path in sorted(glob.glob(os.path.join(GAMEDIR, "seg/rescue_json*/sheet*.json"))):
    n_files += 1
    try:
        data = json.load(open(path))
    except json.JSONDecodeError as e:
        print(f"BAD JSON {path}: {e}")
        continue
    for row in data:
        try:
            patch[int(row["t"])] = row
        except (KeyError, TypeError, ValueError):
            continue

rows = list(csv.DictReader(open(tl_path)))
patched = 0
for r in rows:
    t = int(float(r["t"]))
    p = patch.get(t)
    if not p:
        continue
    patched += 1
    for src, dst in (("dd", "dd"), ("clock", "clock"), ("poss", "poss")):
        v = p.get(src)
        if v:
            r[dst] = str(v).upper().replace(" ", "") if src == "dd" else str(v)
    for src, dst in (("qtr", "qtr"), ("playclock", "playclock"),
                     ("score_l", "score_l"), ("score_r", "score_r")):
        v = p.get(src)
        if v is not None and v != "":
            r[dst] = str(v)

with open(tl_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

dd_n = sum(1 for r in rows if r["dd"])
print(f"{n_files} sheet files, {patched} timeline rows patched; dd readable now {dd_n}/{len(rows)} ({100*dd_n/len(rows):.0f}%)")

for r in rows:
    r["t"] = float(r["t"])
windows = seg.detect_plays(rows)
with open(pl_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["n", "qtr", "clock", "dd", "poss", "t_first", "t_last", "score_l", "score_r"])
    for i, p in enumerate(windows, 1):
        w.writerow([i, p["qtr"], p["clock"], p["dd"], p["poss"],
                    p["t_first"], p["t_last"], p["score_l"], p["score_r"]])
print(f"plays re-detected: {len(windows)} -> {pl_path}")
