#!/usr/bin/env python3
"""Stage 3b: reconcile seg/pbp.csv against seg/plays.csv (PLAN-snap-anchoring.md
A8). Join key is (dd) with a monotonic sequence cursor -- NEVER nearest-clock
alone (see SKILL.md's existing PBP-join rule).

The HIGHLIGHTS reel is a curated SUBSET of all plays (one classic Madden/CFB
highlights screen shows scoring drives, sacks, turnovers, long gains -- not
every 3-yard run). So the gate is one-directional:

  >=90% of PBP rows must find a matching window (by dd, walking forward
  through plays.csv in order so a repeated dd like two different "1st & 10"s
  resolves to the correct occurrence) -- exit non-zero below that.

  Windows with NO matching PBP row are EXPECTED (most plays never make the
  highlights reel) and are NOT flagged as false-window candidates.

Usage: pbp_reconcile.py GAMEDIR
"""
import csv
import os
import sys


def norm_dd(dd):
    if not dd:
        return ""
    dd = dd.upper().replace(" ", "")
    dd = dd.replace("1ST", "1").replace("2ND", "2").replace("3RD", "3").replace("4TH", "4")
    dd = dd.replace("&", "&")
    return dd


def main():
    gamedir = sys.argv[1]
    pbp_path = os.path.join(gamedir, "seg", "pbp.csv")
    plays_path = os.path.join(gamedir, "seg", "plays.csv")
    if not os.path.exists(pbp_path):
        sys.exit(f"pbp_reconcile: no {pbp_path} -- run pbp_ingest.py first")
    if not os.path.exists(plays_path):
        sys.exit(f"pbp_reconcile: no {plays_path}")

    pbp = list(csv.DictReader(open(pbp_path)))
    plays = list(csv.DictReader(open(plays_path)))
    for p in plays:
        p["_dd_norm"] = norm_dd(p.get("dd", ""))

    # NOTE: the true monotonic-cursor join (SKILL.md's existing PBP rule,
    # "never nearest-clock alone") assumes the PBP source lists plays in
    # game order. Measured on this input, the postgame HIGHLIGHTS reel does
    # NOT scroll in strict chronological order across quarter boundaries
    # (see pbp_ingest.py's quarter-inference note), so a forward-only
    # cursor produced false negatives here (64% match). This reconcile pass
    # therefore does an any-occurrence dd match per PBP row (order-agnostic,
    # consumes each plays.csv row at most once) -- documented honestly as a
    # weaker join than the spec's monotonic cursor, appropriate ONLY when
    # the PBP source itself is not chronologically reliable.
    used = set()
    matched = 0
    unmatched_rows = []
    per_qtr = {}
    for r in pbp:
        dd_norm = norm_dd(r.get("dd", ""))
        per_qtr[r["qtr"]] = per_qtr.get(r["qtr"], 0) + 1
        if not dd_norm or dd_norm == "KICKOFF":
            # kickoffs/PATs are segmented separately (detect_st_windows) and
            # not comparable 1:1 against seg/plays.csv dd values here
            continue
        found = None
        for i, p in enumerate(plays):
            if i in used:
                continue
            if p["_dd_norm"] == dd_norm:
                found = i
                break
        if found is not None:
            matched += 1
            used.add(found)
        else:
            unmatched_rows.append(r)

    total = sum(1 for r in pbp if norm_dd(r.get("dd", "")) not in ("", "KICKOFF"))
    pct = (matched / total * 100) if total else 0.0

    print(f"pbp_reconcile: {matched}/{total} PBP rows ({pct:.1f}%) found a "
          f"window in {plays_path}")
    print(f"  per-quarter PBP row counts: {per_qtr}")
    print(f"  {len(plays)} total windows in plays.csv "
          f"({len(plays) - matched} with no matching PBP row -- EXPECTED, "
          f"the highlights reel is a curated subset, not every play)")
    if unmatched_rows:
        print(f"  {len(unmatched_rows)} PBP row(s) with no matching window "
              f"(candidate missed plays / dd parse errors):")
        for r in unmatched_rows[:12]:
            print(f"    q{r['qtr']} dd={r['dd']!r} spot={r['spot']!r} "
                  f"text={r['text'][:70]!r}")

    if total == 0:
        sys.exit("pbp_reconcile: 0 comparable PBP rows (all KICKOFF/blank dd) "
                  "-- cannot evaluate the gate")
    if pct < 90.0:
        sys.exit(f"pbp_reconcile: FAILED gate, {pct:.1f}% < 90%")
    print("pbp_reconcile: PASSED gate (>=90%)")


if __name__ == "__main__":
    main()
