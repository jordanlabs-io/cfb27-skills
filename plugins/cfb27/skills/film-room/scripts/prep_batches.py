#!/usr/bin/env python3
"""Build charting batches for the Claude-vision lane (no Gemini key available).

For each play in seg/plays.csv:
  - extract up to 3 menu-candidate frames from the inter-play gap
    (the recorder's play-call screen lives between play windows) -> film/playNNN/menuK.jpg
  - list frames.py composites (presnap/ghost/strip/result) if present
Group plays into batches of 8 by possession side, write batches/batchNN.txt manifests.

Usage: prep_batches.py GAMEDIR TEAM_L TEAM_R [SEAM_T OWNER_A OWNER_B]
  TEAM_L/TEAM_R = scorebug left/right team names (poss column is L/R)
  SEAM_T = concat boundary sec; screen owner = OWNER_A before, OWNER_B after
  (no seam args -> constant owner OWNER_A if given, else TEAM_L)
"""
import csv
import os
import subprocess
import sys

GAMEDIR, TEAM_L, TEAM_R = sys.argv[1], sys.argv[2], sys.argv[3]
SEAM = float(sys.argv[4]) if len(sys.argv) > 4 else None
OWNER_A = sys.argv[5] if len(sys.argv) > 5 else TEAM_L
OWNER_B = sys.argv[6] if len(sys.argv) > 6 else OWNER_A
VIDEO = os.path.join(GAMEDIR, "video.mp4")
BATCH_SIZE = 8


def grab(t, out):
    if os.path.exists(out):
        return
    # full-res lower-half crop: play-call tiles + personnel tabs + counters stay legible
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.1f}", "-i", VIDEO,
                    "-frames:v", "1", "-vf", "crop=1920:620:0:460", "-q:v", "4", out],
                   check=False)


plays = list(csv.DictReader(open(os.path.join(GAMEDIR, "seg/plays.csv"))))
prev_end = 0.0
manifest_rows = []
for p in plays:
    n = int(p["n"])
    t0, t1 = float(p["t_first"]), float(p["t_last"])
    pdir = os.path.join(GAMEDIR, f"film/play{n:03d}")
    os.makedirs(pdir, exist_ok=True)
    # snap estimate from frames.py meta when present
    snap = None
    meta = os.path.join(pdir, "meta.txt")
    if os.path.exists(meta):
        for tok in open(meta).read().split():
            if tok.startswith("snap_est="):
                try:
                    snap = float(tok.split("=", 1)[1])
                except ValueError:
                    pass
    gap_a, gap_b = prev_end, (snap - 2 if snap else t0)
    if gap_b - gap_a > 60:
        gap_a = gap_b - 35
    menus = []
    if gap_b - gap_a >= 4:
        for i, frac in enumerate((0.3, 0.6, 0.85), 1):
            t = gap_a + (gap_b - gap_a) * frac
            out = os.path.join(pdir, f"menu{i}.jpg")
            grab(t, out)
            if os.path.exists(out):
                menus.append(f"menu{i}.jpg")
    imgs = [f for f in ("preplay.jpg", "presnap.jpg", "ghost.jpg", "strip.jpg", "result.jpg")
            if os.path.exists(os.path.join(pdir, f))]
    manifest_rows.append((n, p, imgs, menus))
    prev_end = t1

bdir = os.path.join(GAMEDIR, "batches")
os.makedirs(bdir, exist_ok=True)
# group by possession so each batch is one offense
by_side = {"L": [], "R": []}
for row in manifest_rows:
    poss = (row[1]["poss"] or "L").strip()
    if poss == TEAM_L:
        poss = "L"
    elif poss == TEAM_R:
        poss = "R"
    by_side.setdefault(poss, []).append(row)

bi = 0
for side_key, team in (("L", TEAM_L), ("R", TEAM_R)):
    rows = by_side.get(side_key, [])
    for c in range(0, len(rows), BATCH_SIZE):
        bi += 1
        chunk = rows[c:c + BATCH_SIZE]
        lines = [f"OFFENSE THIS BATCH: {team} offense (scorebug side {side_key})", ""]
        for n, p, imgs, menus in chunk:
            t0 = float(p["t_first"])
            owner = OWNER_A if (SEAM is None or t0 < SEAM) else OWNER_B
            lines.append(f"PLAY {n:03d}  dd={p['dd']}  qtr={p['qtr'] or '?'}  clock={p['clock'] or '?'}  menu_screen_owner={owner}")
            lines.append(f"  play_images: film/play{n:03d}/: {' '.join(imgs) if imgs else 'NONE'}")
            lines.append(f"  menu_images: {' '.join(menus) if menus else 'NONE'}")
        open(os.path.join(bdir, f"batch{bi:02d}.txt"), "w").write("\n".join(lines) + "\n")
print(f"{bi} batches written to {bdir} ({len(manifest_rows)} plays)")
