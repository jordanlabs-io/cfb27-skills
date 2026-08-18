#!/usr/bin/env python3
"""
Coverage-schematic diagram generator for the film-room skill (v2, 2026-07-30).

Regenerates every coverage diagram deterministically (pure PIL, no network,
no random) into references/visual-passes/diagrams/. Content is grounded in
references/football-iq.md, the visual-pass notes, and cross-checked against
the curated coaching-site diagrams in visual-passes/web-diagrams/.

v2 design goals (for haiku VISION-AGENT readability, not humans):
  - one fixed visual grammar, restated in a legend strip on EVERY diagram
  - yard ruler up the left edge so depths ("safeties at 10-12yd") are literal
  - full 11-man defenses incl. a countable 4-man line (DL = squares)
  - zone bubbles named with the CFB 27 coach-cam landmark vocabulary
  - numbered TELL badges tied to callout boxes

Run with: ~/CFB27-film/.venv/bin/python diagrams.py
"""

import math
import os
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- paths ---

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(SKILL_ROOT, "references", "visual-passes", "diagrams")
os.makedirs(OUT_DIR, exist_ok=True)

FONT_REG = "/Users/elijah/Library/Caches/camoufox/Camoufox.app/Contents/Resources/fonts/arial.ttf"
FONT_BOLD = "/Users/elijah/Library/Caches/camoufox/Camoufox.app/Contents/Resources/fonts/arialbd.ttf"


def font(size, bold=False):
    path = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()

# ---------------------------------------------------------------- canvas ---

W, H = 1440, 1080
TITLE_H = 64
LEGEND_H = 58
CAPTION_H = 52
FIELD_TOP = TITLE_H
FIELD_BOTTOM = H - CAPTION_H - LEGEND_H
FIELD_H = FIELD_BOTTOM - FIELD_TOP

DARK_GREEN = (24, 74, 42)
STRIPE_GREEN = (28, 84, 48)
WHITE = (255, 255, 255)
LINE = (225, 225, 225)
OFFENSE = (255, 255, 255)
OFFENSE_OUTLINE = (40, 40, 40)
DEFENSE = (205, 35, 35)
DEFENSE_OUTLINE = (60, 10, 10)
# Zone colors matched to CFB 27's own play art (see visual-passes/playart/,
# legend user-verified 2026-07-30). Kind -> (fill RGBA, outline RGBA).
ZONE_COLORS = {
    "deep":      ((28, 48, 150, 150), (70, 100, 230, 230)),   # quarters/halves/thirds
    "hook":      ((150, 145, 60, 150), (190, 185, 95, 230)),  # hook curl / 3 rec hook / mid read
    "curlflat":  ((110, 70, 160, 150), (155, 110, 210, 230)), # curl flat (royal purple)
    "seamflat":  ((185, 150, 220, 140), (215, 185, 245, 230)),# seam flat (lavender)
    "cloudflat": ((40, 150, 150, 150), (75, 195, 195, 230)),  # cloud flat (teal)
    "hardflat":  ((120, 170, 220, 100), (150, 195, 235, 210)),# hard flat (translucent baby blue)
    "softsquat": ((90, 150, 230, 190), (125, 180, 250, 240)), # soft squat (opaque baby blue)
    "spy":       ((200, 120, 30, 220), (255, 165, 55, 255)),  # QB spy (orange circle)
}
MAN_ARROW = (255, 230, 40)
ROUTE_ARROW = (255, 255, 255)
ROT_ARROW = (80, 230, 230)
TELL_RING = (255, 220, 0)
BAR_BG = (12, 30, 20)
TEXT_LIGHT = (240, 240, 240)
ACCENT = (255, 230, 150)
BOX_BG = (8, 8, 8, 200)

# vertical scale: 25 yards of defense above the LOS + 7 yards of offense below
YDS_ABOVE = 25
YDS_TOTAL = 32


def new_canvas():
    return Image.new("RGB", (W, H), DARK_GREEN)


def draw_title(draw, title):
    draw.rectangle([0, 0, W, TITLE_H], fill=BAR_BG)
    f = font(32, bold=True)
    b = draw.textbbox((0, 0), title, font=f)
    draw.text(((W - (b[2] - b[0])) / 2, (TITLE_H - (b[3] - b[1])) / 2 - b[1]),
              title, font=f, fill=TEXT_LIGHT)


def draw_caption(draw, caption):
    draw.rectangle([0, H - CAPTION_H, W, H], fill=BAR_BG)
    f = font(21, bold=True)
    b = draw.textbbox((0, 0), caption, font=f)
    draw.text(((W - (b[2] - b[0])) / 2, H - CAPTION_H + (CAPTION_H - (b[3] - b[1])) / 2 - b[1]),
              caption, font=f, fill=ACCENT)


def draw_legend(img):
    """Two-row glyph legend drawn on EVERY diagram. Row 2 = the in-game
    zone-color vocabulary (matches CFB 27's own play art)."""
    y0 = H - CAPTION_H - LEGEND_H
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, y0, W, y0 + LEGEND_H], fill=(10, 24, 16))
    draw.line([(0, y0), (W, y0)], fill=(90, 110, 95), width=1)
    f = font(15, bold=True)

    # ---- row 1: glyphs
    cy = y0 + 15
    x = 18
    draw.text((x, cy - 9), "KEY:", font=f, fill=TEXT_LIGHT)
    x += 58

    def label(t, pad=20):
        nonlocal x
        draw.text((x, cy - 9), t, font=f, fill=(215, 215, 215))
        x += draw.textbbox((0, 0), t, font=f)[2] + pad

    draw.ellipse([x, cy - 10, x + 20, cy + 10], fill=OFFENSE, outline=OFFENSE_OUTLINE, width=2)
    x += 26; label("offense")
    draw.rectangle([x, cy - 9, x + 18, cy + 9], fill=OFFENSE, outline=OFFENSE_OUTLINE, width=2)
    x += 24; label("OL")
    draw.rectangle([x, cy - 9, x + 18, cy + 9], fill=DEFENSE, outline=DEFENSE_OUTLINE, width=2)
    x += 24; label("DL")
    draw.ellipse([x, cy - 10, x + 20, cy + 10], fill=DEFENSE, outline=DEFENSE_OUTLINE, width=2)
    x += 26; label("LB/DB")
    draw.ellipse([x, cy - 11, x + 22, cy + 11], outline=TELL_RING, width=4)
    x += 28; label("= THE TELL")
    draw.line([(x, cy), (x + 40, cy)], fill=MAN_ARROW, width=4)
    draw.line([(x + 40, cy), (x + 31, cy - 6)], fill=MAN_ARROW, width=4)
    draw.line([(x + 40, cy), (x + 31, cy + 6)], fill=MAN_ARROW, width=4)
    x += 48; label("man/carry (in-game art: man = lone dot, no zone)")
    for sx in range(0, 36, 13):
        draw.line([(x + sx, cy), (x + sx + 7, cy)], fill=ROUTE_ARROW, width=3)
    x += 44; label("route/motion")
    for sx in range(0, 36, 13):
        draw.line([(x + sx, cy), (x + sx + 7, cy)], fill=ROT_ARROW, width=3)
    x += 44; label("post-snap drop")

    # ---- row 2: in-game zone colors
    cy = y0 + 43
    x = 18
    draw.text((x, cy - 9), "ZONES (in-game colors):", font=f, fill=ACCENT)
    x += 200
    for kind, name in (("deep", "deep 1/4-1/2-1/3"), ("hook", "hook/3RH/mid read"),
                       ("curlflat", "curl flat"), ("seamflat", "seam flat"),
                       ("cloudflat", "cloud flat"), ("hardflat", "hard flat"),
                       ("softsquat", "soft squat"), ("spy", "QB spy")):
        fill, line = ZONE_COLORS[kind]
        draw.ellipse([x, cy - 10, x + 30, cy + 10], fill=fill[:3], outline=line[:3], width=2)
        x += 36; label(name, pad=18)


