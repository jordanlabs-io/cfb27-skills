#!/usr/bin/env python3
"""Series-level intelligence (the Christian Sam logging method — see
references/presnap-tells.md §series-logging): rep-count formation->play pairs,
per-series defensive sequencing, first-drive probes.

Reads plays_charted.csv, groups run/pass windows into series (consecutive
same-possession runs), and writes GAMEDIR/series_book.csv:
  series,poss,n_first,n_last,snaps,formations,off_sequence,def_sequence

Prints the analyst digest:
  - formation -> play-family rep counts per offense, flagging 100% pairings
    at n>=2 ("you can do it once, but you can't do it twice")
  - motion -> run/pass split (the motion==pass tell, when it holds)
  - per-series defensive sequencing (man/zone + coverage per snap, in order)
    so sky-then-match style shifts are visible
  - first drive vs rest of game, per team (opening-script probes)

Tendencies on <5 snaps are flashes, never percentages (extraction-framework
claims ledger). Pre-v3 charts work; v3-only columns degrade to n/a.

Usage: series_book.py GAMEDIR TEAM_L TEAM_R
"""
import csv
import os
import sys
from collections import Counter, defaultdict

GAMEDIR, TEAM_L, TEAM_R = sys.argv[1], sys.argv[2], sys.argv[3]
rows = list(csv.DictReader(open(os.path.join(GAMEDIR, "plays_charted.csv"))))
rows.sort(key=lambda r: int(r["n"]))


def real(r):
    return (r.get("play_type") or "") in ("run", "pass")


def fam(r):
    """Play family: play_style when the chart has it (v3), else play_type."""
    return r.get("play_style") or r.get("play_type") or "?"


def form_short(r):
    return (r.get("formation") or "unknown").strip() or "unknown"


def cov_label(r):
    cov = (r.get("def_coverage") or "").strip()
    if cov and cov != "unknown":
        return cov
    mz = (r.get("man_zone_verdict") or "").strip()
    return f"~{mz}" if mz and mz != "unknown" else "?"


# ---- group into series: consecutive run of same non-blank poss over real plays
series = []          # list of dicts
cur = None
for r in rows:
    if not real(r):
        continue
    poss = r.get("poss") or ""
    if cur is None or poss != cur["poss"] or not poss:
        cur = {"poss": poss, "plays": []}
        series.append(cur)
    cur["plays"].append(r)
series = [s for s in series if s["plays"]]

out_path = os.path.join(GAMEDIR, "series_book.csv")
with open(out_path, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["series", "poss", "n_first", "n_last", "snaps",
                "formations", "off_sequence", "def_sequence"])
    for i, s in enumerate(series, 1):
        ps = s["plays"]
        w.writerow([
            i, s["poss"], ps[0]["n"], ps[-1]["n"], len(ps),
            "; ".join(sorted({form_short(p) for p in ps})),
            " > ".join(f"{form_short(p)}:{fam(p)}" for p in ps),
            " > ".join(cov_label(p) for p in ps),
        ])
print(f"{len(series)} series -> {out_path}")

for side, team in (("L", TEAM_L), ("R", TEAM_R)):
    poss_values = {side, team}
    own = [s for s in series if s["poss"] in poss_values]
    snaps = [p for s in own for p in s["plays"]]
    if not snaps:
        continue
    print(f"\n{'='*16} {team} — {len(own)} series, {len(snaps)} snaps {'='*16}")

    # formation -> family rep counts; 100% pairings flagged at n>=2
    pair = Counter((form_short(p), fam(p)) for p in snaps)
    by_form = defaultdict(Counter)
    for (f, t), c in pair.items():
        by_form[f][t] += c
    print("  formation -> play family:")
    for f, cnt in sorted(by_form.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(cnt.values())
        parts = ", ".join(f"{t} {c}" for t, c in cnt.most_common())
        lock = ""
        if len(cnt) == 1 and total >= 2:
            lock = "  << 100% pairing (scoutable)" + \
                   ("" if total >= 5 else " [flash, n<5]")
        print(f"    {f}: {parts}  (n={total}){lock}")

    # motion tell
    mo = Counter(((p.get("motion") or "?"), (p.get("play_type") or "?")) for p in snaps)
    m_run, m_pass = mo[("yes", "run")], mo[("yes", "pass")]
    if m_run + m_pass:
        note = "  << motion==pass holds" if m_run == 0 and m_pass >= 2 else ""
        print(f"  motion snaps: run {m_run} / pass {m_pass}{note}")

    # first drive vs rest (opening-script probes)
    first, rest = own[0]["plays"], [p for s in own[1:] for p in s["plays"]]
    f_seq = " > ".join(f"{form_short(p)}:{fam(p)}" for p in first)
    print(f"  first drive script ({len(first)} snaps): {f_seq}")
    if rest:
        fr = Counter(fam(p) for p in first)
        rr = Counter(fam(p) for p in rest)
        print(f"  family mix first-drive vs rest: {dict(fr)} vs {dict(rr)}")

    # defensive sequencing they FACED (i.e. the other team's defense)
    dteam = TEAM_R if side == "L" else TEAM_L
    print(f"  {dteam} defense, series-by-series:")
    for i, s in enumerate(own, 1):
        seq = " > ".join(cov_label(p) for p in s["plays"])
        print(f"    S{i} ({len(s['plays'])}): {seq}")
    # coverage-mix shift across game halves of this team's series
    half = max(1, len(own) // 2)
    early = Counter(cov_label(p) for s in own[:half] for p in s["plays"])
    late = Counter(cov_label(p) for s in own[half:] for p in s["plays"])
    if early and late:
        print(f"  coverage mix early-series vs late-series: "
              f"{dict(early.most_common(4))} vs {dict(late.most_common(4))}")
