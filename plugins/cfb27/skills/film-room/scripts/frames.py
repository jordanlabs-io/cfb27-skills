#!/usr/bin/env python3
"""Film Room Stage 3: per-play keyframes + motion composites.

For each play window from segment.py's plays.csv:
  1. Localize the snap via a motion profile (signalstats YDIF on the field
     region — camera is static pre-snap, pans hard after the snap).
  2. Emit:
     presnap.jpg   - formation still, ~1.2s before the snap
     ghost.jpg     - stabilized min-blend | max-blend long-exposure pair:
                     player paths appear as streaks (dark jerseys in the
                     left/min panel, light jerseys in the right/max panel)
     strip.jpg     - 3x2 film strip, snap -> +3.3s
     result.jpg    - end-of-window frame (post-play spot / gain visible)

Usage:
  frames.py VIDEO PLAYS_CSV OUTDIR [--plays 1,4,9|20-45] [--ghost-secs 3.2]
           [--procs N]
"""
import argparse
import csv
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import segment as seg

FIELD_CROP = "iw:ih*0.85:0:0"     # cut the scorebug strip off the bottom
STRIP_OFFSETS = [0.4, 0.9, 1.5, 2.1, 2.7, 3.3]
PREPLAY_OFFSETS = [-8.0, -5.0, -3.0, -1.2]   # lineup -> snap alignment
SEQ_OFFSETS = [-12.0, -9.7, -7.4, -5.1, -2.8, -0.5]  # presnap_seq label grid
MOTION_FPS = 4
MOTION_LOOKBACK = 25.0            # search the last N s of the window for the snap
PLAY_MOTION_SECS = 2.0            # sustained motion needed to call it a snap
SHORT_WINDOW = 5.0                # windows this brief can't be snap-localized


def parse_play_selector(spec):
    """'1,4,9' and '20-45' and mixtures of both -> set of play-number strings.

    Ranges are supported because SKILL.md documents parallel-splitting a slow
    frames.py run with '--plays A-B'. Before this they silently matched nothing
    and the run exited 0 having produced no output.
    """
    want = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                sys.exit(f"--plays: reversed range {part!r}")
            want.update(str(i) for i in range(a, b + 1))
        elif part.isdigit():
            want.add(str(int(part)))
        else:
            sys.exit(f"--plays: cannot parse {part!r} (want N, N,N or A-B)")
    if not want:
        sys.exit("--plays selected nothing")
    return want


def run(cmd, ok_fail=False):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 and not ok_fail:
        sys.exit(f"command failed: {' '.join(cmd[:8])}...\n{r.stderr[-500:]}")
    return r


def motion_profile(video, t0, t1):
    """Return [(t, ydif)] sampled at MOTION_FPS over [t0, t1]."""
    r = run(["ffmpeg", "-hide_banner", "-ss", str(t0), "-t", str(t1 - t0),
             "-i", video, "-vf",
             f"fps={MOTION_FPS},crop={FIELD_CROP},scale=320:-2,signalstats,"
             "metadata=print:key=lavfi.signalstats.YDIF:file=-",
             "-f", "null", "-"], ok_fail=True)
    prof, t = [], None
    for line in r.stdout.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.search(r"YDIF=([\d.]+)", line)
        if m and t is not None:
            prof.append((t0 + t, float(m.group(1))))
    return prof


