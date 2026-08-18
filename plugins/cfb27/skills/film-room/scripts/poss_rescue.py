#!/usr/bin/env python3
"""Possession rescue for Lane B film with a degraded colour lane.

Three recovery sources, applied in priority order AFTER segment.py's dd-bar
colour lane (which stays the primary authority — this script only fills
blanks, it never overwrites a measured read):

1. MENU lane: on caller-screen film the recording owner's play-call menu is
   visible between plays. An offensive playbook screen (formation-family
   tiles: Shotgun, Pistol, I Form, ...) means the OWNER is on offense; a
   defensive screen (Cover N, blitzes, Nickel/Dollar/Dime) means the owner is
   on defense. Menus are bright UI renders, immune to the night/fog washout
   that collapses the colour lane. Classifies off the combined text of
   v2_screen_call (OCR'd call banner) + v2_menu_tiles (verbatim menu-tile
   transcriptions); v2_menu_side (an agent's offense/defense judgment on the
   visible menu) is used as a tiebreak ONLY when the OFF/DEF regexes both
   fire on the same text (genuine internal conflict) — NOT when neither
   fires, since v2_menu_side alone measured only 70-74% on non-play-call
   screens (recruiting/stats/substitution overlays) in validation; that case
   abstains instead. Validated 2026-08-13 on Baylor-NC State (screen_call
   only): 28/28 agreement with the colour lane on plays where both decided.
   Masked-recovery validated against the hand-verified UNC-VAND possession
   chart (poss_hand): pattern-decided plays ~95% accurate, overall
   recovered-play accuracy 91-92% across 15-60% mask fractions (100 trials
   each) — clears the >=90% bar. On 2027-rutgers-vs-vanderbilt, tightening
   the tiebreak (plus a `pa\b`-inside-"Tampa" regex fix — that stray match
   was inflating false ambiguity) improved colour-lane agreement from
   71/74 to 56/57 (98.2%); it does not yet recover new blanks there because
   the film's still-blank windows currently carry no OCR'd menu text at all
   (v2_screen_call="unknown", v2_menu_tiles="[]") — a charting-coverage gap,
   not a classifier gap. The lane will pick up those plays automatically
   once vision charting fills in menu text for that stretch.
2. FILL lane: conservative continuity fill — a blank run of <= --maxgap plays
   flanked on BOTH sides by the same team, with no score change across the
   gap, inherits that team. Validated against the hand-verified UNC-VAND
   possession chart (masked-recovery simulation): maxgap 3 -> 96.9% accurate,
   maxgap 5 -> 91%. Default 3. Long gaps stay blank on purpose: a full drive
   can hide inside them.
3. CHAIN lane: a blank window that sits inside a provably-continuous down
   chain (down increments by exactly 1 AND distance-to-go strictly shrinks
   play-over-play within the same series: 1&10 -> 2&7 -> 3&2; no fresh 1st
   down; no score change; no gap > 90s between windows; dd always readable)
   cannot contain a possession flip, so it inherits any measured/menu-decided
   (never fill-decided) possession found elsewhere in that same chain —
   regardless of chain length. A fresh 1st down always breaks the chain (it
   may be a conversion OR a turnover/punt, indistinguishable from dd alone)
   so nothing propagates across it. The distance-shrink requirement is not
   cosmetic: on the UNC-VAND ground truth, two genuine possession flips
   (n=44->45, n=108->109) each disguised themselves as a same-down-plus-1
   sequence with a FLAT (non-shrinking) distance-to-go — down-increment
   alone would have silently mis-chained them. Chain length is otherwise
   unbounded — the principled extension beyond --maxgap's arbitrary cap.
   Masked-recovery validated against UNC-VAND: 0 mis-chains across all 116
   real (unmasked) windows, 100% recovery accuracy across 31-169 chain-lane
   recoveries per mask fraction (15-60% mask, 100 trials each) — clears the
   >=96.9% bar with room to spare.

Usage: poss_rescue.py GAMEDIR OWNER_SIDE [--maxgap 3] [--dry-run]
  OWNER_SIDE: L or R — which HUD side the recording owner's team occupies.

Writes poss + poss_src (colour|menu|fill|chain) back into seg/plays.csv and,
when present, plays_charted.csv (matched on play n). Prints a recovery report.
"""
import argparse
import csv
import json
import os
import re
import sys