# ----------------------------------------------------------------- field ---

def draw_field(img, x0=88, x1=W - 36, top=None, bottom=None, ruler=True):
    """Top-down field. Defense above the yellow LOS, offense below.
    Returns geometry incl. yd(y) mapper (yards above LOS -> pixel y)."""
    draw = ImageDraw.Draw(img)
    top = FIELD_TOP + 10 if top is None else top
    bottom = FIELD_BOTTOM - 8 if bottom is None else bottom
    ppy = (bottom - top) / YDS_TOTAL          # pixels per yard
    los_y = top + YDS_ABOVE * ppy

    def yd(yards):
        """yards above the LOS (negative = offense side below)."""
        return los_y - yards * ppy

    # stripes every 5 yards
    n = YDS_TOTAL // 4
    stripe_h = 5 * ppy
    y = top
    i = 0
    while y < bottom - 1:
        if i % 2 == 0:
            draw.rectangle([x0, y, x1, min(y + stripe_h, bottom)], fill=STRIPE_GREEN)
        y += stripe_h
        i += 1
    # yard lines every 5 yards, measured off the LOS
    yards_marks = list(range(-5, YDS_ABOVE + 1, 5))
    for ym in yards_marks:
        yy = yd(ym)
        if top - 1 <= yy <= bottom + 1:
            draw.line([(x0, yy), (x1, yy)], fill=LINE, width=2)
    # hashes (college hashes at 40% / 60% of field width)
    hx_l = x0 + (x1 - x0) * 0.40
    hx_r = x0 + (x1 - x0) * 0.60
    yy = top
    while yy < bottom:
        draw.line([(hx_l - 6, yy), (hx_l + 6, yy)], fill=LINE, width=2)
        draw.line([(hx_r - 6, yy), (hx_r + 6, yy)], fill=LINE, width=2)
        yy += ppy  # every yard
    # sidelines
    draw.line([(x0, top), (x0, bottom)], fill=WHITE, width=3)
    draw.line([(x1, top), (x1, bottom)], fill=WHITE, width=3)
    # LOS
    draw.line([(x0, los_y), (x1, los_y)], fill=(255, 255, 0), width=4)
    # depth ruler on left margin
    if ruler:
        f = font(17, bold=True)
        for ym in range(0, YDS_ABOVE + 1, 5):
            yy = yd(ym)
            lab = "LOS" if ym == 0 else f"{ym}yd"
            b = draw.textbbox((0, 0), lab, font=f)
            draw.text((x0 - (b[2] - b[0]) - 10, yy - (b[3] - b[1]) / 2 - b[1]), lab,
                      font=f, fill=(255, 255, 160) if ym == 0 else (200, 220, 205))
    return dict(x0=x0, x1=x1, top=top, bottom=bottom, los_y=los_y, ppy=ppy, yd=yd,
                xf=lambda fr: x0 + (x1 - x0) * fr)


# --------------------------------------------------------------- players ---

def player(draw, x, y, label, offense=True, r=17, tell=False, tell_n=None):
    fill = OFFENSE if offense else DEFENSE
    outline = OFFENSE_OUTLINE if offense else DEFENSE_OUTLINE
    if tell:
        draw.ellipse([x - r - 9, y - r - 9, x + r + 9, y + r + 9], outline=TELL_RING, width=5)
    draw.ellipse([x - r, y - r, x + r, y + r], fill=fill, outline=outline, width=3)
    f = font(15 if len(label) > 1 else 17, bold=True)
    tcolor = (20, 20, 20) if offense else (255, 255, 255)
    b = draw.textbbox((0, 0), label, font=f)
    draw.text((x - (b[2] - b[0]) / 2, y - (b[3] - b[1]) / 2 - b[1]), label, font=f, fill=tcolor)
    if tell and tell_n is not None:
        badge_r = 12
        bx, by = x + r + 12, y - r - 12
        draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r],
                     fill=TELL_RING, outline=(60, 50, 0), width=2)
        f2 = font(15, bold=True)
        t = str(tell_n)
        b2 = draw.textbbox((0, 0), t, font=f2)
        draw.text((bx - (b2[2] - b2[0]) / 2, by - (b2[3] - b2[1]) / 2 - b2[1]), t, font=f2, fill=(30, 30, 30))


def square(draw, x, y, label, offense=True, s=15, tell=False):
    fill = OFFENSE if offense else DEFENSE
    outline = OFFENSE_OUTLINE if offense else DEFENSE_OUTLINE
    if tell:
        draw.rectangle([x - s - 8, y - s - 8, x + s + 8, y + s + 8], outline=TELL_RING, width=5)
    draw.rectangle([x - s, y - s, x + s, y + s], fill=fill, outline=outline, width=3)
    f = font(13, bold=True)
    tcolor = (20, 20, 20) if offense else (255, 255, 255)
    b = draw.textbbox((0, 0), label, font=f)
    draw.text((x - (b[2] - b[0]) / 2, y - (b[3] - b[1]) / 2 - b[1]), label, font=f, fill=tcolor)


def zone(od, cx, cy, rx, ry, label, kind="deep"):
    fill, line = ZONE_COLORS[kind]
    od.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=line, width=3)
    f = font(14, bold=True)
    b = od.textbbox((0, 0), label, font=f)
    od.text((cx - (b[2] - b[0]) / 2, cy - ry + 5 - b[1]), label, font=f, fill=WHITE)


def arrow(draw, x0, y0, x1, y1, color, width=4, dash=False, head=12):
    if dash:
        seg, gapl = 13, 8
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        ux, uy = dx / dist, dy / dist
        d = 0.0
        while d < dist:
            ed = min(d + seg, dist)
            draw.line([(x0 + ux * d, y0 + uy * d), (x0 + ux * ed, y0 + uy * ed)], fill=color, width=width)
            d += seg + gapl
    else:
        draw.line([(x0, y0), (x1, y1)], fill=color, width=width)
    ang = math.atan2(y1 - y0, x1 - x0)
    for da in (0.5, -0.5):
        draw.line([(x1, y1), (x1 - head * math.cos(ang - da), y1 - head * math.sin(ang - da))],
                  fill=color, width=width)


