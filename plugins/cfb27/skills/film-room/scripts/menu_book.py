#!/usr/bin/env python3
"""Call-sheet book: aggregate menu-tile usage counters from chart_v2_flash.jsonl.

Caller-screen menus show per-play season usage ("N CALLS | X.X AVG YDS") and
starred favorites — verbatim call-sheet truth. This collects every tile the
charting agents transcribed into a per-owner table: the coach's actual playbook
with usage, sorted by calls. Counters are season-cumulative, so the delta
between two films of the same coach = calls made in games we never saw.

Usage: menu_book.py GAMEDIR TEAM_L TEAM_R [SEAM_T OWNER_A OWNER_B]
  (owner args as in prep_batches.py; no seam -> constant OWNER_A, else TEAM_L)
Outputs GAMEDIR/menu_book.md + menu_book.csv.
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict

GAMEDIR, TEAM_L, TEAM_R = sys.argv[1], sys.argv[2], sys.argv[3]
SEAM = float(sys.argv[4]) if len(sys.argv) > 4 else None
OWNER_A = sys.argv[5] if len(sys.argv) > 5 else TEAM_L
OWNER_B = sys.argv[6] if len(sys.argv) > 6 else OWNER_A

t_first = {}
with open(os.path.join(GAMEDIR, "seg/plays.csv")) as f:
    for r in csv.DictReader(f):
        try:
            t_first[int(r["n"])] = float(r["t_first"])
        except (ValueError, KeyError):
            pass

CALLS_RE = re.compile(r"^(\d+)\s*CALLS?$", re.I)
AVG_RE = re.compile(r"^([\d.]+)\s*AVG", re.I)
TAGS = {"MAN", "ZONE", "BLITZ", "MATCH", "PASS", "RUN", "RPO", "PERSONNEL",
        "SCREEN", "PA", "OPTION", "HB DIRECT", "SPECIAL"}


def parse_tile(s):
    """Anchor on the 'N CALLS' segment from the right — tiles vary between
    'NAME | TAG | N CALLS | X.X AVG' and 'FORMATION | PLAY | TAG | N CALLS |
    X.X AVG'. Returns (name, tag, calls, avg) or None."""
    parts = [p.strip() for p in s.split("|") if p.strip()]
    ci = next((i for i, p in enumerate(parts) if CALLS_RE.match(p)), None)
    if ci is None or ci == 0:
        return None
    calls = int(CALLS_RE.match(parts[ci]).group(1))
    avg = ""
    if ci + 1 < len(parts):
        m = AVG_RE.match(parts[ci + 1])
        avg = m.group(1) if m else ""
    pre = parts[:ci]
    tag = ""
    if len(pre) > 1 and pre[-1].upper() in TAGS:
        tag = pre[-1].upper()
        pre = pre[:-1]
    return " ".join(pre), tag, calls, avg

book = defaultdict(lambda: {"max_calls": -1, "avg": "", "tag": "",
                            "sides": set(), "plays": [], "starred": False})
unparsed = []
for line in open(os.path.join(GAMEDIR, "chart_v2_flash.jsonl")):
    rec = json.loads(line)
    n, read = int(rec["n"]), rec.get("read", {})
    tiles = read.get("menu_tiles") or []
    if not isinstance(tiles, list):
        continue
    owner = OWNER_A if (SEAM is None or t_first.get(n, 0.0) < SEAM) else OWNER_B
    side = (read.get("menu_side") or "unknown").lower()
    for tile in tiles:
        s = str(tile).strip()
        star = "★" in s or "star" in s.lower() or "favorite" in s.lower()
        parsed = parse_tile(s.replace("★", "").strip())
        if parsed is None:
            unparsed.append((n, s))
            continue
        name, tag, calls, avg = parsed
        e = book[(owner, name.upper())]
        if calls >= e["max_calls"]:
            e["max_calls"] = calls
            e["avg"] = avg
        e["tag"] = e["tag"] or tag
        e["sides"].add(side)
        e["plays"].append(n)
        e["starred"] = e["starred"] or star

mdp = os.path.join(GAMEDIR, "menu_book.md")
csvp = os.path.join(GAMEDIR, "menu_book.csv")
with open(csvp, "w", newline="") as cf, open(mdp, "w") as mf:
    w = csv.writer(cf)
    w.writerow(["owner", "play", "tag", "max_calls", "avg_yds_at_max",
                "starred", "sightings", "plays_seen"])
    mf.write(f"# Call-sheet book — {os.path.basename(os.path.abspath(GAMEDIR))}\n")
    for owner in sorted({k[0] for k in book}):
        mf.write(f"\n## {owner} (their screen's menus)\n\n"
                 "| play | tag | calls | avg yds | ★ | seen |\n"
                 "| --- | --- | --- | --- | --- | --- |\n")
        rows = sorted(((k[1], e) for k, e in book.items() if k[0] == owner),
                      key=lambda x: -x[1]["max_calls"])
        for name, e in rows:
            seen = sorted(set(e["plays"]))
            w.writerow([owner, name, e["tag"], e["max_calls"], e["avg"],
                        "yes" if e["starred"] else "", len(seen),
                        " ".join(f"p{p}" for p in seen[:12])])
            mf.write(f"| {name} | {e['tag']} | {e['max_calls']} | {e['avg']} "
                     f"| {'★' if e['starred'] else ''} | {len(seen)}x |\n")
    if unparsed:
        mf.write(f"\n{len(unparsed)} tile strings didn't parse "
                 "(raw text remains in chart_v2_flash.jsonl)\n")
print(f"menu_book: {len(book)} plays booked, {len(unparsed)} unparsed "
      f"-> {mdp} + {csvp}")
