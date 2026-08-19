#!/usr/bin/env python3
"""Build a contradiction-recheck manifest: rows whose play_type is logically
impossible given the independent outcome lane.

A run cannot be 'complete', 'incomplete', or a 'sack' — those all imply a dropback.
These get re-examined by vision (never auto-flipped: vision stays authoritative,
the contradiction is only a reason to look again).

Tiered by default: manifests list ONLY ghost.jpg + strip.jpg — run vs pass is
decided from post-snap movement, and the pre-snap/result images are dead weight
on a re-read (the full 5-image resend measured ~2.5x the tokens for no extra
signal). An agent that cannot decide from ghost+strip answers ESCALATE for that
play; rebuild just those with --full.

Usage: build_contradictions.py GAMEDIR [--full N,N,...]
  --full: emit full-image manifests for the listed play numbers (the escalation
          tier), into recheck_c/ as batchF*.txt
"""
import csv
import os
import re
import sys

PASS_ONLY = re.compile(r"\b(complete|incomplete|interception|intercepted|sack)\b", re.I)
ST_WORDS = re.compile(r"\b(punt|kickoff|kick off|field goal|extra point|PAT|touchback)\b", re.I)

gamedir = sys.argv[1]
FULL_PLAYS = set()
if "--full" in sys.argv:
    FULL_PLAYS = {int(x) for x in sys.argv[sys.argv.index("--full") + 1].split(",")}
rows = list(csv.DictReader(open(f"{gamedir}/plays_charted.csv")))

sus = []
for x in rows:
    pt = (x.get("play_type") or "").lower()
    outcome = f"{x.get('result','')} {x.get('key_event','')}"
    if pt == "run" and PASS_ONLY.search(outcome):
        sus.append((x, f"outcome '{outcome.strip()}' implies a dropback — a run cannot be that"))
    elif pt in ("run", "pass") and ST_WORDS.search(x.get("note", "")):
        sus.append((x, "note describes special teams — likely not a scrimmage play"))

if FULL_PLAYS:
    sus = [(x, why) for x, why in sus if int(x["n"]) in FULL_PLAYS]
    missing = FULL_PLAYS - {int(x["n"]) for x, why in sus}
    if missing:
        sys.exit(f"--full: plays {sorted(missing)} are not contradictions")

if not sus:
    print(f"{gamedir}: no contradictions")
    sys.exit()

TIER1_IMGS = ("ghost.jpg", "strip.jpg")
FULL_IMGS = ("presnap_seq.jpg", "preplay.jpg", "presnap.jpg", "ghost.jpg",
             "strip.jpg", "result.jpg")

out = os.path.join(gamedir, "recheck_c")
os.makedirs(out, exist_ok=True)
B, bi = 6, 0
prefix = "batchF" if FULL_PLAYS else "batch"
for c in range(0, len(sus), B):
    bi += 1
    lines = ["CONTRADICTION RE-CHECK.",
             "Each window's play_type is logically incompatible with an independently recorded outcome.",
             "Look again at ghost.jpg/strip.jpg and decide honestly. You MAY keep your call if the",
             "imagery genuinely supports it — say so and set confidence low. Do NOT flip merely because",
             "the outcome disagrees. But a sack/completion/incompletion means the QB dropped back to throw.",
             "If the window is punt/FG/kickoff, use play_type 'non-play' and say special teams in note.", ""]
    if not FULL_PLAYS:
        lines.insert(5, "If ghost+strip genuinely cannot support ANY decision for a play, reply ESCALATE "
                        "for that play instead of guessing — it will be re-run with the full image set.")
    for x, why in sus[c:c + B]:
        n = int(x["n"])
        d = f"film/play{n:03d}"
        wanted = FULL_IMGS if FULL_PLAYS else TIER1_IMGS
        imgs = [f for f in wanted
                if os.path.exists(os.path.join(gamedir, d, f))]
        lines.append(f"PLAY {n:03d}  dd={x['dd']}  poss={x['poss']}  current_call={x['play_type']}")
        lines.append(f"  CONTRADICTION: {why}")
        lines.append(f"  adjudicated_outcome: result={x.get('result','')} yards={x.get('yards','')} key_event={x.get('key_event','')}")
        lines.append(f"  play_images: {d}/: {' '.join(imgs)}")
    open(os.path.join(out, f"{prefix}{bi:02d}.txt"), "w").write("\n".join(lines) + "\n")
tier = "FULL-image escalation" if FULL_PLAYS else "tier-1 (ghost+strip)"
print(f"{gamedir}: {len(sus)} contradictions -> {bi} {tier} manifests in recheck_c/")
