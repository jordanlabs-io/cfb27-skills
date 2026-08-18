#!/usr/bin/env python3
"""Tendency splits digest from plays_charted.csv (v2 columns included).
Usage: splits.py GAMEDIR TEAM_L TEAM_R
Prints a per-team digest: offense identity + the defense they faced.
"""
import csv
import re
import sys
from collections import Counter, defaultdict

GAMEDIR, TEAM_L, TEAM_R = sys.argv[1], sys.argv[2], sys.argv[3]
rows = list(csv.DictReader(open(f"{GAMEDIR}/plays_charted.csv")))
rows.sort(key=lambda r: int(r["n"]))
DD = re.compile(r"([1234])&(\d+|GOAL|INCHES)", re.I)
SCORED = {"touchdown", "field-goal"}


def real(r):
    return (r.get("play_type") or "") in ("run", "pass")


def down_dist(r):
    m = DD.match(r.get("dd") or "")
    if not m:
        return None, None
    d = m.group(2).upper()
    dist = 1 if d == "INCHES" else (None if d == "GOAL" else int(d))
    return int(m.group(1)), dist


def bucket(dist):
    if dist is None:
        return "goal"
    return "short(1-3)" if dist <= 3 else ("med(4-6)" if dist <= 6 else "long(7+)")


def pct(a, b):
    return f"{a}/{b} ({100*a/b:.0f}%)" if b else "0/0"


def conversion(i):
    """Did window i pick up a first down? -> True / False / None (undetermined).

    Derived from the NEXT window in the same possession, NOT from string
    matching. The old test looked for "1ST-DOWN"/"first down"/"TD" inside
    key_event and result, none of which this pipeline ever writes — so every
    third down scored as a failure (it printed Vanderbilt 0/18 where the truth
    was 3/18). Windows whose successor is unreadable are 'undetermined' and
    leave the denominator rather than being silently scored as failures.
    """
    r = rows[i]
    if ((r.get("result") or "") in SCORED
            or "touchdown" in (r.get("key_event") or "").lower()):
        return True
    for j in range(i + 1, min(i + 3, len(rows))):
        nxt = rows[j]
        if (nxt.get("play_type") or "") == "non-play":
            continue
        nd, _ = down_dist(nxt)
        if nd is None:
            return None
        if nxt["poss"] != r["poss"]:
            return False              # possession changed -> did not convert
        return nd == 1                # same offense, fresh set of downs
    return None


