#!/usr/bin/env python3
"""Film Room Stage 5a: merge all per-play sources into plays_charted.csv.

Sources merged per play:
  plays.csv          - situation, possession, window (segment.py)
  formations.csv     - banner ground truth (scan_formations.py)
  film/playNNN/meta.txt - snap_est (frames.py)
  batches/outNN.md   - vision chart blocks (haiku agents)
  transcript.json    - announcer + mic text overlapping the window

Adds tempo metadata:
  sec_since_prev_snap  - snap-to-snap within the same possession run
  playclock_at_snap    - HUD play clock value just before the snap
  tempo                - hurry-up (<20s snap-to-snap) / normal / slow (>34s)

Coverage columns (added 2026-07-28 — see SKILL.md "Vision field schema"):
  def_safeties_post    - deep safeties AFTER the snap: 2 / 1 / 0 / unknown
  def_cb_technique     - press / off / bail / mixed / unknown
  def_zone_type        - spot-drop / match / man / unknown
  def_coverage         - family label; agent-supplied, else derived from the
                         three fields above via COVERAGE_TABLE (deterministic)
  def_rotation         - computed: shell_pre vs safeties_post (none/to-1-high/
                         to-2-high/unknown). Never charted, always derived.

Usage: assemble.py GAMEDIR BATCHDIR OUT_CSV
  GAMEDIR = folder holding seg/, film/, transcript.json
"""
import csv
import glob
import json
import os
import re
import sys

VALID_FORM = re.compile(
    r"^(Shotgun|Gun|Pistol|I-? ?Form|Singleback|Strong|Weak|Wildcat|Empty|Goal ?Line|Ace|Maryland)", re.I)
RUN_WORDS = re.compile(
    r"\b(hand(s|ed|ing)? (it )?off|handoff|keeps it|runs? (it )?(inside|outside|up)|"
    r"on the ground|rushing|rushes|carries|carry|counter|the run|run inside|"
    r"pitch(es|ed)?|option|scamper|between the tackles|running lanes?|ground game)\b", re.I)
PASS_WORDS = re.compile(
    r"\b(throw(s|n|ing)?|pass(es|ing)?|completion|complete[sd]?|incomplete|"
    r"fires (it|one)|air(s it)? out|receiver|catch(es)?|caught|interception|"
    r"pocket|sack(ed)?|scramble[sd]?)\b", re.I)


# (safeties_post, zone_type) -> coverage family. Only fills def_coverage when
# the vision agent didn't name one itself. Cover-6 and any split-field call
# CANNOT be derived here (needs field/boundary detail) — the agent must say so
# explicitly, otherwise a split-field look lands as cover-4 or cover-2.
COVERAGE_TABLE = {
    ("0", "man"): "cover-0", ("0", "spot-drop"): "cover-0", ("0", "match"): "cover-0",
    ("1", "man"): "cover-1",
    ("1", "spot-drop"): "cover-3", ("1", "match"): "cover-3-match",
    ("2", "man"): "cover-2-man",
    ("2", "spot-drop"): "cover-2", ("2", "match"): "cover-4",
}
SAFETY_N = {"2": "2", "1": "1", "0": "0", "3": "3",
            "2-high": "2", "1-high": "1", "0-high": "0", "3-high": "3",
            "two": "2", "one": "1", "zero": "0", "three": "3",
            "two high": "2", "one high": "1", "zero high": "0"}
# Low-confidence rotation fallback: free-text hints in def_post_snap that the
# shell moved, used ONLY to fill def_rotation_lc (never def_rotation).
ROTATION_HINT = re.compile(r"\b(spin|spun|rotat|roll(ed|s|ing)?|single[- ]high|"
                           r"drops? down|invert)\w*", re.I)


def norm_safeties(v):
    return SAFETY_N.get((v or "").strip().lower(), "")


def derive_coverage(safeties, zone_type):
    """Deterministic family label from the two discriminating observations."""
    s = norm_safeties(safeties)
    z = (zone_type or "").strip().lower()
    if z in ("man-free", "man free"):
        z = "man"
    return COVERAGE_TABLE.get((s, z), "unknown")


def derive_rotation(shell_pre, safeties_post):
    """Did the pre-snap picture hold? This is the whole point of the new fields."""
    pre = norm_safeties((shell_pre or "").strip().lower().replace("-high", ""))
    if not pre:
        pre = norm_safeties(shell_pre)
    post = norm_safeties(safeties_post)
    if not pre or not post:
        return "unknown"
    if pre == post:
        return "none"
    return f"to-{post}-high"


