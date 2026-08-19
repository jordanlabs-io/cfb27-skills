#!/usr/bin/env python3
"""Chart validation — run BEFORE writing any report (SKILL.md step 9.5).

Checks:
  1. Outcome contradictions: run-labelled rows whose adjudicated outcome
     (complete/incomplete/interception/sack) requires a dropback.
  2. Special-teams language sitting in the run/pass pool.
  3. Game-boundary signals: score going backward + quarter resetting to 1
     (film rolled into a second game).
  4. Enum audit (v3): every charted enum field checked against
     chart_schema.ENUMS after normalisation — off-schema values listed.
  5. presnap_adjust consistency: formation_initial != formation (both real,
     neither a menu) but presnap_adjust=none -> recheck candidate.
  6. Header check: column set/order vs chart_schema.FINAL_COLUMNS (pre-v3
     charts are reported, not failed).
  7. Duplicate adjacent windows: same poss + same dd + overlapping/near
     windows + same result -> likely one play segmented twice (inflates
     event counts; merge by hand or via recheck, keep a note).

Usage: validate_chart.py GAMEDIR [...]
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chart_schema as cs

PASS_ONLY = re.compile(r"\b(complete|incomplete|interception|intercepted|sack)\b", re.I)
ST_WORDS = re.compile(r"\b(punt|kickoff|kick off|field goal|FG|extra point|PAT|touchback)\b", re.I)


def _score_pair(s):
    try:
        a, b = (s or "").split("-")
        return int(a), int(b)
    except ValueError:
        return None


for gamedir in sys.argv[1:]:
    rows = list(csv.DictReader(open(f"{gamedir}/plays_charted.csv")))
    print(f"\n=== {gamedir}  ({len(rows)} windows)")

    # 1+2: outcome contradictions / ST language
    bad_run, st_in_pool = [], []
    for r in rows:
        pt = (r.get("play_type") or "").lower()
        outcome = f"{r.get('result','')} {r.get('key_event','')}"
        note = r.get("note", "")
        if pt == "run" and PASS_ONLY.search(outcome):
            bad_run.append((r["n"], r["dd"], outcome.strip(), note[:60]))
        if pt in ("run", "pass") and ST_WORDS.search(note):
            st_in_pool.append((r["n"], pt, note[:70]))
    print(f"  run-labelled but outcome implies pass: {len(bad_run)}")
    for n, dd, o, nt in bad_run:
        print(f"    p{n} dd={dd} outcome='{o}' note={nt}")
    print(f"  special-teams language inside run/pass pool: {len(st_in_pool)}")
    for n, pt, nt in st_in_pool[:12]:
        print(f"    p{n} [{pt}] {nt}")

    # 3: game boundary
    hits, prev, prev_q = [], None, 0
    for x in rows:
        sc = _score_pair(x.get("score", ""))
        q = (x.get("qtr") or "").strip()
        if sc and prev and (sc[0] < prev[0] or sc[1] < prev[1]):
            hits.append(f"p{x['n']}: score went BACKWARD {prev[0]}-{prev[1]} -> {sc[0]}-{sc[1]}")
        if q == "1" and prev_q >= 3:
            hits.append(f"p{x['n']}: quarter reset to 1 after Q{prev_q}")
        if sc:
            prev = sc
        if q.isdigit():
            prev_q = int(q)
    print(f"  game-boundary signals: {len(hits)}")
    for h in hits[:6]:
        print(f"    {h}")

    # 4: enum audit — check base + v2_ variants of every enum field
    header = list(rows[0].keys()) if rows else []
    viol = {}
    for r in rows:
        for field in cs.ENUMS:
            for col in (field, "v2_" + field):
                if col not in header:
                    continue
                v = r.get(col) or ""
                if v and cs.enum_violations(field, v):
                    viol.setdefault(col, {}).setdefault(v, 0)
                    viol[col][v] += 1
    print(f"  off-schema enum values: {sum(len(v) for v in viol.values())} distinct")
    for col, vals in sorted(viol.items()):
        for v, c in sorted(vals.items(), key=lambda kv: -kv[1]):
            print(f"    {col}: {v!r} x{c}")

    # 5: presnap_adjust consistency
    inconsistent = []
    for r in rows:
        fi = (r.get("formation_initial") or "").strip().lower()
        fm = (r.get("formation") or "").strip().lower()
        adj = (r.get("presnap_adjust") or "").strip().lower()
        if (fi and fm and fi not in ("menu", "unknown", "n/a")
                and fm not in ("unknown", "n/a") and fi != fm
                and adj in ("none", "")):
            inconsistent.append((r["n"], fi, fm))
    print(f"  formation changed but presnap_adjust=none: {len(inconsistent)} (recheck candidates)")
    for n, a, b in inconsistent[:10]:
        print(f"    p{n}: {a} -> {b}")

    # 6: header check
    sv = rows[0].get("schema_version", "") if rows else ""
    if not sv:
        print("  header: pre-v3 chart (no schema_version column) — v3 fields will read n/a")
    else:
        missing = [c for c in cs.FINAL_COLUMNS if c not in header]
        extra = [c for c in header if c not in cs.FINAL_COLUMNS]
        out_of_order = header != cs.ordered_columns(header)
        print(f"  header: schema_version={sv}; missing {len(missing)}; "
              f"extra {len(extra)}; order {'NON-CANONICAL' if out_of_order else 'ok'}")
        for c in missing[:8]:
            print(f"    missing: {c}")
        for c in extra[:8]:
            print(f"    extra: {c}")

    # 7: duplicate adjacent windows
    dups = []
    for a, b in zip(rows, rows[1:]):
        if (a.get("poss") and a.get("poss") == b.get("poss")
                and a.get("dd") and a.get("dd") == b.get("dd")
                and (a.get("play_type") or "") not in ("non-play", "")
                and (b.get("play_type") or "") not in ("non-play", "")
                and (a.get("result") or "") == (b.get("result") or "")):
            try:
                gap = float(b.get("snap_t") or 0) - float(a.get("snap_t") or 0)
            except ValueError:
                gap = None
            if gap is None or 0 <= gap <= 30:
                dups.append((a["n"], b["n"], a["dd"], a.get("result", "")))
    print(f"  duplicate-adjacent-window candidates: {len(dups)}")
    for n1, n2, dd, res in dups[:12]:
        print(f"    p{n1}/p{n2} dd={dd} result={res!r} — likely one play twice; "
              f"merge (void one as non-play with a note) before splits")
