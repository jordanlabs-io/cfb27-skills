#!/usr/bin/env python3
"""Situational query engine over the charted play corpus (Phase A of the
"NFL Project Ideas" plan — see /Users/elijah/.claude/plans/
https-docs-google-com-document-d-1hbrcu9-breezy-fox.md, "Pre-flight
amendments" section is authoritative over the earlier Phase A prose).

Reads every dynasties/<slug>/film-room/plays/*.csv, schema-normalizes across
the v1/v2/v3 header variants actually present in this corpus (17 distinct
header tuples observed by column NAME, not order — this loader is
dict-based via csv.DictReader, so header order never matters, only which
columns exist), and answers situational questions a scouting report needs.

Subcommands: disguise, audit-coverage, search, blitz, teams.
Stdlib + csv only. No pandas (matches every sibling script in this dir).

Reuse (per plan): down/distance bucket() and down_dist() lifted from
splits.py; enum/normalise machinery from chart_schema.py; the
"counters/rates never silently drop rows" discipline from call_ledger.py.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chart_schema  # noqa: E402

DEFAULT_DYNASTY_DIR = "/Users/elijah/CFB27/dynasties/north-carolina"

DD_RE = re.compile(r"([1234])&(\d+|GOAL|INCHES)", re.I)


# --------------------------------------------------------------------------
# down/distance helpers (reused from splits.py — same bucket semantics)
# --------------------------------------------------------------------------
def down_dist(dd):
    m = DD_RE.match(dd or "")
    if not m:
        return None, None
    d = m.group(2).upper()
    dist = 1 if d == "INCHES" else (None if d == "GOAL" else int(d))
    return int(m.group(1)), dist


def bucket(dist):
    if dist is None:
        return "goal"
    return "short(1-3)" if dist <= 3 else ("med(4-6)" if dist <= 6 else "long(7+)")


def pct(a, b):
    return f"{a}/{b} ({100*a/b:.0f}%)" if b else "0/0"


# --------------------------------------------------------------------------
# int-or-range parser for v2_rushers / v2_box_count
# --------------------------------------------------------------------------
def parse_int_or_range(s):
    """Returns an int for a clean integer value, or 'unknown' for anything
    else (ranges like '5-9', open-ended '6+', or free-text notes like
    '1 (edge, Vela)'). Never guesses a point value out of a range — a range
    means the charter was uncertain, and query_plays.py should not manufacture
    false precision from that uncertainty."""
    v = (s or "").strip()
    if not v or v.lower() in ("unknown", "n/a", ""):
        return "unknown"
    if re.fullmatch(r"\d+", v):
        return int(v)
    return "unknown"


def is_five_plus(s):
    """True/False/None (unresolvable) for 'rushers >= 5', reading both clean
    ints and simple open ranges ('5-9', '6+') since those ARE resolvable as
    >=5 even though parse_int_or_range calls them 'unknown' for point-value
    purposes."""
    v = (s or "").strip()
    if not v or v.lower() in ("unknown", "n/a"):
        return None
    m = re.match(r"^(\d+)\s*\+?\s*$", v)
    if m:
        return int(m.group(1)) >= 5
    m = re.match(r"^(\d+)\s*-\s*(\d+)", v)
    if m:
        return int(m.group(1)) >= 5  # low end of range decides (conservative)
    return None


# --------------------------------------------------------------------------
# coalescing + family maps
# --------------------------------------------------------------------------
def coalesce(row, base_field, v2_field):
    """Prefer the base (v1/vision-merged) field; fall back to the v2_ lane
    only when base is missing/unknown. Both lanes are the SAME vision read in
    the assembled CSV (v2_ is the raw per-field vision lane the base column
    was merged from) — comment per plan: never average or vote between them,
    base already IS the merge."""
    b = (row.get(base_field) or "").strip()
    if b and b.lower() not in ("", "unknown"):
        return b
    v2 = (row.get(v2_field) or "").strip()
    return v2 if v2 else ""


SHELL_FAMILY = {"0-high": "0-high", "1-high": "1-high", "2-high": "2-high", "3-high": "3-high"}


def shell_family(raw):
    """Normalize a def_shell_pre/v2_def_shell_pre value to a clean family, or
    None when ambiguous/unresolved/n-a (excluded from rate denominators per
    plan amendment #1)."""
    v = (raw or "").strip().lower()
    if v in SHELL_FAMILY:
        return SHELL_FAMILY[v]
    return None  # unknown, n/a, "1-high or 2-high", free-text notes, etc.


COVERAGE_FAMILY = {
    "cover-0": "cover-0", "cover-1": "cover-1", "cover-1-man": "cover-1",
    "cover-2": "cover-2", "cover-2-man": "man", "cover-3": "cover-3",
    "cover-3-match": "cover-3", "cover-3-sky": "cover-3",
    "cover-4": "cover-4", "cover-4-quarters": "cover-4", "cover-6": "cover-6",
}


def coverage_family(raw):
    """Family bucket for a def_coverage value using chart_schema.normalise()
    first (case/spacing fixes only — see NORMALISE additions). Returns None
    for anything off-schema after normalising (leakage) — those are reported
    separately by audit-coverage/disguise, never silently bucketed, per
    amendment #3."""
    norm = chart_schema.normalise("def_coverage", raw)
    if norm in COVERAGE_FAMILY:
        return COVERAGE_FAMILY[norm]
    if norm in ("unknown", "omitted", "", "n/a"):
        return None
    return "OFFSCHEMA"  # a real leakage value distinct from "no data"


# --------------------------------------------------------------------------
# loader
# --------------------------------------------------------------------------
def load_plays(dynasty_dir, team_map=None):
    """Load every film-room/plays/*.csv into a flat list of normalized dict
    rows. Non-play rows (play_type coalesced == 'non-play') are dropped.
    Adds: film (slug), off_team, def_team (via team_map when given, else the
    raw poss code), down, dist, dist_bucket, shell_pre_raw, shell_pre_fam,
    coverage_raw, coverage_fam, def_rotation, rushers, box_count."""
    plays_dir = os.path.join(dynasty_dir, "film-room", "plays")
    rows_out = []
    for path in sorted(glob.glob(os.path.join(plays_dir, "*.csv"))):
        film = os.path.basename(path)[:-4]
        tmap = (team_map or {}).get(film)
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                pt = coalesce(row, "play_type", "v2_play_type").lower()
                if pt == "non-play":
                    continue
                poss = (row.get("poss") or "").strip()
                if tmap:
                    if poss == tmap["team_l"] or poss == "L" or poss.upper() == tmap.get("team_l_code", "\x00"):
                        off, deff = tmap["team_l"], tmap["team_r"]
                    elif poss == tmap["team_r"] or poss == "R" or poss.upper() == tmap.get("team_r_code", "\x00"):
                        off, deff = tmap["team_r"], tmap["team_l"]
                    elif poss.upper() == tmap.get("l_code"):
                        off, deff = tmap["team_l"], tmap["team_r"]
                    elif poss.upper() == tmap.get("r_code"):
                        off, deff = tmap["team_r"], tmap["team_l"]
                    else:
                        off, deff = None, None
                else:
                    off, deff = poss, None
                d, dist = down_dist(row.get("dd"))
                shell_raw = coalesce(row, "def_shell_pre", "v2_def_shell_pre")
                cov_raw = (row.get("def_coverage") or "").strip()
                out = dict(row)
                out.update({
                    "film": film,
                    "off_team": off,
                    "def_team": deff,
                    "play_type_c": pt,
                    "down": d,
                    "dist": dist,
                    "dist_bucket": bucket(dist) if d else None,
                    "shell_pre_raw": shell_raw,
                    "shell_pre_fam": shell_family(shell_raw),
                    "shell_initial_raw": coalesce(row, "def_shell_initial", "v2_def_shell_initial"),
                    "coverage_raw": cov_raw,
                    "coverage_fam": coverage_family(cov_raw),
                    "def_rotation_c": (row.get("def_rotation") or "").strip().lower(),
                    "rushers": row.get("v2_rushers") or "",
                    "rushers_5plus": is_five_plus(row.get("v2_rushers")),
                    "box_count": row.get("v2_box_count") or "",
                    "confidence_c": (row.get("confidence") or "").strip().lower(),
                    "mz_confidence_c": (row.get("mz_confidence") or "").strip().lower(),
                    "def_coverage_src_c": (row.get("def_coverage_src") or "").strip().lower(),
                    "man_zone_verdict_c": (row.get("man_zone_verdict") or "").strip().lower(),
                    "v2_src_c": (row.get("v2_src") or "").strip(),
                })
                rows_out.append(out)
    return rows_out


def score_state(row):
    """trailing/tied/leading for the offense on this snap, from 'score'
    (format 'A-B') and poss side; returns None when unreadable."""
    sc = (row.get("score") or "").strip()
    m = re.match(r"^(-?\d+)\s*-\s*(-?\d+)$", sc)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    poss = (row.get("poss") or "").strip()
    # score is L-R by scorebug convention throughout this corpus
    if poss in ("L",) or poss == row.get("_l_code"):
        mine, theirs = a, b
    elif poss in ("R",) or poss == row.get("_r_code"):
        mine, theirs = b, a
    else:
        return None
    if mine == theirs:
        return "tied"
    return "trailing" if mine < theirs else "leading"


def is_red_zone(row):
    dd = (row.get("dd") or "")
    return bool(re.search(r"GOAL", dd, re.I))


# --------------------------------------------------------------------------
# team map (dynasties/<slug>/film-room/plays/_film_teams.csv)
# --------------------------------------------------------------------------
TEAM_SLUGS = {
    "arizona": ["Arizona", "ARI"], "baylor": ["Baylor"], "illinois": ["Illinois"],
    "kansas-state": ["Kansas State", "KSU", "K-State"],
    "maryland": ["Maryland", "UMD"],
    "nc-state": ["NC State", "N.C. State", "North Carolina State"],
    "north-carolina": ["North Carolina", "UNC"],
    "northwestern": ["Northwestern"], "rutgers": ["Rutgers"],
    "vanderbilt": ["Vanderbilt", "Vandy", "VAND"],
    "west-virginia": ["West Virginia", "WVU"],
    "cincinnati": ["Cincinnati"], "arizona-state": ["ASU"],
}
# codes seen used directly in poss on some films
CODE_ALIASES = {"ARI": "arizona", "ARIZ": "arizona", "UNC": "north-carolina"}

_NAME_TO_SLUG = {}
for _slug, _names in TEAM_SLUGS.items():
    _NAME_TO_SLUG[_slug.replace("-", " ").lower()] = _slug
    for _n in _names:
        _NAME_TO_SLUG[_n.lower()] = _slug


def slug_from_token(tok):
    key = tok.replace("-", " ").lower()
    if key in _NAME_TO_SLUG:
        return _NAME_TO_SLUG[key]
    # try stripping a trailing disambiguator ("rutgers-natty", "rutgers-cc")
    parts = tok.split("-")
    for cut in range(len(parts) - 1, 0, -1):
        cand = "-".join(parts[:cut]).replace("-", " ").lower()
        if cand in _NAME_TO_SLUG:
            return _NAME_TO_SLUG[cand]
    return tok


ORIENT_LINE_RE = re.compile(r"\bscorebug\b", re.I)
TEAMS_LINE_RE = re.compile(r"^\s*-?\s*Teams:", re.I)
TEAMS_PATTERN_RE = re.compile(
    r"Teams:\s*(?P<a>[\w .'\-]+?)\s*\(scorebug\s*L\)\s*vs\s*(?P<b>[\w .'\-]+?)\s*\(R\)", re.I)


def find_side(sentence, aliases, word):
    for a in aliases:
        pat = re.compile(re.escape(a) + r"\s*(?:=|\(scorebug|\(|is scorebug)?\s{0,3}\b" + word + r"\b", re.I)
        if pat.search(sentence):
            return True
    return False


def detect_orientation(game_slug, text, team_a, team_b):
    """Returns (team_l, team_r, source_tag) or None if no pattern matched.
    team_a/team_b come from the filename order (<season>-A-vs-B)."""
    lines = [ln for ln in text.splitlines()
             if ORIENT_LINE_RE.search(ln) or TEAMS_LINE_RE.search(ln)]
    for line in lines:
        m = TEAMS_PATTERN_RE.search(line)
        if m:
            a_slug = slug_from_token(m.group("a").strip())
            b_slug = slug_from_token(m.group("b").strip())
            if {a_slug, b_slug} == {team_a, team_b}:
                return a_slug, b_slug, "Teams:(scorebug L)vs(R)"
        s = line.replace("*", "").replace("`", "")
        aliases_a = TEAM_SLUGS.get(team_a, [team_a])
        aliases_b = TEAM_SLUGS.get(team_b, [team_b])
        leftA = find_side(s, aliases_a, "LEFT")
        leftB = find_side(s, aliases_b, "LEFT")
        rightA = find_side(s, aliases_a, "RIGHT")
        rightB = find_side(s, aliases_b, "RIGHT")
        if leftA and not leftB:
            return team_a, team_b, "prose(A=L)"
        if leftB and not leftA:
            return team_b, team_a, "prose(B=L)"
        if rightA and not rightB:
            return team_b, team_a, "prose(A=R)"
        if rightB and not rightA:
            return team_a, team_b, "prose(B=R)"
    return None


def build_team_map(dynasty_dir):
    """Regenerate the team map from games/*.md orientation prose. Returns a
    dict film -> {team_l, team_r, screen_owner, source}."""
    games_dir = os.path.join(dynasty_dir, "film-room", "games")
    plays_dir = os.path.join(dynasty_dir, "film-room", "plays")
    out = {}
    for path in sorted(glob.glob(os.path.join(plays_dir, "*.csv"))):
        film = os.path.basename(path)[:-4]
        m = re.match(r"^\d{4}-(.+)-vs-(.+)$", film)
        if not m:
            out[film] = {"team_l": "unknown", "team_r": "unknown",
                         "screen_owner": "unknown", "source": "UNVERIFIED(no-vs-in-filename)"}
            continue
        team_a, team_b = slug_from_token(m.group(1)), slug_from_token(m.group(2))
        # special-case: this film uses team codes directly in `poss`, not L/R
        if film == "2026-unc-vs-arizona":
            out[film] = {"team_l": "north-carolina", "team_r": "arizona",
                         "screen_owner": "unknown",
                         "source": "SPECIAL(poss=team-codes:UNC/ARIZ)"}
            continue
        md_path = os.path.join(games_dir, film + ".md")
        result = None
        if os.path.exists(md_path):
            text = open(md_path, encoding="utf-8", errors="replace").read()
            result = detect_orientation(film, text, team_a, team_b)
        if result:
            tl, tr, src = result
            out[film] = {"team_l": tl, "team_r": tr, "screen_owner": "unknown", "source": src}
        else:
            out[film] = {"team_l": team_a, "team_r": team_b,
                         "screen_owner": "unknown", "source": "UNVERIFIED(filename-order)"}
    return out


def team_map_path(dynasty_dir):
    return os.path.join(dynasty_dir, "film-room", "plays", "_film_teams.csv")


def write_team_map(dynasty_dir, tmap):
    path = team_map_path(dynasty_dir)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["film", "team_l", "team_r", "screen_owner", "source"])
        for film in sorted(tmap):
            r = tmap[film]
            w.writerow([film, r["team_l"], r["team_r"], r["screen_owner"], r["source"]])
    return path


