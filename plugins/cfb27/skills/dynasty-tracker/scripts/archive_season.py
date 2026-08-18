#!/usr/bin/env python3
"""Archive a completed dynasty season: snapshot, clear recruiting, age roster, roll to next year.

Usage:
    python3 archive_season.py <dynasty-slug> <year> [--allow-stragglers] [--dry-run] [--vault PATH]

Both positional args are required — the script refuses to run without them.

Preflight (aborts non-zero, with a report, if any fail):
  1. Every recruit with status: signed appears by name in roster.md.
  2. Every recruit has a terminal status (signed | flipped | lost). Non-terminal "stragglers"
     abort the run unless --allow-stragglers is passed. (Scripts can't prompt interactively;
     this flag is the "warn-and-confirm" from the plan.)
  3. seasons/<year>.md exists with a non-empty `record`.

Then:
  4. Copy roster.md -> archive/<year>/roster-snapshot.md; copy recruiting/** ->
     archive/<year>/recruiting-snapshot/, setting archived: true on every copied recruit note.
  5. Generate archive/<year>/league-snapshot.md from h2h.md + rival team notes.
  6. Clear recruiting/high-school/ and recruiting/portal/; reset team-needs.md from template.
  7. Age roster classes (FR->SO->JR->SR); mark existing SRs Status: review (never deleted).
  8. Bump current_season in _dynasty.md; create seasons/<year+1>.md from template.
  9. Print a summary of every action.

--dry-run prints the plan without writing anything. Standard library only.
"""
import argparse
import re
import sys
from pathlib import Path

TERMINAL = {"signed", "flipped", "lost"}
CLASS_NEXT = {"FR": "SO", "SO": "JR", "JR": "SR"}

TEAM_NEEDS_TEMPLATE = """# Team Needs — {team}

_Reset at season archive. One `##` section per position group: a priority line + notes._

## QB
Priority:
Notes:

## RB
Priority:
Notes:

## WR
Priority:
Notes:

## TE
Priority:
Notes:

## OL
Priority:
Notes:

## DL
Priority:
Notes:

## EDGE
Priority:
Notes:

## LB
Priority:
Notes:

## CB
Priority:
Notes:

## S
Priority:
Notes:

## Special Teams
Priority:
Notes:
"""

SEASON_TEMPLATE = """---
type: season
dynasty: {slug}
year: {year}
record: ""
postseason: ""
---

# {team} — {year} Season

## Results

| Week | Opponent | H/A | W/L | Score | Notes |
| --- | --- | --- | --- | --- | --- |

## Narrative

"""


# --------------------------------------------------------------------------- helpers

def clean_value(val: str) -> str:
    val = val.strip()
    if not val:
        return val
    if val[0] in "\"'":
        q = val[0]
        end = val.find(q, 1)
        return val[1:end] if end != -1 else val[1:]
    hp = val.find(" #")
    if hp != -1:
        val = val[:hp].strip()
    return val


def parse_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    block, body = m.group(1), m.group(2)
    data = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        km = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if km:
            data[km.group(1)] = clean_value(km.group(2))
    return data, body


def set_frontmatter_field(text: str, key: str, value: str) -> str:
    """Set/replace a scalar field inside the frontmatter block; append if absent."""
    m = re.match(r"^(---\n)(.*?)(\n---\n?)(.*)$", text, re.S)
    if not m:
        return text
    start, block, end, body = m.groups()
    lines = block.split("\n")
    pat = re.compile(rf"^(\s*){re.escape(key)}:\s*.*$")
    for i, line in enumerate(lines):
        mm = pat.match(line)
        if mm:
            lines[i] = f"{mm.group(1)}{key}: {value}"
            break
    else:
        lines.append(f"{key}: {value}")
    return start + "\n".join(lines) + end + body


def split_sections(text: str):
    """Split markdown body into (heading_text, [body_lines]) by `## ` headings."""
    sections, cur, cur_lines = [], None, []
    for line in text.splitlines():
        hm = re.match(r"^##\s+(.*)$", line)
        if hm:
            if cur is not None:
                sections.append((cur, cur_lines))
            cur, cur_lines = hm.group(1).strip(), []
        elif cur is not None:
            cur_lines.append(line)
    if cur is not None:
        sections.append((cur, cur_lines))
    return sections


def roster_names(roster_text: str):
    names = set()
    for line in roster_text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if not first or first.lower() == "name" or re.match(r"^:?-+:?$", first):
            continue
        names.add(first)
    return names


# --------------------------------------------------------------------------- plan

class Plan:
    def __init__(self, vault: Path, dry_run: bool):
        self.vault = vault
        self.dry_run = dry_run
        self.actions = []

    def _rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.vault).as_posix()
        except ValueError:
            return str(path)

    def mkdir(self, path: Path):
        self.actions.append(f"mkdir   {self._rel(path)}/")
        if not self.dry_run:
            path.mkdir(parents=True, exist_ok=True)

    def write(self, path: Path, content: str, verb="write"):
        self.actions.append(f"{verb:<7} {self._rel(path)}")
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def remove(self, path: Path):
        self.actions.append(f"remove  {self._rel(path)}")
        if not self.dry_run:
            path.unlink()


