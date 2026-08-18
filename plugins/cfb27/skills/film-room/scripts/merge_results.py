#!/usr/bin/env python3
"""Merge adjudicate_hud.py output into plays_charted.csv as result/yards/key_event
(NW-Vandy precedent: silent film -> HUD lane is the result source of record).
Usage: merge_results.py GAMEDIR
"""
import csv
import os
import sys

GAMEDIR = sys.argv[1]
hud = {r["n"]: r for r in csv.DictReader(open(os.path.join(GAMEDIR, "hud_results.csv")))}
path = os.path.join(GAMEDIR, "plays_charted.csv")
rows = list(csv.DictReader(open(path)))
for r in rows:
    h = hud.get(r["n"], {})
    r["result"] = h.get("hud_result", "")
    r["yards"] = h.get("hud_yards", "")
    r["key_event"] = h.get("hud_key_event", "")
cols = [c for c in rows[0].keys()]
with open(path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
n_res = sum(1 for r in rows if r["result"])
print(f"merged HUD results into {path}: {n_res}/{len(rows)} plays have a result")
