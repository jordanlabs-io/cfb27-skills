#!/usr/bin/env python3
"""Build labeled scorebug crop-sheets from segment.py hud_frames for Claude-vision
timeline rescue (tesseract-illegible soft film).

Usage: sheet_gen.py GAMEDIR T_START T_END OUTDIR
Sheets: 24 rows x (scorebug band 1180x95 -> 885x71) + 60px left label margin.
"""
import os
import sys

from PIL import Image, ImageDraw

GAMEDIR, T0, T1, OUTDIR = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
FDIR = os.path.join(GAMEDIR, "seg/hud_frames")
os.makedirs(OUTDIR, exist_ok=True)
CROP = (370, 935, 1560, 1035)   # x0,y0,x1,y1 scorebug band incl dd capsule
ROWS = 24
SC = 0.75
W = int((CROP[2] - CROP[0]) * SC)
H = int((CROP[3] - CROP[1]) * SC)
MARGIN = 70

frames = []
for t in range(T0, T1 + 1):
    p = os.path.join(FDIR, f"f{t+1:06d}.jpg")
    if os.path.exists(p):
        frames.append((t, p))

sheets = 0
for s in range(0, len(frames), ROWS):
    chunk = frames[s:s + ROWS]
    sheet = Image.new("RGB", (MARGIN + W, H * len(chunk)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, (t, p) in enumerate(chunk):
        im = Image.open(p).crop(CROP).resize((W, H), Image.LANCZOS)
        sheet.paste(im, (MARGIN, i * H))
        d.text((4, i * H + H // 2 - 8), f"t{t}", fill=(255, 255, 80))
        d.line([(0, i * H), (MARGIN + W, i * H)], fill=(90, 90, 90))
    sheets += 1
    sheet.save(os.path.join(OUTDIR, f"sheet{sheets:03d}.jpg"), quality=88)
print(f"{sheets} sheets ({len(frames)} frames) -> {OUTDIR}")
