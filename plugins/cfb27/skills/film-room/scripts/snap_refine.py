#!/usr/bin/env python3
"""Sub-second snap refinement, shared by snap_times.py and frames.py.

PLAN-snap-anchoring.md amendments A2-A4 (2026-09-09), calibrated against a
20-play hand-verified truth set on 2028-rutgers-vs-northwestern
(scratchpad/snap/truth.csv in that session -- see
references/calibration-history.md for the measured numbers).

Precedence, all operating inside a bracket around the coarse play-clock
freeze `t_freeze`:

  A2 preplay-chip : the PRE-PLAY/SUBS HUD chip (bottom strip, full width,
                     ~12% of frame height -- same box as frames.py's
                     preplay_box) goes visually uniform (low stddev) and
                     STAYS uniform for >=0.5s. This is the primary estimator:
                     14/20 hand-verified plays resolved cleanly on it.
  A3 motion        : sustained non-returning motion in the field crop, when
                     the chip signal is unusable (camera pan/zoom moved the
                     chip off its fixed position, or a wide/menu-adjacent
                     camera angle). Used as a full visual fallback (this repo
                     does NOT implement a template matcher / cv2 -- PIL +
                     stdlib only, per pre-flight amendment A1).
  A4 playclock     : neither resolves -> keep the play-clock freeze itself,
                     flagged unreliable=True.

NOTE ON A3: unlike the plan text's exact machinery ("reuse motion_onsets at
a finer step"), this repo has no cheap frame-diff-over-the-whole-window path
available to snap_times.py (no motion_profile access without re-running
ffmpeg per play at MOTION_FPS). Given the truth-set evidence -- every play
that failed the chip test failed because the CHIP was unreadable on that
camera angle, not because the chip-clear signal itself was ambiguous -- A3
here is implemented as a full-frame content-change detector over the same
bracket (grayscale mean-abs-diff between consecutive 10fps frames, full
frame minus the scorebug strip), which is cheap, stdlib+PIL+numpy only, and
matches the "sustained non-returning motion" spec functionally.

BRACKET WIDTH: PLAN-snap-anchoring.md A2 specifies [t_freeze-0.5, t_freeze+1.5].
Calibration against the 20-play truth set showed several true snaps sit past
+1.5s (the playclock can freeze up to ~2s before the chip actually clears),
so this implementation widens the bracket to [t_freeze-0.5, t_freeze+2.5].
Even with the wider bracket the measured accuracy did NOT reach the ±0.3s/
>=90% goal -- see references/calibration-history.md for the honest numbers
(median ~0.4s, P90 ~1.5-1.6s, ~40% of hand-verified plays within 0.3s).
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

CHIP_THRESH = 10.0      # stddev below this = chip visually uniform (cleared)
CHIP_SUSTAIN = 5         # consecutive 10fps samples (0.5s) required
MOTION_MIN_RUN = 8        # consecutive 10fps samples (0.8s) of non-returning
                           # motion required for the A3 fallback
FPS = 10


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{r.stderr[-300:]}")


def _extract_frames(video, t0, t1, td):
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
          "-ss", f"{max(t0, 0):.2f}", "-t", f"{max(t1 - t0, 0.1):.2f}",
          "-i", video, "-vf", f"fps={FPS}", "-q:v", "4",
          os.path.join(td, "r_%03d.jpg")])
    files = sorted(f for f in os.listdir(td) if f.startswith("r_"))
    return [(t0 + i / FPS, os.path.join(td, f)) for i, f in enumerate(files)]


def _chip_std_series(frames, hbox):
    x, y, w, h = hbox[0], hbox[1], hbox[2], hbox[3]
    out = []
    for t, fp in frames:
        im = np.asarray(Image.open(fp).convert("L").crop((x, y, x + w, y + h)),
                         dtype=np.float32)
        out.append((t, float(im.std())))
    return out


def _chip_clear_time(series):
    """First timestamp where stddev < CHIP_THRESH and stays below it for
    CHIP_SUSTAIN consecutive samples (allowing a shorter tail run at the end
    of the bracket, same relaxation used to build the hand-verified truth
    set). Returns the MIDPOINT between the last high sample and the first
    low sample of that sustained run (matches how the truth set was
    labelled), or None."""
    n = len(series)
    for i in range(n):
        window = min(CHIP_SUSTAIN, n - i)
        if window < 3:
            break
        if all(series[i + k][1] < CHIP_THRESH for k in range(window)):
            clear_t = series[i][0]
            prev_t = series[i - 1][0] if i > 0 else clear_t
            return round((clear_t + prev_t) / 2, 2)
    return None


def _motion_onset_time(video, t0, t1, td):
    """A3 fallback: full-frame (minus bottom scorebug strip) mean-abs-diff
    between consecutive 10fps frames. Onset = first sample where the diff
    exceeds 2x the bracket's own baseline and never returns below it for
    MOTION_MIN_RUN consecutive samples (no first-crossing, no filtering out
    the tail -- unlike frames.py's motion_onsets, which this deliberately
    does not reuse per A3)."""
    frames = _extract_frames(video, t0, t1, td)
    if len(frames) < MOTION_MIN_RUN + 2:
        return None
    diffs = []
    prev = None
    for t, fp in frames:
        im = np.asarray(Image.open(fp).convert("L"), dtype=np.float32)
        h = im.shape[0]
        im = im[: int(h * 0.85), :]   # drop bottom scorebug strip
        if prev is not None:
            diffs.append((t, float(np.abs(im - prev).mean())))
        prev = im
    if len(diffs) < MOTION_MIN_RUN:
        return None
    vals = [v for _, v in diffs]
    base = sorted(vals)[len(vals) // 5]
    thresh = max(base * 2.0, base + 1.0)
    run_start = None
    for i, (t, v) in enumerate(diffs):
        if v >= thresh:
            if run_start is None:
                run_start = i
            if i - run_start + 1 >= MOTION_MIN_RUN:
                onset_t = diffs[run_start][0]
                prev_t = diffs[run_start - 1][0] if run_start > 0 else onset_t
                return round((onset_t + prev_t) / 2, 2)
        else:
            run_start = None
    return None


def refine_snap(video, hbox, t_freeze, lo=-0.5, hi=2.5):
    """A2/A3/A4 precedence over bracket [t_freeze+lo, t_freeze+hi].

    Returns (snap_t, snap_src, unreliable):
      snap_src in {"preplay-chip", "motion-sustained", "playclock-bracket"}
      unreliable=True only for the playclock-bracket fallback (A4).
    """
    t0, t1 = t_freeze + lo, t_freeze + hi
    with tempfile.TemporaryDirectory() as td:
        try:
            frames = _extract_frames(video, t0, t1, td)
        except RuntimeError:
            return t_freeze, "playclock-bracket", True
        if len(frames) < 5:
            return t_freeze, "playclock-bracket", True

        series = _chip_std_series(frames, hbox)
        snap = _chip_clear_time(series)
        if snap is not None:
            return snap, "preplay-chip", False

        snap = _motion_onset_time(video, t0, t1, td)
        if snap is not None:
            return snap, "motion-sustained", False

    return t_freeze, "playclock-bracket", True


if __name__ == "__main__":
    # Manual smoke test: snap_refine.py VIDEO T_FREEZE [LO] [HI]
    video = sys.argv[1]
    t_freeze = float(sys.argv[2])
    lo = float(sys.argv[3]) if len(sys.argv) > 3 else -0.5
    hi = float(sys.argv[4]) if len(sys.argv) > 4 else 1.5
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import segment as seg
    vw, vh, _ = seg.video_info(video)
    hbox = (0, int(vh * 0.88), vw, vh - int(vh * 0.88))
    print(refine_snap(video, hbox, t_freeze, lo, hi))
