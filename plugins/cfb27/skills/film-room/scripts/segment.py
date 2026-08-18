#!/usr/bin/env python3
"""Film Room Stage 2: HUD OCR play segmentation.

Samples the scorebug at 1 fps, OCRs game-state fields locally (tesseract),
and emits:
  hud_timeline.csv  - one row per sampled second (raw OCR, normalized)
  plays.csv         - one row per detected play (boundaries from down&distance
                      transitions, snap refined via play-clock behavior)

Usage:
  segment.py VIDEO OUTDIR                 # full run
  segment.py VIDEO OUTDIR --calibrate T   # dump field crops at time T and exit
  segment.py VIDEO OUTDIR --start S --end E   # limit to a window (seconds)
  segment.py VIDEO OUTDIR --procs N       # OCR worker processes (default 10)

HUD layout (1920x1080, CFB 27 scorebug; scaled proportionally otherwise):
  down/distance box, quarter+clock strip, play clock, both score boxes.

Possession comes from the COLOUR of the down&distance bar, not from OCR: the
bar is tinted with the possessing team's colour, and the two score boxes always
carry the two teams' colours, so the bar is classified by which score box it is
nearer to in RGB. Team-agnostic, and it self-disables when the two teams'
colours are too close to separate. Measured 96% vs hand verification on
UNC-Vanderbilt 2026 (the OCR ball-spot approach it replaced scored 22%).
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageOps
import pytesseract

# Field boxes at 1920x1080: (x, y, w, h, prep, tesseract config, upscale)
#
# dd is deliberately wider and upscaled 4x: the old (845,980,230,38) box clipped
# the leading ordinal digit on real film ("1st & 10" -> "st a10"), which capped
# readability at ~15%. Widening + the alias-tolerant parser below took the same
# film from 2% to 64% in-game readability (67 -> 116 detected plays).
BOXES = {
    "dd":        (820, 976, 280, 44, "thresh", "--psm 7", 4),
    "qtr":       (838, 950, 68, 34, "inv", "--psm 7 -c tessedit_char_whitelist=01234stndrdh", 3),
    # clock x must not start at 914 - that clips the leading '0' of "0:56"
    "clock":     (905, 950, 108, 34, "inv", "--psm 7 -c tessedit_char_whitelist=0123456789:", 3),
    "playclock": (1028, 950, 52, 34, "inv", "--psm 7 -c tessedit_char_whitelist=0123456789", 3),
    "score_l":   (735, 935, 105, 80, "inv", "--psm 8 -c tessedit_char_whitelist=0123456789", 3),
    "score_r":   (1080, 935, 105, 80, "inv", "--psm 8 -c tessedit_char_whitelist=0123456789", 3),
}

# Colour-sample regions for possession, (x0, y0, x1, y1) at 1920x1080.
POSS_REGIONS = {
    "bar":     (880, 986, 1040, 1004),   # the down&distance bar itself
    "score_l": (745, 950, 830, 995),     # left team's score box (their colour)
    "score_r": (1090, 950, 1175, 995),   # right team's score box
}
POSS_MIN_TEAM_SEP = 25    # if the two teams' colours are closer than this, abstain
POSS_MARGIN = 0.6         # nearer box must beat the other by this ratio

# Adaptive (film-wide k-means) colour classification, see compute_adaptive_poss().
# Looser than POSS_MARGIN because the two reference colours are already the
# tightest available film-wide clusters, not a per-frame score-box read that
# can be discoloured by lighting/compression on any given second.
POSS_ADAPTIVE_MARGIN = 0.8
POSS_ADAPTIVE_MIN_AGREEMENT = 0.90   # cluster->side mapping must match the old
                                      # method this often on its confident frames,
                                      # or we abort and fall back to old behaviour
POSS_ADAPTIVE_MIN_SAMPLES = 20       # too few colour samples to trust a k-means fit

ST_GAP_TOLERANCE = 8      # seconds of gap tolerated inside one kickoff/PAT run

CLOCK_RE = re.compile(r"(\d{1,2})[:.](\d{2})")
QTR_RE = re.compile(r"\b([1234])(?:st|nd|rd|th)\b", re.I)

# tesseract habitually garbles the ordinal prefixes on the stylized HUD font.
# No leading word boundary: stray marks fuse onto the ordinal ("sist" for "1st"),
# so anchoring on a word start loses the down entirely.
DOWN_PATS = [
    (re.compile(r"(?:1st|ist|lst|1sr|jst)", re.I), "1"),
    (re.compile(r"(?:2nd|anda|andes|and|2na|end|ena)", re.I), "2"),
    (re.compile(r"(?:3rd|3rake|3rds|3ra|ard|srd)", re.I), "3"),
    (re.compile(r"(?:4th|4tn|ath|atn)", re.I), "4"),
]
# last resort: a bare ordinal suffix with the down digit clipped off
BARE_PATS = [
    (re.compile(r"(?:^|[^a-z0-9])st", re.I), "1"),
    (re.compile(r"(?:^|[^a-z0-9])nd", re.I), "2"),
    (re.compile(r"(?:^|[^a-z0-9])rd", re.I), "3"),
    (re.compile(r"(?:^|[^a-z0-9])th", re.I), "4"),
]
DIGIT_FIX = str.maketrans({"S": "5", "s": "5", "I": "1", "l": "1",
                           "i": "1", "O": "0", "o": "0", "B": "8"})


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd)}\n{r.stderr[-500:]}")
    return r.stdout


def video_info(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height", "-show_entries",
               "format=duration", "-of", "csv=p=0", path])
    lines = [l for l in out.strip().splitlines() if l]
    w, h = map(int, lines[0].split(",")[:2])
    dur = float(lines[-1])
    return w, h, dur


def scaled_boxes(w, h):
    sx, sy = w / 1920.0, h / 1080.0
    return {k: (int(x * sx), int(y * sy), int(bw * sx), int(bh * sy), prep, cfg, up)
            for k, (x, y, bw, bh, prep, cfg, up) in BOXES.items()}


def scaled_regions(w, h):
    sx, sy = w / 1920.0, h / 1080.0
    return {k: (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))
            for k, (x0, y0, x1, y1) in POSS_REGIONS.items()}


def ocr_field(img, box):
    x, y, w, h, prep, config, up = box
    crop = img.crop((x, y, x + w, y + h)).convert("L")
    crop = crop.resize((crop.width * up, crop.height * up), Image.LANCZOS)
    crop = ImageOps.autocontrast(crop)
    if prep == "inv":
        crop = ImageOps.invert(crop)
    elif prep == "thresh":
        crop = ImageOps.invert(crop).point(lambda p: 255 if p > 100 else 0)
    return pytesseract.image_to_string(crop, config=config).strip().replace("\n", " ")


ST_STATE_PATS = [
    # order matters: check the more specific PAT-result phrasings first
    (re.compile(r"pat\s*[&8sS§]?\s*no\s*good|pat\s*[&8sS§]?\s*miss", re.I), "PAT_NOGOOD"),
    (re.compile(r"pat\s*[&8sS§]?\s*good", re.I), "PAT_GOOD"),
    (re.compile(r"kick\s*off|kickoff", re.I), "KICKOFF"),
    (re.compile(r"\bpat\b|extra\s*point", re.I), "PAT"),
]


def detect_st_state(text):
    """Special-teams state read straight off the dd capsule text (KICKOFF /
    PAT / PAT&GOOD / PAT&NO GOOD). The dd box is unreadable as down&distance
    during these states (parse_dd() returns None for them by design) - this
    is the readable classification for that same text."""
    if not text:
        return ""
    t = text.strip()
    for pat, label in ST_STATE_PATS:
        if pat.search(t):
            return label
    return ""


def parse_dd(text):
    """Down&distance from garbled HUD OCR. Tolerates the observed alias set."""
    if not text:
        return None
    t = text.strip()
    if re.search(r"kick\s*off|kickoff|extra\s*point|pat\b", t, re.I):
        return None

    down = pos = end = None
    for pat, d in DOWN_PATS:
        m = pat.search(t)
        if m and (pos is None or m.start() < pos):
            down, pos, end = d, m.start(), m.end()
    if down is None:
        for pat, d in BARE_PATS:
            m = pat.search(t)
            if m and (pos is None or m.start() < pos):
                down, pos, end = d, m.start(), m.end()
    if down is None:
        return None

    tail = t[end:]
    # the ampersand OCRs as s/S/&/8/section-sign; strip ONE leading separator so
    # it is not then mistaken for a digit ("4thsl" -> tail "sl" -> 1, not 51)
    tail = re.sub(r"^[\s.,/\\|_-]*[&8sS§]?[\s.,/\\|_-]*", "", tail)
    if re.search(r"goal", tail, re.I):
        return f"{down}&GOAL"
    if re.search(r"inch", tail, re.I):
        return f"{down}&INCHES"
    for m in re.finditer(r"[0-9SsIilOoB]{1,2}", tail):
        cand = m.group(0).translate(DIGIT_FIX)
        if not cand.isdigit():
            continue
        v = int(cand)
        if 1 <= v <= 30:
            return f"{down}&{v}"
    return None


def parse_clock(text):
    m = CLOCK_RE.search(text)
    if not m:
        return None
    mins, secs = int(m.group(1)), int(m.group(2))
    if mins > 15 or secs > 59:
        return None
    return f"{mins}:{m.group(2)}"


def parse_qtr(text):
    m = QTR_RE.search(text)
    return m.group(1) if m else None


def parse_score(text):
    m = re.search(r"\d{1,2}", text)
    return m.group(0) if m else None


def _mean_rgb(img, region):
    px = list(img.crop(region).convert("RGB").getdata())
    n = max(len(px), 1)
    return (sum(p[0] for p in px) / n,
            sum(p[1] for p in px) / n,
            sum(p[2] for p in px) / n)


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def sample_colors(img, regions):
    """Raw RGB means for the dd bar and both score boxes, one frame's worth.
    Stored per-frame in hud_timeline.csv so possession classification can be
    re-derived/replayed later without re-OCRing the video."""
    return {
        "bar": _mean_rgb(img, regions["bar"]),
        "score_l": _mean_rgb(img, regions["score_l"]),
        "score_r": _mean_rgb(img, regions["score_r"]),
    }


def classify_poss_from_colors(colors):
    """'L' / 'R' / '' — which team's colour the down&distance bar is wearing,
    from already-sampled RGB means. Fixed per-frame threshold: team-agnostic,
    abstains when the two score boxes' colours are too close to separate."""
    bar, left, right = colors["bar"], colors["score_l"], colors["score_r"]
    if _dist(left, right) < POSS_MIN_TEAM_SEP:
        return ""                       # team colours not separable, abstain
    dl, dr = _dist(bar, left), _dist(bar, right)
    if dl < dr * POSS_MARGIN:
        return "L"
    if dr < dl * POSS_MARGIN:
        return "R"
    return ""


