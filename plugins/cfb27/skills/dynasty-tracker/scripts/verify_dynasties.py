#!/usr/bin/env python3
"""Verify dynasty tracker data integrity under dynasties/.

Usage: python3 verify_dynasties.py [vault-root]

Default vault-root is the script's great-great-grandparent (script lives at
.claude/skills/dynasty-tracker/scripts/). Checks every .md file under dynasties/:

- Frontmatter enums valid:
    type     in dynasty | recruit | rival-team | season
    status   in targeting | committed | signed | flipped | lost   (recruits)
    source   in high-school | portal                               (recruits)
    priority in high | medium | low                                (recruits)
    mode     in online | offline                                   (dynasty hub)
- `dynasty:` frontmatter matches the containing dynasty folder name.
- numeric frontmatter values (season, year, week, ranks, NIL, coach level, ...) are ints.
- roster.md / h2h.md / season-log (and any other) markdown tables are well-formed:
  a header row, a separator row, and every row the same column count as the header.
- Path-qualified wikilinks inside dynasties/ resolve to a real vault file
  (bare wikilinks resolve Obsidian-style by filename; links into wiki/ are allowed).
- Live recruiting/ notes never carry `archived: true`; recruit copies under archive/ always do.

Prints per-file findings + a summary count. Exit 0 = clean, 1 = problems.
If dynasties/ does not exist yet or is empty, exits 0 with a note (the structure may
not have been built yet — that is not an error).
"""
import os
import re
import sys
from pathlib import Path

TYPE_ENUM = {"dynasty", "recruit", "rival-team", "season", "standings", "coach-state"}
STATUS_ENUM = {"targeting", "committed", "signed", "flipped", "lost"}
SOURCE_ENUM = {"high-school", "portal"}
PRIORITY_ENUM = {"high", "medium", "low"}
MODE_ENUM = {"online", "offline"}
# Recruiting-board state as the game displays it. "unknown" is always legal:
# an unread screen must never force a guess.
BOARD_STATUS_ENUM = {"open", "top5", "top3", "verbal", "committed", "unknown"}
LOCK_ENUM = {"none", "locked", "locked-out", "dealbreaker", "unknown"}
# Where our program sits in the recruit's own top-schools list.
STANDING_ENUM = {"leader", "top3", "top5", "listed", "absent", "unknown"}
# Scouted reveal. Only the recruit card's Scouting sub-tab shows this; any capture
# that never opened that tab is legitimately "unknown" for every prospect.
SCOUT_GRADE_ENUM = {"gem", "normal", "bust", "unknown"}
# Numeric frontmatter. Validated only when present; all are optional.
INT_FIELDS = (
    "season", "year", "week", "stars", "nat_rank", "pos_rank", "state_rank",
    "nil_value", "offer", "interest_rank", "hours", "height_in", "weight_lb",
    "level", "skill_points", "gold",
    "race_rank", "race_size", "race_cutoff", "scouting_pct", "ovr",
)


def clean_value(val: str) -> str:
    """Strip a scalar YAML value: unwrap one layer of quotes, else drop an inline comment."""
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
    """Return (frontmatter dict of scalar fields, body) — regex-based, no PyYAML."""
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


def is_int(val: str) -> bool:
    try:
        int(str(val).strip())
        return True
    except (ValueError, TypeError):
        return False


def split_cells(row: str) -> list:
    """Split a markdown table row into cells.

    An escaped pipe (\\|) is literal content inside a cell -- verbatim game
    transcriptions use it constantly ("5-3 (3-2) \\| 5TH IN SEC"). Counting it
    as a separator reports a malformed table for data that is perfectly fine,
    and the only way to "fix" that is to edit the evidence. So: neutralise
    escaped pipes before splitting.
    """
    return row.strip().replace("\\|", "\x00").strip("|").split("|")


def count_cols(row: str) -> int:
    return len(split_cells(row))


def is_separator(row: str) -> bool:
    cells = split_cells(row)
    return bool(cells) and all(re.match(r"^\s*:?-+:?\s*$", c) for c in cells)


def check_tables(text: str, rel: str, problems: list):
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if lines[i].strip().startswith("|"):
            block, j = [], i
            while j < n and lines[j].strip().startswith("|"):
                block.append(lines[j])
                j += 1
            # only treat as a real table if a separator row follows the header
            if len(block) >= 2 and is_separator(block[1]):
                hcols = count_cols(block[0])
                for k, row in enumerate(block):
                    c = count_cols(row)
                    if c != hcols:
                        problems.append(
                            f"{rel}: malformed table — row {k + 1} has {c} column(s), "
                            f"header has {hcols}"
                        )
            i = j
        else:
            i += 1


def link_targets(text: str):
    for raw in re.findall(r"\[\[([^\]|#]+)", text):
        t = raw.strip()
        if t:
            yield t


