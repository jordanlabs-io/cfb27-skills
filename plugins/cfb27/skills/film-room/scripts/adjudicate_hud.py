#!/usr/bin/env python3
"""HUD-delta adjudication - fallback result lane for commentary-less film.

Derives result/yards/key_event per play from the NEXT play's HUD state
(down&distance progression, possession flips, score deltas). Replaces the
transcript-adjudication stage when the recording has no announcer audio.

Usage:
  adjudicate_hud.py seg/plays.csv hud_results.csv
  adjudicate_hud.py --reattribute GAMEDIR

--reattribute re-reads GAMEDIR/plays_charted.csv (which carries post-rescue
poss + poss_src, filled in later by poss_rescue.py) and re-resolves every
TD-UNATTRIBUTED / TD / DEF-TD row against current possession, using score
deltas recomputed from GAMEDIR/seg/plays.csv. It rewrites ONLY the
result/key_event cells it owns -- play_type and v2_* columns (vision
authority) are never touched.
"""
import csv
import os
import re
import sys

DD_RE = re.compile(r"([1234])&(\d{1,2}|GOAL|INCHES)", re.I)
SCORE_BOUND_S = 120.0  # a "next" score reading farther than this is untrusted
OWNED_KEY_EVENTS = ("TD", "DEF-TD", "TD-UNATTRIBUTED")


def parse_dd(dd):
    m = DD_RE.match(dd or "")
    if not m:
        return None, None
    down = int(m.group(1))
    d = m.group(2).upper()
    dist = {"GOAL": None, "INCHES": 1}.get(d, None)
    if dist is None and d not in ("GOAL",):
        dist = int(d)
    return down, dist  # dist None => &GOAL


