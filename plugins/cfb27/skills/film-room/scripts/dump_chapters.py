#!/usr/bin/env python3
"""Merge tier-1 classification shards into chapters.json (see references/data-dump.md).

Usage:
  dump_chapters.py <shard-dir> <chapters.json> [--strict]

Tier-1 agents each write <shard-dir>/out_NN.json. This merges them in frame order,
validates, and prints the per-category counts that seed the capture's coverage ledger.

Two things it fixes rather than trusts, because both were observed in the wild:

1. **Shard shape.** Agents emit either a JSON array or newline-delimited objects
   (JSONL). Both are accepted; the shape is reported. A strict array-only parser
   silently lost 30 of the 2027-w9 capture's 719 classified frames.
2. **`sec` / `ts`.** These are DERIVED from the filename, never taken from the agent.
   `f_0720.jpg` is ffmpeg frame 720 = second 719. Agents routinely write sec=720.
   The filename is deterministic; the agent's arithmetic is not.

NOTE: tier-1 classification is a *reporting* pass, not the coverage contract. It may
cover fewer frames than the dedup survivor set (in the 2027-w9 capture it covered 719 of
1,552). Never gate coverage on chapters.json — gate on the `.keep` file, via
dump_reconcile.py.
"""
import sys, os, json, glob, re

CATEGORIES = {
    "schedule", "team_stats", "player_card", "roster", "depth_chart", "coach_stats",
    "coaching_staff", "standings", "rankings", "recruiting_board", "recruit_card",
    "transfer_portal", "nil", "facilities", "records_awards", "trophy_case",
    "school_info", "dynasty_home", "scores_schedule_league", "menu_nav",
    "loading_transition", "gameplay", "other",
}
REQUIRED = {"frame", "screen_title", "screen_category", "context_chips",
            "has_table", "visible_rows", "readable", "notable"}


def parse_shard(path):
    """Return (rows, shape). Accepts a JSON array or concatenated/newline-delimited objects."""
    txt = open(path).read().strip()
    if not txt:
        return [], "empty"
    try:
        d = json.loads(txt)
        if isinstance(d, list):
            return d, "array"
        if isinstance(d, dict):
            return [d], "single-object"
    except json.JSONDecodeError:
        pass
    dec, i, rows = json.JSONDecoder(), 0, []
    while i < len(txt):
        while i < len(txt) and txt[i] in " \n\r\t,":
            i += 1
        if i >= len(txt):
            break
        obj, i = dec.raw_decode(txt, i)
        rows.extend(obj if isinstance(obj, list) else [obj])
    return rows, "jsonl"


def sec_of(frame):
    m = re.search(r"f_(\d+)", frame)
    if not m:
        return None
    return int(m.group(1)) - 1          # ffmpeg frame 1 = second 0


def main(shard_dir, out, strict=False):
    shards = sorted(glob.glob(os.path.join(shard_dir, "out_*.json")))
    if not shards:
        sys.exit(f"ERROR: no out_*.json in {shard_dir}")

    rows, problems, shapes, seen, resec = [], [], {}, set(), 0
    for p in shards:
        base = os.path.basename(p)
        try:
            data, shape = parse_shard(p)
        except Exception as e:
            problems.append(f"{base}: unparseable ({e})")
            continue
        shapes[shape] = shapes.get(shape, 0) + 1
        for r in data:
            missing = REQUIRED - set(r)
            if missing:
                problems.append(f"{base} {r.get('frame','?')}: missing {sorted(missing)}")
                continue
            if r["screen_category"] not in CATEGORIES:
                problems.append(f"{base} {r['frame']}: bad category {r['screen_category']!r}")
                continue
            if r["frame"] in seen:
                problems.append(f"{r['frame']}: classified twice (overlapping batches)")
                continue
            s = sec_of(r["frame"])
            if s is None:
                problems.append(f"{base} {r['frame']!r}: filename has no frame number")
                continue
            if r.get("sec") != s:
                resec += 1
            r["sec"], r["ts"] = s, f"{s//60:02d}:{s%60:02d}"
            seen.add(r["frame"])
            rows.append(r)

    rows.sort(key=lambda r: r["sec"])
    json.dump(rows, open(out, "w"), indent=1)

    counts = {}
    for r in rows:
        counts[r["screen_category"]] = counts.get(r["screen_category"], 0) + 1
    shape_s = ", ".join(f"{k}={v}" for k, v in sorted(shapes.items()))
    print(f"{len(shards)} shards ({shape_s}) -> {len(rows)} frames classified -> {out}")
    for c, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {c:24} {n}")
    unread = sum(1 for r in rows if not r["readable"])
    if unread:
        print(f"  ({unread} marked readable:false — mid-transition or blurred)")
    if resec:
        print(f"  ({resec} frames had sec/ts corrected from the filename)")

    if problems:
        print(f"\n{len(problems)} problem(s):", file=sys.stderr)
        for p in problems[:40]:
            print("  " + p, file=sys.stderr)
        if strict:
            sys.exit(1)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) != 2:
        sys.exit(__doc__)
    main(a[0], a[1], "--strict" in sys.argv)