def callout(img, x, y, text, badge=None, w=None):
    """Yellow-bordered note box pasted at (x, y); optional numbered badge."""
    f = font(16, bold=True)
    dtmp = ImageDraw.Draw(img)
    lines = text.split("\n")
    line_w = max(dtmp.textbbox((0, 0), ln, font=f)[2] for ln in lines)
    line_h = dtmp.textbbox((0, 0), "Ag", font=f)[3] + 5
    pad = 9
    bw = (w or line_w) + pad * 2 + (30 if badge else 0)
    bh = line_h * len(lines) + pad * 2
    ov = Image.new("RGBA", (int(bw), int(bh)), BOX_BG)
    od = ImageDraw.Draw(ov)
    od.rectangle([0, 0, bw - 1, bh - 1], outline=TELL_RING, width=2)
    tx = pad
    if badge is not None:
        br = 11
        od.ellipse([pad, pad, pad + br * 2, pad + br * 2], fill=TELL_RING)
        f2 = font(15, bold=True)
        t = str(badge)
        b2 = od.textbbox((0, 0), t, font=f2)
        od.text((pad + br - (b2[2] - b2[0]) / 2, pad + br - (b2[3] - b2[1]) / 2 - b2[1]), t, font=f2, fill=(30, 30, 30))
        tx = pad + br * 2 + 8
    for i, ln in enumerate(lines):
        od.text((tx, pad + i * line_h), ln, font=f, fill=(255, 245, 210))
    img.paste(ov, (int(x), int(y)), ov)


def make_overlay():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


# --------------------------------------------------------------- offense ---

def draw_offense(draw, f, formation="trips_right"):
    """Gun 11-personnel. Returns dict of skill-player positions."""
    yd, xf = f["yd"], f["xf"]
    ol_y = yd(-1)
    qb_y = yd(-5)
    rb_y = yd(-5)
    wr_y = yd(-0.8)
    cx = xf(0.5)
    sp = (f["x1"] - f["x0"]) * 0.036
    for i, lab in enumerate(["LT", "LG", "C", "RG", "RT"]):
        square(draw, cx + (i - 2) * sp, ol_y, lab)
    player(draw, cx, qb_y, "QB")
    player(draw, cx - sp * 1.6, rb_y, "RB")
    pos = dict(QB=(cx, qb_y), RB=(cx - sp * 1.6, rb_y))
    if formation == "trips_right":
        pos["X"] = (xf(0.07), wr_y)
        pos["Y"] = (cx - sp * 2.9, ol_y)          # TE attached left
        pos["H"] = (xf(0.66), wr_y)
        pos["T"] = (xf(0.77), wr_y)
        pos["Z"] = (xf(0.93), wr_y)
        player(draw, *pos["X"], "X")
        player(draw, *pos["Y"], "Y")
        player(draw, *pos["H"], "H")
        player(draw, *pos["T"], "T")
        player(draw, *pos["Z"], "Z")
    elif formation == "doubles":
        pos["X"] = (xf(0.07), wr_y)
        pos["H"] = (xf(0.21), wr_y)
        pos["T"] = (xf(0.79), wr_y)
        pos["Z"] = (xf(0.93), wr_y)
        for k in ("X", "H", "T", "Z"):
            player(draw, *pos[k], k)
    return pos


def draw_front4(draw, f, blitz=()):
    """Standard 4-man line as red squares on the LOS edge. Returns x positions."""
    yd, xf = f["yd"], f["xf"]
    dl_y = yd(0.8)
    fr = [0.36, 0.45, 0.55, 0.64]
    labs = ["E", "T", "T", "E"]
    xs = []
    for frx, lab in zip(fr, labs):
        x = xf(frx)
        xs.append(x)
        square(draw, x, dl_y, lab, offense=False)
        arrow(draw, x, dl_y, x, yd(-1.6), (255, 120, 120), width=3, head=9)
    for bx, by in blitz:
        arrow(draw, bx, by, bx, yd(-1.4), MAN_ARROW, width=4)
    return xs


# ------------------------------------------------------------- diagrams ---

def save(img, name):
    path = os.path.join(OUT_DIR, name)
    img.convert("RGB").save(path, "PNG")
    print("wrote", path)


def base(title, caption):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    field = draw_field(img)
    draw = ImageDraw.Draw(img)
    draw_title(draw, title)
    draw_caption(draw, caption)
    draw_legend(img)
    return img, ImageDraw.Draw(img), field


def paste_zones(img, zones_spec):
    ov = make_overlay()
    od = ImageDraw.Draw(ov)
    for cx, cy, rx, ry, lab, kind in zones_spec:
        zone(od, cx, cy, rx, ry, lab, kind)
    img.paste(ov, (0, 0), ov)
    return ImageDraw.Draw(img)


# --- 1. Cover 0 ---
def d_cover0():
    img, draw, f = base("COVER 0 — NO DEEP SAFETY, ALL LOCKED, MAX PRESSURE",
                        "Spot it: NOBODY deeper than 8yd pre-snap; every eligible has a locked defender; 6 rushers")
    yd, xf = f["yd"], f["xf"]
    off = draw_offense(draw, f, "trips_right")
    draw_front4(draw, f)
    # 5 man defenders locked on 5 eligibles, tight inside leverage
    cover = [("C", off["X"], 4), ("N", off["T"], 5), ("S", off["H"], 5),
             ("C", off["Z"], 4), ("M", off["Y"], 4)]
    for lab, (tx, ty), depth in cover:
        dx, dy = tx + 14, yd(depth)
        player(draw, dx, dy, lab, offense=False)
        arrow(draw, dx, dy, tx + 4, ty - 24, MAN_ARROW)
    # 2 extra rushers off the edge / A-gap (6 total with the 4 DL)
    for bx_fr, lab in ((0.30, "W"), (0.52, "B")):
        bx = xf(bx_fr)
        player(draw, bx, yd(3), lab, offense=False, tell=True)
        arrow(draw, bx, yd(3), bx + 8, yd(-1.5), MAN_ARROW, width=5)
    callout(img, xf(0.70), f["yd"](22),
            "No deep safety anywhere —\ndeepest defender ~5yd.\n6 rushers vs 5 blockers +\nRB: someone comes free", badge=1)
    callout(img, xf(0.05), f["yd"](14),
            "Beat it with: hots, quick\ngame, picks — ball out\nbefore the 6th rusher hits", w=230)
    save(img, "cover-0.png")


