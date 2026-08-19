#!/usr/bin/env python3
"""Verify dynasties/_wiki/ — the canonical game-knowledge section.

Usage:  verify_wiki.py <vault>

`_wiki/` holds knowledge that is true in EVERY save, so it needs invariants the
per-dynasty verifier does not enforce. Its whole value is that a claim can be
traced back to something — an external reference page, or a capture frame — so the
citation fields are what this script exists to protect.

Two source lanes, declared per page by `source_class`:

  external   scraped from a reference site  -> requires `sources:` with >=1 URL
  capture    read off the user's own screens -> requires `capture:` + `frames:`

A page that declares neither, or declares one and satisfies the other, fails.
`_index.md` is the section TOC and is exempt from the per-page fields; it is
instead checked for two-way linkage against every page in the tree.
"""
import re
import sys
from pathlib import Path

GAME_CONTEXT = {"cfb27", "cfb26", "mixed"}
SOURCE_CLASS = {"external", "capture"}
ALWAYS = ("title", "kind", "retrieved")
PER_PAGE = ("section", "game_context", "confidence", "source_class")
FRAME_RE = re.compile(r"^f_\d{3,5}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
    """Return (scalars, list_fields, body). List fields are YAML `- item` blocks."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, {}, text
    block, body = m.group(1), m.group(2)
    scalars, lists, current = {}, {}, None
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\s+-\s+", line) and current:
            lists[current].append(line.split("-", 1)[1].strip())
            continue
        km = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if km:
            key, val = km.group(1), clean_value(km.group(2))
            if val == "":
                current, lists[key] = key, []
            else:
                current, scalars[key] = None, val
    return scalars, lists, body


def split_cells(row: str) -> list:
    return row.strip().replace("\\|", "\x00").strip("|").split("|")


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
                block.append(lines[j]); j += 1
            if len(block) >= 2 and is_separator(block[1]):
                hcols = len(split_cells(block[0]))
                for k, row in enumerate(block):
                    c = len(split_cells(row))
                    if c != hcols:
                        problems.append(f"{rel}: malformed table — row {k+1} has {c} "
                                        f"column(s), header has {hcols}")
            i = j
        else:
            i += 1


def main(vault_arg: str) -> int:
    vault = Path(vault_arg).resolve()
    root = vault / "dynasties" / "_wiki"
    if not root.is_dir():
        print(f"dynasties/_wiki/ not found under {vault} — nothing to verify")
        return 0

    pages = sorted(root.rglob("*.md"))
    index = root / "_index.md"
    problems = []
    all_names = {p.stem for p in vault.rglob("*.md")}

    for p in pages:
        rel = p.relative_to(vault).as_posix()
        text = p.read_text(encoding="utf-8")
        fm, lists, body = parse_frontmatter(text)
        if not fm and not lists:
            problems.append(f"{rel}: no frontmatter")
            continue

        for k in ALWAYS:
            if k not in fm:
                problems.append(f"{rel}: missing required field '{k}'")
        if fm.get("kind") and fm["kind"] != "canonical":
            problems.append(f"{rel}: kind '{fm['kind']}' — _wiki pages are kind: canonical")
        if fm.get("retrieved") and not DATE_RE.match(fm["retrieved"]):
            problems.append(f"{rel}: retrieved '{fm['retrieved']}' is not YYYY-MM-DD")

        check_tables(text, rel, problems)

        for raw in re.findall(r"\[\[([^\]|#]+)", text):
            t = raw.strip().split("/")[-1]
            if t and t not in all_names:
                problems.append(f"{rel}: wikilink [[{raw.strip()}]] does not resolve")
        for href in re.findall(r"\]\((?!https?:)([^)#]+)", text):
            if href.endswith(".md") and not (p.parent / href).resolve().exists():
                problems.append(f"{rel}: relative link '{href}' does not resolve")

        if p == index:
            continue

        for k in PER_PAGE:
            if k not in fm:
                problems.append(f"{rel}: missing required field '{k}'")
        if fm.get("game_context") and fm["game_context"] not in GAME_CONTEXT:
            problems.append(f"{rel}: game_context '{fm['game_context']}' not in "
                            f"{sorted(GAME_CONTEXT)}")
        conf = fm.get("confidence")
        if conf is not None and not (str(conf).isdigit() and 1 <= int(conf) <= 5):
            problems.append(f"{rel}: confidence '{conf}' out of range 1-5")
        sec = fm.get("section")
        folder = p.parent.name
        if sec and folder != "_wiki" and sec != folder:
            problems.append(f"{rel}: section '{sec}' does not match folder '{folder}'")

        cls = fm.get("source_class")
        if cls and cls not in SOURCE_CLASS:
            problems.append(f"{rel}: source_class '{cls}' not in {sorted(SOURCE_CLASS)}")
        elif cls == "external":
            urls = [s for s in lists.get("sources", []) if s.startswith("http")]
            if not urls:
                problems.append(f"{rel}: source_class external but no http(s) URL under 'sources:'")
        elif cls == "capture":
            if "capture" not in fm:
                problems.append(f"{rel}: source_class capture but no 'capture:' slug")
            frames = lists.get("frames", [])
            bad = [f for f in frames if not FRAME_RE.match(f)]
            if not frames:
                problems.append(f"{rel}: source_class capture but no 'frames:' list")
            elif bad:
                problems.append(f"{rel}: frames {bad} are not f_NNNN ids")

    # _index.md must link every page, and link nothing that is missing
    if index.exists():
        itext = index.read_text(encoding="utf-8")
        linked = {h.split("/")[-1] for h in re.findall(r"\]\((?!https?:)([^)#]+\.md)\)", itext)}
        linked |= {w.strip().split("/")[-1] + ".md" for w in re.findall(r"\[\[([^\]|#]+)", itext)}
        for p in pages:
            if p != index and p.name not in linked:
                problems.append(f"dynasties/_wiki/_index.md: does not link "
                                f"{p.relative_to(root).as_posix()}")
    else:
        problems.append("dynasties/_wiki/_index.md: missing section TOC")

    print(f"checked {len(pages)} canonical page(s) in dynasties/_wiki/")
    if problems:
        print(f"{len(problems)} problem(s):")
        for pr in problems:
            print("  - " + pr)
        return 1
    print("all clean: frontmatter valid, every page cites its source lane, "
          "links resolve, tables well-formed, TOC complete")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    sys.exit(main(args[0] if args else "."))