def classify_poss(img, regions):
    """'L' / 'R' / '' — which team's colour the down&distance bar is wearing."""
    return classify_poss_from_colors(sample_colors(img, regions))


def _kmeans2(points, iters=50):
    """Minimal, dependency-free (numpy-only) k-means, k=2, deterministic init
    (farthest-pair heuristic - no RNG, so re-runs on the same film reproduce
    the same reference colours). Returns (centers[2,3], assign[n]) or None if
    there are too few distinct points to split."""
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return None
    c0 = pts[0]
    d0 = np.sum((pts - c0) ** 2, axis=1)
    idx1 = int(np.argmax(d0))
    c1 = pts[idx1]
    d1 = np.sum((pts - c1) ** 2, axis=1)
    idx0 = int(np.argmax(d1))
    centers = np.array([pts[idx0], pts[idx1]], dtype=float)
    if np.allclose(centers[0], centers[1]):
        return None                     # all samples identical - one colour only
    for _ in range(iters):
        da = np.sum((pts - centers[0]) ** 2, axis=1)
        db = np.sum((pts - centers[1]) ** 2, axis=1)
        assign = (db < da).astype(int)  # 0 -> nearer centers[0], 1 -> nearer centers[1]
        new_centers = centers.copy()
        moved = False
        for k in (0, 1):
            mask = assign == k
            if mask.any():
                nc = pts[mask].mean(axis=0)
                if not np.allclose(nc, centers[k]):
                    moved = True
                new_centers[k] = nc
        centers = new_centers
        if not moved:
            break
    da = np.sum((pts - centers[0]) ** 2, axis=1)
    db = np.sum((pts - centers[1]) ** 2, axis=1)
    assign = (db < da).astype(int)
    return centers, assign