# --- 2. Cover 1 ---
def d_cover1():
    img, draw, f = base("COVER 1 — SINGLE-HIGH MAN (FS FREE + ROBBER)",
                        "Spot it: 1 deep safety MOF at 12-14yd; corners in man leverage chase releases; robber lurks at 8yd")
    yd, xf = f["yd"], f["xf"]
    off = draw_offense(draw, f, "trips_right")
    z = [
        (xf(0.50), yd(17), 175, 80, "DEEP MIDDLE (FS)", "deep"),
        (xf(0.36), yd(8), 95, 46, "MID READ (R)", "hook"),
    ]
    draw = paste_zones(img, z)
    draw_front4(draw, f)
    # trips rule: nickel WITH trips, safety help OPPOSITE over backside #1
    cover = [("C", off["X"], 6), ("N", off["T"], 5), ("S", off["H"], 5), ("C", off["Z"], 6)]
    for lab, (tx, ty), depth in cover:
        dx, dy = tx + 12, yd(depth)
        player(draw, dx, dy, lab, offense=False)
        arrow(draw, dx, dy, tx + 4, ty - 24, MAN_ARROW)
    # Mike on RB
    mx, my = xf(0.47), yd(4)
    player(draw, mx, my, "M", offense=False)
    arrow(draw, mx, my, off["RB"][0] + 10, off["RB"][1] - 24, MAN_ARROW)
    # FS free MOF (THE tell), robber at 8
    fs = (xf(0.50), yd(14))
    player(draw, *fs, "FS", offense=False, tell=True, tell_n=1)
    rob = (xf(0.36), yd(8))
    player(draw, *rob, "R", offense=False, tell=True, tell_n=2)
    arrow(draw, rob[0], rob[1], xf(0.24), yd(5), ROT_ARROW, width=4, dash=True)
    callout(img, xf(0.60), yd(24),
            "FS free in the deep middle\n12-14yd — the only zone\nplayer on the field", badge=1)
    callout(img, xf(0.06), yd(24),
            "Robber squats 8yd MOF\nreading QB — jumps\ncrossers and digs", badge=2)
    callout(img, xf(0.06), yd(10),
            "Trips rule: in C1 the help\n(robber) shades OPPOSITE\nthe nickel, toward backside X", w=255)
    save(img, "cover-1.png")


# --- 3. Cover 2 ---
def d_cover2():
    img, draw, f = base("COVER 2 — TWO-DEEP HALVES, CORNERS SQUAT FLATS",
                        "Spot it: 2 safeties deep + WIDE (outside hashes) at 13-15yd; corners near the LOS jam and stay")
    yd, xf = f["yd"], f["xf"]
    off = draw_offense(draw, f, "doubles")
    z = [
        (xf(0.28), yd(17), 200, 78, "DEEP 1/2", "deep"),
        (xf(0.72), yd(17), 200, 78, "DEEP 1/2", "deep"),
        (xf(0.09), yd(3), 92, 46, "CLOUD FLAT", "cloudflat"),
        (xf(0.91), yd(3), 92, 46, "CLOUD FLAT", "cloudflat"),
        (xf(0.30), yd(7), 105, 50, "HOOK/CURL", "hook"),
        (xf(0.70), yd(7), 105, 50, "HOOK/CURL", "hook"),
        (xf(0.50), yd(9), 95, 52, "MID READ", "hook"),
    ]
    draw = paste_zones(img, z)
    draw_front4(draw, f)
    player(draw, xf(0.28), yd(14), "SS", offense=False, tell=True, tell_n=1)
    player(draw, xf(0.72), yd(14), "FS", offense=False, tell=True, tell_n=1)
    player(draw, xf(0.09), yd(2), "C", offense=False, tell=True, tell_n=2)
    player(draw, xf(0.91), yd(2), "C", offense=False, tell=True, tell_n=2)
    player(draw, xf(0.30), yd(5), "W", offense=False)
    player(draw, xf(0.70), yd(5), "S", offense=False)
    player(draw, xf(0.50), yd(6), "M", offense=False)
    # corners jam #1
    arrow(draw, xf(0.09), yd(2), off["X"][0] + 6, off["X"][1] - 22, ROUTE_ARROW, width=3, dash=True)
    arrow(draw, xf(0.91), yd(2), off["Z"][0] - 6, off["Z"][1] - 22, ROUTE_ARROW, width=3, dash=True)
    callout(img, xf(0.38), yd(25),
            "Safeties WIDE of the hashes,\n13-15yd. Soft spot between\nthem = deep-middle\n'turkey hole'", badge=1)
    callout(img, xf(0.02), yd(11),
            "Corners stay in the flat\nafter the jam — they never\nrun deep with #1", badge=2, w=225)
    save(img, "cover-2.png")


# --- 4/5. Cover 3 Sky / Match ---
def d_cover3(variant="sky"):
    if variant == "sky":
        title = "COVER 3 SKY — 3 DEEP, 4 UNDER SPOT-DROP"
        cap = "Spot it: corners bail to thirds; SS drops DOWN to the flat (Sky); under-defenders squat landmarks, eyes on QB"
        name = "cover-3-sky.png"
    else:
        title = "COVER 3 MATCH — SAME SHELL, CARRY RULES"
        cap = "Spot it: identical pre-snap to Sky — post-snap the under-defenders open hips and RUN with verticals"
        name = "cover-3-match.png"
    img, draw, f = base(title, cap)
    yd, xf = f["yd"], f["xf"]
    off = draw_offense(draw, f, "doubles")
    is_match = variant == "match"
    # in-game art: Sky's outside unders are CURL FLATS (purple); Match's are
    # SEAM FLATS (lavender) — the under-defenders carry the seams.
    ukind, ulab = ("seamflat", "SEAM FLAT") if is_match else ("curlflat", "CURL FLAT")
    z = [
        (xf(0.15), yd(17), 145, 78, "DEEP 1/3", "deep"),
        (xf(0.50), yd(18), 145, 78, "DEEP 1/3", "deep"),
        (xf(0.85), yd(17), 145, 78, "DEEP 1/3", "deep"),
        (xf(0.10), yd(4), 100, 48, ulab, ukind),
        (xf(0.90), yd(4), 100, 48, ulab, ukind),
        (xf(0.35), yd(6), 100, 48, "HOOK/CURL", "hook"),
        (xf(0.65), yd(6), 100, 48, "HOOK/CURL", "hook"),
    ]
    draw = paste_zones(img, z)
    draw_front4(draw, f)
    # corners bail
    for cfr, wr in ((0.13, "X"), (0.87, "Z")):
        cxp = xf(cfr)
        player(draw, cxp, yd(6), "C", offense=False)
        arrow(draw, cxp, yd(6), cxp + (12 if cfr < 0.5 else -12), yd(14), ROT_ARROW, width=4, dash=True)
    player(draw, xf(0.50), yd(14), "FS", offense=False, tell=True, tell_n=1)
    # SS rotates down = Sky
    ss = (xf(0.86), yd(9))
    player(draw, *ss, "SS", offense=False, tell=True, tell_n=2)
    arrow(draw, ss[0], ss[1], xf(0.90), yd(4.5), ROT_ARROW, width=4, dash=True)
    hook_l = (xf(0.35), yd(4.5))
    hook_r = (xf(0.65), yd(4.5))
    player(draw, *hook_l, "M", offense=False)
    player(draw, *hook_r, "N", offense=False, tell=is_match, tell_n=3 if is_match else None)
    player(draw, xf(0.10), yd(3), "W", offense=False)
    if is_match:
        # N carries #2 (T) vertical
        arrow(draw, hook_r[0], hook_r[1], off["T"][0] + 6, yd(13), MAN_ARROW, width=5)
        arrow(draw, off["T"][0], off["T"][1], off["T"][0], yd(12), ROUTE_ARROW, width=3, dash=True)
        callout(img, xf(0.60), yd(25),
                "Hips OPEN — carries #2's\nvertical stride-for-stride.\nLooks like man post-snap;\nshell says zone", badge=3)
    else:
        callout(img, xf(0.22), yd(25),
                "Under-defenders SQUAT the\nlandmark, eyes on QB, no\nhip turn — pure spot-drop", w=250)
    callout(img, xf(0.02), yd(25), "1-high: FS alone\nin the MOF third", badge=1, w=170)
    callout(img, xf(0.72), yd(12) if not is_match else yd(9),
            "SKY = SS down\nto the flat" if not is_match else "SS down to the\nflat (same as Sky)",
            badge=2, w=150)
    save(img, name)


