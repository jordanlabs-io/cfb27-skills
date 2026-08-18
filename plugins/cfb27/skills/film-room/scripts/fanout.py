#!/usr/bin/env python3
"""Fan the per-batch JSON charting output into (a) legacy batches/outNN.md blocks
for assemble.py and (b) chart_v2_flash.jsonl for the v2 merge.

Agents write batches/json_outNN.json: [{"n": 12, "read": {...}}, ...]
Usage: fanout.py GAMEDIR
"""
import glob
import json
import os
import sys

GAMEDIR = sys.argv[1]
LEGACY_KEYS = ["formation", "personnel", "motion", "play_type", "concept",
               "routes_or_blocking", "def_front", "def_shell_pre", "def_post_snap",
               "def_safeties_post", "def_cb_technique", "def_zone_type",
               "def_coverage", "confidence", "note",
               "formation_initial", "presnap_adjust", "adjust_note", "def_adjust"]

jsonl = open(os.path.join(GAMEDIR, "chart_v2_flash.jsonl"), "w")
count = 0
for path in sorted(glob.glob(os.path.join(GAMEDIR, "batches/json_out*.json"))):
    nn = os.path.basename(path).replace("json_out", "").replace(".json", "")
    blocks = []
    try:
        data = json.load(open(path))
    except json.JSONDecodeError as e:
        print(f"BAD JSON {path}: {e}")
        continue
    for item in data:
        n = int(item["n"])
        read = item.get("read", item)
        lines = [f"PLAY {n:03d}"]
        for k in LEGACY_KEYS:
            v = read.get(k, "")
            if v is None:
                v = ""
            lines.append(f"{k}: {v}")
        blocks.append("\n".join(lines))
        jsonl.write(json.dumps({"n": n, "read": read}) + "\n")
        count += 1
    open(os.path.join(GAMEDIR, f"batches/out{nn}.md"), "w").write("\n\n".join(blocks) + "\n")
jsonl.close()
print(f"fanout: {count} plays -> outNN.md + chart_v2_flash.jsonl")