def _chroma(rgb):
    """Brightness-invariant 2D chromaticity (r/sum, g/sum) * 255.

    Raw-RGB Euclidean distance is dominated by luminance: a dimly-lit
    (shadowed / low-contrast share-screen) capsule of the red team sits
    numerically closer to a neutral grey/black reference than to the same
    team's own brightly-lit red, because the RGB gap from dimming swamps the
    smaller RGB gap from hue. Chromaticity divides out brightness so hue
    dominates the distance instead, fixing that failure mode. Validated on
    2027-rutgers-vs-vanderbilt: raw RGB misread a dim-red 2nd-and-goal
    capsule as the opposing (grey/black) team; chroma correctly read it as
    red. Confirmed to introduce zero window-level flips on a second film.
    """
    r, g, b = rgb
    s = r + g + b
    if s < 1:
        return (0.0, 0.0)
    return (255.0 * r / s, 255.0 * g / s)


def classify_adaptive(bar_rgb, centers, margin):
    """Classify one bar colour against the two film-wide reference centres.
    Returns 0, 1, or None (abstain - within `margin` of both). `bar_rgb` and
    `centers` are in chromaticity space (see _chroma), not raw RGB."""
    d0 = _dist(bar_rgb, tuple(centers[0]))
    d1 = _dist(bar_rgb, tuple(centers[1]))
    if d0 < d1 * margin:
        return 0
    if d1 < d0 * margin:
        return 1
    return None


