#!/usr/bin/env python3
"""Fold recheck/json_out*.json overrides into a game's chart and rebuild the CSV.

Used to repair windows that a charting pass wrongly voided as non-play (menu
overlay on live action) or mis-called in short yardage. Recheck reads WIN over
the original read for the windows they cover; every other window is untouched.

Usage: apply_recheck.py GAMEDIR
"""
import csv
import glob
import json
import os
import subprocess
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
PY = os.path.expanduser("~/CFB27-film/.venv/bin/python")
LEGACY_KEYS = ["formation", "personnel", "motion", "play_type", "concept",
               "routes_or_blocking", "def_front", "def_shell_pre", "def_post_snap",
               "def_safeties_post", "def_cb_technique", "def_zone_type",
               "def_coverage", "confidence", "note",
               "formation_initial", "presnap_adjust", "adjust_note", "def_adjust"]

gamedir = sys.argv[1]

# 1. base reads from the existing chart_v2 jsonl
reads = {}
for line in open(os.path.join(gamedir, "chart_v2_flash.jsonl")):
    d = json.loads(line)
    reads[int(d["n"])] = d.get("read", d)
base_n = len(reads)

# 2. recheck overrides win
over = {}
for f in sorted(sorted(sum([glob.glob(os.path.join(gamedir,d,"json_out*.json")) for d in ("recheck","recheck2","recheck3","recheck4","recheck_c")],[]))):
    for it in json.load(open(f)):
        over[int(it["n"])] = it.get("read", it)
reads.update(over)
print(f"{base_n} base reads; {len(over)} recheck overrides applied")

# schema drift: agents sometimes invent play_type values. The schema allows only
# run / pass / non-play; special teams belongs in non-play with a note.
ALLOWED = {"run", "pass", "non-play", "unknown", ""}
fixed = 0
for n, r in reads.items():
    pt = str(r.get("play_type", "")).strip().lower()
    if pt not in ALLOWED:
        r["note"] = f"[{pt}] " + str(r.get("note", ""))
        r["play_type"] = "non-play" if "special" in pt or "team" in pt else "unknown"
        fixed += 1
if fixed:
    print(f"normalised {fixed} off-schema play_type values")

# v3: normalise every enum field via the canonical map (case drift like
# False/false, ambiguous def_zone_type "zone", etc). Values the map doesn't
# cover stay as-is — validate_chart.py flags them for recheck instead.
sys.path.insert(0, SCRIPTS)
import chart_schema as cs  # noqa: E402
norm_count = 0
for n, r in reads.items():
    for field in cs.ENUMS:
        if field in r and r[field] is not None:
            nv = cs.normalise(field, r[field])
            if nv != str(r[field]).strip():
                r[field] = nv
                norm_count += 1
if norm_count:
    print(f"normalised {norm_count} enum values via chart_schema")

# 3. rewrite legacy blocks + jsonl from the merged set
bdir = os.path.join(gamedir, "batches_merged")
os.makedirs(bdir, exist_ok=True)
for old in glob.glob(os.path.join(bdir, "*.md")):
    os.remove(old)
ns = sorted(reads)
with open(os.path.join(gamedir, "chart_v2_flash.jsonl"), "w") as jl:
    blocks = []
    for n in ns:
        r = reads[n]
        lines = [f"PLAY {n:03d}"]
        for k in LEGACY_KEYS:
            v = r.get(k, "")
            lines.append(f"{k}: {'' if v is None else v}")
        blocks.append("\n".join(lines))
        jl.write(json.dumps({"n": n, "read": r}) + "\n")
open(os.path.join(bdir, "out01.md"), "w").write("\n\n".join(blocks) + "\n")

# 4. reassemble, carry adjudicated outcome forward, re-merge v2
csv_path = os.path.join(gamedir, "plays_charted.csv")
subprocess.run([PY, os.path.join(SCRIPTS, "assemble.py"), gamedir, bdir, csv_path], check=True)

bk = sorted(f for f in os.listdir(gamedir) if f.startswith("plays_charted_pre_rechart"))
if bk:
    old = {r["n"]: r for r in csv.DictReader(open(os.path.join(gamedir, bk[0])))}
    rows = list(csv.DictReader(open(csv_path)))
    extra = [k for k in ("result", "yards", "key_event") if k in next(iter(old.values()), {})]
    cols = list(rows[0].keys()) + extra
    for r in rows:
        o = old.get(r["n"], {})
        for k in extra:
            r[k] = o.get(k, "")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"carried forward {extra}")

slug = os.path.basename(gamedir.rstrip("/"))
subprocess.run([PY, os.path.join(SCRIPTS, "merge_v2_local.py"), slug,
                "claude-haiku-4.5-frames/2026-07-31+recheck"], check=True)