def read_team_map(dynasty_dir):
    path = team_map_path(dynasty_dir)
    if not os.path.exists(path):
        tmap = build_team_map(dynasty_dir)
        write_team_map(dynasty_dir, tmap)
        return tmap
    out = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            out[row["film"]] = row
    return out


def team_map_for_loader(dynasty_dir):
    """Adapt the on-disk map into the {team_l, team_r, l_code, r_code} shape
    load_plays() expects, with L/R codes for the special poss=team-code film."""
    raw = read_team_map(dynasty_dir)
    out = {}
    for film, r in raw.items():
        out[film] = {
            "team_l": r["team_l"], "team_r": r["team_r"],
            "l_code": "UNC" if r["team_l"] == "north-carolina" and "SPECIAL" in r.get("source", "") else "L",
            "r_code": "ARIZ" if r["team_r"] == "arizona" and "SPECIAL" in r.get("source", "") else "R",
        }
    return out


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------
def filter_rows(rows, args):
    out = []
    for r in rows:
        if args.team and r["off_team"] != args.team and r["def_team"] != args.team:
            continue
        if args.game and r["film"] != args.game:
            continue
        out.append(r)
    return out


def print_md_table(headers, rows):
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        print("| " + " | ".join(str(c) for c in row) + " |")


def cmd_teams(args):
    dynasty_dir = args.dynasty_dir
    tmap = read_team_map(dynasty_dir)
    unverified = [f for f, r in tmap.items() if "UNVERIFIED" in r.get("source", "")]
    if args.json:
        print(json.dumps(tmap, indent=2))
    else:
        print_md_table(["film", "team_l", "team_r", "screen_owner", "source"],
                        [[f, r["team_l"], r["team_r"], r["screen_owner"], r["source"]]
                         for f, r in sorted(tmap.items())])
        print(f"\n{len(unverified)}/{len(tmap)} films UNVERIFIED (filename order used, no orientation prose matched):")
        for f in unverified:
            print(f"  - {f}")
    if args.team:
        used_unverified = [f for f in unverified
                            if tmap[f]["team_l"] == args.team or tmap[f]["team_r"] == args.team]
        if used_unverified:
            print(f"\nERROR: --team {args.team} touches UNVERIFIED films: {used_unverified}", file=sys.stderr)
            sys.exit(1)