def compute_adaptive_poss(rows):
    """Film-wide adaptive colour classification (Task 1a).

    Collects every frame's dd-capsule colour, clusters into 2 reference
    colours (k-means, k=2), then maps each cluster to L/R using the frames
    where the existing per-frame fixed-threshold method (classify_poss)
    already decided confidently. If the two methods don't agree on a clean
    mapping, this aborts and leaves poss_adaptive blank everywhere - callers
    then fall back to the old per-frame 'poss' column, per the task's
    "must agree on mapping or abort to old behavior" requirement.

    Mutates rows in place (adds 'poss_adaptive' to every row).
    Returns (used: bool, stats: dict) for the console report.
    """
    for r in rows:
        r["poss_adaptive"] = ""

    # Train (and later classify) only on frames where the capsule is confirmed
    # rendered - a readable dd string. Frames with blank dd include replays,
    # menus, and black transitions, whose bar-region colour is not a team
    # colour at all; mixing those in would let k-means split "HUD vs no-HUD"
    # instead of "team A vs team B". detect_plays() only ever consults poss on
    # rows that already have a non-blank dd, so nothing is lost by restricting
    # here.
    capsule_rows = [r for r in rows if r["dd"] and r["bar_r"] != ""]
    # Classify in chromaticity space (see _chroma) rather than raw RGB - raw
    # RGB distance is luminance-dominated and misreads dim/shadowed frames of
    # one team as the other team's neutral colour.
    chroma_pts = [_chroma((r["bar_r"], r["bar_g"], r["bar_b"])) for r in capsule_rows]
    if len(chroma_pts) < POSS_ADAPTIVE_MIN_SAMPLES:
        return False, {"reason": f"only {len(chroma_pts)} colour samples (<{POSS_ADAPTIVE_MIN_SAMPLES})"}

    fit = _kmeans2(chroma_pts)
    if fit is None:
        return False, {"reason": "k-means could not split the colour samples into 2 clusters"}
    centers, _ = fit

    # Map cluster 0/1 -> L/R using the old method's confident frames (margin=1.0
    # here just means "nearest cluster", used only to build the mapping vote).
    votes = {0: Counter(), 1: Counter()}
    for r, cp in zip(capsule_rows, chroma_pts):
        old = r.get("poss", "")
        if old not in ("L", "R"):
            continue
        cl = classify_adaptive(cp, centers, margin=1.0)
        if cl is not None:
            votes[cl][old] += 1

    side0 = votes[0].most_common(1)[0][0] if votes[0] else None
    side1 = votes[1].most_common(1)[0][0] if votes[1] else None
    if side0 is None or side1 is None or side0 == side1:
        return False, {"reason": "cluster-to-side mapping inconclusive against old method"}
    mapping = {0: side0, 1: side1}

    agree = total = 0
    for r, cp in zip(capsule_rows, chroma_pts):
        old = r.get("poss", "")
        if old not in ("L", "R"):
            continue
        cl = classify_adaptive(cp, centers, margin=1.0)
        if cl is None:
            continue
        total += 1
        if mapping[cl] == old:
            agree += 1
    agreement = agree / total if total else 0.0
    if agreement < POSS_ADAPTIVE_MIN_AGREEMENT:
        return False, {"reason": f"mapping agreement {agreement:.0%} < {POSS_ADAPTIVE_MIN_AGREEMENT:.0%}",
                        "agreement": agreement}

    for r, cp in zip(capsule_rows, chroma_pts):
        cl = classify_adaptive(cp, centers, margin=POSS_ADAPTIVE_MARGIN)
        if cl is not None:
            r["poss_adaptive"] = mapping[cl]

    return True, {"agreement": agreement, "mapping": mapping,
                   "centers_chroma": [tuple(round(v, 1) for v in c) for c in centers],
                   "mapping_votes": total, "n_colour_samples": len(chroma_pts)}


