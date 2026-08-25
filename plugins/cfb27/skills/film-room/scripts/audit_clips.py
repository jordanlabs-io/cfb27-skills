#!/usr/bin/env python3
"""Completeness audit of clip windows vs independent channels.
Checks per game:
  1. down-sequence gaps  (same possession, down jumps by >1 -> missed play between)
  2. score events outside any clip window  (HUD score change not covered)
  3. large time gaps between consecutive windows (holes; halftime shows up too)
  4. transcript kick/punt/FG mentions not covered by any window (special teams blindness)
Read-only. Prints a report; writes audit_gaps.json per game dir.
"""
import csv, json, os, re, sys
from collections import Counter

BASE = "/Users/elijah/CFB27-film"
GAMES = [
    ("2026-unc-vs-west-virginia", "seg/plays.csv"),
    ("2026-unc-vs-maryland", "seg/plays.csv"),
    ("2026-unc-vs-baylor", "seg/plays.csv"),
    ("2026-unc-vs-northwestern", "seg/plays.csv"),
    ("2026-unc-vs-arizona", "seg/plays_gemini.csv"),
]
KICK_WORDS = re.compile(r"\b(kick(s|ed|off)?s?\s*(off|it away)?|kickoff|punt(s|ed|ing)?|field goal|onside|touchback|fair catch)\b", re.I)
PAD_PRE, PAD_POST = 3, 12   # window tolerance in seconds


def load_windows(gdir, segname):
    wins = []
    for r in csv.DictReader(open(f"{gdir}/{segname}")):
        try:
            wins.append((int(r["n"]), float(r["t_first"]), float(r["t_last"]),
                         r.get("dd", ""), r.get("poss", ""), r.get("qtr", "")))
        except (ValueError, KeyError):
            pass
    return sorted(wins, key=lambda w: w[1])


def covered(t, wins):
    return any(a - PAD_PRE <= t <= b + PAD_POST for _, a, b, *_ in wins)


def down_gaps(wins):
    """Same-possession down jumps >1 (2nd -> 4th means a missed 3rd down)."""
    gaps = []
    prev = None
    for w in wins:
        n, a, b, dd, poss, qtr = w
        m = re.match(r"(\d)\s*&", dd or "")
        if not m:
            prev = None
            continue
        down = int(m.group(1))
        if prev:
            pn, pdown, pposs, pb = prev
            if poss == pposs and down > pdown + 1 and a - pb < 300:
                gaps.append({"between": [pn, n], "downs": f"{pdown}->{down}",
                             "t_range": [round(pb), round(a)]})
        prev = (n, down, poss, b)
    return gaps


def score_events(gdir):
    """Consensus score changes from hud_timeline: value must persist 3 consecutive readable rows."""
    events = []
    cur = None          # confirmed (l, r)
    cand, streak, t0 = None, 0, None
    for r in csv.DictReader(open(f"{gdir}/seg/hud_timeline.csv")):
        l, rt = r.get("score_l", ""), r.get("score_r", "")
        if not (l.isdigit() and rt.isdigit()):
            continue
        v = (int(l), int(rt))
        if v == cand:
            streak += 1
        else:
            cand, streak, t0 = v, 1, float(r["t"])
        if streak >= 3 and v != cur:
            # ignore OCR nonsense: scores never decrease, single-team jumps <= 8
            if cur is None or (v[0] >= cur[0] and v[1] >= cur[1]
                               and (v[0] - cur[0]) + (v[1] - cur[1]) <= 8
                               and (v[0] - cur[0] == 0 or v[1] - cur[1] == 0)):
                if cur is not None:
                    events.append({"t": t0, "from": list(cur), "to": list(v)})
                cur = v
    return events


def time_gaps(wins, thresh=180):
    out = []
    for i in range(1, len(wins)):
        gap = wins[i][1] - wins[i - 1][2]
        if gap > thresh:
            out.append({"between": [wins[i - 1][0], wins[i][0]],
                        "gap_s": round(gap), "t_range": [round(wins[i - 1][2]), round(wins[i][1])]})
    return out


def kick_mentions(gdir, wins):
    transcript = f"{gdir}/transcript.json"
    if not os.path.exists(transcript):
        return 0, []
    segs = json.load(open(transcript))
    if isinstance(segs, dict):
        segs = segs["segments"]
    missed, hits = [], 0
    for s in segs:
        if KICK_WORDS.search(s["text"]):
            # announcers narrate ~0-18s after the snap; accept coverage up to 18s back
            if any(a - PAD_PRE <= s["start"] <= b + 18 for _, a, b, *_ in wins):
                hits += 1
            else:
                missed.append({"t": round(s["start"]), "text": s["text"][:90]})
    # collapse mentions within 30s of each other into one event
    events, last = [], -999
    for m in missed:
        if m["t"] - last > 30:
            events.append(m)
        last = m["t"]
    return hits, events


def main():
    games = GAMES
    if len(sys.argv) > 1:
        games = [(slug, "seg/plays_gemini.csv"
                  if __import__("os").path.exists(f"{BASE}/{slug}/seg/plays_gemini.csv")
                  else "seg/plays.csv") for slug in sys.argv[1:]]
    for slug, segname in games:
        gdir = f"{BASE}/{slug}"
        wins = load_windows(gdir, segname)
        dg = down_gaps(wins)
        se = score_events(gdir)
        se_missed = [e for e in se if not covered(e["t"], wins)]
        tg = time_gaps(wins)
        khits, kmissed = kick_mentions(gdir, wins)
        report = {"windows": len(wins), "down_gaps": dg,
                  "score_events": len(se), "score_events_uncovered": se_missed,
                  "time_gaps_over_3min": tg,
                  "kick_mentions_covered": khits, "kick_events_uncovered": kmissed}
        json.dump(report, open(f"{gdir}/audit_gaps.json", "w"), indent=1)
        print(f"\n=== {slug}  ({len(wins)} windows)")
        print(f"  down-sequence gaps: {len(dg)}" + (f"  {dg[:6]}" if dg else ""))
        print(f"  score events: {len(se)}, uncovered: {len(se_missed)}" + (f"  {se_missed[:4]}" if se_missed else ""))
        print(f"  >3min holes: {len(tg)}" + (f"  {tg[:4]}" if tg else ""))
        print(f"  kick/punt/FG mentions covered: {khits}, uncovered events: {len(kmissed)}")
        for m in kmissed[:8]:
            print(f"    t={m['t']}s  \"{m['text']}\"")


if __name__ == "__main__":
    main()
