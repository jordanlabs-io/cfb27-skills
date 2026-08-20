#!/usr/bin/env python3
"""Count recruit star ratings with classical CV instead of a vision model.

F14 measured Sonnet 5 at 3 of 6 star ratings wrong, every error an over-count
by one, and prompt p3 made it worse (4 of 6). The star column is a fixed-pitch
row of five glyphs where filled ones are solid and unfilled ones are hollow
outlines -- which makes it a measurement problem, not a perception problem.

Method: the star strip sits at a fixed x range and a fixed 58px row pitch in
this layout. Split it into five equal glyph cells and sum the ink in each. A
filled star is solid and an unfilled one is a hollow outline of the same size,
so the outline still carries ink -- roughly 45% of a filled glyph's -- which is
why thresholding on horizontal *extent* over-counts by exactly one and
reproduces the model's bug. Ink per cell separates them cleanly instead.

The selected row is rendered dark-on-light rather than light-on-dark, so
polarity is decided per row from its own background.
"""
import sys, json, pathlib
import numpy as np
from PIL import Image

# Template geometry for the Recruiting Board left prospect list, measured at
# 1100x618. A real pipeline stores one of these per layout variant in
# ref.screen_types and scales it by capture resolution.
GEOM = {
    "x0": 78, "x1": 205,      # search window covering all five glyphs
    "y0": 209, "pitch": 58, "h": 9, "rows": 6,
    "star_pitch": 16.0,
}

def count_row(a, y, g):
    strip = a[y:y + g["h"], g["x0"]:g["x1"]]
    bg = np.median(strip)
    ink = strip.mean(axis=0)
    ink = (bg - ink) if bg > 128 else (ink - bg)   # polarity per row
    ink = np.clip(ink, 0, None)
    on = np.where(ink > ink.max() * 0.15)[0]
    if len(on) == 0:
        return 0, []
    left = on.min()
    cells = []
    for i in range(5):
        a0 = left + round(i * g["star_pitch"])
        cells.append(float(ink[a0:a0 + round(g["star_pitch"])].sum()))
    peak = max(cells)
    # a hollow outline lands near half a filled glyph; 0.7 sits in the gap
    return sum(1 for c in cells if c > peak * 0.7), [round(c) for c in cells]

def main(path, scale_from=1100):
    im = Image.open(path).convert("L")
    if im.width != scale_from:                 # captures come at 960 and 1100
        im = im.resize((scale_from, round(im.height * scale_from / im.width)),
                       Image.LANCZOS)
    a = np.asarray(im, dtype=float)
    g = GEOM
    out = []
    for i in range(g["rows"]):
        n, cells = count_row(a, g["y0"] + i * g["pitch"], g)
        out.append({"row": i + 1, "stars": n, "cell_ink": cells})
    return out

if __name__ == "__main__":
    for r in main(sys.argv[1]):
        print(f"  row {r['row']}  stars={r['stars']}  ink per glyph {r['cell_ink']}")