# --------------------------------------------------------------------------- main

def run(slug: str, year: int, allow_stragglers: bool, dry_run: bool, vault: Path) -> int:
    dyn = vault / "dynasties" / slug
    if not dyn.is_dir():
        print(f"ERROR: dynasty folder not found: {dyn}")
        return 1

    roster_path = dyn / "roster.md"
    recruiting_dir = dyn / "recruiting"
    season_path = dyn / "seasons" / f"{year}.md"
    dynasty_hub = dyn / "_dynasty.md"

    if not roster_path.is_file():
        print(f"ERROR: roster.md not found: {roster_path}")
        return 1

    roster_text = roster_path.read_text(encoding="utf-8")

    # collect recruit notes (high-school + portal, live board only)
    recruits = []
    for sub in ("high-school", "portal"):
        d = recruiting_dir / sub
        if d.is_dir():
            for f in sorted(d.glob("*.md")):
                fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                if fm.get("type") == "recruit":
                    recruits.append((f, fm))

    # ---- preflight -------------------------------------------------------
    failures = []

    rnames = {n.lower() for n in roster_names(roster_text)}
    missing_signed = [
        fm.get("name", f.stem) for f, fm in recruits
        if fm.get("status") == "signed" and fm.get("name", "").strip().lower() not in rnames
    ]
    if missing_signed:
        failures.append(
            "Preflight 1 FAILED — signed recruits missing from roster.md:\n    - "
            + "\n    - ".join(missing_signed)
        )

    stragglers = [
        f"{fm.get('name', f.stem)} (status: {fm.get('status', 'none')})"
        for f, fm in recruits
        if fm.get("status") not in TERMINAL
    ]
    if stragglers and not allow_stragglers:
        failures.append(
            "Preflight 2 FAILED — recruits without a terminal status "
            "(pass --allow-stragglers to proceed anyway):\n    - "
            + "\n    - ".join(stragglers)
        )

    if not season_path.is_file():
        failures.append(f"Preflight 3 FAILED — season log not found: {season_path.relative_to(vault)}")
    else:
        sfm, _ = parse_frontmatter(season_path.read_text(encoding="utf-8"))
        if not sfm.get("record", "").strip():
            failures.append(
                f"Preflight 3 FAILED — {season_path.relative_to(vault)} has an empty `record` "
                "(fill in the season record before archiving)"
            )

    if failures:
        print(f"ABORTING archive of {slug} {year} — preflight failed:\n")
        for f in failures:
            print(f)
            print()
        return 1

    if stragglers and allow_stragglers:
        print(f"WARNING: proceeding with {len(stragglers)} non-terminal recruit(s) (--allow-stragglers).\n")

    # ---- execute ---------------------------------------------------------
    plan = Plan(vault, dry_run)
    team = ""
    if dynasty_hub.is_file():
        team = parse_frontmatter(dynasty_hub.read_text(encoding="utf-8"))[0].get("team", "")
    team = team or slug.replace("-", " ").title()

    archive_dir = dyn / "archive" / str(year)
    plan.mkdir(archive_dir)

    # 4. snapshot roster + recruiting (archived: true on recruit copies)
    plan.write(archive_dir / "roster-snapshot.md", roster_text, verb="snap")

    recruiting_snap = archive_dir / "recruiting-snapshot"
    copied_recruits = 0
    if recruiting_dir.is_dir():
        for src in sorted(recruiting_dir.rglob("*.md")):
            dst = recruiting_snap / src.relative_to(recruiting_dir)
            content = src.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(content)
            if fm.get("type") == "recruit":
                content = set_frontmatter_field(content, "archived", "true")
                copied_recruits += 1
            plan.write(dst, content, verb="snap")

    # 5. league snapshot from h2h.md + rival notes
    plan.write(archive_dir / "league-snapshot.md",
               build_league_snapshot(dyn, slug, year, team), verb="snap")

    # 6. clear live recruiting boards; reset team-needs.md
    cleared = 0
    for sub in ("high-school", "portal"):
        d = recruiting_dir / sub
        if d.is_dir():
            for f in sorted(d.glob("*.md")):
                plan.remove(f)
                cleared += 1
    team_needs = recruiting_dir / "team-needs.md"
    plan.write(team_needs, TEAM_NEEDS_TEMPLATE.format(team=team), verb="reset")

    # 7. age roster classes; SRs -> Status review
    new_roster, aged, flagged = age_roster(roster_text)
    plan.write(roster_path, new_roster, verb="age")

    # 8. bump current_season; create next season log
    if dynasty_hub.is_file():
        hub_text = dynasty_hub.read_text(encoding="utf-8")
        plan.write(dynasty_hub, set_frontmatter_field(hub_text, "current_season", str(year + 1)), verb="bump")
    else:
        plan.actions.append(f"SKIP    _dynasty.md not found — current_season not bumped")

    next_season = dyn / "seasons" / f"{year + 1}.md"
    if next_season.is_file():
        plan.actions.append(f"SKIP    seasons/{year + 1}.md already exists — not overwritten")
    else:
        plan.write(next_season, SEASON_TEMPLATE.format(slug=slug, year=year + 1, team=team), verb="new")

    # 9. summary
    header = "DRY RUN — no files written\n" if dry_run else ""
    print(
        f"{header}Archived {team} ({slug}) season {year} -> live season {year + 1}\n"
        f"  recruit notes snapshotted (archived: true): {copied_recruits}\n"
        f"  live recruiting notes cleared:              {cleared}\n"
        f"  roster rows aged up:                        {aged}\n"
        f"  seniors flagged Status: review:             {flagged}\n"
    )
    print("Actions:")
    for a in plan.actions:
        print("  " + a)
    return 0