# --- 6. Cover 3 Mabel ---
def d_cover3_mabel():
    img, draw, f = base("COVER 3 MABEL — MAN LOOK, ZONE UNDERNEATH",
                        "Spot it: press look like Cover 1 vs trips, but a free 'buzzer' LB sits MOF matched to NOBODY")
    yd, xf = f["yd"], f["xf"]
    off = draw_offense(draw, f, "trips_right")
    # Under structure verified vs Sam's C3-variations transcript [08:37-10:53]:
    # nickel = SEAM FLAT carrier; safety down = STRONG HOOK; backer exchange =
    # buzzer takes the CURL FLAT; weak flat draws HARD (press) / CLOUD (off).
    z = [
        (xf(0.50), yd(17), 145, 78, "DEEP 1/3 (FS)", "deep"),
        (xf(0.77), yd(4), 95, 46, "SEAM FLAT (N)", "seamflat"),
        (xf(0.62), yd(6.5), 95, 46, "STRONG HOOK (S)", "hook"),
        (xf(0.42), yd(5.5), 95, 46, "CURL FLAT (buzzer)", "curlflat"),
        (xf(0.13), yd(3), 88, 42, "HARD/CLOUD FLAT", "hardflat"),
    ]
    draw = paste_zones(img, z)
    draw_front4(draw, f)
    # corners show press man on #1 each side (the Cover 1 disguise) and match
    # their man; safety/backer exchange fills the zones above
    for tx, ty in (off["X"], off["Z"]):
        player(draw, tx + 10, yd(1.5), "C", offense=False)
        arrow(draw, tx + 10, yd(1.5), tx + 2, ty - 24, MAN_ARROW, width=3)
    player(draw, xf(0.77), yd(3.5), "N", offense=False)
    arrow(draw, xf(0.77), yd(3.5), off["T"][0], yd(10), MAN_ARROW, width=3)  # carries #2 vertical
    player(draw, xf(0.62), yd(5.5), "S", offense=False)
    player(draw, xf(0.13), yd(2.5), "W", offense=False)
    player(draw, xf(0.50), yd(14), "FS", offense=False)
    buz = (xf(0.42), yd(5))
    player(draw, *buz, "M", offense=False, tell=True, tell_n=1)
    callout(img, xf(0.03), yd(24),
            "Press-man look on the\ncorners (Cover 1 disguise)\n— but the buzzer sits in a\nzone matched to NOBODY.\nA free hat = still ZONE", badge=1)
    callout(img, xf(0.63), yd(24),
            "Safety/backer EXCHANGE:\nsafety down = strong hook,\nbacker = new curl flat,\nnickel carries the seam", w=245)
    callout(img, xf(0.03), yd(9),
            "Weak flat: pressed corner\ndraws HARD FLAT, backed\noff draws CLOUD FLAT", w=230)
    save(img, "cover-3-mabel.png")


# --- 7. Cover 3 Cloud ---
def d_cover3_cloud():
    img, draw, f = base("COVER 3 CLOUD — CORNER FLAT ONE SIDE, C3 RULES THE OTHER",
                        "Spot it: cloud-side CORNER squats the flat (C2 look) while a safety takes his third; far side normal C3")
    yd, xf = f["yd"], f["xf"]
    off = draw_offense(draw, f, "doubles")
    z = [
        (xf(0.15), yd(17), 145, 78, "DEEP 1/3 (S)", "deep"),
        (xf(0.50), yd(18), 145, 78, "DEEP 1/3", "deep"),
        (xf(0.85), yd(17), 145, 78, "DEEP 1/3", "deep"),
        (xf(0.09), yd(3), 95, 46, "CLOUD FLAT (C)", "cloudflat"),
        (xf(0.90), yd(4), 100, 48, "CURL FLAT", "curlflat"),
        (xf(0.42), yd(6), 100, 48, "HOOK/CURL", "hook"),
        (xf(0.68), yd(6), 100, 48, "HOOK/CURL", "hook"),
    ]
    draw = paste_zones(img, z)
    draw_front4(draw, f)
    # cloud side (left): corner flat, SS takes deep third behind him
    player(draw, xf(0.09), yd(2), "C", offense=False, tell=True, tell_n=1)
    ss = (xf(0.20), yd(11))
    player(draw, *ss, "SS", offense=False, tell=True, tell_n=2)
    arrow(draw, ss[0], ss[1], xf(0.15), yd(15), ROT_ARROW, width=4, dash=True)
    # normal C3 right side
    player(draw, xf(0.87), yd(6), "C", offense=False)
    arrow(draw, xf(0.87), yd(6), xf(0.85), yd(14), ROT_ARROW, width=4, dash=True)
    player(draw, xf(0.50), yd(14), "FS", offense=False)
    player(draw, xf(0.42), yd(4.5), "M", offense=False)
    player(draw, xf(0.68), yd(4.5), "N", offense=False)
    player(draw, xf(0.90), yd(3), "W", offense=False)
    callout(img, xf(0.02), yd(25),
            "CLOUD side: corner jams &\nSQUATS the flat like C2;\nsafety runs to the deep\nthird behind him", badge=1)
    callout(img, xf(0.60), yd(25),
            "Far side keeps normal C3:\ncorner bails to his third,\ncurl/flat under", w=240)
    save(img, "cover-3-cloud.png")


