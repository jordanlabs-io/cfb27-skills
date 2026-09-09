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
(The A12 numbers once quoted here -- median ~0.4s, P90 ~1.5s, ~40% within
0.3s -- were measured against the truth_v2 reference that A14 showed to be
wrong by up to 2.3s and are VOID. Against truth_v3 the A2/A3/A4 precedence
alone scores median 0.200s / P90 0.850s / 14/20 within 0.3s, and with the A15
tick constraint 0.150s / 0.450s / 16/20.)

PLAYCLOCK TICK (A15, 2026-09-09): the play clock decrements once a second and
FREEZES at the snap. `playclock_tick_time()` / `refine_snap_tick()` below are
the FIRST attempt at exploiting that (hash/diff spike detection, no OCR); they
scored worse than A2/A3 and remain unused, kept only for reference. The second
attempt (OCR + >=3-frame persistence, `t_tick` = last confirmed decrement,
bracket [t_tick, t_tick+1.05]) also appeared to fail -- but that verdict was
measured against a truth set that was itself wrong by up to 2.3s. See
references/calibration-history.md A14.

What IS wired in is `playclock_last_tick()`, used by `refine_snap()` as a
REJECTION CONSTRAINT on the A2/A3 answer rather than as an estimator: 16/20
within +/-0.3s (median 0.150s, P90 0.450s) vs 14/20 (0.200s / 0.850s) for
A2/A3 alone, on the truth_v3 20-play set in references/calibration/.

BRACKET WIDTH note above still applies to the A2/A3 search window.
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
import pytesseract
from PIL import Image, ImageOps

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


TICK_LO, TICK_HI = -1.0, 1.5    # search window for the last playclock tick
TICK_RUN_GAP = 1                # merge diff-spikes <=1 sample apart into one tick


