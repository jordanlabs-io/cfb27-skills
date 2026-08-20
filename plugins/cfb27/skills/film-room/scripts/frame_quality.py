#!/usr/bin/env python3
"""Deterministic frame-quality gate for Lane C menu frames.

Usage:
    frame_quality.py FRAMES_DIR OUT.json [--min 200]

Run it BEFORE tier-1 classification. Frames below threshold are transition or
motion-blur artifacts and must not be handed to a transcription agent: a
vision model does not refuse an illegible frame, it transcribes a coin flip
(measured 52% correct against the same screen captured sharp).

The tier-1 classifier's model-judged `readable` flag is not trustworthy: it
marked f_0626 -- a motion-blurred menu transition whose numbers are illegible
-- readable, with visible_rows 9. Legibility cannot be judged by the same
model that is about to read the frame.

Measured on 318 real menu frames: median 816, sharp frames >1600, blurred
transitions ~100. About 10% of distinct screen runs have NO frame above
threshold -- there is nothing to transcribe on them at any price.

Variance of the Laplacian over the table region is the cheap classical
alternative. Menu chrome (logos, the coach portrait, the background art) stays
sharp through a transition, so the whole-frame score is misleading; the score
is taken over the central band where the data table lives.
"""
import sys, json, pathlib
import numpy as np
from PIL import Image

# central band: skips the top header/HUD and the bottom button bar, and the
# right-hand detail card, which is sharp even when the table is smeared.
BAND = (0.04, 0.22, 0.66, 0.88)  # x0, y0, x1, y1 as fractions

K = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)

def laplacian_var(a):
    from numpy.lib.stride_tricks import sliding_window_view
    w = sliding_window_view(a, (3, 3))
    return float((w * K).sum(axis=(-2, -1)).var())

def score(path):
    im = Image.open(path).convert("L")
    w, h = im.size
    x0, y0, x1, y1 = BAND
    im = im.crop((int(w*x0), int(h*y0), int(w*x1), int(h*y1)))
    # normalise for capture resolution -- the dumps mix 960x540 and 1100x619
    im = im.resize((640, int(640 * im.size[1] / im.size[0])), Image.BILINEAR)
    return laplacian_var(np.asarray(im, dtype=np.float64))

# Per-screen-type floors. Depth charts render at lower contrast than stat
# tables (median 436 vs 1129), so one global threshold over-rejects them.
MIN_DEFAULT = 200
MIN_BY_TYPE = {"depth_chart": 170, "team_stats": 260, "scores_schedule": 200}

if __name__ == "__main__":
    src = pathlib.Path(sys.argv[1])
    dest = sys.argv[2]
    floor = MIN_DEFAULT
    if "--min" in sys.argv:
        floor = float(sys.argv[sys.argv.index("--min") + 1])
    out = {}
    for p in sorted(src.rglob("*.jpg")):
        out[p.name] = round(score(p), 2)
    reject = sorted(k for k, v in out.items() if v < floor)
    json.dump({"threshold": floor, "scores": out, "reject": reject},
              open(dest, "w"), indent=1)
    v = sorted(out.values())
    print(f"{len(v)} frames  min={v[0]}  median={v[len(v)//2]}  max={v[-1]}")
    print(f"{len(reject)} below {floor} -> excluded from transcription")
    for k in reject[:20]:
        print(f"   {k}  {out[k]}")
    if len(reject) > 20:
        print(f"   ... and {len(reject)-20} more")