def sample_frames(video, outdir, start, end, fps=1):
    fdir = os.path.join(outdir, "hud_frames")
    os.makedirs(fdir, exist_ok=True)
    dur = end - start
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", str(start), "-t", str(dur), "-i", video,
         "-vf", f"fps={fps}", "-q:v", "5", os.path.join(fdir, "f%06d.jpg")])
    return fdir


# Pool workers get the geometry through module state - it is read-only and
# identical for every frame, and pickling it per task is pure overhead.
_BOXES = None
_REGIONS = None


def _init_worker(boxes, regions):
    global _BOXES, _REGIONS
    _BOXES, _REGIONS = boxes, regions


def _read_frame(path):
    img = Image.open(path)
    dd_raw = ocr_field(img, _BOXES["dd"])
    pc_raw = ocr_field(img, _BOXES["playclock"])
    colors = sample_colors(img, _REGIONS)
    bar, sl, sr = colors["bar"], colors["score_l"], colors["score_r"]
    return {
        "poss": classify_poss_from_colors(colors),
        "dd": parse_dd(dd_raw) or "",
        "qtr": parse_qtr(ocr_field(img, _BOXES["qtr"])) or "",
        "clock": parse_clock(ocr_field(img, _BOXES["clock"])) or "",
        "playclock": pc_raw if pc_raw.isdigit() else "",
        "score_l": parse_score(ocr_field(img, _BOXES["score_l"])) or "",
        "score_r": parse_score(ocr_field(img, _BOXES["score_r"])) or "",
        "dd_raw": dd_raw,
        "st_state": detect_st_state(dd_raw),
        # raw colour samples, kept so possession classification can be
        # replayed/re-clustered offline later without re-OCRing the video
        "bar_r": round(bar[0], 1), "bar_g": round(bar[1], 1), "bar_b": round(bar[2], 1),
        "sl_r": round(sl[0], 1), "sl_g": round(sl[1], 1), "sl_b": round(sl[2], 1),
        "sr_r": round(sr[0], 1), "sr_g": round(sr[1], 1), "sr_b": round(sr[2], 1),
    }


def build_timeline(fdir, boxes, regions, start, fps=1, procs=10):
    files = sorted(os.listdir(fdir))
    paths = [os.path.join(fdir, f) for f in files]
    n = len(paths)
    rows = []
    with Pool(procs, initializer=_init_worker, initargs=(boxes, regions)) as pool:
        for i, rec in enumerate(pool.imap(_read_frame, paths, chunksize=16)):
            rec["t"] = round(start + i / fps, 1)
            rows.append(rec)
            if (i + 1) % 500 == 0:
                ok = sum(1 for r in rows if r["dd"]) / len(rows)
                print(f"  ocr {i+1}/{n} dd_ok={ok:.0%}", flush=True)
    # keep t first for readability
    return [{"t": r.pop("t"), **r} for r in rows]