def check_team_verified(dynasty_dir, team):
    if not team:
        return
    tmap = read_team_map(dynasty_dir)
    bad = [f for f, r in tmap.items()
           if "UNVERIFIED" in r.get("source", "") and (r["team_l"] == team or r["team_r"] == team)]
    if bad:
        print(f"WARNING: --team {team} includes UNVERIFIED-orientation films (using filename order, "
              f"unverified L/R): {', '.join(bad)}", file=sys.stderr)


def cmd_disguise(args):
    dynasty_dir = args.dynasty_dir
    check_team_verified(dynasty_dir, args.team)
    tmap = team_map_for_loader(dynasty_dir)
    rows = load_plays(dynasty_dir, tmap)
    rows = filter_rows(rows, args)
    # def_team is the coach we're profiling: snaps where def_team is set (an
    # off/def split from the team map) and, if --team given, def_team==team.
    def_rows = [r for r in rows if r["def_team"] and (not args.team or r["def_team"] == args.team)]

    print(f"# Disguise report — {args.team or 'all coaches'} ({len(def_rows)} defensive snaps, "
          f"dynasty={os.path.basename(dynasty_dir)})\n")

    by_coach = defaultdict(list)
    for r in def_rows:
        by_coach[r["def_team"]].append(r)

    for coach, crows in sorted(by_coach.items()):
        print(f"## {coach} — {len(crows)} defensive snaps\n")

        # --- Primary: rotation rate over resolved rows (none + to-*)
        resolved = [r for r in crows if r["def_rotation_c"] in
                    ("none", "to-1-high", "to-2-high", "to-3-high")]
        rotated = [r for r in resolved if r["def_rotation_c"].startswith("to-")]
        print(f"**Rotation rate (primary metric):** "
              f"{pct(len(rotated), len(resolved))} of resolved snaps "
              f"({len(resolved)}/{len(crows)} rows had a readable def_rotation)\n")

        def split_rotation(pred, label):
            groups = defaultdict(lambda: [0, 0])
            for r in resolved:
                key = pred(r)
                if key is None:
                    continue
                groups[key][1] += 1
                if r["def_rotation_c"].startswith("to-"):
                    groups[key][0] += 1
            if not groups:
                return
            print(f"By {label}:")
            for key in sorted(groups):
                rot, tot = groups[key]
                print(f"  - {key}: {pct(rot, tot)}")
            print()

        split_rotation(lambda r: r["down"], "down")
        split_rotation(lambda r: r["dist_bucket"], "distance bucket")
        split_rotation(lambda r: "red-zone" if is_red_zone(r) else "non-red-zone", "red zone")
        split_rotation(lambda r: score_state(r), "score state")

        # --- Secondary: initial->pre shell change rate (within-pre-snap disguise)
        shell_pairs = [(shell_family(r["shell_initial_raw"]), r["shell_pre_fam"]) for r in crows]
        shell_pairs = [(a, b) for a, b in shell_pairs if a and b]
        changed = sum(1 for a, b in shell_pairs if a != b)
        print(f"**Secondary — initial shell -> pre-snap shell change rate:** "
              f"{pct(changed, len(shell_pairs))} ({len(shell_pairs)} rows with both fields readable)\n")

        # --- Tertiary: shell-family -> coverage-family matrix, n-gated,
        # excluding def_coverage_src=derived (circular per amendment #1)
        matrix_rows = [r for r in crows if r["def_coverage_src_c"] != "derived"]
        matrix = defaultdict(Counter)
        resolved_n = 0
        for r in matrix_rows:
            sf, cf = r["shell_pre_fam"], r["coverage_fam"]
            if sf and cf and cf != "OFFSCHEMA":
                matrix[sf][cf] += 1
                resolved_n += 1
        print(f"**Tertiary — shell-family -> coverage-family matrix** "
              f"(resolved {resolved_n}/{len(matrix_rows)}, excludes def_coverage_src=derived, "
              f"min-n={args.min_n} per cell to report a rate):")
        if resolved_n < args.min_n:
            print(f"  (n={resolved_n} below min-n={args.min_n} — table suppressed, not reliable)\n")
        else:
            for sf in sorted(matrix):
                tot = sum(matrix[sf].values())
                if tot < args.min_n:
                    print(f"  - {sf}: n={tot} below min-n, skipped")
                    continue
                parts = ", ".join(f"{cf} {c}/{tot} ({100*c/tot:.0f}%)"
                                   for cf, c in matrix[sf].most_common())
                print(f"  - {sf} (n={tot}): {parts}")
            print()

        # --- Rotation tells conditioned on pre-snap shell
        print("**Rotation tells (def_rotation / def_safeties_post by pre-snap shell family):**")
        by_shell = defaultdict(Counter)
        for r in resolved:
            sf = r["shell_pre_fam"]
            if sf:
                by_shell[sf][r["def_rotation_c"]] += 1
        for sf in sorted(by_shell):
            tot = sum(by_shell[sf].values())
            parts = ", ".join(f"{k} {v}/{tot} ({100*v/tot:.0f}%)" for k, v in by_shell[sf].most_common())
            print(f"  - shows {sf}: {parts}")
        print()

        # --- footer: v2_src era mix
        eras = Counter()
        for r in crows:
            src = r["v2_src_c"] or "unknown"
            # collapse to model+date prefix (strip "+respot" etc suffixes)
            eras[src.split("+")[0]] += 1
        print("**Charting era mix (v2_src) for this coach's snaps:**")
        for era, c in eras.most_common():
            print(f"  - {era}: {c}")
        print()

    if not by_coach:
        print("(no defensive snaps matched — check --team spelling against `query_plays.py teams`)")


