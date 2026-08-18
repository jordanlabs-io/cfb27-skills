#!/usr/bin/env python3
"""Build recheck manifests for windows hit by the 2026-07-31 menu-overlay bugs.

Suspect set:
  (a) EVERY window charted `non-play`  — the rule over-fired on menu panels drawn
      over live football.
  (b) every `pass` call by the offense whose screen we are watching — that coach
      opens the PASS PROTECTION panel pre-snap on runs too, and agents read the
      panel title as the play call.

Usage: build_recheck.py GAMEDIR OWN_POSS   (OWN_POSS = L or R, whose screen it is)
"""
import csv
import os
import sys

gamedir, own = sys.argv[1], sys.argv[2].upper()
rows = list(csv.DictReader(open(f"{gamedir}/plays_charted.csv")))

sus = []
for x in rows:
    pt = (x["play_type"] or "").lower()
    if pt == "non-play":
        sus.append((x, "voided"))
    elif pt == "pass" and x["poss"] == own:
        sus.append((x, "own-offense pass (menu contamination)"))
    elif pt == "unknown":
        sus.append((x, "unknown"))

out = os.path.join(gamedir, "recheck")
os.makedirs(out, exist_ok=True)
B, bi = 6, 0
for c in range(0, len(sus), B):
    bi += 1
    lines = ["RE-CHECK — menu-overlay + menu-title bugs (2026-07-31).",
             "Two rules were wrong before: (1) a menu PANEL drawn over live football is NOT a",
             "non-play; (2) a `PASS PROTECTION` panel is NOT evidence of a pass — this coach opens",
             "it before nearly every call, runs included. Decide run vs pass ONLY from post-snap",
             "player action in ghost.jpg/strip.jpg. Chart each window FRESH.", ""]
    for x, why in sus[c:c + B]:
        n = int(x["n"])
        d = f"film/play{n:03d}"
        imgs = [f for f in ("preplay.jpg", "presnap.jpg", "ghost.jpg", "strip.jpg", "result.jpg")
                if os.path.exists(os.path.join(gamedir, d, f))]
        menus = [f for f in ("menu1.jpg", "menu2.jpg", "menu3.jpg")
                 if os.path.exists(os.path.join(gamedir, d, f))]
        lines.append(f"PLAY {n:03d}  dd={x['dd']}  qtr={x['qtr'] or '?'}  poss={x['poss']}  prior_call={x['play_type']} ({why})")
        lines.append(f"  adjudicated_outcome: result={x.get('result','')} yards={x.get('yards','')} key_event={x.get('key_event','')}")
        lines.append("    ^ independent lane. Use it to judge WHETHER a snap happened, and note that")
        lines.append("      'incomplete'/'complete'/'sack' imply a dropback. Never use it alone to set play_type.")
        lines.append(f"  play_images: {d}/: {' '.join(imgs)}")
        lines.append(f"  menu_images: {' '.join(menus) if menus else 'NONE'}")
    open(os.path.join(out, f"batch{bi:02d}.txt"), "w").write("\n".join(lines) + "\n")
print(f"{gamedir}: {len(sus)} suspect windows -> {bi} manifests")
