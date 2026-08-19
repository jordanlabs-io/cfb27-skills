#!/usr/bin/env python3
"""Generate the deterministic skeleton of a scout report (SKILL.md step 9).

Everything re-derivable from plays_charted.csv is generated here — score flow,
tendency digest, pre-snap adjustment splits, the standard caveat/definition
boilerplate — so each game's report starts identical instead of re-written
prose drifting between games. The model fills ONLY the <!-- NARRATIVE --> slots
(scout analysis, "What to fix") and the header facts it alone knows (VOD link,
corrections applied during the ingest).

Usage: report_gen.py GAMEDIR SLUG TEAM_L TEAM_R
Writes GAMEDIR/report_skeleton.md; copy/merge into
dynasties/<dynasty>/film-room/games/<slug>.md.
"""
import csv
import os
import subprocess
import sys
from collections import Counter, defaultdict

GAMEDIR, SLUG, TEAM_L, TEAM_R = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
SCRIPTS = os.path.dirname(os.path.abspath(__file__))

BOILERPLATE = """\
## Reading notes (standard caveats — identical on every report)

- **Tempo**: `hurry-up` < 20s between same-possession snaps, `slow` > 34s, else `normal`.
- **Vision pass-bias**: run/pass comes from vision (authority rule 3) and skews
  pass on ambiguous ghosts; disclosed, never "corrected" by commentary.
- **Possession**: dd-bar colour lane, plus poss_rescue lanes where colour
  abstained — per-play `poss_src` says which. Splits are only as good as the
  "possession decided on X%" line for this film.
- **Conversions** are derived from the NEXT window's down; `undetermined`
  windows leave the denominator (count reported alongside the rate).
- **Menu counters are ALL-TIME call totals** (multi-season) — deltas between
  films = calls made in the interval, including games never filmed.
"""


def load_rows():
    rows = list(csv.DictReader(open(os.path.join(GAMEDIR, "plays_charted.csv"))))
    rows.sort(key=lambda r: int(r["n"]))
    return rows


def score_flow(rows):
    out = ["| Qtr | Clock | Play | Score (L-R) |", "| --- | --- | --- | --- |"]
    last = None
    for r in rows:
        s = (r.get("score") or "").strip()
        parts = s.split("-")
        # only fully-read scores; half-blank pairs ("7-", "-21") are OCR gaps,
        # not score changes
        if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
            continue
        if s != last:
            out.append(f"| {r.get('qtr','?')} | {r.get('clock','?')} | "
                       f"{r['n']} | {s} |")
            last = s
    return "\n".join(out)


def adjustment_splits(rows, side, team):
    poss_values = {side, team}
    off = [r for r in rows if r["poss"] in poss_values
           and (r.get("play_type") or "") in ("run", "pass")]
    if not off:
        return f"_(no charted snaps for {team})_"
    lines = []
    # audible/shift rate by down
    by_down = defaultdict(lambda: [0, 0])
    for r in off:
        d = (r.get("dd") or "")[:1]
        if d.isdigit():
            adj = (r.get("presnap_adjust") or "") in ("audible", "shift")
            by_down[d][0 if adj else 1] += 1
    lines.append("| Down | audible/shift | static | rate |")
    lines.append("| --- | --- | --- | --- |")
    for d in sorted(by_down):
        a, s = by_down[d]
        lines.append(f"| {d} | {a} | {s} | {100*a/(a+s):.0f}% |")
    # initial shell -> post-snap safeties (rotation/disguise structure)
    rot = Counter((r.get("v2_def_shell_initial") or r.get("def_shell_pre") or "?",
                   r.get("def_safeties_post") or "?") for r in off)
    if rot:
        lines.append("")
        lines.append("| Shown (initial/pre) | Safeties post | n |")
        lines.append("| --- | --- | --- |")
        for (shell, post), c in rot.most_common(10):
            lines.append(f"| {shell} | {post} | {c} |")
    # disguise rate from postsnap_confirms, when charted
    pc = Counter(r.get("v2_postsnap_confirms") or "" for r in off)
    seen = pc.get("yes", 0) + pc.get("partial", 0) + pc.get("no", 0)
    if seen:
        lines.append("")
        lines.append(f"Disguise rate (postsnap_confirms=no): "
                     f"{pc.get('no',0)}/{seen} ({100*pc.get('no',0)/seen:.0f}%) "
                     f"— partial {pc.get('partial',0)}, confirmed {pc.get('yes',0)}")
    return "\n".join(lines)


def main():
    rows = load_rows()
    digest = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "splits.py"), GAMEDIR, TEAM_L, TEAM_R],
        capture_output=True, text=True).stdout
    charted = sum(1 for r in rows if (r.get("play_type") or "") in ("run", "pass"))
    poss_dec = sum(1 for r in rows if (r.get("poss") or "").strip())

    md = [f"# {SLUG} — scout report",
          "",
          f"- Teams: {TEAM_L} (scorebug L) vs {TEAM_R} (R)",
          f"- Windows: {len(rows)} · charted run/pass: {charted} · "
          f"possession attributed: {poss_dec}/{len(rows)}",
          "- Source/VOD: <!-- NARRATIVE: link + lane + final score confirmed "
          "against the postgame screen -->",
          "- Pipeline: <!-- NARRATIVE: v2_src tag, rescue lanes run, "
          "validation status -->",
          "",
          "## Corrections applied during this ingest",
          "",
          "<!-- NARRATIVE: merge fixes, contradiction flips, dedups — or 'none' -->",
          "",
          BOILERPLATE,
          "## Game flow (score changes)",
          "",
          score_flow(rows),
          ""]
    for side, team in (("L", TEAM_L), ("R", TEAM_R)):
        md += [f"## {team} — pre-snap adjustments & disguise",
               "",
               adjustment_splits(rows, side, team),
               "",
               f"### {team} scout notes",
               "",
               f"<!-- NARRATIVE: what {team}'s tendencies mean, keyed to the "
               "digest below; football-iq.md is the interpretation authority -->",
               ""]
    md += ["## Tendency digest (splits.py, verbatim)",
           "",
           "```",
           digest.rstrip(),
           "```",
           "",
           "## What to fix",
           "",
           "<!-- NARRATIVE: action items for the user's own play -->",
           ""]
    out = os.path.join(GAMEDIR, "report_skeleton.md")
    open(out, "w").write("\n".join(md))
    print(f"skeleton -> {out} ({len(rows)} windows, {charted} charted)")


if __name__ == "__main__":
    main()