def majority(values):
    values = [v for v in values if v]
    if not values:
        return ""
    return max(set(values), key=values.count)


def vote_with_conf(values):
    """Majority vote plus how unanimous it was. Returns (winner, conf, n)
    where conf is winner's share of the non-blank votes and n is how many
    non-blank votes were cast (Task 1b: possession cannot change mid-window,
    so plays.csv's poss is decided by voting across the whole window, not a
    single frame)."""
    values = [v for v in values if v]
    if not values:
        return "", 0.0, 0
    c = Counter(values)
    winner, n = c.most_common(1)[0]
    return winner, n / len(values), len(values)


def detect_plays(rows):
    """A play window = a maximal run of one stable down&distance value.

    Same-dd back-to-back plays (e.g. 1st&10 -> 10+ yard gain -> 1st&10) are
    split when the play clock resets upward (>=35 after having been <15).
    Clock/qtr/score are majority-voted over the window (OCR is noisy on the
    stylized clock font). Snap localization happens later in frames.py via
    motion analysis inside each window.
    """
    windows = []
    cur = None
    GAP_TOLERANCE = 12  # seconds of unreadable dd tolerated inside one window
                        # (replay overlays hide the HUD mid-cycle)

    def close(c):
        if c and c["t_last"] - c["t_first"] >= 4:
            windows.append(c)

    for r in rows:
        dd = r["dd"]
        t = float(r["t"])
        if not dd:
            if cur and t - cur["t_last"] > GAP_TOLERANCE:
                close(cur)
                cur = None
            continue
        pc = int(r["playclock"]) if r["playclock"] else None
        pc_high = pc is not None and pc >= 25
        if cur is None or dd != cur["dd"]:
            close(cur)
            cur = None
        elif (pc_high and cur["pc_high_streak"] >= 1 and cur["pc_low_seen"]
              and t - cur["t_first"] >= 10):
            # two consecutive high play-clock reads after a low = genuine
            # reset = same-dd back-to-back play (single high reads are
            # OCR misreads and must not split)
            close(cur)
            cur = None
        if cur is None:
            cur = {"dd": dd, "t_first": t, "t_last": t,
                   "qtrs": [], "clocks": [], "sls": [], "srs": [], "poss": [],
                   "pc_low_seen": False, "pc_high_streak": 0}
        cur["t_last"] = t
        cur["qtrs"].append(r["qtr"])
        cur["clocks"].append(r["clock"])
        cur["sls"].append(r["score_l"])
        cur["srs"].append(r["score_r"])
        # Task 1b window vote: the old fixed-threshold call wins whenever it
        # decided (regression guard - adaptive must never overturn a confident
        # old-method call, only add coverage where the old method abstained).
        # Task 2b: special-teams frames (KICKOFF/PAT) never contribute a vote -
        # possession during a kickoff/PAT is not the dd-bar's team colour.
        if r.get("st_state"):
            frame_poss = ""
        else:
            frame_poss = r.get("poss", "") or r.get("poss_adaptive", "")
        cur["poss"].append(frame_poss)
        cur["pc_high_streak"] = cur["pc_high_streak"] + 1 if pc_high else 0
        if pc is not None and pc < 15:
            cur["pc_low_seen"] = True
    close(cur)

    plays = []
    for w in windows:
        poss, poss_conf, poss_n = vote_with_conf(w["poss"])
        plays.append({"dd": w["dd"], "qtr": majority(w["qtrs"]),
                       "clock": majority(w["clocks"][:5]),
                       "t_first": w["t_first"], "t_last": w["t_last"],
                       "score_l": majority(w["sls"]), "score_r": majority(w["srs"]),
                       "poss": poss, "poss_conf": round(poss_conf, 2), "poss_n": poss_n})
    return plays


def write_plays(plays, path):
    with open(path, "w", newline="") as f:
        # original columns first and unchanged, new columns appended at the end
        wtr = csv.DictWriter(f, fieldnames=["n", "qtr", "clock", "dd", "poss",
                                            "t_first", "t_last", "score_l", "score_r",
                                            "poss_conf", "poss_n"])
        wtr.writeheader()
        for i, p in enumerate(plays, 1):
            wtr.writerow({"n": i, "qtr": p["qtr"], "clock": p["clock"],
                          "dd": p["dd"], "poss": p["poss"],
                          "t_first": p["t_first"], "t_last": p["t_last"],
                          "score_l": p["score_l"], "score_r": p["score_r"],
                          "poss_conf": p.get("poss_conf", ""), "poss_n": p.get("poss_n", "")})