def cmd_audit_coverage(args):
    dynasty_dir = args.dynasty_dir
    tmap = team_map_for_loader(dynasty_dir)
    rows = load_plays(dynasty_dir, tmap)
    rows = filter_rows(rows, args)
    gt_rows = [r for r in rows if r["def_coverage_src_c"] == "playart"]
    print(f"# Coverage audit: play-art vs man_zone_verdict proxy — NOT a vision accuracy measurement\n")
    print(f"Ground truth = def_coverage_src=playart rows only. n={len(gt_rows)} "
          f"of {len(rows)} total defensive-eligible rows. See calibration-history.md "
          f"'2026-09-08 — coverage ground truth audit' for why this is a proxy comparison, "
          f"not an independent recognition test.\n")
    if not gt_rows:
        print("(no playart-sourced rows in this selection — nothing to audit)")
        return
    # agreement: family(def_coverage) [play-art] vs family(man_zone_verdict
    # collapsed to man/zone) as the "vision" read, since this corpus doesn't
    # carry a separate vision-only coverage column distinct from def_coverage
    # once merged — the comparison available is coverage family vs the
    # independently-verdicted man/zone read.
    by_family = defaultdict(lambda: [0, 0])
    by_film = defaultdict(lambda: [0, 0])
    for r in gt_rows:
        cf = r["coverage_fam"]
        if not cf or cf == "OFFSCHEMA":
            continue
        expect_mz = "man" if cf in ("cover-1", "cover-0", "man") else "zone"
        got_mz = r["man_zone_verdict_c"]
        if got_mz not in ("man", "zone"):
            continue
        agree = 1 if got_mz == expect_mz else 0
        by_family[cf][0] += agree
        by_family[cf][1] += 1
        by_film[r["film"]][0] += agree
        by_film[r["film"]][1] += 1
    print("Agreement (play-art family implies man/zone vs. charted man_zone_verdict), per family:")
    for fam, (a, t) in sorted(by_family.items()):
        print(f"  - {fam}: {pct(a, t)}")
    print("\nPer film (n shown; small-n films are noise, not signal):")
    for film, (a, t) in sorted(by_film.items()):
        print(f"  - {film}: {pct(a, t)}")
    print("\nReminder: this is play-art vs. man_zone_verdict proxy agreement, not a vision "
          "accuracy measurement — do not report it as one.")


