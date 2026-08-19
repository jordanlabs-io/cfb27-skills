#!/usr/bin/env python3
"""Merge chart_v2_flash.jsonl (Claude-vision lane) into plays_charted.csv as v2_* columns
+ derived man_zone_verdict. Adapted from prior session's merge_v2.py; adds menu-intel fields.
Usage: merge_v2_local.py SLUG TAG"""
import csv
import importlib.util
import json
import os
import shutil
import sys

BASE = "/Users/elijah/CFB27-film"
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("assemble", os.path.join(SCRIPTS, "assemble.py"))
assemble = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assemble)

V2_FIELDS = ["off_formation", "def_shell_pre", "cb_depth_pre", "play_type",
             "motion_type", "motion_response", "def_front", "box_count", "nickel_present",
             "rushers", "cb_relation", "lb_pass_action", "crosser_handoff",
             "qb_drop", "target_area", "run_direction", "pressure",
             "menu_visible", "menu_side", "screen_call", "menu_tiles",
             "def_shell_initial", "adjust_seq", "playart_delta", "postsnap_confirms"]
NEW_COLS = ["v2_" + f for f in V2_FIELDS] + ["man_zone_verdict", "mz_confidence", "v2_src"]


def merge_game(slug, tag):
    gdir = f"{BASE}/{slug}"
    cov_path = f"{gdir}/chart_v2_flash.jsonl"
    csv_path = f"{gdir}/plays_charted.csv"
    backup = f"{gdir}/plays_charted_pre_v2.csv"
    if not os.path.exists(backup):
        shutil.copy2(csv_path, backup)
    v2 = {}
    for line in open(cov_path):
        d = json.loads(line)
        if "read" in d:
            v2[int(d["n"])] = d["read"]
    rows = list(csv.DictReader(open(csv_path)))
    base_cols = [c for c in rows[0].keys() if c not in NEW_COLS]
    matched, mz_counts = 0, {}
    for r in rows:
        for k in NEW_COLS:
            r.setdefault(k, "")
        c = v2.get(int(r["n"]))
        if not c:
            continue
        matched += 1
        for f in V2_FIELDS:
            v = c.get(f)
            if f == "off_formation" and v is None:
                v = c.get("formation")
            r["v2_" + f] = "" if v is None else (json.dumps(v) if isinstance(v, list) else str(v))
        verdict, conf = assemble.derive_man_zone(c)
        r["man_zone_verdict"], r["mz_confidence"] = verdict, str(conf)
        r["v2_src"] = tag
        mz_counts[verdict] = mz_counts.get(verdict, 0) + 1
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=base_cols + NEW_COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"[{slug}] merged {matched}/{len(rows)} plays; man/zone: {mz_counts}")


if __name__ == "__main__":
    merge_game(sys.argv[1], sys.argv[2])