def playclock_tick_time(video, pbox, t_freeze, lo=TICK_LO, hi=TICK_HI):
    """Experimental (see module docstring): last mean-abs-diff spike run in
    the playclock digit box over [t_freeze+lo, t_freeze+hi], taken as the
    last tick before the clock freezes. Returns None if no spike found."""
    t0, t1 = t_freeze + lo, t_freeze + hi
    with tempfile.TemporaryDirectory() as td:
        try:
            frames = _extract_frames(video, t0, t1, td)
        except RuntimeError:
            return None
        x, y, w, h = pbox
        prev, diffs = None, []
        for t, fp in frames:
            arr = np.asarray(Image.open(fp).convert("L").crop((x, y, x + w, y + h)),
                              dtype=np.float32)
            if prev is not None:
                diffs.append((t, float(np.abs(arr - prev).mean())))
            prev = arr
        if not diffs:
            return None
        vals = [v for _, v in diffs]
        base = sorted(vals)[len(vals) // 4]
        thresh = max(base * 3.0, base + 4.0)
        spikes = [i for i, (t, v) in enumerate(diffs) if v >= thresh]
        if not spikes:
            return None
        runs, cur = [], [spikes[0]]
        for i in spikes[1:]:
            if i - cur[-1] <= TICK_RUN_GAP:
                cur.append(i)
            else:
                runs.append(cur)
                cur = [i]
        runs.append(cur)
        start_i = runs[-1][0]
        tick_t = diffs[start_i][0]
        prev_t = diffs[start_i - 1][0] if start_i > 0 else tick_t
        return round((tick_t + prev_t) / 2, 2)


def refine_snap_tick(video, pbox, t_freeze):
    """Experimental A1 tier (see module docstring): playclock-tick + motion,
    NOT called by refine_snap(). Returns (snap_t, snap_src, unreliable) with
    snap_src in {"playclock-tick+motion", "playclock-tick"}."""
    t_tick = playclock_tick_time(video, pbox, t_freeze)
    if t_tick is None:
        return t_freeze, "playclock-bracket", True
    onset = _bracket_motion_onset(video, t_tick, t_tick + 1.0, min_run=3)
    if onset is not None:
        return onset, "playclock-tick+motion", False
    return round(t_tick + 0.5, 2), "playclock-tick", True


def _bracket_motion_onset(video, t0, t1, min_run=3):
    """Motion search sized for a short (~1.0s) bracket, unlike
    _motion_onset_time's MOTION_MIN_RUN=8 which is tuned for the wider A3
    fallback window and rarely fires in a 1.0s span."""
    with tempfile.TemporaryDirectory() as td:
        try:
            frames = _extract_frames(video, t0, t1, td)
        except RuntimeError:
            return None
        if len(frames) < min_run + 2:
            return None
        prev, diffs = None, []
        for t, fp in frames:
            im = np.asarray(Image.open(fp).convert("L"), dtype=np.float32)
            h = im.shape[0]
            im = im[: int(h * 0.85), :]
            if prev is not None:
                diffs.append((t, float(np.abs(im - prev).mean())))
            prev = im
        if len(diffs) < min_run:
            return None
        vals = [v for _, v in diffs]
        base = sorted(vals)[len(vals) // 5]
        thresh = max(base * 2.0, base + 1.0)
        run_start = None
        for i, (t, v) in enumerate(diffs):
            if v >= thresh:
                if run_start is None:
                    run_start = i
                if i - run_start + 1 >= min_run:
                    onset_t = diffs[run_start][0]
                    prev_t = diffs[run_start - 1][0] if run_start > 0 else onset_t
                    return round((onset_t + prev_t) / 2, 2)
            else:
                run_start = None
        return None



# ---------------------------------------------------------------------------
# A15 (2026-09-09): OCR'd play-clock tick used as a REJECTION CONSTRAINT.
#
# The CFB27 play clock decrements by 1 every ~1.0s and freezes at the snap
# (verified frame-by-frame on 20 plays -- see references/calibration-history.md
# A14, which also documents that the A13 truth set this was first measured
# against was itself wrong by up to 2.3s). Measured offset from the last tick
# to the true snap: mean 0.624s, sd 0.256s over the 17 of 20 calibration plays
# whose digit box is readable.
#
# The tick is NOT a good point estimator (t_tick + 0.60 scores 12/20 within
# +/-0.3s). It IS a good sanity bound on the chip-clear/motion answer, which
# occasionally latches onto a later camera state 1-2s past the snap: keeping
# the A2/A3 answer only when it lands in [t_tick, t_tick + TICK_BRACKET] and
# otherwise falling back to t_tick + TICK_OFFSET scores 16/20 (median 0.150s,
# P90 0.450s) vs 14/20 (0.200s / 0.850s) for A2/A3 alone.
#
# Parameter choice: 16/20 holds across a flat plateau -- bracket 1.3-1.4s,
# offset 0.60-0.65s, read-rate guard 0.60-0.95 -- so the shipped values are the
# MIDDLE of that plateau, not an edge that happens to score well. TICK_BRACKET
# 1.3s is also the physically motivated value (one 1.0s clock period + 0.3s of
# label/render slack); 1.5s also scores 16/20 but implies a missed tick, and
# 1.2s drops to 15/20.
# ---------------------------------------------------------------------------

TICK_BRACKET = 1.3      # snap must land within this of the last tick
TICK_OFFSET = 0.60      # fallback point estimate = t_tick + this
TICK_MIN_READ = 0.75    # skip the constraint below this digit-box read rate
TICK_LO_W, TICK_HI_W = -4.0, 3.0   # OCR window around t_freeze; TICK_MIN_READ
                                    # is calibrated over exactly this span
TICK_PERIOD = 1.0
TICK_TOL = 0.45
TICK_MAX_SPAN = 5.0
TICK_PERSIST = 3


def _pc_digit(im, pbox):
    x, y, w, h = pbox[:4]
    crop = im.crop((x, y, x + w, y + h)).convert("L")
    crop = crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS)
    for mode in ("inv", "white", "red"):
        c = ImageOps.autocontrast(crop)
        if mode == "inv":
            c = ImageOps.invert(c)
        elif mode == "white":
            c = ImageOps.invert(c).point(lambda p: 255 if p > 140 else 0)
        else:
            c = c.point(lambda p: 0 if p > 120 else 255)
        txt = pytesseract.image_to_string(
            c, config="--psm 7 -c tessedit_char_whitelist=0123456789").strip()
        d = "".join(ch for ch in txt if ch.isdigit())
        if d and 0 <= int(d) <= 40:
            return int(d)
    return None


def _pc_runs(video, pbox, t0, t1):
    """[(value, start_t, end_t, n)] runs of a value held >=TICK_PERSIST read
    samples, plus the read fraction over the window."""
    with tempfile.TemporaryDirectory() as td:
        try:
            frames = _extract_frames(video, t0, t1, td)
        except RuntimeError:
            return [], 0.0
        series = [(t, _pc_digit(Image.open(fp), pbox)) for t, fp in frames]
    if not series:
        return [], 0.0
    read_frac = sum(1 for _, v in series if v is not None) / len(series)
    runs, cur = [], None
    for t, v in series:
        if v is None:
            continue
        if cur and v == cur[0]:
            cur[2], cur[3] = t, cur[3] + 1
        else:
            if cur and cur[3] >= TICK_PERSIST:
                runs.append(tuple(cur))
            cur = [v, t, t, 1]
    if cur and cur[3] >= TICK_PERSIST:
        runs.append(tuple(cur))
    merged = []
    for r in runs:
        if merged and merged[-1][0] == r[0]:
            v, st, _, c = merged[-1]
            merged[-1] = (v, st, r[2], c + r[3])
        else:
            merged.append(r)
    return merged, read_frac


def _pc_drop(a_val, b_val):
    """Value drop a->b of 1-3, tolerating a dropped leading digit on a
    single-digit read (OCR renders 12 as "2"). None if implausible."""
    a_alts = {a_val} | ({a_val + 10, a_val + 20, a_val + 30} if a_val < 10 else set())
    b_alts = {b_val} | ({b_val + 10, b_val + 20, b_val + 30} if b_val < 10 else set())
    for av in a_alts:
        for bv in b_alts:
            if av <= 40 and bv <= 40 and 1 <= av - bv <= 3:
                return av - bv
    return None


def _pc_link(a, b):
    dt = b[1] - a[1]
    if dt <= 0 or dt > TICK_MAX_SPAN:
        return None
    dv = _pc_drop(a[0], b[0])
    if dv is None or dt < dv * TICK_PERIOD - TICK_TOL:
        return None
    if abs(dt - dv * TICK_PERIOD) <= TICK_TOL:
        return b[1]
    # b only became readable late; the real transition was one period after a
    return round(min(max(a[1] + dv * TICK_PERIOD, a[2] + 0.05), b[1]), 2)


def playclock_last_tick(video, pbox, t_freeze):
    """(t_tick, read_frac): time of the play clock's last decrement before it
    freezes at the snap, from the longest run-chain consistent with -1 per
    ~1.0s. t_tick is None when no chain of >=2 links exists."""
    runs, read_frac = _pc_runs(video, pbox, t_freeze + TICK_LO_W, t_freeze + TICK_HI_W)
    # The window can span a play boundary. The clock RESETS upward (to 40) once
    # the next play is set, so split on any upward jump >3 and keep only the
    # segment covering t_freeze -- otherwise the chain happily walks into the
    # next play's countdown and reports a tick seconds after this play's snap.
    segs, cur = [], []
    for r in runs:
        if cur and r[0] > cur[-1][0] + 3:
            segs.append(cur); cur = []
        cur.append(r)
    if cur:
        segs.append(cur)
    runs = None
    for sg in segs:
        if sg[0][1] <= t_freeze <= sg[-1][2]:
            runs = sg
            break
    if runs is None:
        cands = [sg for sg in segs if sg[0][1] <= t_freeze]
        runs = cands[-1] if cands else (segs[0] if segs else [])
    n = len(runs)
    if n < 2:
        return None, read_frac
    best, prev, tick = [1] * n, [-1] * n, [None] * n
    for j in range(n):
        for i in range(j):
            t = _pc_link(runs[i], runs[j])
            if t is not None and best[i] + 1 > best[j]:
                best[j], prev[j], tick[j] = best[i] + 1, i, t
    end = max(range(n), key=lambda k: (best[k], k))
    if best[end] < 2:
        return None, read_frac
    return tick[end], read_frac


_PBOX_CACHE = {}


def _playclock_box(video):
    """Scaled playclock digit box, memoised (refine_snap is called once per
    play and this would otherwise be one ffprobe per call)."""
    if video not in _PBOX_CACHE:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import segment as _seg
        vw, vh, _d = _seg.video_info(video)
        _PBOX_CACHE[video] = _seg.scaled_boxes(vw, vh)["playclock"][:4]
    return _PBOX_CACHE[video]


def refine_snap(video, hbox, t_freeze, lo=-0.5, hi=2.5, pbox=None):
    """A2/A3/A4 precedence over bracket [t_freeze+lo, t_freeze+hi].

    Returns (snap_t, snap_src, unreliable):
      snap_src in {"preplay-chip", "motion-sustained", "playclock-bracket"}
      unreliable=True only for the playclock-bracket fallback (A4).
    """
    t0, t1 = t_freeze + lo, t_freeze + hi
    snap, src, unreliable = t_freeze, "playclock-bracket", True
    with tempfile.TemporaryDirectory() as td:
        try:
            frames = _extract_frames(video, t0, t1, td)
        except RuntimeError:
            frames = []
        if len(frames) >= 5:
            s = _chip_clear_time(_chip_std_series(frames, hbox))
            if s is not None:
                snap, src, unreliable = s, "preplay-chip", False
            else:
                s = _motion_onset_time(video, t0, t1, td)
                if s is not None:
                    snap, src, unreliable = s, "motion-sustained", False

    # A15: constrain that answer with the play clock's last tick.
    if pbox is None:
        pbox = _playclock_box(video)
    try:
        t_tick, read_frac = playclock_last_tick(video, pbox, t_freeze)
    except Exception:
        t_tick, read_frac = None, 0.0
    if t_tick is not None and read_frac >= TICK_MIN_READ:
        if not (t_tick <= snap <= t_tick + TICK_BRACKET):
            return round(t_tick + TICK_OFFSET, 2), "playclock-tick", False

    return snap, src, unreliable


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
