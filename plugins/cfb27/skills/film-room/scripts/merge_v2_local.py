#!/usr/bin/env python3
"""Merge chart_v2_flash.jsonl (Claude-vision lane) into plays_charted.csv as v2_* columns
+ derived columns (man_zone_verdict, coverage_candidates, field_side, play_style,
hud_conflict, def_coverage_src, schema_version). Field list and column order come
from chart_schema.py — the v3 canonical schema.
Usage: merge_v2_local.py SLUG TAG"""
import csv
import importlib.util
import json
import os
import re
import shutil
import sys

BASE = os.environ.get("CFB27_FILM_BASE", os.path.expanduser("~/CFB27-film"))
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("assemble", os.path.join(SCRIPTS, "assemble.py"))
assemble = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assemble)
sys.path.insert(0, SCRIPTS)
import chart_schema as cs

V2_FIELDS = cs.V2_FIELDS
NEW_COLS = (["v2_" + f for f in V2_FIELDS] + cs.DERIVED_COLUMNS
            + ["def_coverage_src", "coverage_candidates"])


def derive_coverage_candidates(read):
    """Top-2 plausible families from pre-snap structure, for rows where
    def_coverage stays unknown. Leans only — splits must never count these as
    calls (chart-schema.md)."""
    shell = (read.get("def_shell_pre") or "").lower()
    lev = cs.normalise("cb_leverage_pre", read.get("cb_leverage_pre"))
    depth = cs.normalise("saf_depth_band", read.get("saf_depth_band"))
    trips = cs.normalise("saf_nickel_trips_side", read.get("saf_nickel_trips_side"))
    cbd = (read.get("cb_depth_pre") or "").lower()
    if lev == "mixed" or depth == "split":
        return "cover-6, cover-9 plausible"
    if shell == "1-high" or shell == "0-high":
        if lev == "inside":
            return "cover-1, cover-0 plausible"
        if trips == "both":
            return "cover-1, cover-3 plausible"
        if trips == "safety-opposite":
            return "cover-3, cover-1 plausible"
        return "cover-3, cover-1 plausible" if shell == "1-high" else ""
    if shell == "2-high":
        if lev == "inside" or (cbd == "press" and lev != "head-up"):
            return "cover-2-man, cover-1 plausible"
        if lev == "head-up" or depth == "<10" or depth == "10-14":
            return "cover-4, cover-2 plausible"
        return "cover-2, cover-4 plausible"
    return ""


def derive_field_side(read):
    hash_ = cs.normalise("ball_hash", read.get("ball_hash"))
    return {"left": "field-right", "right": "field-left", "middle": "balanced"}.get(hash_, "")


def derive_play_style(read, row):
    pt = (row.get("play_type") or "").lower()
    concept = f'{row.get("concept") or ""} {read.get("screen_call") or ""}'.lower()
    if pt == "pass" and cs.normalise("screen_dir", read.get("screen_dir")) in ("L", "R", "middle"):
        return "screen"
    if pt == "pass" and "screen" in concept:
        return "screen"
    if cs.normalise("rpo_look", read.get("rpo_look")) == "yes":
        return "rpo"
    if pt == "pass" and cs.normalise("pa_fake", read.get("pa_fake")) == "yes":
        return "pa-pass"
    return pt


def derive_hud_conflict(read, row):
    """Vision's full-frame scorebug read vs the machine HUD row. Deterministic
    lane stays primary; a conflict is a flag for the rescue/adjudication lanes."""
    conflicts = []
    h_poss = cs.normalise("hud_poss", read.get("hud_poss"))
    if h_poss in ("L", "R", "l", "r") and (row.get("poss") or "") and h_poss.upper() != row["poss"].upper():
        conflicts.append(f"poss:{row['poss']}!={h_poss.upper()}")
    def canon_dd(s):
        s = (s or "").strip().upper().replace(" ", "").replace("AND", "&")
        s = re.sub(r"(\d)(ST|ND|RD|TH)", r"\1", s)   # 1ST&10 -> 1&10
        return s
    h_dd = canon_dd(read.get("hud_dd"))
    m_dd = canon_dd(row.get("dd"))
    if h_dd and h_dd not in ("UNKNOWN", "N/A") and m_dd and h_dd != m_dd:
        conflicts.append(f"dd:{m_dd}!={h_dd}")
    return "; ".join(conflicts)


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
    matched, mz_counts, conflicts = 0, {}, 0
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
            if isinstance(v, list):
                r["v2_" + f] = json.dumps(v)
            else:
                r["v2_" + f] = cs.normalise(f, v) if v is not None else ""
        verdict, conf = assemble.derive_man_zone(c)
        r["man_zone_verdict"], r["mz_confidence"] = verdict, str(conf)
        # coverage ladder: play art (the call itself) > agent post-snap ID > derivation
        playart_cov = (c.get("def_playart_coverage") or "").strip().lower()
        if playart_cov and playart_cov not in ("unknown", "n/a", "none"):
            r["def_coverage"] = playart_cov
            r["def_coverage_src"] = "playart"
        elif (r.get("def_coverage") or "") not in ("", "unknown"):
            r.setdefault("def_coverage_src", "")
            if not r["def_coverage_src"]:
                r["def_coverage_src"] = "agent" if (c.get("def_coverage") or "").strip() else "derived"
        if (r.get("def_coverage") or "unknown") == "unknown":
            r["coverage_candidates"] = derive_coverage_candidates(c)
        r["field_side"] = derive_field_side(c)
        r["play_style"] = derive_play_style(c, r)
        hc = derive_hud_conflict(c, r)
        r["hud_conflict"] = hc
        if hc:
            conflicts += 1
        r["schema_version"] = cs.SCHEMA_VERSION
        r["v2_src"] = tag
        mz_counts[verdict] = mz_counts.get(verdict, 0) + 1
    cols = cs.ordered_columns(list(rows[0].keys()))
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"[{slug}] merged {matched}/{len(rows)} plays; man/zone: {mz_counts}; "
          f"hud_conflicts: {conflicts}")


if __name__ == "__main__":
    merge_game(sys.argv[1], sys.argv[2])