def derive_man_zone(read):
    """Vote man/zone from v2 behavior tells (references/extraction-framework.md).
    Returns (verdict, confidence) where confidence = net agreeing tells; unknowns abstain."""
    man, zone = 0, 0
    mr = (read.get("motion_response") or "").lower()
    if mr == "follow":
        man += 2          # strongest single tell
    elif mr == "slide":
        zone += 1
    cb = (read.get("cb_relation") or "").lower()
    if cb == "chase":
        man += 1
    elif cb in ("squat", "land"):
        zone += 1
    lb = (read.get("lb_pass_action") or "").lower()
    if lb == "run-with":
        man += 1
    elif lb == "spot":
        zone += 1
    cr = (read.get("crosser_handoff") or "").lower()
    if cr == "trail":
        man += 1
    elif cr == "pass-off":
        zone += 1
    try:
        if int(read.get("rushers")) >= 5:
            man += 1      # heavy pressure usually means man behind it
    except (TypeError, ValueError):
        pass
    # v3: static inside shade is a weak man tell (Trey Thomas stack,
    # references/presnap-tells.md). Weak because coverage shells fake it on
    # human ranked opponents; hand-verify before trusting in a man-heavy film.
    if (read.get("cb_leverage_pre") or "").lower() == "inside":
        man += 1
    if man and zone and abs(man - zone) < 2:
        return "conflicted", 0   # flag for pro adjudication (match looks live here)
    if man > zone:
        return "man", man - zone
    if zone > man:
        return "zone", zone - man
    return "unknown", 0


def transcript_play_type(txt):
    """Adjudicate run vs pass from announcer text; '' when ambiguous."""
    r = len(RUN_WORDS.findall(txt))
    p = len(PASS_WORDS.findall(txt))
    if r >= 2 and r > p:
        return "run"
    if p >= 2 and p > r:
        return "pass"
    return ""


def parse_blocks(batchdir):
    blocks = {}
    for path in sorted(glob.glob(os.path.join(batchdir, "out*.md"))):
        for m in re.split(r"(?m)^PLAY\s+", open(path).read()):
            m = m.strip()
            if not m:
                continue
            lines = m.splitlines()
            try:
                n = int(re.match(r"0*(\d+)", lines[0]).group(1))
            except (AttributeError, ValueError):
                continue
            d = {}
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    d[k.strip()] = v.strip()
            blocks[n] = d
    return blocks