def motion_onsets(prof, t_last):
    """Sustained-motion onsets as [(still_secs_before_onset, onset_time)] in
    time order, constrained to end no later than t_last - 5 (the down&distance
    flips several seconds after the tackle, and the next play's clock restarts
    near the window tail)."""
    prof = [(t, v) for t, v in prof if t <= t_last - 5]
    if len(prof) < MOTION_FPS * 4:
        return []
    vals = [v for _, v in prof]
    base = sorted(vals)[len(vals) // 5]          # 20th percentile = idle level
    thresh = max(base * 2.5, base + 1.0)
    need = int(PLAY_MOTION_SECS * MOTION_FPS)
    onsets = []            # (still_secs_before_onset, onset_time)
    streak = 0             # consecutive high-motion samples
    still_before = 0       # low-motion run length preceding current streak
    still_run = 0
    for i, (t, v) in enumerate(prof):
        if v >= thresh:
            if streak == 0:
                still_before = still_run
                still_run = 0
            streak += 1
            if streak == need:
                onsets.append((still_before / MOTION_FPS, prof[i - need + 1][0]))
        else:
            streak = 0
            still_run += 1
    return onsets


def find_snap(prof, t_last, mode="stillest"):
    """Pick a snap time out of the motion onsets.

    mode="stillest": onset following the longest still stretch. Only safe when
      the play-clock signal is there to arbitrate — the longest still stretch
      is often the static play-call menu, not the pre-snap 'set'.
    mode="last": the last onset before t_last - 5. The snap is the final motion
      onset before the play's end region; the menu-return onset happens earlier
      (and after a much longer stillness), so this is the honest fallback when
      pc_stop is None.
    """
    clipped = [(t, v) for t, v in prof if t <= t_last - 5]
    if len(clipped) < MOTION_FPS * 4:
        return max(clipped[0][0], t_last - 8) if clipped else t_last - 8
    onsets = motion_onsets(prof, t_last)
    if not onsets:
        return t_last - 8
    if mode == "last":
        return onsets[-1][1]
    return sorted(onsets)[-1][1]                  # longest stillness wins


def pc_stop_time(video, boxes, t0, t1):
    """Last moment the play clock is visibly counting = just before the snap.

    The CFB 27 HUD hides the play clock once the ball is snapped, so the
    last readable play-clock sample followed by a >=4s unreadable gap marks
    the snap within ~0.5s.
    """
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-ss", str(t0), "-t", str(t1 - t0), "-i", video,
             "-vf", "fps=2", "-q:v", "5", os.path.join(td, "p%04d.jpg")])
        readable = []
        for i, fn in enumerate(sorted(os.listdir(td))):
            img = Image.open(os.path.join(td, fn))
            txt = seg.ocr_field(img, boxes["playclock"])
            if txt.isdigit() and int(txt) <= 40:
                readable.append((t0 + i / 2.0, int(txt)))
    if not readable:
        return None
    # walk from the end: find the last readable sample with no readable
    # successor within 4s
    for t, _v in reversed(readable):
        later = [x for x, _ in readable if t < x <= t + 4]
        if not later:
            prior = [x for x, _ in readable if t - 6 <= x < t]
            if len(prior) >= 2:   # was genuinely counting before it vanished
                return t
    return None


def preplay_box(vw, vh):
    """seg.ocr_field-style box over the bottom HUD strip (full width, bottom
    12%) — the band where CFB 27 prints its PRE-PLAY / SUBS state tag."""
    y = int(vh * 0.88)
    return (0, y, vw, vh - y, "inv", "--psm 6", 3)


def hud_says_presnap(video, box, t):
    """True when the HUD at time t still reads PRE-PLAY / SUBS, i.e. the frame
    is pre-snap and the snap estimate fired early.

    Needs its own uncropped frame: grab() cuts the scorebug off via FIELD_CROP.
    Fails open (False) on any ffmpeg/OCR trouble — a broken gate must never
    take down a charting run.
    """
    try:
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "hud.jpg")
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-ss", f"{max(t, 0):.2f}", "-i", video, "-frames:v", "1",
                 "-q:v", "3", fp], ok_fail=True)
            if not os.path.exists(fp):
                return False
            txt = seg.ocr_field(Image.open(fp), box)
        flat = re.sub(r"[^A-Z]", "", txt.upper())   # PRE-PLAY / PRE PLAY / PREPLAY
        return "PREPLAY" in flat or "SUBS" in flat
    except Exception:
        return False


def grab(video, t, out, width=1280):
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", f"{max(t, 0):.2f}", "-i", video, "-frames:v", "1",
         "-vf", f"crop={FIELD_CROP},scale={width}:-2", "-q:v", "4", out])


def ghost(video, snap, secs, out):
    """Stabilized long-exposure pair: min-blend | max-blend."""
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-ss", f"{snap:.2f}", "-t", f"{secs:.2f}", "-i", video,
             "-vf", f"crop={FIELD_CROP},deshake=rx=32:ry=32,fps=8,scale=960:-2",
             "-q:v", "4", os.path.join(td, "g%03d.jpg")])
        files = sorted(os.listdir(td))
        if len(files) < 8:
            return False
        imgs = [Image.open(os.path.join(td, f)).convert("RGB") for f in files]
        dark = imgs[0]
        light = imgs[0]
        for im in imgs[1:]:
            dark = ImageChops.darker(dark, im)
            light = ImageChops.lighter(light, im)
        w, h = dark.size
        pair = Image.new("RGB", (w * 2 + 8, h), "black")
        pair.paste(dark, (0, 0))
        pair.paste(light, (w + 8, 0))
        pair.save(out, quality=85)
    return True


