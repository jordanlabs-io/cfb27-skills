---
name: civil-sync
description: Keep a permanent local copy of the College Football 27 play database from cfblabs.com (offense and defense: category, sub-formation, play name, art URL) and verify playbook or scheme rows against it. Use when a play, formation, or set name must be checked against the real in-game database, when a wiki or playbook page lists plays (for example a Formation and Play Name bullet list) that need confirming, or when the local dump needs refreshing after a patch.
---

# civil-sync — local CFB Labs play DB + play verification

Two scripts in `scripts/`, Python 3 standard library only.

## Refresh the dump

```bash
python3 scripts/dump_cfblabs.py --out-dir ~/CFB27/playbook/db --cache-dir ~/.cache/cfblabs-plays
```

Reads the `/plays` index for every category and set link, then each set page's `__NEXT_DATA__` (play list, side) and page HTML (art URL). Single-threaded, 0.3s delay, retry with backoff, raw pages cached gzip'd in `--cache-dir` (delete the cache to force a full refetch after a patch). Writes `cfblabs-plays.json` (adds an `extra` object) and `cfblabs-plays.csv` (flat fields only), sorted by side, category, set, play name, and prints plays/sets/categories per side. Exits non-zero if any set page failed. Fields: `side, category, set, play_name, play_type, art_url, source_url`. `play_type` is the site's `playType` value (offense/defense); the run/pass tag shown on the site is computed client-side and is not in the data.

## Verify rows against the dump

```bash
python3 scripts/verify_plays.py ROWS.csv --db ~/CFB27/playbook/db/cfblabs-plays.json \
    --category-col category --set-col set --play-col play_name [--side offense] [--out results.csv] [--report-only]
python3 scripts/verify_plays.py --selftest --db ~/CFB27/playbook/db/cfblabs-plays.json
```

Input is CSV or JSON with one row per play. Match is exact on category + set + play name together after normalising case, punctuation, underscores, and whitespace; no fuzzy verdicts. Status per row: `verified`, `name-mismatch` (set exists, play absent; closest 3 names listed), `set-mismatch` (play exists under other sets; listed), `not-in-db`. Writes a results CSV, prints counts, and exits non-zero unless every row is verified (or `--report-only`). Rows must already be split into category and set; a combined "Formation" string (for example "Gun Bunch Open Offset") needs splitting first, and abbreviations such as "Gun" for SHOTGUN are not expanded by the script.