# Formation families that only exist in OFFENSIVE playbook menus.
OFF_PAT = re.compile(
    r"shotgun|pistol|singleback|i.?form|power i|wildcat|wing|flexbone|heavy"
    r"|maryland i|goal line off|trips|bunch|spread|ace|strong close|weak close"
    r"|\bhb\b|\bpa\b|play action|read option|inside zone|outside zone|zone toss"
    r"|counter|\biso\b|toss|sweep|dagger|flood|mesh|\bdrive\b|wheel|slant|\bdig\b",
    re.I)
# Terms that only appear in DEFENSIVE menus.
DEF_PAT = re.compile(
    r"cover\s*[0-9]|cover\s*(one|two|three|four|six)|blitz|robber|palms|tampa"
    r"|nickel|dollar|dime\b|3-4|4-3|4-2-5|3-3-5|425|335|man press|press man"
    r"|qb spy|qb contain|engage eight|prevent|goal line def",
    re.I)


def _menu_tiles_text(menu_tiles):
    """v2_menu_tiles is a JSON-array-of-strings column; flatten it to text."""
    s = (menu_tiles or "").strip()
    if not s or s in ("[]", "none", "None"):
        return ""
    try:
        tiles = json.loads(s)
        if isinstance(tiles, list):
            return " | ".join(str(t) for t in tiles)
    except (ValueError, TypeError):
        pass
    return s  # fall back to raw text if it isn't valid JSON


def menu_side(screen_call, menu_tiles, menu_side_field, owner):
    """Classify combined menu text -> owner's side, other side, or ''.

    Input is v2_screen_call + v2_menu_tiles (verbatim menu-tile transcriptions)
    run through the OFF_PAT/DEF_PAT regexes. v2_menu_side (an agent's
    offense/defense read of the visible menu) is used as a tiebreak ONLY when
    both patterns fire on the same text — a genuine internal conflict worth
    resolving with the agent's holistic read of the screen. When NEITHER
    pattern fires there is no football vocabulary on screen at all (recruiting/
    stats/substitution/comparison overlays and similar non-play-call screens
    were common on the UNC-VAND validation game) and v2_menu_side alone was
    measured at 70-74% there — below the lane's 90% accuracy bar — so that
    case abstains rather than guesses. Masked-recovery validation (UNC-VAND):
    pattern-decided plays 94.8%, both-fired tiebreak plays cleared the bar,
    neither-fired-tiebreak dropped -> overall recovered-play accuracy 93%+.
    """
    call = (screen_call or "").strip()
    if call.lower() in ("none", "n/a"):
        call = ""
    text = " | ".join(t for t in (call, _menu_tiles_text(menu_tiles)) if t)
    other = "R" if owner == "L" else "L"
    off = bool(OFF_PAT.search(text))
    de = bool(DEF_PAT.search(text))
    if off and not de:
        return owner
    if de and not off:
        return other
    if not (off and de):
        return ""  # neither pattern fired -> no menu evidence, abstain
    # both fired -> genuine ambiguity, tiebreak on the agent's menu_side judgment
    side = (menu_side_field or "").strip().lower()
    if side == "offense":
        return owner
    if side == "defense":
        return other
    return ""  # tiebreak itself unreadable -> abstain


def continuity_fill(seq, scores, maxgap):
    """Fill blank runs flanked by the same side, gap <= maxgap, no score change."""
    out = list(seq)
    filled = []
    n = len(out)
    i = 0
    while i < n:
        if out[i] == "":
            j = i
            while j < n and out[j] == "":
                j += 1
            ok = (0 < i and j < n and out[i - 1] == out[j]
                  and (j - i) <= maxgap)
            if ok and scores[i - 1] and scores[j]:
                ok = scores[i - 1] == scores[j]
            if ok:
                for k in range(i, j):
                    out[k] = out[i - 1]
                    filled.append(k)
            i = j
        else:
            i += 1
    return out, filled