def cmd_search(args):
    dynasty_dir = args.dynasty_dir
    tmap = team_map_for_loader(dynasty_dir)
    rows = load_plays(dynasty_dir, tmap)
    rows = filter_rows(rows, args)

    def keep(r):
        if args.down and r["down"] != args.down:
            return False
        if args.dist_min is not None and (r["dist"] is None or r["dist"] < args.dist_min):
            return False
        if args.dist_max is not None and (r["dist"] is None or r["dist"] > args.dist_max):
            return False
        if args.qtr and (r.get("qtr") or "") != str(args.qtr):
            return False
        ss = score_state(r)
        if args.trailing and ss != "trailing":
            return False
        if args.leading and ss != "leading":
            return False
        if args.tied and ss != "tied":
            return False
        if args.red_zone and not is_red_zone(r):
            return False
        if args.formation and args.formation.lower() not in (coalesce(r, "formation", "v2_off_formation") or "").lower():
            return False
        if args.coverage and args.coverage.lower() not in (r["coverage_raw"] or "").lower():
            return False
        if args.play_type and r["play_type_c"] != args.play_type.lower():
            return False
        if args.side == "off" and not r["off_team"]:
            return False
        if args.side == "def" and not r["def_team"]:
            return False
        if args.side == "off" and args.team and r["off_team"] != args.team:
            return False
        if args.side == "def" and args.team and r["def_team"] != args.team:
            return False
        return True

    matched = [r for r in rows if keep(r)]
    print(f"# Search — {len(matched)} matching rows\n")
    hdrs = ["film", "n", "qtr", "dd", "off", "def", "formation", "play_type", "yards", "coverage"]
    table = []
    for r in matched[:200]:
        table.append([r["film"], r.get("n", ""), r.get("qtr", ""), r.get("dd", ""),
                      r["off_team"] or "?", r["def_team"] or "?",
                      coalesce(r, "formation", "v2_off_formation"), r["play_type_c"],
                      r.get("yards", ""), r["coverage_raw"] or ""])
    print_md_table(hdrs, table)
    if len(matched) > 200:
        print(f"\n(showing first 200 of {len(matched)} rows)")

    runs = sum(1 for r in matched if r["play_type_c"] == "run")
    passes = sum(1 for r in matched if r["play_type_c"] == "pass")
    print(f"\n**Summary:** run {pct(runs, len(matched))}, pass {pct(passes, len(matched))}")
    yards = [float(r["yards"]) for r in matched if (r.get("yards") or "").strip()
             and re.fullmatch(r"-?\d+(\.\d+)?", r["yards"].strip())]
    if yards:
        print(f"Avg yards (numeric rows only, n={len(yards)}): {sum(yards)/len(yards):.1f}")

    def top5(field_fn, label):
        c = Counter(field_fn(r) for r in matched if field_fn(r))
        if not c:
            return
        print(f"\nTop 5 {label}:")
        for val, n in c.most_common(5):
            print(f"  - {val}: {n}")

    top5(lambda r: coalesce(r, "formation", "v2_off_formation"), "formations")
    top5(lambda r: r.get("concept") or "", "concepts")
    top5(lambda r: r["coverage_raw"], "coverages")

    if args.json:
        print("\n```json")
        print(json.dumps([{k: r.get(k) for k in hdrs} for r in matched], indent=2))
        print("```")