# --- 8. Cover 4 Quarters ---
def d_cover4_quarters():
    img, draw, f = base("COVER 4 QUARTERS — 4 DEEP, RUN-FIT SAFETIES",
                        "Spot it: safeties 10-12yd FLAT-FOOTED reading #2; corners ~6-7yd off; NOT a prevent — safeties have run gaps")
    yd, xf = f["yd"], f["xf"]
    off = draw_offense(draw, f, "doubles")
    z = [
        (xf(0.11), yd(16), 120, 72, "QUARTER", "deep"),
        (xf(0.37), yd(17), 120, 72, "QUARTER", "deep"),
        (xf(0.63), yd(17), 120, 72, "QUARTER", "deep"),
        (xf(0.89), yd(16), 120, 72, "QUARTER", "deep"),
        (xf(0.50), yd(6), 110, 50, "3 REC HOOK", "hook"),
        (xf(0.11), yd(3), 92, 44, "SEAM FLAT", "seamflat"),
        (xf(0.89), yd(3), 92, 44, "SEAM FLAT", "seamflat"),
        (xf(0.50), yd(3.2), 34, 26, "SPY", "spy"),
    ]
    draw = paste_zones(img, z)
    draw_front4(draw, f)
    player(draw, xf(0.11), yd(7), "C", offense=False)
    player(draw, xf(0.89), yd(7), "C", offense=False)
    ss = (xf(0.37), yd(11))
    fs = (xf(0.63), yd(11))
    player(draw, *ss, "SS", offense=False, tell=True, tell_n=1)
    player(draw, *fs, "FS", offense=False, tell=True, tell_n=1)
    # safeties read #2 (H / T)
    arrow(draw, ss[0], ss[1], off["H"][0] + 6, off["H"][1] - 26, ROUTE_ARROW, width=3, dash=True)
    arrow(draw, fs[0], fs[1], off["T"][0] - 6, off["T"][1] - 26, ROUTE_ARROW, width=3, dash=True)
    # run-fit arrows down into the box
    arrow(draw, ss[0], ss[1], xf(0.42), yd(1.5), MAN_ARROW, width=4)
    arrow(draw, fs[0], fs[1], xf(0.58), yd(1.5), MAN_ARROW, width=4)
    player(draw, xf(0.50), yd(4.5), "M", offense=False)
    player(draw, xf(0.24), yd(3.5), "W", offense=False)
    player(draw, xf(0.76), yd(3.5), "S", offense=False)
    callout(img, xf(0.40), yd(25),
            "Safeties FLAT-FOOTED at\n10-12yd, eyes on #2, and\nthey FIT THE RUN (yellow)\n— quarters is not prevent", badge=1)
    callout(img, xf(0.02), yd(13),
            "Corners 1-on-1 outside\nwith no help over the top\n= best go-ball matchup", w=225)
    save(img, "cover-4-quarters.png")


# --- 9. Cover 4 Palms (two panel) ---
def two_panel(title, caption):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_title(draw, title)
    draw_caption(draw, caption)
    draw_legend(img)
    mid = W // 2
    draw.line([(mid, TITLE_H), (mid, FIELD_BOTTOM)], fill=WHITE, width=3)
    return img, mid


def panel_field(img, x0, x1):
    return draw_field(img, x0=x0 + 62, x1=x1 - 16, ruler=True)


def panel_label(draw, x0, label):
    f = font(21, bold=True)
    draw.rectangle([x0 + 4, TITLE_H + 4, x0 + 16 + draw.textbbox((0, 0), label, font=f)[2], TITLE_H + 38],
                   fill=(8, 8, 8))
    draw.text((x0 + 10, TITLE_H + 10), label, font=f, fill=ACCENT)


