#!/usr/bin/env python3
"""Cross-check charted play_type against the independent adjudication lane.

The transcript/HUD adjudication records an outcome word that constrains play_type:
  complete / incomplete / interception  -> MUST be a pass
  sack                                  -> MUST be a pass (dropback)
A row violating that is a charting error, not a judgement call.

Also flags special-teams language sitting in the run/pass pool.

Usage: validate_chart.py GAMEDIR [...]
"""
import csv
import re
import sys

PASS_ONLY = re.compile(r"\b(complete|incomplete|interception|intercepted|sack)\b", re.I)
ST_WORDS = re.compile(r"\b(punt|kickoff|kick off|field goal|FG|extra point|PAT|touchback)\b", re.I)

for gamedir in sys.argv[1:]:
    rows = list(csv.DictReader(open(f"{gamedir}/plays_charted.csv")))
    bad_run, st_in_pool = [], []
    for r in rows:
        pt = (r.get("play_type") or "").lower()
        outcome = f"{r.get('result','')} {r.get('key_event','')}"
        note = r.get("note", "")
        if pt == "run" and PASS_ONLY.search(outcome):
            bad_run.append((r["n"], r["dd"], outcome.strip(), note[:60]))
        if pt in ("run", "pass") and ST_WORDS.search(note):
            st_in_pool.append((r["n"], pt, note[:70]))
    print(f"\n=== {gamedir}  ({len(rows)} windows)")
    print(f"  run-labelled but outcome implies pass: {len(bad_run)}")
    for n, dd, o, nt in bad_run:
        print(f"    p{n} dd={dd} outcome='{o}' note={nt}")
    print(f"  special-teams language inside run/pass pool: {len(st_in_pool)}")
    for n, pt, nt in st_in_pool[:12]:
        print(f"    p{n} [{pt}] {nt}")

# --- game-boundary detector (added 2026-07-31 after a second game was found
# --- charted inside the OSU-Maryland VOD). A score that DROPS, or a quarter
# --- that resets to 1 late in the file, means the film rolled into a new game.
import csv as _csv
import sys as _sys


def _score_pair(s):
    try:
        a, b = (s or "").split("-")
        return int(a), int(b)
    except ValueError:
        return None


print("\n--- game-boundary check")
for gamedir in _sys.argv[1:]:
    rows = list(_csv.DictReader(open(f"{gamedir}/plays_charted.csv")))
    hits, prev, prev_q = [], None, 0
    for x in rows:
        sc = _score_pair(x.get("score", ""))
        q = x.get("qtr", "").strip()
        if sc and prev and (sc[0] < prev[0] or sc[1] < prev[1]):
            hits.append(f"p{x['n']}: score went BACKWARD {prev[0]}-{prev[1]} -> {sc[0]}-{sc[1]}")
        if q == "1" and prev_q >= 3:
            hits.append(f"p{x['n']}: quarter reset to 1 after Q{prev_q}")
        if sc:
            prev = sc
        if q.isdigit():
            prev_q = int(q)
    print(f"  {gamedir}: {len(hits)} boundary signal(s)")
    for h in hits[:6]:
        print(f"    {h}")