def detect_anchors(rows):
    """Task 2b: kickoff possession anchors. Each KICKOFF run is a deterministic
    possession boundary - the team that just scored kicks off, so the OTHER
    team has the ball once play resumes. Direction is known whenever a
    readable score change straddles the run; otherwise it's an opening/half-
    opening kickoff (or the scoreboard was unreadable) and the anchor is
    still emitted with an empty scoring_team/receiving_team.
    Anchors are NOT wired into the poss decision here - reporting only.

    The scoreboard updates as soon as the TD/PAT graphic shows, which is
    BEFORE the KICKOFF graphic that follows it - so bracketing only the
    KICKOFF sub-run finds "before" and "after" scores that are both already
    post-score and shows no delta. Special-teams states are merged into one
    continuous sequence (PAT/PAT_GOOD/PAT_NOGOOD immediately followed by
    KICKOFF, tolerating ST_GAP_TOLERANCE gaps) and the score is read from
    before/after the WHOLE sequence, while the anchor's own timestamp stays
    pinned to the KICKOFF sub-run so it still marks the actual kickoff."""
    score_series = [(float(r["t"]), int(r["score_l"]), int(r["score_r"]))
                    for r in rows if r["score_l"] and r["score_r"]]

    seqs = []
    cur = None
    for r in rows:
        t = float(r["t"])
        st = r.get("st_state", "")
        if st:
            if cur and t - cur["t_last"] > ST_GAP_TOLERANCE:
                seqs.append(cur)
                cur = None
            if cur is None:
                cur = {"t_first": t, "t_last": t, "kickoff_runs": []}
            cur["t_last"] = t
            if st == "KICKOFF":
                if cur["kickoff_runs"] and t - cur["kickoff_runs"][-1][1] <= ST_GAP_TOLERANCE:
                    cur["kickoff_runs"][-1] = (cur["kickoff_runs"][-1][0], t)
                else:
                    cur["kickoff_runs"].append((t, t))
        elif cur and t - cur["t_last"] > ST_GAP_TOLERANCE:
            seqs.append(cur)
            cur = None
    if cur:
        seqs.append(cur)

    anchors = []
    for seq in seqs:
        if not seq["kickoff_runs"]:
            continue   # PAT-only sequence with no kickoff in view (e.g. end of half)
        run = {"t_first": seq["kickoff_runs"][0][0], "t_last": seq["kickoff_runs"][-1][1]}
        before = [s for s in score_series if s[0] < seq["t_first"]]
        after = [s for s in score_series if s[0] > seq["t_last"]]
        b = before[-1] if before else None
        a = after[0] if after else None
        scoring_team = ""
        note = ""
        if b and a:
            dl, dr = a[1] - b[1], a[2] - b[2]
            if dl > 0 and dr <= 0:
                scoring_team = "L"
            elif dr > 0 and dl <= 0:
                scoring_team = "R"
            elif dl == 0 and dr == 0:
                note = "no score change around kickoff (opening kickoff / no-score punt-style kick)"
            else:
                note = "both scores changed around kickoff - ambiguous, needs hand check"
        else:
            note = "score unreadable before or after this kickoff"
        receiving_team = {"L": "R", "R": "L"}.get(scoring_team, "")
        anchors.append({
            "t_kickoff_start": run["t_first"], "t_kickoff_end": run["t_last"],
            "score_l_before": b[1] if b else "", "score_r_before": b[2] if b else "",
            "score_l_after": a[1] if a else "", "score_r_after": a[2] if a else "",
            "scoring_team": scoring_team, "receiving_team": receiving_team, "note": note,
        })
    return anchors


