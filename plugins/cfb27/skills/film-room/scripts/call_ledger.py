#!/usr/bin/env python3
"""Per-player call-sheet ledger — cumulative menu counters across films.

The usage counters on play-call tiles are the USER'S ALL-TIME call totals
(at minimum multi-season / dynasty-scope — user ruling 2026-08-13), so each
film is a point-in-time snapshot of that coach's lifetime call sheet. Tracking
snapshots per player makes the deltas meaningful: delta between two films =
calls made in the interval, including games we never saw.

Rebuilds the ledger deterministically from every menu_book.csv given:

  call_ledger.py OUT_DIR GAMEDIR [GAMEDIR ...]

Writes OUT_DIR/<team-slug>.csv (long format, one row per film x play):
  film,owner,play,tag,calls,avg_yds,starred,sightings
sorted by play then film so consecutive rows of a play show its counter
history. Films are ordered by slug (they start with the season year).

The FILE is named from the team slug, never from the raw `owner` string
transcribed off the in-game menu — that string varies between films ("UNC" vs
"NORTH CAROLINA", "VAND" vs "Vanderbilt") and once split a coach's counter
history across two ledgers. The raw string is still written to the `owner`
column so provenance survives.
"""
import csv
import os
import re
import sys


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# In-game menus abbreviate school names inconsistently between films. Only
# irreducible abbreviations belong here (ones no rule could derive); a wrong
# entry silently merges two coaches' counter histories, so add by hand after
# eyeballing the menu, never by guessing. Keys are slugify()'d owner strings.
OWNER_ALIASES = {
    "unc": "north-carolina",
    "vand": "vanderbilt",
    "vandy": "vanderbilt",
    "wvu": "west-virginia",
    "ksu": "kansas-state",
    "k-state": "kansas-state",
    "ari": "arizona",
    "ncst": "nc-state",
    "nw": "northwestern",
}


def known_team_slugs(out_dir):
    """Team slugs for this dynasty, read from <dynasty>/league/teams/*.md
    (out_dir is <dynasty>/film-room/call-sheets). Used only to warn about an
    owner string that resolved to something the league does not contain."""
    dynasty = os.path.dirname(os.path.dirname(os.path.abspath(out_dir)))
    teams_dir = os.path.join(dynasty, "league", "teams")
    slugs = set()
    for name in os.listdir(teams_dir) if os.path.isdir(teams_dir) else []:
        if name.endswith(".md"):
            slugs.add(slugify(name[:-3]))
        elif os.path.isdir(os.path.join(teams_dir, name)):
            slugs.add(slugify(name))
    return slugs


def team_slug(owner, known):
    """Canonical ledger key for a transcribed menu `owner` string."""
    s = slugify(owner)
    s = OWNER_ALIASES.get(s, s)
    if known and s not in known:
        print(f"WARNING: owner {owner!r} -> '{s}', which is not a team in "
              f"league/teams/. Its ledger may be a duplicate under another "
              f"name; add an OWNER_ALIASES entry in call_ledger.py if so.")
    return s


def normalise_plays(rows):
    """Tile-name normalisation (flagged on Maryland + Northwestern reports):
    the same tile can be transcribed with and without a leading team/package
    token ('NICKEL 3-3 CUB COVER 3 BUZZ' vs 'UNC NICKEL 3-3 CUB COVER 3 BUZZ'),
    double-booking its counter history. Within one owner's ledger, when
    dropping a play name's first word yields another play name that exists,
    fold the longer name onto the shorter (the un-prefixed form). Whitespace
    and case are canonicalised first. Counters are never altered — only the
    play KEY they file under."""
    canon = {}
    for r in rows:
        key = re.sub(r"\s+", " ", (r["play"] or "").strip().upper())
        r["play"] = key
        canon[key] = True
    folded = 0
    for r in rows:
        parts = r["play"].split(" ", 1)
        if len(parts) == 2 and parts[1] in canon:
            r["play"] = parts[1]
            folded += 1
    return folded


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)

    known = known_team_slugs(out_dir)
    ledgers = {}  # team-slug -> list of rows
    for gamedir in sys.argv[2:]:
        mb = os.path.join(gamedir, "menu_book.csv")
        if not os.path.exists(mb):
            print(f"skip (no menu_book.csv): {gamedir}")
            continue
        film = os.path.basename(os.path.normpath(gamedir))
        for r in csv.DictReader(open(mb)):
            ledgers.setdefault(team_slug(r["owner"], known), []).append({
                "film": film, "owner": r["owner"], "play": r["play"],
                "tag": r.get("tag", ""), "calls": r.get("max_calls", ""),
                "avg_yds": r.get("avg_yds_at_max", ""),
                "starred": r.get("starred", ""),
                "sightings": r.get("sightings", ""),
            })

    fields = ["film", "owner", "play", "tag", "calls", "avg_yds",
              "starred", "sightings"]
    for team, rows in sorted(ledgers.items()):
        folded = normalise_plays(rows)
        if folded:
            print(f"[{team}] folded {folded} team-prefixed tile name(s)")
        rows.sort(key=lambda r: (r["play"], r["film"]))
        path = os.path.join(out_dir, f"{team}.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        films = sorted({r["film"] for r in rows})
        print(f"{path}: {len(rows)} rows, {len(films)} film(s)")
        # Counter history for plays seen in more than one film = the deltas.
        by_play = {}
        for r in rows:
            by_play.setdefault(r["play"], []).append(r)
        multi = {p: rs for p, rs in by_play.items() if len(rs) > 1}
        for p, rs in sorted(multi.items()):
            hist = " -> ".join(f"{r['calls']} ({r['film'][:4]})" for r in rs)
            print(f"  delta {p}: {hist}")


if __name__ == "__main__":
    main()
