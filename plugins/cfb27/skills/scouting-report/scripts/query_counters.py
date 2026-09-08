#!/usr/bin/env python3
"""Read-only query over a scouting-report call-sheet CSV
(`film-room/call-sheets/<team>.csv`, written by film-room's call_ledger.py).

The ledger is long-format: one row per film x play, so the same play tile
appears once per film it showed up in. Lifetime counters can't fall (a lower
reading on a later film is that film's parse failing to read the tile, not
the coach abandoning the call) -- so the current count for a play is the MAX
`calls` across its rows, not any single row. This script applies that rule
so callers never have to eyeball the CSV by hand.

Usage:
  query_counters.py <call-sheets.csv> [--top N] [--play SUBSTRING]
"""
import argparse
import csv
import re
import sys
from collections import defaultdict


def normalise(play):
    """Loose form used only to flag possible name-variant collisions --
    never used to merge rows, since a wrong merge silently fuses two
    different plays' counter histories."""
    s = play.lower()
    s = s.replace(":", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_path")
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--play", default=None, help="substring filter on play name")
    args = ap.parse_args()

    # play -> list of (calls, avg_yds, film) rows, kept for max-picking
    rows_by_play = defaultdict(list)
    with open(args.csv_path, newline="") as f:
        for row in csv.DictReader(f):
            play = row["play"]
            try:
                calls = int(float(row["calls"]))
            except (KeyError, ValueError):
                calls = 0
            try:
                avg_yds = float(row["avg_yds"])
            except (KeyError, ValueError):
                avg_yds = None
            rows_by_play[play].append((calls, avg_yds, row.get("film", "")))

    if args.play:
        needle = args.play.lower()
        rows_by_play = {p: v for p, v in rows_by_play.items() if needle in p.lower()}

    if not rows_by_play:
        print("No matching plays.", file=sys.stderr)
        return 1

    # current count per play = max calls seen for it, with the avg_yds and
    # film that produced that max (a lower reading elsewhere is unread, not
    # a real decrease -- see module docstring).
    current = {}
    for play, entries in rows_by_play.items():
        best = max(entries, key=lambda e: e[0])
        current[play] = best  # (calls, avg_yds, film)

    # flag normalized-name collisions across DIFFERENT exact play strings,
    # without merging them.
    norm_groups = defaultdict(list)
    for play in current:
        norm_groups[normalise(play)].append(play)
    variant_of = {}
    for norm, plays in norm_groups.items():
        if len(plays) > 1:
            for p in plays:
                others = [o for o in plays if o != p]
                variant_of[p] = others

    ordered = sorted(current.items(), key=lambda kv: kv[1][0], reverse=True)
    if args.top:
        ordered = ordered[: args.top]

    for play, (calls, avg_yds, film) in ordered:
        avg_str = f"{avg_yds:.1f}" if avg_yds is not None else "?"
        print(f"{calls:>4} calls  {avg_str:>6} avg  {play}  (from {film})")
        if play in variant_of:
            for other in variant_of[play]:
                print(f'        ⚠ possible variant of "{other}" -- check before treating as separate')

    return 0


if __name__ == "__main__":
    sys.exit(main())