def preplay(video, snap, out):
    """2x2 lineup grid at PREPLAY_OFFSETS, earliest (top-left) -> latest
    (bottom-right): the offense's first set vs. the snap alignment, so charting
    agents can read audibles/shifts. Cells that predate the lineup show the
    play-call menu — that's signal (the call screen), not a failure."""
    with tempfile.TemporaryDirectory() as td:
        cells = []
        for i, off in enumerate(PREPLAY_OFFSETS):
            fp = os.path.join(td, f"pp{i}.jpg")
            grab(video, snap + off, fp, width=640)
            if os.path.exists(fp):
                cells.append(Image.open(fp).convert("RGB"))
        if len(cells) < 2:
            return False
        cw, ch = cells[0].size
        grid = Image.new("RGB", (cw * 2 + 4, ch * 2 + 4), "black")
        for i, im in enumerate(cells):
            grid.paste(im, ((i % 2) * (cw + 4), (i // 2) * (ch + 2)))
        grid.save(out, quality=85)
    return True


def presnap_seq(video, snap, out):
    """Timestamp-labeled 3x2 grid, snap-12s -> snap-0.5s, reading order = time
    order. The adjustment read: initial alignment (top-left) through audibles /
    shifts / coverage rotations to the final look just before the snap
    (bottom-right). Each cell is stamped with its offset so agents can order
    WHEN an adjustment happened, which preplay.jpg's unlabeled cells cannot."""
    with tempfile.TemporaryDirectory() as td:
        cells = []
        for i, off in enumerate(SEQ_OFFSETS):
            fp = os.path.join(td, f"sq{i}.jpg")
            grab(video, snap + off, fp, width=640)
            if not os.path.exists(fp):
                continue
            im = Image.open(fp).convert("RGB")
            d = ImageDraw.Draw(im)
            label = f"snap{off:+.1f}s"
            d.rectangle([0, 0, 8 * len(label) + 10, 22], fill="black")
            d.text((5, 4), label, fill="yellow")
            cells.append(im)
        if len(cells) < 2:
            return False
        cw, ch = cells[0].size
        grid = Image.new("RGB", (cw * 3 + 8, ch * 2 + 4), "black")
        for i, im in enumerate(cells):
            grid.paste(im, ((i % 3) * (cw + 4), (i // 3) * (ch + 2)))
        grid.save(out, quality=85)
    return True


def strip(video, snap, out):
    with tempfile.TemporaryDirectory() as td:
        cells = []
        for i, off in enumerate(STRIP_OFFSETS):
            fp = os.path.join(td, f"s{i}.jpg")
            grab(video, snap + off, fp, width=640)
            if os.path.exists(fp):   # a grab past EOF writes nothing (rc 0)
                cells.append(Image.open(fp).convert("RGB"))
        if not cells:
            return
        cw, ch = cells[0].size
        grid = Image.new("RGB", (cw * 3 + 8, ch * 2 + 4), "black")
        for i, im in enumerate(cells):
            grid.paste(im, ((i % 3) * (cw + 4), (i // 3) * (ch + 2)))
        grid.save(out, quality=85)


def process_play(job):
    """Everything for one play window. Runs in a worker process; returns the
    status line(s) so the parent prints them in play order."""
    video, outdir, ghost_secs, vw, vh, p = job
    n = p["n"]
    notes = []
    t_first, t_last = float(p["t_first"]), float(p["t_last"])
    pdir = os.path.join(outdir, f"play{int(n):03d}")
    os.makedirs(pdir, exist_ok=True)

    boxes = seg.scaled_boxes(vw, vh)
    pc_stop = pc_stop_time(video, boxes, t_first, t_last - 4)
    m0 = max(t_first, t_last - MOTION_LOOKBACK)
    prof = motion_profile(video, m0, t_last + 2)
    if pc_stop is not None:
        # prefer the play-clock signal; use motion onset when it agrees
        snap_motion = find_snap(prof, t_last)
        snap = snap_motion if abs(snap_motion - pc_stop) <= 3 else pc_stop + 0.5
    else:
        # no play-clock signal: the snap is the LAST onset before the end
        # region, never the stillest (that one is the play-call menu)
        snap = find_snap(prof, t_last, mode="last")

    # Clamp into the window. Every estimator above can hand back a time
    # outside [t_first, t_last] on degenerate input; on UNC-Vanderbilt five
    # short windows all collapsed onto one out-of-window value (4021.5s, in
    # the postgame menus) and two of them were charted as real plays off
    # composites cut from the wrong part of the video.
    short = (t_last - t_first) <= SHORT_WINDOW
    clamped = min(max(snap, t_first), max(t_first, t_last - 1))
    if abs(clamped - snap) > 0.05:
        notes.append(f"  play {n}: snap {snap:.1f}s outside window "
                     f"{t_first:.1f}-{t_last:.1f} -> clamped to {clamped:.1f}s")
        snap = clamped

    # HUD gate: re-grab at successively later onsets while the frame just
    # after the estimated snap still reads PRE-PLAY / SUBS
    later = [t for _, t in motion_onsets(prof, t_last) if t > snap + 0.5]
    hbox = preplay_box(vw, vh)
    unreliable = False
    for _attempt in range(3):
        grab(video, snap - 1.2, os.path.join(pdir, "presnap.jpg"))
        ok = ghost(video, snap, ghost_secs, os.path.join(pdir, "ghost.jpg"))
        strip(video, snap, os.path.join(pdir, "strip.jpg"))
        if not hud_says_presnap(video, hbox, snap + STRIP_OFFSETS[0]):
            break
        if not later or _attempt == 2:   # 2 retries, then give up
            unreliable = True
            break
        snap = later.pop(0)              # only advance if we re-grab

    pp_ok = preplay(video, snap, os.path.join(pdir, "preplay.jpg"))
    sq_ok = presnap_seq(video, snap, os.path.join(pdir, "presnap_seq.jpg"))
    grab(video, t_last - 0.5, os.path.join(pdir, "result.jpg"))
    if short:
        unreliable = True
    flag = " snap_unreliable=1" if unreliable else ""
    flag += f" short_window={t_last - t_first:.1f}s" if short else ""
    with open(os.path.join(pdir, "meta.txt"), "w") as f:
        f.write(f"play={n} dd={p['dd']} qtr={p['qtr']} clock={p['clock']}\n"
                f"window={t_first}-{t_last} snap_est={snap:.1f} "
                f"ghost={'ok' if ok else 'FAILED'} "
                f"preplay={'ok' if pp_ok else 'FAILED'} "
                f"presnap_seq={'ok' if sq_ok else 'FAILED'}{flag}\n")
    notes.append(f"play {n}: dd={p['dd']:<9s} snap≈{snap:7.1f}s "
                 f"ghost={'ok' if ok else 'FAIL'}"
                 f"{' UNRELIABLE' if unreliable else ''}"
                 f"{' SHORT-WINDOW' if short else ''}")
    return "\n".join(notes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("plays_csv")
    ap.add_argument("outdir")
    ap.add_argument("--plays", default=None,
                    help="play numbers: '1,4,9', a range '20-45', or a mix")
    ap.add_argument("--ghost-secs", type=float, default=3.2)
    ap.add_argument("--procs", type=int,
                    default=max(1, (os.cpu_count() or 4) - 2),
                    help="parallel play workers (default: cpu count - 2)")
    args = ap.parse_args()

    plays = list(csv.DictReader(open(args.plays_csv)))
    wanted = parse_play_selector(args.plays) if args.plays else None
    if wanted:
        have = {p["n"] for p in plays}
        missing = wanted - have
        if missing:
            sys.exit(f"--plays: {len(missing)} selected play(s) not in "
                     f"{args.plays_csv}: {sorted(missing, key=int)[:10]}")
    os.makedirs(args.outdir, exist_ok=True)

    vw, vh, _ = seg.video_info(args.video)
    jobs = [(args.video, args.outdir, args.ghost_secs, vw, vh, p)
            for p in plays if not wanted or p["n"] in wanted]

    if args.procs <= 1 or len(jobs) <= 1:
        for job in jobs:
            print(process_play(job), flush=True)
    else:
        with multiprocessing.Pool(min(args.procs, len(jobs))) as pool:
            for line in pool.imap(process_play, jobs):
                print(line, flush=True)
    print(f"frames written for {len(jobs)} play(s)")


if __name__ == "__main__":
    main()