def main():
    gamedir, batchdir, out_csv = sys.argv[1], sys.argv[2], sys.argv[3]
    plays = list(csv.DictReader(open(os.path.join(gamedir, "seg/plays.csv"))))
    forms = {r["n"]: r for r in csv.DictReader(open(os.path.join(gamedir, "seg/formations.csv")))}
    tl = {float(r["t"]): r for r in csv.DictReader(open(os.path.join(gamedir, "seg/hud_timeline.csv")))}
    transcript_data = json.load(open(os.path.join(gamedir, "transcript.json")))
    # Older Lane A workspaces stored the segment array at the document root;
    # newer transcriptions wrap it in {"segments": [...]}. Accept both.
    trans = transcript_data["segments"] if isinstance(transcript_data, dict) else transcript_data
    blocks = parse_blocks(batchdir)

    rows = []
    transcript_rows = []
    prev = {"poss": None, "snap": None}
    for p in plays:
        n = int(p["n"])
        meta_path = os.path.join(gamedir, f"film/play{n:03d}/meta.txt")
        snap = None
        if os.path.exists(meta_path):
            m = re.search(r"snap_est=([\d.]+)", open(meta_path).read())
            snap = float(m.group(1)) if m else None
        # play clock just before snap (last readable value in the 6s prior)
        pc_at_snap = ""
        if snap:
            for dt in range(1, 7):
                r = tl.get(float(int(snap) - dt))
                if r and r.get("playclock"):
                    pc_at_snap = r["playclock"]
                    break
        gap = ""
        if snap and prev["snap"] and p["poss"] == prev["poss"] and p["poss"]:
            gap = round(snap - prev["snap"], 1)
        tempo = ""
        if gap != "":
            tempo = "hurry-up" if gap < 20 else ("slow" if gap > 34 else "normal")
        t0, t1 = float(p["t_first"]), float(p["t_last"])
        # announcers narrate the play from the snap onward (their account of
        # play N spills into window N+1) — anchor on the snap, not the window
        if snap:
            a0, a1 = snap, snap + 18
        else:
            a0, a1 = t1 - 10, t1 + 8
        txt = " ".join(s["text"].strip() for s in trans
                       if s["start"] < a1 and s["end"] > a0)[:400]
        b = blocks.get(n, {})
        f = forms.get(p["n"], {})
        banner = f.get("formation", "")
        banner_ok = bool(banner) and bool(VALID_FORM.match(banner))
        vis_type = b.get("play_type", "").lower()
        tr_type = transcript_play_type(txt)
        # Vision is the authority for run/pass (user directive 2026-07-31).
        # The announcer read stays recorded in play_type_transcript for conflict
        # spotting, but never overrides what the charting agent saw.
        final_type = vis_type or tr_type
        rows.append({
            "n": n, "qtr": p["qtr"], "clock": p["clock"], "dd": p["dd"],
            "poss": p["poss"], "score": f'{p["score_l"]}-{p["score_r"]}',
            "snap_t": snap or "", "sec_since_prev_snap": gap,
            "playclock_at_snap": pc_at_snap, "tempo": tempo,
            "formation": banner if banner_ok else b.get("formation", ""),
            "personnel": (f.get("personnel") or b.get("personnel", "")),
            "formation_src": "banner" if banner_ok else "vision",
            "motion": b.get("motion", ""),
            "play_type": final_type,
            "play_type_vision": vis_type, "play_type_transcript": tr_type,
            "concept": b.get("concept", ""),
            "routes_or_blocking": b.get("routes_or_blocking", ""),
            "def_front": b.get("def_front", ""), "def_shell_pre": b.get("def_shell_pre", ""),
            "def_post_snap": b.get("def_post_snap", ""),
            "def_safeties_post": norm_safeties(b.get("def_safeties_post", "")),
            "def_cb_technique": b.get("def_cb_technique", ""),
            "def_zone_type": b.get("def_zone_type", ""),
            "def_coverage": (b.get("def_coverage", "").strip()
                             or derive_coverage(b.get("def_safeties_post", ""),
                                                b.get("def_zone_type", ""))),
            "def_rotation": derive_rotation(b.get("def_shell_pre", ""),
                                            b.get("def_safeties_post", "")),
            # low-confidence lane: free-text rotation hints, kept separate so
            # tendency splits can choose the strict column
            "def_rotation_lc": (
                "rotation-hinted"
                if derive_rotation(b.get("def_shell_pre", ""),
                                   b.get("def_safeties_post", "")) == "unknown"
                and ROTATION_HINT.search(b.get("def_post_snap", "") or "")
                else ""),
            "formation_initial": b.get("formation_initial", ""),
            "presnap_adjust": b.get("presnap_adjust", ""),
            "adjust_note": b.get("adjust_note", ""),
            "def_adjust": b.get("def_adjust", ""),
            "confidence": b.get("confidence", ""), "note": b.get("note", ""),
        })
        transcript_rows.append({"n": n, "transcript": txt})
        if snap:
            prev = {"poss": p["poss"], "snap": snap}

    with open(out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # Verbatim per-window transcript lives in a sidecar, not the deliverable
    # CSV — it is only consumed during step-7 adjudication, and inlining it
    # roughly doubled row size in the vault copy.
    side = re.sub(r"\.csv$", "", out_csv) + "_transcript.csv"
    with open(side, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["n", "transcript"])
        w.writeheader()
        w.writerows(transcript_rows)
    charted = sum(1 for r in rows if r["play_type"])
    print(f"{len(rows)} plays assembled; {charted} charted; -> {out_csv}")

    # Health check: trustworthy snaps cluster at low playclock (reading taken
    # 1-6s before snap). A bimodal distribution with a fat tail at >=15 means
    # the snap estimator is grabbing menu screens, not real snaps.
    pc_vals = sorted(float(r["playclock_at_snap"]) for r in rows if r["playclock_at_snap"] not in ("", None))
    if pc_vals:
        mid = len(pc_vals) // 2
        median_pc = pc_vals[mid] if len(pc_vals) % 2 else (pc_vals[mid - 1] + pc_vals[mid]) / 2
        pct_low = 100 * sum(1 for v in pc_vals if v <= 5) / len(pc_vals)
        print(f"playclock_at_snap: median={median_pc:.1f}  {pct_low:.0f}% <= 5  (n={len(pc_vals)})")
        if median_pc > 10:
            print("WARNING: median playclock_at_snap > 10 — this signature (bimodal, fat tail "
                  ">=15) means snap localization is likely broken (grabbing menu screens, not real snaps).")


if __name__ == "__main__":
    main()