def d_cover4_palms():
    img, mid = two_panel("COVER 4 PALMS (2-READ) — CORNER READS #2 AFTER THE SNAP",
                         "Spot it: NO pre-snap tell vs Quarters (frame-verified). The only tell is the corner's reaction to #2's release")
    draw = ImageDraw.Draw(img)

    dnote = ImageDraw.Draw(img)
    dnote.text((W // 2 - 300, FIELD_BOTTOM - 26),
               "Trigger side shown zoomed — the backside of the call mirrors Quarters rules.",
               font=font(17, bold=True), fill=(210, 210, 210))
    for side, (x0, x1) in enumerate(((0, mid - 2), (mid + 2, W))):
        triggered = side == 1
        f = panel_field(img, x0, x1)
        yd, xf = f["yd"], f["xf"]
        draw = ImageDraw.Draw(img)
        # offense: #1 outside, #2 slot, QB
        p1 = (xf(0.78), yd(-0.8))
        p2 = (xf(0.52), yd(-0.8))
        player(draw, *p1, "1")
        player(draw, *p2, "2")
        player(draw, xf(0.30), yd(-5), "QB")
        c = (xf(0.82), yd(7))
        s = (xf(0.48), yd(11))
        if not triggered:
            panel_label(draw, x0, "#2 VERTICAL -> STAYS QUARTERS")
            # #2 runs vertical; corner keeps 1, safety takes 2
            arrow(draw, p2[0], p2[1], p2[0], yd(13), ROUTE_ARROW, width=3, dash=True)
            arrow(draw, p1[0], p1[1], p1[0], yd(13), ROUTE_ARROW, width=3, dash=True)
            player(draw, *c, "C", offense=False, tell=True, tell_n=1)
            player(draw, *s, "S", offense=False)
            arrow(draw, c[0], c[1], p1[0] + 6, yd(12), MAN_ARROW, width=4)
            arrow(draw, s[0], s[1], p2[0] - 6, yd(13), MAN_ARROW, width=4)
            callout(img, x0 + 70, f["yd"](24),
                    "No trigger: corner stays\nover #1, safety carries #2\n— plain Quarters rules", badge=1, w=235)
        else:
            panel_label(draw, x0, "#2 FLAT -> SIDE CONVERTS TO C2")
            # #2 breaks flat; corner squats on it, safety takes vertical #1
            arrow(draw, p2[0], p2[1], xf(0.86), yd(2.5), ROUTE_ARROW, width=3, dash=True)
            arrow(draw, p1[0], p1[1], p1[0], yd(13), ROUTE_ARROW, width=3, dash=True)
            player(draw, *c, "C", offense=False, tell=True, tell_n=2)
            player(draw, *s, "S", offense=False, tell=True, tell_n=2)
            arrow(draw, c[0], c[1], xf(0.87), yd(3.2), MAN_ARROW, width=5)
            arrow(draw, s[0], s[1], p1[0] - 8, yd(13), MAN_ARROW, width=5)
            callout(img, x0 + 70, f["yd"](24),
                    "TRIGGER: #2 flat -> corner\nDRIVES DOWN on it, safety\ntakes the vertical. That\nside is now Cover 2", badge=2, w=245)
            callout(img, x0 + 70, f["yd"](-5.8),
                    "Beat it: double-move behind\nthe squatting corner", w=235)
    save(img, "cover-4-palms.png")


# --- 10. Cover 6 ---
def d_cover6():
    img, draw, f = base("COVER 6 — QUARTERS TO THE FIELD, COVER 2 TO THE BOUNDARY",
                        "Spot it: split-field — call it ONLY when you positively see different rules on each side of the MOF")
    yd, xf = f["yd"], f["xf"]
    off = draw_offense(draw, f, "doubles")
    z = [
        (xf(0.15), yd(17), 165, 78, "DEEP 1/2 (BOUNDARY)", "deep"),
        (xf(0.62), yd(17), 118, 72, "QUARTER", "deep"),
        (xf(0.88), yd(16), 118, 72, "QUARTER", "deep"),
        (xf(0.09), yd(3), 92, 44, "SOFT SQUAT (C)", "softsquat"),
        (xf(0.88), yd(3), 92, 44, "SEAM FLAT", "seamflat"),
        (xf(0.28), yd(5), 95, 46, "HOOK/CURL", "hook"),
        (xf(0.45), yd(6.5), 100, 48, "HOOK/CURL", "hook"),
        (xf(0.68), yd(5.5), 95, 46, "3 REC HOOK", "hook"),
    ]
    draw = paste_zones(img, z)
    draw_front4(draw, f)
    # boundary C2 side
    player(draw, xf(0.09), yd(2), "C", offense=False, tell=True, tell_n=1)
    player(draw, xf(0.15), yd(14), "SS", offense=False, tell=True, tell_n=1)
    # field quarters side
    player(draw, xf(0.62), yd(11), "FS", offense=False, tell=True, tell_n=2)
    player(draw, xf(0.88), yd(7), "C", offense=False, tell=True, tell_n=2)
    arrow(draw, xf(0.62), yd(11), off["T"][0] - 6, off["T"][1] - 26, ROUTE_ARROW, width=3, dash=True)
    player(draw, xf(0.45), yd(5), "M", offense=False)
    player(draw, xf(0.68), yd(4), "N", offense=False)
    player(draw, xf(0.28), yd(3.5), "W", offense=False)
    # MOF divider
    draw.line([(xf(0.40), f["top"] + 4), (xf(0.40), f["los_y"] - 4)], fill=WHITE, width=2)
    callout(img, xf(0.02), yd(25),
            "Boundary = C2 rules:\ncorner squats flat,\nsafety takes the half", badge=1, w=210)
    callout(img, xf(0.44), yd(25),
            "Field = Quarters rules:\nsafety reads #2, corner\noff at 6-7yd", badge=2, w=220)
    save(img, "cover-6.png")


# --- 11. Tell: trips C3 vs C1 ---
def d_tell_trips():
    img, mid = two_panel("TELL: TRIPS LANDMARK — COVER 3 vs COVER 1",
                         "Trips self-reveals with NO motion: nickel AND safety to the trips side = C3; safety OPPOSITE over backside X = C1")
    for side, (x0, x1) in enumerate(((0, mid - 2), (mid + 2, W))):
        is_c3 = side == 0
        f = panel_field(img, x0, x1)
        yd, xf = f["yd"], f["xf"]
        draw = ImageDraw.Draw(img)
        # trips right: X alone left, H/T/Z right
        pos = dict(X=(xf(0.08), yd(-0.8)), H=(xf(0.58), yd(-0.8)),
                   T=(xf(0.73), yd(-0.8)), Z=(xf(0.90), yd(-0.8)))
        for k, p in pos.items():
            player(draw, *p, k)
        player(draw, xf(0.35), yd(-5), "QB")
        player(draw, pos["X"][0] + 10, yd(6), "C", offense=False)
        player(draw, pos["Z"][0] - 4, yd(6), "C", offense=False)
        nk = (pos["T"][0] + 6, yd(4))
        player(draw, *nk, "N", offense=False, tell=True, tell_n=1)
        if is_c3:
            panel_label(draw, x0, "NICKEL + SAFETY SAME SIDE = COVER 3")
            s = (xf(0.72), yd(12))
            player(draw, *s, "S", offense=False, tell=True, tell_n=2)
            callout(img, x0 + 70, f["yd"](24),
                    "Safety stacked over the\ntrips WITH the nickel:\nlandmark zone — Cover 3", badge=2, w=230)
        else:
            panel_label(draw, x0, "SAFETY OPPOSITE NICKEL = COVER 1")
            s = (xf(0.16), yd(12))
            player(draw, *s, "S", offense=False, tell=True, tell_n=2)
            arrow(draw, s[0], s[1], pos["X"][0] + 8, yd(2), ROT_ARROW, width=4, dash=True)
            callout(img, x0 + 70, f["yd"](24),
                    "Safety leaves the trips,\nhelps backside X man\n1-on-1 — Cover 1", badge=2, w=225)
    save(img, "tell-trips-c3-vs-c1.png")


# --- 12. Tell: motion test ---
def d_tell_motion():
    img, mid = two_panel("TELL: THE MOTION TEST — STRONGEST MAN/ZONE READ",
                         "Send a man across: his defender TRAVELS with him = MAN. Defender passes him off, front just re-sets = ZONE")
    for side, (x0, x1) in enumerate(((0, mid - 2), (mid + 2, W))):
        is_man = side == 0
        f = panel_field(img, x0, x1)
        yd, xf = f["yd"], f["xf"]
        draw = ImageDraw.Draw(img)
        h0 = (xf(0.15), yd(-0.8))          # motion start
        h1 = (xf(0.62), yd(-0.8))          # motion end
        t = (xf(0.75), yd(-0.8))
        zz = (xf(0.90), yd(-0.8))
        player(draw, *h0, "H")
        player(draw, *t, "T")
        player(draw, *zz, "Z")
        player(draw, xf(0.38), yd(-5), "QB")
        arrow(draw, h0[0] + 24, h0[1], h1[0] - 20, h1[1], ROUTE_ARROW, width=3, dash=True)
        d0 = (h0[0] + 8, yd(4))
        if is_man:
            panel_label(draw, x0, "DEFENDER TRAVELS = MAN")
            d1 = (h1[0] + 8, yd(4))
            player(draw, *d1, "N", offense=False, tell=True, tell_n=1)
            arrow(draw, d0[0], d0[1], d1[0] - 26, d1[1], MAN_ARROW, width=5)
            callout(img, x0 + 70, f["yd"](24),
                    "His defender chases the\nmotion all the way across\nthe formation = MAN", badge=1, w=230)
        else:
            panel_label(draw, x0, "PASSED OFF = ZONE")
            player(draw, *d0, "N", offense=False)
            s = (xf(0.45), yd(12))
            player(draw, *s, "S", offense=False, tell=True, tell_n=1)
            arrow(draw, d0[0], d0[1], xf(0.40), yd(4.5), ROT_ARROW, width=4, dash=True)
            callout(img, x0 + 70, f["yd"](24),
                    "Nickel slides, safety stays\nhigh, front re-sets strength\n— nobody chases = ZONE", badge=1, w=245)
    save(img, "tell-motion-test.png")


# --- 13. Tell: sky vs match hips ---
def d_tell_hips():
    img, mid = two_panel("TELL: SKY vs MATCH — HIPS AND EYES",
                         "Same shell, different bodies: squatting square to the QB = SKY spot-drop; hips flipped, sprinting with #2 = MATCH")
    draw = ImageDraw.Draw(img)
    for side, (x0, x1) in enumerate(((0, mid - 2), (mid + 2, W))):
        is_match = side == 1
        f = panel_field(img, x0, x1)
        yd, xf = f["yd"], f["xf"]
        draw = ImageDraw.Draw(img)
        p2 = (xf(0.62), yd(-0.8))
        player(draw, *p2, "2")
        player(draw, xf(0.35), yd(-5), "QB")
        n = (xf(0.55), yd(5))
        if is_match:
            panel_label(draw, x0, "MATCH: HIPS FLIP, RUNS WITH #2")
            arrow(draw, p2[0], p2[1], p2[0] + 14, yd(13), ROUTE_ARROW, width=3, dash=True)
            player(draw, *n, "N", offense=False, tell=True, tell_n=2)
            arrow(draw, n[0], n[1], p2[0] + 8, yd(12), MAN_ARROW, width=5)
            callout(img, x0 + 70, f["yd"](24),
                    "#2 threatens vertical ->\nhips OPEN, turns and runs\nstride-for-stride.\nZone that looks like man", badge=2, w=245)
        else:
            panel_label(draw, x0, "SKY: SQUATS, EYES ON QB")
            player(draw, *n, "N", offense=False, tell=True, tell_n=1)
            # facing indicator toward QB
            arrow(draw, n[0], n[1], xf(0.38), yd(-3.5), ROT_ARROW, width=4, dash=True)
            ovd = ImageDraw.Draw(img)
            ovd.text((n[0] + 32, n[1] - 10), "eyes", font=font(15, bold=True), fill=ROT_ARROW)
            callout(img, x0 + 70, f["yd"](24),
                    "Feet planted on the\nlandmark, shoulders square,\neyes locked on the QB —\nnever turns to run", badge=1, w=240)
    save(img, "tell-sky-vs-match-hips.png")


# --- 14. Tell: shell-first read protocol ---
def d_tell_shell_first():
    img, mid = two_panel("TELL: SHELL FIRST — SAFETIES CAN CHEAT BUT THEY CAN'T LIE",
                         "Read order: count deep safeties -> confirm post-snap at top of drop -> only then name the family")
    for side, (x0, x1) in enumerate(((0, mid - 2), (mid + 2, W))):
        one_high = side == 0
        f = panel_field(img, x0, x1)
        yd, xf = f["yd"], f["xf"]
        draw = ImageDraw.Draw(img)
        # minimal offense for scale
        player(draw, xf(0.35), yd(-5), "QB")
        for frx in (0.08, 0.30, 0.70, 0.92):
            player(draw, xf(frx), yd(-0.8), "R")
        if one_high:
            panel_label(draw, x0, "1-HIGH SHELL")
            player(draw, xf(0.50), yd(13), "FS", offense=False, tell=True, tell_n=1)
            fams = ["Cover 1 (man, chase corners)", "Cover 3 Sky / Match (bail corners)",
                    "Cover 3 Mabel / Buzz / Cloud", "Cover 0 (nobody deep, all-out)"]
            tip = "C1 vs C3 is THE confusion\npair: weight CB technique\n(chase=C1, bail=C3) and LB\naction (run-with=man)"
        else:
            panel_label(draw, x0, "2-HIGH SHELL")
            player(draw, xf(0.32), yd(12), "S", offense=False, tell=True, tell_n=1)
            player(draw, xf(0.68), yd(12), "S", offense=False, tell=True, tell_n=1)
            fams = ["Cover 2 (wide safeties 13-15yd)", "Cover 4 Quarters (10-12yd, read #2)",
                    "Cover 4 Palms (identical to Quarters)", "Cover 6 (different rules per side)"]
            tip = "2-high is almost always a\nzone family — man from\n2-high is rare"
        fy = f["yd"](8)
        fnt = font(17, bold=True)
        draw.text((x0 + 72, fy), "Family branches:", font=fnt, fill=WHITE)
        f3 = font(16)
        for i, fam in enumerate(fams):
            draw.text((x0 + 84, fy + 30 + i * 27), "- " + fam, font=f3, fill=(230, 230, 230))
        callout(img, x0 + 70, f["yd"](24), tip, badge=1, w=250)
    save(img, "tell-shell-first.png")


# --------------------------------------------------------- contact sheet ---

def build_diagram_key():
    """Contact sheet: legend header + the 6 load-bearing diagrams, <=2MB."""
    names = [
        "tell-shell-first.png",
        "tell-trips-c3-vs-c1.png",
        "tell-motion-test.png",
        "tell-sky-vs-match-hips.png",
        "cover-3-sky.png",
        "cover-4-palms.png",
    ]
    thumb_w, thumb_h = 660, 495
    cols, rows = 2, 3
    pad = 18
    label_h = 32
    head_h = 118
    sheet_w = cols * thumb_w + (cols + 1) * pad
    sheet_h = head_h + rows * (thumb_h + label_h + pad) + pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), BAR_BG)
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 14), "DIAGRAM KEY — 6 load-bearing coverage/tell schematics", font=font(30, bold=True), fill=TEXT_LIGHT)
    draw.text((pad, 56),
              "Shared grammar: white=offense, red=defense (squares=linemen), yellow ring=THE TELL, yellow arrow=man/carry, white dash=route, cyan dash=drop.",
              font=font(19), fill=(210, 210, 210))
    draw.text((pad, 82),
              "Zone colors match CFB 27's own play art: dark blue=deep, olive=hook/3RH/mid read, purple=curl flat, lavender=seam flat, teal=cloud flat, baby blues=hard flat/soft squat, orange=QB spy.",
              font=font(19), fill=(210, 210, 210))
    f_lab = font(20, bold=True)
    for i, name in enumerate(names):
        col, row = i % cols, i // cols
        x = pad + col * (thumb_w + pad)
        y = head_h + row * (thumb_h + label_h + pad)
        thumb = Image.open(os.path.join(OUT_DIR, name)).convert("RGB").resize((thumb_w, thumb_h))
        sheet.paste(thumb, (x, y))
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline=WHITE, width=2)
        draw.text((x, y + thumb_h + 4), name, font=f_lab, fill=ACCENT)
    out_path = os.path.join(OUT_DIR, "diagram-key.jpg")
    sheet.save(out_path, "JPEG", quality=85, optimize=True)
    size = os.path.getsize(out_path)
    print("wrote", out_path, f"({size/1e6:.2f} MB)")
    if size > 2 * 1024 * 1024:
        sheet.save(out_path, "JPEG", quality=65, optimize=True)
        print("re-saved at lower quality:", os.path.getsize(out_path) / 1e6, "MB")


def main():
    d_cover0()
    d_cover1()
    d_cover2()
    d_cover3("sky")
    d_cover3("match")
    d_cover3_mabel()
    d_cover3_cloud()
    d_cover4_quarters()
    d_cover4_palms()
    d_cover6()
    d_tell_trips()
    d_tell_motion()
    d_tell_hips()
    d_tell_shell_first()
    build_diagram_key()


if __name__ == "__main__":
    main()