def write_anchors(anchors, path):
    with open(path, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=["n", "t_kickoff_start", "t_kickoff_end",
                                            "score_l_before", "score_r_before",
                                            "score_l_after", "score_r_after",
                                            "scoring_team", "receiving_team", "note"])
        wtr.writeheader()
        for i, a in enumerate(anchors, 1):
            wtr.writerow({"n": i, **a})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("outdir")
    ap.add_argument("--calibrate", type=float, default=None)
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--procs", type=int, default=10)
    args = ap.parse_args()

    w, h, dur = video_info(args.video)
    boxes = scaled_boxes(w, h)
    regions = scaled_regions(w, h)
    end = min(args.end or dur, dur)
    os.makedirs(args.outdir, exist_ok=True)

    if args.calibrate is not None:
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "cal.png")
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-ss", str(args.calibrate), "-i", args.video, "-frames:v", "1", fp])
            img = Image.open(fp)
            for name, box in boxes.items():
                x, y, bw, bh = box[:4]
                crop = img.crop((x, y, x + bw, y + bh))
                out = os.path.join(args.outdir, f"cal_{name}.png")
                crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS).save(out)
                txt = ocr_field(img, box)
                print(f"{name:10s} -> {txt!r}  ({out})")
            for name, reg in regions.items():
                img.crop(reg).save(os.path.join(args.outdir, f"cal_poss_{name}.png"))
            print(f"possession -> {classify_poss(img, regions)!r} "
                  f"(crops cal_poss_*.png; '' = teams' colours too close)")
        return

    print(f"sampling {args.start:.0f}-{end:.0f}s at 1 fps...")
    fdir = sample_frames(args.video, args.outdir, args.start, end)
    print(f"running OCR ({args.procs} procs)...")
    rows = build_timeline(fdir, boxes, regions, args.start, procs=args.procs)

    adaptive_used, adaptive_stats = compute_adaptive_poss(rows)

    tl_path = os.path.join(args.outdir, "hud_timeline.csv")
    with open(tl_path, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)

    plays = detect_plays(rows)
    pl_path = os.path.join(args.outdir, "plays.csv")
    write_plays(plays, pl_path)

    anchors = detect_anchors(rows)
    an_path = os.path.join(args.outdir, "poss_anchors.csv")
    write_anchors(anchors, an_path)

    readable = sum(1 for r in rows if r["dd"]) / max(len(rows), 1)
    pc = Counter(r["poss"] for r in rows)
    decided = (pc["L"] + pc["R"]) / max(len(rows), 1)
    print(f"timeline: {len(rows)} samples, dd readable {readable:.0%}")
    print(f"possession decided on {decided:.0%} of samples (L {pc['L']} / R {pc['R']})")
    if decided < 0.5:
        print("WARN: possession mostly undecided - the two teams' colours may be "
              "too close to separate; verify by hand before trusting per-team splits")

    if adaptive_used:
        apc = Counter(r["poss_adaptive"] for r in rows if r["poss_adaptive"])
        adecided = sum(apc.values()) / max(len(rows), 1)
        print(f"adaptive colour clustering: trained on {adaptive_stats['n_colour_samples']} capsule-rendered "
              f"frames, mapping agreement {adaptive_stats['agreement']:.0%} on "
              f"{adaptive_stats['mapping_votes']} reference frames - USED "
              f"(adaptive decided {adecided:.0%} of samples, L {apc['L']} / R {apc['R']})")
    else:
        print(f"adaptive colour clustering: NOT used ({adaptive_stats['reason']}) - "
              "window voting falls back to the old per-frame method")

    n_windows = len(plays)
    decided_windows = sum(1 for p in plays if p["poss"])
    print(f"window vote: possession decided on {decided_windows}/{n_windows} play windows "
          f"({decided_windows / max(n_windows, 1):.0%})")

    print(f"plays detected: {len(plays)} -> {pl_path}")

    st_counts = Counter(r["st_state"] for r in rows if r["st_state"])
    if st_counts:
        print(f"special-teams frames tagged: {dict(st_counts)}")
    n_kickoffs = len(anchors)
    n_directed = sum(1 for a in anchors if a["scoring_team"])
    print(f"kickoff anchors: {n_kickoffs} found, {n_directed} with a known direction "
          f"-> {an_path}")

    if readable < 0.5:
        sys.exit("WARN: <50% of samples had readable down&distance - check HUD boxes")


if __name__ == "__main__":
    main()