def iscore(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def itime(row, key):
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return None


def load_plays(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def next_nonblank(plays, j, side):
    """First non-blank raw reading strictly after index j, any distance."""
    for k in range(j + 1, len(plays)):
        raw = iscore(plays[k].get(f"score_{side}"))
        if raw is not None:
            return raw
    return None


def build_monotonic(plays):
    """Running best-known-good score per side BEFORE each row (best_l/best_r
    as of just before row i), used to sanity-check each row's OWN raw
    reading as a non-garbage base.

    seg/plays.csv scores are OCR'd off the HUD and are frequently blank,
    or garbled by a replay overlay -- either a transient *backward* blip
    (e.g. 21 -> 2 -> 21) or a transient *upward* spike that reverses one
    row later (e.g. this game's R 9 -> 7 at n13 -> n14: a single misread
    frame, not a real 2-point swing). A real score never decreases, so any
    reading below the running best is noise; a reading that DOES clear the
    running best is only trusted once confirmed by the following non-blank
    reading not dropping below it -- otherwise it's a one-frame misread and
    must not get folded into the running best, or it would permanently
    poison every later row's base-validity check.

    This is deliberately NOT used as a substitute base when a row's own
    reading is blank -- carrying a stale/never-observed "0" forward as a
    window's base would let one real score jump, first picked up several
    rows later, get independently claimed by every blank-scored row before
    it (a duplicate-attribution bug). A window only owns a scoring delta
    when its own row has a real score reading to diff from.
    """
    best_l = best_r = 0
    out = []
    for i, p in enumerate(plays):
        out.append((best_l, best_r))  # state as of just before this row
        li, ri = iscore(p.get("score_l")), iscore(p.get("score_r"))
        if li is not None and li >= best_l:
            confirm = next_nonblank(plays, i, "l")
            if confirm is None or confirm >= li:
                best_l = li
        if ri is not None and ri >= best_r:
            confirm = next_nonblank(plays, i, "r")
            if confirm is None or confirm >= ri:
                best_r = ri
    return out


def find_next_reading(plays, i, side, base, bound_s=SCORE_BOUND_S):
    """Nearest readable, monotonic, *stable* score for `side` after window i.

    Returns (value, status). status is "ok" only when a candidate reading is
    found within bound_s seconds of the window's end, is not a backward
    (garbage) blip, and is confirmed by the following non-blank reading not
    dropping below it (rejects a single-row upward spike that gets reversed
    one row later -- e.g. a replay overlay misreading a digit for one frame
    and correcting itself, seen in this game's HUD as R 9 -> 7 at n13->n14).
    "distant" means a candidate existed but only past the bound; "absent"
    means nothing was seen at all.
    """
    t0 = itime(plays[i], "t_last")
    if t0 is None:
        t0 = itime(plays[i], "t_first") or 0.0
    saw = False
    for j in range(i + 1, len(plays)):
        tj = itime(plays[j], "t_first")
        if tj is None:
            tj = itime(plays[j], "t_last") or 0.0
        gap = tj - t0
        raw = iscore(plays[j].get(f"score_{side}"))
        if gap > bound_s:
            if raw is not None:
                saw = True
            break
        if raw is not None:
            saw = True
            if raw >= base:
                confirm = next_nonblank(plays, j, side)
                if confirm is None or confirm >= raw:
                    return raw, "ok"
                # else: single-row spike immediately reversed -- garbage,
                # keep scanning within bound for a stable candidate
            # else: backward/garbage reading, keep scanning within bound
    return None, ("distant" if saw else "absent")


def resolve_scorer(plays, i, monotonic):
    """Bounded, monotonic-guarded scorer/delta for window i, or (None, None).

    A window only owns a delta on a side when its OWN row has a raw,
    non-garbage reading for that side to serve as the base (matching the
    original semantics of "diff this row against the next"); the forward
    search only extends how far we're willing to look for the confirming
    *next* reading, bounded so a replay-stale or distant readback can't
    masquerade as this window's own scoring event.
    """
    mono_before_l, mono_before_r = monotonic[i]
    own_l = iscore(plays[i].get("score_l"))
    own_r = iscore(plays[i].get("score_r"))
    base_l_ok = own_l is not None and own_l >= mono_before_l
    base_r_ok = own_r is not None and own_r >= mono_before_r
    # Only search for a confirming "next" reading when this row's own
    # reading is itself trustworthy -- a rejected/garbage own-reading has
    # no valid base to diff against, so there's nothing to search for.
    d_l = d_r = 0
    if base_l_ok:
        nl, stat_l = find_next_reading(plays, i, "l", own_l)
        if stat_l == "ok":
            d_l = nl - own_l
    if base_r_ok:
        nr, stat_r = find_next_reading(plays, i, "r", own_r)
        if stat_r == "ok":
            d_r = nr - own_r
    if 0 < d_l <= 8 and d_r <= 0:
        return "L", d_l
    if 0 < d_r <= 8 and d_l <= 0:
        return "R", d_r
    return None, None


def naive_scorer(p, nxt):
    """Original unguarded immediate-neighbor delta, used only to detect
    'a scoring-looking delta exists but the safe/bounded resolver could not
    confirm it' -> CHECK, instead of silently doing nothing."""
    dl = iscore(nxt.get("score_l")), iscore(p.get("score_l"))
    dr = iscore(nxt.get("score_r")), iscore(p.get("score_r"))
    d_l = dl[0] - dl[1] if None not in dl else 0
    d_r = dr[0] - dr[1] if None not in dr else 0
    if 0 < d_l <= 8 and d_r <= 0:
        return "L"
    if 0 < d_r <= 8 and d_l <= 0:
        return "R"
    return None


def adjudicate_window(plays, i, monotonic, poss_override=None):
    """(result, yards, key) for a scoring event in window i, or None if no
    score signal was found (caller falls through to DD-based logic)."""
    p = plays[i]
    nxt = plays[i + 1] if i + 1 < len(plays) else None
    if nxt is None:
        return None
    poss = poss_override if poss_override is not None else p.get("poss")
    scorer, delta = resolve_scorer(plays, i, monotonic)
    if scorer:
        if delta >= 6:
            if not poss:
                return ("touchdown (side unattributed - rerun after possession rescue)",
                        "", "TD-UNATTRIBUTED")
            off_scored = scorer == poss
            return ("touchdown" if off_scored else "defensive touchdown", "",
                     "TD" if off_scored else "DEF-TD")
        elif delta == 3:
            return ("field goal", "", "FG")
        elif delta == 2:
            return ("safety", "", "SAFETY")
    elif naive_scorer(p, nxt):
        return ("score change unresolved (stale/distant HUD reading)", "", "CHECK")
    return None


def adjudicate(plays):
    monotonic = build_monotonic(plays)
    rows = []
    for i, p in enumerate(plays):
        nxt = plays[i + 1] if i + 1 < len(plays) else None
        down, dist = parse_dd(p["dd"])
        result, yards, key = "", "", ""
        if nxt:
            win = adjudicate_window(plays, i, monotonic)
            if win:
                result, yards, key = win
            else:
                ndown, ndist = parse_dd(nxt["dd"])
                same_poss = p["poss"] and p["poss"] == nxt["poss"]
                if same_poss and down and ndown:
                    if ndown == down + 1 and dist and ndist:
                        yards = dist - ndist
                        result = f"gain of {yards}" if yards > 0 else (
                            "no gain" if yards == 0 else f"loss of {-yards}")
                    elif ndown == 1 and (ndist == 10 or nxt["dd"].upper().endswith("GOAL")):
                        result = "first down"
                        yards = f">={dist}" if dist else ""
                        key = "1ST-DOWN"
                    elif ndown == down + 1 and dist and ndist is None:
                        result = "gain (to goal-to-go)"
                    elif ndown == 1 and ndist and ndist != 10:
                        result = "penalty/unusual"
                        key = "CHECK"
                    elif ndown == down and dist == ndist:
                        result = "repeat dd"
                        key = "CHECK"
                    else:
                        result = "unclear"
                        key = "CHECK"
                elif p["poss"] and nxt["poss"] and p["poss"] != nxt["poss"]:
                    if down == 4:
                        result = "possession flip (punt or turnover-on-downs)"
                        key = "POSS-FLIP-4TH"
                    else:
                        result = "possession flip (turnover or end of half)"
                        key = "TURNOVER?"
        rows.append({"n": p["n"], "hud_result": result, "hud_yards": yards,
                     "hud_key_event": key})
    return rows


def main_default(plays_path, out_path):
    plays = load_plays(plays_path)
    rows = adjudicate(plays)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["n", "hud_result", "hud_yards", "hud_key_event"])
        w.writeheader()
        w.writerows(rows)
    filled = sum(1 for r in rows if r["hud_result"])
    print(f"{len(rows)} plays, {filled} adjudicated from HUD deltas")


def reattribute(gamedir):
    seg_path = os.path.join(gamedir, "seg", "plays.csv")
    charted_path = os.path.join(gamedir, "plays_charted.csv")

    plays = load_plays(seg_path)
    monotonic = build_monotonic(plays)
    seg_index = {p["n"]: i for i, p in enumerate(plays)}

    with open(charted_path, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        charted = list(reader)

    changed = []
    for row in charted:
        if row.get("key_event") not in OWNED_KEY_EVENTS:
            continue
        i = seg_index.get(row.get("n"))
        if i is None:
            continue
        win = adjudicate_window(plays, i, monotonic, poss_override=row.get("poss"))
        if not win:
            continue
        new_result, _yards, new_key = win
        old_result, old_key = row.get("result", ""), row.get("key_event", "")
        if new_key != old_key or new_result != old_result:
            changed.append((row.get("n"), old_key, new_key, old_result, new_result))
            row["result"] = new_result
            row["key_event"] = new_key

    with open(charted_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(charted)

    print(f"reattribute: {len(charted)} rows scanned, {len(changed)} updated")
    for n, ok, nk, orr, nr in changed:
        print(f"  n={n}: {ok} -> {nk}  ({orr!r} -> {nr!r})")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--reattribute":
        reattribute(sys.argv[2])
        return
    main_default(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
