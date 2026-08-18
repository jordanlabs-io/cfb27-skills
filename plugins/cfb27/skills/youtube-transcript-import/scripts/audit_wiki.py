#!/usr/bin/env python3
"""Audit wiki pages against source transcripts: wikilink resolution + citation timestamps.

Usage: python3 audit_wiki.py <project-root> [--snap]

Assumes <project-root>/transcripts/ (sources) and <project-root>/wiki/ (pages).

Checks every wiki .md file:
- YAML frontmatter present
- every [[wikilink]] resolves to a transcript or wiki page (by filename, Obsidian-style)
- every citation of the form [[transcript|...]] **[MM:SS]** (optionally a **[..]**–**[..]** range)
  points to a timestamp marker that actually exists at a paragraph start in that transcript
- non-index pages contain at least one timestamped citation

--snap: rewrite citations whose timestamp is within 20s of a real paragraph marker to that
marker (agents often cite raw SRT cue times; snapping preserves citeability). Larger misses
are never auto-fixed — they usually mean the citation is attributed to the wrong video and
must be re-verified against the source by whoever wrote the page.

Exit code 0 = clean, 1 = problems remain.
"""
import re
import sys
import glob
import os

CITE_RE = r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]\s*\*\*\[([0-9:]+)\]\*\*(?:\s*[–-]\s*\*\*\[([0-9:]+)\]\*\*)?"


def secs(ts: str) -> int:
    s = 0
    for p in ts.split(":"):
        s = s * 60 + int(p)
    return s


def main(root: str, snap: bool) -> int:
    transcripts = {
        os.path.splitext(os.path.basename(p))[0]: p
        for p in glob.glob(os.path.join(root, "transcripts", "**", "*.md"), recursive=True)
    }
    wiki_files = glob.glob(os.path.join(root, "wiki", "**", "*.md"), recursive=True)
    # keyed by relative path (not bare basename): multiple identically-named files
    # (e.g. every folder's _index.md) would otherwise collide on one dict key and
    # silently drop all but one from every check below.
    wiki_pages = {
        os.path.relpath(os.path.splitext(p)[0], os.path.join(root, "wiki")): p
        for p in wiki_files
    }
    # wikilinks may target a bare filename (Obsidian-style, e.g. [[recruiting]]) or a
    # folder-qualified path for same-named files like [[dynasty/_index|...]]
    known = set(transcripts) | set(wiki_pages) | {
        os.path.splitext(os.path.basename(p))[0] for p in wiki_files
    } | {
        # user-approved non-transcript sources (e.g. sources/web/...) may be
        # wikilinked from wiki pages; Obsidian resolves these basenames vault-wide
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(root, "sources", "**", "*.md"), recursive=True)
    }
    marks = {
        n: sorted({m for m in re.findall(r"\*\*\[([0-9:]+)\]\*\*", open(p).read())}, key=secs)
        for n, p in transcripts.items()
    }

    problems, snapped, total = [], 0, 0
    for name, path in sorted(wiki_pages.items()):
        text = open(path).read()
        rel = os.path.relpath(path, root)
        if not text.startswith("---"):
            problems.append(f"{rel}: missing frontmatter")
        for link in re.findall(r"\[\[([^\]|#]+)", text):
            if link.strip() not in known:
                problems.append(f"{rel}: unresolvable wikilink [[{link.strip()}]]")

        def check_or_snap(m):
            nonlocal total, snapped
            tgt = m.group(1).strip()
            chunk = m.group(0)
            if tgt not in marks:
                return chunk  # link to another wiki page, not a citation
            tmarks, tsecs = marks[tgt], [secs(x) for x in marks[tgt]]

            def fix_ts(tm):
                nonlocal total, snapped
                ts = tm.group(1)
                total += 1
                if ts in tmarks:
                    return tm.group(0)
                sv = secs(ts)
                best = min(range(len(tsecs)), key=lambda i: abs(tsecs[i] - sv))
                delta = tsecs[best] - sv
                if snap and abs(delta) <= 20:
                    snapped += 1
                    return f"**[{tmarks[best]}]**"
                problems.append(
                    f"{rel}: [[{tgt}]] cites [{ts}] — no such marker "
                    f"(nearest {tmarks[best]}, delta {delta:+d}s"
                    + ("; would snap with --snap" if abs(delta) <= 20 else "; RE-VERIFY ATTRIBUTION")
                    + ")"
                )
                return tm.group(0)

            return re.sub(r"\*\*\[([0-9:]+)\]\*\*", fix_ts, chunk)

        new_text = re.sub(CITE_RE, check_or_snap, text)
        if new_text != text:
            open(path, "w").write(new_text)
        if "_index" not in name and name != "CHANGELOG" and "**[" not in text and name not in transcripts:
            problems.append(f"{rel}: no timestamped citations")

    print(f"wiki pages: {len(wiki_pages)} | citations checked: {total} | snapped: {snapped}")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    print("all clean: links resolve, every citation hits a real paragraph marker")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--snap"]
    sys.exit(main(args[0] if args else ".", "--snap" in sys.argv))
