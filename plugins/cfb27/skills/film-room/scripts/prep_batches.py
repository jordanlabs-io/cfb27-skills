#!/usr/bin/env python3
"""Build charting batches for the Claude-vision lane (no Gemini key available).

For each play in seg/plays.csv:
  - extract up to 3 menu-candidate frames from the inter-play gap
    (the recorder's play-call screen lives between play windows) -> film/playNNN/menuK.jpg
  - list frames.py composites (presnap/ghost/strip/result) if present
Group plays into batches of 8 by possession side, write batches/batchNN.txt manifests.

Usage: prep_batches.py GAMEDIR TEAM_L TEAM_R [SEAM_T OWNER_A OWNER_B] [--tiles]
  TEAM_L/TEAM_R = scorebug left/right team names (poss column is L/R)
  SEAM_T = concat boundary sec; screen owner = OWNER_A before, OWNER_B after
  (no seam args -> constant owner OWNER_A if given, else TEAM_L)
  --tiles: split each menu band into two 960-wide tiles. The API downsamples
    any image over 1568px on the long edge, so a 1920-wide band loses ~18%
    of its text resolution; two <=1568px tiles keep native resolution at
    ~1.5x the image tokens. Use when tile names / counters come back garbled.
"""
import csv
import os
import subprocess
import sys
import tempfile

ARGS = [a for a in sys.argv[1:] if a != "--tiles"]
TILES = "--tiles" in sys.argv
GAMEDIR, TEAM_L, TEAM_R = ARGS[0], ARGS[1], ARGS[2]
SEAM = float(ARGS[3]) if len(ARGS) > 3 else None
OWNER_A = ARGS[4] if len(ARGS) > 4 else TEAM_L
OWNER_B = ARGS[5] if len(ARGS) > 5 else OWNER_A
VIDEO = os.path.join(GAMEDIR, "video.mp4")
BATCH_SIZE = 8

# >=2 of these in an OCR pass over the band = a play-call/adjustment overlay
# is up (used to keep pre-snap playart_check grabs; field frames don't hit).
PLAYART_MARKERS = ("CALLS", "AVG", "AUDIBLE", "PROTECTION", "COVER",
                   "PERSONNEL", "ADJUSTMENT", "BLITZ", "FORMATION")


def grab(t, out, x0=0, w=1920):
    if os.path.exists(out):
        return
    # full-res lower-half crop: play-call tiles + personnel tabs + counters stay legible
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.1f}", "-i", VIDEO,
                    "-frames:v", "1", "-vf", f"crop={w}:620:{x0}:460", "-q:v", "4", out],
                   check=False)


def grab_menu(t, pdir, stem):
    """Grab the menu band as one 1920-wide image, or two native-res tiles."""
    outs = []
    if TILES:
        for suffix, x0 in (("_L", 0), ("_R", 960)):
            out = os.path.join(pdir, f"{stem}{suffix}.jpg")
            grab(t, out, x0=x0, w=960)
            if os.path.exists(out):
                outs.append(os.path.basename(out))
    else:
        out = os.path.join(pdir, f"{stem}.jpg")
        grab(t, out)
        if os.path.exists(out):
            outs.append(os.path.basename(out))
    return outs


def band_is_menu(t):
    """OCR gate: True when the band at time t shows a menu/adjustment overlay.
    Fails closed (False) when OCR is unavailable — a missing dep must not
    start attaching two extra field crops to every play."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return False
    with tempfile.TemporaryDirectory() as td:
        fp = os.path.join(td, "band.jpg")
        grab(t, fp)
        if not os.path.exists(fp):
            return False
        try:
            txt = pytesseract.image_to_string(Image.open(fp)).upper()
        except Exception:
            return False
    return sum(m in txt for m in PLAYART_MARKERS) >= 2


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
            menus += grab_menu(t, pdir, f"menu{i}")
    # Pre-snap play-art re-checks: a coach re-opening play art between the
    # lineup and the snap reveals the original call AND post-audible art.
    # OCR-gated so field frames don't get grabbed as menu payload.
    if snap:
        for i, off in enumerate((-6.0, -2.5), 1):
            t = snap + off
            if t > gap_b and band_is_menu(t):
                menus += grab_menu(t, pdir, f"playart_check{i}")
    # presnap_seq (labeled 6-cell sequence) supersedes preplay (unlabeled 2x2);
    # older film dirs without it fall back to preplay. Never send both.
    pre = "presnap_seq.jpg" if os.path.exists(os.path.join(pdir, "presnap_seq.jpg")) \
        else "preplay.jpg"
    imgs = [f for f in (pre, "presnap.jpg", "fullframe.jpg", "playart.jpg",
                        "ghost.jpg", "strip.jpg", "result.jpg")
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