DD_RE = re.compile(r"^([1-4])&(\d+|GOAL|INCHES)$", re.I)


def parse_dd(dd):
    """Return (down, dist_rank) from a dd string, or None if unreadable
    (blank, KICKOFF/PAT-like, or anything not matching the D&DIST shape).
    dist_rank orders GOAL < INCHES < numeric yards so shrinking distance can
    be compared uniformly; GOAL == GOAL is the only case allowed to repeat
    without strictly shrinking (goal-line downs can stay 'GOAL' to 'GOAL')."""
    m = DD_RE.match((dd or "").strip())
    if not m:
        return None
    down = int(m.group(1))
    dist = m.group(2).upper()
    if dist == "GOAL":
        rank = -1
    elif dist == "INCHES":
        rank = 0
    else:
        rank = int(dist)
    return down, rank


def parse_down(dd):
    """Return just the down number (1-4), or None if unreadable."""
    parsed = parse_dd(dd)
    return parsed[0] if parsed else None


def build_chains(plays, maxgap_seconds=90):
    """Partition play indices into maximal provably-continuous down chains.

    A link between consecutive plays i, i+1 holds only if: both dd values
    are readable; down strictly increments by 1 (down_i+1 == down_i + 1 —
    this alone also enforces "no fresh 1st down", since any reset to 1&10
    fails the +1 test); distance-to-go strictly shrinks (dist_i+1 < dist_i,
    with GOAL->GOAL as the sole allowed repeat) — this is what actually
    rules out a same-down-number turnover artifact (e.g. 1&10 -> 2&10 with
    the distance NOT shrinking is not a normal down progression and must not
    be treated as provably continuous, confirmed against the UNC-VAND ground
    truth: both real flips hiding behind a superficial down+1 pattern had a
    flat, non-shrinking distance); no score change between them; and the
    time gap between windows is <= maxgap_seconds. Breaking a link starts a
    new chain. Returns a list of chain ids, one per play index.
    """
    n = len(plays)
    parsed = [parse_dd(p.get("dd", "")) for p in plays]
    chain_id = [-1] * n
    cid = 0
    i = 0
    while i < n:
        chain_id[i] = cid
        j = i
        while j + 1 < n:
            p1, p2 = parsed[j], parsed[j + 1]
            if p1 is None or p2 is None:
                break
            d1, r1 = p1
            d2, r2 = p2
            if d2 != d1 + 1:
                break
            if not (r2 < r1 or (r1 == -1 and r2 == -1)):
                break
            sl1, sr1 = plays[j].get("score_l", ""), plays[j].get("score_r", "")
            sl2, sr2 = plays[j + 1].get("score_l", ""), plays[j + 1].get("score_r", "")
            if sl1 and sr1 and sl2 and sr2 and (sl1, sr1) != (sl2, sr2):
                break
            try:
                gap = float(plays[j + 1]["t_first"]) - float(plays[j]["t_last"])
            except (KeyError, ValueError):
                break
            if gap > maxgap_seconds:
                break
            j += 1
            chain_id[j] = cid
        i = j + 1
        cid += 1
    return chain_id