def build_league_snapshot(dyn: Path, slug: str, year: int, team: str) -> str:
    h2h_path = dyn / "league" / "h2h.md"
    teams_dir = dyn / "league" / "teams"
    h2h_sections = []
    if h2h_path.is_file():
        _, h2h_body = parse_frontmatter(h2h_path.read_text(encoding="utf-8"))
        h2h_sections = split_sections(h2h_body)

    lines = [
        f"# {team} — League Snapshot (end of {year})",
        "",
        f"_Compiled from league/h2h.md and league/teams/ notes at the close of the {year} season._",
        "",
    ]
    rivals = sorted(teams_dir.glob("*.md")) if teams_dir.is_dir() else []
    if not rivals:
        lines.append("_No rival team notes found._")
    for rf in rivals:
        fm, body = parse_frontmatter(rf.read_text(encoding="utf-8"))
        rteam = fm.get("team", rf.stem)
        person = fm.get("controlled_by", "?")
        lines.append(f"## {rteam} — controlled by {person}")
        # find a matching h2h section (heading mentions the person or team)
        tally = None
        for heading, hlines in h2h_sections:
            hl = heading.lower()
            if person.lower() in hl or rteam.lower() in hl:
                for l in hlines:
                    if l.strip():
                        tally = l.strip()
                        break
                break
        lines.append(f"**H2H:** {tally}" if tally else "**H2H:** (no h2h.md section found)")
        # first couple of non-empty scheme/intel lines from the rival note
        intel = [l for l in body.splitlines() if l.strip() and not l.strip().startswith("#")][:3]
        if intel:
            lines.append("")
            lines.extend(intel)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def age_roster(roster_text: str):
    """Return (new_text, rows_aged, seniors_flagged). SRs keep class SR, Status -> review."""
    lines = roster_text.splitlines()
    header_idx = sep_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|"):
            if header_idx is None:
                header_idx = i
            elif sep_idx is None and is_separator(line):
                sep_idx = i
                break
    if header_idx is None or sep_idx is None:
        return roster_text, 0, 0  # no parseable table; leave untouched

    header_cells = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    lower = [c.lower() for c in header_cells]
    class_i = lower.index("class") if "class" in lower else None
    status_i = lower.index("status") if "status" in lower else None
    ncols = len(header_cells)

    aged = flagged = 0
    for i in range(sep_idx + 1, len(lines)):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != ncols or is_separator(line):
            continue
        if class_i is not None:
            cls = cells[class_i].upper()
            if cls == "SR":
                if status_i is not None:
                    cells[status_i] = "review"
                    flagged += 1
            elif cls in CLASS_NEXT:
                cells[class_i] = CLASS_NEXT[cls]
                aged += 1
        lines[i] = "| " + " | ".join(cells) + " |"
    return "\n".join(lines) + ("\n" if roster_text.endswith("\n") else ""), aged, flagged


def is_separator(row: str) -> bool:
    cells = row.strip().strip("|").split("|")
    return bool(cells) and all(re.match(r"^\s*:?-+:?\s*$", c) for c in cells)


def default_vault() -> str:
    # script lives at <vault>/.claude/skills/dynasty-tracker/scripts/archive_season.py
    return str(Path(__file__).resolve().parents[4])


def main() -> int:
    p = argparse.ArgumentParser(
        description="Archive a completed dynasty season (snapshot, clear recruiting, age roster, roll year)."
    )
    p.add_argument("dynasty", help="dynasty slug, e.g. stanford")
    p.add_argument("year", type=int, help="the season year that just finished, e.g. 2026")
    p.add_argument("--allow-stragglers", action="store_true",
                   help="proceed even if some recruits lack a terminal status")
    p.add_argument("--dry-run", action="store_true", help="print the plan without writing")
    p.add_argument("--vault", default=None, help="vault root (default: derived from script location)")
    args = p.parse_args()
    vault = Path(args.vault).resolve() if args.vault else Path(default_vault())
    return run(args.dynasty, args.year, args.allow_stragglers, args.dry_run, vault)


if __name__ == "__main__":
    sys.exit(main())
