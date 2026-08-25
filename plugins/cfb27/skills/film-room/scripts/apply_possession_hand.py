#!/usr/bin/env python3
"""Apply a complete, human-reviewed Lane B possession map.

Usage: apply_possession_hand.py GAMEDIR MAP.json [MAP.json ...] [--dry-run]

Every play in seg/plays.csv must appear exactly once across the supplied maps.
Live plays use L or R; deliberately identified non-play windows use an empty
value.  The script updates seg/plays.csv and plays_charted.csv atomically and
marks the provenance as ``hand`` or ``hand_non_play``.
"""
import argparse
import csv
import json
import os
import tempfile
from pathlib import Path


def load_map(paths):
    mapped = {}
    for path in paths:
        data = json.loads(Path(path).read_text())
        if not isinstance(data, list):
            raise ValueError(f"{path}: expected a JSON list")
        for item in data:
            n = int(item["n"])
            poss = item.get("poss", "")
            if poss not in ("L", "R", ""):
                raise ValueError(f"{path}: play {n} has invalid poss {poss!r}")
            if n in mapped:
                raise ValueError(f"duplicate play {n} across hand maps")
            mapped[n] = poss
    return mapped


def read_csv(path):
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader), list(reader.fieldnames or [])


def write_csv_atomic(path, rows, fields):
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def apply(game_dir, map_paths, dry_run=False):
    game = Path(game_dir)
    seg_path = game / "seg" / "plays.csv"
    if not seg_path.exists():
        raise ValueError(f"missing {seg_path}")
    mapped = load_map(map_paths)
    seg_rows, seg_fields = read_csv(seg_path)
    expected = {int(row["n"]) for row in seg_rows}
    if set(mapped) != expected:
        missing = sorted(expected - set(mapped))
        extra = sorted(set(mapped) - expected)
        raise ValueError(f"hand map must cover every play; missing={missing} extra={extra}")

    targets = [(seg_path, seg_rows, seg_fields)]
    chart_path = game / "plays_charted.csv"
    if chart_path.exists():
        chart_rows, chart_fields = read_csv(chart_path)
        chart_ns = {int(row["n"]) for row in chart_rows}
        if chart_ns != expected:
            raise ValueError("plays_charted.csv play numbers do not match seg/plays.csv")
        targets.append((chart_path, chart_rows, chart_fields))

    for _, rows, fields in targets:
        if "poss_src" not in fields:
            fields.insert(fields.index("poss") + 1, "poss_src")
        for row in rows:
            poss = mapped[int(row["n"])]
            row["poss"] = poss
            row["poss_src"] = "hand" if poss else "hand_non_play"

    if not dry_run:
        for path, rows, fields in targets:
            write_csv_atomic(path, rows, fields)
    live = sum(bool(v) for v in mapped.values())
    print(f"hand possession: {live}/{len(mapped)} live plays; "
          f"{len(mapped) - live} non-play windows; dry_run={dry_run}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("gamedir")
    parser.add_argument("maps", nargs="+")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        apply(args.gamedir, args.maps, args.dry_run)
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