def cmd_blitz(args):
    dynasty_dir = args.dynasty_dir
    check_team_verified(dynasty_dir, args.team)
    tmap = team_map_for_loader(dynasty_dir)
    rows = load_plays(dynasty_dir, tmap)
    rows = filter_rows(rows, args)
    def_rows = [r for r in rows if r["def_team"] and (not args.team or r["def_team"] == args.team)]

    print(f"# Blitz report — {args.team or 'all coaches'} ({len(def_rows)} defensive snaps)\n")
    resolved = [r for r in def_rows if r["rushers_5plus"] is not None]
    blitzed = [r for r in resolved if r["rushers_5plus"]]
    print(f"**Overall 5+ rushers rate:** {pct(len(blitzed), len(resolved))} "
          f"({len(resolved)}/{len(def_rows)} rows had a readable rusher count)\n")

    def split(pred, label):
        groups = defaultdict(lambda: [0, 0])
        for r in resolved:
            key = pred(r)
            if key is None:
                continue
            groups[key][1] += 1
            if r["rushers_5plus"]:
                groups[key][0] += 1
        if not groups:
            return
        print(f"By {label}:")
        for key in sorted(groups, key=str):
            b, t = groups[key]
            print(f"  - {key}: {pct(b, t)}")
        print()

    split(lambda r: coalesce(r, "def_front", "v2_def_front") or None, "def_front")
    split(lambda r: r["box_count"] or None, "box_count (raw, includes ranges)")
    split(lambda r: r["down"], "down")
    split(lambda r: r["dist_bucket"], "distance bucket")

    print("**Pre-snap tells preceding 5+ rushers (shell family shown pre-snap):**")
    by_shell = defaultdict(lambda: [0, 0])
    for r in resolved:
        sf = r["shell_pre_fam"]
        if not sf:
            continue
        by_shell[sf][1] += 1
        if r["rushers_5plus"]:
            by_shell[sf][0] += 1
    for sf in sorted(by_shell):
        b, t = by_shell[sf]
        print(f"  - shows {sf} pre-snap: {pct(b, t)} blitzed")