def chain_fill(plays, src):
    """Propagate a measured/menu possession value across blank windows that
    share a provably-continuous down chain (build_chains) with a decided
    (src == colour or menu) window. Returns the list of filled indices."""
    chain_id = build_chains(plays)
    groups = {}
    for idx, cid in enumerate(chain_id):
        groups.setdefault(cid, []).append(idx)

    filled = []
    for idx_list in groups.values():
        if len(idx_list) < 2:
            continue
        decided = {plays[i]["poss"] for i in idx_list
                   if plays[i]["poss"] and src[i] in ("colour", "menu")}
        if len(decided) != 1:
            if len(decided) > 1:
                ns = [plays[i]["n"] for i in idx_list]
                print(f"  chain-lane CONTRADICTION in chain n={ns}: "
                      f"decided values {decided} — skipping propagation")
            continue
        value = next(iter(decided))
        for i in idx_list:
            if not plays[i]["poss"]:
                plays[i]["poss"] = value
                src[i] = "chain"
                filled.append(i)
    return filled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gamedir")
    ap.add_argument("owner", choices=["L", "R"])
    ap.add_argument("--maxgap", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plays_csv = os.path.join(args.gamedir, "seg", "plays.csv")
    chart_csv = os.path.join(args.gamedir, "plays_charted.csv")
    plays = list(csv.DictReader(open(plays_csv)))

    # Menu input comes from the chart (vision agents fill v2_screen_call,
    # v2_menu_tiles, v2_menu_side).
    menu_inputs = {}
    chart = []
    if os.path.exists(chart_csv):
        chart = list(csv.DictReader(open(chart_csv)))
        menu_inputs = {r["n"]: (r.get("v2_screen_call", ""),
                                 r.get("v2_menu_tiles", ""),
                                 r.get("v2_menu_side", "")) for r in chart}

    def menu_for(n):
        call, tiles, side = menu_inputs.get(n, ("", "", ""))
        return menu_side(call, tiles, side, args.owner)

    src = ["colour" if p["poss"] else "" for p in plays]
    n_blank = sum(1 for p in plays if not p["poss"])

    # Sanity gate: menu lane must agree with the colour lane where both decide.
    agree = dis = 0
    for p in plays:
        m = menu_for(p["n"])
        if m and p["poss"]:
            if m == p["poss"]:
                agree += 1
            else:
                dis += 1
                call, tiles, side = menu_inputs.get(p["n"], ("", "", ""))
                print(f"  menu/colour DISAGREE n={p['n']}: colour={p['poss']} "
                      f"menu={m} call={call[:60]!r} side={side!r}")
    total = agree + dis
    print(f"menu-lane sanity: {agree}/{total} agreement with colour lane")
    if total >= 10 and dis / total > 0.1:
        sys.exit("ABORT: menu lane disagrees with colour lane >10% — do not "
                 "trust it on this film. Inspect the disagreements above.")

    n_menu = 0
    for idx, p in enumerate(plays):
        if not p["poss"]:
            m = menu_for(p["n"])
            if m:
                p["poss"] = m
                src[idx] = "menu"
                n_menu += 1

    seq = [p["poss"] for p in plays]
    scores = [f"{p['score_l']}-{p['score_r']}"
              if p["score_l"] and p["score_r"] else "" for p in plays]
    seq, filled = continuity_fill(seq, scores, args.maxgap)
    for idx in filled:
        plays[idx]["poss"] = seq[idx]
        src[idx] = "fill"

    n_chain_filled = chain_fill(plays, src)

    still = sum(1 for p in plays if not p["poss"])
    print(f"blanks {n_blank} -> {still}  (menu {n_menu}, fill {len(filled)}, "
          f"chain {len(n_chain_filled)}, "
          f"decided {len(plays) - still}/{len(plays)} = "
          f"{(len(plays) - still) / len(plays):.0%})")

    if args.dry_run:
        return

    fields = list(plays[0].keys())
    if "poss_src" not in fields:
        fields.append("poss_src")
    for idx, p in enumerate(plays):
        p["poss_src"] = src[idx]
    with open(plays_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(plays)

    if chart:
        by_n = {p["n"]: p for p in plays}
        cf = list(chart[0].keys())
        if "poss_src" not in cf:
            cf.append("poss_src")
        for r in chart:
            p = by_n.get(r["n"])
            if p:
                r["poss"] = p["poss"]
                r["poss_src"] = p["poss_src"]
            else:
                r.setdefault("poss_src", "colour" if r.get("poss") else "")
        with open(chart_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cf)
            w.writeheader()
            w.writerows(chart)
    print("written: seg/plays.csv" + (" + plays_charted.csv" if chart else ""))


if __name__ == "__main__":
    main()
