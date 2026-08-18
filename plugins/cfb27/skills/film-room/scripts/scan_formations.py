#!/usr/bin/env python3
"""Film Room: OCR the opponent-formation banner from the play-call screen.

When the opposing offense picks its play first, the user's defensive
play-call screen shows a banner in the mini live-feed window:
    "Gun - Y Off Trips"
    "1 RB | 1 TE | 3 WR   :12"
That text is ground truth for the opponent's formation + personnel.

For each play window in plays.csv, samples the banner region at 1 fps
over the pre-snap phase and keeps the most common successful read.

Output: formations.csv (n, formation, personnel, reads)

Usage: scan_formations.py VIDEO PLAYS_CSV OUT_CSV
"""
import csv
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image, ImageOps
import pytesseract

BANNER = (390, 427, 330, 68)      # x, y, w, h at 1920x1080

PERS_RE = re.compile(r"([0-9ILS])\s*RB.*?([0-9ILS])\s*TE.*?([0-9ILS])\s*WR", re.I)
DIGIT_FIX = {"I": "1", "L": "1", "S": "3"}


def ocr_banner(img):
    x, y, w, h = BANNER
    sx = img.width / 1920.0
    crop = img.crop((int(x*sx), int(y*sx), int((x+w)*sx), int((y+h)*sx)))
    big = crop.resize((crop.width*3, crop.height*3), Image.LANCZOS)
    # Banner background gradient varies by broadcast skin: grayscale+autocontrast
    # can wash out low-contrast skins to blank. Try color first, fall back to the
    # grayscale path (tuned for the OSU-UMD calibration skin) if color finds nothing
    # or no personnel pattern.
    txt = pytesseract.image_to_string(big, config="--psm 6").strip()
    if not PERS_RE.search(txt):
        gray = ImageOps.autocontrast(big.convert("L"))
        gray_txt = pytesseract.image_to_string(gray, config="--psm 6").strip()
        if PERS_RE.search(gray_txt) or len(gray_txt) > len(txt):
            txt = gray_txt
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    if not lines:
        return None, None
    m = PERS_RE.search(txt)
    pers = None
    if m:
        rb, te, wr = (DIGIT_FIX.get(g.upper(), g) for g in m.groups())
        pers = f"{rb}RB {te}TE {wr}WR"
    # formation = first line, minus trailing play-clock junk
    form = re.sub(r"[^A-Za-z0-9 &().-]", "", lines[0]).strip(" -")
    form = re.sub(r"\s+\d+$", "", form)          # trailing ':12' remnants
    if len(form) < 3 or "PICK A PLAY" in form.upper():
        form = None
    return form, pers


def main():
    video, plays_csv, out_csv = sys.argv[1], sys.argv[2], sys.argv[3]
    plays = list(csv.DictReader(open(plays_csv)))
    out = []
    for p in plays:
        t0, t1 = float(p["t_first"]), float(p["t_last"])
        span = max(4, min(t1 - 6 - t0, 30))      # pre-snap phase only
        forms, perss = [], []
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-ss", str(t0), "-t", str(span), "-i", video,
                            "-vf", "fps=1", "-q:v", "5",
                            os.path.join(td, "b%03d.jpg")],
                           capture_output=True)
            for fn in sorted(os.listdir(td)):
                f, pr = ocr_banner(Image.open(os.path.join(td, fn)))
                if f:
                    forms.append(f)
                if pr:
                    perss.append(pr)
        form = max(set(forms), key=forms.count) if forms else ""
        pers = max(set(perss), key=perss.count) if perss else ""
        out.append({"n": p["n"], "formation": form, "personnel": pers,
                    "reads": len(forms)})
        print(f'play {p["n"]}: {form or "-"} | {pers or "-"} ({len(forms)} reads)',
              flush=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["n", "formation", "personnel", "reads"])
        w.writeheader()
        w.writerows(out)
    hits = sum(1 for o in out if o["formation"])
    print(f"banner found on {hits}/{len(out)} plays")


if __name__ == "__main__":
    main()