def main(vault: str) -> int:
    vault = Path(vault).resolve()
    dyn_dir = vault / "dynasties"
    if not dyn_dir.is_dir():
        print(f"dynasties/ not found under {vault} — nothing to verify (structure not built yet)")
        return 0

    dyn_files = sorted(dyn_dir.rglob("*.md"))
    if not dyn_files:
        print("dynasties/ is empty — nothing to verify (structure not built yet)")
        return 0

    # Resolution sets for wikilinks: every non-hidden file in the vault (not just .md —
    # dynasty notes legitimately link to .base files, images, etc.). Obsidian resolves a
    # bare link by basename (with or without extension) and a path-qualified link by path
    # (with or without a trailing .md).
    all_files = [
        p for p in vault.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(vault).parts)
    ]
    names = {p.name for p in all_files}
    stems = {p.stem for p in all_files}
    relpaths_full = {p.relative_to(vault).as_posix() for p in all_files}
    relpaths_noext = {p.relative_to(vault).with_suffix("").as_posix() for p in all_files}

    problems = []
    for path in dyn_files:
        rel = path.relative_to(vault).as_posix()
        text = path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        parts = path.relative_to(dyn_dir).parts  # e.g. ('stanford','recruiting','hs','x.md')
        dynasty_folder = parts[0] if len(parts) >= 2 else None
        under_archive = "archive" in parts

        # --- enum checks ---
        # _index.md is a structural navigation file, not one of the four data entities —
        # exempt it from the type enum (mirrors audit_wiki.py's _index/CHANGELOG exemption).
        if path.name != "_index.md" and "type" in fm and fm["type"] not in TYPE_ENUM:
            problems.append(f"{rel}: invalid type '{fm['type']}' (expected {sorted(TYPE_ENUM)})")
        if "status" in fm and fm["status"] not in STATUS_ENUM:
            problems.append(f"{rel}: invalid status '{fm['status']}' (expected {sorted(STATUS_ENUM)})")
        if "source" in fm and fm["source"] not in SOURCE_ENUM:
            problems.append(f"{rel}: invalid source '{fm['source']}' (expected {sorted(SOURCE_ENUM)})")
        if "priority" in fm and fm["priority"] not in PRIORITY_ENUM:
            problems.append(f"{rel}: invalid priority '{fm['priority']}' (expected {sorted(PRIORITY_ENUM)})")
        if "mode" in fm and fm["mode"] not in MODE_ENUM:
            problems.append(f"{rel}: invalid mode '{fm['mode']}' (expected {sorted(MODE_ENUM)})")
        if "board_status" in fm and fm["board_status"] not in BOARD_STATUS_ENUM:
            problems.append(f"{rel}: invalid board_status '{fm['board_status']}' (expected {sorted(BOARD_STATUS_ENUM)})")
        if "lock" in fm and fm["lock"] not in LOCK_ENUM:
            problems.append(f"{rel}: invalid lock '{fm['lock']}' (expected {sorted(LOCK_ENUM)})")
        if "unc_standing" in fm and fm["unc_standing"] not in STANDING_ENUM:
            problems.append(f"{rel}: invalid unc_standing '{fm['unc_standing']}' (expected {sorted(STANDING_ENUM)})")
        if "scout_grade" in fm and fm["scout_grade"] not in SCOUT_GRADE_ENUM:
            problems.append(f"{rel}: invalid scout_grade '{fm['scout_grade']}' (expected {sorted(SCOUT_GRADE_ENUM)})")
        if "scouting_pct" in fm and is_int(fm["scouting_pct"]) and not 0 <= int(fm["scouting_pct"]) <= 100:
            problems.append(f"{rel}: scouting_pct {fm['scouting_pct']} out of range 0-100")
        # p_tier is the pipeline pin: 1-5 only. Anything else is a misread magenta 5
        # (see dynasty-tracker/SKILL.md and dynasties/_wiki/recruiting/pipelines.md).
        if "p_tier" in fm and str(fm["p_tier"]) != "unknown":
            v = str(fm["p_tier"])
            if not (v.isdigit() and 1 <= int(v) <= 5):
                problems.append(
                    f"{rel}: p_tier {fm['p_tier']!r} outside 1-5 — re-read the pin's colour "
                    f"(bronze 1, silver 2, gold 3, teal 4, magenta 5); 6/8/9/B/S are misread 5s")
        # A race rank you cannot place inside its own field is a transcription slip,
        # not a judgement call -- catch it here rather than in a Bases view.
        if is_int(fm.get("race_rank")) and is_int(fm.get("race_size")) and int(fm["race_rank"]) > int(fm["race_size"]):
            problems.append(f"{rel}: race_rank {fm['race_rank']} exceeds race_size {fm['race_size']}")

        # --- dynasty field matches containing folder ---
        if "dynasty" in fm and dynasty_folder and fm["dynasty"] != dynasty_folder:
            problems.append(
                f"{rel}: dynasty '{fm['dynasty']}' does not match containing folder '{dynasty_folder}'"
            )

        # --- numeric frontmatter must be ints (all optional; checked if present) ---
        for field in INT_FIELDS:
            if field in fm and not is_int(fm[field]):
                problems.append(f"{rel}: {field} '{fm[field]}' is not an integer")

        # --- table well-formedness ---
        check_tables(text, rel, problems)

        # --- archived flag rules (recruits only) ---
        if fm.get("type") == "recruit":
            archived_true = fm.get("archived", "").lower() == "true"
            in_live_recruiting = "recruiting" in parts and not under_archive
            if in_live_recruiting and archived_true:
                problems.append(f"{rel}: live recruiting note must not have archived: true")
            if under_archive and not archived_true:
                problems.append(f"{rel}: archived recruit copy must have archived: true")

        # --- wikilink resolution ---
        for t in link_targets(text):
            if "/" in t:
                resolved = t in relpaths_full or t in relpaths_noext
            else:
                resolved = t in names or t in stems
            if not resolved:
                problems.append(f"{rel}: unresolvable wikilink [[{t}]]")

    dynasties = sorted({p.relative_to(dyn_dir).parts[0] for p in dyn_files if len(p.relative_to(dyn_dir).parts) >= 2})
    print(f"checked {len(dyn_files)} dynasty note(s) across {len(dynasties)} dynasty folder(s): {', '.join(dynasties) or '(none)'}")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    print("all clean: enums valid, dynasty fields match folders, tables well-formed, links resolve, archive flags correct")
    return 0


def default_vault() -> str:
    # script lives at <vault>/.claude/skills/dynasty-tracker/scripts/verify_dynasties.py
    return str(Path(__file__).resolve().parents[4])


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    sys.exit(main(args[0] if args else default_vault()))