def parse_args():
    # Shared flags live on a parent parser so they work BOTH before and
    # after the subcommand ("query_plays.py disguise --team X" and
    # "query_plays.py --team X disguise" both work) — argparse subparsers
    # don't inherit the top-level parser's own options otherwise.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dynasty-dir", default=DEFAULT_DYNASTY_DIR)
    common.add_argument("--team")
    common.add_argument("--game")
    common.add_argument("--json", action="store_true")
    common.add_argument("--min-n", type=int, default=15)

    p = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("teams", parents=[common])
    sub.add_parser("disguise", parents=[common])
    sub.add_parser("audit-coverage", parents=[common])
    sub.add_parser("blitz", parents=[common])

    sp = sub.add_parser("search", parents=[common])
    sp.add_argument("--down", type=int)
    sp.add_argument("--dist-min", type=int)
    sp.add_argument("--dist-max", type=int)
    sp.add_argument("--qtr", type=int)
    sp.add_argument("--trailing", action="store_true")
    sp.add_argument("--leading", action="store_true")
    sp.add_argument("--tied", action="store_true")
    sp.add_argument("--red-zone", action="store_true")
    sp.add_argument("--formation")
    sp.add_argument("--coverage")
    sp.add_argument("--play-type")
    sp.add_argument("--side", choices=["off", "def"])

    return p.parse_args()


def main():
    args = parse_args()
    for a in ("down", "dist_min", "dist_max", "qtr", "trailing", "leading", "tied",
              "red_zone", "formation", "coverage", "play_type", "side"):
        if not hasattr(args, a):
            setattr(args, a, None if a not in ("trailing", "leading", "tied", "red_zone") else False)
    dispatch = {
        "teams": cmd_teams, "disguise": cmd_disguise, "audit-coverage": cmd_audit_coverage,
        "search": cmd_search, "blitz": cmd_blitz,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
