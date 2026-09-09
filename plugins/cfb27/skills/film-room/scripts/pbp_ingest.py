#!/usr/bin/env python3
"""Stage 3b: postgame play-by-play ground truth (PLAN-snap-anchoring.md A8).

Input: a menu-intel JSONL of ingested postgame HIGHLIGHTS screens (Lane C
menu_ingest.py shape: one JSON object per screen, `type":"scoring-summary"`
records carry `content.highlights[]` = [{time, rating, highlight}, ...]).
The postgame HIGHLIGHTS screen is a scrollable list; each screen is scrolled
a few rows further than the last, so the same highlight rows commonly repeat
across consecutive screens (see `notes: "duplicate_of ..."` in the source).

This dedupes by (time, highlight text) exact match, infers a quarter number
from clock monotonicity (the highlight `time` counts DOWN within a quarter;
an increase after a decrease means a new quarter started), and parses each
highlight's free text into dd/spot/carrier/play_type/result/yards/scoring.

Output: GAMEDIR/seg/pbp.csv with columns:
  time, qtr, dd, spot, carrier, text, play_type, result, yards, scoring

Usage: pbp_ingest.py GAMEDIR --highlights JSONL
"""
import argparse
import csv
import json
import os
import re

TIME_RE = re.compile(r"^(\d+):(\d{2})$")
DD_SPOT_RE = re.compile(
    r"^(?P<dd>\d(?:st|nd|rd|th)\s*&\s*(?:\d+|Goal))\s+on\s+(?P<spot>[A-Z]+\s*\d+)\.\s*(?P<rest>.*)$",
    re.I)
KICKOFF_RE = re.compile(r"^Kickoff\s+on\s+(?P<spot>[A-Z]+\s*\d+)\.\s*(?P<rest>.*)$", re.I)
YARDS_RE = re.compile(r"(-?\d+)\s*yard", re.I)
SACK_RE = re.compile(r"sacked", re.I)
FUMBLE_RE = re.compile(r"fumble", re.I)
INT_RE = re.compile(r"intercept", re.I)
PENALTY_RE = re.compile(r"penalty", re.I)
PASS_RE = re.compile(r"pass (?:to|knocked|incomplete|broken)", re.I)
RUSH_RE = re.compile(r"\brush\b", re.I)
PUNT_RE = re.compile(r"\bpunt\b", re.I)


def time_to_secs(t):
    m = TIME_RE.match(t)
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def classify(text):
    if FUMBLE_RE.search(text):
        return "fumble"
    if INT_RE.search(text):
        return "interception"
    if SACK_RE.search(text):
        return "sack"
    if PENALTY_RE.search(text):
        return "penalty"
    if PUNT_RE.search(text):
        return "punt"
    if PASS_RE.search(text):
        return "pass"
    if RUSH_RE.search(text):
        return "rush"
    return "other"


def parse_highlight(text):
    """-> dict with dd/spot/carrier/play_type/result/yards/scoring, best-effort."""
    row = {"dd": "", "spot": "", "carrier": "", "play_type": "",
           "result": "", "yards": "", "scoring": ""}
    m = DD_SPOT_RE.match(text)
    if m:
        row["dd"] = re.sub(r"\s+", " ", m.group("dd")).strip()
        row["spot"] = re.sub(r"\s+", " ", m.group("spot")).strip()
        rest = m.group("rest")
    else:
        mk = KICKOFF_RE.match(text)
        if mk:
            row["dd"] = "KICKOFF"
            row["spot"] = re.sub(r"\s+", " ", mk.group("spot")).strip()
            rest = mk.group("rest")
        else:
            rest = text
    row["play_type"] = classify(rest)
    ym = YARDS_RE.search(rest)
    if ym:
        row["yards"] = ym.group(1)
    if row["play_type"] in ("pass", "rush"):
        pm = re.match(r"(?:.*pass to |^)(?P<name>[A-Z][a-zA-Z' -]+?)\s+for\s+-?\d+\s*yard",
                      rest)
        if pm:
            row["carrier"] = pm.group("name").strip()
        else:
            pm2 = re.match(r"-?\d+\s*yard\s+(?:rush|reception)\s+by\s+(?P<name>[A-Z][a-zA-Z' -]+)",
                            rest)
            if pm2:
                row["carrier"] = pm2.group("name").strip()
    if re.search(r"touchdown|touchback", rest, re.I):
        row["scoring"] = "1" if re.search(r"touchdown", rest, re.I) else ""
    row["result"] = rest.strip().rstrip(".")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gamedir")
    ap.add_argument("--highlights", required=True,
                     help="menu-intel JSONL with scoring-summary highlights records")
    args = ap.parse_args()

    seen = set()
    ordered = []   # [(time_str, highlight_text)] in first-seen order
    with open(args.highlights) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "scoring-summary":
                continue
            content = rec.get("content") or {}
            for h in content.get("highlights") or []:
                key = (h.get("time"), h.get("highlight"))
                if key in seen or not h.get("time") or not h.get("highlight"):
                    continue
                seen.add(key)
                ordered.append(h)

    # Quarter inference: time counts DOWN within a quarter (this list is a
    # postgame HIGHLIGHTS reel, not a play-clock -- an increase after having
    # decreased means the reel moved to the next quarter's plays).
    rows = []
    qtr = 1
    prev_secs = None
    for h in ordered:
        secs = time_to_secs(h["time"])
        if secs is not None and prev_secs is not None and secs > prev_secs:
            qtr += 1
        if secs is not None:
            prev_secs = secs
        parsed = parse_highlight(h["highlight"])
        rows.append({"time": h["time"], "qtr": qtr, **parsed,
                     "text": h["highlight"]})

    os.makedirs(os.path.join(args.gamedir, "seg"), exist_ok=True)
    out_path = os.path.join(args.gamedir, "seg", "pbp.csv")
    fieldnames = ["time", "qtr", "dd", "spot", "carrier", "text",
                  "play_type", "result", "yards", "scoring"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"pbp_ingest: {len(rows)} unique highlight rows ({len(ordered)} "
          f"raw entries across the scrolled screens) -> {out_path}")
    qtr_counts = {}
    for r in rows:
        qtr_counts[r["qtr"]] = qtr_counts.get(r["qtr"], 0) + 1
    print(f"  quarter breakdown: {qtr_counts}")


if __name__ == "__main__":
    main()