for side, team in (("L", TEAM_L), ("R", TEAM_R)):
    # Older workspaces sometimes stored team names instead of scorebug L/R.
    poss_values = {side, team}
    off_i = [i for i, r in enumerate(rows)
             if r["poss"] in poss_values and real(r)]
    off = [rows[i] for i in off_i]
    print(f"\n{'='*20} {team} OFFENSE — {len(off)} charted run/pass snaps {'='*20}")
    rp = Counter(r["play_type"] for r in off)
    print(f"run {rp['run']} / pass {rp['pass']}  (vision play_type, pass-bias caveat)")
    by_down = defaultdict(Counter)
    for r in off:
        d, dist = down_dist(r)
        if d:
            by_down[d][r["play_type"]] += 1
    for d in sorted(by_down):
        c = by_down[d]
        print(f"  down {d}: run {c['run']} / pass {c['pass']}")
    for down in (3, 4):
        buckets = defaultdict(lambda: [0, 0, 0])       # converted, failed, undet
        for i in off_i:
            d, dist = down_dist(rows[i])
            if d != down:
                continue
            c = conversion(i)
            buckets[bucket(dist)][0 if c is True else 1 if c is False else 2] += 1
        if not buckets:
            continue
        conv = sum(b[0] for b in buckets.values())
        fail = sum(b[1] for b in buckets.values())
        undet = sum(b[2] for b in buckets.values())
        print(f"  down {down} conversions: {pct(conv, conv + fail)}"
              + (f"  [{undet} undetermined]" if undet else ""))
        for b in ("short(1-3)", "med(4-6)", "long(7+)", "goal"):
            if b in buckets:
                c, f_, u = buckets[b]
                print(f"    {down} {b:<11} {pct(c, c + f_)}"
                      + (f"  [{u} undet]" if u else ""))
    form = Counter()
    for r in off:
        f = (r.get("formation") or "unknown").lower()
        fam = ("gun" if "gun" in f or "shotgun" in f else
               "pistol" if "pistol" in f else
               "i-form" if "i-form" in f or "iform" in f else
               "empty" if "empty" in f else
               "singleback" if "single" in f or "ace" in f else
               "spread" if "spread" in f else "other/unk")
        form[(fam, r["play_type"])] += 1
    fams = sorted({k[0] for k in form})
    print("  formation x type: " + "; ".join(
        f"{fam}: {form[(fam,'run')]}r/{form[(fam,'pass')]}p" for fam in fams))
    mo = Counter((r.get("motion") or "unknown", r["play_type"]) for r in off)
    print(f"  motion: yes {mo[('yes','run')]}r/{mo[('yes','pass')]}p · no {mo[('no','run')]}r/{mo[('no','pass')]}p")
    adj = Counter(r.get("presnap_adjust") or "?" for r in off)
    print(f"  presnap_adjust: {dict(adj)}")
    aud = Counter((r.get("formation_initial") or "?", r.get("formation") or "?")
                  for r in off if (r.get("presnap_adjust") or "") in ("audible", "shift"))
    if aud:
        print("  audible/shift transitions: " + "; ".join(
            f"{a} -> {b}: {c}" for (a, b), c in aud.most_common(8)))
    v2m = Counter(r.get("v2_motion_type") or "?" for r in off)
    print(f"  v2_motion_type: {dict(v2m)}")
    tempo = Counter(r.get("tempo") or "?" for r in off if r.get("tempo"))
    print(f"  tempo: {dict(tempo)}")
    qd = Counter(r.get("v2_qb_drop") or "?" for r in off if r["play_type"] == "pass")
    print(f"  qb_drop (pass): {dict(qd)}")
    ta = Counter(r.get("v2_target_area") or "?" for r in off if r["play_type"] == "pass")
    print(f"  target_area: {dict(ta)}")
    rd = Counter(r.get("v2_run_direction") or "?" for r in off if r["play_type"] == "run")
    print(f"  run_direction: {dict(rd)}")
    pr = Counter(r.get("v2_pressure") or "?" for r in off if r["play_type"] == "pass")
    print(f"  pressure taken: {dict(pr)}")

    # defense they faced = other team's D
    dteam = TEAM_R if side == "L" else TEAM_L
    print(f"\n  ---- {dteam} DEFENSE vs this offense ({len(off)} snaps) ----")
    sh = Counter(r.get("def_shell_pre") or "?" for r in off)
    print(f"  shell_pre: {dict(sh)}")
    sp = Counter(r.get("def_safeties_post") or "?" for r in off)
    print(f"  safeties_post: {dict(sp)}")
    rot = Counter(r.get("def_rotation") or "?" for r in off)
    print(f"  rotation: {dict(rot)}")
    fr = Counter(r.get("def_front") or "?" for r in off)
    print(f"  front: {dict(fr)}")
    bx = Counter(r.get("v2_box_count") or "?" for r in off)
    print(f"  box: {dict(bx)}")
    cb = Counter(r.get("def_cb_technique") or "?" for r in off)
    print(f"  cb_technique: {dict(cb)}")
    cbr = Counter(r.get("v2_cb_relation") or "?" for r in off)
    print(f"  cb_relation: {dict(cbr)}")
    ru = Counter(r.get("v2_rushers") or "?" for r in off if r["play_type"] == "pass")
    print(f"  rushers (pass): {dict(ru)}")
    mz = Counter((r.get("man_zone_verdict") or "?", r.get("mz_confidence") or "0") for r in off)
    print(f"  man/zone verdicts (verdict,conf): {dict(mz)}")
    cov = Counter(r.get("def_coverage") or "?" for r in off if (r.get("def_coverage") or "") not in ("", "unknown"))
    print(f"  coverage families (agent-called): {dict(cov)}")

print(f"\n{'='*20} KEY EVENTS / RESULTS {'='*20}")
ev = Counter(r.get("key_event") or "" for r in rows if r.get("key_event"))
print(dict(ev))
menus = [(r["n"], r["poss"], r.get("v2_screen_call"), r.get("v2_menu_tiles"))
         for r in rows if (r.get("v2_screen_call") or "unknown") not in ("unknown", "", "n/a")]
print(f"\nscreen_calls read: {len(menus)}")
for n, poss, call, _tiles in menus[:40]:
    print(f"  p{n} poss={poss}: {call}")
